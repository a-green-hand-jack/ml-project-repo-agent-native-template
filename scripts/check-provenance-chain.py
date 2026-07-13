#!/usr/bin/env python3
"""provenance 链检查：run → artifact → evidence → claim → deliverable。

对应 doctrine：`.agent/artifact-policy.md`（provenance 字段、checksum 政策、claim marker）。
由 `validate-governance.py` 经 run_subcheck 拉起（CI 与手动同源、runtime-neutral），
也可单独运行。不挂任何 runtime hook。

检查项（三态输出：PASS / FAIL / UNKNOWN，unknown 不算 pass）：
1. 覆盖的 index / ledger YAML 带 `schema_version`（整数 ≥1）。
2. artifact index 条目：commit/config/run_id 三元组非占位（全部 7 类统一要求；
   确无 run 来源的合法场景须显式豁免：provenance_unavailable_reason 固定枚举 +
   非占位 justification，不允许静默留空）；run_id 存在于 experiment-ledger 且
   run 已闭环（status=done 且有 run_summary）。
3. checksum：统一 sha256，进程内 hashlib 计算；本地 bytes 可达则真算比对；
   外部 URI / 不可达路径只要求记录完备；无法校验必须给固定枚举 reason +
   非占位 justification，枚举外或占位理由判 FAIL（不是 unknown）。
4. evidence → artifact index 交叉引用（metric_source 等指向 index 条目时必须存在
   且未 archived）；evidence.run_id 的 run 必须闭环。
5. deliverables/index.md → claims.yaml 引用存在；「evidence 齐全」列与 claims 实际
   evidence 一致；submitted/published 状态要求「齐全=是」；「齐全=是」的非 draft
   条目还必须「正文含 claim marker」或「登记人工 review 证据（行内引用
   human/reviews/results/ 下存在的文件）」二选一（plan 任务 5.3），两者皆无判 FAIL
   （豁免仅限占位/示例行与 draft 状态）。
6. deliverable Markdown 正文的 claim marker
   `<!-- claim: id=<claim-id> [evidence=<ev-id>,...] -->` 引用必须存在。
7. release gate 结构化检查（structured_checks，只覆盖可客观机械验证的 kind）：
   结果仅作建议信号（ADVISE），gate_status 翻转仍是 human 动作；唯一会 FAIL 的
   情形是 gate_status=passed 却有结构化检查不满足（不该放行）。语义收紧：
   artifact-exists 除条目存在外还查 repo 内 location 文件真实存在（外部/不可达
   location 查 checksum/manifest 记录完备）；checksum-verified 只在真算 sha256
   比对通过时满足，waived（豁免）/ recorded-unverified（登记未校验）≠ verified。

覆盖范围：同一套逻辑经 INDEX_SPECS / COVERED_INDEX_TYPES 白名单扩展——Phase A 为
最短闭环（result-index → evidence → claims → deliverables），Phase B 已扩展到全部
7 类 index + regression-matrix / release-gates（见 plans/20260712-artifact-evidence-chain.zh.md）。

无第三方硬依赖：PyYAML 可选（缺失时用内置受限解析器回退；再失败记 UNKNOWN，
--strict 下 unknown 也算失败，不静默降级）。模板占位条目只有在未激活、未被引用时
才可保留；一旦进入 active evidence、submitted/published deliverable 或 passed gate，
占位值一律 FAIL，且绝不参与 claim 强度计算。

用法：python scripts/check-provenance-chain.py [--strict] [--self-test]
退出码：0 = 无 FAIL（非 strict 时允许 UNKNOWN）；1 = 有 FAIL 或（strict 且有 UNKNOWN）。
"""
from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# 常量：schema / 枚举（见 .agent/artifact-policy.md 与 plan doc 决策 2/3/8）
# ---------------------------------------------------------------------------

CHECKSUM_ALGORITHM = "sha256"  # 唯一取值（决策 8）
CHECKSUM_UNAVAILABLE_REASONS = {
    "external-uri-no-checksum",  # 外部托管资源，未产出/未提供 checksum
    "pending-upload",            # bytes 尚未落地/上传，条目先行占位登记
    "legacy-untracked",          # 历史遗留条目，尚未回填 checksum
    "oversized-defer-hash",      # 文件过大，暂不具备本地算 hash 条件
}
PROVENANCE_UNAVAILABLE_REASONS = {  # 三元组豁免（决策 9）：无 run 来源的合法场景
    "external-origin",   # 外部/上游产生（如外部数据集），repo 内无 run/config 来源
    "human-authored",    # human 手工产生（如 human-cc trace），无 run/config
    "legacy-untracked",  # 历史遗留条目，来源三元组尚未回填
}
JUSTIFICATION_PLACEHOLDERS = {"tbd", "n/a", "na", "none", "todo", "...", "-", "?"}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
URI_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*://")
WINDOWS_ABSOLUTE_RE = re.compile(r"^[A-Za-z]:[\\/]")

ARTIFACT_STATUS = {"active", "superseded", "archived", "unknown"}
RUN_STATUS = {"planned", "running", "done", "failed", "superseded"}
GRADE_RANK = {"log": 1, "metric": 2, "table": 3, "figure": 4, "paper-claim": 5}
STRUCTURED_CHECK_KINDS = {  # release gate 可机械验证部分（决策 3；Phase B 启用）
    "artifact-exists", "checksum-verified", "run-closed",
    "regression-status", "evidence-grade-min",
}

# index 类型注册表：同一套校验逻辑按类型扩展，不另起实现（plan 任务 2.0）。
# required_triplet: 该类型条目离开占位状态后必须非占位的可复现字段。
INDEX_SPECS: dict[str, dict] = {
    "result": {
        "file": "lab/artifacts/result-index.yaml",
        "key": "results",
        "id_prefixes": ("result-",),
        "required_triplet": ("commit", "config", "run_id"),
        "checksum": True,
    },
    "table": {
        "file": "lab/artifacts/table-index.yaml",
        "key": "tables",
        "id_prefixes": ("table-",),
        "required_triplet": ("commit", "config", "run_id"),
        "checksum": True,
    },
    "figure": {
        "file": "lab/artifacts/figure-index.yaml",
        "key": "figures",
        "id_prefixes": ("figure-",),
        "required_triplet": ("commit", "config", "run_id"),
        "checksum": True,
    },
    "trace": {
        "file": "lab/artifacts/trace-index.yaml",
        "key": "traces",
        "id_prefixes": ("trace-",),
        # human-cc/agent trace 无 run 来源时走显式 provenance 豁免（决策 9），不清空要求。
        "required_triplet": ("commit", "config", "run_id"),
        "checksum": True,
    },
    "model": {
        "file": "lab/artifacts/model-index.yaml",
        "key": "models",
        "id_prefixes": ("model-",),
        "required_triplet": ("commit", "config", "run_id"),
        "checksum": True,
    },
    "checkpoint": {
        "file": "lab/models/checkpoint-index.yaml",
        "key": "checkpoints",
        "id_prefixes": ("ckpt-",),
        "required_triplet": ("commit", "config", "run_id"),
        "checksum": True,
    },
    "dataset": {
        "file": "lab/data/dataset-index.yaml",
        "key": "datasets",
        "id_prefixes": ("dataset-",),
        # 外部数据集无 run 来源时走显式 provenance 豁免（决策 9），不清空要求。
        "required_triplet": ("commit", "config", "run_id"),
        "checksum": True,
    },
}

# 覆盖白名单：Phase A 为 ("result",) 最短闭环；Phase B 已扩展到全部 7 类（决策 1）。
COVERED_INDEX_TYPES: tuple[str, ...] = (
    "result", "table", "figure", "trace", "model", "checkpoint", "dataset",
)

CLAIM_MARKER_RE = re.compile(
    r"<!--\s*claim:\s*id=([A-Za-z0-9._-]+)"
    r"(?:\s+evidence=([A-Za-z0-9._,-]+))?\s*-->"
)


# ---------------------------------------------------------------------------
# 三态报告
# ---------------------------------------------------------------------------

class Report:
    def __init__(self) -> None:
        self.fails: list[str] = []
        self.unknowns: list[str] = []
        self.passes: list[str] = []
        self.advisories: list[str] = []  # 建议信号（gate 未放行时的结构化检查结果，不计三态）

    def fail(self, msg: str) -> None:
        self.fails.append(msg)

    def unknown(self, msg: str) -> None:
        self.unknowns.append(msg)

    def ok(self, msg: str) -> None:
        self.passes.append(msg)

    def advise(self, msg: str) -> None:
        self.advisories.append(msg)

    def extend(self, other: "Report") -> None:
        self.fails.extend(other.fails)
        self.unknowns.extend(other.unknowns)
        self.passes.extend(other.passes)
        self.advisories.extend(other.advisories)


# ---------------------------------------------------------------------------
# YAML 加载：PyYAML 可选，缺失时受限解析器回退（覆盖本 repo index/ledger 的子集）
# ---------------------------------------------------------------------------

def _strip_comment(line: str) -> str:
    out: list[str] = []
    quote: str | None = None
    for i, ch in enumerate(line):
        if quote:
            out.append(ch)
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
            out.append(ch)
        elif ch == "#" and (i == 0 or line[i - 1] in " \t"):
            break
        else:
            out.append(ch)
    return "".join(out).rstrip()


def _split_inline(s: str) -> list[str]:
    parts, buf, quote = [], [], None
    for ch in s:
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
            buf.append(ch)
        elif ch == ",":
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    if buf:
        parts.append("".join(buf))
    return [p for p in (x.strip() for x in parts) if p]


def _mini_scalar(s: str):
    s = s.strip()
    if s == "" or s in ("null", "~"):
        return None
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
        return s[1:-1]
    if s.startswith("[") and s.endswith("]"):
        return [_mini_scalar(x) for x in _split_inline(s[1:-1])]
    if s in ("true", "True"):
        return True
    if s in ("false", "False"):
        return False
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    return s


_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*$")


def _parse_node(lines: list[list], i: int, min_indent: int):
    if i >= len(lines) or lines[i][0] < min_indent:
        return None, i
    indent, content = lines[i]
    if content == "-" or content.startswith("- "):
        return _parse_list(lines, i, indent)
    key, sep, _ = content.partition(":")
    if sep and _KEY_RE.match(key.strip()):
        return _parse_map(lines, i, indent)
    # 裸标量（列表项展开后出现）
    return _mini_scalar(content), i + 1


def _parse_map(lines: list[list], i: int, indent: int):
    result: dict = {}
    while i < len(lines):
        ind, content = lines[i]
        if ind < indent:
            break
        if ind > indent:
            raise ValueError(f"意外缩进：{content!r}")
        if content == "-" or content.startswith("- "):
            break
        key, sep, rest = content.partition(":")
        key = key.strip()
        if not sep or not _KEY_RE.match(key):
            raise ValueError(f"无法解析映射行：{content!r}")
        rest = rest.strip()
        i += 1
        if rest:
            result[key] = _mini_scalar(rest)
        elif i < len(lines) and lines[i][0] > indent:
            result[key], i = _parse_node(lines, i, indent + 1)
        elif i < len(lines) and lines[i][0] == indent and (
            lines[i][1] == "-" or lines[i][1].startswith("- ")
        ):
            result[key], i = _parse_list(lines, i, indent)
        else:
            result[key] = None
    return result, i


def _parse_list(lines: list[list], i: int, indent: int):
    out: list = []
    while i < len(lines) and lines[i][0] == indent and (
        lines[i][1] == "-" or lines[i][1].startswith("- ")
    ):
        content = lines[i][1][1:].strip()
        if content:
            lines[i] = [indent + 2, content]
            val, i = _parse_node(lines, i, indent + 1)
        else:
            i += 1
            val, i = _parse_node(lines, i, indent + 1)
        out.append(val)
    return out, i


def _mini_yaml(text: str):
    """受限 YAML 子集解析器（映射/列表/标量/inline 列表/注释）。仅作 PyYAML 缺失回退。"""
    lines: list[list] = []
    for raw in text.splitlines():
        s = _strip_comment(raw)
        if not s.strip():
            continue
        lines.append([len(s) - len(s.lstrip(" ")), s.strip()])
    if not lines:
        return None
    val, i = _parse_node(lines, 0, 0)
    if i < len(lines):
        raise ValueError(f"未消费的行：{lines[i][1]!r}")
    return val


def load_yaml(path: Path):
    """返回 (data, err)。err 为 (kind, msg)，kind ∈ {'parse','fallback'}。"""
    try:
        if not path.is_file():
            return None, ("parse", f"不是 regular file：{path}")
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        return None, ("parse", f"无法读取：{exc}")
    try:
        import yaml  # type: ignore
    except ImportError:
        try:
            return _mini_yaml(text), None
        except Exception as e:  # noqa: BLE001
            return None, ("fallback", f"未安装 PyYAML 且受限解析器失败：{e}")
    try:
        return yaml.safe_load(text), None
    except Exception as e:  # noqa: BLE001
        return None, ("parse", str(e))


# ---------------------------------------------------------------------------
# 小工具
# ---------------------------------------------------------------------------

def _filled(v) -> bool:
    """字段已填真实值（非空、非 <...> 占位、非 YYYY-MM-DD 类占位）。"""
    if not isinstance(v, str) or not v.strip():
        return False
    value = v.strip()
    return not value.startswith("<") and value not in {"YYYY-MM-DD", "YYYY-MM-DDTHH:MM:SSZ"}


def _path_value(raw) -> str:
    """Normalize a Markdown/YAML path cell without weakening lexical checks."""
    return raw.strip().strip("`").strip() if isinstance(raw, str) else ""


def _locate(
    root: Path, raw, *, allow_external: bool = True, require_file: bool = True,
) -> tuple[str, Path | None, str]:
    """Resolve an untrusted path inside ``root`` without allowing path escape.

    States are ``external`` / ``local`` / ``missing`` / ``invalid``. Local paths
    must be repo-relative, contain no ``..``, resolve inside the repo, and point
    to a regular file when ``require_file`` is true. Symlink escapes are caught
    by the resolved containment check.
    """
    value = _path_value(raw)
    if not _filled(value):
        return "invalid", None, "路径为空或占位"
    if URI_RE.match(value):
        if value.split(":", 1)[0].lower() == "file":
            return "invalid", None, f"拒绝 file:// 本地 absolute URI：{value}"
        if allow_external:
            return "external", None, f"外部 URI：{value}"
        return "invalid", None, f"此字段不允许外部 URI：{value}"
    candidate = Path(value)
    if candidate.is_absolute() or WINDOWS_ABSOLUTE_RE.match(value):
        return "invalid", None, f"拒绝 absolute path：{value}"
    if ".." in candidate.parts:
        return "invalid", None, f"拒绝包含 '..' 的路径：{value}"
    try:
        root_resolved = root.resolve(strict=True)
        lexical = root / candidate
        resolved = lexical.resolve(strict=False)
    except (OSError, RuntimeError, ValueError) as exc:
        return "invalid", None, f"路径无法安全解析：{value}（{exc}）"
    if resolved != root_resolved and root_resolved not in resolved.parents:
        return "invalid", None, f"路径 resolve 越出 repo（含 symlink escape）：{value}"
    try:
        if not resolved.exists():
            return "missing", resolved, f"repo 内路径不存在：{value}"
        if require_file and not resolved.is_file():
            kind = "目录" if resolved.is_dir() else "特殊文件"
            return "invalid", resolved, f"路径不是 regular file（{kind}）：{value}"
    except OSError as exc:
        return "invalid", None, f"路径状态无法检查：{value}（{exc}）"
    return "local", resolved, f"repo 内 regular file：{value}"


def _sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_indexed(root: Path, rel: str, key: str, rep: Report, label: str):
    """加载 YAML 并返回 (doc, entries)；解析失败记 FAIL/UNKNOWN 并返回 (None, [])。"""
    f = root / rel
    if not f.exists():
        rep.unknown(f"{label}：{rel} 不存在，未检查")
        return None, []
    if not f.is_file():
        rep.fail(f"{label}：{rel} 不是 regular file")
        return None, []
    doc, err = load_yaml(f)
    if err is not None:
        kind, msg = err
        if kind == "parse":
            rep.fail(f"{label}：{rel} 解析失败：{msg}")
        else:
            rep.unknown(f"{label}：{rel} 未检查（{msg}）")
        return None, []
    doc = doc or {}
    if not isinstance(doc, dict):
        rep.fail(f"{label}：{rel} 顶层必须是 mapping")
        return None, []
    entries = doc.get(key) or []
    if not isinstance(entries, list):
        rep.fail(f"{label}：{rel} 的 {key} 必须是 list")
        return doc, []
    for n, entry in enumerate(entries):
        if not isinstance(entry, dict):
            rep.fail(f"{label}：{key}[{n}] 不是 mapping")
    return doc, [e for e in entries if isinstance(e, dict)]


def _entries_by_id(entries: list[dict], label: str, rep: Report) -> dict:
    """Index entries without silently overwriting duplicate IDs."""
    by_id: dict = {}
    for n, entry in enumerate(entries):
        eid = entry.get("id")
        if not _filled(eid):
            rep.fail(f"{label} entries[{n}]：id 缺失或占位")
            continue
        if eid in by_id:
            rep.fail(f"{label}：duplicate id {eid}")
            continue
        by_id[eid] = entry
    return by_id


def _check_schema_version(doc, rel: str, rep: Report) -> None:
    if doc is None:
        return
    sv = doc.get("schema_version")
    if type(sv) is int and sv >= 1:
        rep.ok(f"schema_version：{rel} = {sv}")
    else:
        rep.fail(f"schema_version：{rel} 缺失或非法（应为整数 ≥1，实际 {sv!r}）")


# ---------------------------------------------------------------------------
# checksum / manifest 校验（决策 2/8：统一 sha256 + 固定枚举 reason + 必填理由）
# ---------------------------------------------------------------------------

def _check_reason_justification(
    ident: str, field_prefix: str, reason, just, enum: set, rep: Report,
) -> bool:
    """校验「固定枚举 reason + 非占位 justification」双关卡组合（决策 2 模式，
    checksum 与 provenance 豁免共用）。返回记录是否完备；不完备时已记 FAIL。"""
    if reason not in enum:
        rep.fail(
            f"{ident}：{field_prefix}_reason 非法（{reason!r}），"
            f"合法枚举：{sorted(enum)}"
        )
        return False
    if not _filled(just) or str(just).strip().lower() in JUSTIFICATION_PLACEHOLDERS:
        rep.fail(
            f"{ident}：{field_prefix}_justification 为空或占位（{just!r}）——"
            "reason 枚举 + 具体人工理由两者都要，防止校验逃逸"
        )
        return False
    return True


def _check_justified_unavailable(entry: dict, ident: str, rep: Report) -> None:
    reason = entry.get("checksum_unavailable_reason")
    if _check_reason_justification(
        ident, "checksum_unavailable", reason,
        entry.get("checksum_unavailable_justification"),
        CHECKSUM_UNAVAILABLE_REASONS, rep,
    ):
        rep.ok(f"{ident}：无 checksum，reason={reason} 且理由已填，记录完备")


def _verify_sum(root: Path, ident: str, location: str, checksum: str, rep: Report) -> None:
    state, p, detail = _locate(root, location, allow_external=True, require_file=True)
    if state == "local":
        try:
            actual = _sha256_file(p)
        except OSError as exc:
            rep.fail(f"{ident}：本地 bytes 无法读取：{exc}")
            return
        if actual == checksum:
            rep.ok(f"{ident}：本地 bytes sha256 校验通过")
        else:
            rep.fail(f"{ident}：checksum 不匹配（登记 {checksum[:12]}…，实际 {actual[:12]}…）")
    elif state == "missing":
        rep.fail(f"{ident}：location 指向 repo 内不存在的文件：{location}")
    elif state == "external":
        rep.ok(f"{ident}：bytes 是外部 URI，checksum 已记录，跳过重算")
    else:
        rep.fail(f"{ident}：artifact path 非法：{detail}")


def _check_manifest(root: Path, ident: str, manifest_rel: str, rep: Report) -> None:
    state, f, detail = _locate(
        root, manifest_rel, allow_external=False, require_file=True
    )
    if state == "missing":
        rep.fail(f"{ident}：manifest 不存在：{manifest_rel}")
        return
    if state != "local" or f is None:
        rep.fail(f"{ident}：manifest path 非法：{detail}")
        return
    doc, err = load_yaml(f)
    if err is not None:
        kind, msg = err
        if kind == "parse":
            rep.fail(f"{ident}：manifest 解析失败：{msg}")
        else:
            rep.unknown(f"{ident}：manifest 未检查（{msg}）")
        return
    if not isinstance(doc, dict):
        rep.fail(f"{ident}：manifest {manifest_rel} 顶层必须是 mapping")
        return
    files = doc.get("files") or []
    if not isinstance(files, list):
        rep.fail(f"{ident}：manifest {manifest_rel} 的 files 必须是 list")
        return
    if not files:
        rep.fail(f"{ident}：manifest {manifest_rel} 无 files 条目")
        return
    for n, fe in enumerate(files):
        if not isinstance(fe, dict):
            rep.fail(f"{ident}：manifest files[{n}] 不是映射")
            continue
        floc = fe.get("path") or fe.get("uri")
        fid = f"{ident} manifest files[{n}]"
        if not _filled(floc):
            rep.fail(f"{fid}：缺 path/uri")
            continue
        path_state, _path, path_detail = _locate(
            root, floc, allow_external=bool(fe.get("uri")), require_file=True
        )
        if path_state == "missing":
            rep.fail(f"{fid}：manifest local path 不存在 regular file：{floc}")
            continue
        if path_state == "invalid":
            rep.fail(f"{fid}：artifact path 非法：{path_detail}")
            continue
        fsum = fe.get("sha256")
        if _filled(fsum):
            if not SHA256_RE.match(fsum.strip()):
                rep.fail(f"{fid}：sha256 不是合法 64 位 hex")
            else:
                _verify_sum(root, fid, floc, fsum.strip(), rep)
        else:
            _check_justified_unavailable(fe, fid, rep)


def _check_entry_checksum(root: Path, entry: dict, ident: str, location: str, rep: Report) -> None:
    manifest = entry.get("manifest")
    if _filled(manifest):
        _check_manifest(root, ident, manifest, rep)
        return
    checksum = entry.get("checksum")
    has_sum = _filled(checksum)
    has_reason = entry.get("checksum_unavailable_reason") is not None or _filled(
        entry.get("checksum_unavailable_justification")
    )
    if has_sum and has_reason:
        rep.fail(f"{ident}：checksum 与 checksum_unavailable_* 同时填写，二选一")
        return
    if has_sum:
        algo = entry.get("checksum_algorithm")
        if algo != CHECKSUM_ALGORITHM:
            rep.fail(f"{ident}：checksum_algorithm 必须为 {CHECKSUM_ALGORITHM}（实际 {algo!r}）")
            return
        if not SHA256_RE.match(checksum.strip()):
            rep.fail(f"{ident}：checksum 不是合法 sha256 hex（64 位小写十六进制）")
            return
        _verify_sum(root, ident, location, checksum.strip(), rep)
    elif has_reason:
        _check_justified_unavailable(entry, ident, rep)
    else:
        rep.fail(
            f"{ident}：既无 checksum（sha256）也无 checksum_unavailable_reason/"
            "justification——无法校验必须显式登记原因"
        )


# ---------------------------------------------------------------------------
# run / artifact / evidence / claim / deliverable 各段检查
# ---------------------------------------------------------------------------

def _load_runs(root: Path, rep: Report) -> dict:
    doc, entries = _load_indexed(
        root, "lab/research/experiment-ledger.yaml", "experiments", rep, "experiment-ledger"
    )
    _check_schema_version(doc, "lab/research/experiment-ledger.yaml", rep)
    runs = _entries_by_id(entries, "experiment-ledger", rep)
    for e in entries:
        rid = e.get("id")
        status = e.get("status")
        if status not in RUN_STATUS:
            rep.fail(f"experiment-ledger {rid}：status 非法：{status!r}")
    return runs


def _check_run_closed(runs: dict, run_id: str, ident: str, rep: Report) -> None:
    run = runs.get(run_id)
    if run is None:
        rep.fail(f"{ident}：run_id={run_id} 不存在于 experiment-ledger.yaml")
        return
    if run.get("status") != "done" or not _filled(run.get("run_summary")):
        rep.fail(
            f"{ident}：引用未闭环 run {run_id}"
            f"（status={run.get('status')!r}，需 done 且 run_summary 已填）"
        )
    else:
        rep.ok(f"{ident}：run {run_id} 已闭环（done + run_summary）")


def _index_ids(root: Path, itype: str) -> tuple[dict, set[str]]:
    """返回 (id -> entry, id 集合)。文件缺失/不可解析时返回空（引用检查降级为按前缀报悬空）。"""
    spec = INDEX_SPECS[itype]
    f = root / spec["file"]
    if not f.exists():
        return {}, set()
    doc, err = load_yaml(f)
    if err is not None:
        return {}, set()
    if not isinstance(doc, dict):
        return {}, set()
    entries = doc.get(spec["key"]) or []
    if not isinstance(entries, list):
        return {}, set()
    by_id = {}
    for entry in entries:
        if not isinstance(entry, dict) or not _filled(entry.get("id")):
            continue
        by_id.setdefault(entry["id"], entry)
    return by_id, set(by_id)


def check_artifact_indexes(root: Path, runs: dict, claim_ids: set, rep: Report) -> None:
    for itype in COVERED_INDEX_TYPES:
        spec = INDEX_SPECS[itype]
        doc, entries = _load_indexed(root, spec["file"], spec["key"], rep, f"{itype}-index")
        _check_schema_version(doc, spec["file"], rep)
        _entries_by_id(entries, f"{itype}-index", rep)
        for e in entries:
            eid = e.get("id") or "<无 id>"
            ident = f"{itype}-index {eid}"
            status = e.get("status")
            if status not in ARTIFACT_STATUS:
                rep.fail(f"{ident}：status 非法：{status!r}")
            location = e.get("location")
            if not _filled(location):
                # 仅未激活 scaffold 可保留占位；任何真实状态都不得借此跳过。
                if status != "unknown":
                    rep.fail(
                        f"{ident}：status={status!r} 时 location 不得为空/占位"
                    )
                continue
            if not _filled(e.get("how_to_inspect")):
                rep.fail(f"{ident}：how_to_inspect 缺失或占位")
            path_state, _path, path_detail = _locate(
                root, location, allow_external=True, require_file=True
            )
            if path_state == "invalid":
                rep.fail(f"{ident}：artifact path 非法：{path_detail}")
            elif path_state == "missing" and status == "active":
                rep.fail(f"{ident}：active artifact 的 repo 内 location 不存在：{location}")
            # 可复现三元组非占位（任务 2.1）。全部 7 类共用同一要求（决策 9）：
            # 无 run 来源的合法场景（外部数据集 / human-cc trace / 历史遗留）必须
            # 显式豁免（固定枚举 reason + 非占位理由），不允许静默留空。
            missing = [f for f in spec["required_triplet"] if not _filled(e.get(f))]
            prov_reason = e.get("provenance_unavailable_reason")
            prov_just = e.get("provenance_unavailable_justification")
            if prov_reason is not None or _filled(prov_just):
                if _check_reason_justification(
                    ident, "provenance_unavailable", prov_reason, prov_just,
                    PROVENANCE_UNAVAILABLE_REASONS, rep,
                ):
                    if missing:
                        rep.ok(
                            f"{ident}：三元组缺 {missing}，已显式豁免"
                            f"（reason={prov_reason}，理由已填）"
                        )
                    else:
                        rep.fail(
                            f"{ident}：三元组已齐全，不应再填 provenance_unavailable_*"
                            "（豁免只用于字段确实缺失的场景）"
                        )
            else:
                for field in missing:
                    rep.fail(
                        f"{ident}：{field} 缺失或占位（可复现三元组必填；确无 run 来源"
                        "需填 provenance_unavailable_reason/justification 显式豁免）"
                    )
            # run 闭环（任务 2.2）：required 或已填时校验。
            run_id = e.get("run_id")
            if _filled(run_id):
                _check_run_closed(runs, run_id, ident, rep)
            # supports → claim 引用（若指向 claim id）。
            supports = e.get("supports") or e.get("supports_claim")
            if status == "active" and (
                "supports" in e or "supports_claim" in e
            ) and not _filled(supports):
                rep.fail(f"{ident}：active artifact 的 supports claim 不得为空/占位")
            if _filled(supports) and supports.startswith("claim-"):
                if supports in claim_ids:
                    rep.ok(f"{ident}：supports={supports} 存在")
                else:
                    rep.fail(f"{ident}：supports 指向未知 claim：{supports}")
            # model → checkpoint 交叉引用（checkpoint 在覆盖范围时校验）。
            ckpt_ref = e.get("checkpoint_ref")
            if _filled(ckpt_ref) and "checkpoint" in COVERED_INDEX_TYPES:
                ckpt_ids = _index_ids(root, "checkpoint")[1]
                if ckpt_ref in ckpt_ids:
                    rep.ok(f"{ident}：checkpoint_ref={ckpt_ref} 存在")
                else:
                    rep.fail(f"{ident}：checkpoint_ref 指向未知 checkpoint：{ckpt_ref}")
            # checksum / manifest（任务 3.x）。
            if spec["checksum"]:
                if path_state != "invalid":
                    _check_entry_checksum(root, e, ident, location, rep)


def _load_claims(root: Path, rep: Report) -> tuple[dict, set[str]]:
    doc, entries = _load_indexed(root, "lab/research/claims.yaml", "claims", rep, "claims")
    _check_schema_version(doc, "lab/research/claims.yaml", rep)
    by_id = _entries_by_id(entries, "claims", rep)
    for cid, claim in by_id.items():
        status = claim.get("status")
        if status not in {"proposed", "partial", "supported", "refuted", "retired"}:
            rep.fail(f"claim {cid}：status 非法：{status!r}")
        if status != "proposed" and not _filled(claim.get("title")):
            rep.fail(f"claim {cid}：status={status!r} 时 title 不得为空/占位")
    return by_id, set(by_id)


def check_evidence(root: Path, runs: dict, rep: Report) -> tuple[dict, set[str]]:
    """Validate evidence and return both all entries and claim-eligible IDs.

    Unreferenced scaffold rows may remain in the template, but they are never
    eligible evidence and therefore cannot raise a claim's strength.
    """
    doc, entries = _load_indexed(root, "lab/research/evidence.yaml", "evidence", rep, "evidence")
    _check_schema_version(doc, "lab/research/evidence.yaml", rep)
    by_id = _entries_by_id(entries, "evidence", rep)
    valid_ids: set[str] = set()
    # 交叉引用目标：覆盖范围内的 index 类型（Phase B 自动随白名单扩展）。
    ids_by_type = {t: _index_ids(root, t)[0] for t in COVERED_INDEX_TYPES}
    ref_fields = ("metric_source", "checkpoint", "data_split")
    for e in entries:
        eid = e.get("id") or "<无 id>"
        ident = f"evidence {eid}"
        if not _filled(e.get("commit")):
            if eid == "ev-000":
                continue  # canonical template scaffold；被引用时 claim edge 仍会拒绝。
            rep.fail(f"{ident}：commit 缺失或占位；active evidence 不得跳过校验")
            continue
        sub = Report()
        if not _filled(e.get("supports_claim")):
            sub.fail(f"{ident}：supports_claim 缺失或占位")
        if e.get("grade") not in GRADE_RANK:
            sub.fail(f"{ident}：grade 缺失、占位或非法：{e.get('grade')!r}")
        for field in ("command", "config"):
            if not _filled(e.get(field)):
                sub.fail(f"{ident}：{field} 缺失或占位")
        run_id = e.get("run_id")
        if not _filled(run_id):
            sub.fail(f"{ident}：run_id 缺失或占位（evidence 必须可回溯到 run）")
        else:
            _check_run_closed(runs, run_id, ident, sub)
        for field in ref_fields:
            val = e.get(field)
            if not _filled(val):
                continue
            ref_id = val.split("/", 1)[0].strip()  # 允许 dataset-000/test 形式
            matched_index = False
            for itype, target_by_id in ids_by_type.items():
                if not any(ref_id.startswith(p) for p in INDEX_SPECS[itype]["id_prefixes"]):
                    continue
                matched_index = True
                target = target_by_id.get(ref_id)
                if target is None:
                    sub.fail(f"{ident}：{field}={val} 指向不存在的 {itype}-index 条目")
                elif target.get("status") in {"archived", "unknown"}:
                    sub.fail(
                        f"{ident}：{field}={val} 指向 status={target.get('status')!r} "
                        f"的 {itype}-index 条目；占位/归档 artifact 不得支撑 evidence"
                    )
                elif field == "data_split":
                    parts = val.split("/", 1)
                    split = parts[1].strip() if len(parts) == 2 else ""
                    splits = target.get("splits")
                    if not split:
                        sub.fail(
                            f"{ident}：data_split={val} 缺 dataset split（格式应为 <dataset-id>/<split>）"
                        )
                    elif not isinstance(splits, list) or split not in splits:
                        sub.fail(
                            f"{ident}：data_split={val} 的 split={split!r} 不在"
                            f" dataset {ref_id} 的 splits={splits!r}"
                        )
                    else:
                        sub.ok(f"{ident}：data_split → dataset {ref_id}/{split} 已登记")
                else:
                    sub.ok(f"{ident}：{field} → {itype}-index {ref_id} 存在且未 archived")
                break
            if field == "data_split" and not matched_index:
                sub.fail(
                    f"{ident}：data_split={val} 未使用已登记的 dataset id/split"
                )
        rep.extend(sub)
        if not sub.fails and not sub.unknowns and _filled(eid):
            valid_ids.add(eid)
    return by_id, valid_ids


def check_claim_evidence_edges(
    claims_by_id: dict, evidence_by_id: dict, valid_evidence_ids: set[str], rep: Report,
) -> dict[str, list[str]]:
    """Validate claim→evidence ownership and return only eligible owned edges."""
    owned: dict[str, list[str]] = {}
    for evidence_id in sorted(valid_evidence_ids):
        owner = evidence_by_id[evidence_id].get("supports_claim")
        if owner not in claims_by_id:
            rep.fail(
                f"evidence {evidence_id}：supports_claim={owner!r} 不存在于 claims.yaml"
            )
    for cid, claim in claims_by_id.items():
        refs = claim.get("evidence") or []
        if not isinstance(refs, list):
            rep.fail(f"claim {cid}：evidence 必须是 list")
            refs = []
        seen_refs: set[str] = set()
        eligible: list[str] = []
        for evidence_id in refs:
            if not _filled(evidence_id):
                rep.fail(f"claim {cid}：evidence 引用缺失或占位：{evidence_id!r}")
                continue
            if evidence_id in seen_refs:
                rep.fail(f"claim {cid}：evidence 含 duplicate id {evidence_id}")
                continue
            seen_refs.add(evidence_id)
            evidence = evidence_by_id.get(evidence_id)
            if evidence is None:
                rep.fail(f"claim {cid}：引用不存在的 evidence={evidence_id}")
                continue
            if evidence_id not in valid_evidence_ids:
                rep.fail(
                    f"claim {cid}：evidence={evidence_id} 仍是占位/不完整记录，"
                    "不得贡献 claim 强度"
                )
                continue
            owner = evidence.get("supports_claim")
            if owner != cid:
                rep.fail(
                    f"claim {cid}：evidence={evidence_id} 的 supports_claim={owner!r}，"
                    "归属边不匹配"
                )
                continue
            eligible.append(evidence_id)
        owned[cid] = eligible
        if claim.get("status") in {"partial", "supported"} and not eligible:
            rep.fail(
                f"claim {cid}：status={claim.get('status')} 但没有有效且 supports_claim 归属匹配的 evidence"
            )
    return owned


# ---------------------------------------------------------------------------
# deliverables：index.md 表格 + claim marker（决策 4）
# ---------------------------------------------------------------------------

_CLAIM_REF_RE = re.compile(r"claims\.yaml#([A-Za-z0-9._-]+)|(claim-[A-Za-z0-9._-]+)")
def _iter_markers(md: Path):
    """产出 md 文件正文（跳过 code fence）里的 claim marker 匹配。"""
    in_fence = False
    for line in md.read_text(encoding="utf-8").splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        yield from CLAIM_MARKER_RE.finditer(line)


def _deliverable_marker_claims(
    root: Path, path_cell: str, ident: str, rep: Report,
) -> set[str]:
    """Return marker claim IDs from one safe, repo-local Markdown deliverable."""
    state, path, detail = _locate(
        root, path_cell, allow_external=False, require_file=True
    )
    if state != "local" or path is None:
        rep.fail(f"{ident}：deliverable path 非法或不可达：{detail}")
        return set()
    if path.suffix.lower() != ".md":
        return set()
    return {match.group(1) for match in _iter_markers(path)}


def check_deliverables_index(
    root: Path, claims_by_id: dict, claim_evidence: dict[str, list[str]], rep: Report,
) -> None:
    f = root / "deliverables" / "index.md"
    if not f.exists():
        rep.unknown("deliverables/index.md 不存在，未检查")
        return
    rows = []
    for line in f.read_text(encoding="utf-8").splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 6 or set(cells[0]) <= {"-", " ", ":"} or cells[0] in ("id",):
            continue
        rows.append(cells)
    seen_rows: set[str] = set()
    for cells in rows:
        rid, _, path_cell, claims_cell, status_cell, complete_cell = cells[:6]
        is_example = "示例" in rid or "example" in rid.lower()
        if is_example and status_cell == "draft":
            continue
        ident = f"deliverables/index.md 条目 {rid}"
        if not _filled(rid):
            rep.fail(f"{ident}：id 缺失或占位")
        elif rid in seen_rows:
            rep.fail(f"deliverables/index.md：duplicate id {rid}")
        else:
            seen_rows.add(rid)
        deliverable_state, deliverable_path, deliverable_detail = _locate(
            root, path_cell, allow_external=False, require_file=True
        )
        if deliverable_state != "local" or deliverable_path is None:
            rep.fail(f"{ident}：deliverable path 非法或不可达：{deliverable_detail}")
        claim_refs = [a or b for a, b in _CLAIM_REF_RE.findall(claims_cell)]
        if not claim_refs:
            rep.fail(f"{ident}：「支撑 claim」列没有可解析的 claim 引用：{claims_cell!r}")
            continue
        if len(claim_refs) != len(set(claim_refs)):
            rep.fail(f"{ident}：「支撑 claim」列含 duplicate id")
        complete = complete_cell.strip("*_ ")
        all_have_evidence = True
        for cid in claim_refs:
            c = claims_by_id.get(cid)
            if c is None:
                rep.fail(f"{ident}：引用未知 claim：{cid}")
                all_have_evidence = False
            elif not claim_evidence.get(cid):
                all_have_evidence = False
        if complete in ("是", "yes", "Yes"):
            if all_have_evidence:
                rep.ok(f"{ident}：evidence 齐全列=是，且引用 claim 均有 evidence")
            else:
                rep.fail(
                    f"{ident}：「evidence 齐全」列为「是」，但存在缺 evidence 或"
                    "不存在的 claim（与 claims.yaml 不一致）"
                )
        if status_cell in ("submitted", "published") and complete not in ("是", "yes", "Yes"):
            rep.fail(f"{ident}：状态 {status_cell} 要求「evidence 齐全」列为「是」")
        if status_cell not in ("draft", "submitted", "published"):
            rep.fail(f"{ident}：状态非法或占位：{status_cell!r}")
        # plan 任务 5.3：判「evidence 齐全=是」还必须有机器可见的支撑动作——正文含
        # claim marker，或登记了人工 review 证据（行内引用 human/reviews/results/ 下
        # 存在的文件）。二者皆无 → FAIL。豁免条件（仅此两类）：
        #   a) 占位/示例行（上方已 continue 跳过）；
        #   b) status=draft——尚未对外，允许先标「齐全」再补 marker/review；提升到
        #      submitted/published 时本检查即生效。
        if complete in ("是", "yes", "Yes") and status_cell != "draft":
            review_refs: list[str] = []
            if len(cells) >= 7 and cells[6].strip():
                review_cell = cells[6].strip()
                review_refs = re.findall(r"`([^`]+)`", review_cell) or [review_cell]
            live_reviews = []
            for r in review_refs:
                if not _path_value(r).startswith("human/reviews/results/"):
                    rep.fail(f"{ident}：人工 review path 必须位于 human/reviews/results/：{r}")
                    continue
                review_state, _review_path, review_detail = _locate(
                    root, r, allow_external=False, require_file=True
                )
                if review_state == "local":
                    live_reviews.append(r)
                else:
                    rep.fail(f"{ident}：登记的人工 review path 非法或不存在：{review_detail}")
            marker_claims = _deliverable_marker_claims(root, path_cell, ident, rep)
            missing_marker_claims = sorted(set(claim_refs) - marker_claims)
            if marker_claims and not missing_marker_claims:
                rep.ok(
                    f"{ident}：「齐全=是」且正文 marker 覆盖该行全部 claim（任务 5.3 满足）"
                )
            elif marker_claims and missing_marker_claims:
                rep.fail(
                    f"{ident}：deliverable marker 未覆盖该行 claim：{missing_marker_claims}"
                )
            elif live_reviews:
                rep.ok(
                    f"{ident}：「齐全=是」，正文无 marker，但已登记人工 review 证据："
                    f"{live_reviews[0]}（任务 5.3 兜底路径）"
                )
            else:
                rep.fail(
                    f"{ident}：「evidence 齐全=是」（状态 {status_cell}）但正文"
                    "无 claim marker、也未登记 human/reviews/results/ 人工 review 证据"
                    "——两者至少其一（任务 5.3），否则「齐全」列不得为「是」"
                )


def check_claim_markers(
    root: Path, claim_ids: set, evidence_by_id: dict,
    valid_evidence_ids: set[str], rep: Report,
) -> None:
    deliv = root / "deliverables"
    if not deliv.is_dir():
        return
    n_markers = 0
    for md in sorted(deliv.rglob("*.md")):
        rel = md.relative_to(root)
        state, safe_md, detail = _locate(root, str(rel), allow_external=False, require_file=True)
        if state != "local" or safe_md is None:
            rep.fail(f"claim marker source path 非法：{detail}")
            continue
        for m in _iter_markers(safe_md):
            n_markers += 1
            cid, ev_list = m.group(1), m.group(2)
            ident = f"claim marker（{rel}）"
            if cid in claim_ids:
                rep.ok(f"{ident}：id={cid} 存在")
            else:
                rep.fail(f"{ident}：id={cid} 不存在于 claims.yaml")
            for ev in (ev_list or "").split(","):
                ev = ev.strip()
                if not ev:
                    continue
                evidence = evidence_by_id.get(ev)
                if evidence is None:
                    rep.fail(f"{ident}：evidence={ev} 不存在于 evidence.yaml")
                elif ev not in valid_evidence_ids:
                    rep.fail(f"{ident}：evidence={ev} 是占位/不完整记录，不得支撑 claim")
                elif evidence.get("supports_claim") != cid:
                    rep.fail(
                        f"{ident}：evidence={ev} 的 supports_claim="
                        f"{evidence.get('supports_claim')!r}，不属于 marker claim {cid}"
                    )
                else:
                    rep.ok(f"{ident}：evidence={ev} 存在且 supports_claim 归属匹配")
    if n_markers == 0:
        rep.ok(
            "claim marker：deliverables 下暂无 marker（无 marker 的活跃交付物由"
            " deliverables/index.md 的 marker-or-review 检查兜底）"
        )


# ---------------------------------------------------------------------------
# release gate 结构化检查（决策 3：只覆盖可客观机械验证的 kind；
# 校验结果仅作建议信号，gate_status 翻转仍是 human 动作——validator 只拦
# 「gate_status=passed 却有结构化检查不满足」这种不该放行的情况）
# ---------------------------------------------------------------------------

def _checksum_verification_state(root: Path, entry: dict, location: str) -> str:
    """区分 checksum 的三种「记录完备」状态（前提：_check_entry_checksum 无 FAIL）：
    - verified：validator 真算 sha256 且比对通过（本地 bytes 可达）；
    - waived：走 checksum_unavailable_reason/justification 豁免（理由完备 ≠ 校验过）；
    - recorded-unverified：登记了 checksum 但 bytes 不在本地，无法真算比对。
    manifest 场景按 files 逐条聚合：全部 verified 才算 verified。"""
    manifest = entry.get("manifest")
    if _filled(manifest):
        manifest_state, manifest_path, _detail = _locate(
            root, manifest, allow_external=False, require_file=True
        )
        if manifest_state != "local" or manifest_path is None:
            return "recorded-unverified"
        doc, _err = load_yaml(manifest_path)
        files = [fe for fe in ((doc or {}).get("files") or []) if isinstance(fe, dict)]
        states = []
        for fe in files:
            if _filled(fe.get("sha256")):
                st, _, _ = _locate(
                    root, fe.get("path") or fe.get("uri") or "",
                    allow_external=bool(fe.get("uri")), require_file=True,
                )
                states.append("verified" if st == "local" else "recorded-unverified")
            else:
                states.append("waived")
        if states and all(s == "verified" for s in states):
            return "verified"
        return "waived" if "waived" in states else "recorded-unverified"
    if _filled(entry.get("checksum")):
        st, _, _ = _locate(root, location, allow_external=True, require_file=True)
        return "verified" if st == "local" else "recorded-unverified"
    return "waived"


def _eval_structured_check(
    root: Path, c: dict, runs: dict, claims_by_id: dict,
    evidence_by_id: dict, claim_evidence: dict[str, list[str]], regs_by_id: dict,
):
    """返回 (result, detail)：result ∈ {True, False, None(无法机械验证), 'malformed'}。"""
    kind = c.get("kind")
    if kind == "artifact-exists":
        # 语义（决策 3「文件/manifest 存在性」）：index 条目登记存在还不够——repo 内
        # location 必须真实存在；外部/不可达 location 要求 checksum/manifest 记录完备。
        target = c.get("target")
        if not _filled(target):
            return "malformed", "artifact-exists 缺 target 字段"
        for itype in COVERED_INDEX_TYPES:
            if any(target.startswith(p) for p in INDEX_SPECS[itype]["id_prefixes"]):
                entry = _index_ids(root, itype)[0].get(target)
                if entry is None:
                    return False, f"{itype}-index 无条目 {target}"
                location = entry.get("location")
                if not _filled(location):
                    return False, (
                        f"{itype}-index 条目 {target} 的 location 未填/占位，"
                        "无法确认产物真实存在"
                    )
                state, _p, path_detail = _locate(
                    root, location, allow_external=True, require_file=True
                )
                if state == "local":
                    return True, f"{itype}-index 条目 {target} 存在且 location 文件可达"
                if state == "missing":
                    return False, (
                        f"{itype}-index 条目 {target} 的 location 指向 repo 内"
                        f"不存在的文件：{location}"
                    )
                if state == "invalid":
                    return False, f"{itype}-index 条目 {target} 的 artifact path 非法：{path_detail}"
                sub = Report()
                _check_entry_checksum(root, entry, target, location, sub)
                ok = not sub.fails and not sub.unknowns
                return ok, (
                    f"{itype}-index 条目 {target} 的 location 在外部/不可达（{state}），"
                    f"checksum/manifest 记录{'完备' if ok else '不完备'}"
                )
        if URI_RE.match(target):
            return None, f"外部 URI {target} 无法机械验证存在性"
        path_state, _path, path_detail = _locate(
            root, target, allow_external=False, require_file=True
        )
        if path_state == "local":
            return True, f"路径 {target} 存在且为 regular file"
        if path_state == "missing":
            return False, f"路径 {target} 不存在"
        return False, f"artifact-exists path 非法：{path_detail}"
    if kind == "checksum-verified":
        # 语义（决策 3「checksum 状态为已校验通过」）：只有 validator 真算 sha256 且
        # 比对通过才为 True；「理由完备的无 checksum」是 waived、「登记了 checksum 但
        # bytes 不可达」是 recorded-unverified——两者都 ≠ verified，不放行。
        aid = c.get("artifact")
        if not _filled(aid):
            return "malformed", "checksum-verified 缺 artifact 字段"
        for itype in COVERED_INDEX_TYPES:
            if any(aid.startswith(p) for p in INDEX_SPECS[itype]["id_prefixes"]):
                entry = _index_ids(root, itype)[0].get(aid)
                if entry is None:
                    return False, f"{itype}-index 无条目 {aid}"
                location = entry.get("location") or ""
                sub = Report()
                _check_entry_checksum(root, entry, aid, location, sub)
                if sub.fails or sub.unknowns:
                    return False, f"{aid} checksum 记录不完备或校验失败"
                state = _checksum_verification_state(root, entry, location)
                if state == "verified":
                    return True, f"{aid} checksum 已真算 sha256 且比对通过"
                return False, (
                    f"{aid} checksum 状态为 {state}（记录完备但未经真实校验），"
                    "waived/recorded-unverified ≠ verified——本 kind 只认真算比对通过"
                )
        return "malformed", f"checksum-verified 的 artifact={aid} 不匹配任何已知 index 前缀"
    if kind == "run-closed":
        run_id = c.get("run")
        if not _filled(run_id):
            return "malformed", "run-closed 缺 run 字段"
        run = runs.get(run_id)
        ok = bool(run) and run.get("status") == "done" and _filled(run.get("run_summary"))
        return ok, f"run {run_id}{'已闭环' if ok else ' 未闭环或不存在'}"
    if kind == "regression-status":
        rid, expect = c.get("regression"), c.get("expect", "pass")
        if not _filled(rid):
            return "malformed", "regression-status 缺 regression 字段"
        reg = regs_by_id.get(rid)
        if reg is None:
            return False, f"regression-matrix 无条目 {rid}"
        actual = reg.get("last_status")
        return actual == expect, f"regression {rid} last_status={actual!r}（期望 {expect!r}）"
    if kind == "evidence-grade-min":
        cid, min_grade = c.get("claim"), c.get("min_grade")
        if not _filled(cid) or min_grade not in GRADE_RANK:
            return "malformed", "evidence-grade-min 需要 claim + 合法 min_grade"
        claim = claims_by_id.get(cid)
        if claim is None:
            return False, f"claims.yaml 无条目 {cid}"
        strongest = max(
            (GRADE_RANK.get((evidence_by_id.get(r) or {}).get("grade"), 0)
             for r in claim_evidence.get(cid, [])),
            default=0,
        )
        ok = strongest >= GRADE_RANK[min_grade]
        return ok, f"claim {cid} 最强证据 rank={strongest}（要求 ≥ {min_grade}）"
    return "malformed", f"kind 非法：{kind!r}（合法：{sorted(STRUCTURED_CHECK_KINDS)}）"


def check_release_gates_structured(
    root: Path, runs: dict, claims_by_id: dict, evidence_by_id: dict,
    claim_evidence: dict[str, list[str]], rep: Report,
) -> None:
    reg_doc, regs = _load_indexed(
        root, "lab/research/regression-matrix.yaml", "regressions", rep, "regression-matrix"
    )
    _check_schema_version(reg_doc, "lab/research/regression-matrix.yaml", rep)
    regs_by_id = _entries_by_id(regs, "regression-matrix", rep)
    gates_doc, gates = _load_indexed(
        root, "lab/research/release-gates.yaml", "gates", rep, "release-gates"
    )
    _check_schema_version(gates_doc, "lab/research/release-gates.yaml", rep)
    _entries_by_id(gates, "release-gates", rep)
    for g in gates:
        gid, status = g.get("id"), g.get("gate_status")
        if status not in {"open", "passed", "blocked"}:
            rep.fail(f"gate {gid}：gate_status 非法：{status!r}")
        if status == "passed":
            claim_id = g.get("for_claim")
            if not _filled(claim_id) or claim_id not in claims_by_id:
                rep.fail(f"gate {gid}：passed gate 的 for_claim 缺失/占位/不存在：{claim_id!r}")
            if "for_deliverable" in g and not _filled(g.get("for_deliverable")):
                rep.fail(f"gate {gid}：passed gate 的 for_deliverable 不得保留 placeholder")
            if not _filled(g.get("approved_by")):
                rep.fail(f"gate {gid}：passed gate 的 approved_by 缺失或占位")
            if not (g.get("structured_checks") or []):
                rep.fail(f"gate {gid}：passed gate 不得没有 structured_checks")
        for n, c in enumerate(g.get("structured_checks") or []):
            if not isinstance(c, dict):
                rep.fail(f"gate {gid}：structured_checks[{n}] 不是映射")
                continue
            # 模板占位（任意值以 < 开头）天然跳过。
            if any(isinstance(v, str) and v.strip().startswith("<") for v in c.values()):
                if status == "passed":
                    rep.fail(
                        f"gate {gid} structured_checks[{n}]：passed gate 不得含 placeholder"
                    )
                continue
            ident = f"gate {gid} structured_checks[{n}]（kind={c.get('kind')}）"
            result, detail = _eval_structured_check(
                root, c, runs, claims_by_id, evidence_by_id, claim_evidence, regs_by_id
            )
            if result == "malformed":
                rep.fail(f"{ident}：{detail}")
            elif result is None:
                if status == "passed":
                    rep.fail(
                        f"{ident}：结果 unknown（{detail}）但 gate_status=passed——"
                        "fail-closed，不该放行"
                    )
                else:
                    rep.advise(f"{ident}：{detail}")
            elif result:
                rep.ok(f"{ident}：满足——{detail}")
            elif status == "passed":
                rep.fail(f"{ident}：不满足（{detail}）但 gate_status=passed——不该放行")
            else:
                rep.advise(
                    f"{ident}：不满足（{detail}）；建议信号，gate_status={status}，"
                    "翻转仍是 human 动作"
                )


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def run_checks(root: Path, rep: Report) -> None:
    runs = _load_runs(root, rep)
    claims_by_id, claim_ids = _load_claims(root, rep)
    check_artifact_indexes(root, runs, claim_ids, rep)
    evidence_by_id, valid_evidence_ids = check_evidence(root, runs, rep)
    claim_evidence = check_claim_evidence_edges(
        claims_by_id, evidence_by_id, valid_evidence_ids, rep
    )
    check_deliverables_index(root, claims_by_id, claim_evidence, rep)
    check_claim_markers(root, claim_ids, evidence_by_id, valid_evidence_ids, rep)
    check_release_gates_structured(
        root, runs, claims_by_id, evidence_by_id, claim_evidence, rep
    )


def _print_report(rep: Report, strict: bool) -> int:
    for msg in rep.passes:
        print(f"PASS    {msg}")
    for msg in rep.advisories:
        print(f"ADVISE  {msg}")
    for msg in rep.unknowns:
        print(f"UNKNOWN {msg}")
    for msg in rep.fails:
        print(f"FAIL    {msg}")
    n_f, n_u, n_p = len(rep.fails), len(rep.unknowns), len(rep.passes)
    ok = not n_f and not (strict and n_u)
    print(
        f"\n[check-provenance-chain] {'OK' if ok else 'FAIL'} — "
        f"{n_f} fail, {n_u} unknown, {n_p} pass"
        + ("（strict：unknown 不算 pass）" if strict and n_u else "")
    )
    return 0 if ok else 1


def main(argv: list[str]) -> int:
    if "--self-test" in argv or "--selftest" in argv:
        return _self_test()
    strict = "--strict" in argv
    rep = Report()
    run_checks(REPO, rep)
    return _print_report(rep, strict)


# ---------------------------------------------------------------------------
# self-test：内嵌正负 fixture（决策 5：不新开 tests/、不引入 pytest）
# ---------------------------------------------------------------------------

_GOOD_LEDGER = """\
schema_version: 1
experiments:
  - id: run-001
    question: does X beat Y
    status: done
    commit: abc1234
    config: lab/code/configs/exp1.yaml
    run_summary: lab/code/experiments/run-001.md
    promote: yes
    updated: "2026-07-12"
"""

_GOOD_CLAIMS = """\
schema_version: 1
claims:
  - id: claim-001
    title: method X beats baseline Y on benchmark Z
    status: supported
    evidence: [ev-001]
    verified_by_fresh_reviewer: false
    updated: "2026-07-12"
"""

_GOOD_EVIDENCE = """\
schema_version: 1
evidence:
  - id: ev-001
    supports_claim: claim-001
    grade: metric
    command: uv run python eval.py
    commit: abc1234
    run_id: run-001
    config: lab/code/configs/exp1.yaml
    data_split: dataset-001/test
    metric_source: result-001
    verified_by_fresh_reviewer: false
    updated: "2026-07-12"
"""

_GOOD_DELIVERABLES_INDEX = """\
# deliverables/index.md

| id | 类型 | 路径 | 支撑 claim | 状态 | evidence 齐全 |
| --- | --- | --- | --- | --- | --- |
| paper-1 | paper | `deliverables/paper/README.md` | claim-001 | draft | 是 |
"""

_GOOD_PAPER = """\
# paper

Method X beats baseline Y. <!-- claim: id=claim-001 evidence=ev-001 -->
"""


def _write(root: Path, rel: str, text: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def _result_index(checksum: str, **overrides) -> str:
    e = {
        "location": "lab/runs/exports/result-001.json",
        "commit": "abc1234",
        "config": "lab/code/configs/exp1.yaml",
        "run_id": "run-001",
        "status": "active",
        "checksum_block": (
            f"    checksum: {checksum}\n    checksum_algorithm: sha256\n"
        ),
    }
    e.update(overrides)
    return (
        "schema_version: 1\n"
        "results:\n"
        "  - id: result-001\n"
        "    summary: main metric export\n"
        f"    location: \"{e['location']}\"\n"
        "    how_to_inspect: cat\n"
        f"    commit: {e['commit']}\n"
        f"    config: {e['config']}\n"
        f"    run_id: {e['run_id']}\n"
        "    supports: claim-001\n"
        f"    status: {e['status']}\n"
        f"{e['checksum_block']}"
        "    updated: \"2026-07-12\"\n"
        "  - id: result-002\n"
        "    summary: externally hosted parquet\n"
        "    location: \"s3://bucket/results/result-002.parquet\"\n"
        "    how_to_inspect: aws s3 cp\n"
        "    commit: abc1234\n"
        "    config: lab/code/configs/exp1.yaml\n"
        "    run_id: run-001\n"
        "    supports: claim-001\n"
        "    status: active\n"
        "    checksum_unavailable_reason: external-uri-no-checksum\n"
        "    checksum_unavailable_justification: \"结果由上游 pipeline 托管在 s3，"
        "当前未导出 checksum，待 pipeline 补 sha256 后回填\"\n"
        "    updated: \"2026-07-12\"\n"
    )


_GOOD_DATASET_INDEX = """\
schema_version: 1
datasets:
  - id: dataset-001
    summary: benchmark Z eval set
    location: "https://example.org/datasets/z-v1.tar.gz"
    how_to_inspect: tar -tzf
    commit: abc1234
    splits: [train, test]
    status: active
    provenance_unavailable_reason: external-origin
    provenance_unavailable_justification: "外部基准集由上游发布，无本 repo run/config 来源"
    checksum_unavailable_reason: external-uri-no-checksum
    checksum_unavailable_justification: "上游只发布 tarball，未发布 sha256；镜像后回填"
    updated: "2026-07-12"
"""

_GOOD_REGRESSIONS = """\
schema_version: 1
regressions:
  - id: reg-001
    guards_claim: claim-001
    code_path: lab/code/src/core.py
    check_kind: smoke
    command: uv run pytest -k smoke
    last_status: pass
    last_run: "2026-07-12"
"""

_GOOD_GATES = """\
schema_version: 1
gates:
  - id: gate-001
    for_claim: claim-001
    requirements:
      - "叙述充分（human 判断）"
    structured_checks:
      - kind: run-closed
        run: run-001
      - kind: regression-status
        regression: reg-001
        expect: pass
      - kind: evidence-grade-min
        claim: claim-001
        min_grade: metric
      - kind: checksum-verified
        artifact: result-001
      - kind: artifact-exists
        target: result-001
      - kind: artifact-exists
        target: result-002
    gate_status: open
    approved_by: human-reviewer
    updated: "2026-07-12"
"""

# 其余 index 类型的最小合法文件（schema_version + 空列表）。
_EMPTY_INDEXES = {
    "lab/artifacts/table-index.yaml": "tables",
    "lab/artifacts/figure-index.yaml": "figures",
    "lab/artifacts/trace-index.yaml": "traces",
    "lab/artifacts/model-index.yaml": "models",
    "lab/models/checkpoint-index.yaml": "checkpoints",
}


def _make_good(root: Path) -> str:
    """写正常闭环 fixture，返回真实 bytes 的 sha256。"""
    payload = b'{"metric": 0.93, "baseline": 0.90}\n'
    _write(root, "lab/runs/exports/result-001.json", payload.decode())
    digest = hashlib.sha256(payload).hexdigest()
    _write(root, "lab/research/experiment-ledger.yaml", _GOOD_LEDGER)
    _write(root, "lab/research/claims.yaml", _GOOD_CLAIMS)
    _write(root, "lab/research/evidence.yaml", _GOOD_EVIDENCE)
    _write(root, "lab/research/regression-matrix.yaml", _GOOD_REGRESSIONS)
    _write(root, "lab/research/release-gates.yaml", _GOOD_GATES)
    _write(root, "lab/artifacts/result-index.yaml", _result_index(digest))
    _write(root, "lab/data/dataset-index.yaml", _GOOD_DATASET_INDEX)
    for rel, key in _EMPTY_INDEXES.items():
        _write(root, rel, f"schema_version: 1\n{key}: []\n")
    _write(root, "deliverables/index.md", _GOOD_DELIVERABLES_INDEX)
    _write(root, "deliverables/paper/README.md", _GOOD_PAPER)
    return digest


def _run_case(name: str, mutate, expect_fail_substrings: list[str],
              expect_ok: bool, failures: list[str]) -> None:
    import tempfile

    with tempfile.TemporaryDirectory(prefix="provenance-fixture-") as tmp:
        root = Path(tmp)
        digest = _make_good(root)
        if mutate is not None:
            mutate(root, digest)
        rep = Report()
        run_checks(root, rep)
        if expect_ok:
            if rep.fails or rep.unknowns:
                failures.append(
                    f"{name}：期望全通过，实际 fails={rep.fails} unknowns={rep.unknowns}"
                )
            return
        if not rep.fails:
            failures.append(f"{name}：期望有 FAIL，实际 0 fail")
            return
        joined = "\n".join(rep.fails)
        for sub in expect_fail_substrings:
            if sub not in joined:
                failures.append(f"{name}：期望 FAIL 信息包含 {sub!r}，实际：\n{joined}")


def _self_test() -> int:
    failures: list[str] = []

    # 正例：完整闭环（本地 bytes 真校验 + 外部 URI 记录完备）全 PASS、零 unknown。
    _run_case("positive-closed-loop", None, [], True, failures)

    # 负例 1：missing file —— location 指向 repo 内不存在的文件。
    def bad_missing(root: Path, digest: str) -> None:
        _write(root, "lab/artifacts/result-index.yaml",
               _result_index(digest, location="lab/runs/exports/gone.json"))
    _run_case("negative-missing-file", bad_missing, ["不存在的文件"], False, failures)

    # 负例 2：bad checksum —— 登记值与实际 bytes 不符。
    def bad_sum(root: Path, digest: str) -> None:
        flipped = ("0" if digest[0] != "0" else "1") + digest[1:]
        _write(root, "lab/artifacts/result-index.yaml", _result_index(flipped))
    _run_case("negative-bad-checksum", bad_sum, ["checksum 不匹配"], False, failures)

    # 负例 3：悬空引用 —— evidence.metric_source 指向不存在的 result 条目。
    def dangling_ref(root: Path, digest: str) -> None:
        _write(root, "lab/research/evidence.yaml",
               _GOOD_EVIDENCE.replace("metric_source: result-001",
                                      "metric_source: result-999"))
    _run_case("negative-dangling-evidence-ref", dangling_ref,
              ["metric_source=result-999", "不存在"], False, failures)

    # 负例 4：未闭环 run —— run 仍 running 却被 result/evidence 引用。
    def open_run(root: Path, digest: str) -> None:
        _write(root, "lab/research/experiment-ledger.yaml",
               _GOOD_LEDGER.replace("status: done", "status: running"))
    _run_case("negative-unclosed-run", open_run, ["未闭环 run"], False, failures)

    # 负例 5：checksum 逃逸口 —— 枚举外 reason 判 FAIL（不是 unknown）。
    def bad_reason(root: Path, digest: str) -> None:
        _write(root, "lab/artifacts/result-index.yaml",
               _result_index(digest).replace(
                   "external-uri-no-checksum", "dont-feel-like-it"))
    _run_case("negative-bad-reason-enum", bad_reason,
              ["checksum_unavailable_reason 非法"], False, failures)

    # 负例 6：占位理由 —— justification 写 TBD 判 FAIL。
    def placeholder_just(root: Path, digest: str) -> None:
        text = _result_index(digest)
        text = re.sub(r'checksum_unavailable_justification: ".*"',
                      'checksum_unavailable_justification: "TBD"', text)
        _write(root, "lab/artifacts/result-index.yaml", text)
    _run_case("negative-placeholder-justification", placeholder_just,
              ["为空或占位"], False, failures)

    # 负例 7：过强 claim（deliverable 层）——「evidence 齐全=是」但 claim 无 evidence。
    def overclaim_deliverable(root: Path, digest: str) -> None:
        _write(root, "lab/research/claims.yaml",
               _GOOD_CLAIMS.replace("evidence: [ev-001]", "evidence: []")
                           .replace("status: supported", "status: proposed"))
        _write(root, "lab/research/evidence.yaml",
               "schema_version: 1\nevidence: []\n")
        _write(root, "deliverables/paper/README.md", "# paper\n")
    _run_case("negative-deliverable-overclaim", overclaim_deliverable,
              ["evidence 齐全」列为「是」"], False, failures)

    # 负例 8：deliverable 引用未知 claim；marker 引用未知 evidence。
    def dangling_claim(root: Path, digest: str) -> None:
        _write(root, "deliverables/index.md",
               _GOOD_DELIVERABLES_INDEX.replace("claim-001", "claim-999"))
        _write(root, "deliverables/paper/README.md",
               _GOOD_PAPER.replace("evidence=ev-001", "evidence=ev-999"))
    _run_case("negative-dangling-claim-and-marker", dangling_claim,
              ["引用未知 claim：claim-999", "ev-999 不存在"], False, failures)

    # 负例 9：schema_version 缺失。
    def no_schema_version(root: Path, digest: str) -> None:
        _write(root, "lab/research/claims.yaml",
               _GOOD_CLAIMS.replace("schema_version: 1\n", ""))
    _run_case("negative-missing-schema-version", no_schema_version,
              ["schema_version", "缺失或非法"], False, failures)

    # 负例 10：submitted 状态但「evidence 齐全」列为否。
    def premature_submit(root: Path, digest: str) -> None:
        _write(root, "deliverables/index.md",
               _GOOD_DELIVERABLES_INDEX.replace("| draft | 是 |", "| submitted | 否 |"))
    _run_case("negative-submitted-without-evidence", premature_submit,
              ["要求「evidence 齐全」列为「是」"], False, failures)

    # --- Phase B：其余 index 类型 + release gate 结构化检查 ---

    # 负例 11：evidence.data_split 指向不存在的 dataset 条目。
    def dangling_dataset(root: Path, digest: str) -> None:
        _write(root, "lab/research/evidence.yaml",
               _GOOD_EVIDENCE.replace("data_split: dataset-001/test",
                                      "data_split: dataset-999/test"))
    _run_case("negative-dangling-dataset-split", dangling_dataset,
              ["data_split=dataset-999/test", "不存在"], False, failures)

    # 负例 12：model-index checkpoint_ref 悬空 + checkpoint 未闭环 run。
    def dangling_ckpt(root: Path, digest: str) -> None:
        _write(root, "lab/artifacts/model-index.yaml",
               "schema_version: 1\n"
               "models:\n"
               "  - id: model-001\n"
               "    name: main model\n"
               "    location: \"s3://bucket/weights/model-001\"\n"
               "    checkpoint_ref: ckpt-999\n"
               "    commit: abc1234\n"
               "    config: lab/code/configs/exp1.yaml\n"
               "    run_id: run-001\n"
               "    status: active\n"
               "    checksum_unavailable_reason: external-uri-no-checksum\n"
               "    checksum_unavailable_justification: \"权重在对象存储，"
               "由训练框架管理，暂无导出的 sha256\"\n"
               "    updated: \"2026-07-12\"\n")
    _run_case("negative-dangling-checkpoint-ref", dangling_ckpt,
              ["checkpoint_ref 指向未知 checkpoint：ckpt-999"], False, failures)

    # 负例 13：未通过 gate —— gate_status=passed 但 regression last_status=fail。
    def gate_passed_but_failing(root: Path, digest: str) -> None:
        _write(root, "lab/research/regression-matrix.yaml",
               _GOOD_REGRESSIONS.replace("last_status: pass", "last_status: fail"))
        _write(root, "lab/research/release-gates.yaml",
               _GOOD_GATES.replace("gate_status: open", "gate_status: passed"))
    _run_case("negative-gate-passed-but-failing-check", gate_passed_but_failing,
              ["gate_status=passed——不该放行"], False, failures)

    # 负例 13b：同样的失败检查，但 gate 仍 open —— 只是建议信号，不算 FAIL。
    def gate_open_failing(root: Path, digest: str) -> None:
        _write(root, "lab/research/regression-matrix.yaml",
               _GOOD_REGRESSIONS.replace("last_status: pass", "last_status: fail"))
    with_advice_ok = []
    _run_case("positive-gate-open-advisory-only", gate_open_failing,
              [], True, with_advice_ok)
    failures.extend(with_advice_ok)

    # 负例 14：structured check kind 枚举外。
    def bad_kind(root: Path, digest: str) -> None:
        _write(root, "lab/research/release-gates.yaml",
               _GOOD_GATES.replace("kind: run-closed", "kind: vibes-good"))
    _run_case("negative-structured-check-bad-kind", bad_kind,
              ["kind 非法"], False, failures)

    # 负例 15：evidence-grade-min 不达标且 gate 已 passed。
    def grade_below_min(root: Path, digest: str) -> None:
        _write(root, "lab/research/release-gates.yaml",
               _GOOD_GATES.replace("min_grade: metric", "min_grade: figure")
                          .replace("gate_status: open", "gate_status: passed"))
    _run_case("negative-evidence-grade-below-min", grade_below_min,
              ["最强证据 rank=", "不该放行"], False, failures)

    # --- 初审修复（2026-07-13）：MAJOR-1 deliverable marker-or-review ---

    # 正例：submitted + 齐全=是 + 正文有 marker（任务 5.3 主路径）。
    def submitted_with_marker(root: Path, digest: str) -> None:
        _write(root, "deliverables/index.md",
               _GOOD_DELIVERABLES_INDEX.replace("| draft |", "| submitted |"))
    _run_case("positive-submitted-with-marker", submitted_with_marker,
              [], True, failures)

    # 负例 16：submitted + 齐全=是，但零 marker、零人工 review 证据 → FAIL。
    def no_marker_no_review(root: Path, digest: str) -> None:
        _write(root, "deliverables/index.md",
               _GOOD_DELIVERABLES_INDEX.replace("| draft |", "| submitted |"))
        _write(root, "deliverables/paper/README.md",
               "# paper\n\nMethod X beats baseline Y.\n")
    _run_case("negative-active-deliverable-no-marker-no-review", no_marker_no_review,
              ["无 claim marker", "人工 review 证据"], False, failures)

    # 正例：零 marker 但登记了人工 review 证据（任务 5.3 兜底路径成立）。
    def review_fallback(root: Path, digest: str) -> None:
        _write(root, "human/reviews/results/paper-1-review.md",
               "# paper-1 review\n\nhuman 复核：claim-001 由 ev-001 支撑。2026-07-12\n")
        _write(root, "deliverables/index.md",
               "# deliverables/index.md\n\n"
               "| id | 类型 | 路径 | 支撑 claim | 状态 | evidence 齐全 | 人工 review |\n"
               "| --- | --- | --- | --- | --- | --- | --- |\n"
               "| paper-1 | paper | `deliverables/paper/README.md` | claim-001 | submitted "
               "| 是 | `human/reviews/results/paper-1-review.md` |\n")
        _write(root, "deliverables/paper/README.md",
               "# paper\n\nMethod X beats baseline Y.\n")
    _run_case("positive-review-evidence-fallback", review_fallback,
              [], True, failures)

    # 负例 17：登记的人工 review 证据文件不存在（悬空引用）。
    def dangling_review(root: Path, digest: str) -> None:
        review_fallback(root, digest)
        (root / "human/reviews/results/paper-1-review.md").unlink()
    _run_case("negative-dangling-review-ref", dangling_review,
              ["review path 非法或不存在"], False, failures)

    # --- 初审修复：MAJOR-2 gate 结构化检查语义收紧 ---

    # 负例 18：checksum-verified 指向 waived 条目（豁免 ≠ 已校验）且 gate=passed。
    def gate_passed_waived_checksum(root: Path, digest: str) -> None:
        _write(root, "lab/research/release-gates.yaml",
               _GOOD_GATES.replace("artifact: result-001", "artifact: result-002")
                          .replace("gate_status: open", "gate_status: passed"))
    _run_case("negative-gate-checksum-waived-not-verified", gate_passed_waived_checksum,
              ["≠ verified", "不该放行"], False, failures)

    # 负例 19：artifact-exists 的条目索引仍在、但 location 文件已不存在，gate=passed。
    def gate_passed_artifact_gone(root: Path, digest: str) -> None:
        (root / "lab/runs/exports/result-001.json").unlink()
        _write(root, "lab/research/release-gates.yaml",
               _GOOD_GATES.replace("gate_status: open", "gate_status: passed"))
    _run_case("negative-gate-artifact-file-missing", gate_passed_artifact_gone,
              ["不存在的文件", "不该放行"], False, failures)

    # --- 初审修复：MAJOR-3 三元组统一 + provenance 豁免；MINOR-4 各类型负例 ---

    # 负例 20：table 条目缺三元组（无 provenance 豁免）。
    def table_missing_triplet(root: Path, digest: str) -> None:
        _write(root, "lab/artifacts/table-index.yaml",
               "schema_version: 1\n"
               "tables:\n"
               "  - id: table-001\n"
               "    caption: main results table\n"
               "    location: \"s3://bucket/tables/table-001.csv\"\n"
               "    how_to_inspect: aws s3 cp\n"
               "    run_id: run-001\n"
               "    status: active\n"
               "    checksum_unavailable_reason: external-uri-no-checksum\n"
               "    checksum_unavailable_justification: \"表格由导出 pipeline 托管在"
               " s3，待回填 sha256\"\n"
               "    updated: \"2026-07-12\"\n")
    _run_case("negative-table-missing-triplet", table_missing_triplet,
              ["table-index table-001：commit 缺失或占位",
               "table-index table-001：config 缺失或占位"], False, failures)

    # 负例 21：figure 条目 supports_claim 悬空引用。
    def figure_dangling_claim(root: Path, digest: str) -> None:
        _write(root, "lab/artifacts/figure-index.yaml",
               "schema_version: 1\n"
               "figures:\n"
               "  - id: figure-001\n"
               "    caption: main curve\n"
               "    location: \"s3://bucket/figures/figure-001.pdf\"\n"
               "    how_to_inspect: aws s3 cp\n"
               "    commit: abc1234\n"
               "    config: lab/code/configs/exp1.yaml\n"
               "    run_id: run-001\n"
               "    supports_claim: claim-999\n"
               "    status: active\n"
               "    checksum_unavailable_reason: external-uri-no-checksum\n"
               "    checksum_unavailable_justification: \"图由绘图 pipeline 托管在"
               " s3，待回填 sha256\"\n"
               "    updated: \"2026-07-12\"\n")
    _run_case("negative-figure-dangling-supports-claim", figure_dangling_claim,
              ["supports 指向未知 claim：claim-999"], False, failures)

    _TRACE_ENTRY = (
        "schema_version: 1\n"
        "traces:\n"
        "  - id: trace-001\n"
        "    kind: human-cc\n"
        "    location: \"s3://bucket/traces/trace-001.jsonl\"\n"
        "    how_to_inspect: aws s3 cp\n"
        "    summary: human-cc session trace\n"
        "    status: active\n"
        "    checksum_unavailable_reason: external-uri-no-checksum\n"
        "    checksum_unavailable_justification: \"trace 由采集端上传对象存储，"
        "暂无导出的 sha256\"\n"
        "    updated: \"2026-07-12\"\n"
    )

    # 负例 22：trace 条目缺三元组且未显式豁免（静默留空不再放行）。
    def trace_missing_triplet(root: Path, digest: str) -> None:
        _write(root, "lab/artifacts/trace-index.yaml", _TRACE_ENTRY)
    _run_case("negative-trace-missing-triplet-no-waiver", trace_missing_triplet,
              ["trace-index trace-001：commit 缺失或占位",
               "provenance_unavailable_reason/justification 显式豁免"],
              False, failures)

    # 正例：同一 trace 条目，带显式 provenance 豁免（human-authored）→ 放行。
    def trace_with_waiver(root: Path, digest: str) -> None:
        _write(root, "lab/artifacts/trace-index.yaml",
               _TRACE_ENTRY.replace(
                   "    updated:",
                   "    provenance_unavailable_reason: human-authored\n"
                   "    provenance_unavailable_justification: \"human-cc 会话"
                   "手工产生，无 run/config 来源\"\n"
                   "    updated:"))
    _run_case("positive-trace-provenance-waiver", trace_with_waiver,
              [], True, failures)

    # 负例 23：provenance 豁免理由为占位（TBD）→ 逃逸口关闭。
    def waiver_placeholder_just(root: Path, digest: str) -> None:
        _write(root, "lab/data/dataset-index.yaml",
               re.sub(r'provenance_unavailable_justification: ".*"',
                      'provenance_unavailable_justification: "TBD"',
                      _GOOD_DATASET_INDEX))
    _run_case("negative-provenance-waiver-placeholder", waiver_placeholder_just,
              ["provenance_unavailable_justification 为空或占位"], False, failures)

    # 负例 24：checkpoint 条目 run_id 悬空引用（experiment-ledger 中不存在）。
    def checkpoint_dangling_run(root: Path, digest: str) -> None:
        _write(root, "lab/models/checkpoint-index.yaml",
               "schema_version: 1\n"
               "checkpoints:\n"
               "  - id: ckpt-001\n"
               "    name: best checkpoint\n"
               "    location: \"s3://bucket/ckpts/ckpt-001\"\n"
               "    how_to_inspect: aws s3 ls\n"
               "    commit: abc1234\n"
               "    config: lab/code/configs/exp1.yaml\n"
               "    run_id: run-999\n"
               "    status: active\n"
               "    checksum_unavailable_reason: external-uri-no-checksum\n"
               "    checksum_unavailable_justification: \"checkpoint 由训练框架"
               "写入对象存储，暂无导出的 sha256\"\n"
               "    updated: \"2026-07-12\"\n")
    _run_case("negative-checkpoint-dangling-run", checkpoint_dangling_run,
              ["checkpoint-index ckpt-001", "run_id=run-999 不存在"], False, failures)

    # --- fresh review 修复：placeholder 不能激活/贡献 claim 强度 ---

    def active_artifact_placeholder(root: Path, digest: str) -> None:
        _write(root, "lab/artifacts/result-index.yaml",
               _result_index(digest, location="<still-placeholder>"))
    _run_case("negative-active-artifact-placeholder", active_artifact_placeholder,
              ["status='active' 时 location 不得为空/占位"], False, failures)

    def active_artifact_no_inspection(root: Path, digest: str) -> None:
        _write(root, "lab/artifacts/result-index.yaml",
               _result_index(digest).replace("how_to_inspect: cat",
                                             "how_to_inspect: <TBD>"))
    _run_case("negative-active-artifact-how-to-inspect", active_artifact_no_inspection,
              ["how_to_inspect 缺失或占位"], False, failures)

    def placeholder_evidence_passed_gate(root: Path, digest: str) -> None:
        _write(root, "lab/research/evidence.yaml",
               _GOOD_EVIDENCE.replace("commit: abc1234", "commit: <git-sha>"))
        _write(root, "lab/research/release-gates.yaml",
               _GOOD_GATES.replace("gate_status: open", "gate_status: passed"))
    _run_case(
        "negative-placeholder-evidence-no-claim-strength",
        placeholder_evidence_passed_gate,
        ["占位/不完整记录", "最强证据 rank=0", "不该放行"], False, failures,
    )

    def submitted_placeholder_claim(root: Path, digest: str) -> None:
        _write(root, "deliverables/index.md",
               _GOOD_DELIVERABLES_INDEX.replace("claim-001 | draft",
                                                "<claim-id> | submitted"))
    _run_case("negative-submitted-placeholder-claim", submitted_placeholder_claim,
              ["引用未知 claim：claim-id"], False, failures)

    def passed_gate_placeholder(root: Path, digest: str) -> None:
        _write(root, "lab/research/release-gates.yaml",
               _GOOD_GATES.replace("run: run-001", "run: <run-id>")
                          .replace("gate_status: open", "gate_status: passed"))
    _run_case("negative-passed-gate-placeholder", passed_gate_placeholder,
              ["passed gate 不得含 placeholder"], False, failures)

    def passed_gate_all_verified(root: Path, digest: str) -> None:
        _write(root, "lab/research/release-gates.yaml",
               _GOOD_GATES.replace("gate_status: open", "gate_status: passed"))
    _run_case("positive-passed-gate-fully-verified", passed_gate_all_verified,
              [], True, failures)

    # claim→evidence 与 deliverable row→marker 必须是同一条边，不可只验存在。
    def wrong_evidence_owner(root: Path, digest: str) -> None:
        _write(root, "lab/research/evidence.yaml",
               _GOOD_EVIDENCE.replace("supports_claim: claim-001",
                                      "supports_claim: claim-999"))
    _run_case("negative-evidence-supports-wrong-claim", wrong_evidence_owner,
              ["supports_claim='claim-999'", "归属边不匹配"], False, failures)

    def marker_misses_row_claim(root: Path, digest: str) -> None:
        _write(root, "lab/research/claims.yaml",
               _GOOD_CLAIMS.replace(
                   "    updated: \"2026-07-12\"\n",
                   "    updated: \"2026-07-12\"\n"
                   "  - id: claim-002\n"
                   "    title: second supported claim\n"
                   "    status: supported\n"
                   "    evidence: [ev-002]\n"
                   "    verified_by_fresh_reviewer: false\n"
                   "    updated: \"2026-07-12\"\n",
               ))
        _write(root, "lab/research/evidence.yaml",
               _GOOD_EVIDENCE.replace(
                   "    updated: \"2026-07-12\"\n",
                   "    updated: \"2026-07-12\"\n"
                   "  - id: ev-002\n"
                   "    supports_claim: claim-002\n"
                   "    grade: metric\n"
                   "    command: uv run python eval.py --second\n"
                   "    commit: abc1234\n"
                   "    run_id: run-001\n"
                   "    config: lab/code/configs/exp1.yaml\n"
                   "    data_split: dataset-001/test\n"
                   "    metric_source: result-001\n"
                   "    verified_by_fresh_reviewer: false\n"
                   "    updated: \"2026-07-12\"\n",
               ))
        _write(root, "deliverables/index.md",
               _GOOD_DELIVERABLES_INDEX.replace(
                   "claim-001 | draft", "claim-001, claim-002 | submitted"
               ))
    _run_case("negative-marker-does-not-cover-row-claims", marker_misses_row_claim,
              ["marker 未覆盖该行 claim", "claim-002"], False, failures)

    # passed gate 遇到 artifact-exists unknown 必须 fail-closed，不能仅 ADVISE。
    def passed_gate_external_unknown(root: Path, digest: str) -> None:
        _write(root, "lab/research/release-gates.yaml",
               _GOOD_GATES.replace("target: result-002",
                                   "target: https://example.org/result.bin")
                          .replace("gate_status: open", "gate_status: passed"))
    _run_case("negative-passed-gate-artifact-unknown", passed_gate_external_unknown,
              ["结果 unknown", "fail-closed", "不该放行"], False, failures)

    # 所有路径入口统一拒绝 absolute / .. / symlink escape / directory。
    def artifact_absolute(root: Path, digest: str) -> None:
        _write(root, "lab/artifacts/result-index.yaml",
               _result_index(digest, location="/etc/passwd"))
    _run_case("negative-artifact-absolute-path", artifact_absolute,
              ["拒绝 absolute path"], False, failures)

    def artifact_windows_absolute(root: Path, digest: str) -> None:
        _write(root, "lab/artifacts/result-index.yaml",
               _result_index(digest, location="C:/outside/result.json"))
    _run_case("negative-artifact-windows-absolute", artifact_windows_absolute,
              ["拒绝 absolute path"], False, failures)

    def artifact_parent_escape(root: Path, digest: str) -> None:
        _write(root, "lab/artifacts/result-index.yaml",
               _result_index(digest, location="../outside.json"))
    _run_case("negative-artifact-dotdot", artifact_parent_escape,
              ["拒绝包含 '..'"], False, failures)

    def artifact_symlink_escape(root: Path, digest: str) -> None:
        link = root / "lab/runs/exports/escape.json"
        link.symlink_to("/etc/passwd")
        _write(root, "lab/artifacts/result-index.yaml",
               _result_index(digest, location="lab/runs/exports/escape.json"))
    _run_case("negative-artifact-symlink-escape", artifact_symlink_escape,
              ["symlink escape"], False, failures)

    def artifact_directory(root: Path, digest: str) -> None:
        _write(root, "lab/artifacts/result-index.yaml",
               _result_index(digest, location="lab/runs/exports"))
    _run_case("negative-artifact-directory-no-crash", artifact_directory,
              ["不是 regular file（目录）"], False, failures)

    def manifest_escape(root: Path, digest: str) -> None:
        _write(root, "lab/artifacts/result-index.yaml",
               _result_index(digest, checksum_block="    manifest: ../evil.yaml\n"))
    _run_case("negative-manifest-dotdot", manifest_escape,
              ["manifest path 非法", "拒绝包含 '..'"], False, failures)

    def manifest_absolute(root: Path, digest: str) -> None:
        _write(root, "lab/artifacts/result-index.yaml",
               _result_index(digest, checksum_block="    manifest: /etc/passwd\n"))
    _run_case("negative-manifest-absolute", manifest_absolute,
              ["manifest path 非法", "拒绝 absolute path"], False, failures)

    def manifest_entry_escape(root: Path, digest: str) -> None:
        _write(root, "lab/data/manifests/result-001.yaml",
               "files:\n"
               "  - path: ../outside.bin\n"
               f"    sha256: {digest}\n")
        _write(root, "lab/artifacts/result-index.yaml",
               _result_index(
                   digest,
                   checksum_block="    manifest: lab/data/manifests/result-001.yaml\n",
               ))
    _run_case("negative-manifest-entry-dotdot", manifest_entry_escape,
              ["artifact path 非法", "拒绝包含 '..'"], False, failures)

    def manifest_entry_absolute(root: Path, digest: str) -> None:
        _write(root, "lab/data/manifests/result-001.yaml",
               "files:\n"
               "  - path: /etc/passwd\n"
               f"    sha256: {digest}\n")
        _write(root, "lab/artifacts/result-index.yaml",
               _result_index(
                   digest,
                   checksum_block="    manifest: lab/data/manifests/result-001.yaml\n",
               ))
    _run_case("negative-manifest-entry-absolute", manifest_entry_absolute,
              ["artifact path 非法", "拒绝 absolute path"], False, failures)

    def manifest_entry_directory(root: Path, digest: str) -> None:
        _write(root, "lab/data/manifests/result-001.yaml",
               "files:\n"
               "  - path: lab/runs/exports\n"
               f"    sha256: {digest}\n")
        _write(root, "lab/artifacts/result-index.yaml",
               _result_index(
                   digest,
                   checksum_block="    manifest: lab/data/manifests/result-001.yaml\n",
               ))
    _run_case("negative-manifest-entry-directory", manifest_entry_directory,
              ["artifact path 非法", "不是 regular file（目录）"], False, failures)

    def manifest_entry_symlink_escape(root: Path, digest: str) -> None:
        link = root / "lab/runs/exports/manifest-escape.bin"
        link.symlink_to("/etc/passwd")
        _write(root, "lab/data/manifests/result-001.yaml",
               "files:\n"
               "  - path: lab/runs/exports/manifest-escape.bin\n"
               f"    sha256: {digest}\n")
        _write(root, "lab/artifacts/result-index.yaml",
               _result_index(
                   digest,
                   checksum_block="    manifest: lab/data/manifests/result-001.yaml\n",
               ))
    _run_case("negative-manifest-entry-symlink", manifest_entry_symlink_escape,
              ["artifact path 非法", "symlink escape"], False, failures)

    def manifest_missing_waived_passed_gate(root: Path, digest: str) -> None:
        _write(root, "lab/data/manifests/result-001.yaml",
               "files:\n"
               "  - path: lab/runs/exports/not-uploaded.bin\n"
               "    checksum_unavailable_reason: pending-upload\n"
               "    checksum_unavailable_justification: \"bytes 尚未上传，"
               "manifest 条目先行登记并等待产物落盘\"\n")
        _write(root, "lab/artifacts/result-index.yaml",
               _result_index(
                   digest,
                   location="s3://bucket/results/result-001",
                   checksum_block="    manifest: lab/data/manifests/result-001.yaml\n",
               ))
        _write(root, "lab/research/release-gates.yaml",
               _GOOD_GATES.replace(
                   "      - kind: checksum-verified\n"
                   "        artifact: result-001\n", ""
               ).replace("gate_status: open", "gate_status: passed"))
    _run_case("negative-manifest-local-member-missing-waived-passed-gate",
              manifest_missing_waived_passed_gate,
              ["manifest local path 不存在 regular file", "不该放行"],
              False, failures)

    def manifest_directory(root: Path, digest: str) -> None:
        (root / "lab/data/manifests").mkdir(parents=True, exist_ok=True)
        _write(root, "lab/artifacts/result-index.yaml",
               _result_index(
                   digest, checksum_block="    manifest: lab/data/manifests\n"
               ))
    _run_case("negative-manifest-directory-no-crash", manifest_directory,
              ["manifest path 非法", "不是 regular file（目录）"], False, failures)

    def manifest_symlink_escape(root: Path, digest: str) -> None:
        link = root / "lab/data/manifests/escape.yaml"
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to("/etc/passwd")
        _write(root, "lab/artifacts/result-index.yaml",
               _result_index(
                   digest,
                   checksum_block="    manifest: lab/data/manifests/escape.yaml\n",
               ))
    _run_case("negative-manifest-symlink-escape", manifest_symlink_escape,
              ["manifest path 非法", "symlink escape"], False, failures)

    def deliverable_absolute(root: Path, digest: str) -> None:
        _write(root, "deliverables/index.md",
               _GOOD_DELIVERABLES_INDEX.replace(
                   "`deliverables/paper/README.md`", "`/etc/passwd`"
               ))
    _run_case("negative-deliverable-absolute", deliverable_absolute,
              ["deliverable path 非法", "拒绝 absolute path"], False, failures)

    def deliverable_directory(root: Path, digest: str) -> None:
        _write(root, "deliverables/index.md",
               _GOOD_DELIVERABLES_INDEX.replace(
                   "`deliverables/paper/README.md`", "`deliverables/paper/`"
               ))
    _run_case("negative-deliverable-directory", deliverable_directory,
              ["不是 regular file（目录）"], False, failures)

    def deliverable_parent_escape(root: Path, digest: str) -> None:
        _write(root, "deliverables/index.md",
               _GOOD_DELIVERABLES_INDEX.replace(
                   "`deliverables/paper/README.md`", "`../outside.md`"
               ))
    _run_case("negative-deliverable-dotdot", deliverable_parent_escape,
              ["deliverable path 非法", "拒绝包含 '..'"], False, failures)

    def deliverable_symlink_escape(root: Path, digest: str) -> None:
        path = root / "deliverables/paper/README.md"
        path.unlink()
        path.symlink_to("/etc/passwd")
    _run_case("negative-deliverable-symlink-escape", deliverable_symlink_escape,
              ["deliverable path 非法", "symlink escape"], False, failures)

    def review_path_escape(root: Path, digest: str) -> None:
        _write(root, "deliverables/index.md",
               "# deliverables/index.md\n\n"
               "| id | 类型 | 路径 | 支撑 claim | 状态 | evidence 齐全 | 人工 review |\n"
               "| --- | --- | --- | --- | --- | --- | --- |\n"
               "| paper-1 | paper | `deliverables/paper/README.md` | claim-001 "
               "| submitted | 是 | `human/reviews/results/../../../../etc/passwd` |\n")
        _write(root, "deliverables/paper/README.md", "# paper\n\nNo marker.\n")
    _run_case("negative-review-path-escape", review_path_escape,
              ["review path 非法", "拒绝包含 '..'"], False, failures)

    def review_absolute(root: Path, digest: str) -> None:
        _write(root, "deliverables/index.md",
               "# deliverables/index.md\n\n"
               "| id | 类型 | 路径 | 支撑 claim | 状态 | evidence 齐全 | 人工 review |\n"
               "| --- | --- | --- | --- | --- | --- | --- |\n"
               "| paper-1 | paper | `deliverables/paper/README.md` | claim-001 "
               "| submitted | 是 | `/etc/passwd` |\n")
        _write(root, "deliverables/paper/README.md", "# paper\n\nNo marker.\n")
    _run_case("negative-review-absolute", review_absolute,
              ["人工 review path 必须位于 human/reviews/results/"], False, failures)

    def review_directory(root: Path, digest: str) -> None:
        (root / "human/reviews/results/paper-1").mkdir(parents=True, exist_ok=True)
        _write(root, "deliverables/index.md",
               "# deliverables/index.md\n\n"
               "| id | 类型 | 路径 | 支撑 claim | 状态 | evidence 齐全 | 人工 review |\n"
               "| --- | --- | --- | --- | --- | --- | --- |\n"
               "| paper-1 | paper | `deliverables/paper/README.md` | claim-001 "
               "| submitted | 是 | `human/reviews/results/paper-1` |\n")
        _write(root, "deliverables/paper/README.md", "# paper\n\nNo marker.\n")
    _run_case("negative-review-directory", review_directory,
              ["review path 非法", "不是 regular file（目录）"], False, failures)

    def review_symlink_escape(root: Path, digest: str) -> None:
        review = root / "human/reviews/results/paper-1-review.md"
        review.parent.mkdir(parents=True, exist_ok=True)
        review.symlink_to("/etc/passwd")
        _write(root, "deliverables/index.md",
               "# deliverables/index.md\n\n"
               "| id | 类型 | 路径 | 支撑 claim | 状态 | evidence 齐全 | 人工 review |\n"
               "| --- | --- | --- | --- | --- | --- | --- |\n"
               "| paper-1 | paper | `deliverables/paper/README.md` | claim-001 "
               "| submitted | 是 | `human/reviews/results/paper-1-review.md` |\n")
        _write(root, "deliverables/paper/README.md", "# paper\n\nNo marker.\n")
    _run_case("negative-review-symlink-escape", review_symlink_escape,
              ["review path 非法", "symlink escape"], False, failures)

    # dataset split 必须存在于 dataset-index.splits；各类 ID 不得静默覆盖。
    def unknown_dataset_split(root: Path, digest: str) -> None:
        _write(root, "lab/research/evidence.yaml",
               _GOOD_EVIDENCE.replace("dataset-001/test", "dataset-001/validation"))
    _run_case("negative-dataset-split-not-declared", unknown_dataset_split,
              ["split='validation'", "splits=['train', 'test']"], False, failures)

    def unregistered_dataset_split(root: Path, digest: str) -> None:
        _write(root, "lab/research/evidence.yaml",
               _GOOD_EVIDENCE.replace("dataset-001/test", "ad-hoc/test"))
    _run_case("negative-dataset-split-unregistered", unregistered_dataset_split,
              ["data_split=ad-hoc/test 未使用已登记的 dataset id/split"],
              False, failures)

    def evidence_references_unknown_artifact(root: Path, digest: str) -> None:
        _write(root, "lab/artifacts/result-index.yaml",
               _result_index(digest, status="unknown"))
    _run_case("negative-evidence-references-unknown-artifact",
              evidence_references_unknown_artifact,
              ["metric_source=result-001 指向 status='unknown'"], False, failures)

    def duplicate_artifact_id(root: Path, digest: str) -> None:
        _write(root, "lab/artifacts/result-index.yaml",
               _result_index(digest).replace("id: result-002", "id: result-001"))
    _run_case("negative-duplicate-artifact-id", duplicate_artifact_id,
              ["result-index：duplicate id result-001"], False, failures)

    def duplicate_research_ids(root: Path, digest: str) -> None:
        _write(root, "lab/research/claims.yaml",
               _GOOD_CLAIMS.replace(
                   "    updated: \"2026-07-12\"\n",
                   "    updated: \"2026-07-12\"\n"
                   "  - id: claim-001\n"
                   "    title: duplicate\n"
                   "    status: proposed\n"
                   "    evidence: []\n",
               ))
        _write(root, "lab/research/evidence.yaml",
               _GOOD_EVIDENCE.replace(
                   "    updated: \"2026-07-12\"\n",
                   "    updated: \"2026-07-12\"\n"
                   "  - id: ev-001\n"
                   "    supports_claim: claim-001\n"
                   "    grade: metric\n"
                   "    command: duplicate\n"
                   "    commit: abc1234\n"
                   "    run_id: run-001\n"
                   "    config: lab/code/configs/exp1.yaml\n",
               ))
    _run_case("negative-duplicate-claim-evidence-ids", duplicate_research_ids,
              ["claims：duplicate id claim-001", "evidence：duplicate id ev-001"],
              False, failures)

    def duplicate_run_gate_ids(root: Path, digest: str) -> None:
        _write(root, "lab/research/experiment-ledger.yaml",
               _GOOD_LEDGER.replace(
                   "    updated: \"2026-07-12\"\n",
                   "    updated: \"2026-07-12\"\n"
                   "  - id: run-001\n"
                   "    question: duplicate\n"
                   "    status: planned\n",
               ))
        _write(root, "lab/research/release-gates.yaml",
               _GOOD_GATES.replace(
                   "    updated: \"2026-07-12\"\n",
                   "    updated: \"2026-07-12\"\n"
                   "  - id: gate-001\n"
                   "    for_claim: claim-001\n"
                   "    gate_status: open\n",
               ))
    _run_case("negative-duplicate-run-gate-ids", duplicate_run_gate_ids,
              ["experiment-ledger：duplicate id run-001",
               "release-gates：duplicate id gate-001"], False, failures)

    if failures:
        for f in failures:
            print(f"SELFTEST-FAIL {f}")
        print(f"\n[check-provenance-chain --self-test] FAIL — {len(failures)} 个断言未过")
        return 1
    print("[check-provenance-chain --self-test] OK — 正负 fixture 全部符合预期")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
