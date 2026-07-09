# .claude/hooks/

repo-local lifecycle hooks（可执行，以本机权限运行——保持小而可审计）。

| 文件 | 事件 | 作用 | 阻止能力 |
| --- | --- | --- | --- |
| `pre_tool_guard.py` | `PreToolUse(Bash\|Edit\|Write)` | 拦截危险 Bash、受保护路径写入、push 到 `main`/`master` | 硬阻止（exit 2） |
| `pre_compact_memory_check.py` | `PreCompact` | 提醒落盘 `memory/current-status.md` | 仅提醒（exit 0） |
| `subagent_report_index.py` | `SubagentStop` | 向 `agent-reports/index.md` 追加时间线 | 仅记录（exit 0） |
| `zh_review_advisory.py` | `PostToolUse(Edit\|Write)` | 命中 `human/reviews/**`、`human/decisions/**`、`lab/docs/audits/**`、`DECISIONS.md` 时，用中日韩字符占比启发检查是否忘了用中文；不做翻译判断，只提醒派发 `zh-review-gate` | 仅提醒（exit 0） |

## 协议

hook 从 stdin 读 JSON（`tool_name` / `tool_input` 等）。`pre_tool_guard` 以 exit code 2 + stderr 表示阻止；两者解析失败时保守放行。

## `pre_tool_guard` 拦什么（地板层，bypass/自主窗口也拦）

- 用 **shlex 真正解析命令**（非子串正则）：引号里的字面量（commit message、`echo "..."`）不误伤；引号里的真实路径/分支（`rm -rf "lab/data"`、`git push origin "main"`）仍识别。
- 提权/远程执行：`sudo`、`curl|sh`、`wget|sh`。
- 依赖：`pip install`、`python -m pip install`（用 `uv add`）。
- `rm -r` **目标分级**：数据/产物 bytes、`.git`、绝对路径(非 `/tmp`)、`~`、仓库根、`..` → 拦；缓存/构建/临时目录（`__pycache__` 等）→ 放行。另有兜底正则拦 `find -exec rm ... lab/data` 类嵌套。
- `mv`/`cp`/`rsync`/`dd` 触碰受保护路径 → 拦。
- 受保护路径的 `Edit`/`Write` → 拦。
- push 到 `main`/`master` → 拦，除非 `CLAUDE_ALLOW_PUSH_MAIN=1`。

## 注意

- hook 与 `.claude/settings.json` 的 deny/ask、`.agent/action-boundary.md` 必须一致。
- worktree/desktop/remote surface 下 hook 行为可能不一致——高风险 workflow 仍需 permission + Git + manual review 兜底。
- 改动后用 `/hooks` 或 debug mode 验证触发。
- push 分支感知：topic/实验分支放行；`main`/`master` 被 hook 拦（exit 2），除非命令带 `CLAUDE_ALLOW_PUSH_MAIN=1` 或 session 内 export。见 `.agent/autonomous-window.md`。
- 本地手测（构造串避免误触自身守卫）：
  `python3 -c "import json,subprocess as s;print(s.run(['python3','.claude/hooks/pre_tool_guard.py'],input=json.dumps({'tool_name':'Bash','tool_input':{'command':'git push origin main'}}),capture_output=True,text=True).returncode)"`（在 main 之外的分支上应为 2）。`
