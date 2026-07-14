#!/usr/bin/env python3
"""检查声明式能力目录（capability catalog）与真实能力面 + 生成 adapter 的一致性。

canonical 目录：`.agent/capability-catalog.toml`。它把散落在
DESIGN/doctrine/skills/adapters 中的能力表面收敛成一份**声明式、可执行校验**的
contract：每项正式 capability（agent / skill / command / hook）都在此登记（或有显式
exemption），并声明 inputs / outputs / validators / human gates / path boundaries /
adapters / completion contract。见 issue #28 与 DESIGN.md §10。

校验项（结构性、机器可判定；不判断字段语义是否"写得对"）：
1. 顶层 schema：`schema_version`（int≥1）、`profile == "research"`、`chassis_spec`
   带 Bridge pin / compatibility 字段（消费 research-writing-bridge chassis-spec）。
2. 每条 capability：必填字段齐全且非占位、`id` 唯一、`kind`/`status` 合法。
3. **登记齐全**（missing）：`.claude/{agents,skills,commands,hooks}` 下每个正式能力
   都必须在目录里登记或标 exempt——canonical 存在但目录漏登 → 失败。
4. **无幽灵条目**（unexpected）：目录里登记的 registered 能力必须有对应 canonical 文件
   ——目录写了但 canonical 不存在 → 失败。
5. **adapter parity**：目录声明的 adapters 必须与 `scripts/sync-codex-adapters.py` 的
   canonical→adapter 映射一致，且 adapter 文件真实存在（agent→`.codex/agents/<name>.toml`、
   skill→`.agents/skills/<name>/SKILL.md`、command→`.agents/skills/command-<name>/SKILL.md`、
   hook→无 adapter，`adapters` 必须为空）。

对应 doctrine：`.agent/tool-skill-interface.md`（"没有索引的能力不算正式 surface"）。
无第三方依赖（仅用 stdlib `tomllib`）。退出码 0 = 通过，1 = 有 error。
用法：python scripts/check-capability-catalog.py [--strict] [--self-test]
"""
from __future__ import annotations

import sys
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CATALOG_REL = ".agent/capability-catalog.toml"

VALID_KINDS = {"agent", "skill", "command", "hook"}
VALID_STATUS = {"registered", "exempt"}
# 每条 capability 必须声明的 7 个契约维度（见 issue #28 验收）。
DECLARATION_FIELDS = [
    "inputs", "outputs", "validators", "human_gates",
    "path_boundaries", "adapters", "completion_contract",
]
STRING_FIELDS = ["id", "kind", "name", "path", "status",
                 "inputs", "outputs", "path_boundaries", "completion_contract"]
LIST_FIELDS = ["validators", "human_gates", "adapters"]


def _is_placeholder(value: str) -> bool:
    return not value.strip() or value.strip().startswith(("<", "TODO", "TBD"))


def discover_canonical(repo: Path) -> dict[str, str]:
    """扫描真实能力面，返回 {"<kind>:<name>": canonical_repo_relative_path}。"""
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
    for py in sorted((repo / ".claude" / "hooks").glob("*.py")):
        found[f"hook:{py.stem}"] = f".claude/hooks/{py.name}"
    return found


def expected_adapters(kind: str, name: str) -> list[str]:
    """镜像 scripts/sync-codex-adapters.py 的 canonical→adapter 映射。"""
    if kind == "agent":
        return [f".codex/agents/{name}.toml"]
    if kind == "skill":
        return [f".agents/skills/{name}/SKILL.md"]
    if kind == "command":
        return [f".agents/skills/command-{name}/SKILL.md"]
    return []  # hook：共享地板，两边由 config 调用同一脚本，无生成 adapter


def _check_top_level(data: dict, errors: list[str], warnings: list[str]) -> None:
    ver = data.get("schema_version")
    if not isinstance(ver, int) or ver < 1:
        errors.append("顶层 schema_version 缺失或非法（应为 int≥1）")
    if data.get("profile") != "research":
        errors.append(f"顶层 profile 必须为 'research'，实际：{data.get('profile')!r}")
    chassis = data.get("chassis_spec")
    if not isinstance(chassis, dict):
        errors.append("缺少 [chassis_spec]（应声明 Bridge chassis-spec pin/compatibility）")
        return
    for key in ("source", "pin", "compatibility", "status"):
        val = chassis.get(key)
        if not isinstance(val, str) or _is_placeholder(val):
            errors.append(f"[chassis_spec].{key} 缺失或为占位")


def _check_entry(cap: dict, idx: int, errors: list[str]) -> tuple[str, str, str] | None:
    """校验单条 capability 的字段完整性，返回 (kind, name, status) 供 parity 用。"""
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
        errors.append(f"capability {tag}: kind 非法（应 ∈ {sorted(VALID_KINDS)}）：{kind!r}")
        ok = False
    if status not in VALID_STATUS:
        errors.append(f"capability {tag}: status 非法（应 ∈ {sorted(VALID_STATUS)}）：{status!r}")
        ok = False
    if status == "exempt":
        reason = cap.get("exemption_reason")
        if not isinstance(reason, str) or _is_placeholder(reason):
            errors.append(f"capability {tag}: status=exempt 必须给出非占位 exemption_reason")
            ok = False
    if not ok or kind not in VALID_KINDS or not isinstance(name, str):
        return None
    return kind, name, status


def validate(repo: Path, data: dict) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    _check_top_level(data, errors, warnings)

    caps = data.get("capability") or []
    if not isinstance(caps, list):
        errors.append("[[capability]] 必须是表数组")
        return errors, warnings

    seen_ids: set[str] = set()
    registered: dict[str, dict] = {}   # "<kind>:<name>" -> cap
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
        # path 必须与 kind/name 推出的 canonical 路径一致（防 typo / 张冠李戴）。
        expected_path = _canonical_path_for(kind, name)
        if cap.get("path") != expected_path:
            errors.append(
                f"capability {key}: path={cap.get('path')!r} 与 kind/name 推出的 "
                f"canonical 路径 {expected_path!r} 不一致"
            )
        if status == "registered":
            registered[key] = cap
            _check_adapter_parity(repo, key, kind, name, cap, errors)

    _check_registry_parity(repo, caps, registered, errors)
    return errors, warnings


def _canonical_path_for(kind: str, name: str) -> str:
    if kind == "agent":
        return f".claude/agents/{name}.md"
    if kind == "skill":
        return f".claude/skills/{name}/SKILL.md"
    if kind == "command":
        return f".claude/commands/{name}.md"
    return f".claude/hooks/{name}.py"


def _check_adapter_parity(
    repo: Path, key: str, kind: str, name: str, cap: dict, errors: list[str]
) -> None:
    declared = [a for a in cap.get("adapters", []) if isinstance(a, str)]
    expected = expected_adapters(kind, name)
    if sorted(declared) != sorted(expected):
        errors.append(
            f"capability {key}: adapters 声明 {declared} 与预期映射 {expected} 不一致"
        )
    for adapter in expected:
        if not (repo / adapter).exists():
            errors.append(f"capability {key}: 预期 adapter 文件不存在：{adapter}")


def _check_registry_parity(
    repo: Path, caps: list, registered: dict[str, dict], errors: list[str]
) -> None:
    canonical = discover_canonical(repo)
    exempt_keys = {
        f"{c.get('kind')}:{c.get('name')}"
        for c in caps
        if isinstance(c, dict) and c.get("status") == "exempt"
    }
    # missing：真实能力未登记（既没 registered 也没 exempt）。
    for key, path in canonical.items():
        if key not in registered and key not in exempt_keys:
            errors.append(f"能力未登记进目录（missing）：{key}（{path}）—— 登记或标 exempt")
    # unexpected：目录登记了 registered 条目但 canonical 文件不存在。
    for key in registered:
        if key not in canonical:
            errors.append(f"目录登记的 registered 能力无对应 canonical 文件（unexpected）：{key}")


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


# --------------------------------------------------------------------------- #
# 自测：用临时 repo 树 + 合成目录跑对抗 fixture，确认 missing/unexpected/字段缺失/
# adapter 不符/profile 错误/exempt 无理由 都会失败，good fixture 通过。
# --------------------------------------------------------------------------- #
def _self_test() -> int:
    import tempfile

    def good_cap(**over):
        cap = {
            "id": "agent.demo", "kind": "agent", "name": "demo",
            "path": ".claude/agents/demo.md", "status": "registered",
            "inputs": "x", "outputs": "y", "validators": ["scripts/v.py"],
            "human_gates": [], "path_boundaries": "owned only",
            "adapters": [".codex/agents/demo.toml"],
            "completion_contract": "report",
        }
        cap.update(over)
        return cap

    def base_doc(caps):
        return {
            "schema_version": 1, "profile": "research",
            "chassis_spec": {"source": "org/bridge", "pin": "unpinned",
                             "compatibility": ">=0 <1", "status": "pending"},
            "capability": caps,
        }

    failures: list[str] = []

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / ".claude" / "agents").mkdir(parents=True)
        (root / ".codex" / "agents").mkdir(parents=True)
        (root / ".claude" / "agents" / "demo.md").write_text("---\nname: demo\n---\n", "utf-8")
        (root / ".codex" / "agents" / "demo.toml").write_text("name='demo'\n", "utf-8")

        def expect(label, doc, should_pass):
            errs, _ = validate(root, doc)
            ok = (len(errs) == 0)
            if ok != should_pass:
                failures.append(f"{label}: 期望 {'通过' if should_pass else '失败'}，实际 errors={errs}")

        # 1) good fixture 通过
        expect("good", base_doc([good_cap()]), True)
        # 2) missing：canonical demo 存在但目录空
        expect("missing", base_doc([]), False)
        # 3) unexpected：登记了 canonical 不存在的 ghost
        expect("unexpected", base_doc([good_cap(), good_cap(
            id="agent.ghost", name="ghost", path=".claude/agents/ghost.md",
            adapters=[".codex/agents/ghost.toml"])]), False)
        # 4) 缺契约字段
        bad = good_cap(); bad.pop("completion_contract")
        expect("missing-field", base_doc([bad]), False)
        # 5) profile 错误
        doc = base_doc([good_cap()]); doc["profile"] = "writing"
        expect("wrong-profile", doc, False)
        # 6) adapter 声明与映射不符
        expect("adapter-mismatch", base_doc([good_cap(adapters=[".codex/agents/wrong.toml"])]), False)
        # 7) exempt 无 reason
        expect("exempt-no-reason", base_doc([good_cap(
            id="agent.demo", status="exempt")]), False)
        # 8) chassis_spec 缺 compatibility
        doc = base_doc([good_cap()]); doc["chassis_spec"].pop("compatibility")
        expect("chassis-missing", doc, False)

    if failures:
        for f in failures:
            print(f"SELFTEST-FAIL {f}")
        print(f"[check-capability-catalog --self-test] FAIL — {len(failures)} case(s)")
        return 1
    print("[check-capability-catalog --self-test] OK — 8 对抗场景全部符合预期")
    return 0


def main() -> int:
    if "--self-test" in sys.argv:
        return _self_test()
    return _run_real("--strict" in sys.argv)


if __name__ == "__main__":
    sys.exit(main())
