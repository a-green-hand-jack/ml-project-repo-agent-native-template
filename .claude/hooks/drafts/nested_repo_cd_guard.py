#!/usr/bin/env python3
"""DRAFT hook — 未启用，不在 `.claude/settings.json` 里注册。等 human review 后再决定是否
移入 `.claude/hooks/` 并接线。见本文件末尾的「拟接线片段」与「待 human 决定项」。

## 触发的模式（单一触发）

一条 Bash 命令里出现**裸的（非子 shell）`cd <path>`**，且这条命令跑完之后 shell 会停留在
一个属于**另一个独立 git 仓库**的目录里——不是本仓库的另一个 worktree，是真正独立的仓库
（比如 vendor 进 `lab/code/external/` 的第三方 repo）。

真实事故：`lab/traces/human-cc/2026-07-09/hook-cwd-drift-stuck-recovery/trace.md`。
`git clone` 第三方仓库到 `lab/code/external/ELF` 后，用顶层命令
`cd lab/code/external/ELF && ...`（非 subshell）跑 smoke test，cwd 漂移并跨工具调用持续存在；
下一条 Bash 调用触发的 hook 因为用了裸相对路径而找不到自己，整个工具调用被拦，
`cd` 回仓库根的命令本身也被同一个坏掉的 hook 挡住——自锁，只能靠 ExitWorktree/EnterWorktree
脱困（这两个工具不走这条 hook）。

现有三个 hook 命令已经用 `$CLAUDE_PROJECT_DIR` 锚定绝对路径修过这个具体 wedge（commit
`6fed240`）。但那只堵住了"已有 hook 因裸相对路径而失效"这一种后果。cd 进嵌套仓库这个**动作
本身**没有被治理：
1. 回归风险——以后新增的 hook / script / statusline 命令只要有一个又写成裸相对路径，
   同样的自锁就会重演。
2. 更隐蔽的风险——`pre_tool_guard.py` 的 `_current_branch()` 直接 `subprocess.run(["git",
   "branch", "--show-current"])`，不带 `cwd=`，天然继承调用它的进程的 cwd。如果 cwd 已经
   漂移进嵌套仓库，这个函数读到的就是**嵌套仓库的分支**，不是本仓库的；同理，任何后续
   `git status` / `git add` / `git commit` / `git push` 也会不声不响地作用在嵌套仓库上，
   而不是 agent 以为自己在操作的这个仓库。目录名不显眼时，人和 agent 都不容易第一时间
   注意到。

## 为什么是「提醒」而不是「拦截」（对齐 `.agent/action-boundary.md` 的三档模型）

`action-boundary.md` 的设计原则是"把绝对红线钉进 hook 地板，只把'有人在就确认'留在 ask"。
`cd` 本身**没有副作用**——它不是 deny 清单上的任何一类（不删数据、不提权、不远程执行、不写
受保护路径、不 push main），而且题目本身就点明"vendor 第三方仓库后 cd 进去测试是正常操作"。
把一个无副作用的目录切换动作硬拦下来，既超出了 hook 地板该管的"红线"范围，也不是这次
hook-maker 任务被允许做的事（"绝不产出会执行高副作用动作的 hook"——反过来，`cd` 也不该被
当成高副作用动作来一刀切挡住）。

同时它也不完全等同于 `action-boundary.md` 里现有的 ask 档条目（`git checkout/reset/rebase/
merge` 等）——那些都是**动作本身**有外部副作用、需要人签字。这里的风险是**下游、潜伏的**：
cwd 漂移期间后续命令可能悄悄作用错仓库，或者未来某个新 hook 又踩到裸相对路径的坑。这种
"当下不确认，但值得让 agent 当场注意到"的情况，更贴近本仓库里 `pre_compact_memory_check.py`
已经在用的模式：**advisory，只提醒，永远不阻断**（`exit 0`，消息写 stderr，会展示给
Claude/acting agent，不强制人工确认）。所以本 draft 默认选这一档，而不是发 `permissionDecision:
"ask"`（那需要人工确认弹窗，代价更高，且其在 PreToolUse+Bash+持久 shell 这个组合下的确切
运行时语义本 draft 未做独立验证——见文末"待 human 决定项"）。

如果 human review 认为下游风险（git 操作悄悄指错仓库）足够严重、值得强到"需要人工确认"，
可以把本文件的输出从"仅 print 到 stderr"升级成 `hookSpecificOutput.permissionDecision =
"ask"`（结构可参考 `pre_tool_guard.py._block()`，把 `permissionDecision` 从 `"deny"` 换成
`"ask"`，`exit 0` 而非 `exit 2`）——但这是一次刻意留给 human 的选择，本 draft 不代为决定。

## worktree 感知（避免误报）

本 repo 大量使用 git worktree（本 session 自己就跑在 `.claude/worktrees/...` 里）。同一个
仓库的不同 worktree 各有自己的 `git rev-parse --show-toplevel`，但共享同一个
`git rev-parse --git-common-dir`。所以本 hook **比较 common-dir 而不是 toplevel**：
在同一仓库的 worktree 之间 cd 不会被误判成"进了别的仓库"；只有 common-dir 真正不同
（或者目标目录根本不在任何 git 仓库里）才提醒。

## 失败行为

任何解析失败 / `git` 不可用 / 目标路径不存在 / 拿不到本仓库自己的 common-dir → 一律静默放行
（`exit 0`，不打印）。这是刻意的：本 hook 的存在理由之一就是"一个写死裸路径的 hook 曾经把
session 自锁过"，它自己绝不能成为新的自锁点。

## 局限（best-effort，非完整 shell 语法解析）

- 只识别 `(...)` / `$(...)` / 反引号 这几种会创建子 shell 的写法；不识别 `cd` 别名、
  `pushd`/`popd`、函数包装等。
- `cd -`（回到 `$OLDPWD`）无法在 hook 里得知 `$OLDPWD`，保守当作"cwd 不变"处理（可能漏报）。
- 依赖 `git` 二进制在 PATH 上；容器/沙箱里没有 git 时会静默放行（见"失败行为"）。

## 拟接线片段（本 draft 不会自己改 `.claude/settings.json`）

若 review 通过：把本文件从 `.claude/hooks/drafts/` 挪到 `.claude/hooks/nested_repo_cd_guard.py`，
在 `.claude/settings.json` 的 `hooks.PreToolUse` 数组里加一条新 entry（与现有
`pre_tool_guard.py` 那条并列，matcher 只需要 `"Bash"`），并在 `.claude/hooks/README.md` 的
表格里补一行：

```json
{
  "matcher": "Bash",
  "hooks": [
    {
      "type": "command",
      "command": "python3 \"$CLAUDE_PROJECT_DIR/.claude/hooks/nested_repo_cd_guard.py\""
    }
  ]
}
```

**务必**保持 `$CLAUDE_PROJECT_DIR` 锚定的绝对路径——写成裸相对路径就是重演本 hook 本身
想要防的那个事故（见文件头 trace 引用）。

协议：Claude Code 通过 stdin 传 JSON（`tool_name` / `tool_input`）；本 hook 永远 `exit 0`。
无第三方依赖。
"""
import json
import os
import re
import shlex
import subprocess
import sys

_ENV_ASSIGN = re.compile(r"^[A-Za-z_]\w*=")


def _project_root() -> str:
    """本仓库（或本 worktree）根目录。优先信 `$CLAUDE_PROJECT_DIR`（已由 6fed240 验证在
    hook 子进程里存在）；缺失时从本文件向上找最近的 `.git` 条目兜底，不依赖本文件的具体
    嵌套深度（这样 draft 挪出 `drafts/` 目录后仍然算得对）。"""
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    if env:
        return os.path.realpath(env)
    cur = os.path.dirname(os.path.realpath(__file__))
    while True:
        if os.path.exists(os.path.join(cur, ".git")):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            return cur  # 找不到就交给下游的 git 调用去失败/放行
        cur = parent


def _git_common_dir(path: str, timeout: float = 3.0) -> str | None:
    """`git -C <path> rev-parse --git-common-dir`，规范化为绝对路径。任何失败（非仓库、
    git 不存在、超时、path 不存在）一律返回 None，调用方按"未知→放行"处理。

    用 `--git-common-dir` 而不是 `--show-toplevel`：同一仓库的不同 worktree 共享同一个
    common dir，这样在本仓库的 worktree 之间 cd 不会被误判成"进了别的仓库"。
    """
    try:
        if not os.path.isdir(path):
            return None
        out = subprocess.run(
            ["git", "-C", path, "rev-parse", "--git-common-dir"],
            capture_output=True, text=True, timeout=timeout,
        )
        if out.returncode != 0:
            return None
        raw = out.stdout.strip()
        if not raw:
            return None
        if not os.path.isabs(raw):
            raw = os.path.join(path, raw)
        return os.path.realpath(raw)
    except Exception:  # noqa: BLE001  advisory hook：保守放行
        return None


def _mask_non_top_level(raw: str) -> str:
    """把子 shell（`(...)`、`$(...)`）与反引号命令替换成等长空白，只留下"会影响当前
    persistent shell cwd"的顶层文本。引号内的字面量在深度 0 时保留（供后续 shlex 正确切
    词），深度 > 0 时一并抹掉。不做完整 shell 语法解析——够用即可，其余情况一律保守放行
    （见 main() 的 try/except）。"""
    out: list[str] = []
    i, n = 0, len(raw)
    depth = 0
    in_backtick = False
    while i < n:
        c = raw[i]
        if in_backtick:
            out.append(" ")
            if c == "`":
                in_backtick = False
            i += 1
            continue
        if c == "`":
            in_backtick = True
            out.append(" ")
            i += 1
            continue
        if c in ("'", '"'):
            quote = c
            j = i + 1
            while j < n and raw[j] != quote:
                if quote == '"' and raw[j] == "\\":
                    j += 1
                j += 1
            j = min(j + 1, n)
            span = raw[i:j]
            out.append(span if depth == 0 else (" " * len(span)))
            i = j
            continue
        if c == "(":
            depth += 1
            out.append(" ")
            i += 1
            continue
        if c == ")":
            depth = max(0, depth - 1)
            out.append(" ")
            i += 1
            continue
        out.append(c if depth == 0 else " ")
        i += 1
    return "".join(out)


def _toplevel_simple_commands(masked: str) -> list[list[str]]:
    """把已 mask 过的串切成若干顶层简单命令的 token 列表（按 `;`/`&`/`|`/`<`/`>` 分段；
    `(`/`)` 已在 mask 阶段抹成空白，不会再出现）。解析失败回退到空白分割（保守）。"""
    try:
        lex = shlex.shlex(masked, posix=True, punctuation_chars=True)
        lex.whitespace_split = True
        toks = list(lex)
    except ValueError:
        toks = masked.split()
    cmds: list[list[str]] = []
    cur: list[str] = []
    for t in toks:
        if t and set(t) <= set(";|&<>"):
            if cur:
                cmds.append(cur)
                cur = []
        else:
            cur.append(t)
    if cur:
        cmds.append(cur)
    return cmds


def _cd_targets(raw_cmd: str) -> list[str]:
    """按左到右顺序返回命令里所有顶层（非子 shell）`cd` 的目标参数（未解析成路径）。"""
    masked = _mask_non_top_level(raw_cmd)
    targets: list[str] = []
    for tokens in _toplevel_simple_commands(masked):
        i = 0
        while i < len(tokens) and _ENV_ASSIGN.match(tokens[i]):
            i += 1
        rest = tokens[i:]
        if not rest or rest[0] != "cd":
            continue
        args = rest[1:]
        if args and args[0] == "-":
            targets.append("-")  # cd - ：见文件头"局限"
            continue
        non_flags = [a for a in args if not (a.startswith("-") and a != "-")]
        targets.append(non_flags[0] if non_flags else "")
    return targets


def _resolve_cd(base: str, target: str) -> str:
    if target == "-":
        return base  # 不知道 $OLDPWD，保守当作不变（可能漏报，见文件头"局限"）
    t = target.strip()
    if not t:
        t = os.environ.get("HOME", os.path.expanduser("~"))
    elif t.startswith("~"):
        t = os.path.expanduser(t)
    if os.path.isabs(t):
        return os.path.normpath(t)
    return os.path.normpath(os.path.join(base, t))


def _final_cwd_after_cds(base_cwd: str, raw_cmd: str) -> str | None:
    """依次模拟命令里所有顶层 cd，返回这条命令跑完后 shell 会停留的目录；命令里没有顶层
    cd 时返回 None（绝大多数 Bash 调用都是这种情况——调用方应尽早短路，见 main()）。"""
    targets = _cd_targets(raw_cmd)
    if not targets:
        return None
    cur = base_cwd
    for t in targets:
        cur = _resolve_cd(cur, t)
    return cur


def main() -> None:
    raw = sys.stdin.read()
    if not raw.strip():
        sys.exit(0)
    try:
        event = json.loads(raw)
    except json.JSONDecodeError:
        sys.exit(0)  # 保守放行

    if event.get("tool_name") != "Bash":
        sys.exit(0)

    command = (event.get("tool_input") or {}).get("command", "") or ""
    if not re.search(r"\bcd\b", command):
        sys.exit(0)  # 快速短路：绝大多数 Bash 调用不含 cd，不必做后面的解析/subprocess

    try:
        base_cwd = os.getcwd()
        final_cwd = _final_cwd_after_cds(base_cwd, command)
        if final_cwd is None or not os.path.isdir(final_cwd):
            sys.exit(0)

        project_root = _project_root()
        project_common = _git_common_dir(project_root)
        if project_common is None:
            sys.exit(0)  # 连本仓库自己的 common-dir 都拿不到，保守放行，不误判

        target_common = _git_common_dir(final_cwd)

        if target_common is None:
            print(
                f"[nested_repo_cd_guard] 提醒：这条命令会把 shell 停留在 {final_cwd}，"
                "该目录不在任何 git 仓库内（或无法确认）。后续命令的相对路径/git 操作可能"
                "作用在意外的位置。建议改用子 shell `(cd ... && ...)`、一次性 `git -C <path> ...`，"
                "或跑完这条命令后立刻 cd 回仓库根。",
                file=sys.stderr,
            )
        elif target_common != project_common:
            print(
                f"[nested_repo_cd_guard] 提醒：这条命令会把 shell 停留在 {final_cwd}，"
                f"它属于一个独立的 git 仓库（common dir: {target_common}），不是本仓库"
                f"（common dir: {project_common}）的另一个 worktree。cwd 会在后续所有 Bash "
                "调用里持续漂移：任何裸相对路径的 hook/脚本可能找不到文件（历史事故见 "
                "lab/traces/human-cc/2026-07-09/hook-cwd-drift-stuck-recovery/trace.md），"
                "任何后续 git 命令（status/add/commit/push）也会不声不响作用在这个嵌套仓库，"
                "而不是当前仓库。建议改用子 shell `(cd ... && ...)`、一次性 `git -C <path> ...`，"
                "或跑完这条命令后立刻 cd 回仓库根。",
                file=sys.stderr,
            )
    except Exception:  # noqa: BLE001  advisory hook：任何内部错误都不阻断，保守放行
        pass

    sys.exit(0)


if __name__ == "__main__":
    main()
