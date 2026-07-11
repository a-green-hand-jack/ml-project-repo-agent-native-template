# .claude/hooks/

repo-local lifecycle hooks（可执行，以本机权限运行——保持小而可审计）。

| 文件 | 事件 | 作用 | 阻止能力 |
| --- | --- | --- | --- |
| `pre_tool_guard.py` | `PreToolUse(Bash\|Edit\|Write)` | 拦截危险 Bash、受保护路径写入、push 到 `main`/`master` | 硬阻止（exit 2） |
| `pre_compact_memory_check.py` | `PreCompact` | 提醒落盘 `memory/current-status.md` | 仅提醒（exit 0） |
| `subagent_report_index.py` | `SubagentStop` | 向 `agent-reports/index.md` 追加时间线 | 仅记录（exit 0） |
| `zh_review_advisory.py` | `PostToolUse(Edit\|Write)` | 命中 `human/reviews/**`、`human/decisions/**`、`lab/docs/audits/**`、`DECISIONS.md` 时，用中日韩字符占比启发检查是否忘了用中文；不做翻译判断，只提醒派发 `zh-review-gate` | 仅提醒（exit 0） |
| `context_threshold_notice.py` | `UserPromptSubmit` | 上下文 ≥65%/≥80% 时向本轮注入「派 checkpoint-writer + 考虑 compact」建议；每 session 每档只提醒一次 | 仅注入建议（exit 0） |
| `context_continuity.py` | `SessionStart(compact\|clear)` | compact/clear 后把 `memory/current-status.md` 摘要回注新上下文，接续不断档 | 仅注入（exit 0） |
| `context_usage.py` | —（库/CLI，非注册 hook） | 共用 helper：读 transcript `usage` 求精确上下文 token%，供 statusline 与上面阈值 hook 调用 | N/A |

## 上下文调配（信号层，见 `plans/20260711-context-orchestration.zh.md`）

`context_usage.py` / `context_threshold_notice.py` / `context_continuity.py` + `statusline.sh` 的
`🧠 NN%` 段共同补齐「主动调配」链：statusline 让占用**可见**，UserPromptSubmit hook 在 65/80 档
把建议**注入**，SessionStart hook 在压缩后**回注** status 保连续性。

**硬边界**：这三者只发信号/注入文本，**不 block、不自动 `/compact`**——真正按下 compact 需宿主 CLI +
主 agent 在任务边界判断（repo hook 无法可靠按 token 阈值自动压缩）。token% 精确来自 transcript
`usage`（`input+cache_read+cache_creation`）。

**窗口大小**：默认 200000（标准 Claude Code 窗口）。statusline 从 `.model.id`（含 `[1m]`）能自动
认出 1M 上下文；但 UserPromptSubmit hook 的 stdin 没有 model，transcript 又只存 base id（不带
`[1m]`）——所以**跑 1M 上下文（Opus 4.8 [1m]）的项目要显式设 `CLAUDE_CTX_WINDOW=1000000`**（放
`.claude/settings.json` 的 `env` 块或 `.claude/settings.local.json`），否则 hook 会按 200k 早报警。
默认偏 200k 是刻意的**安全方向**：宁可早提醒，也不漏（反过来用 1M 默认会漏掉 200k session 的真阈值）。

**运行表面**：`context_threshold_notice`（UserPromptSubmit）与 `context_continuity`（SessionStart）目前只注册在
Claude Code 表面（`.claude/settings.json`）。Codex 侧 `.codex/config.toml` 是否支持这两个事件未确认，故未加，
以免塞入 Codex 不认的事件破坏配置——`PreCompact` 落盘提醒已在两个表面对等。待确认 Codex 事件支持后再补对等注册。

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
