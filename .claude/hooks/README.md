# .claude/hooks/

repo-local lifecycle hooks（可执行，以本机权限运行——保持小而可审计）。

| 文件 | 事件 | 作用 | 阻止能力 |
| --- | --- | --- | --- |
| `pre_tool_guard.py` | `PreToolUse(Bash\|Edit\|Write)` | 拦截危险 Bash 与受保护路径写入 | 硬阻止（exit 2） |
| `pre_compact_memory_check.py` | `PreCompact` | 提醒落盘 `memory/current-status.md` | 仅提醒（exit 0） |

## 协议

hook 从 stdin 读 JSON（`tool_name` / `tool_input` 等）。`pre_tool_guard` 以 exit code 2 + stderr 表示阻止；两者解析失败时保守放行。

## 注意

- hook 与 `.claude/settings.json` 的 deny/ask、`.agent/action-boundary.md` 必须一致。
- worktree/desktop/remote surface 下 hook 行为可能不一致——高风险 workflow 仍需 permission + Git + manual review 兜底。
- 改动后用 `/hooks` 或 debug mode 验证触发。
- 本地手测：`echo '{"tool_name":"Bash","tool_input":{"command":"git push origin main"}}' | python3 .claude/hooks/pre_tool_guard.py; echo "exit=$?"`
