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
from datetime import date, datetime
from fnmatch import fnmatchcase
from glob import iglob
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

STATUS_PREFIX = re.compile(r"^\s*>?\s*Status[:：]")
STATUS_LINE = re.compile(
    r"^\s*>?\s*Status[:：]\s*([A-Za-z-]+)\s*·\s*"
    r"(\d{4}-\d{2}-\d{2})\s*·\s*(.*?)\s*$"
)
UNRESOLVED_MARK = re.compile(r"^\s*(?:[-*]\s*)?\[(?:\?|改)\]", re.MULTILINE)
MARKDOWN_LIST_PREFIX = re.compile(r"^(?:[-*+]|\d+[.)])(?:\s+|$)")
MARKDOWN_CHECK_PREFIX = re.compile(r"^\[[ xX]\](?:\s+|$)")
EVIDENCE_PLACEHOLDER = re.compile(
    r"^(?:"
    r"\[(?:todo|tbd|n/?a|none|null)\](?:$|[\s:(])"
    r"|(?:todo|tbd)(?:$|\s*:|\s+(?:pending|replace)\b)"
    r"|n/?a(?:$|(?:\s+|\s*:\s*)(?:pending|todo|tbd|replace)\b)"
    r"|(?:none|null)(?:$|\s*:\s*(?:pending|todo|tbd|replace)\b)"
    r")",
    re.IGNORECASE,
)
FENCE_LINE = re.compile(r"^(`{3,}|~{3,})(.*)$")
FORMATTING_ONLY = re.compile(r"^(?:`+|~+|\*+|_+|#+|>+|<code>\s*</code>)$", re.IGNORECASE)
HEADING_PREFIX = re.compile(r"^#{1,6}(?:\s+|$)")
BLOCKQUOTE_PREFIX = re.compile(r"^>+\s*")
HORIZONTAL_RULE = re.compile(r"^(?:(?:-\s*){3,}|(?:\*\s*){3,}|(?:_\s*){3,})$")
TABLE_SEPARATOR_CELL = re.compile(r"^:?-{3,}:?$")
SKIP_ENV = "DOC_LIFECYCLE_SKIP"
_ESCAPE_HINT = f"确属 human 明示例外可 {SKIP_ENV}=1 显式放行（validator 仍会事后校验）。"

LIST_FIELDS = ("upstream", "downstream")


def _strip_markdown_item_prefixes(value: str) -> str:
    """递归剥掉 Markdown list/checkbox 前缀，不把正文中的符号当作前缀。"""
    text = value.strip()
    while text:
        before = text
        for pattern in (MARKDOWN_LIST_PREFIX, MARKDOWN_CHECK_PREFIX):
            match = pattern.match(text)
            if match:
                text = text[match.end():].strip()
        if text == before:
            break
    return text


def _strip_wrapping_formatting(value: str) -> str:
    """只剥完整包裹的轻量行内格式；普通 prose/code 中的符号保持原样。"""
    text = value.strip()
    pairs = (("**", "**"), ("__", "__"), ("~~", "~~"), ("`", "`"))
    for _ in range(8):
        for left, right in pairs:
            if len(text) > len(left) + len(right) and text.startswith(left) and text.endswith(right):
                text = text[len(left):-len(right)].strip()
                break
        else:
            return text
    return text


def _normalized_scalar(value) -> str | None:
    if not isinstance(value, str):
        return None
    return _strip_wrapping_formatting(_strip_markdown_item_prefixes(value))


def _is_evidence_missing_or_placeholder(value) -> bool:
    """approval/anchor/section 证据：拒绝明确 placeholder phrase，不误伤正常开头 prose。"""
    text = _normalized_scalar(value)
    return text is None or not text or text.startswith("<") or bool(EVIDENCE_PLACEHOLDER.match(text))


def _is_association_missing_or_placeholder(value) -> bool:
    """issue/branch/worktree 坐标只拒绝空值与 exact token；todo/foo 等合法名字可用。"""
    text = _normalized_scalar(value)
    return (
        text is None
        or not text
        or text.startswith("<")
        or text.lower() in {"none", "null", "n/a", "na", "tbd", "todo", "-"}
    )


# ---------------------------------------------------------------- 注册表解析

def _strip_yaml_inline_comment(raw: str) -> str:
    """剥掉 YAML plain-scalar inline comment；引号内的 `#` 保持为证据正文。"""
    quote: str | None = None
    escaped = False
    for index, char in enumerate(raw):
        if quote == '"' and char == "\\" and not escaped:
            escaped = True
            continue
        if char in "'\"" and not escaped:
            quote = None if quote == char else (char if quote is None else quote)
        elif char == "#" and quote is None and (index == 0 or raw[index - 1].isspace()):
            return raw[:index].rstrip()
        escaped = False
    return raw


def _scalar(raw: str):
    v = raw.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "'\"":
        return v[1:-1]
    lower = v.lower()
    if not v or lower == "null" or v == "~":
        return None
    if v == "[]":
        return []
    if v == "{}":
        return {}
    if v.startswith("[") and v.endswith("]"):
        inner = v[1:-1].strip()
        return [_scalar(item) for item in inner.split(",") if item.strip()] if inner else []
    if v.startswith("{") and v.endswith("}"):
        # The restricted parser only needs type parity here. Registry fields never accept mappings,
        # so preserving the mapping type is sufficient to reject it deterministically.
        return {"__inline_mapping__": v[1:-1].strip()}
    if lower in ("true", "false", "yes", "no", "on", "off"):
        return lower in ("true", "yes", "on")
    if re.fullmatch(r"[+-]?0x[0-9a-f]+", lower):
        return int(lower, 0)
    if re.fullmatch(r"[+-]?0b[01]+", lower):
        return int(lower, 0)
    if re.fullmatch(r"[+-]?\d[\d_]*", v):
        return int(v.replace("_", ""))
    if re.fullmatch(r"[+-]?(?:\d+\.\d*|\.\d+)(?:e[+-]\d+)?", lower):
        return float(lower)
    if lower in (".inf", "+.inf", "-.inf", ".nan"):
        return float(lower.replace(".", "", 1))
    if re.fullmatch(r"\d+(?::[0-5]?\d){1,}", v):
        total = 0
        for part in v.split(":"):
            total = total * 60 + int(part)
        return total
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}[Tt ]\S+", v):
        try:
            return datetime.fromisoformat(v.replace("Z", "+00:00").replace("z", "+00:00"))
        except ValueError:
            pass
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
        try:
            return date.fromisoformat(v)
        except ValueError:
            pass
    return v


def _parse_restricted(text: str):
    """无 PyYAML 时的受限解析器：只支持本注册表约定的结构。返回 (entries, errors)。"""
    entries: list[dict] = []
    errors: list[str] = []
    cur: dict | None = None
    cur_list: str | None = None
    in_docs = False
    for lineno, raw in enumerate(text.splitlines(), 1):
        raw = _strip_yaml_inline_comment(raw)
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


def _parse_status_anchor(text: str) -> tuple[str | None, str | None]:
    """返回 (status, error)：没有锚点不是解析错误，出现 Status 前缀却不完整则是。"""
    for line in text.splitlines():
        if not STATUS_PREFIX.match(line):
            continue
        m = STATUS_LINE.fullmatch(line)
        if not m:
            return None, "状态锚点格式非法（应为 Status: <enum> · <YYYY-MM-DD> · <ref>）"
        status, raw_date, ref = m.groups()
        try:
            date.fromisoformat(raw_date)
        except ValueError:
            return None, f"状态锚点日期非法：{raw_date}（应为真实 YYYY-MM-DD 日期）"
        if _is_evidence_missing_or_placeholder(ref):
            return None, "状态锚点 ref 缺失/占位（需可核验的非占位引用）"
        return status, None
    return None, None


def extract_status(text: str) -> str | None:
    status, error = _parse_status_anchor(text)
    return None if error else status


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
    fence: str | None = None
    for raw_line in body:
        text = _strip_markdown_item_prefixes(raw_line)
        for _ in range(8):
            before = text
            text = BLOCKQUOTE_PREFIX.sub("", text).strip()
            text = HEADING_PREFIX.sub("", text).strip()
            text = _strip_markdown_item_prefixes(text)
            if text == before:
                break
        fence_match = FENCE_LINE.match(text)
        if fence is not None:
            if fence_match and fence_match.group(1)[0] == fence:
                fence = None
            elif (
                text
                and not FORMATTING_ONLY.fullmatch(text)
                and not HORIZONTAL_RULE.fullmatch(text)
                and not _is_evidence_missing_or_placeholder(text)
            ):
                return True
            continue
        if fence_match:
            fence = fence_match.group(1)[0]
            continue
        if FORMATTING_ONLY.fullmatch(text) or HORIZONTAL_RULE.fullmatch(text):
            continue
        if text.startswith("|") and text.endswith("|"):
            cells = [cell.strip() for cell in text[1:-1].split("|")]
            if all(
                not cell
                or TABLE_SEPARATOR_CELL.fullmatch(cell)
                or _is_evidence_missing_or_placeholder(cell)
                for cell in cells
            ):
                continue
        if not _is_evidence_missing_or_placeholder(text):
            return True
    return False


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
    raw_id = e.get("id")
    eid = raw_id if isinstance(raw_id, str) and raw_id else "<invalid-id>"
    status = e.get("status")
    if (
        e.get("kind") != "plan"
        or not isinstance(status, str)
        or status not in ACTIVE_PLAN_ASSOC_REQUIRED
    ):
        return []

    errors: list[str] = []
    issue = e.get("issue")
    branch = e.get("branch")
    worktree = e.get("worktree")
    if _is_association_missing_or_placeholder(issue):
        errors.append(f"{eid}: status={status} 的活跃 plan 缺非占位 issue 关联")
    elif not ISSUE_REF.fullmatch(str(issue).strip()):
        errors.append(
            f"{eid}: issue 关联格式非法：{issue}（应为 #N 或 https://github.com/<owner>/<repo>/issues/N）"
        )

    if _is_association_missing_or_placeholder(branch):
        errors.append(f"{eid}: status={status} 的活跃 plan 缺非占位 branch 关联")
    elif not _branch_exists(repo, str(branch)):
        errors.append(f"{eid}: branch 不存在或不是单一 Git ref：{branch}")

    if status == "implementing" and _is_association_missing_or_placeholder(worktree):
        errors.append(f"{eid}: status=implementing 的 plan 缺非占位 worktree 关联")
    elif (
        not _is_association_missing_or_placeholder(worktree)
        and not _is_association_missing_or_placeholder(branch)
    ):
        if not _worktree_matches(repo, str(worktree), str(branch)):
            errors.append(
                f"{eid}: worktree 不存在、未登记，或未绑定 branch={branch}：{worktree}"
            )
    return errors


def registry_errors(entries: list[dict], repo: Path, *, check_paths: bool = True) -> list[str]:
    errs: list[str] = []
    if not entries and scan_docs(repo):
        errs.append(
            f"{REGISTRY_REL} 的 docs 不能为空——repo 中仍存在四类受管文档，"
            "清空注册表会静默关闭治理"
        )
    ids: dict[str, dict] = {}
    for e in entries:
        raw_id = e.get("id")
        if not isinstance(raw_id, str) or not raw_id.strip():
            errs.append(f"注册表 id 应为非空字符串，实际：{raw_id!r}")
            continue
        eid = raw_id.strip()
        if eid in ids:
            errs.append(f"注册表 id 重复：{eid}")
        ids[eid] = e
    for e in entries:
        raw_id = e.get("id")
        eid = raw_id.strip() if isinstance(raw_id, str) and raw_id.strip() else "<invalid-id>"
        kind, status, path = e.get("kind"), e.get("status"), e.get("path")
        if not isinstance(kind, str):
            errs.append(f"{eid}: kind 应为字符串，实际：{kind!r}")
        elif kind not in KINDS:
            errs.append(f"{eid}: kind 非法：{kind}（合法：{'/'.join(sorted(KINDS))}）")
        if not isinstance(status, str):
            errs.append(f"{eid}: status 应为字符串，实际：{status!r}")
        elif status not in VALID_STATUS:
            errs.append(f"{eid}: status 非法：{status}（合法：{'/'.join(sorted(VALID_STATUS))}）")
        if not isinstance(path, str) or not path.strip():
            errs.append(f"{eid}: path 应为非空字符串，实际：{path!r}")
        elif check_paths and not (repo / path).is_file():
            errs.append(f"{eid}: path 指向不存在的文件：{path}（悬空引用）")
        # kind 与路径类别一致性：四类目录内的文档不允许谎报 kind（否则可绕过 plan 必填段校验）。
        if isinstance(path, str) and isinstance(kind, str) and kind in KINDS:
            expected = doc_kind(path)
            if expected is not None and expected != kind:
                errs.append(
                    f"{eid}: kind={kind} 与路径类别不符：{path} 属 {expected} 目录，"
                    f"必须登记为 kind={expected}（防止谎报 kind 绕过必填段校验）"
                )
        if (
            isinstance(status, str)
            and status in APPROVAL_REQUIRED
            and _is_evidence_missing_or_placeholder(e.get("approval"))
        ):
            errs.append(f"{eid}: status={status} 但 approval 证据缺失/占位（human gate 引用必填）")
        for field in LIST_FIELDS:
            raw_refs = e.get(field)
            if raw_refs is None:
                refs = []
            elif not isinstance(raw_refs, list):
                errs.append(f"{eid}: {field} 应为字符串列表，实际：{raw_refs!r}")
                refs = []
            else:
                refs = raw_refs
            for ref in refs:
                if not isinstance(ref, str) or not ref.strip():
                    errs.append(f"{eid}: {field} 条目应为非空字符串，实际：{ref!r}")
                elif ref not in ids:
                    errs.append(f"{eid}: {field} 引用不存在的条目：{ref}（悬空引用）")
        sb = e.get("superseded_by")
        if sb is not None and not isinstance(sb, str):
            errs.append(f"{eid}: superseded_by 应为字符串或 null，实际：{sb!r}")
        elif isinstance(sb, str) and sb and sb not in ids:
            errs.append(f"{eid}: superseded_by 引用不存在的条目：{sb}（悬空引用）")
        errs += _active_plan_association_errors(e, repo)
    # 过期 approval（唯一触发，human 拍板）：上游被标 superseded → 本条进阶态失效。
    for e in entries:
        status = e.get("status")
        upstream = e.get("upstream")
        if isinstance(status, str) and status in SCOPE_REQUIRED and isinstance(upstream, list):
            for ref in upstream:
                if not isinstance(ref, str):
                    continue
                up = ids.get(ref)
                if up is not None and up.get("status") == "superseded":
                    errs.append(
                        f"{e.get('id')}: 过期 approval——上游 {ref} 已 superseded，"
                        f"本条 {e.get('status')} 随之失效，需重新走 human gate"
                    )
    return errs


def doc_errors_for_entry(e: dict, repo: Path) -> list[str]:
    errs: list[str] = []
    path = e.get("path")
    if not isinstance(path, str) or not path:
        return errs
    f = repo / path
    if not f.is_file():
        return errs  # registry_errors 已报悬空
    try:
        text = f.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return [f"{path}: 无法读取"]
    status = e.get("status")
    anchor, anchor_error = _parse_status_anchor(text)
    if anchor_error:
        errs.append(f"{path}: {anchor_error}")
    elif anchor is None:
        errs.append(f"{path}: 缺状态锚点行（Status: <enum> · <date> · <ref>）")
    elif anchor != status:
        errs.append(f"{path}: 状态锚点 {anchor} 与注册表 {status} 矛盾（同 commit 对齐两处）")
    if e.get("kind") == "plan" and isinstance(status, str) and status in SCOPE_REQUIRED:
        errs += [f"{path}: {m}（{status} 态必填）" for m in missing_plan_sections(text)]
    if isinstance(status, str) and status in SCOPE_REQUIRED and annotation_conflict(text):
        errs.append(
            f"{path}: Human 批注区仍有 [?]/[改] 未决批注，不能停留在 {status}——先收敛或回 in-review"
        )
    return errs


def kind_path_warnings(entries: list[dict]) -> list[str]:
    """路径不在四类目录内的条目：kind 为自由声明，允许但告警（校验按声明 kind 执行）。"""
    warns = []
    for e in entries:
        kind, path = e.get("kind"), e.get("path")
        if (
            isinstance(path, str)
            and isinstance(kind, str)
            and kind in KINDS
            and doc_kind(path) is None
        ):
            warns.append(
                f"{e.get('id')}: path 不在四类目录（{'、'.join(DOC_DIRS)}）内：{path}——"
                f"kind={kind} 为自由声明，必填段校验按声明 kind 执行"
            )
    return warns


def coverage_errors(entries: list[dict], repo: Path) -> list[str]:
    registered = {e["path"] for e in entries if isinstance(e.get("path"), str)}
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


def _path_identities(
    path_str: str,
    repo: Path,
    *,
    base_dir: Path | None = None,
    follow_final_symlink: bool = True,
) -> tuple[str, ...]:
    """返回 path 的 repo 内词法/解析后身份；两者都保留且绝不靠 basename/suffix 猜测。"""
    p = (path_str or "").strip().strip('"').strip("'")
    if not p:
        return ()
    pp = Path(p)
    try:
        root = repo.resolve()
        base = base_dir if base_dir is not None else root
        base = Path(os.path.abspath(os.path.normpath(os.fspath(base))))
        candidate = pp if pp.is_absolute() else base / pp
        lexical = Path(os.path.abspath(os.path.normpath(os.fspath(candidate))))
    except (ValueError, OSError, RuntimeError):
        return ()

    identities: list[str] = []
    candidates = [lexical]
    try:
        resolved = (
            lexical.resolve(strict=False)
            if follow_final_symlink
            else lexical.parent.resolve(strict=False) / lexical.name
        )
        candidates.append(resolved)
    except (OSError, RuntimeError):
        pass
    for candidate in candidates:
        try:
            rel = candidate.relative_to(root).as_posix()
        except (ValueError, OSError, RuntimeError):
            continue
        if rel not in identities:
            identities.append(rel)
    return tuple(identities)


def _rel_to_repo(path_str: str, repo: Path, *, base_dir: Path | None = None) -> str | None:
    identities = _path_identities(path_str, repo, base_dir=base_dir)
    return identities[0] if identities else None


def _managed_doc_identity(
    path_str: str,
    repo: Path,
    *,
    base_dir: Path | None = None,
    follow_final_symlink: bool = True,
) -> tuple[str, str] | None:
    """返回操作实际触及的受管文档身份；解析后目标优先于词法 alias。"""
    identities = _path_identities(
        path_str,
        repo,
        base_dir=base_dir,
        follow_final_symlink=follow_final_symlink,
    )
    for rel in reversed(identities):
        kind = doc_kind(rel)
        if kind:
            return rel, kind
    return None


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
    by_id = {e["id"]: e for e in entries if isinstance(e.get("id"), str) and e["id"]}
    for e in entries:
        if e.get("path") != rel:
            continue
        upstream = e.get("upstream")
        if not isinstance(upstream, list):
            continue
        for ref in upstream:
            if not isinstance(ref, str):
                continue
            up = by_id.get(ref)
            if up is not None and up.get("status") == "superseded":
                return (
                    f"doc-lifecycle: {rel} 标记 {status} 但其上游 {ref} 已 superseded"
                    f"——approval 已过期，需重新走 human gate。{_ESCAPE_HINT}"
                )
    return None


def _doc_write_reason(rel: str, kind: str, content: str, markers_text: str, repo: Path) -> str | None:
    """对一次「写入后的文档内容」判定进阶态完整性。content=用于状态/段落检查的全文（或联合语料），
    markers_text=用于未决批注检查的文本（apply_patch update 只看新增行，避免误拦）。"""
    status, anchor_error = _parse_status_anchor(content)
    if anchor_error:
        return f"doc-lifecycle: {rel} 的{anchor_error}。{_ESCAPE_HINT}"
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
_SHELL_WRAPPERS = {"builtin", "command", "exec"}
_ENV_FLAGS_WITH_VALUE = {"-u", "--unset", "-C", "--chdir", "-S", "--split-string"}
_GIT_GLOBAL_FLAGS_WITH_VALUE = {
    "-C", "-c", "--config-env", "--exec-path", "--git-dir", "--work-tree",
    "--namespace", "--super-prefix", "--list-cmds", "--attr-source",
}
_SHELL_LITERAL_GLOB_MARKERS = {
    "*": "__DL_LITERAL_STAR__",
    "?": "__DL_LITERAL_QMARK__",
    "[": "__DL_LITERAL_LBRACKET__",
    "]": "__DL_LITERAL_RBRACKET__",
}


def _is_registry_path(
    raw: str,
    repo: Path,
    *,
    base_dir: Path | None = None,
    follow_final_symlink: bool = True,
) -> bool:
    return REGISTRY_REL in _path_identities(
        raw,
        repo,
        base_dir=base_dir,
        follow_final_symlink=follow_final_symlink,
    )


def _strip_command_wrapper_options(args: list[str]) -> list[str]:
    i = 0
    while i < len(args) and args[i] in {"-p", "--"}:
        i += 1
    return args[i:]


def _strip_env_wrapper(args: list[str], cwd: Path) -> tuple[list[str], Path]:
    i = 0
    env_cwd = cwd
    while i < len(args):
        arg = args[i]
        if arg == "--":
            return args[i + 1:], env_cwd
        if re.match(r"^[A-Za-z_]\w*=", arg):
            i += 1
            continue
        if arg in {"-i", "--ignore-environment", "-0", "--null"}:
            i += 1
            continue
        if arg in {"-C", "--chdir"}:
            if i + 1 >= len(args):
                return [], env_cwd
            env_cwd = _lexical_path(args[i + 1], env_cwd)
            i += 2
            continue
        if arg.startswith("--chdir="):
            env_cwd = _lexical_path(arg.split("=", 1)[1], env_cwd)
            i += 1
            continue
        if arg.startswith("-C") and len(arg) > 2:
            env_cwd = _lexical_path(arg[2:], env_cwd)
            i += 1
            continue
        if arg in {"-S", "--split-string"}:
            if i + 1 >= len(args):
                return [], env_cwd
            try:
                args = shlex.split(args[i + 1]) + args[i + 2:]
            except ValueError:
                return [], env_cwd
            i = 0
            continue
        if arg.startswith("--split-string="):
            try:
                args = shlex.split(arg.split("=", 1)[1]) + args[i + 1:]
            except ValueError:
                return [], env_cwd
            i = 0
            continue
        if arg in _ENV_FLAGS_WITH_VALUE:
            if i + 1 >= len(args):
                return [], env_cwd
            i += 2
            continue
        if any(arg.startswith(flag + "=") for flag in _ENV_FLAGS_WITH_VALUE if flag.startswith("--")):
            i += 1
            continue
        break
    return args[i:], env_cwd


def _strip_nice_wrapper(args: list[str]) -> list[str]:
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--":
            return args[i + 1:]
        if arg in {"-n", "--adjustment"}:
            if i + 1 >= len(args):
                return []
            i += 2
            continue
        if (
            arg.startswith("--adjustment=")
            or re.fullmatch(r"-\d+", arg)
            or re.fullmatch(r"-n[+-]?\d+", arg)
        ):
            i += 1
            continue
        if arg.startswith("-"):
            return []  # --help/--version/未知 option：没有可安全识别的子命令
        break
    return args[i:]


def _strip_nohup_wrapper(args: list[str]) -> list[str]:
    if args and args[0] == "--":
        return args[1:]
    if args and args[0].startswith("-"):
        return []
    return args


def _strip_timeout_wrapper(args: list[str]) -> list[str]:
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--":
            i += 1
            break
        if arg in {"-k", "--kill-after", "-s", "--signal"}:
            if i + 1 >= len(args):
                return []
            i += 2
            continue
        if arg in {"--foreground", "--preserve-status", "-v", "--verbose"}:
            i += 1
            continue
        if arg.startswith(("--kill-after=", "--signal=")):
            i += 1
            continue
        break
    if i >= len(args):
        return []
    return args[i + 1:]  # 第一个非 option 是 DURATION


def _unwrap_command(seg: list[str], cwd: Path) -> tuple[str, list[str], Path]:
    """展开常见执行 wrapper，返回实际命令与参数。"""
    remaining = list(seg)
    for _ in range(12):  # wrapper 可嵌套；有界循环避免畸形输入拖住 hook
        while remaining and remaining[0] == "(":
            remaining.pop(0)
        while remaining and re.match(r"^[A-Za-z_]\w*=", remaining[0]):
            remaining.pop(0)
        if not remaining:
            return "", [], cwd
        name = remaining[0].rsplit("/", 1)[-1]
        args = remaining[1:]
        if name in _SHELL_WRAPPERS:
            remaining = _strip_command_wrapper_options(args)
            continue
        if name == "env":
            remaining, cwd = _strip_env_wrapper(args, cwd)
            continue
        if name == "nice":
            remaining = _strip_nice_wrapper(args)
            continue
        if name == "nohup":
            remaining = _strip_nohup_wrapper(args)
            continue
        if name == "timeout":
            remaining = _strip_timeout_wrapper(args)
            continue
        return name, args, cwd
    return "", [], cwd


def _lexical_path(raw: str, cwd: Path) -> Path:
    path = Path(raw)
    candidate = path if path.is_absolute() else cwd / path
    return Path(os.path.abspath(os.path.normpath(os.fspath(candidate))))


def _git_subcommand(args: list[str], cwd: Path) -> tuple[str, list[str], Path]:
    """跳过 git 全局选项并累计 `-C` cwd，返回 subcommand、参数和路径基准。"""
    i = 0
    git_cwd = cwd
    path_base = cwd
    explicit_work_tree = False
    while i < len(args):
        arg = args[i]
        if arg == "--":
            i += 1
            break
        if not arg.startswith("-") or arg == "-":
            return arg, args[i + 1:], path_base
        if arg == "-C":
            if i + 1 >= len(args):
                return "", [], path_base
            git_cwd = _lexical_path(args[i + 1], git_cwd)
            if not explicit_work_tree:
                path_base = git_cwd
            i += 2
            continue
        if arg.startswith("-C") and len(arg) > 2:
            git_cwd = _lexical_path(arg[2:], git_cwd)
            if not explicit_work_tree:
                path_base = git_cwd
            i += 1
            continue
        if arg == "--work-tree":
            if i + 1 >= len(args):
                return "", [], path_base
            path_base = _lexical_path(args[i + 1], git_cwd)
            explicit_work_tree = True
            i += 2
            continue
        if arg.startswith("--work-tree="):
            path_base = _lexical_path(arg.split("=", 1)[1], git_cwd)
            explicit_work_tree = True
            i += 1
            continue
        if arg in _GIT_GLOBAL_FLAGS_WITH_VALUE:
            if i + 1 >= len(args):
                return "", [], path_base
            i += 2
            continue
        if any(arg.startswith(flag + "=") for flag in _GIT_GLOBAL_FLAGS_WITH_VALUE
               if flag.startswith("--")):
            i += 1
            continue
        i += 1  # 无参数全局 flag，如 --literal-pathspecs
    if i < len(args):
        return args[i], args[i + 1:], path_base
    return "", [], path_base


def _cd_target(args: list[str], cwd: Path) -> Path | None:
    remaining = list(args)
    while remaining and remaining[0] in {"-L", "-P", "-e", "-@"}:
        remaining.pop(0)
    if remaining and remaining[0] == "--":
        remaining.pop(0)
    if len(remaining) != 1 or remaining[0] == "-":
        return None
    target = _lexical_path(remaining[0], cwd)
    return target if target.is_dir() else None


def _prepare_shell_source(cmd: str) -> str:
    """标记 shell-literal glob 字符，并把引号外换行变成 `;` 命令边界。"""
    out: list[str] = []
    quote: str | None = None
    i = 0
    while i < len(cmd):
        char = cmd[i]
        if char == "\\" and quote != "'" and i + 1 < len(cmd):
            if cmd[i + 1] == "\n":
                i += 2
                continue
            if cmd[i + 1] in _SHELL_LITERAL_GLOB_MARKERS:
                out.append(_SHELL_LITERAL_GLOB_MARKERS[cmd[i + 1]])
                i += 2
                continue
            out.extend((char, cmd[i + 1]))
            i += 2
            continue
        if char in "'\"":
            quote = None if quote == char else (char if quote is None else quote)
            out.append(char)
        elif quote is not None and char in _SHELL_LITERAL_GLOB_MARKERS:
            out.append(_SHELL_LITERAL_GLOB_MARKERS[char])
        else:
            out.append(";" if char == "\n" and quote is None else char)
        i += 1
    return "".join(out)


def _restore_shell_literals(raw: str) -> str:
    restored = raw
    for literal, marker in _SHELL_LITERAL_GLOB_MARKERS.items():
        restored = restored.replace(marker, literal)
    return restored


def _has_active_shell_glob(raw: str) -> bool:
    return any(ch in raw for ch in "*?[")


def _shell_glob_matches(raw: str, cwd: Path, *, limit: int = 1024) -> tuple[list[str], bool]:
    """按有效 cwd 有界展开真实 shell glob；返回 (matches, 是否因上限截断)。"""
    pattern = Path(raw)
    absolute = pattern if pattern.is_absolute() else cwd / pattern
    matches: list[str] = []
    try:
        for index, match in enumerate(iglob(os.fspath(absolute))):
            if index >= limit:
                return matches, True
            matches.append(match)
    except (OSError, RuntimeError, ValueError):
        return [], False
    return matches, False


def _destructive_redirect_targets(command: list[str]) -> list[str]:
    return [
        command[index + 1]
        for index, token in enumerate(command[:-1])
        if token in {">", ">>", ">|", "<>"}
    ]


def _shell_events(tokens: list[str]) -> list[list[str] | str]:
    """把 shlex token 流拆成 command/control events；只理解本 guard 所需控制符。"""
    events: list[list[str] | str] = []
    command: list[str] = []

    def flush() -> None:
        nonlocal command
        if command:
            events.append(command)
            command = []

    for token in tokens:
        controls: list[str] | None = None
        if token in {"{", "}"}:
            controls = [token]
        elif token and set(token) <= set("();|&"):
            controls = []
            i = 0
            while i < len(token):
                pair = token[i:i + 2]
                if pair in {"&&", "||"}:
                    controls.append(pair)
                    i += 2
                else:
                    controls.append(token[i])
                    i += 1
        if controls is None:
            command.append(token)
            continue
        flush()
        events.extend(controls)
    flush()
    return events


def _git_pathspec_identity(arg: str, repo: Path, cwd: Path) -> tuple[str, Path, set[str]]:
    """抽出本 guard 需要的 git pathspec magic；glob 等语义仍交给 git。"""
    arg = _restore_shell_literals(arg)
    if arg.startswith(":/"):
        return arg[2:], repo.resolve(), {"top"}
    match = re.match(r"^:\(([^)]*)\)(.*)$", arg)
    if not match:
        return arg, cwd, set()
    magic = {part.strip() for part in match.group(1).split(",")}
    return match.group(2), repo.resolve() if "top" in magic else cwd, magic


def _path_covers_registry(
    raw: str,
    repo: Path,
    cwd: Path,
    *,
    follow_final_symlink: bool,
    include_ancestors: bool,
) -> bool:
    if _has_active_shell_glob(raw):
        candidates, truncated = _shell_glob_matches(raw, cwd)
    else:
        candidates, truncated = [_restore_shell_literals(raw)], False
    for candidate in candidates:
        identities = _path_identities(
            candidate, repo, base_dir=cwd, follow_final_symlink=follow_final_symlink
        )
        if any(
            rel == REGISTRY_REL
            or (include_ancestors and REGISTRY_REL.startswith(rel.rstrip("/") + "/"))
            for rel in identities
        ):
            return True
    return truncated  # security guard: expansion cap is uncertainty, so fail closed


def _git_pathspec_covers_registry(
    arg: str, repo: Path, cwd: Path, *, include_ancestors: bool
) -> bool:
    raw, base, magic = _git_pathspec_identity(arg, repo, cwd)
    if "literal" in magic:
        identities = _path_identities(
            raw, repo, base_dir=base, follow_final_symlink=False
        )
        return any(
            rel == REGISTRY_REL
            or (include_ancestors and REGISTRY_REL.startswith(rel.rstrip("/") + "/"))
            for rel in identities
        )
    if not any(ch in raw for ch in "*?["):
        return _path_covers_registry(
            raw,
            repo,
            base,
            follow_final_symlink=False,
            include_ancestors=include_ancestors,
        )
    root = repo.resolve()
    for pattern_base in (base, base.resolve(strict=False)):
        try:
            pattern = _lexical_path(raw, pattern_base).relative_to(root).as_posix()
        except (ValueError, OSError, RuntimeError):
            continue
        if fnmatchcase(REGISTRY_REL, pattern):
            return True
    return False


def _bash_reason(cmd: str, repo: Path) -> str | None:
    """Bash 命令中对注册表的删除/移动（rm/unlink/shred/truncate/mv/git rm）→ 拦。"""
    try:
        protected = re.sub(
            r":\(([A-Za-z0-9_,!^-]+)\)",
            lambda m: f":__DL_LP__{m.group(1)}__DL_RP__",
            _prepare_shell_source(cmd),
        )
        lex = shlex.shlex(protected, posix=True, punctuation_chars=True)
        lex.whitespace_split = True
        toks = [t.replace("__DL_LP__", "(").replace("__DL_RP__", ")") for t in lex]
    except ValueError:
        toks = cmd.split()
    events = _shell_events(toks)
    cwd = repo.resolve()
    subshell_cwds: list[Path] = []
    for index, event in enumerate(events):
        if isinstance(event, str):
            if event == "(":
                subshell_cwds.append(cwd)
            elif event == ")" and subshell_cwds:
                cwd = subshell_cwds.pop()
            continue
        if any(
            _path_covers_registry(
                target,
                repo,
                cwd,
                follow_final_symlink=True,
                include_ancestors=False,
            )
            for target in _destructive_redirect_targets(event)
        ):
            return _REGISTRY_REMOVE_MSG
        name, args, command_cwd = _unwrap_command(event, cwd)
        if name == "cd":
            next_control = events[index + 1] if index + 1 < len(events) else None
            if next_control not in {"|", "&"}:
                cwd = _cd_target(args, cwd) or cwd
            continue
        git_command = name == "git"
        if git_command:
            subcommand, args, command_cwd = _git_subcommand(args, command_cwd)
            name = subcommand.rsplit("/", 1)[-1]
        if name == "cp":
            cp_targets = [arg for arg in args if not arg.startswith("-")]
            if cp_targets and _path_covers_registry(
                cp_targets[-1],
                repo,
                command_cwd,
                follow_final_symlink=True,
                include_ancestors=False,
            ):
                return _REGISTRY_REMOVE_MSG
            continue
        if name not in _DELETIONISH:
            continue
        recursive = name == "rm" and any(
            arg == "--recursive"
            or (arg.startswith("-") and not arg.startswith("--") and "r" in arg.lower())
            for arg in args
        )
        for arg in args:
            if arg.startswith("-"):
                continue
            if git_command:
                touches_registry = _git_pathspec_covers_registry(
                    arg, repo, command_cwd, include_ancestors=recursive
                )
            else:
                touches_registry = _path_covers_registry(
                    arg,
                    repo,
                    command_cwd,
                    follow_final_symlink=(name in {"shred", "truncate"}),
                    include_ancestors=(name == "mv" or recursive),
                )
            if touches_registry:
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
        raw_path = tool_input.get("file_path") or ""
        managed_doc = _managed_doc_identity(raw_path, repo)
        identities = _path_identities(raw_path, repo)
        rel = managed_doc[0] if managed_doc else (identities[0] if identities else None)
        if tool_name == "Write":
            prospective = tool_input.get("content") or ""
        else:
            if rel is None:
                return None
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
        if _is_registry_path(raw_path, repo):
            return _registry_write_reason(prospective, repo)
        if managed_doc:
            rel, kind = managed_doc
            return _doc_write_reason(rel, kind, prospective, prospective, repo)
        return None

    if tool_name == "Bash":
        return _bash_reason(tool_input.get("command") or "", repo)

    if tool_name == "apply_patch":
        patch = tool_input.get("command") or tool_input.get("patch") or ""
        for op in _patch_ops(patch):
            raw_path = op["path"]
            raw_dest = op["move_to"] or raw_path
            follows_final = op["op"] != "delete" and not op["move_to"]
            source_managed = _managed_doc_identity(
                raw_path, repo, follow_final_symlink=follows_final
            )
            dest_managed = _managed_doc_identity(
                raw_dest, repo, follow_final_symlink=follows_final
            )
            source_identities = _path_identities(
                raw_path, repo, follow_final_symlink=follows_final
            )
            rel = source_managed[0] if source_managed else (
                source_identities[0] if source_identities else None
            )
            if rel is None:
                continue
            source_is_registry = _is_registry_path(
                raw_path, repo, follow_final_symlink=follows_final
            )
            dest_is_registry = _is_registry_path(
                raw_dest, repo, follow_final_symlink=follows_final
            )

            if op["op"] == "delete":
                if source_is_registry:
                    return _REGISTRY_REMOVE_MSG
                continue

            if source_is_registry or dest_is_registry:
                if op["op"] == "update" and source_is_registry and not dest_is_registry:
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

            managed_doc = source_managed or dest_managed
            if not managed_doc:
                continue
            managed_rel, kind = managed_doc
            if op["op"] == "add":
                prospective = _added_text(op)
            else:
                current = _read_rel(repo, managed_rel)
                if current is None:
                    continue  # 文件不存在：apply_patch 本身会失败，无需拦
                prospective = _reconstruct_update(current, op["lines"])
                if prospective is None:
                    return (
                        f"doc-lifecycle: 无法可靠重建对 {managed_rel} 的 apply_patch Update 结果"
                        f"（hunk 上下文与当前文件对不上/语法不明）——保守拦截，"
                        f"请改用 Edit 工具或拆成更小的 patch。{_ESCAPE_HINT}"
                    )
            reason = _doc_write_reason(managed_rel, kind, prospective, prospective, repo)
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
        f"builtin command rm {REGISTRY_REL}",
        f"env rm {REGISTRY_REL}",
        "rm memory/../memory/doc-lifecycle.yaml",
        "cd memory && rm doc-lifecycle.yaml",
        "(cd memory && rm doc-lifecycle.yaml)",
        "git -C memory rm doc-lifecycle.yaml",
        "git --work-tree memory rm doc-lifecycle.yaml",
        "git --work-tree=memory rm doc-lifecycle.yaml",
        f"nice -n 10 rm {REGISTRY_REL}",
        f"nice -n10 rm {REGISTRY_REL}",
        f"nohup rm {REGISTRY_REL}",
        "(cd /tmp && true); rm memory/doc-lifecycle.yaml",
        "{ cd memory && rm doc-lifecycle.yaml; }",
        "cd memory || exit 1; rm doc-lifecycle.yaml",
        "env --chdir=memory rm doc-lifecycle.yaml",
        "env -C memory rm doc-lifecycle.yaml",
        "env -Cmemory rm doc-lifecycle.yaml",
        "git rm :(top)memory/doc-lifecycle.yaml",
        "git rm :/memory/doc-lifecycle.yaml",
        "git rm :(literal)memory/doc-lifecycle.yaml",
        "git rm -- 'memory/doc-lifecycle.*'",
        "git rm -- ':(glob)memory/doc-lifecycle.y*'",
        "rm -rf memory",
        "mv memory /tmp/memory-away",
        "git rm -r memory",
        f"shred {REGISTRY_REL}",
        "rm memory/doc-lifecycle.y*",
        "cd memory\nrm doc-lifecycle.yaml",
        f": > {REGISTRY_REL}",
        "cd memory && : > doc-lifecycle.yaml",
        f"cp /dev/null {REGISTRY_REL}",
        f'env -S "rm {REGISTRY_REL}"',
        f'env --split-string="rm {REGISTRY_REL}"',
        f"timeout 5s rm {REGISTRY_REL}",
    ):
        check(
            f"hook 拦 Bash wrapper/global-option 绕过：{wrapped.split()[0:3]}",
            pretooluse_reason("Bash", {"command": wrapped}, root) is not None,
        )
    for literal_glob in (
        "rm 'memory/doc-lifecycle.y*'",
        r"rm memory/doc-lifecycle.y\*",
        "cd memory && command rm 'doc-lifecycle.y*'",
        "nice rm 'memory/doc-lifecycle.y*'",
    ):
        check(
            f"hook 放行 shell-literal glob：{literal_glob}",
            pretooluse_reason("Bash", {"command": literal_glob}, root) is None,
        )
    check(
        "hook 放行 root nonrecursive rm *（* 不跨 slash）",
        pretooluse_reason("Bash", {"command": "rm *"}, root) is None,
    )
    check(
        "hook 拦 root recursive rm -rf *（展开含 registry ancestor）",
        pretooluse_reason("Bash", {"command": "rm -rf *"}, root) is not None,
    )
    check(
        "hook 拦 cwd + wrapper active glob 命中 registry",
        pretooluse_reason(
            "Bash", {"command": "cd memory && nice rm doc-lifecycle.y*"}, root
        ) is not None,
    )
    traversal_del = (
        "*** Begin Patch\n*** Delete File: memory/../memory/doc-lifecycle.yaml\n*** End Patch"
    )
    check(
        "hook 拦 apply_patch 路径归一化绕过",
        pretooluse_reason("apply_patch", {"command": traversal_del}, root) is not None,
    )
    alias_rel = "memory/registry-alias.yaml"
    (root / alias_rel).symlink_to("doc-lifecycle.yaml")
    alias_del = f"*** Begin Patch\n*** Delete File: {alias_rel}\n*** End Patch"
    check(
        "hook 拦 Write symlink alias 清空注册表",
        pretooluse_reason(
            "Write", {"file_path": str(root / alias_rel), "content": "docs: []\n"}, root
        ) is not None,
    )
    check("hook 放行 apply_patch Delete final symlink alias",
          pretooluse_reason("apply_patch", {"command": alias_del}, root) is None)
    check("hook 放行 Bash rm final symlink alias",
          pretooluse_reason("Bash", {"command": f"rm {alias_rel}"}, root) is None)
    check("hook 放行 Bash mv final symlink alias",
          pretooluse_reason("Bash", {"command": f"mv {alias_rel} /tmp/alias"}, root) is None)
    check("hook 拦 Bash truncate final symlink alias",
          pretooluse_reason("Bash", {"command": f"truncate -s 0 {alias_rel}"}, root) is not None)
    check("hook 拦 Bash shred final symlink alias",
          pretooluse_reason("Bash", {"command": f"shred {alias_rel}"}, root) is not None)
    check("hook 拦重定向覆盖 final symlink alias",
          pretooluse_reason("Bash", {"command": f": > {alias_rel}"}, root) is not None)
    check("hook 拦 cp 覆盖 final symlink alias",
          pretooluse_reason("Bash", {"command": f"cp /dev/null {alias_rel}"}, root) is not None)
    check("hook 放行 Bash rm -rf final symlink alias",
          pretooluse_reason("Bash", {"command": f"rm -rf {alias_rel}"}, root) is None)
    alias_update = (
        f"*** Begin Patch\n*** Update File: {alias_rel}\n@@\n"
        "-docs:\n+docs: []\n*** End Patch"
    )
    check("hook 拦 apply_patch Update final symlink alias",
          pretooluse_reason("apply_patch", {"command": alias_update}, root) is not None)
    check(
        "hook 拦 Edit final symlink alias",
        pretooluse_reason(
            "Edit", {"file_path": str(root / alias_rel), "old_string": "docs:",
                     "new_string": "docs: []\nlegacy:"}, root
        ) is not None,
    )
    plan_alias_rel = "plan-alias.md"
    (root / plan_alias_rel).symlink_to("plans/demo.zh.md")
    check(
        "hook 拦 Write managed plan final alias 的违规 target content",
        pretooluse_reason(
            "Write",
            {"file_path": plan_alias_rel,
             "content": "# alias\n\nStatus: approved · 2026-07-13 · synthetic\n"},
            root,
        ) is not None,
    )
    check(
        "hook 拦 Edit managed plan final alias 的违规 target content",
        pretooluse_reason(
            "Edit",
            {"file_path": plan_alias_rel, "old_string": "- plans/demo.zh.md",
             "new_string": "- [ ] TODO"},
            root,
        ) is not None,
    )
    plan_alias_update = (
        f"*** Begin Patch\n*** Update File: {plan_alias_rel}\n@@\n"
        "-- plans/demo.zh.md\n+- [ ] TODO\n*** End Patch"
    )
    check(
        "hook 拦 apply_patch Update managed plan final alias 的违规 target content",
        pretooluse_reason("apply_patch", {"command": plan_alias_update}, root) is not None,
    )
    plan_alias_delete = (
        f"*** Begin Patch\n*** Delete File: {plan_alias_rel}\n*** End Patch"
    )
    check(
        "hook 放行 apply_patch Delete managed plan final alias",
        pretooluse_reason("apply_patch", {"command": plan_alias_delete}, root) is None,
    )
    dir_alias = root / "memory-alias"
    dir_alias.symlink_to(root / "memory", target_is_directory=True)
    check("hook 拦 Bash rm intermediate-dir symlink 下的 registry",
          pretooluse_reason("Bash", {"command": "rm memory-alias/doc-lifecycle.yaml"}, root)
          is not None)
    check(
        "hook 拦 apply_patch Delete intermediate-dir symlink 下的 registry",
        pretooluse_reason(
            "apply_patch",
            {"command": "*** Begin Patch\n*** Delete File: memory-alias/doc-lifecycle.yaml\n*** End Patch"},
            root,
        ) is not None,
    )
    outside_same_suffix = "/tmp/not-this-repo/memory/doc-lifecycle.yaml"
    check(
        "hook 放行 Write repo 外同 suffix 路径",
        pretooluse_reason(
            "Write", {"file_path": outside_same_suffix, "content": "docs: []\n"}, root
        ) is None,
    )
    check(
        "hook 放行 apply_patch Delete repo 外同 suffix 路径",
        pretooluse_reason(
            "apply_patch",
            {"command": f"*** Begin Patch\n*** Delete File: {outside_same_suffix}\n*** End Patch"},
            root,
        ) is None,
    )
    for harmless in (
        f"rm {outside_same_suffix}",
        "cd /tmp && rm not-this-repo/memory/doc-lifecycle.yaml",
        "git -C /tmp rm not-this-repo/memory/doc-lifecycle.yaml",
        "git --work-tree /tmp rm not-this-repo/memory/doc-lifecycle.yaml",
        "git --work-tree=/tmp rm not-this-repo/memory/doc-lifecycle.yaml",
        "env --chdir=/tmp rm not-this-repo/memory/doc-lifecycle.yaml",
        "env -C /tmp rm not-this-repo/memory/doc-lifecycle.yaml",
        "env -C/tmp rm not-this-repo/memory/doc-lifecycle.yaml",
        "git rm -- 'memory/not-doc-lifecycle.*'",
        "git rm -- ':(glob)memory/not-doc-lifecycle.y*'",
        "rm -rf /tmp/not-this-repo/memory",
        "mv /tmp/not-this-repo/memory /tmp/memory-away",
        "rm /tmp/not-this-repo/memory/doc-lifecycle.y*",
        ": > /tmp/not-this-repo/memory/doc-lifecycle.yaml",
        "cp /dev/null /tmp/not-this-repo/memory/doc-lifecycle.yaml",
        f'env -S "echo {REGISTRY_REL}"',
        f'env --split-string="echo {REGISTRY_REL}"',
        f"timeout 5s echo {REGISTRY_REL}",
        f"echo {REGISTRY_REL}",
        f"nice -n 10 echo {REGISTRY_REL}",
        f"nice -n10 echo {REGISTRY_REL}",
        f"nohup cat {REGISTRY_REL}",
    ):
        check(
            f"hook 不误拦 repo 外/只读 control：{harmless.split()[0:4]}",
            pretooluse_reason("Bash", {"command": harmless}, root) is None,
        )
    with tempfile.TemporaryDirectory() as outside_dir:
        outside_alias = Path(outside_dir) / "registry-alias.yaml"
        outside_alias.symlink_to(root / REGISTRY_REL)
        check(
            "hook 拦 Write repo 外 final symlink alias",
            pretooluse_reason(
                "Write", {"file_path": str(outside_alias), "content": "docs: []\n"}, root
            ) is not None,
        )
        check("hook 放行 Bash rm repo 外 final symlink alias",
              pretooluse_reason("Bash", {"command": f"rm {outside_alias}"}, root) is None)
        check("hook 拦 Bash shred repo 外 final symlink alias",
              pretooluse_reason("Bash", {"command": f"shred {outside_alias}"}, root) is not None)
        outside_del = (
            f"*** Begin Patch\n*** Delete File: {outside_alias}\n*** End Patch"
        )
        check("hook 放行 apply_patch Delete repo 外 final symlink alias",
              pretooluse_reason("apply_patch", {"command": outside_del}, root) is None)
    with tempfile.NamedTemporaryFile() as outside_registry:
        (root / REGISTRY_REL).unlink()
        (root / REGISTRY_REL).symlink_to(outside_registry.name)
        check(
            "registry 即使 symlink 到 repo 外仍按词法路径受保护",
            pretooluse_reason("apply_patch", {"command": del_patch}, root) is not None,
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

    # 19. fresh review MAJOR-1：受管文档存在时，空文件或 docs: [] 不得静默关闭注册表。
    for label, empty_registry in (("空文件", ""), ("docs: []", "docs: []\n")):
        td, root = fresh({"plans/demo.zh.md": _OK_PLAN, REGISTRY_REL: empty_registry})
        errs, _ = validate_repo(root)
        check(f"{label} 注册表被 validator 报错", any("不能为空" in e for e in errs))
        check(
            f"hook 拦 Write {label} 注册表",
            pretooluse_reason(
                "Write", {"file_path": str(root / REGISTRY_REL), "content": empty_registry}, root
            ) is not None,
        )
        td.cleanup()

    # 20. fresh review MAJOR-2：状态锚点必须完整，日期真实且 ref 非占位。
    bad_anchors = (
        ("仅状态", "Status: approved", "格式非法"),
        ("draft 仅状态", "Status: draft", "格式非法"),
        ("非法日期", "Status: approved · 2026-02-30 · human 批准", "日期非法"),
        ("占位 ref", "Status: approved · 2026-07-12 · TODO", "ref"),
        ("占位 ref 前缀", "Status: approved · 2026-07-12 · TODO: replace", "ref"),
        ("占位 ref 方括号", "Status: approved · 2026-07-12 · [TODO]", "ref"),
        ("占位 ref N/A 前缀", "Status: approved · 2026-07-12 · N/A pending", "ref"),
        ("占位 ref 列表前缀", "Status: approved · 2026-07-12 · - TODO", "ref"),
    )
    for label, bad_anchor, needle in bad_anchors:
        malformed = _OK_PLAN.replace(
            "Status: approved · 2026-07-12 · human 批准（demo）", bad_anchor
        )
        td, root = fresh({"plans/demo.zh.md": malformed, REGISTRY_REL: _OK_REGISTRY})
        errs, _ = validate_repo(root)
        check(f"{label}锚点被 validator 报错", any(needle in e for e in errs))
        check(
            f"hook 拦 Write {label}锚点",
            pretooluse_reason(
                "Write", {"file_path": str(root / "plans/demo.zh.md"), "content": malformed}, root
            ) is not None,
        )
        td.cleanup()

    prose_ref_plan = _OK_PLAN.replace(
        "human 批准（demo）", "review completed after checking TODO handling"
    )
    td, root = fresh({"plans/demo.zh.md": prose_ref_plan, REGISTRY_REL: _OK_REGISTRY})
    errs, _ = validate_repo(root)
    check("ref prose 中间含 TODO 不误判", errs == [])
    check(
        "hook 放行 ref prose 中间含 TODO",
        pretooluse_reason(
            "Write", {"file_path": str(root / "plans/demo.zh.md"), "content": prose_ref_plan}, root
        ) is None,
    )
    td.cleanup()
    for prose in (
        "None of the risks remain; review approved",
        "TODO detector regression verified",
        "TBD detector regression verified",
    ):
        prose_plan = _OK_PLAN.replace("human 批准（demo）", prose)
        td, root = fresh({"plans/demo.zh.md": prose_plan, REGISTRY_REL: _OK_REGISTRY})
        errs, _ = validate_repo(root)
        check(f"合法 evidence prose 开头不误判：{prose.split()[0]}", errs == [])
        td.cleanup()

    for association in ("todo/fix-parser", "none-feature", "null-safety"):
        check(
            f"合法 association 名不误判：{association}",
            not _is_association_missing_or_placeholder(association),
        )

    # 21. fresh review MAJOR-3a：进阶态 approval 的常见占位值一律拒绝。
    scalar_placeholders = (
        "TODO", "TBD", "N/A", "-", "TODO: replace", "[TODO]", "N/A pending", "- TODO",
        "TBD pending",
    )
    for placeholder in scalar_placeholders:
        placeholder_reg = _OK_REGISTRY.replace(
            'approval: "human 批准（demo）"', f'approval: "{placeholder}"'
        )
        td, root = fresh({"plans/demo.zh.md": _OK_PLAN, REGISTRY_REL: placeholder_reg})
        errs, _ = validate_repo(root)
        check(
            f"approval={placeholder} 被 validator 报错",
            any("approval 证据缺失/占位" in e for e in errs),
        )
        check(
            f"hook 拦 approval={placeholder} 注册表写入",
            pretooluse_reason(
                "Write", {"file_path": str(root / REGISTRY_REL), "content": placeholder_reg}, root
            ) is not None,
        )
        td.cleanup()

    typed_yaml_values = (
        ("list", "[]"), ("map", "{}"), ("bool", "false"), ("int", "0"),
        ("yes", "yes"), ("no", "no"), ("on", "on"), ("off", "off"),
        ("float", "1.0"), ("hex", "0x10"), ("date", "2026-07-13"), ("inf", ".inf"),
        ("binary", "0b1010"), ("datetime", "2026-07-13T12:34:56Z"),
        ("sexagesimal", "12:34:56"),
        ("underscore-int", "1_000"), ("null-inline-comment", "null # pending"),
    )
    for label, yaml_value in typed_yaml_values:
        non_scalar_reg = _OK_REGISTRY.replace(
            'approval: "human 批准（demo）"', f"approval: {yaml_value}"
        )
        td, root = fresh({"plans/demo.zh.md": _OK_PLAN, REGISTRY_REL: non_scalar_reg})
        errs, _ = validate_repo(root)
        check(
            f"approval 非 string {label} 被 validator 报错",
            any("approval 证据缺失/占位" in e for e in errs),
        )
        check(
            f"hook 拦 approval 非 string {label}",
            pretooluse_reason(
                "Write", {"file_path": str(root / REGISTRY_REL), "content": non_scalar_reg}, root
            ) is not None,
        )
        restricted_entries, restricted_errors = _parse_restricted(non_scalar_reg)
        check(
            f"受限 parser 保留 approval {label} 的非 string 类型",
            restricted_errors == []
            and bool(restricted_entries)
            and not isinstance(restricted_entries[0].get("approval"), str),
        )
        td.cleanup()

    # Exact-head final review: fallback must match PyYAML's case-insensitive nulls while quoted
    # values stay strings; malformed non-scalar registry fields must fail closed, never raise.
    for raw_null in ("null", "Null", "NULL", "~"):
        check(f"受限 parser 将 {raw_null!r} 解析为 null", _scalar(raw_null) is None)
    for quoted_null in ('"Null"', "'NULL'"):
        check(
            f"受限 parser 保留 quoted null {quoted_null}",
            isinstance(_scalar(quoted_null), str),
        )

    malformed_fields = (
        ("id-list", "id: plan-demo", "id: [plan-demo]", "id 应为非空字符串"),
        ("path-list", "path: plans/demo.zh.md", "path: [plans/demo.zh.md]", "path 应为非空字符串"),
        ("kind-list", "kind: plan", "kind: [plan]", "kind 应为字符串"),
        ("status-list", "status: approved", "status: [approved]", "status 应为字符串"),
        ("upstream-map", "upstream: []", "upstream: {bad: ref}", "upstream 应为字符串列表"),
    )
    for label, old, new, needle in malformed_fields:
        malformed_registry = _OK_REGISTRY.replace(old, new, 1)
        td, root = fresh({"plans/demo.zh.md": _OK_PLAN, REGISTRY_REL: malformed_registry})
        entries, perr = parse_registry_text(malformed_registry)
        try:
            typed_errors = registry_errors(entries, root) if not perr else perr
        except Exception as exc:  # noqa: BLE001  regression assertion: never fail open via TypeError
            typed_errors = [f"unexpected exception: {type(exc).__name__}: {exc}"]
        check(f"非标量 registry {label} 返回结构化错误", any(needle in e for e in typed_errors))
        check(
            f"hook 拦非标量 registry {label}",
            pretooluse_reason(
                "Write", {"file_path": str(root / REGISTRY_REL), "content": malformed_registry}, root
            ) is not None,
        )
        restricted_entries, restricted_perr = _parse_restricted(malformed_registry)
        try:
            restricted_errors = (
                registry_errors(restricted_entries, root) if not restricted_perr else restricted_perr
            )
        except Exception as exc:  # noqa: BLE001
            restricted_errors = [f"unexpected exception: {type(exc).__name__}: {exc}"]
        check(
            f"受限 parser 非标量 registry {label} 同样拒绝",
            any(needle in e for e in restricted_errors),
        )
        td.cleanup()

    for quoted_value in (
        "yes", "no", "on", "off", "1.0", "0x10", "2026-07-13", ".inf",
        "0b1010", "2026-07-13T12:34:56Z", "12:34:56",
        "1_000",
    ):
        quoted_reg = _OK_REGISTRY.replace(
            'approval: "human 批准（demo）"', f'approval: "{quoted_value}"'
        )
        td, root = fresh({"plans/demo.zh.md": _OK_PLAN, REGISTRY_REL: quoted_reg})
        entries, perr = _parse_restricted(quoted_reg)
        errs, _ = validate_repo(root)
        check(
            f"quoted approval={quoted_value} 保持 string 并通过",
            perr == [] and isinstance(entries[0].get("approval"), str) and errs == [],
        )
        td.cleanup()

    exponent_string_reg = _OK_REGISTRY.replace(
        'approval: "human 批准（demo）"', "approval: 1.2e3"
    )
    td, root = fresh({"plans/demo.zh.md": _OK_PLAN, REGISTRY_REL: exponent_string_reg})
    entries, perr = _parse_restricted(exponent_string_reg)
    errs, _ = validate_repo(root)
    check(
        "unquoted approval=1.2e3 与 PyYAML 一致保持 string",
        perr == [] and entries[0].get("approval") == "1.2e3" and errs == [],
    )
    td.cleanup()

    quoted_hash_reg = _OK_REGISTRY.replace(
        'approval: "human 批准（demo）"', 'approval: "commit #123 verified"'
    )
    td, root = fresh({"plans/demo.zh.md": _OK_PLAN, REGISTRY_REL: quoted_hash_reg})
    entries, perr = _parse_restricted(quoted_hash_reg)
    errs, _ = validate_repo(root)
    check(
        "quoted approval 内 # 保持正文而非 inline comment",
        perr == [] and entries[0].get("approval") == "commit #123 verified" and errs == [],
    )
    td.cleanup()

    prose_approval_reg = _OK_REGISTRY.replace(
        'approval: "human 批准（demo）"',
        'approval: "review completed after checking TODO handling"',
    )
    td, root = fresh({"plans/demo.zh.md": _OK_PLAN, REGISTRY_REL: prose_approval_reg})
    errs, _ = validate_repo(root)
    check("approval prose 中间含 TODO 不误判", errs == [])
    check(
        "hook 放行 approval prose 中间含 TODO",
        pretooluse_reason(
            "Write", {"file_path": str(root / REGISTRY_REL), "content": prose_approval_reg}, root
        ) is None,
    )
    td.cleanup()

    # 22. fresh review MAJOR-3b：剥掉列表/checkbox 前缀后，段落仅余占位值仍视为空。
    placeholder_sections = (
        "- TODO", "* TBD", "+ N/A", "-", "- [ ] TODO", "1. TBD",
        "- - TODO", "- [ ] [TODO]", "```\n```", "```text\n```", "``", "<code></code>",
        "```text\nTODO\n```", "### TODO", "---",
        "> TODO", "> [ ] TODO", "[TODO](#replace)",
        "| |\n| --- |",
    )
    for placeholder_line in placeholder_sections:
        placeholder_plan = _OK_PLAN.replace("- plans/demo.zh.md", placeholder_line)
        td, root = fresh({"plans/demo.zh.md": placeholder_plan, REGISTRY_REL: _OK_REGISTRY})
        errs, _ = validate_repo(root)
        check(
            f"Allowed paths={placeholder_line!r} 被 validator 报错",
            any("Allowed paths" in e for e in errs),
        )
        check(
            f"hook 拦 Allowed paths={placeholder_line!r}",
            pretooluse_reason(
                "Write", {"file_path": str(root / "plans/demo.zh.md"), "content": placeholder_plan}, root
            ) is not None,
        )
        td.cleanup()

    for real_line in (
        "- prose documents how the TODO detector was verified",
        "```bash\npython scripts/check-doc-lifecycle.py\n```",
        "- `python scripts/check-doc-lifecycle.py`",
        "> approved scope path",
        "[implementation](#section)",
        "| Path |\n| --- |\n| plans/demo.zh.md |",
    ):
        real_plan = _OK_PLAN.replace("- plans/demo.zh.md", real_line)
        td, root = fresh({"plans/demo.zh.md": real_plan, REGISTRY_REL: _OK_REGISTRY})
        errs, _ = validate_repo(root)
        check(f"合法 prose/code section 不误判：{real_line.splitlines()[0]!r}", errs == [])
        check(
            f"hook 放行合法 prose/code section：{real_line.splitlines()[0]!r}",
            pretooluse_reason(
                "Write", {"file_path": str(root / "plans/demo.zh.md"), "content": real_plan}, root
            ) is None,
        )
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
