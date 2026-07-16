#!/usr/bin/env python3
"""下游数据层初始化：给新落地的 G1 governance validator 补结构骨架（issue #63 D1）。

背景：template-sync 会把 `check-doc-lifecycle.py` / `validate-experiment-state.py` /
`check-provenance-chain.py` 这三个门禁脚本落到下游 repo，但不迁移它们要求的数据层
（`memory/doc-lifecycle.yaml` 注册表、`lab/research/*.yaml` 与 `lab/artifacts/*-index.yaml`
的 `schema_version`、`status_history`/`approval` 等必填字段）。追平后下游从全绿掉到大面积
FAIL——这是「新门禁 vs 旧数据」的初始化缺口，不是回归 bug（见 issue #63 复现记录）。

本脚本只做两类结构性动作，绝不伪造语义内容：
1. **纯结构骨架**：缺失的 `schema_version: 1`（新旧数据同等安全，不是语义判断）、缺失的
   `memory/doc-lifecycle.yaml` 注册表框架。
2. **显式 legacy 标记**：条目因缺 run_id/config/status_history/approval/location 等字段
   FAIL，但这些字段在条目落地时（迁移自旧 boards.yaml、或 governance validator 落地前）
   本就不存在、无法回填真实值——登记 `governance_status: legacy_unverified` +
   非占位 `governance_note`，不编造 run_id/commit/approved_by 等具体值。

三个 validator 的对应豁免逻辑：
- `check-doc-lifecycle.py`：不改代码，复用既有 `status: draft` 档位（该门禁本就为此设计，
  见其模块 docstring「占位符容忍范式」）——本脚本补状态锚点行 + 注册表条目。
- `validate-experiment-state.py` / `check-provenance-chain.py`：新增
  `governance_status: legacy_unverified` 豁免（见两文件模块 docstring）。

**「对新数据不放松」的机制保证**（不是承诺，是结构性防线）：每个数据文件用「该文件是否已有
`schema_version`」（doc-lifecycle 用「注册表文件是否已存在」）作为「是否已做过一次 init」的
信号——首次运行（信号缺失）才会把当前所有 FAIL 条目回填为 legacy；本文件一旦落过
`schema_version`/注册表已建立，之后新出现的 FAIL 条目一律只 FLAG（打印待人工处理），不会
被静默标成 legacy。已登记 `governance_status` 的条目（不论新旧）永远跳过，不重复处理。
条目本身缺 commit/supports_claim/grade 等「非治理新增」的基础字段时也只 FLAG，不视为
legacy 缺口——那类字段的空缺不是「新门禁字段」，标 legacy 会掩盖真实缺陷。

幂等：二次运行对已处理条目/文件零改动（诚实计数验证，见 --self-test）。

用法：
  python scripts/init-governance-data.py [--verbose]   # 就地初始化（本 repo）
  python scripts/init-governance-data.py --dry-run [--verbose]  # 只报告 gap，不写任何文件
  python scripts/init-governance-data.py --self-test    # 跑内嵌 fixture（临时目录，无副作用）
退出码：0 = 正常完成（不代表 0 flagged；FLAG 需要人工处理，不阻断退出码）。

`--dry-run` 供 `scripts/template-sync.py` 收尾阶段调用，只读预览 gap 计数，不落盘
（claims.yaml 一侧因依赖 evidence.yaml 已落盘的 legacy 标记，dry-run 下可能保守低估，
见 `init_claims` 函数注释）。
"""
from __future__ import annotations

import datetime
import importlib.util
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
_TODAY = datetime.date.today().isoformat()
GOVERNANCE_LEGACY = "legacy_unverified"


def _load_module(mod_name: str, repo: Path, rel: str):
    spec = importlib.util.spec_from_file_location(mod_name, repo / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


# ---------------------------------------------------------------------------
# 计数器：诚实报告 changed / skipped / flagged（issue #67 教训：不许虚报）
# ---------------------------------------------------------------------------


class Counters:
    def __init__(self) -> None:
        self.changed: list[tuple[str, str]] = []
        self.skipped: list[tuple[str, str]] = []
        self.flagged: list[tuple[str, str]] = []

    def change(self, key: str, msg: str) -> None:
        self.changed.append((key, msg))

    def skip(self, key: str, msg: str) -> None:
        self.skipped.append((key, msg))

    def flag(self, key: str, msg: str) -> None:
        self.flagged.append((key, msg))

    def report(self, *, verbose: bool = False) -> None:
        print(
            f"[init-governance-data] changed={len(self.changed)} "
            f"skipped={len(self.skipped)} flagged={len(self.flagged)}"
        )
        for key, msg in self.changed:
            print(f"CHANGED {key}: {msg}")
        for key, msg in self.flagged:
            print(f"FLAG    {key}: {msg}")
        if verbose:
            for key, msg in self.skipped:
                print(f"SKIP    {key}: {msg}")


def _legacy_note(detail: str) -> str:
    return (
        f"pre-governance backfill by scripts/init-governance-data.py on {_TODAY}; "
        f"{detail}；未编造任何字段真实值，待 human 复核（issue #63）"
    )


def _has_schema_version(text: str) -> bool:
    return bool(re.search(r"(?m)^schema_version:\s*\S", text))


def _ensure_schema_version(repo: Path, rel: str, counts: Counters, *, dry_run: bool = False) -> None:
    path = repo / rel
    if not path.is_file():
        counts.skip(rel, "文件不存在")
        return
    text = path.read_text(encoding="utf-8")
    if _has_schema_version(text):
        counts.skip(rel, "已有 schema_version")
        return
    lines = text.splitlines(keepends=True)
    insert_at = None
    for i, line in enumerate(lines):
        stripped = line.rstrip("\n")
        if not stripped.strip() or stripped.lstrip().startswith("#"):
            continue
        if stripped[0] in " \t":
            continue
        insert_at = i
        break
    if insert_at is None:
        counts.flag(rel, "找不到顶层 key，无法安全插入 schema_version")
        return
    new_lines = lines[:insert_at] + ["schema_version: 1\n", "\n"] + lines[insert_at:]
    if not dry_run:
        path.write_text("".join(new_lines), encoding="utf-8")
    counts.change(rel, "补 schema_version: 1" + ("（dry-run，未落盘）" if dry_run else ""))


def _insert_after_id_line(text: str, entry_id: str, new_fields: list[str]) -> tuple[str, bool]:
    """在 `- id: <entry_id>` 行后插入新字段行（缩进 = list 项缩进 + 2）。"""
    pat = re.compile(r"^(\s*)-\s+id:\s*" + re.escape(entry_id) + r"\s*(#.*)?$")
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    inserted = False
    for line in lines:
        out.append(line)
        if not inserted:
            m = pat.match(line.rstrip("\n"))
            if m:
                field_indent = " " * (len(m.group(1)) + 2)
                for field in new_fields:
                    out.append(f"{field_indent}{field}\n")
                inserted = True
    return "".join(out), inserted


# ---------------------------------------------------------------------------
# 1. doc-lifecycle：注册表框架 + 状态锚点回填（不改 validator 代码，复用 draft 档位）
# ---------------------------------------------------------------------------

_REGISTRY_HEADER = """# doc-lifecycle.yaml — brief/plan/review/decision 四类文档生命周期注册表（issue #13）
#
# 由 agent 维护，human 不手填复杂 YAML；文档标题后的第一条非空正文必须是唯一状态锚点行
# （Status: <enum> · <date> · <ref>；fenced、blockquoted、四空格代码块示例不算），
# 本文件是机器可解析的关联/证据。两处必须一致（validator 在 commit 粒度强制）。
#
# 校验：scripts/check-doc-lifecycle.py（由 validate-governance.py 拉起）。
# schema 与状态语义详见 plans/ANATOMY.md。
#
# 格式约定（保证无 PyYAML 时受限解析器可读）：两空格缩进；条目以 `- id:` 开头；
# 列表用块列表或行内 `[a, b]`；不用行内注释、不用制表符。
#
# 本文件由 scripts/init-governance-data.py 首次创建（issue #63 D1）：下列条目是落地
# 这套治理门禁前已存在的文档，登记为 status=draft（不伪造 approval/issue/branch 等未知
# 字段），文档正文已同步补状态锚点行，待 human 走正常 interactive-plan-doc 流程推进状态。

docs:
"""


def _slug_id(kind: str, rel: str, used: set[str]) -> str:
    stem = Path(rel).name
    for suffix in (".zh.md", ".md"):
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
            break
    base = f"{kind}-{stem}"
    if base not in used:
        return base
    parent = Path(rel).parent.name
    candidate = f"{kind}-{parent}-{stem}"
    i = 2
    while candidate in used:
        candidate = f"{kind}-{parent}-{stem}-{i}"
        i += 1
    return candidate


def _insert_status_anchor(text: str, status: str, ref: str) -> str | None:
    lines = text.splitlines(keepends=True)
    title_idx = None
    for i, line in enumerate(lines):
        if line.strip():
            if not re.match(r"^ {0,3}#(?:\s+|$)", line.rstrip("\n")):
                return None
            title_idx = i
            break
    if title_idx is None:
        return None
    anchor_line = f"Status: {status} · {_TODAY} · {ref}\n"
    insert_at = title_idx + 1
    new_lines = lines[:insert_at] + ["\n", anchor_line, "\n"] + lines[insert_at:]
    return "".join(new_lines)


def _doc_entry_block(doc_id: str, rel: str, kind: str, status: str) -> str:
    return (
        f"  - id: {doc_id}\n"
        f"    path: {rel}\n"
        f"    kind: {kind}\n"
        f"    status: {status}\n"
        f"    issue: null\n"
        f"    branch: null\n"
        f"    worktree: null\n"
        f"    approval: null\n"
        f"    upstream: []\n"
        f"    downstream: []\n"
        f"    superseded_by: null\n"
    )


def init_doc_lifecycle(repo: Path, dl, counts: Counters, *, dry_run: bool = False) -> None:
    registry_path = repo / dl.REGISTRY_REL
    first_pass = not registry_path.is_file()
    docs = dl.scan_docs(repo)
    if first_pass:
        entries: list[dict] = []
    else:
        text = registry_path.read_text(encoding="utf-8", errors="replace")
        entries, perr = dl.parse_registry_text(text)
        if perr:
            counts.flag(dl.REGISTRY_REL, f"注册表解析失败，不动：{perr}")
            return
    registered_paths = {e.get("path") for e in entries if isinstance(e, dict)}
    used_ids = {e.get("id") for e in entries if isinstance(e, dict) and isinstance(e.get("id"), str)}
    new_blocks: list[str] = []
    for rel in docs:
        if rel in registered_paths:
            continue
        if not first_pass:
            counts.flag(
                dl.REGISTRY_REL + "#" + rel,
                "新出现的未登记文档（注册表已完成过一次 init），不自动 legacy 登记——"
                "请走正常 interactive-plan-doc 流程登记",
            )
            continue
        kind = dl.doc_kind(rel)
        if kind is None:
            counts.flag(dl.REGISTRY_REL + "#" + rel, "路径不在四类目录内，无法自动判定 kind，跳过")
            continue
        doc_path = repo / rel
        doc_text = doc_path.read_text(encoding="utf-8", errors="replace")
        anchor, anchor_err = dl._parse_status_anchor(doc_text)
        if anchor_err:
            counts.flag(dl.REGISTRY_REL + "#" + rel, f"状态锚点格式异常，跳过自动登记：{anchor_err}")
            continue
        if anchor is None:
            ref = "legacy backfill by scripts/init-governance-data.py, structure only, unverified"
            new_doc_text = _insert_status_anchor(doc_text, "draft", ref)
            if new_doc_text is None:
                counts.flag(dl.REGISTRY_REL + "#" + rel, "缺一级标题，无法安全插入状态锚点，跳过")
                continue
            if not dry_run:
                doc_path.write_text(new_doc_text, encoding="utf-8")
            status = "draft"
        else:
            status = anchor
        doc_id = _slug_id(kind, rel, used_ids)
        used_ids.add(doc_id)
        new_blocks.append(_doc_entry_block(doc_id, rel, kind, status))
        suffix = "（dry-run，未落盘）" if dry_run else ""
        counts.change(
            dl.REGISTRY_REL + "#" + rel,
            f"补状态锚点(若缺) + 登记 kind={kind} status={status}{suffix}",
        )
    if not new_blocks:
        if first_pass:
            counts.skip(dl.REGISTRY_REL, "未发现受管文档，无需创建注册表")
        return
    if dry_run:
        return
    if first_pass:
        registry_path.write_text(_REGISTRY_HEADER + "".join(new_blocks), encoding="utf-8")
    else:
        text = registry_path.read_text(encoding="utf-8")
        registry_path.write_text(text.rstrip("\n") + "\n\n" + "".join(new_blocks), encoding="utf-8")


# ---------------------------------------------------------------------------
# 2. experiment-ledger：legacy 豁免（history / approval / closure）
# ---------------------------------------------------------------------------


def init_experiment_ledger(repo: Path, es, counts: Counters, *, dry_run: bool = False) -> None:
    rel = es.LEDGER_REL
    path = repo / rel
    if not path.is_file():
        counts.skip(rel, "文件不存在")
        return
    text = path.read_text(encoding="utf-8")
    first_pass = not _has_schema_version(text)
    data, _parser = es.load_yaml(text)
    experiments = (data or {}).get("experiments") or []
    warnings: list[str] = []
    artifact_run_ids = es._artifact_index_run_ids(repo, warnings)
    new_text = text
    for exp in experiments:
        if not isinstance(exp, dict):
            continue
        eid = exp.get("id")
        if not isinstance(eid, str) or not eid:
            continue
        key = f"{rel}#{eid}"
        if exp.get("governance_status") is not None:
            counts.skip(key, "已登记 governance_status")
            continue
        if es._is_placeholder(exp.get("commit")):
            counts.flag(key, "commit 缺失/占位（非治理新增字段的缺口，需人工处理）")
            continue
        errs: list[str] = []
        es._check_history(exp, False, errs)
        es._check_approval_fields(exp, False, errs)
        es._check_closure(exp, repo, artifact_run_ids, False, errs)
        if not errs:
            counts.skip(key, "当前已合规，无需标记")
            continue
        if not first_pass:
            counts.flag(key, f"新的不合规条目（本文件已完成过一次 init），不自动标记 legacy：{len(errs)} 项")
            continue
        note = _legacy_note(f"{len(errs)} 项 history/approval/closure 字段缺口（历史条目从未记录，非新数据回归）")
        new_text, ok = _insert_after_id_line(
            new_text, eid, ["governance_status: legacy_unverified", f'governance_note: "{note}"']
        )
        if ok:
            counts.change(key, f"标记 legacy_unverified（{len(errs)} 项缺口）" + ("（dry-run，未落盘）" if dry_run else ""))
        else:
            counts.flag(key, "找不到 - id 行，无法插入标记")
    if new_text != text and not dry_run:
        path.write_text(new_text, encoding="utf-8")
    _ensure_schema_version(repo, rel, counts, dry_run=dry_run)


# ---------------------------------------------------------------------------
# 3. evidence：legacy 豁免（command / config / run_id）
# ---------------------------------------------------------------------------


def init_evidence(repo: Path, pc, counts: Counters, *, dry_run: bool = False) -> None:
    rel = "lab/research/evidence.yaml"
    path = repo / rel
    if not path.is_file():
        counts.skip(rel, "文件不存在")
        return
    text = path.read_text(encoding="utf-8")
    first_pass = not _has_schema_version(text)
    data, err = pc.load_yaml(path)
    if err is not None or not isinstance(data, dict):
        counts.flag(rel, f"解析失败，不动：{err}")
        return
    entries = data.get("evidence") or []
    new_text = text
    for e in entries:
        if not isinstance(e, dict):
            continue
        eid = e.get("id")
        if not isinstance(eid, str) or not eid:
            continue
        key = f"{rel}#{eid}"
        if e.get("governance_status") is not None:
            counts.skip(key, "已登记 governance_status")
            continue
        core_missing = [f for f in ("commit", "supports_claim") if not pc._filled(e.get(f))]
        if e.get("grade") not in pc.GRADE_RANK:
            core_missing.append("grade")
        if core_missing:
            counts.flag(key, f"基础字段缺失（非治理新增字段的缺口，需人工处理）：{core_missing}")
            continue
        gap = [f for f in ("command", "config", "run_id") if not pc._filled(e.get(f))]
        if not gap:
            counts.skip(key, "当前已合规，无需标记")
            continue
        if not first_pass:
            counts.flag(key, f"新的字段缺口（本文件已完成过一次 init），不自动标记 legacy：{gap}")
            continue
        note = _legacy_note(f"字段缺口 {gap}（历史条目从未记录，非新数据回归）")
        new_text, ok = _insert_after_id_line(
            new_text, eid, ["governance_status: legacy_unverified", f'governance_note: "{note}"']
        )
        if ok:
            counts.change(key, f"标记 legacy_unverified（缺 {gap}）" + ("（dry-run，未落盘）" if dry_run else ""))
        else:
            counts.flag(key, "找不到 - id 行，无法插入标记")
    if new_text != text and not dry_run:
        path.write_text(new_text, encoding="utf-8")
    _ensure_schema_version(repo, rel, counts, dry_run=dry_run)


# ---------------------------------------------------------------------------
# 4. claims：legacy 豁免（evidence 全部降级为 legacy 后 eligible 为空）
# ---------------------------------------------------------------------------


def init_claims(repo: Path, pc, counts: Counters, *, dry_run: bool = False) -> None:
    """注意（dry-run 局限）：valid/legacy evidence 集合从磁盘上的 evidence.yaml 现状重算——
    真实运行时 init_evidence 已先落盘，这里能看到刚写入的 legacy 标记；dry-run 下
    init_evidence 不落盘，所以这里看到的仍是 evidence.yaml 的**当前**状态，可能低估
    claim 侧本应一并变为 legacy 的条目。receipt 的 gap 预览因此是保守下界，不是精确值，
    真实 gap 以 --self-test/实际运行为准（不影响本函数在非 dry-run 下的正确性）。"""
    rel = "lab/research/claims.yaml"
    path = repo / rel
    if not path.is_file():
        counts.skip(rel, "文件不存在")
        return
    text = path.read_text(encoding="utf-8")
    first_pass = not _has_schema_version(text)
    # 用真实 validator 逻辑重新计算 valid/legacy evidence（evidence.yaml 此时已处理完毕）。
    runs = pc._load_runs(repo, pc.Report())
    _by_id, valid_evidence_ids, legacy_evidence_ids = pc.check_evidence(repo, runs, pc.Report())
    data, err = pc.load_yaml(path)
    if err is not None or not isinstance(data, dict):
        counts.flag(rel, f"解析失败，不动：{err}")
        return
    claims = data.get("claims") or []
    new_text = text
    for c in claims:
        if not isinstance(c, dict):
            continue
        cid = c.get("id")
        if not isinstance(cid, str) or not cid:
            continue
        key = f"{rel}#{cid}"
        if c.get("governance_status") is not None:
            counts.skip(key, "已登记 governance_status")
            continue
        status = c.get("status")
        if status not in ("partial", "supported"):
            counts.skip(key, "status 不要求 eligible evidence，无需标记")
            continue
        refs = c.get("evidence") or []
        if not isinstance(refs, list) or not refs:
            counts.flag(key, "status 要求 eligible evidence 但 evidence 列表为空——非 legacy 缺口，需人工处理")
            continue
        if any(r in valid_evidence_ids for r in refs):
            counts.skip(key, "已有有效 evidence，无需标记")
            continue
        if not all((r in valid_evidence_ids or r in legacy_evidence_ids) for r in refs):
            counts.flag(key, "引用了占位/不存在的 evidence——非 legacy 缺口，需人工处理")
            continue
        if not first_pass:
            counts.flag(key, "新的 no-eligible-evidence 缺口（本文件已完成过一次 init），不自动标记 legacy")
            continue
        note = _legacy_note("全部引用 evidence 已标记 legacy_unverified，claim 当前没有可机器核验的 eligible evidence")
        new_text, ok = _insert_after_id_line(
            new_text, cid, ["governance_status: legacy_unverified", f'governance_note: "{note}"']
        )
        if ok:
            counts.change(key, "标记 legacy_unverified（evidence 全部降级）" + ("（dry-run，未落盘）" if dry_run else ""))
        else:
            counts.flag(key, "找不到 - id 行，无法插入标记")
    if new_text != text and not dry_run:
        path.write_text(new_text, encoding="utf-8")
    _ensure_schema_version(repo, rel, counts, dry_run=dry_run)


# ---------------------------------------------------------------------------
# 5. artifact-index（7 类）：schema_version + legacy 豁免（active 但 location 缺失）
# ---------------------------------------------------------------------------


def init_artifact_indexes(repo: Path, pc, counts: Counters, *, dry_run: bool = False) -> None:
    for itype in pc.COVERED_INDEX_TYPES:
        spec = pc.INDEX_SPECS[itype]
        rel = spec["file"]
        path = repo / rel
        if not path.is_file():
            counts.skip(rel, "文件不存在")
            continue
        text = path.read_text(encoding="utf-8")
        first_pass = not _has_schema_version(text)
        data, err = pc.load_yaml(path)
        if err is not None or not isinstance(data, dict):
            counts.flag(rel, f"解析失败，不动：{err}")
            continue
        entries = data.get(spec["key"]) or []
        new_text = text
        for e in entries:
            if not isinstance(e, dict):
                continue
            eid = e.get("id")
            if not isinstance(eid, str) or not eid:
                continue
            key = f"{rel}#{eid}"
            if e.get("governance_status") is not None:
                counts.skip(key, "已登记 governance_status")
                continue
            status = e.get("status")
            needs_legacy = status not in (None, "unknown") and not pc._filled(e.get("location"))
            if not needs_legacy:
                counts.skip(key, "当前已合规，无需标记")
                continue
            if not first_pass:
                counts.flag(key, "新的 location 缺口（本文件已完成过一次 init），不自动标记 legacy")
                continue
            note = _legacy_note("location 字段缺失（历史条目从未记录可回溯 location，非新数据回归）")
            new_text, ok = _insert_after_id_line(
                new_text, eid, ["governance_status: legacy_unverified", f'governance_note: "{note}"']
            )
            if ok:
                counts.change(key, "标记 legacy_unverified（location 缺口）" + ("（dry-run，未落盘）" if dry_run else ""))
            else:
                counts.flag(key, "找不到 - id 行，无法插入标记")
        if new_text != text and not dry_run:
            path.write_text(new_text, encoding="utf-8")
        _ensure_schema_version(repo, rel, counts, dry_run=dry_run)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def run(repo: Path, *, dry_run: bool = False) -> Counters:
    dl = _load_module("_igd_doc_lifecycle", repo, "scripts/check-doc-lifecycle.py")
    es = _load_module("_igd_experiment_state", repo, "scripts/validate-experiment-state.py")
    pc = _load_module("_igd_provenance_chain", repo, "scripts/check-provenance-chain.py")
    counts = Counters()
    init_doc_lifecycle(repo, dl, counts, dry_run=dry_run)
    init_experiment_ledger(repo, es, counts, dry_run=dry_run)
    init_evidence(repo, pc, counts, dry_run=dry_run)
    init_claims(repo, pc, counts, dry_run=dry_run)
    init_artifact_indexes(repo, pc, counts, dry_run=dry_run)
    for rel in ("lab/research/regression-matrix.yaml", "lab/research/release-gates.yaml"):
        _ensure_schema_version(repo, rel, counts, dry_run=dry_run)
    return counts


def _self_test() -> int:
    import shutil
    import tempfile

    failed = 0

    def expect(cond: bool, msg: str) -> None:
        nonlocal failed
        if not cond:
            failed += 1
            print(f"FAIL {msg}")

    tmp = Path(tempfile.mkdtemp(prefix="init-governance-data-selftest-"))
    try:
        for name in (
            "check-doc-lifecycle.py",
            "validate-experiment-state.py",
            "check-provenance-chain.py",
        ):
            (tmp / "scripts").mkdir(exist_ok=True)
            (tmp / "scripts" / name).write_text(
                (REPO / "scripts" / name).read_text(encoding="utf-8"), encoding="utf-8"
            )
        (tmp / "lab" / "research").mkdir(parents=True)
        (tmp / "lab" / "artifacts").mkdir(parents=True)
        (tmp / "lab" / "models").mkdir(parents=True)
        (tmp / "lab" / "code" / "experiments").mkdir(parents=True)
        (tmp / "plans").mkdir(parents=True)
        (tmp / "memory").mkdir(parents=True)

        (tmp / "lab/research/experiment-ledger.yaml").write_text(
            "experiments:\n"
            "  - id: run-legacy\n"
            "    status: done\n"
            "    commit: \"abc123\"\n"
            "    config: null\n"
            "    data_split: null\n"
            "    promote: no\n",
            encoding="utf-8",
        )
        (tmp / "lab/research/evidence.yaml").write_text(
            "evidence:\n"
            "  - id: ev-legacy\n"
            "    supports_claim: claim-legacy\n"
            "    grade: log\n"
            "    commit: \"abc123\"\n"
            "    run_id: null\n"
            "    config: null\n",
            encoding="utf-8",
        )
        (tmp / "lab/research/claims.yaml").write_text(
            "claims:\n"
            "  - id: claim-legacy\n"
            "    title: \"legacy claim\"\n"
            "    status: partial\n"
            "    evidence: [ev-legacy]\n",
            encoding="utf-8",
        )
        (tmp / "lab/artifacts/result-index.yaml").write_text(
            "results:\n"
            "  - id: result-legacy\n"
            "    status: active\n",
            encoding="utf-8",
        )
        (tmp / "plans/20260101-example.zh.md").write_text(
            "# Example plan\n\nSome legacy content, no anchor.\n", encoding="utf-8"
        )

        # dry-run：应报告同样的 gap，但不写任何文件（模拟 template-sync 收尾阶段预览）。
        pre_snapshot = {
            p: p.read_bytes()
            for p in tmp.rglob("*")
            if p.is_file() and p.name != "init-governance-data.py" and "__pycache__" not in p.parts
        }
        dry_counts = run(tmp, dry_run=True)
        post_snapshot = {
            p: p.read_bytes()
            for p in tmp.rglob("*")
            if p.is_file() and p.name != "init-governance-data.py" and "__pycache__" not in p.parts
        }
        _diff_keys = sorted(
            str(k) for k in (set(pre_snapshot) | set(post_snapshot))
            if pre_snapshot.get(k) != post_snapshot.get(k)
        )
        expect(pre_snapshot == post_snapshot, f"dry-run 不应写任何文件，实际差异：{_diff_keys}")
        expect(
            any("run-legacy" in k and "legacy_unverified" in m for k, m in dry_counts.changed),
            "dry-run 也应报告 ledger legacy gap（只是不落盘）",
        )

        counts = run(tmp)
        expect(
            any("run-legacy" in k and "legacy_unverified" in m for k, m in counts.changed),
            "ledger 条目应被标记 legacy_unverified",
        )
        expect(
            any("ev-legacy" in k and "legacy_unverified" in m for k, m in counts.changed),
            "evidence 条目应被标记 legacy_unverified",
        )
        expect(
            any("claim-legacy" in k and "legacy_unverified" in m for k, m in counts.changed),
            "claim 条目应被标记 legacy_unverified（evidence 全部降级）",
        )
        expect(
            any("result-legacy" in k and "legacy_unverified" in m for k, m in counts.changed),
            "artifact-index 条目应被标记 legacy_unverified（location 缺口）",
        )
        expect(
            any("doc-lifecycle.yaml" in k and "20260101-example" in k for k, m in counts.changed),
            "doc 应被登记进新建的注册表",
        )
        anchor_text = (tmp / "plans/20260101-example.zh.md").read_text(encoding="utf-8")
        expect("Status: draft" in anchor_text, "doc 正文应补状态锚点")

        # 幂等：二次运行应零 changed。
        counts2 = run(tmp)
        expect(counts2.changed == [], f"二次运行应零 changed，得到：{counts2.changed}")

        # 负例：模拟已完成过一次 init 后新增的不合规条目——不应被自动标记 legacy。
        ledger_text = (tmp / "lab/research/experiment-ledger.yaml").read_text(encoding="utf-8")
        ledger_text += (
            "  - id: run-new-bad\n"
            "    status: done\n"
            "    commit: \"def456\"\n"
        )
        (tmp / "lab/research/experiment-ledger.yaml").write_text(ledger_text, encoding="utf-8")
        counts3 = run(tmp)
        expect(
            not any("run-new-bad" in k and "legacy_unverified" in m for k, m in counts3.changed),
            "已完成过一次 init 后的新不合规条目不应被自动标记 legacy",
        )
        expect(
            any("run-new-bad" in k for k, m in counts3.flagged),
            "新不合规条目应被 flag 而不是静默通过",
        )

        # 负例：伪造语义内容不应发生——legacy 条目本身没有新增 run_id/config/approved_by
        # 等具体值字段，只多了 governance_status/governance_note 两行。
        ledger_after = (tmp / "lab/research/experiment-ledger.yaml").read_text(encoding="utf-8")
        legacy_block = ledger_after.split("run-legacy")[1].split("run-new-bad")[0]
        expect("governance_note:" in legacy_block, "legacy 条目应带 governance_note")
        expect(
            "approved_by:" not in legacy_block and "run_id:" not in legacy_block,
            "legacy 条目不应被编造出 approved_by/run_id 等具体值字段",
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    total_msg = "OK" if not failed else f"FAIL（{failed} 处）"
    print(f"[init-governance-data --self-test] {total_msg}")
    return 1 if failed else 0


def main(argv: list[str]) -> int:
    if "--self-test" in argv:
        return _self_test()
    counts = run(REPO, dry_run="--dry-run" in argv)
    counts.report(verbose="--verbose" in argv)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
