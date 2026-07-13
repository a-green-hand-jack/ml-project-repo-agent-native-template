#!/usr/bin/env python3
"""doc-lifecycle 校验：brief/plan/review/decision 四类文档的生命周期状态与引用完整性。

见 `plans/20260712-plan-lifecycle-state.zh.md`（issue #13，human 已拍板）与 `plans/ANATOMY.md`。
状态载体是 runtime-neutral 的两层：
- 文档正文顶部一行状态锚点：`Status: <enum> · <date> · <ref>`（人类可读，一行文本）；
- `memory/doc-lifecycle.yaml` 注册表（机器可解析，agent 维护，human 不手填）。

状态枚举：draft → in-review → approved → implementing → verified；superseded 为终态。
只判「可判定的事实」，不替 human 做主观判断（研究方向/风险接受/是否真收敛仍是 human gate）：

1. 注册表可解析、无制表符；id 唯一；kind/status 枚举合法。
2. path 指向真实存在的文件；upstream/downstream/superseded_by 指向注册表内真实条目（悬空即错）。
3. approved/implementing/verified 必须有非占位 approval 证据引用。
4. 活跃 plan（approved/implementing）的 issue 必须是非占位规范坐标、branch 必须是现存
   Git ref；implementing 的 worktree 必须是 `git worktree list` 中绑定同一 branch 的真实条目。
   issue 是远端实体，离线 validator 只锁定 `#N`/GitHub issue URL，不发网络请求。
5. plan 类在 approved/implementing 态必须有非空、非占位的
   「## Allowed paths」「## Forbidden paths」「## 验证标准」段（verified/superseded 是历史态，不追溯）。
6. 过期 approval（human 拍板：唯一触发）：上游引用被标 superseded → 本条 approved/implementing 失效。
7. approved/implementing 态的「## Human 批注区」不得残留 `[?]` / `[改]` 未决批注
   （格式约定 + 模式匹配，不做语义分类；防止未收敛被误判为已收敛）。
8. 文档状态锚点必须与注册表一致（矛盾即错）；四类文档（导航四件套除外）必须登记。
9. kind 必须与路径类别一致（plans/ 只能登记 kind=plan，human/decisions/ 只能 kind=decision，
   以此类推；防止谎报 kind 绕过 plan 必填段校验）。路径不在四类目录内才允许自由声明 kind（告警）。
10. 存在四类受管文档但注册表缺失 → error（非 strict 也 fail）：注册表一旦建立就是治理面，
   缺失/被删即异常。

复用 check_release_gates / check_regression_matrix 的「占位符容忍 + 非默认态需真实证据」范式：
draft/in-review 天然通过，状态进阶才强制证据。PyYAML 可选：缺依赖时用受限解析器
（注册表约定：两空格缩进、条目以 `- id:` 开头、列表用块列表或行内 `[a, b]`、不用行内注释）。

同时暴露 `pretooluse_reason(tool_name, tool_input, repo_root)` 给
`.claude/hooks/pre_tool_guard.py` 做机械拦截（Claude/Codex 共用同一物理 hook）：
在编辑动作阶段拦「状态跃迁到进阶态但完整性不成立」的写入。hook 侧解析失败原则上保守放行，
两个例外**保守拦截**（宁可要求换工具，不能静默放行）：
- 删除/移走 `memory/doc-lifecycle.yaml`（apply_patch Delete/Move、Bash rm/mv 等）——治理面不可拆除；
- apply_patch Update 触碰受管文档/注册表但 hunk 无法可靠重建 patch 后全文——提示改用 Edit 或分两步。
human 显式绕过：`DOC_LIFECYCLE_SKIP=1`（validator 仍会事后校验）。

用法：
  python scripts/check-doc-lifecycle.py [--strict]   # 校验本 repo（validate-governance 拉起）
  python scripts/check-doc-lifecycle.py --self-test  # 跑内嵌 fixtures（无外部 fixture 目录）
退出码 0 = 通过，非 0 = 有失败。
"""
from __future__ import annotations

import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
REGISTRY_REL = "memory/doc-lifecycle.yaml"

VALID_STATUS = {"draft", "in-review", "approved", "implementing", "verified", "superseded"}
KINDS = {"brief", "plan", "review", "decision"}
# 状态进阶后需要真实 approval 证据（占位符容忍范式：draft/in-review 天然通过）。
APPROVAL_REQUIRED = {"approved", "implementing", "verified"}
# scope/forbidden/verification 必填 + 批注收敛 + 过期 approval 检查只作用于「进行中的授权工作」；
# verified/superseded 是历史事实，不追溯重写正文（存量回填据此可行）。
SCOPE_REQUIRED = {"approved", "implementing"}
# 活跃 plan 的执行坐标必须能在本地离线核验。verified 是历史态：branch/worktree 合并后可清理，
# 不追溯要求它们继续存在；此时由 approval 中的 commit/PR/test 证据承担历史可追溯性。
ACTIVE_PLAN_ASSOC_REQUIRED = {"approved", "implementing"}
ISSUE_REF = re.compile(
    r"(?:#[1-9]\d*|https://github\.com/[^/\s]+/[^/\s]+/issues/[1-9]\d*)\Z"
)

REQUIRED_PLAN_SECTIONS = ("Allowed paths", "Forbidden paths", "验证标准")
ANNOTATION_SECTION = "Human 批注区"
NAV_BASENAMES = {"README.md", "AGENTS.md", "CLAUDE.md", "ANATOMY.md"}
DOC_DIRS = ("plans", "human/briefs", "human/reviews", "human/decisions")

STATUS_LINE = re.compile(r"^\s*>?\s*Status[:：]\s*([A-Za-z-]+)")
UNRESOLVED_MARK = re.compile(r"^\s*(?:[-*]\s*)?\[(?:\?|改)\]", re.MULTILINE)
SKIP_ENV = "DOC_LIFECYCLE_SKIP"
_ESCAPE_HINT = f"确属 human 明示例外可 {SKIP_ENV}=1 显式放行（validator 仍会事后校验）。"

LIST_FIELDS = ("upstream", "downstream")


def _is_placeholder(value) -> bool:
    return isinstance(value, str) and value.strip().startswith("<")


def _is_missing_or_placeholder(value) -> bool:
    if value is None:
        return True
    text = str(value).strip()
    return (
        not text
        or _is_placeholder(text)
        or text.lower() in {"none", "null", "n/a", "na", "tbd", "todo", "-"}
    )


# ---------------------------------------------------------------- 注册表解析

def _scalar(raw: str):
    v = raw.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "'\"":
        v = v[1:-1]
    if v in ("", "null", "~"):
        return None
    return v


def _parse_restricted(text: str):
    """无 PyYAML 时的受限解析器：只支持本注册表约定的结构。返回 (entries, errors)。"""
    entries: list[dict] = []
    errors: list[str] = []
    cur: dict | None = None
    cur_list: str | None = None
    in_docs = False
    for lineno, raw in enumerate(text.splitlines(), 1):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        s = raw.strip()
        if indent == 0:
            in_docs = s.split(":", 1)[0].strip() == "docs"
            cur, cur_list = None, None
            continue
        if not in_docs:
            continue
        if s.startswith("- "):
            body = s[2:].strip()
            if ":" in body:  # 新条目（约定以 `- id:` 开头）
                key, _, val = body.partition(":")
                cur = {key.strip(): _scalar(val)}
                entries.append(cur)
                cur_list = None
            elif cur is not None and cur_list is not None:
                cur.setdefault(cur_list, []).append(_scalar(body))
            else:
                errors.append(f"注册表第 {lineno} 行：列表项没有归属字段")
            continue
        if ":" in s and cur is not None:
            key, _, val = s.partition(":")
            key, val = key.strip(), val.strip()
            if val == "":
                cur[key] = []
                cur_list = key
            elif val.startswith("[") and val.endswith("]"):
                inner = val[1:-1].strip()
                cur[key] = [_scalar(x) for x in inner.split(",") if x.strip()] if inner else []
                cur_list = None
            else:
                cur[key] = _scalar(val)
                cur_list = None
        else:
            errors.append(f"注册表第 {lineno} 行无法解析：{s[:60]}")
    return entries, errors


def parse_registry_text(text: str):
    """解析注册表全文。优先 PyYAML；缺依赖时回退受限解析器。返回 (entries, errors)。"""
    if "\t" in text:
        return [], [f"{REGISTRY_REL} 含制表符（应用空格）"]
    try:
        import yaml  # type: ignore
    except ImportError:
        return _parse_restricted(text)
    try:
        data = yaml.safe_load(text) or {}
    except Exception as e:  # noqa: BLE001
        return [], [f"{REGISTRY_REL} YAML 解析失败：{e}"]
    if not isinstance(data, dict):
        return [], [f"{REGISTRY_REL} 顶层应为映射（含 docs: 列表）"]
    docs = data.get("docs") or []
    if not isinstance(docs, list):
        return [], [f"{REGISTRY_REL} 的 docs 应为列表"]
    entries = []
    for d in docs:
        if not isinstance(d, dict):
            return [], [f"{REGISTRY_REL} 的 docs[] 条目应为映射"]
        entries.append(d)
    return entries, []


# ---------------------------------------------------------------- 文档解析

def doc_kind(rel: str) -> str | None:
    """按路径判定四类文档 kind；导航四件套与其他路径返回 None。"""
    if not rel.endswith(".md") or rel.split("/")[-1] in NAV_BASENAMES:
        return None
    if rel.startswith("plans/"):
        return "plan"
    if rel.startswith("human/briefs/"):
        return "brief"
    if rel.startswith("human/reviews/"):
        return "review"
    if rel.startswith("human/decisions/"):
        return "decision"
    return None


def scan_docs(repo: Path) -> list[str]:
    rels = []
    for d in DOC_DIRS:
        base = repo / d
        if not base.is_dir():
            continue
        for f in sorted(base.rglob("*.md")):
            rel = f.relative_to(repo).as_posix()
            if doc_kind(rel):
                rels.append(rel)
    return rels


def extract_status(text: str) -> str | None:
    for line in text.splitlines():
        m = STATUS_LINE.match(line)
        if m:
            return m.group(1)
    return None


def _section_body(text: str, name: str) -> list[str] | None:
    """返回「## <name>…」段正文行（到下一个 ## 为止）；无该段返回 None。"""
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.startswith("## ") and line[3:].strip().startswith(name):
            start = i + 1
            break
    if start is None:
        return None
    body = []
    for line in lines[start:]:
        if line.startswith("## "):
            break
        body.append(line)
    return body


def _has_real_content(body: list[str]) -> bool:
    return any(ln.strip() and not ln.strip().startswith("<") for ln in body)


def missing_plan_sections(text: str) -> list[str]:
    missing = []
    for name in REQUIRED_PLAN_SECTIONS:
        body = _section_body(text, name)
        if body is None:
            missing.append(f"缺少「## {name}」段")
        elif not _has_real_content(body):
            missing.append(f"「## {name}」段为空或仅占位符")
    return missing


def annotation_conflict(text: str, *, whole_doc: bool = True) -> bool:
    """Human 批注区是否残留未决批注标记（[?] / [改]）。whole_doc=False 时对片段全文匹配。"""
    if whole_doc:
        body = _section_body(text, ANNOTATION_SECTION)
        if body is None:
            return False
        text = "\n".join(body)
    return bool(UNRESOLVED_MARK.search(text))


# ---------------------------------------------------------------- 校验规则

def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return subprocess.CompletedProcess(["git", *args], 127, "", "git unavailable")


def _branch_exists(repo: Path, branch: str) -> bool:
    """只接受一个真实 Git ref；活跃 plan 不允许用自由文本拼多个 branch。"""
    branch = branch.strip()
    if not branch or any(ch.isspace() for ch in branch):
        return False
    refs = [branch] if branch.startswith("refs/") else [
        f"refs/heads/{branch}",
        f"refs/remotes/{branch}",
    ]
    return any(_git(repo, "show-ref", "--verify", "--quiet", ref).returncode == 0 for ref in refs)


def _worktree_records(repo: Path) -> list[tuple[Path, str | None]]:
    proc = _git(repo, "worktree", "list", "--porcelain")
    if proc.returncode != 0:
        return []
    records: list[tuple[Path, str | None]] = []
    path: Path | None = None
    branch: str | None = None
    for line in [*proc.stdout.splitlines(), ""]:
        if line.startswith("worktree "):
            path = Path(line[len("worktree "):]).resolve()
        elif line.startswith("branch "):
            branch = line[len("branch "):].strip()
        elif not line and path is not None:
            records.append((path, branch))
            path, branch = None, None
    return records


def _worktree_candidates(repo: Path, raw: str) -> set[Path]:
    path = Path(raw.strip())
    if path.is_absolute():
        return {path.resolve()}
    candidates = {(repo / path).resolve()}
    common = _git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir")
    if common.returncode == 0 and common.stdout.strip():
        # linked worktree 的 common dir 位于主 checkout 的 .git；registry 路径以主 checkout 为基准。
        candidates.add((Path(common.stdout.strip()).resolve().parent / path).resolve())
    return candidates


def _worktree_matches(repo: Path, raw: str, branch: str) -> bool:
    candidates = _worktree_candidates(repo, raw)
    expected_branch = branch if branch.startswith("refs/") else f"refs/heads/{branch}"
    return any(path in candidates and actual_branch == expected_branch
               for path, actual_branch in _worktree_records(repo))


def _active_plan_association_errors(e: dict, repo: Path) -> list[str]:
    """活跃 plan 的 issue/branch/worktree 关联合同。

    issue 是远端实体，离线 validator 不做网络请求；以非占位、规范 `#N`/GitHub issue URL
    锁定明确坐标。branch/worktree 是本地实体，分别核验 Git ref 与 `git worktree list`，且
    implementing worktree 必须绑定同一 branch。
    """
    eid = str(e.get("id") or "<no-id>")
    status = e.get("status")
    if e.get("kind") != "plan" or status not in ACTIVE_PLAN_ASSOC_REQUIRED:
        return []

    errors: list[str] = []
    issue = e.get("issue")
    branch = e.get("branch")
    worktree = e.get("worktree")
    if _is_missing_or_placeholder(issue):
        errors.append(f"{eid}: status={status} 的活跃 plan 缺非占位 issue 关联")
    elif not ISSUE_REF.fullmatch(str(issue).strip()):
        errors.append(
            f"{eid}: issue 关联格式非法：{issue}（应为 #N 或 https://github.com/<owner>/<repo>/issues/N）"
        )

    if _is_missing_or_placeholder(branch):
        errors.append(f"{eid}: status={status} 的活跃 plan 缺非占位 branch 关联")
    elif not _branch_exists(repo, str(branch)):
        errors.append(f"{eid}: branch 不存在或不是单一 Git ref：{branch}")

    if status == "implementing" and _is_missing_or_placeholder(worktree):
        errors.append(f"{eid}: status=implementing 的 plan 缺非占位 worktree 关联")
    elif not _is_missing_or_placeholder(worktree) and not _is_missing_or_placeholder(branch):
        if not _worktree_matches(repo, str(worktree), str(branch)):
            errors.append(
                f"{eid}: worktree 不存在、未登记，或未绑定 branch={branch}：{worktree}"
            )
    return errors


def registry_errors(entries: list[dict], repo: Path, *, check_paths: bool = True) -> list[str]:
    errs: list[str] = []
    ids: dict[str, dict] = {}
    for e in entries:
        eid = e.get("id")
        if not eid:
            errs.append("注册表存在缺 id 的条目")
            continue
        if eid in ids:
            errs.append(f"注册表 id 重复：{eid}")
        ids[str(eid)] = e
    for e in entries:
        eid = str(e.get("id") or "<no-id>")
        kind, status, path = e.get("kind"), e.get("status"), e.get("path")
        if kind not in KINDS:
            errs.append(f"{eid}: kind 非法：{kind}（合法：{'/'.join(sorted(KINDS))}）")
        if status not in VALID_STATUS:
            errs.append(f"{eid}: status 非法：{status}（合法：{'/'.join(sorted(VALID_STATUS))}）")
        if not path:
            errs.append(f"{eid}: 缺 path")
        elif check_paths and not (repo / str(path)).is_file():
            errs.append(f"{eid}: path 指向不存在的文件：{path}（悬空引用）")
        # kind 与路径类别一致性：四类目录内的文档不允许谎报 kind（否则可绕过 plan 必填段校验）。
        if path and kind in KINDS:
            expected = doc_kind(str(path))
            if expected is not None and expected != kind:
                errs.append(
                    f"{eid}: kind={kind} 与路径类别不符：{path} 属 {expected} 目录，"
                    f"必须登记为 kind={expected}（防止谎报 kind 绕过必填段校验）"
                )
        if status in APPROVAL_REQUIRED and (not e.get("approval") or _is_placeholder(str(e.get("approval")))):
            errs.append(f"{eid}: status={status} 但 approval 证据缺失/占位（human gate 引用必填）")
        for field in LIST_FIELDS:
            for ref in e.get(field) or []:
                if str(ref) not in ids:
                    errs.append(f"{eid}: {field} 引用不存在的条目：{ref}（悬空引用）")
        sb = e.get("superseded_by")
        if sb and str(sb) not in ids:
            errs.append(f"{eid}: superseded_by 引用不存在的条目：{sb}（悬空引用）")
        errs += _active_plan_association_errors(e, repo)
    # 过期 approval（唯一触发，human 拍板）：上游被标 superseded → 本条进阶态失效。
    for e in entries:
        if e.get("status") in SCOPE_REQUIRED:
            for ref in e.get("upstream") or []:
                up = ids.get(str(ref))
                if up is not None and up.get("status") == "superseded":
                    errs.append(
                        f"{e.get('id')}: 过期 approval——上游 {ref} 已 superseded，"
                        f"本条 {e.get('status')} 随之失效，需重新走 human gate"
                    )
    return errs


def doc_errors_for_entry(e: dict, repo: Path) -> list[str]:
    errs: list[str] = []
    path = e.get("path")
    if not path:
        return errs
    f = repo / str(path)
    if not f.is_file():
        return errs  # registry_errors 已报悬空
    try:
        text = f.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return [f"{path}: 无法读取"]
    status = e.get("status")
    anchor = extract_status(text)
    if anchor is None:
        errs.append(f"{path}: 缺状态锚点行（Status: <enum> · <date> · <ref>）")
    elif anchor != status:
        errs.append(f"{path}: 状态锚点 {anchor} 与注册表 {status} 矛盾（同 commit 对齐两处）")
    if e.get("kind") == "plan" and status in SCOPE_REQUIRED:
        errs += [f"{path}: {m}（{status} 态必填）" for m in missing_plan_sections(text)]
    if status in SCOPE_REQUIRED and annotation_conflict(text):
        errs.append(
            f"{path}: Human 批注区仍有 [?]/[改] 未决批注，不能停留在 {status}——先收敛或回 in-review"
        )
    return errs


def kind_path_warnings(entries: list[dict]) -> list[str]:
    """路径不在四类目录内的条目：kind 为自由声明，允许但告警（校验按声明 kind 执行）。"""
    warns = []
    for e in entries:
        kind, path = e.get("kind"), e.get("path")
        if path and kind in KINDS and doc_kind(str(path)) is None:
            warns.append(
                f"{e.get('id')}: path 不在四类目录（{'、'.join(DOC_DIRS)}）内：{path}——"
                f"kind={kind} 为自由声明，必填段校验按声明 kind 执行"
            )
    return warns


def coverage_errors(entries: list[dict], repo: Path) -> list[str]:
    registered = {str(e.get("path")) for e in entries}
    return [
        f"{rel}: 四类文档未登记进 {REGISTRY_REL}"
        for rel in scan_docs(repo)
        if rel not in registered
    ]


def validate_repo(repo: Path):
    """返回 (errors, warnings)。存在四类受管文档但注册表缺失 → error（非 strict 也 fail）：
    注册表一旦建立就是治理面，缺失/被删即异常（删除注册表不能静默关闭治理）。"""
    errors: list[str] = []
    warnings: list[str] = []
    reg = repo / REGISTRY_REL
    if not reg.is_file():
        if scan_docs(repo):
            errors.append(
                f"存在四类受管文档但 {REGISTRY_REL} 缺失——注册表是治理面，缺失/被删即异常；"
                "恢复注册表并登记全部四类文档（schema 见 plans/ANATOMY.md）"
            )
        return errors, warnings
    entries, perr = parse_registry_text(reg.read_text(encoding="utf-8", errors="replace"))
    errors += perr
    if perr:
        return errors, warnings
    errors += registry_errors(entries, repo)
    warnings += kind_path_warnings(entries)
    for e in entries:
        errors += doc_errors_for_entry(e, repo)
    errors += coverage_errors(entries, repo)
    return errors, warnings


# ---------------------------------------------------------------- hook 判定入口

def _skip_by_env() -> bool:
    return os.environ.get(SKIP_ENV, "").strip().lower() in ("1", "true", "yes")


def _rel_to_repo(path_str: str, repo: Path) -> str | None:
    p = (path_str or "").strip().strip('"').strip("'")
    if not p:
        return None
    if p.startswith("./"):
        p = p[2:]
    pp = Path(p)
    if pp.is_absolute():
        try:
            return pp.resolve().relative_to(repo.resolve()).as_posix()
        except (ValueError, OSError):
            return None
    return pp.as_posix()


def _load_registry(repo: Path) -> list[dict] | None:
    reg = repo / REGISTRY_REL
    if not reg.is_file():
        return None
    try:
        entries, perr = parse_registry_text(reg.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return None
    return None if perr else entries


def _stale_reason(rel: str, status: str, repo: Path) -> str | None:
    entries = _load_registry(repo)
    if not entries:
        return None
    by_id = {str(e.get("id")): e for e in entries if e.get("id")}
    for e in entries:
        if str(e.get("path")) != rel:
            continue
        for ref in e.get("upstream") or []:
            up = by_id.get(str(ref))
            if up is not None and up.get("status") == "superseded":
                return (
                    f"doc-lifecycle: {rel} 标记 {status} 但其上游 {ref} 已 superseded"
                    f"——approval 已过期，需重新走 human gate。{_ESCAPE_HINT}"
                )
    return None


def _doc_write_reason(rel: str, kind: str, content: str, markers_text: str, repo: Path) -> str | None:
    """对一次「写入后的文档内容」判定进阶态完整性。content=用于状态/段落检查的全文（或联合语料），
    markers_text=用于未决批注检查的文本（apply_patch update 只看新增行，避免误拦）。"""
    status = extract_status(content)
    if status is None:
        return None  # 无状态锚点：coverage 由 validator 事后管，hook 不拦
    if status not in VALID_STATUS:
        return (
            f"doc-lifecycle: {rel} 的状态锚点非法：{status}"
            f"（合法：{'/'.join(sorted(VALID_STATUS))}）。{_ESCAPE_HINT}"
        )
    if status not in SCOPE_REQUIRED:
        return None  # draft/in-review/verified/superseded 的写入不拦
    if kind == "plan":
        missing = missing_plan_sections(content)
        if missing:
            return (
                f"doc-lifecycle: {rel} 标记 {status} 但完整性不成立：{'；'.join(missing)}。"
                f"approved/implementing 需 scope/forbidden/verification 齐全"
                f"（见 .agent/human-gates.md）。{_ESCAPE_HINT}"
            )
    if annotation_conflict(markers_text, whole_doc=(markers_text is content)):
        return (
            f"doc-lifecycle: {rel} 标记 {status} 但 Human 批注区仍有 [?]/[改] 未决批注"
            f"——先收敛批注或把状态回 in-review。{_ESCAPE_HINT}"
        )
    return _stale_reason(rel, status, repo)


def _registry_write_reason(content: str, repo: Path) -> str | None:
    entries, perr = parse_registry_text(content)
    problems = perr or registry_errors(entries, repo)
    # 不查 coverage 与文档锚点一致性：写入顺序上允许先建文档再登记/先登记状态再改锚点，
    # 两处对齐由 validator 在 commit 粒度强制。
    if problems:
        head = "；".join(problems[:3]) + ("；…" if len(problems) > 3 else "")
        return f"doc-lifecycle: 写入 {REGISTRY_REL} 后完整性不成立：{head}。{_ESCAPE_HINT}"
    return None


def _patch_ops(patch_text: str):
    """解析 apply_patch 文本为操作列表 dict(op, path, move_to, lines)。
    lines 为该操作块内的原始行（Add 全为 `+` 前缀；Update 为 hunk 行，含 `@@`/上下文/±行）。"""
    ops: list[dict] = []
    cur: dict | None = None
    for line in patch_text.splitlines():
        if line.startswith("*** Add File: "):
            cur = {"op": "add", "path": line[len("*** Add File: "):].strip(),
                   "move_to": None, "lines": []}
            ops.append(cur)
        elif line.startswith("*** Update File: "):
            cur = {"op": "update", "path": line[len("*** Update File: "):].strip(),
                   "move_to": None, "lines": []}
            ops.append(cur)
        elif line.startswith("*** Delete File: "):
            ops.append({"op": "delete", "path": line[len("*** Delete File: "):].strip(),
                        "move_to": None, "lines": []})
            cur = None
        elif line.startswith("*** Move to: ") and cur is not None and cur["op"] == "update":
            cur["move_to"] = line[len("*** Move to: "):].strip()
        elif line.startswith("*** End of File"):
            continue  # hunk 延伸到文件尾的标记，不影响行归属
        elif line.startswith("***"):
            cur = None  # Begin/End Patch 等边界
        elif cur is not None:
            cur["lines"].append(line)
    return ops


def _added_text(op: dict) -> str:
    return "\n".join(ln[1:] for ln in op["lines"] if ln.startswith("+"))


def _find_seq(haystack: list[str], needle: list[str], start: int) -> int:
    for i in range(start, len(haystack) - len(needle) + 1):
        if haystack[i:i + len(needle)] == needle:
            return i
    return -1


def _unique_anchor(haystack: list[str], anchor: str, start: int) -> int:
    matches = [i for i in range(start, len(haystack)) if haystack[i] == anchor]
    return matches[0] if len(matches) == 1 else -1


def _reconstruct_update(current: str, hunk_lines: list[str]) -> str | None:
    """按 apply_patch Update 语义把 hunk 应用到 current，返回 patch 后全文。
    `@@ <anchor>` 是 apply_patch 的 section 定位符，不是可丢弃的装饰：先唯一定位 anchor，
    再在其后匹配 hunk 的旧序列。anchor 缺失或重复时无法证明与真实 patch 落点一致，返回 None
    让调用方保守拦截。上下文对不上/行前缀不明/纯新增无定位同理。

    不再用「旧全文+新增行」联合语料（那会先读到旧状态，静默放行状态跃迁，见初审
    MAJOR-1）；也不忽略 anchor 后从文件头匹配重复片段（fresh review 回归）。
    """
    orig = current.split("\n")
    hunks: list[tuple[str | None, list[str]]] = []
    anchor: str | None = None
    body: list[str] = []
    for ln in hunk_lines:
        if ln.startswith("@@"):
            if body:
                hunks.append((anchor, body))
            anchor = ln[2:].strip() or None
            # 数字 unified-diff header 不是本 parser 承诺支持的 apply_patch section anchor。
            if anchor and re.match(r"^-\d+(?:,\d+)?\s+\+\d+(?:,\d+)?\s+@@", anchor):
                return None
            body = []
        else:
            body.append(ln)
    if body:
        hunks.append((anchor, body))
    out: list[str] = []
    pos = 0
    for anchor, hunk in hunks:
        if not hunk:
            continue
        old_seq: list[str] = []
        new_seq: list[str] = []
        for ln in hunk:
            if ln.startswith("+"):
                new_seq.append(ln[1:])
            elif ln.startswith("-"):
                old_seq.append(ln[1:])
            elif ln.startswith(" "):
                old_seq.append(ln[1:])
                new_seq.append(ln[1:])
            elif ln == "":
                old_seq.append("")
                new_seq.append("")
            else:
                return None  # 行前缀不属于 apply_patch 语法，语义不明
        if not old_seq:
            return None  # 纯新增且无上下文行，无法可靠定位
        search_from = pos
        if anchor is not None:
            anchor_idx = _unique_anchor(orig, anchor, pos)
            if anchor_idx < 0:
                return None  # 非空 anchor 缺失/重复：不能猜真实 apply_patch 落点
            search_from = anchor_idx + 1
        idx = _find_seq(orig, old_seq, search_from)
        if idx < 0:
            return None  # hunk 上下文与当前文件对不上
        out.extend(orig[pos:idx])
        out.extend(new_seq)
        pos = idx + len(old_seq)
    out.extend(orig[pos:])
    return "\n".join(out)


def _read_rel(repo: Path, rel: str) -> str | None:
    try:
        return (repo / rel).read_text(encoding="utf-8")
    except OSError:
        return None


_REGISTRY_REMOVE_MSG = (
    f"doc-lifecycle: 禁止删除/移走 {REGISTRY_REL}——注册表是治理面，"
    f"删除等于静默关闭 doc-lifecycle 校验。{_ESCAPE_HINT}"
)
# Bash 侧只拦「删除/移走注册表」这一件可判定的事；其余 Bash 写入由 validator 兜底。
_DELETIONISH = {"rm", "unlink", "shred", "srm", "truncate", "mv"}
_SHELL_WRAPPERS = {"command", "exec"}
_ENV_FLAGS_WITH_VALUE = {"-u", "--unset", "-C", "--chdir", "-S", "--split-string"}
_GIT_GLOBAL_FLAGS_WITH_VALUE = {
    "-C", "-c", "--config-env", "--exec-path", "--git-dir", "--work-tree",
    "--namespace", "--super-prefix", "--list-cmds", "--attr-source",
}


def _is_registry_path(raw: str, repo: Path) -> bool:
    if _rel_to_repo(raw, repo) == REGISTRY_REL:
        return True
    p = (raw or "").strip().strip('"').strip("'")
    return p == REGISTRY_REL or p.endswith("/" + REGISTRY_REL)


def _strip_command_wrapper_options(args: list[str]) -> list[str]:
    i = 0
    while i < len(args) and args[i] in {"-p", "--"}:
        i += 1
    return args[i:]


def _strip_env_wrapper(args: list[str]) -> list[str]:
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--":
            return args[i + 1:]
        if re.match(r"^[A-Za-z_]\w*=", arg):
            i += 1
            continue
        if arg in {"-i", "--ignore-environment", "-0", "--null"}:
            i += 1
            continue
        if arg in _ENV_FLAGS_WITH_VALUE:
            if i + 1 >= len(args):
                return []
            i += 2
            continue
        if any(arg.startswith(flag + "=") for flag in _ENV_FLAGS_WITH_VALUE if flag.startswith("--")):
            i += 1
            continue
        break
    return args[i:]


def _unwrap_command(seg: list[str]) -> tuple[str, list[str]]:
    """展开前导 assignment 与 `command`/`exec`/`env` wrapper，返回实际命令与参数。"""
    remaining = list(seg)
    for _ in range(8):  # wrapper 可嵌套；有界循环避免畸形输入拖住 hook
        while remaining and re.match(r"^[A-Za-z_]\w*=", remaining[0]):
            remaining.pop(0)
        if not remaining:
            return "", []
        name = remaining[0].rsplit("/", 1)[-1]
        args = remaining[1:]
        if name in _SHELL_WRAPPERS:
            remaining = _strip_command_wrapper_options(args)
            continue
        if name == "env":
            remaining = _strip_env_wrapper(args)
            continue
        return name, args
    return "", []


def _git_subcommand(args: list[str]) -> tuple[str, list[str]]:
    """跳过 git 全局选项，定位 subcommand；覆盖 `git -C . rm` 等合法形态。"""
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--":
            i += 1
            break
        if not arg.startswith("-") or arg == "-":
            return arg, args[i + 1:]
        if arg in _GIT_GLOBAL_FLAGS_WITH_VALUE:
            if i + 1 >= len(args):
                return "", []
            i += 2
            continue
        if any(arg.startswith(flag + "=") for flag in _GIT_GLOBAL_FLAGS_WITH_VALUE
               if flag.startswith("--")):
            i += 1
            continue
        i += 1  # 无参数全局 flag，如 --literal-pathspecs
    if i < len(args):
        return args[i], args[i + 1:]
    return "", []


def _bash_reason(cmd: str, repo: Path) -> str | None:
    """Bash 命令中对注册表的删除/移动（rm/unlink/shred/truncate/mv/git rm）→ 拦。"""
    if REGISTRY_REL.rsplit("/", 1)[-1] not in cmd:
        return None  # 廉价预过滤：命令未提及注册表文件名
    try:
        lex = shlex.shlex(cmd, posix=True, punctuation_chars=True)
        lex.whitespace_split = True
        toks = list(lex)
    except ValueError:
        toks = cmd.split()
    segs: list[list[str]] = [[]]
    for t in toks:
        if t and set(t) <= set(";|&<>()"):
            segs.append([])
        else:
            segs[-1].append(t)
    for seg in segs:
        name, args = _unwrap_command(seg)
        if name == "git":
            subcommand, args = _git_subcommand(args)
            name = subcommand.rsplit("/", 1)[-1]
        if name not in _DELETIONISH:
            continue
        if any(not a.startswith("-") and _is_registry_path(a, repo) for a in args):
            return _REGISTRY_REMOVE_MSG
    return None


def pretooluse_reason(tool_name: str, tool_input: dict, repo_root) -> str | None:
    """PreToolUse 机械拦截判定入口（pre_tool_guard.py 薄接线调用）。
    返回 None = 放行；返回字符串 = 阻止理由。只判可判定事实；解析不确定时原则上放行，
    两个例外保守拦截：删除/移走注册表；apply_patch Update 触碰受管目标但无法可靠重建全文。"""
    if _skip_by_env():
        return None
    repo = Path(repo_root)
    tool_input = tool_input or {}

    if tool_name in ("Edit", "Write"):
        rel = _rel_to_repo(tool_input.get("file_path") or "", repo)
        if rel is None:
            return None
        if tool_name == "Write":
            prospective = tool_input.get("content") or ""
        else:
            f = repo / rel
            try:
                current = f.read_text(encoding="utf-8")
            except OSError:
                return None
            old = tool_input.get("old_string") or ""
            new = tool_input.get("new_string") or ""
            if not old or old not in current:
                return None  # tool 本身会失败，无需拦
            prospective = (
                current.replace(old, new)
                if tool_input.get("replace_all")
                else current.replace(old, new, 1)
            )
        if rel == REGISTRY_REL:
            return _registry_write_reason(prospective, repo)
        kind = doc_kind(rel)
        if kind:
            return _doc_write_reason(rel, kind, prospective, prospective, repo)
        return None

    if tool_name == "Bash":
        return _bash_reason(tool_input.get("command") or "", repo)

    if tool_name == "apply_patch":
        patch = tool_input.get("command") or tool_input.get("patch") or ""
        for op in _patch_ops(patch):
            rel = _rel_to_repo(op["path"], repo)
            if rel is None:
                continue
            dest = _rel_to_repo(op["move_to"], repo) if op["move_to"] else rel

            if op["op"] == "delete":
                if rel == REGISTRY_REL:
                    return _REGISTRY_REMOVE_MSG
                continue

            if rel == REGISTRY_REL or dest == REGISTRY_REL:
                if op["op"] == "update" and dest != REGISTRY_REL:
                    return _REGISTRY_REMOVE_MSG  # Move to 把注册表移走 = 变相删除
                if op["op"] == "add":
                    prospective = _added_text(op)
                else:
                    current = _read_rel(repo, rel)
                    if current is None:
                        continue  # 文件不存在：apply_patch 本身会失败，无需拦
                    prospective = _reconstruct_update(current, op["lines"])
                    if prospective is None:
                        return (
                            f"doc-lifecycle: 无法可靠重建对 {REGISTRY_REL} 的 apply_patch Update"
                            f" 结果（hunk 上下文与当前文件对不上/语法不明）——保守拦截，"
                            f"请改用 Edit 工具或拆成更小的 patch。{_ESCAPE_HINT}"
                        )
                reason = _registry_write_reason(prospective, repo)
                if reason:
                    return reason
                continue

            kind = doc_kind(rel) or (doc_kind(dest) if dest else None)
            if not kind:
                continue
            if op["op"] == "add":
                prospective = _added_text(op)
            else:
                current = _read_rel(repo, rel)
                if current is None:
                    continue  # 文件不存在：apply_patch 本身会失败，无需拦
                prospective = _reconstruct_update(current, op["lines"])
                if prospective is None:
                    return (
                        f"doc-lifecycle: 无法可靠重建对 {rel} 的 apply_patch Update 结果"
                        f"（hunk 上下文与当前文件对不上/语法不明）——保守拦截，"
                        f"请改用 Edit 工具或拆成更小的 patch。{_ESCAPE_HINT}"
                    )
            reason = _doc_write_reason(rel, kind, prospective, prospective, repo)
            if reason:
                return reason
    return None


# ---------------------------------------------------------------- 内嵌 fixtures（self-test）

_OK_PLAN = """# demo plan

Status: approved · 2026-07-12 · human 批准（demo）

## Allowed paths

- plans/demo.zh.md

## Forbidden paths

- lab/data/**

## Human 批注区

- [OK] 同意

## 验证标准

- python scripts/check-doc-lifecycle.py
"""

_OK_REGISTRY = """# demo registry
docs:
  - id: plan-demo
    path: plans/demo.zh.md
    kind: plan
    status: approved
    issue: "#123"
    branch: feat/demo
    worktree: .
    approval: "human 批准（demo）"
    upstream: []
    downstream: []
"""


def _mk(root: Path, files: dict[str, str]) -> None:
    for rel, text in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")


def _init_fixture_git(root: Path) -> None:
    subprocess.run(
        ["git", "init", "-q", "-b", "feat/demo", str(root)],
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        [
            "git", "-C", str(root), "-c", "user.name=doc-lifecycle-fixture",
            "-c", "user.email=fixture@example.invalid", "commit", "--allow-empty", "-qm", "fixture",
        ],
        check=True,
        capture_output=True,
        text=True,
    )


def self_test() -> int:
    import tempfile

    failures: list[str] = []

    def check(name: str, cond: bool) -> None:
        print(f"  {'PASS' if cond else 'FAIL'}  {name}")
        if not cond:
            failures.append(name)

    def fresh(files: dict[str, str]):
        td = tempfile.TemporaryDirectory()
        root = Path(td.name)
        _mk(root, files)
        _init_fixture_git(root)
        return td, root

    print("[check-doc-lifecycle] self-test（内嵌 fixtures）")

    # 1. 正向：approved 且字段齐全、注册表引用真实
    td, root = fresh({"plans/demo.zh.md": _OK_PLAN, REGISTRY_REL: _OK_REGISTRY})
    errs, _ = validate_repo(root)
    check("正向样例通过", errs == [])
    td.cleanup()

    # 2. 缺字段：approved 但 Forbidden paths 段缺失
    bad = _OK_PLAN.replace("## Forbidden paths\n\n- lab/data/**\n\n", "")
    td, root = fresh({"plans/demo.zh.md": bad, REGISTRY_REL: _OK_REGISTRY})
    errs, _ = validate_repo(root)
    check("缺 Forbidden paths 段被报错", any("Forbidden paths" in e for e in errs))
    td.cleanup()

    # 3. 悬空引用：upstream 指向不存在条目
    reg = _OK_REGISTRY.replace("upstream: []", "upstream: [brief-missing]")
    td, root = fresh({"plans/demo.zh.md": _OK_PLAN, REGISTRY_REL: reg})
    errs, _ = validate_repo(root)
    check("悬空 upstream 被报错", any("悬空引用" in e and "brief-missing" in e for e in errs))
    td.cleanup()

    # 4. 过期 approval：上游 brief 已 superseded
    brief = "# demo brief\n\nStatus: superseded · 2026-07-12 · 已被新 brief 取代\n"
    reg = (
        _OK_REGISTRY.replace("upstream: []", "upstream: [brief-demo]")
        + """  - id: brief-demo
    path: human/briefs/active/demo.md
    kind: brief
    status: superseded
    approval: null
    upstream: []
    downstream: [plan-demo]
"""
    )
    td, root = fresh({
        "plans/demo.zh.md": _OK_PLAN,
        "human/briefs/active/demo.md": brief,
        REGISTRY_REL: reg,
    })
    errs, _ = validate_repo(root)
    check("过期 approval（上游 superseded）被报错", any("过期 approval" in e for e in errs))
    td.cleanup()

    # 5. 冲突/未决批注：approved 但批注区残留 [改]
    conflicted = _OK_PLAN.replace("- [OK] 同意", "- [OK] 第一段可以\n- [改] 第二段要重写")
    td, root = fresh({"plans/demo.zh.md": conflicted, REGISTRY_REL: _OK_REGISTRY})
    errs, _ = validate_repo(root)
    check("approved 残留 [改] 批注被报错", any("未决批注" in e for e in errs))
    td.cleanup()

    # 6. 锚点与注册表矛盾
    reg = _OK_REGISTRY.replace("status: approved", "status: verified")
    td, root = fresh({"plans/demo.zh.md": _OK_PLAN, REGISTRY_REL: reg})
    errs, _ = validate_repo(root)
    check("锚点/注册表状态矛盾被报错", any("矛盾" in e for e in errs))
    td.cleanup()

    # 7. 未登记文档（coverage）
    td, root = fresh({
        "plans/demo.zh.md": _OK_PLAN,
        "plans/rogue.zh.md": "# rogue\n\nStatus: draft · 2026-07-12 · 未登记\n",
        REGISTRY_REL: _OK_REGISTRY,
    })
    errs, _ = validate_repo(root)
    check("未登记文档被报错", any("未登记" in e for e in errs))
    td.cleanup()

    # 8. hook：Write 标 approved 但缺段 → 拦；DOC_LIFECYCLE_SKIP=1 → 放行
    td, root = fresh({REGISTRY_REL: _OK_REGISTRY})
    w = {"file_path": str(root / "plans/demo.zh.md"), "content": bad}
    check("hook 拦 Write(approved 缺段)", pretooluse_reason("Write", w, root) is not None)
    old_env = os.environ.get(SKIP_ENV)
    os.environ[SKIP_ENV] = "1"
    try:
        check("DOC_LIFECYCLE_SKIP=1 显式放行", pretooluse_reason("Write", w, root) is None)
    finally:
        if old_env is None:
            os.environ.pop(SKIP_ENV, None)
        else:
            os.environ[SKIP_ENV] = old_env
    w_draft = {"file_path": str(root / "plans/demo.zh.md"),
               "content": bad.replace("Status: approved", "Status: draft")}
    check("hook 放行 draft 写入", pretooluse_reason("Write", w_draft, root) is None)
    td.cleanup()

    # 9. hook：Edit 把 draft 跃迁到 approved 但缺段 → 拦
    td, root = fresh({
        "plans/demo.zh.md": bad.replace("Status: approved", "Status: draft"),
        REGISTRY_REL: _OK_REGISTRY.replace("status: approved", "status: draft"),
    })
    e_in = {"file_path": str(root / "plans/demo.zh.md"),
            "old_string": "Status: draft", "new_string": "Status: approved"}
    check("hook 拦 Edit(跃迁 approved 缺段)", pretooluse_reason("Edit", e_in, root) is not None)
    td.cleanup()

    # 10. hook：apply_patch Add File 违规 → 拦（Codex 表面）
    td, root = fresh({REGISTRY_REL: _OK_REGISTRY})
    patch = "*** Begin Patch\n*** Add File: plans/demo.zh.md\n" + "\n".join(
        "+" + ln for ln in bad.splitlines()
    ) + "\n*** End Patch"
    check("hook 拦 apply_patch(Add 违规)",
          pretooluse_reason("apply_patch", {"command": patch}, root) is not None)
    td.cleanup()

    # 11. hook：写注册表引入悬空 path → 拦
    td, root = fresh({"plans/demo.zh.md": _OK_PLAN})
    reg_bad = _OK_REGISTRY.replace("plans/demo.zh.md", "plans/ghost.zh.md")
    r_in = {"file_path": str(root / REGISTRY_REL), "content": reg_bad}
    check("hook 拦注册表悬空 path", pretooluse_reason("Write", r_in, root) is not None)
    r_ok = {"file_path": str(root / REGISTRY_REL), "content": _OK_REGISTRY}
    check("hook 放行合法注册表写入", pretooluse_reason("Write", r_ok, root) is None)
    td.cleanup()

    # 12. 受限解析器（无 PyYAML 路径）：行内列表 + 块列表
    sample = (
        "# c\ndocs:\n  - id: a\n    path: p.md\n    kind: plan\n    status: draft\n"
        "    upstream: [x, y]\n    downstream:\n      - z\n    superseded_by: null\n"
    )
    entries, perr = _parse_restricted(sample)
    check(
        "受限解析器解析块/行内列表",
        perr == [] and len(entries) == 1
        and entries[0]["upstream"] == ["x", "y"]
        and entries[0]["downstream"] == ["z"]
        and entries[0]["superseded_by"] is None,
    )

    # 13. hook：apply_patch Update 状态跃迁 verified→approved 但缺段 → 拦（初审 MAJOR-1 PoC）
    doc_v = "# demo\n\nStatus: verified · 2026-07-12 · done\n\n## Human 批注区\n\n- [OK] 同意\n"
    td, root = fresh({
        "plans/demo.zh.md": doc_v,
        REGISTRY_REL: _OK_REGISTRY.replace("status: approved", "status: verified"),
    })
    up = (
        "*** Begin Patch\n*** Update File: plans/demo.zh.md\n@@\n"
        "-Status: verified · 2026-07-12 · done\n"
        "+Status: approved · 2026-07-13 · human ok\n*** End Patch"
    )
    check("hook 拦 apply_patch(Update 跃迁 approved 缺段)",
          pretooluse_reason("apply_patch", {"command": up}, root) is not None)
    ok_up = (
        "*** Begin Patch\n*** Update File: plans/demo.zh.md\n@@\n"
        "-- [OK] 同意\n+- [OK] 同意（补充说明）\n*** End Patch"
    )
    check("hook 放行 apply_patch(Update 合规内容修改)",
          pretooluse_reason("apply_patch", {"command": ok_up}, root) is None)
    bad_ctx = (
        "*** Begin Patch\n*** Update File: plans/demo.zh.md\n@@\n"
        "-这一行不存在于当前文件\n+Status: approved · x · y\n*** End Patch"
    )
    check("hook 保守拦 apply_patch(Update 无法重建全文)",
          pretooluse_reason("apply_patch", {"command": bad_ctx}, root) is not None)

    # fresh review 回归：`@@ <anchor>` 必须把重复片段定位到指定 section，不能丢 anchor 后改第一处。
    anchored_doc = _OK_PLAN.replace(
        "## Human 批注区\n\n- [OK] 同意",
        "## Notes\n\n- [OK] 同意\n\n## Human 批注区\n\n- [OK] 同意",
    )
    (root / "plans/demo.zh.md").write_text(anchored_doc, encoding="utf-8")
    anchored_patch = (
        "*** Begin Patch\n*** Update File: plans/demo.zh.md\n@@ ## Human 批注区\n"
        "-- [OK] 同意\n+- [改] 仍未收敛\n*** End Patch"
    )
    anchored_result = _reconstruct_update(
        anchored_doc,
        ["@@ ## Human 批注区", "-- [OK] 同意", "+- [改] 仍未收敛"],
    )
    check(
        "apply_patch Update 尊重 @@ anchor 定位重复片段",
        anchored_result is not None
        and "## Notes\n\n- [OK] 同意" in anchored_result
        and "## Human 批注区\n\n- [改] 仍未收敛" in anchored_result,
    )
    check(
        "hook 拦 anchored Update 在 Human 批注区引入 [改]",
        pretooluse_reason("apply_patch", {"command": anchored_patch}, root) is not None,
    )
    ambiguous = anchored_doc.replace("## Notes", "## Human 批注区")
    check(
        "重复非空 anchor 时保守拒绝重建",
        _reconstruct_update(
            ambiguous,
            ["@@ ## Human 批注区", "-- [OK] 同意", "+- [改] 仍未收敛"],
        ) is None,
    )
    td.cleanup()

    # 14. hook：apply_patch Update 注册表 → 重建全文判定（初审 MAJOR-1 PoC：悬空 upstream）
    td, root = fresh({"plans/demo.zh.md": _OK_PLAN, REGISTRY_REL: _OK_REGISTRY})
    reg_up = (
        f"*** Begin Patch\n*** Update File: {REGISTRY_REL}\n@@\n"
        "-    upstream: []\n+    upstream: [ghost-entry]\n*** End Patch"
    )
    check("hook 拦 apply_patch(注册表 Update 悬空 upstream)",
          pretooluse_reason("apply_patch", {"command": reg_up}, root) is not None)
    reg_ok = (
        f"*** Begin Patch\n*** Update File: {REGISTRY_REL}\n@@\n"
        "-    status: approved\n+    status: implementing\n*** End Patch"
    )
    check("hook 放行 apply_patch(注册表 Update 合法)",
          pretooluse_reason("apply_patch", {"command": reg_ok}, root) is None)
    td.cleanup()

    # 15. hook：删除/移走注册表 → 拦（初审 MAJOR-2 PoC：apply_patch Delete；另覆盖 Move/Bash）
    td, root = fresh({"plans/demo.zh.md": _OK_PLAN, REGISTRY_REL: _OK_REGISTRY})
    del_patch = f"*** Begin Patch\n*** Delete File: {REGISTRY_REL}\n*** End Patch"
    check("hook 拦 apply_patch(Delete 注册表)",
          pretooluse_reason("apply_patch", {"command": del_patch}, root) is not None)
    mv_patch = (
        f"*** Begin Patch\n*** Update File: {REGISTRY_REL}\n"
        "*** Move to: /tmp/graveyard.yaml\n@@\n-# demo registry\n+# gone\n*** End Patch"
    )
    check("hook 拦 apply_patch(Move 注册表)",
          pretooluse_reason("apply_patch", {"command": mv_patch}, root) is not None)
    check("hook 拦 Bash rm 注册表",
          pretooluse_reason("Bash", {"command": f"rm {REGISTRY_REL}"}, root) is not None)
    check("hook 拦 Bash mv 注册表",
          pretooluse_reason("Bash", {"command": f"cd /x && mv {REGISTRY_REL} /tmp/"}, root)
          is not None)
    for wrapped in (
        f"git -C . rm {REGISTRY_REL}",
        f"git --literal-pathspecs rm {REGISTRY_REL}",
        f"command rm {REGISTRY_REL}",
        f"env rm {REGISTRY_REL}",
    ):
        check(
            f"hook 拦 Bash wrapper/global-option 绕过：{wrapped.split()[0:3]}",
            pretooluse_reason("Bash", {"command": wrapped}, root) is not None,
        )
    check("hook 放行 Bash 只读触碰注册表",
          pretooluse_reason(
              "Bash", {"command": f"cat {REGISTRY_REL} && grep status {REGISTRY_REL}"}, root
          ) is None)
    td.cleanup()

    # 16. kind 谎报（初审 MAJOR-3 PoC）：plans/ 下登记成 decision → error + hook 拦
    lie = _OK_REGISTRY.replace("kind: plan", "kind: decision")
    plan_bare = "# demo\n\nStatus: approved · 2026-07-12 · human ok\n"
    td, root = fresh({"plans/demo.zh.md": plan_bare, REGISTRY_REL: lie})
    errs, _ = validate_repo(root)
    check("kind 与路径类别不符被报错", any("路径类别不符" in e for e in errs))
    w_lie = {"file_path": str(root / REGISTRY_REL), "content": lie}
    check("hook 拦注册表 kind 谎报写入", pretooluse_reason("Write", w_lie, root) is not None)
    td.cleanup()
    outside = _OK_REGISTRY.replace("plans/demo.zh.md", "notes/demo.md")
    td, root = fresh({"notes/demo.md": _OK_PLAN, REGISTRY_REL: outside})
    errs, warns = validate_repo(root)
    check("四类目录外路径自由声明 kind 仅告警",
          errs == [] and any("自由声明" in w for w in warns))
    td.cleanup()

    # 17. 活跃 plan 关联：issue 非占位规范坐标、branch 真实存在、implementing worktree
    # 必须是 git worktree 且绑定同一 branch；verified 历史态允许清理临时实体。
    implementing_plan = _OK_PLAN.replace("Status: approved", "Status: implementing")
    implementing_reg = _OK_REGISTRY.replace("status: approved", "status: implementing")
    td, root = fresh({"plans/demo.zh.md": implementing_plan, REGISTRY_REL: implementing_reg})
    errs, _ = validate_repo(root)
    check("implementing plan 的真实 issue/branch/worktree 关联通过", errs == [])

    for label, bad_reg, needle in (
        ("issue 占位", implementing_reg.replace('issue: "#123"', 'issue: "<issue>"'), "issue"),
        ("branch 不存在", implementing_reg.replace("branch: feat/demo", "branch: feat/missing"), "branch"),
        ("worktree 缺失", implementing_reg.replace("worktree: .", "worktree: null"), "worktree"),
        ("worktree 未登记", implementing_reg.replace("worktree: .", "worktree: missing"), "worktree"),
    ):
        (root / REGISTRY_REL).write_text(bad_reg, encoding="utf-8")
        errs, _ = validate_repo(root)
        check(f"implementing plan 的{label}被报错", any(needle in e for e in errs))
        check(
            f"hook 拦 implementing plan 的{label}注册表写入",
            pretooluse_reason(
                "Write", {"file_path": str(root / REGISTRY_REL), "content": bad_reg}, root
            ) is not None,
        )
    td.cleanup()

    verified_plan = _OK_PLAN.replace("Status: approved", "Status: verified")
    verified_reg = (
        _OK_REGISTRY.replace("status: approved", "status: verified")
        .replace('issue: "#123"', "issue: null")
        .replace("branch: feat/demo", "branch: feat/already-deleted")
        .replace("worktree: .", "worktree: null")
    )
    td, root = fresh({"plans/demo.zh.md": verified_plan, REGISTRY_REL: verified_reg})
    errs, _ = validate_repo(root)
    check("verified 历史 plan 不追溯要求临时 branch/worktree 存活", errs == [])
    td.cleanup()

    # 18. 注册表缺失（初审 MAJOR-2）：有受管文档 → error；完全未启用 → 不报
    td, root = fresh({"plans/demo.zh.md": _OK_PLAN})
    errs, _ = validate_repo(root)
    check("有受管文档但注册表缺失升级为 error", any("缺失" in e for e in errs))
    td.cleanup()
    td, root = fresh({"docs/x.md": "# x\n"})
    errs, warns = validate_repo(root)
    check("无四类文档时注册表缺失不报", errs == [] and warns == [])
    td.cleanup()

    n = len(failures)
    print(f"[check-doc-lifecycle] self-test {'OK' if not n else 'FAIL'} — {n} failure(s)")
    return 1 if n else 0


# ---------------------------------------------------------------- CLI

def main(argv: list[str]) -> int:
    if "--self-test" in argv:
        return self_test()
    strict = "--strict" in argv
    errors, warnings = validate_repo(REPO)
    for w in warnings:
        print(f"WARN  {w}")
    for e in errors:
        print(f"ERROR {e}")
    n_e, n_w = len(errors), len(warnings)
    ok = not n_e and not (strict and n_w)
    print(f"[check-doc-lifecycle] {'OK' if ok else 'FAIL'} — {n_e} error(s), {n_w} warning(s)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
