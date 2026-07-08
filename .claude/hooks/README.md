# .claude/hooks/

repo-local lifecycle hooks（可执行，以本机权限运行——保持小而可审计）。

| 文件 | 事件 | 作用 | 阻止能力 |
| --- | --- | --- | --- |
| `pre_tool_guard.py` | `PreToolUse(Bash\|Edit\|Write)` | 拦截危险 Bash、受保护路径写入、push 到 `main`/`master` | 硬阻止（exit 2） |
| `pre_compact_memory_check.py` | `PreCompact` | 提醒落盘 `memory/current-status.md` | 仅提醒（exit 0） |
| `subagent_report_index.py` | `SubagentStop` | 向 `agent-reports/index.md` 追加时间线 | 仅记录（exit 0） |

## 协议

hook 从 stdin 读 JSON（`tool_name` / `tool_input` 等）。`pre_tool_guard` 以 exit code 2 + stderr 表示阻止；两者解析失败时保守放行。

## 注意

- hook 与 `.claude/settings.json` 的 deny/ask、`.agent/action-boundary.md` 必须一致。
- worktree/desktop/remote surface 下 hook 行为可能不一致——高风险 workflow 仍需 permission + Git + manual review 兜底。
- 改动后用 `/hooks` 或 debug mode 验证触发。
- push 分支感知：topic/实验分支放行；`main`/`master` 被 hook 拦（exit 2），除非命令带 `CLAUDE_ALLOW_PUSH_MAIN=1` 或 session 内 export。见 `.agent/autonomous-window.md`。
- 本地手测（构造串避免误触自身守卫）：
  `python3 -c "import json,subprocess as s;print(s.run(['python3','.claude/hooks/pre_tool_guard.py'],input=json.dumps({'tool_name':'Bash','tool_input':{'command':'git push origin main'}}),capture_output=True,text=True).returncode)"`（在 main 之外的分支上应为 2）。`
