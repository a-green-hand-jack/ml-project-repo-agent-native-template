#!/usr/bin/env python3
"""检查声明式能力目录（capability catalog）与真实能力面 + 生成 adapter 的一致性。

canonical 目录：`.agent/capability-catalog.toml`。每项正式 capability（agent / skill /
command / hook）在此登记（或有显式 exemption），并声明 inputs / outputs / validators /
human gates / path boundaries / adapters / completion contract。见 issue #28 与 DESIGN §10。

校验项：
1. 顶层 schema：`schema_version` 只接受当前支持版本（future fail loud）、`profile == research`。
2. chassis：catalog 只引用窄 lock artifact（`.agent/chassis-lock.toml`）的 lock_id/commit；
   validator 结构化加载 lock，要求 source/pin/paths/blob OID/compatibility 与 catalog 精确
   一致，且 lock 内 commit/blob 非全零、spec_version/兼容 major 落在本地支持范围——mismatch /
   missing / all-zero fake / future schema 全部失败。validator 不联网（lock 是 human-reviewed
   provenance owner）。
3. 每条 capability：必填字段齐全且非占位、`id` 唯一、`kind:name` 全局唯一（registered 与
   exempt 之间也不许重复）、`kind`/`status` 合法。
4. 登记齐全（missing）+ 无幽灵条目（unexpected）+ ghost exemption 失败。hook 正式面**结构化
   解析** settings.json / codex config 的 hooks 字段，从 command argv 解析 repo-local
   `.claude/hooks/<name>.py`；无法解析 / 越界 / 间接 shell 形式 **fail closed**（不 regex 扫
   注释或任意文本）。
5. adapter 内容 parity：复用 `sync-codex-adapters.py` 的 `expected_files()` 真实生成内容逐字比对。

无第三方依赖（仅 stdlib）。退出码 0 = 通过，1 = 有 error。
用法：python scripts/check-capability-catalog.py [--strict] [--self-test]
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import shlex
import sys
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CATALOG_REL = ".agent/capability-catalog.toml"
LOCK_REL = ".agent/chassis-lock.toml"

SUPPORTED_SCHEMA_VERSION = 1
SUPPORTED_CHASSIS_MAJOR = 1
SUPPORTED_CHASSIS_SPEC_VERSION = "v1"
REQUIRED_SPEC_PATHS = {
    "chassis/v1/spec.md",
    "chassis/v1/capability.schema.json",
    "compatibility/matrix.json",
}

VALID_KINDS = {"agent", "skill", "command", "hook"}
VALID_STATUS = {"registered", "exempt"}
DECLARATION_FIELDS = [
    "inputs", "outputs", "validators", "human_gates",
    "path_boundaries", "adapters", "completion_contract",
]
STRING_FIELDS = ["id", "kind", "name", "path", "status",
                 "inputs", "outputs", "path_boundaries", "completion_contract"]
LIST_FIELDS = ["validators", "human_gates", "adapters"]

OID_RE = re.compile(r"^[0-9a-f]{40}$")
SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
HOOK_TOKEN_RE = re.compile(r"\.claude/hooks/([A-Za-z0-9_]+)\.py$")
KNOWN_ROOT_PREFIXES = ("$CLAUDE_PROJECT_DIR/", "$(git rev-parse --show-toplevel)/")
_UNSET = object()


def _is_placeholder(value: str) -> bool:
    return not value.strip() or value.strip().startswith(("<", "TODO", "TBD", "unpinned"))


def _is_zero(oid: str) -> bool:
    return set(oid) == {"0"}


# --------------------------------------------------------------------------- #
# hook 结构化发现（只读真实 hooks 字段，从 argv 解析脚本，fail-closed）。
# --------------------------------------------------------------------------- #
def _settings_hook_commands(repo: Path) -> list[str] | None:
    f = repo / ".claude" / "settings.json"
    if not f.exists():
        return []
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    cmds: list[str] = []
    for groups in (data.get("hooks") or {}).values():
        if not isinstance(groups, list):
            continue
        for g in groups:
            for h in (g.get("hooks") or []):
                c = h.get("command")
                if isinstance(c, str):
                    cmds.append(c)
    return cmds


def _codex_hook_commands(repo: Path) -> list[str] | None:
    f = repo / ".codex" / "config.toml"
    if not f.exists():
        return []
    try:
        data = tomllib.loads(f.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError:
        return None
    cmds: list[str] = []
    for groups in (data.get("hooks") or {}).values():
        if not isinstance(groups, list):
            continue
        for g in groups:
            for h in (g.get("hooks") or []):
                c = h.get("command")
                if isinstance(c, str):
                    cmds.append(c)
    return cmds


def resolve_hook_ref(command: str, repo: Path) -> tuple[str | None, str | None]:
    """从单条 hook command 解析 repo-local hook 脚本名。

    返回 (name, error_reason)。非 hook-script 命令（如 ruff format）→ (None, None)。
    引用了 .claude/hooks 但无法安全解析（间接 shell / 越界 / 不可解析）→ (None, reason)。
    """
    try:
        argv = shlex.split(command)
    except ValueError:
        return (None, "hook command 无法 shlex 解析" if ".claude/hooks/" in command else None)
    if not argv:
        return (None, None)
    exe = os.path.basename(argv[0])
    if exe in {"bash", "sh", "zsh", "dash"} and any(a in ("-c", "-lc") for a in argv[1:]):
        # 间接 shell：hook 脚本藏在 -c 字符串里，无法静态确证 → fail closed。
        return (None, "间接 shell hook command（fail-closed）") if ".claude/hooks/" in command else (None, None)
    tokens = [t for t in argv if ".claude/hooks/" in t]
    if not tokens:
        return (None, None)
    if len(tokens) != 1:
        return (None, "hook command 含多个/歧义 hook 脚本 token")
    tok = tokens[0]
    for prefix in KNOWN_ROOT_PREFIXES:
        if tok.startswith(prefix):
            tok = tok[len(prefix):]
            break
    if not re.fullmatch(r"\.claude/hooks/[A-Za-z0-9_]+\.py", tok):
        return (None, f"hook 脚本路径无法解析/越界（fail-closed）：{tokens[0]}")
    name = HOOK_TOKEN_RE.search(tok).group(1)
    if not (repo / ".claude" / "hooks" / f"{name}.py").exists():
        return (None, f"注册的 hook 脚本不存在：.claude/hooks/{name}.py")
    return (name, None)


def discover_canonical(repo: Path, errors: list[str] | None = None) -> dict[str, str]:
    """扫描真实能力面。hook 结构化解析注册表面，fail-closed 错误写入 errors（若提供）。"""
    found: dict[str, str] = {}
    for md in sorted((repo / ".claude" / "agents").glob("*.md")):
        found[f"agent:{md.stem}"] = f".claude/agents/{md.name}"
    skills_dir = repo / ".claude" / "skills"
    if skills_dir.is_dir():
        for d in sorted(p for p in skills_dir.iterdir() if p.is_dir()):
            if (d / "SKILL.md").exists():
                found[f"skill:{d.name}"] = f".claude/skills/{d.name}/SKILL.md"
    for md in sorted((repo / ".claude" / "commands").glob("*.md")):
        found[f"command:{md.stem}"] = f".claude/commands/{md.name}"
    for label, getter in (("settings.json", _settings_hook_commands),
                          ("codex/config.toml", _codex_hook_commands)):
        cmds = getter(repo)
        if cmds is None:
            if errors is not None:
                errors.append(f"hook 注册配置解析失败（{label}）—— fail closed")
            continue
        for c in cmds:
            name, reason = resolve_hook_ref(c, repo)
            if reason and errors is not None:
                errors.append(f"hook 注册命令无法安全解析（{label}）：{reason}")
            elif name:
                found[f"hook:{name}"] = f".claude/hooks/{name}.py"
    return found


def expected_adapters(kind: str, name: str) -> list[str]:
    if kind == "agent":
        return [f".codex/agents/{name}.toml"]
    if kind == "skill":
        return [f".agents/skills/{name}/SKILL.md"]
    if kind == "command":
        return [f".agents/skills/command-{name}/SKILL.md"]
    return []


def _canonical_path_for(kind: str, name: str) -> str:
    if kind == "agent":
        return f".claude/agents/{name}.md"
    if kind == "skill":
        return f".claude/skills/{name}/SKILL.md"
    if kind == "command":
        return f".claude/commands/{name}.md"
    return f".claude/hooks/{name}.py"


def load_sync_expected(repo: Path) -> dict[str, str] | None:
    spec_path = repo / "scripts" / "sync-codex-adapters.py"
    if not spec_path.exists():
        return None
    spec = importlib.util.spec_from_file_location("_sync_codex_adapters_probe", spec_path)
    if spec is None or spec.loader is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
        return {p.relative_to(mod.REPO).as_posix(): c for p, c in mod.expected_files().items()}
    except Exception:  # noqa: BLE001
        return None


def load_chassis_lock(repo: Path) -> dict | None:
    f = repo / LOCK_REL
    if not f.exists():
        return None
    try:
        return tomllib.loads(f.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError:
        return None


def _check_top_level(data: dict, lock: dict | None, errors: list[str]) -> None:
    ver = data.get("schema_version")
    if not isinstance(ver, int):
        errors.append("顶层 schema_version 缺失或非整数")
    elif ver != SUPPORTED_SCHEMA_VERSION:
        errors.append(f"schema_version={ver} 非本地支持版本 {SUPPORTED_SCHEMA_VERSION}（future fail loud）")
    if data.get("profile") != "research":
        errors.append(f"顶层 profile 必须为 'research'，实际：{data.get('profile')!r}")
    _check_chassis(data.get("chassis_spec"), lock, errors)


def _check_chassis(chassis, lock: dict | None, errors: list[str]) -> None:
    if not isinstance(chassis, dict):
        errors.append("缺少 [chassis_spec]（应引用 chassis-lock）")
        return
    if not isinstance(lock, dict):
        errors.append(f"缺少/无法加载 chassis lock：{LOCK_REL}")
        return
    # lock 内部自洽 + 非全零 fake。
    commit = lock.get("commit")
    if not (isinstance(commit, str) and OID_RE.match(commit) and not _is_zero(commit)):
        errors.append("chassis-lock.commit 必须是 40 位非全零 commit OID")
    if lock.get("spec_version") != SUPPORTED_CHASSIS_SPEC_VERSION:
        errors.append(f"chassis-lock.spec_version 必须为 {SUPPORTED_CHASSIS_SPEC_VERSION!r}")
    blobs = lock.get("blobs")
    if not isinstance(blobs, dict) or set(blobs) != REQUIRED_SPEC_PATHS:
        errors.append(f"chassis-lock.blobs 路径集必须精确为 {sorted(REQUIRED_SPEC_PATHS)}")
    else:
        for rel, oid in blobs.items():
            if not (isinstance(oid, str) and OID_RE.match(oid) and not _is_zero(oid)):
                errors.append(f"chassis-lock.blobs['{rel}'] 必须是 40 位非全零 blob OID")
    compat = lock.get("compatibility")
    if not isinstance(compat, dict):
        errors.append("chassis-lock.compatibility 缺失")
    else:
        m = SEMVER_RE.match(compat.get("chassis")) if isinstance(compat.get("chassis"), str) else None
        if not m:
            errors.append("chassis-lock.compatibility.chassis 必须是 semver")
        elif int(m.group(1)) != SUPPORTED_CHASSIS_MAJOR:
            errors.append(f"chassis-lock chassis major={m.group(1)} 不在本地支持范围（{SUPPORTED_CHASSIS_MAJOR}）")
        if compat.get("status") != "supported":
            errors.append("chassis-lock.compatibility.status 必须为 'supported'")
    # catalog 引用与 lock 精确一致。
    if chassis.get("source") != lock.get("source"):
        errors.append("chassis_spec.source 与 lock 不一致")
    if chassis.get("pin") != commit:
        errors.append("chassis_spec.pin 必须精确等于 lock.commit")
    if chassis.get("lock_id") != lock.get("lock_id"):
        errors.append("chassis_spec.lock_id 与 lock 不一致")


def _check_entry(cap: dict, idx: int, errors: list[str]) -> tuple[str, str, str] | None:
    tag = cap.get("id") or f"#{idx}"
    ok = True
    for field in STRING_FIELDS:
        val = cap.get(field)
        if not isinstance(val, str) or _is_placeholder(val):
            errors.append(f"capability {tag}: 字段 {field} 缺失/占位/非字符串")
            ok = False
    for field in LIST_FIELDS:
        val = cap.get(field)
        if not isinstance(val, list):
            errors.append(f"capability {tag}: 字段 {field} 必须是列表")
            ok = False
        elif any(not isinstance(x, str) or not x.strip() for x in val):
            errors.append(f"capability {tag}: 字段 {field} 含空/非字符串项")
            ok = False
    for field in DECLARATION_FIELDS:
        if field not in cap:
            errors.append(f"capability {tag}: 缺少契约字段 {field}")
            ok = False
    kind, name, status = cap.get("kind"), cap.get("name"), cap.get("status")
    if kind not in VALID_KINDS:
        errors.append(f"capability {tag}: kind 非法：{kind!r}")
        ok = False
    if status not in VALID_STATUS:
        errors.append(f"capability {tag}: status 非法：{status!r}")
        ok = False
    if status == "exempt":
        reason = cap.get("exemption_reason")
        if not isinstance(reason, str) or _is_placeholder(reason):
            errors.append(f"capability {tag}: status=exempt 必须给出非占位 exemption_reason")
            ok = False
    if not ok or kind not in VALID_KINDS or not isinstance(name, str):
        return None
    return kind, name, status


def _check_adapter_parity(repo, key, kind, name, cap, expected_content, errors) -> None:
    declared = [a for a in cap.get("adapters", []) if isinstance(a, str)]
    expected = expected_adapters(kind, name)
    if sorted(declared) != sorted(expected):
        errors.append(f"capability {key}: adapters 声明 {declared} 与预期映射 {expected} 不一致")
    for adapter in expected:
        path = repo / adapter
        if not path.exists():
            errors.append(f"capability {key}: 预期 adapter 文件不存在：{adapter}")
            continue
        if expected_content is not None:
            want = expected_content.get(adapter)
            if want is None:
                errors.append(f"capability {key}: adapter 不在 sync 预期生成集：{adapter}")
            elif path.read_text(encoding="utf-8", errors="replace") != want:
                errors.append(f"capability {key}: adapter 生成内容 stale/不一致：{adapter}")


def validate(repo: Path, data: dict, expected_content=None, chassis_lock=_UNSET
             ) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    lock = load_chassis_lock(repo) if chassis_lock is _UNSET else chassis_lock
    _check_top_level(data, lock, errors)

    caps = data.get("capability") or []
    if not isinstance(caps, list):
        errors.append("[[capability]] 必须是表数组")
        return errors, warnings
    if expected_content is None:
        expected_content = load_sync_expected(repo)
        if expected_content is None:
            errors.append("无法复用 sync-codex-adapters.expected_files() 做内容 parity")

    seen_ids: set[str] = set()
    seen_keys: set[str] = set()
    registered: dict[str, dict] = {}
    exempt_keys: set[str] = set()
    for idx, cap in enumerate(caps):
        if not isinstance(cap, dict):
            errors.append(f"capability #{idx}: 不是表")
            continue
        cid = cap.get("id")
        if isinstance(cid, str):
            if cid in seen_ids:
                errors.append(f"capability id 重复：{cid}")
            seen_ids.add(cid)
        parsed = _check_entry(cap, idx, errors)
        if parsed is None:
            continue
        kind, name, status = parsed
        key = f"{kind}:{name}"
        if key in seen_keys:
            errors.append(f"capability kind:name 重复（registered/exempt 均不许）：{key}")
        seen_keys.add(key)
        if cap.get("path") != _canonical_path_for(kind, name):
            errors.append(f"capability {key}: path 与 kind/name 推出的 canonical 路径不一致")
        if status == "registered":
            registered[key] = cap
            _check_adapter_parity(repo, key, kind, name, cap, expected_content, errors)
        elif status == "exempt":
            exempt_keys.add(key)

    canonical = discover_canonical(repo, errors)
    for k, path in canonical.items():
        if k not in registered and k not in exempt_keys:
            errors.append(f"能力未登记进目录（missing）：{k}（{path}）")
    for k in registered:
        if k not in canonical:
            errors.append(f"registered 能力无对应 canonical 文件（unexpected）：{k}")
    for k in exempt_keys:
        if k not in canonical:
            errors.append(f"exempt 无对应 discovered canonical（ghost exemption）：{k}")
    return errors, warnings


def load_catalog(path: Path) -> dict:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def _run_real(strict: bool) -> int:
    catalog = REPO / CATALOG_REL
    if not catalog.exists():
        print(f"ERROR 缺少能力目录：{CATALOG_REL}")
        print("[check-capability-catalog] FAIL — 1 error(s), 0 warning(s)")
        return 1
    try:
        data = load_catalog(catalog)
    except tomllib.TOMLDecodeError as e:
        print(f"ERROR 能力目录 TOML 解析失败：{e}")
        print("[check-capability-catalog] FAIL — 1 error(s), 0 warning(s)")
        return 1
    errors, warnings = validate(REPO, data)
    for w in warnings:
        print(f"WARN  {w}")
    for e in errors:
        print(f"ERROR {e}")
    n_e, n_w = len(errors), len(warnings)
    status = "FAIL" if (n_e or (strict and n_w)) else "OK"
    n_caps = len(data.get("capability") or [])
    print(f"[check-capability-catalog] {status} — 登记 {n_caps} 项，{n_e} error(s), {n_w} warning(s)")
    return 1 if status == "FAIL" else 0


def _self_test() -> int:
    import tempfile

    ADAPTER = ".codex/agents/demo.toml"
    GOOD_CONTENT = {ADAPTER: "GENERATED-GOOD\n"}
    GOOD_LOCK = {
        "lock_id": "bridge-chassis-v1", "source": "org/bridge",
        "commit": "a" * 40, "spec_version": "v1",
        "blobs": {p: f"{i}" + "b" * 39 for i, p in enumerate(sorted(REQUIRED_SPEC_PATHS))},
        "compatibility": {"chassis": "1.0.0", "status": "supported"},
    }

    def good_cap(**over):
        cap = {"id": "agent.demo", "kind": "agent", "name": "demo",
               "path": ".claude/agents/demo.md", "status": "registered",
               "inputs": "x", "outputs": "y", "validators": ["scripts/v.py"],
               "human_gates": [], "path_boundaries": "owned only",
               "adapters": [ADAPTER], "completion_contract": "report"}
        cap.update(over)
        return cap

    def base_doc(caps):
        return {"schema_version": 1, "profile": "research",
                "chassis_spec": {"lock_id": "bridge-chassis-v1", "source": "org/bridge",
                                 "pin": "a" * 40, "lock": LOCK_REL},
                "capability": caps}

    failures: list[str] = []
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / ".claude" / "agents").mkdir(parents=True)
        (root / ".codex" / "agents").mkdir(parents=True)
        (root / ".claude" / "hooks").mkdir(parents=True)
        (root / ".claude" / "agents" / "demo.md").write_text("---\nname: demo\n---\n", "utf-8")
        (root / ".codex" / "agents" / "demo.toml").write_text("GENERATED-GOOD\n", "utf-8")

        def expect(label, doc, should_pass, ec=GOOD_CONTENT, lock=GOOD_LOCK):
            errs, _ = validate(root, doc, expected_content=ec, chassis_lock=lock)
            if (len(errs) == 0) != should_pass:
                failures.append(f"{label}: 期望 {'通过' if should_pass else '失败'}，errors={errs}")

        expect("good", base_doc([good_cap()]), True)
        expect("missing", base_doc([]), False)
        expect("unexpected", base_doc([good_cap(), good_cap(
            id="agent.ghost", name="ghost", path=".claude/agents/ghost.md",
            adapters=[".codex/agents/ghost.toml"])]), False)
        bad = good_cap(); bad.pop("completion_contract")
        expect("missing-field", base_doc([bad]), False)
        d = base_doc([good_cap()]); d["profile"] = "writing"; expect("wrong-profile", d, False)
        d = base_doc([good_cap()]); d["schema_version"] = 2; expect("future-schema", d, False)
        # chassis lock 门禁
        expect("chassis-missing-lock", base_doc([good_cap()]), False, lock=None)
        expect("chassis-zero-commit", base_doc([good_cap()]), False,
               lock={**GOOD_LOCK, "commit": "0" * 40})
        expect("chassis-future-major", base_doc([good_cap()]), False,
               lock={**GOOD_LOCK, "compatibility": {"chassis": "2.0.0", "status": "supported"}})
        d = base_doc([good_cap()]); d["chassis_spec"]["pin"] = "b" * 40
        expect("chassis-pin-mismatch", d, False)
        expect("adapter-mismatch", base_doc([good_cap(adapters=[".codex/agents/wrong.toml"])]), False)
        expect("adapter-stale", base_doc([good_cap()]), False, ec={ADAPTER: "GENERATED-NEW\n"})
        expect("exempt-no-reason", base_doc([good_cap(status="exempt")]), False)
        expect("ghost-exempt", base_doc([good_cap(), {
            "id": "skill.ghost", "kind": "skill", "name": "ghost",
            "path": ".claude/skills/ghost/SKILL.md", "status": "exempt",
            "exemption_reason": "made up", "inputs": "x", "outputs": "y",
            "validators": [], "human_gates": [], "path_boundaries": "n/a",
            "adapters": [], "completion_contract": "n/a"}]), False)
        expect("dup-key", base_doc([good_cap(), good_cap(
            id="agent.demo2", status="exempt", exemption_reason="dup test")]), False)

        # hook 结构化解析：直接单元断言。
        (root / ".claude" / "hooks" / "real.py").write_text("x\n", "utf-8")
        cases = [
            # false-positive：注释/无关字符串里出现路径但不是 hook token → 不解析、不误报。
            ('python3 "$CLAUDE_PROJECT_DIR/.claude/hooks/real.py"', "real", None),
            ("ruff format \"$CLAUDE_FILE_PATHS\" 2>/dev/null || true", None, None),
            ('echo "see .claude/hooks/notahook.py for details"', None, "fail"),  # 引用了路径但非直接调用
            # false-negative：间接 shell 隐藏脚本 → fail closed（reason 非空）。
            ('bash -c "python3 .claude/hooks/real.py"', None, "fail"),
            # 越界绝对路径 → fail closed。
            ('python3 "/etc/.claude/hooks/real.py"', None, "fail"),
        ]
        for cmd, want_name, want_fail in cases:
            name, reason = resolve_hook_ref(cmd, root)
            if want_name and name != want_name:
                failures.append(f"hook-resolve[{cmd}]: 期望 name={want_name}，得 {name!r}")
            if want_fail == "fail" and reason is None:
                failures.append(f"hook-resolve[{cmd}]: 期望 fail-closed reason，但为 None（name={name!r}）")
            if want_fail is None and want_name is None and (name or reason):
                failures.append(f"hook-resolve[{cmd}]: 期望静默跳过，得 name={name!r} reason={reason!r}")

    if failures:
        for f in failures:
            print(f"SELFTEST-FAIL {f}")
        print(f"[check-capability-catalog --self-test] FAIL — {len(failures)} case(s)")
        return 1
    print("[check-capability-catalog --self-test] OK — catalog 16 + hook-resolve 5 对抗场景全部符合预期")
    return 0


def main() -> int:
    if "--self-test" in sys.argv:
        return _self_test()
    return _run_real("--strict" in sys.argv)


if __name__ == "__main__":
    sys.exit(main())
