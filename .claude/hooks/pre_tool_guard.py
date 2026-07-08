#!/usr/bin/env python3
"""PreToolUse 硬约束 hook。

拦截危险 Bash 命令与对受保护路径的写入。这是 doctrine 的机器强制层，
与 `.agent/action-boundary.md`、`.claude/settings.json` 的 deny 列表对齐——
permissions 是第一道门，这个 hook 是兜底（尤其当命令拼接绕过简单模式匹配时）。

协议：Claude Code 通过 stdin 传入 JSON（含 tool_name / tool_input），
本 hook 以 exit code 2 + stderr 表示「阻止」，exit 0 表示「放行」。
无第三方依赖；解析失败时保守放行（exit 0），避免误伤正常工作流。
"""
import json
import re
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

    elif tool in ("Edit", "Write", "NotebookEdit"):
        path = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
        if path and _is_protected(path):
            _block(
                f"受保护路径不可写：{path}。bytes/私有/产物只留 index，删改走 human gate。"
            )

    sys.exit(0)


if __name__ == "__main__":
    main()
