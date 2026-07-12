#!/usr/bin/env python3
"""provenance 链检查：run → artifact → evidence → claim → deliverable。

对应 doctrine：`.agent/artifact-policy.md`（provenance 字段、checksum 政策、claim marker）。
由 `validate-governance.py` 经 run_subcheck 拉起（CI 与手动同源、runtime-neutral），
也可单独运行。不挂任何 runtime hook。

检查项（三态输出：PASS / FAIL / UNKNOWN，unknown 不算 pass）：
1. 覆盖的 index / ledger YAML 带 `schema_version`（整数 ≥1）。
2. artifact index 条目：commit/config/run_id 三元组非占位；run_id 存在于
   experiment-ledger 且 run 已闭环（status=done 且有 run_summary）。
3. checksum：统一 sha256，进程内 hashlib 计算；本地 bytes 可达则真算比对；
   外部 URI / 不可达路径只要求记录完备；无法校验必须给固定枚举 reason +
   非占位 justification，枚举外或占位理由判 FAIL（不是 unknown）。
4. evidence → artifact index 交叉引用（metric_source 等指向 index 条目时必须存在
   且未 archived）；evidence.run_id 的 run 必须闭环。
5. deliverables/index.md → claims.yaml 引用存在；「evidence 齐全」列与 claims 实际
   evidence 一致；submitted/published 状态要求「齐全=是」。
6. deliverable Markdown 正文的 claim marker
   `<!-- claim: id=<claim-id> [evidence=<ev-id>,...] -->` 引用必须存在。

覆盖范围：Phase A 为最短闭环（result-index → evidence → claims → deliverables），
Phase B 用同一套逻辑经 INDEX_SPECS / COVERED_INDEX_TYPES 扩展到其余 index 类型
（见 plans/20260712-artifact-evidence-chain.zh.md 决策 1）。

无第三方硬依赖：PyYAML 可选（缺失时用内置受限解析器回退；再失败记 UNKNOWN，
--strict 下 unknown 也算失败，不静默降级）。模板占位条目（`<...>`）天然通过。

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
JUSTIFICATION_PLACEHOLDERS = {"tbd", "n/a", "na", "none", "todo", "...", "-", "?"}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

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
        # human-cc trace 可无 commit/config；run_id 若填了才校验。
        "required_triplet": (),
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
        # 外部数据集可无 run 来源；run_id 若填了才校验。
        "required_triplet": (),
        "checksum": True,
    },
}

# Phase A：最短闭环只覆盖 result；Phase B 扩展这里的白名单（决策 1）。
COVERED_INDEX_TYPES: tuple[str, ...] = ("result",)

# 覆盖的 research YAML（schema_version 检查）。Phase B 追加 regression/release-gates。
COVERED_RESEARCH_FILES: tuple[str, ...] = (
    "lab/research/claims.yaml",
    "lab/research/evidence.yaml",
    "lab/research/experiment-ledger.yaml",
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

    def fail(self, msg: str) -> None:
        self.fails.append(msg)

    def unknown(self, msg: str) -> None:
        self.unknowns.append(msg)

    def ok(self, msg: str) -> None:
        self.passes.append(msg)


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
    text = path.read_text(encoding="utf-8")
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
    return isinstance(v, str) and bool(v.strip()) and not v.strip().startswith("<")


def _sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _locate(root: Path, location: str) -> tuple[str, Path | None]:
    """判定 location 的可达性：('external'|'local'|'unreachable'|'missing', path)。"""
    if "://" in location:
        return "external", None
    if location.startswith("/"):
        p = Path(location)
        return ("local", p) if p.exists() else ("unreachable", None)
    p = root / location
    return ("local", p) if p.exists() else ("missing", None)


def _load_indexed(root: Path, rel: str, key: str, rep: Report, label: str):
    """加载 YAML 并返回 (doc, entries)；解析失败记 FAIL/UNKNOWN 并返回 (None, [])。"""
    f = root / rel
    if not f.exists():
        rep.unknown(f"{label}：{rel} 不存在，未检查")
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
    entries = doc.get(key) or []
    return doc, [e for e in entries if isinstance(e, dict)]


def _check_schema_version(doc, rel: str, rep: Report) -> None:
    if doc is None:
        return
    sv = doc.get("schema_version")
    if isinstance(sv, int) and sv >= 1:
        rep.ok(f"schema_version：{rel} = {sv}")
    else:
        rep.fail(f"schema_version：{rel} 缺失或非法（应为整数 ≥1，实际 {sv!r}）")


# ---------------------------------------------------------------------------
# checksum / manifest 校验（决策 2/8：统一 sha256 + 固定枚举 reason + 必填理由）
# ---------------------------------------------------------------------------

def _check_justified_unavailable(entry: dict, ident: str, rep: Report) -> None:
    reason = entry.get("checksum_unavailable_reason")
    just = entry.get("checksum_unavailable_justification")
    if reason not in CHECKSUM_UNAVAILABLE_REASONS:
        rep.fail(
            f"{ident}：checksum_unavailable_reason 非法（{reason!r}），"
            f"合法枚举：{sorted(CHECKSUM_UNAVAILABLE_REASONS)}"
        )
        return
    if not _filled(just) or str(just).strip().lower() in JUSTIFICATION_PLACEHOLDERS:
        rep.fail(
            f"{ident}：checksum_unavailable_justification 为空或占位（{just!r}）——"
            "reason 枚举 + 具体人工理由两者都要，防止校验逃逸"
        )
        return
    rep.ok(f"{ident}：无 checksum，reason={reason} 且理由已填，记录完备")


def _verify_sum(root: Path, ident: str, location: str, checksum: str, rep: Report) -> None:
    state, p = _locate(root, location)
    if state == "local":
        actual = _sha256_file(p)
        if actual == checksum:
            rep.ok(f"{ident}：本地 bytes sha256 校验通过")
        else:
            rep.fail(f"{ident}：checksum 不匹配（登记 {checksum[:12]}…，实际 {actual[:12]}…）")
    elif state == "missing":
        rep.fail(f"{ident}：location 指向 repo 内不存在的文件：{location}")
    else:  # external / unreachable：记录完备即通过（bytes 不进 Git）
        rep.ok(f"{ident}：bytes 不在本地（{state}），checksum 已记录，跳过重算")


def _check_manifest(root: Path, ident: str, manifest_rel: str, rep: Report) -> None:
    f = root / manifest_rel
    if not f.exists():
        rep.fail(f"{ident}：manifest 不存在：{manifest_rel}")
        return
    doc, err = load_yaml(f)
    if err is not None:
        kind, msg = err
        if kind == "parse":
            rep.fail(f"{ident}：manifest 解析失败：{msg}")
        else:
            rep.unknown(f"{ident}：manifest 未检查（{msg}）")
        return
    files = (doc or {}).get("files") or []
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
    runs: dict = {}
    for e in entries:
        rid = e.get("id")
        if rid:
            runs[rid] = e
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
    entries = (doc or {}).get(spec["key"]) or []
    by_id = {e.get("id"): e for e in entries if isinstance(e, dict) and e.get("id")}
    return by_id, set(by_id)


def check_artifact_indexes(root: Path, runs: dict, claim_ids: set, rep: Report) -> None:
    for itype in COVERED_INDEX_TYPES:
        spec = INDEX_SPECS[itype]
        doc, entries = _load_indexed(root, spec["file"], spec["key"], rep, f"{itype}-index")
        _check_schema_version(doc, spec["file"], rep)
        for e in entries:
            eid = e.get("id") or "<无 id>"
            ident = f"{itype}-index {eid}"
            status = e.get("status")
            if status not in ARTIFACT_STATUS:
                rep.fail(f"{ident}：status 非法：{status!r}")
            location = e.get("location")
            if not _filled(location):
                # 模板占位条目（location 未填/占位）天然通过，不误伤。
                continue
            # 可复现三元组非占位（任务 2.1）。
            for field in spec["required_triplet"]:
                if not _filled(e.get(field)):
                    rep.fail(f"{ident}：{field} 缺失或占位（可复现三元组必填）")
            # run 闭环（任务 2.2）：required 或已填时校验。
            run_id = e.get("run_id")
            if _filled(run_id):
                _check_run_closed(runs, run_id, ident, rep)
            # supports → claim 引用（若指向 claim id）。
            supports = e.get("supports") or e.get("supports_claim")
            if _filled(supports) and supports.startswith("claim-"):
                if supports in claim_ids:
                    rep.ok(f"{ident}：supports={supports} 存在")
                else:
                    rep.fail(f"{ident}：supports 指向未知 claim：{supports}")
            # checksum / manifest（任务 3.x）。
            if spec["checksum"]:
                _check_entry_checksum(root, e, ident, location, rep)


def _load_claims(root: Path, rep: Report) -> tuple[dict, set[str]]:
    doc, entries = _load_indexed(root, "lab/research/claims.yaml", "claims", rep, "claims")
    _check_schema_version(doc, "lab/research/claims.yaml", rep)
    by_id = {c.get("id"): c for c in entries if c.get("id")}
    return by_id, set(by_id)


def check_evidence(root: Path, runs: dict, rep: Report) -> set:
    """校验 evidence 条目；返回 evidence id 集合（供 marker 检查复用，避免重复加载）。"""
    doc, entries = _load_indexed(root, "lab/research/evidence.yaml", "evidence", rep, "evidence")
    _check_schema_version(doc, "lab/research/evidence.yaml", rep)
    # 交叉引用目标：覆盖范围内的 index 类型（Phase B 自动随白名单扩展）。
    ids_by_type = {t: _index_ids(root, t)[0] for t in COVERED_INDEX_TYPES}
    ref_fields = ("metric_source", "checkpoint", "data_split")
    for e in entries:
        eid = e.get("id") or "<无 id>"
        ident = f"evidence {eid}"
        if not _filled(e.get("commit")):
            continue  # 模板占位条目
        run_id = e.get("run_id")
        if not _filled(run_id):
            rep.fail(f"{ident}：run_id 缺失或占位（evidence 必须可回溯到 run）")
        else:
            _check_run_closed(runs, run_id, ident, rep)
        for field in ref_fields:
            val = e.get(field)
            if not _filled(val):
                continue
            ref_id = val.split("/", 1)[0].strip()  # 允许 dataset-000/test 形式
            for itype, by_id in ids_by_type.items():
                if not any(ref_id.startswith(p) for p in INDEX_SPECS[itype]["id_prefixes"]):
                    continue
                target = by_id.get(ref_id)
                if target is None:
                    rep.fail(f"{ident}：{field}={val} 指向不存在的 {itype}-index 条目")
                elif target.get("status") == "archived":
                    rep.fail(f"{ident}：{field}={val} 指向已 archived 的 {itype}-index 条目")
                else:
                    rep.ok(f"{ident}：{field} → {itype}-index {ref_id} 存在且未 archived")
                break
    return {e.get("id") for e in entries if e.get("id")}


# ---------------------------------------------------------------------------
# deliverables：index.md 表格 + claim marker（决策 4）
# ---------------------------------------------------------------------------

_CLAIM_REF_RE = re.compile(r"claims\.yaml#([A-Za-z0-9._-]+)|(claim-[A-Za-z0-9._-]+)")


def check_deliverables_index(root: Path, claims_by_id: dict, rep: Report) -> None:
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
    for cells in rows:
        rid, _, path_cell, claims_cell, status_cell, complete_cell = cells[:6]
        if "示例" in rid or "example" in rid.lower() or claims_cell.startswith("<"):
            continue
        ident = f"deliverables/index.md 条目 {rid}"
        claim_refs = [a or b for a, b in _CLAIM_REF_RE.findall(claims_cell)]
        if not claim_refs:
            rep.fail(f"{ident}：「支撑 claim」列没有可解析的 claim 引用：{claims_cell!r}")
            continue
        complete = complete_cell.strip("*_ ")
        all_have_evidence = True
        for cid in claim_refs:
            c = claims_by_id.get(cid)
            if c is None:
                rep.fail(f"{ident}：引用未知 claim：{cid}")
                all_have_evidence = False
            elif not (c.get("evidence") or []):
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


def check_claim_markers(root: Path, claim_ids: set, evidence_ids: set, rep: Report) -> None:
    deliv = root / "deliverables"
    if not deliv.is_dir():
        return
    n_markers = 0
    for md in sorted(deliv.rglob("*.md")):
        in_fence = False
        for line in md.read_text(encoding="utf-8").splitlines():
            if line.lstrip().startswith("```"):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            for m in CLAIM_MARKER_RE.finditer(line):
                n_markers += 1
                cid, ev_list = m.group(1), m.group(2)
                ident = f"claim marker（{md.relative_to(root)}）"
                if cid in claim_ids:
                    rep.ok(f"{ident}：id={cid} 存在")
                else:
                    rep.fail(f"{ident}：id={cid} 不存在于 claims.yaml")
                for ev in (ev_list or "").split(","):
                    ev = ev.strip()
                    if not ev:
                        continue
                    if ev in evidence_ids:
                        rep.ok(f"{ident}：evidence={ev} 存在")
                    else:
                        rep.fail(f"{ident}：evidence={ev} 不存在于 evidence.yaml")
    if n_markers == 0:
        rep.ok("claim marker：deliverables 下暂无 marker（非 Markdown/无 marker 走人工 review 兜底）")


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def run_checks(root: Path, rep: Report) -> None:
    runs = _load_runs(root, rep)
    claims_by_id, claim_ids = _load_claims(root, rep)
    check_artifact_indexes(root, runs, claim_ids, rep)
    evidence_ids = check_evidence(root, runs, rep)
    check_deliverables_index(root, claims_by_id, rep)
    check_claim_markers(root, claim_ids, evidence_ids, rep)


def _print_report(rep: Report, strict: bool) -> int:
    for msg in rep.passes:
        print(f"PASS    {msg}")
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
| paper-1 | paper | `deliverables/paper/` | claim-001 | draft | 是 |
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


def _make_good(root: Path) -> str:
    """写正常闭环 fixture，返回真实 bytes 的 sha256。"""
    payload = b'{"metric": 0.93, "baseline": 0.90}\n'
    _write(root, "lab/runs/exports/result-001.json", payload.decode())
    digest = hashlib.sha256(payload).hexdigest()
    _write(root, "lab/research/experiment-ledger.yaml", _GOOD_LEDGER)
    _write(root, "lab/research/claims.yaml", _GOOD_CLAIMS)
    _write(root, "lab/research/evidence.yaml", _GOOD_EVIDENCE)
    _write(root, "lab/artifacts/result-index.yaml", _result_index(digest))
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

    if failures:
        for f in failures:
            print(f"SELFTEST-FAIL {f}")
        print(f"\n[check-provenance-chain --self-test] FAIL — {len(failures)} 个断言未过")
        return 1
    print("[check-provenance-chain --self-test] OK — 正负 fixture 全部符合预期")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
