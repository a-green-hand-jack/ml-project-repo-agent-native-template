#!/usr/bin/env python3
"""检查 ANATOMY.md 的引用漂移（防止 citation rot）+ 显式 typed relation 图一致性。

对每个名为 `ANATOMY.md` 的文件：
1. frontmatter `related_files:` 列出的路径必须存在（相对该 ANATOMY 所在目录解析）。
   这是通用导航引用，语义不变，与下面的 governed typed relation 完全分离。
2. 正文里的 line-addressed citation `path/to/file.py:42` 或 `:42-90`：
   - 被引文件必须存在（相对 repo 根 或 相对该目录解析）。
   - 行号必须在文件行数范围内。
3. 行数不超过硬上限（见 .agent/anatomy-protocol.md：目标 ~80，硬上限 120）。
   写不短通常是代码边界不清，不是文档该加长——把口头阈值升级成运行时防线。
4. 显式 typed relation 图（见 .agent/anatomy-protocol.md「typed relation schema」一节）：
   - `parent` / `children`：ANATOMY <-> ANATOMY 的父子边，必须双向声明。
   - `contracts` / `contract_for`：component-scoped 的 ANATOMY <-> 承诺 owner 边，必须双向且
     component 全局唯一 owner。
   只纳管显式声明这些字段的节点；没有声明的目录（合法 ungoverned leaf/template scaffold）
   不受影响、不会被强行拉入 governed set。

只校验「看起来像真实 repo 文件」的引用；占位符（含 `<...>`、`example`、模板示例）跳过。
这是结构性检查：只能挡 missing file / out-of-range line / 图不自洽；语义正确性仍需人打开代码验证。

无第三方依赖。退出码 0 = 通过，1 = 有漂移（或 --strict 下有 governance 发现）。
用法：
    python scripts/check-anatomy-drift.py               # 结构漂移必查 + governance 只读 report
    python scripts/check-anatomy-drift.py --strict      # governance 发现同样 fail loud
    python scripts/check-anatomy-drift.py --self-test   # 跑内嵌对抗 fixture，不碰真实 repo
"""
from __future__ import annotations

import re
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKIP_DIRS = {".git", ".venv", "__pycache__", ".reference-docs", "node_modules"}
ANATOMY_LINE_LIMIT = 120  # 硬上限，见 .agent/anatomy-protocol.md

# 形如 `path/seg.ext:12` 或 `path/seg.ext:12-90`，允许被反引号包裹。
CITATION_RE = re.compile(
    r"`?([A-Za-z0-9_./-]+\.[A-Za-z0-9_]+):(\d+)(?:-(\d+))?`?"
)
# 占位/示例信号（用于 related_files 逐条判断）。
PLACEHOLDER_HINTS = ("<", ">", "example", "path/to", "foo.", "bar.")
# 能出现在 citation ref 内部的占位信号（逐个匹配判断，不整行跳过）。
PLACEHOLDER_REF_HINTS = ("example", "path/to", "foo.", "bar.")

errors: list[str] = []


def iter_anatomy_files(repo: Path):
    for p in repo.rglob("ANATOMY.md"):
        if any(part in SKIP_DIRS for part in p.relative_to(repo).parts):
            continue
        yield p


def resolve(ref: str, anatomy: Path) -> Path | None:
    """把引用解析成实际路径：优先相对 ANATOMY 目录，其次相对 repo 根。"""
    cand1 = (anatomy.parent / ref).resolve()
    if cand1.exists():
        return cand1
    cand2 = (REPO / ref).resolve()
    if cand2.exists():
        return cand2
    return None


def check_related_files(anatomy: Path, text: str) -> None:
    m = re.search(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not m:
        return
    fm = m.group(1)
    block = re.search(r"related_files:\s*\n((?:\s*-\s*.+\n?)+)", fm)
    if not block:
        return
    for line in block.group(1).splitlines():
        ref = line.strip().lstrip("-").strip().strip('"').strip("'")
        if not ref or any(h in ref for h in PLACEHOLDER_HINTS):
            continue
        if resolve(ref, anatomy) is None:
            errors.append(
                f"{anatomy.relative_to(REPO)}: related_files 引用不存在 -> {ref}"
            )


def _is_placeholder_citation(line: str, m: re.Match) -> bool:
    """逐个匹配判断是否占位/示例（不再整行跳过，避免漏检同行的真实 citation）。"""
    ref = m.group(1)
    if any(h in ref for h in PLACEHOLDER_REF_HINTS):
        return True
    # 被尖括号包裹的示例，如 `<示例：a.py:42>`：ref 本身不含 <>，看上下文。
    if "<" in line[: m.start()] and ">" in line[m.end() :]:
        return True
    return False


def check_citations(anatomy: Path, text: str) -> None:
    # 去掉 frontmatter 再扫正文。
    body = re.sub(r"^---\s*\n.*?\n---\s*\n", "", text, count=1, flags=re.DOTALL)
    for line in body.splitlines():
        for m in CITATION_RE.finditer(line):
            if _is_placeholder_citation(line, m):
                continue
            ref, start, end = m.group(1), int(m.group(2)), m.group(3)
            # 只关心带路径分隔符或已知代码后缀的引用，避免误判 "3.10" 之类。
            if "/" not in ref and not ref.endswith(
                (".py", ".md", ".yaml", ".yml", ".json", ".toml", ".js", ".ts", ".sh")
            ):
                continue
            target = resolve(ref, anatomy)
            if target is None:
                errors.append(
                    f"{anatomy.relative_to(REPO)}: 引用文件不存在 -> {ref}:{start}"
                )
                continue
            try:
                n_lines = sum(1 for _ in target.open("r", encoding="utf-8", errors="replace"))
            except OSError:
                continue
            hi = int(end) if end else start
            if start < 1 or hi > n_lines:
                errors.append(
                    f"{anatomy.relative_to(REPO)}: 行号越界 -> {ref}:{start}"
                    f"{'-' + end if end else ''}（文件共 {n_lines} 行）"
                )


def check_line_budget(anatomy: Path, text: str) -> None:
    n = text.count("\n") + (0 if text.endswith("\n") or not text else 1)
    if n > ANATOMY_LINE_LIMIT:
        errors.append(
            f"{anatomy.relative_to(REPO)}: 超过硬上限 {ANATOMY_LINE_LIMIT} 行"
            f"（当前 {n} 行）——拆分边界，别加长文档"
        )


# --------------------------------------------------------------------------
# Typed relation schema（governed 子图；不是通用 YAML parser，只认这四个固定字段）
#
#   parent: <path>                         # ANATOMY -> 父 ANATOMY，单值
#   children:                              # ANATOMY -> 子 ANATOMY 列表
#     - <path>
#   contracts:                             # ANATOMY -> component-scoped 承诺 owner
#     - component: <id>
#       owner: <path>
#   contract_for:                          # 承诺 owner 文件 -> 反向声明它治理哪些 component
#     - component: <id>
#       anatomy: <path>
#
# 只解析这四个字段的固定形状；任何歧义/重复 key/错误形状 fail closed（记进 findings，
# 不静默丢弃、不崩溃），不影响 `related_files` 现有的多行 maintenance 块解析。
# --------------------------------------------------------------------------


def _frontmatter(text: str) -> str | None:
    m = re.search(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    return m.group(1) if m else None


def _extract_scalar(fm: str, key: str) -> tuple[bool, str | None]:
    """返回 (是否声明该 key, 值或 None)。值为空字符串时也返回 None，由调用方判断「拒绝空值」。"""
    m = re.search(rf"^{re.escape(key)}:[ \t]*(.*)$", fm, re.MULTILINE)
    if not m:
        return False, None
    v = m.group(1).strip().strip('"').strip("'")
    return True, (v or None)


def _extract_block(fm: str, key: str) -> str | None:
    m = re.search(rf"^{re.escape(key)}:[ \t]*\n((?:[ \t]+\S.*\n?)+)", fm, re.MULTILINE)
    return m.group(1) if m else None


def _extract_scalar_list(fm: str, key: str) -> list[str]:
    block = _extract_block(fm, key)
    if not block:
        return []
    out: list[str] = []
    for line in block.splitlines():
        s = line.strip()
        if s.startswith("-"):
            out.append(s[1:].strip().strip('"').strip("'"))
    return out


def _extract_dict_list(fm: str, key: str) -> tuple[list[dict[str, str]], list[str]]:
    """固定两字段 dict-list（例：`- component: x` + 下一行 `  owner: y`）。
    条目内重复 key / 非 `key: value` 形状 -> fail closed，记进第二个返回值而不是吞掉。
    """
    block = _extract_block(fm, key)
    if not block:
        return [], []
    entries: list[dict[str, str]] = []
    errs: list[str] = []
    current: dict[str, str] | None = None
    for raw in block.splitlines():
        s = raw.strip()
        if not s:
            continue
        if s.startswith("-"):
            if current is not None:
                entries.append(current)
            current = {}
            s = s[1:].strip()
            if not s:
                continue
        if current is None:
            continue
        if ":" not in s:
            errs.append(f"{key} 条目格式错误（非 key: value）-> {s!r}")
            continue
        k, _, v = s.partition(":")
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if not k:
            errs.append(f"{key} 条目 key 为空 -> {s!r}")
            continue
        if k in current:
            errs.append(f"{key} 条目内重复 key -> {k!r}")
            continue
        current[k] = v
    if current is not None:
        entries.append(current)
    return entries, errs


_TYPED_TOP_LEVEL_KEYS = (
    ("parent", "scalar"),
    ("children", "list"),
    ("contracts", "list"),
    ("contract_for", "list"),
)


def _scan_typed_key_schema(fm: str, key: str, kind: str) -> list[str]:
    """typed relation 顶层字段窄 scanner：只认 frontmatter 里列首（无缩进）出现的 `key:` 行，
    不是通用 YAML parser。`maintenance: |` 等 literal block 内的缩进 prose 天然不匹配列首正则，
    不会被误判成声明。

    检测两类问题并各自产出违规短语（不含 GOVERNANCE 前缀，由调用方拼行）：
    - 顶层 key 重复声明（同一 key 出现多次，语义歧义，只有第一次声明会被下游实际采用）。
    - 不支持的 shape：scalar key（parent）用了 `[`/`{` 开头的 inline/flow 值；list key
      （children/contracts/contract_for）用了任意 inline 值，或声明了 key 却没有紧跟
      文档化的缩进 `- ...` block。
    """
    occurrences = [
        (i, m.group(1))
        for i, line in enumerate(fm.splitlines())
        for m in (re.match(rf"^{re.escape(key)}:(.*)$", line),)
        if m
    ]
    if not occurrences:
        return []
    violations: list[str] = []
    if len(occurrences) > 1:
        at = "、".join(str(i + 1) for i, _ in occurrences)
        violations.append(
            f"顶层字段 {key} 重复声明 {len(occurrences)} 次（frontmatter 第 {at} 行，"
            f"只有第一次声明会被采用，语义歧义）"
        )
    rest = occurrences[0][1].strip()
    if kind == "scalar":
        if rest.startswith("[") or rest.startswith("{"):
            violations.append(f"{key} 使用了不支持的 inline/flow 值 -> {rest!r}")
    else:
        if rest:
            violations.append(f"{key} 使用了不支持的 inline/flow 值 -> {rest!r}")
        elif _extract_block(fm, key) is None:
            violations.append(
                f"声明了 {key} 但未找到合法的缩进 block（需紧跟 `- item` 或 `- k: v` 形式）"
            )
    return violations


def _classify_relation_target(ref: str, repo: Path) -> tuple[Path | None, str | None]:
    """路径安全校验：typed relation target 一律 repo-root-relative（不是相对当前文件）。
    返回 (安全解析后的绝对路径 或 None, 违规原因 或 None)。
    """
    if not ref:
        return None, "target 为空"
    if ref.startswith("/") or ref.startswith("~"):
        return None, f"绝对路径不允许 -> {ref}"
    if ".." in Path(ref).parts:
        return None, f"target 含 '..' 不允许 -> {ref}"
    target = (repo / ref).resolve()
    try:
        target.relative_to(repo)
    except ValueError:
        return None, f"target 逃逸 repo 根 -> {ref}"
    if not target.exists():
        return None, f"target 不存在 -> {ref}"
    return target, None


def validate_typed_relations(repo: Path, anatomy_files: list[Path]) -> list[str]:
    """真实 repo 与 --self-test synthetic fixture 共用的唯一图校验函数。

    只纳管显式声明 parent/children/contracts/contract_for 的节点；其余目录
    （合法 ungoverned leaf、template scaffold）完全不受影响。
    """
    repo = repo.resolve()
    findings: list[str] = []

    def rel(p: Path) -> str:
        try:
            return str(p.relative_to(repo))
        except ValueError:
            return str(p)

    parent_of: dict[Path, Path] = {}
    children_of: dict[Path, list[Path]] = {}
    contracts_of: dict[Path, list[tuple[str, Path]]] = {}
    contract_for_of: dict[Path, list[tuple[str, Path]]] = {}
    owner_targets: set[Path] = set()

    for anatomy in anatomy_files:
        text = anatomy.read_text(encoding="utf-8", errors="replace")
        fm = _frontmatter(text)
        if not fm:
            continue

        for key, kind in _TYPED_TOP_LEVEL_KEYS:
            for v in _scan_typed_key_schema(fm, key, kind):
                findings.append(
                    f"GOVERNANCE anatomy={rel(anatomy)} relation={key} rule=schema "
                    f"violation={v} action=改为 .agent/anatomy-protocol.md 文档化的顶层唯一 "
                    f"+ 缩进 block 语法"
                )

        present, parent_ref = _extract_scalar(fm, "parent")
        if present:
            if not parent_ref:
                findings.append(
                    f"GOVERNANCE anatomy={rel(anatomy)} relation=parent rule=path-safety "
                    f"violation=parent 为空值 action=删除该字段或填写合法 repo-relative 路径"
                )
            else:
                target, reason = _classify_relation_target(parent_ref, repo)
                if reason:
                    findings.append(
                        f"GOVERNANCE anatomy={rel(anatomy)} relation=parent rule=path-safety "
                        f"violation={reason} action=修正 parent 为 repo 内安全相对路径"
                    )
                else:
                    parent_of[anatomy] = target

        seen_children: set[str] = set()
        resolved_children: list[Path] = []
        for ref in _extract_scalar_list(fm, "children"):
            if ref in seen_children:
                findings.append(
                    f"GOVERNANCE anatomy={rel(anatomy)} relation=children rule=no-duplicate "
                    f"violation=重复声明 children -> {ref!r} action=去重 children 列表"
                )
                continue
            seen_children.add(ref)
            target, reason = _classify_relation_target(ref, repo)
            if reason:
                findings.append(
                    f"GOVERNANCE anatomy={rel(anatomy)} relation=children rule=path-safety "
                    f"violation={reason} action=修正 children 条目为 repo 内安全相对路径"
                )
                continue
            resolved_children.append(target)
        if resolved_children:
            children_of[anatomy] = resolved_children

        contract_entries, entry_errs = _extract_dict_list(fm, "contracts")
        for e in entry_errs:
            findings.append(
                f"GOVERNANCE anatomy={rel(anatomy)} relation=contracts rule=schema "
                f"violation={e} action=改为固定形状 '- component: <id>' + 下一行 '  owner: <path>'"
            )
        seen_components: set[str] = set()
        parsed_contracts: list[tuple[str, Path]] = []
        for e in contract_entries:
            comp, owner_ref = e.get("component"), e.get("owner")
            if not comp or not owner_ref:
                findings.append(
                    f"GOVERNANCE anatomy={rel(anatomy)} relation=contracts rule=schema "
                    f"violation=条目缺失或空 component/owner -> {e} action=补全两个字段（不接受空值）"
                )
                continue
            if comp in seen_components:
                findings.append(
                    f"GOVERNANCE anatomy={rel(anatomy)} component={comp} rule=no-duplicate "
                    f"violation=同一文件内重复声明 component -> {comp} action=去重 contracts 列表"
                )
                continue
            seen_components.add(comp)
            target, reason = _classify_relation_target(owner_ref, repo)
            if reason:
                findings.append(
                    f"GOVERNANCE anatomy={rel(anatomy)} component={comp} rule=path-safety "
                    f"violation={reason} action=修正 owner 为 repo 内安全相对路径"
                )
                continue
            parsed_contracts.append((comp, target))
            owner_targets.add(target)
        if parsed_contracts:
            contracts_of[anatomy] = parsed_contracts

    # owner 候选集 = 被 contracts 显式引用的文件 ∪ 仓库内任何声明了 contract_for 字段的
    # markdown 文件（否则「owner 单方面反向声明、anatomy 完全没回指」的 orphan 无法被发现——
    # 这类文件从未被任何 contracts 引用过，不在 owner_targets 里）。只做一次廉价子串预筛，
    # 命中才走 _frontmatter/_extract_dict_list 正式解析，不是通用 YAML 扫描。
    for p in repo.rglob("*.md"):
        if any(part in SKIP_DIRS for part in p.relative_to(repo).parts):
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if "contract_for:" in text:
            owner_targets.add(p.resolve())

    for owner_path in owner_targets:
        text = owner_path.read_text(encoding="utf-8", errors="replace")
        fm = _frontmatter(text)
        if not fm:
            contract_for_of[owner_path] = []
            continue
        for v in _scan_typed_key_schema(fm, "contract_for", "list"):
            findings.append(
                f"GOVERNANCE owner={rel(owner_path)} relation=contract_for rule=schema "
                f"violation={v} action=改为 .agent/anatomy-protocol.md 文档化的顶层唯一 "
                f"+ 缩进 block 语法"
            )
        cf_entries, entry_errs = _extract_dict_list(fm, "contract_for")
        for e in entry_errs:
            findings.append(
                f"GOVERNANCE owner={rel(owner_path)} relation=contract_for rule=schema "
                f"violation={e} action=改为固定形状 '- component: <id>' + 下一行 '  anatomy: <path>'"
            )
        seen = set()
        parsed: list[tuple[str, Path]] = []
        for e in cf_entries:
            comp, anatomy_ref = e.get("component"), e.get("anatomy")
            if not comp or not anatomy_ref:
                findings.append(
                    f"GOVERNANCE owner={rel(owner_path)} relation=contract_for rule=schema "
                    f"violation=条目缺失或空 component/anatomy -> {e} action=补全两个字段（不接受空值）"
                )
                continue
            if comp in seen:
                findings.append(
                    f"GOVERNANCE owner={rel(owner_path)} component={comp} rule=no-duplicate "
                    f"violation=同一文件内重复声明 component -> {comp} action=去重 contract_for 列表"
                )
                continue
            seen.add(comp)
            target, reason = _classify_relation_target(anatomy_ref, repo)
            if reason:
                findings.append(
                    f"GOVERNANCE owner={rel(owner_path)} component={comp} rule=path-safety "
                    f"violation={reason} action=修正 anatomy 为 repo 内安全相对路径"
                )
                continue
            parsed.append((comp, target))
        contract_for_of[owner_path] = parsed

    # --- parent <-> children 必须双向 ---
    for anatomy, parent in parent_of.items():
        kids = children_of.get(parent, [])
        if anatomy not in kids:
            findings.append(
                f"GOVERNANCE anatomy={rel(anatomy)} rule=parent-child-bidirectional "
                f"violation=声明 parent={rel(parent)}，但 {rel(parent)} 未在 children 中回链本节点 "
                f"missing_link={rel(parent)}#children "
                f"action=在 {rel(parent)} frontmatter 的 children 加入 {rel(anatomy)}"
            )
    for anatomy, kids in children_of.items():
        for child in kids:
            if parent_of.get(child) != anatomy:
                findings.append(
                    f"GOVERNANCE anatomy={rel(anatomy)} rule=parent-child-bidirectional "
                    f"violation=声明 children 含 {rel(child)}，但该节点未声明 parent={rel(anatomy)} "
                    f"missing_link={rel(child)}#parent "
                    f"action=在 {rel(child)} frontmatter 加入 parent 指向 {rel(anatomy)}"
                )

    # --- component 全局唯一 owner + contract 双向 ---
    component_owner: dict[str, Path] = {}
    component_declarer: dict[str, Path] = {}
    for anatomy, entries in contracts_of.items():
        for comp, owner in entries:
            if comp in component_owner and component_owner[comp] != owner:
                findings.append(
                    f"GOVERNANCE component={comp} rule=single-owner "
                    f"violation=同一 component 被多个 owner 认领 -> "
                    f"{rel(component_owner[comp])} 与 {rel(owner)} "
                    f"action=确认唯一 owner，移除多余的 contracts 声明"
                )
                continue
            component_owner[comp] = owner
            component_declarer[comp] = anatomy

    for comp, anatomy in component_declarer.items():
        owner = component_owner[comp]
        back = dict(contract_for_of.get(owner, []))
        if comp not in back:
            findings.append(
                f"GOVERNANCE component={comp} rule=contract-bidirectional "
                f"violation={rel(anatomy)} 声明 owner={rel(owner)}，"
                f"但 {rel(owner)} 未反向声明 contract_for "
                f"missing_link={rel(owner)}#contract_for "
                f"action=在 {rel(owner)} frontmatter 加入 contract_for: "
                f"[{{component: {comp}, anatomy: <指向 {rel(anatomy)} 的路径>}}]"
            )
        elif back[comp] != anatomy:
            findings.append(
                f"GOVERNANCE component={comp} rule=contract-bidirectional "
                f"violation={rel(owner)} 的 contract_for 指回 {rel(back[comp])}，"
                f"与声明方 {rel(anatomy)} 不一致 "
                f"action=核对 component={comp} 的双向声明是否指向同一 ANATOMY"
            )

    # --- orphan governed node：owner 反向声明了 contract_for，但被指向的 anatomy 完全没有回指 ---
    for owner, cf_entries in contract_for_of.items():
        for comp, anatomy in cf_entries:
            declared = contracts_of.get(anatomy, [])
            if not any(c == comp and o == owner for c, o in declared):
                findings.append(
                    f"GOVERNANCE component={comp} rule=orphan-governed-node "
                    f"violation={rel(owner)} 的 contract_for 指向 {rel(anatomy)}，"
                    f"但该节点未声明对应 contracts "
                    f"missing_link={rel(anatomy)}#contracts "
                    f"action=在 {rel(anatomy)} frontmatter 加入 contracts: "
                    f"[{{component: {comp}, owner: <指向 {rel(owner)} 的路径>}}]，"
                    f"或从 {rel(owner)} 移除这条 contract_for"
                )

    return findings


# --------------------------------------------------------------------------
# --self-test：对抗 fixture，全部走 validate_typed_relations()，不碰真实 repo。
# --------------------------------------------------------------------------


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _build_fixtures(root: Path) -> None:
    # 1) 合法 root<->child + component contract 双向图。
    _write(root / "ANATOMY.md", (
        "---\n"
        "children:\n"
        "  - child/ANATOMY.md\n"
        "contracts:\n"
        "  - component: comp-ok\n"
        "    owner: policy.md\n"
        "---\n# root\n"
    ))
    _write(root / "child/ANATOMY.md", "---\nparent: ANATOMY.md\n---\n# child\n")
    _write(root / "policy.md", (
        "---\ncontract_for:\n  - component: comp-ok\n    anatomy: ANATOMY.md\n---\n# policy\n"
    ))

    # 2) 单向 parent-child：child 声明 parent，parent 完全没声明 children。
    _write(root / "oneway_pc/parent/ANATOMY.md", "---\n# parent，无 children\n---\n# 占位\n")
    _write(root / "oneway_pc/child/ANATOMY.md", "---\nparent: oneway_pc/parent/ANATOMY.md\n---\n# child\n")

    # 3) 单向 anatomy-contract：anatomy 声明 contracts，owner 存在但无 contract_for。
    _write(root / "oneway_contract/anatomy/ANATOMY.md", (
        "---\ncontracts:\n  - component: comp-oneway\n    owner: oneway_contract/policy.md\n---\n# a\n"
    ))
    _write(root / "oneway_contract/policy.md", "---\nrelated_files:\n  - anatomy/ANATOMY.md\n---\n# policy 无 contract_for\n")

    # 4) duplicate owner：两个 anatomy 为同一 component 声明不同 owner。
    _write(root / "dup_owner/a/ANATOMY.md", "---\ncontracts:\n  - component: comp-dup\n    owner: dup_owner/policyA.md\n---\n# a\n")
    _write(root / "dup_owner/b/ANATOMY.md", "---\ncontracts:\n  - component: comp-dup\n    owner: dup_owner/policyB.md\n---\n# b\n")
    _write(root / "dup_owner/policyA.md", "---\ncontract_for:\n  - component: comp-dup\n    anatomy: dup_owner/a/ANATOMY.md\n---\n# A\n")
    _write(root / "dup_owner/policyB.md", "---\ncontract_for:\n  - component: comp-dup\n    anatomy: dup_owner/b/ANATOMY.md\n---\n# B\n")

    # 5) orphan governed node：owner 声明 contract_for 指向的 anatomy 完全没有 contracts。
    _write(root / "orphan/policy.md", "---\ncontract_for:\n  - component: comp-orphan\n    anatomy: orphan/anatomy/ANATOMY.md\n---\n# policy\n")
    _write(root / "orphan/anatomy/ANATOMY.md", "---\nrelated_files:\n  - ../policy.md\n---\n# 无 contracts\n")

    # 6) 绝对路径 target。
    _write(root / "abs_target/ANATOMY.md", "---\nparent: /etc/passwd\n---\n# abs\n")

    # 7) '..' target/escape。
    _write(root / "escape/ANATOMY.md", "---\nchildren:\n  - ../../outside.md\n---\n# escape\n")

    # 8) duplicate relation：children 列表内同一条目重复。
    _write(root / "dup_rel/x/ANATOMY.md", "---\n# 被引用的占位子节点\n---\n# x\n")
    _write(root / "dup_rel/ANATOMY.md", "---\nchildren:\n  - dup_rel/x/ANATOMY.md\n  - dup_rel/x/ANATOMY.md\n---\n# dup\n")

    # 9) 合法 ungoverned leaf/template scaffold：只有 related_files，无 governance 字段。
    _write(root / "leaf/ANATOMY.md", "---\nrelated_files:\n  - ../ANATOMY.md\n---\n# leaf，不进 governed set\n")

    # 10) 顶层 typed key 重复声明（同一 key 出现两次，语义歧义）。
    _write(root / "schema_dup/ANATOMY.md", "---\nparent: a.md\nparent: b.md\n---\n# dup key\n")

    # 11) 不支持的 inline/flow shape（不是文档化的缩进 block 语法）。
    _write(root / "schema_inline/ANATOMY.md", (
        "---\ncontracts: [{component: comp-inline, owner: policy.md}]\n---\n# inline\n"
    ))

    # 12) maintenance literal block 里出现 typed-key-looking 文字，仍合法、不应被扫描器误判。
    _write(root / "schema_maintenance/ANATOMY.md", (
        "---\n"
        "maintenance: |\n"
        "  这里提到 children: [a, b] 只是文字说明，不是真实顶层字段。\n"
        "  也提到 contracts: 这个词，同样不是声明。\n"
        "---\n# maintenance 内 typed-key-looking prose 合法\n"
    ))


def self_test() -> int:
    with tempfile.TemporaryDirectory(prefix="anatomy-graph-selftest-") as td:
        root = Path(td)
        _build_fixtures(root)
        files = list(iter_anatomy_files(root))
        findings = validate_typed_relations(root, files)
        joined = "\n".join(findings)

        checks: list[tuple[str, bool]] = [
            ("1 合法 root<->child + contract 双向图不产生 comp-ok 相关发现",
             "comp-ok" not in joined and "anatomy=child/ANATOMY.md" not in joined
             and "owner=policy.md" not in joined),
            ("2 单向 parent-child 被检出", (
                "rule=parent-child-bidirectional" in joined
                and "oneway_pc/child/ANATOMY.md" in joined
            )),
            ("3 单向 anatomy-contract 被检出", (
                "rule=contract-bidirectional" in joined and "comp-oneway" in joined
            )),
            ("4 duplicate owner 被检出", (
                "rule=single-owner" in joined and "comp-dup" in joined
            )),
            ("5 orphan governed node 被检出", (
                "rule=orphan-governed-node" in joined and "comp-orphan" in joined
            )),
            ("6 绝对路径 target 被拒绝", (
                "rule=path-safety" in joined and "绝对路径不允许" in joined
            )),
            ("7 '..' target/escape 被拒绝", (
                "rule=path-safety" in joined and "含 '..' 不允许" in joined
            )),
            ("8 duplicate relation 被检出", (
                "rule=no-duplicate" in joined and "dup_rel/ANATOMY.md" in joined
            )),
            ("9 合法 ungoverned leaf 不产生发现", "leaf/ANATOMY.md" not in joined),
            ("10 顶层 typed key 重复声明被检出", (
                "anatomy=schema_dup/ANATOMY.md" in joined
                and "relation=parent" in joined
                and "rule=schema" in joined
                and "重复声明" in joined
            )),
            ("11 不支持的 inline/flow shape 被检出", (
                "anatomy=schema_inline/ANATOMY.md" in joined
                and "relation=contracts" in joined
                and "rule=schema" in joined
                and "不支持的 inline/flow 值" in joined
            )),
            ("12 maintenance 内 typed-key-looking prose 合法不误报", (
                "schema_maintenance/ANATOMY.md" not in joined
            )),
        ]

        ok = True
        for label, passed in checks:
            status = "PASS" if passed else "FAIL"
            if not passed:
                ok = False
            print(f"[self-test] {status} {label}")

        print(f"[self-test] 共 {len(findings)} 条 governance 发现（fixture 图）")
        print(f"[self-test] {'OK' if ok else 'FAIL'}")
        return 0 if ok else 1


def main() -> int:
    if "--self-test" in sys.argv:
        return self_test()

    strict = "--strict" in sys.argv
    files = list(iter_anatomy_files(REPO))
    for anatomy in files:
        text = anatomy.read_text(encoding="utf-8", errors="replace")
        check_related_files(anatomy, text)
        check_citations(anatomy, text)
        check_line_budget(anatomy, text)

    governance_findings = validate_typed_relations(REPO, files)
    label = "ERROR" if strict else "REPORT"
    for f in governance_findings:
        print(f"{label} {f}")

    for e in errors:
        print(f"ERROR {e}")

    hard_errors = list(errors) + (governance_findings if strict else [])
    status = "FAIL" if hard_errors else "OK"
    mode = "strict 生效" if strict else "non-strict：governance 仅报告不拦截"
    print(
        f"[check-anatomy-drift] {status} — 扫描 {len(files)} 个 ANATOMY.md，"
        f"{len(errors)} 处结构漂移，{len(governance_findings)} 处 governance 发现（{mode}）"
    )
    return 1 if hard_errors else 0


if __name__ == "__main__":
    sys.exit(main())
