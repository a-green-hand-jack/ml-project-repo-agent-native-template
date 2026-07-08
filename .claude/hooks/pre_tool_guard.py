#!/usr/bin/env python3
"""PreToolUse 硬约束 hook。

拦截危险 Bash 命令、对受保护路径的写入、以及推向受保护分支（main/master）的 push。
这是 doctrine 的机器强制层，与 `.agent/action-boundary.md`、`.claude/settings.json` 对齐——
permissions 是可调的第一道门，这个 hook 是**不可调的地板**：即使 human 授权自主窗口
或开 bypass 让 permission 放开，hook 仍拦截红线（破坏性删除、写产物 bytes、push main）。

push 到受保护分支需 human 明确放行（`CLAUDE_ALLOW_PUSH_MAIN=1`），见 `.agent/autonomous-window.md`。

协议：Claude Code 通过 stdin 传入 JSON（含 tool_name / tool_input），
本 hook 以 exit code 2 + stderr 表示「阻止」，exit 0 表示「放行」。
无第三方依赖；解析失败时保守放行（exit 0），避免误伤正常工作流。
"""
import json
import os
import re
import subprocess
import sys

# 受保护路径前缀：agent 不应写入这些（bytes / 私有 / 追踪产物）。
PROTECTED_PREFIXES = (
    "lab/data/",
    "lab/runs/",
    "lab/models/",
    "lab/infra/private/",
    "checkpoints/",
    "wandb/",
    "mlruns/",
)
PROTECTED_FILES = (".env",)

# 受保护分支：push 到这些分支需 human 明确放行（env 或命令内 escape）。
# 这是 hook 地板——即使 permission 层放开（自主窗口/bypass），它仍拦截。
PROTECTED_BRANCHES = {"main", "master"}
PUSH_ESCAPE_ENV = "CLAUDE_ALLOW_PUSH_MAIN"

# 只在命令边界（行首 / ; & | 之后，允许 env 前缀）识别 git push 调用，
# 降低把 commit message 等字符串里的 "git push" 误判为 push 的概率。
GIT_PUSH_INVOCATION = re.compile(
    r"(?:^|[;&|]|\n)\s*(?:[A-Za-z_]\w*=\S+\s+)*git\s+push\b"
)

# 危险 Bash 模式。
DANGEROUS_BASH = [
    (re.compile(r"\brm\s+-rf?\b"), "rm -rf 属破坏性删除，走人工确认"),
    (re.compile(r"\bsudo\b"), "sudo 提权禁止"),
    (re.compile(r"curl\b.*\|\s*(sudo\s+)?sh\b"), "curl | sh 远程执行禁止"),
    # 注：git push 不在此硬拦截。它是 `ask`（每次确认），不是 deny——见
    # .agent/action-boundary.md 需问档、.agent/human-gates.md。PR/merge/release/远端基础设施仍走 human gate。
    (re.compile(r"\brm\b.*\b(lab/(data|runs|models)|checkpoints|wandb)\b"), "禁止删除数据/产物/checkpoint bytes"),
]


def _norm(path: str) -> str:
    p = path.strip().strip('"').strip("'")
    p = p.replace("./", "", 1) if p.startswith("./") else p
    return p


def _is_protected(path: str) -> bool:
    p = _norm(path)
    if p in PROTECTED_FILES:
        return True
    return any(p.startswith(prefix) for prefix in PROTECTED_PREFIXES)


def _current_branch() -> str:
    try:
        out = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True, text=True, timeout=5,
        )
        return out.stdout.strip()
    except Exception:  # noqa: BLE001  # 无 git / 超时 / 非仓库：保守当作未知
        return ""


def _push_hits_protected(cmd: str) -> bool:
    """Best-effort：判断一条 git push 是否推向受保护分支（main/master）。

    - 命令边界处才算 push（避免误判 commit message 里的 "git push"）。
    - 只在 push 自身参数（tail，截到下一个分隔符）里找受保护分支名。
    - 裸 push（无显式 refspec）时回退看当前分支。
    """
    m = GIT_PUSH_INVOCATION.search(cmd)
    if not m:
        return False
    tail = re.split(r"[;&|\n]", cmd[m.end():], 1)[0]
    for b in PROTECTED_BRANCHES:
        if re.search(rf"(^|[\s:/]){re.escape(b)}(\s|$)", tail):
            return True
    # 去掉 flags，剩下的应是 [remote] [refspec...]；<=1 个 token 视为裸 push。
    tail_wo_flags = re.sub(r"(?:^|\s)-{1,2}[A-Za-z][\w-]*(?:=\S+)?", " ", tail)
    tokens = tail_wo_flags.split()
    if len(tokens) <= 1:
        return _current_branch() in PROTECTED_BRANCHES
    return False


def _push_escape_active(cmd: str) -> bool:
    """human 明确放行推受保护分支：session 级 env，或命令内 env 前缀。"""
    if os.environ.get(PUSH_ESCAPE_ENV, "").strip().lower() in ("1", "true", "yes"):
        return True
    return bool(re.search(rf"\b{PUSH_ESCAPE_ENV}\s*=\s*(?:1|true|yes)\b", cmd))


def _block(reason: str) -> None:
    # 新式结构化输出（较新 Claude Code 支持）+ 传统 stderr/exit 2 双通道。
    out = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }
    print(json.dumps(out))
    print(f"[pre_tool_guard] 阻止：{reason}", file=sys.stderr)
    sys.exit(2)


def main() -> None:
    raw = sys.stdin.read()
    if not raw.strip():
        sys.exit(0)
    try:
        event = json.loads(raw)
    except json.JSONDecodeError:
        sys.exit(0)  # 保守放行

    tool = event.get("tool_name", "")
    tool_input = event.get("tool_input", {}) or {}

    if tool == "Bash":
        cmd = tool_input.get("command", "") or ""
        for pattern, reason in DANGEROUS_BASH:
            if pattern.search(cmd):
                _block(reason)
        # 分支感知 push：topic/实验分支放行；推 main/master 需 human 明确放行。
        # 这层在 hook（地板），自主窗口/bypass 放开 permission 也拦得住。
        if _push_hits_protected(cmd) and not _push_escape_active(cmd):
            _block(
                f"push 到受保护分支（{'/'.join(sorted(PROTECTED_BRANCHES))}）需 human 明确放行："
                f"在命令前加 `{PUSH_ESCAPE_ENV}=1 `，或在 session 内 export {PUSH_ESCAPE_ENV}=1。"
                "topic/实验分支 push 不受此限。"
            )

    elif tool in ("Edit", "Write", "NotebookEdit"):
        path = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
        if path and _is_protected(path):
            _block(
                f"受保护路径不可写：{path}。bytes/私有/产物只留 index，删改走 human gate。"
            )

    sys.exit(0)


if __name__ == "__main__":
    main()
