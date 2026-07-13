# synthetic 探针证据 — 2026-07-13（issue #13 doc-lifecycle）

> 初审（Codex gpt-5.6-sol high）MAJOR-4 的整改：此前 startup/clear/compact 冒烟只在
> commit message 声称，未落 diff。本文件是可复跑脚本的实跑记录；真实 fresh session 的
> runtime 冒烟**不在本文件范围**；真实 8/8 PASS 见
> `evidence-20260713-runtime-probes.md` 与 `runtime-smoke-checklist.md`。

## continuity + hook stdout 协议探针

- 日期：2026-07-13 · 基线 commit：02626c3 + working-tree JSON 协议修复
- 命令：`python3 lab/evals/doc-lifecycle/run-continuity-probes.py --record`
- 结果：8/8 PASS

| 事件 | payload | exit | stdout | 断言 |
| --- | --- | --- | --- | --- |
| fresh startup | `{"hook_event_name": "SessionStart", "source": "startup"}` | 0 | 0 chars（空） | 不注入（决策 11b：startup 靠入口纪律，不靠 hook） |
| clear 恢复 | `{"hook_event_name": "SessionStart", "source": "clear"}` | 0 | 4317 chars | stdout 是唯一 JSON 对象；`hookSpecificOutput.hookEventName=SessionStart`；`additionalContext` 含 `[continuity] clear 后回注` 与当前 plan 指针 |
| compact 恢复 | `{"hook_event_name": "SessionStart", "source": "compact"}` | 0 | 4319 chars | 同上，`additionalContext` 含 `[continuity] compact 后回注` |
| identity 首轮注入 | `UserPromptSubmit` + 无 identity | 0 | JSON | 事件名精确绑定 `UserPromptSubmit`，文本位于 `additionalContext` |
| identity 边界重申 | `SessionStart(clear)` + `AGENT_NAME=test-persona` | 0 | JSON | 事件名精确绑定 `SessionStart`，包含 identity |
| context threshold | `UserPromptSubmit` + synthetic 80% usage | 0 | JSON | 事件名精确绑定 `UserPromptSubmit`，包含 `[context]` |
| 无 identity startup | `SessionStart(startup)` | 0 | 0 chars（空） | 静默路径保持空 stdout |
| PostCompact 防回归 | `PostCompact(manual)` | 0 | 0 chars（空） | 不输出该事件不支持的 `hookSpecificOutput`，避免 invalid JSON/field |

clear 探针 stdout 头部（截取）：

```json
{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"[continuity] clear 后回注 memory/current-status.md（可能滞后——请对照当前 git 状态）。以下为压缩/清空前的工作状态，据此接续，不要从零重建：\n\n# current-status.md\n…"}}
```

Codex 0.144 的官方源码 schema 还确认：`SessionStart` 输入 source 包含 `compact`，且只有
`SessionStart` / `UserPromptSubmit` 支持 `hookSpecificOutput.additionalContext`；`PostCompact`
只接受通用状态字段，不能用于模型上下文回注。因此 Codex 接线改为
`SessionStart(compact|clear)`，而不是把裸文本打印给 `PostCompact`。

> 证据边界：本节证明脚本输出协议和静态接线，不替代下方真实 runtime 冒烟。

## hook 拦截面探针（pre_tool_guard × doc-lifecycle）

- 命令：`python3 scripts/check-doc-lifecycle.py --self-test`（判定层，内嵌 fixtures，47/47 PASS，
  含初审 4 个 PoC + fresh review 的 `@@ <anchor>` 重复片段、wrapper/global-option 删除绕过、
  活跃 plan issue/branch/worktree 关联负向用例）+
  `python3 lab/evals/doc-lifecycle/run-guard-regression.py`（对
  `.claude/hooks/pre_tool_guard.py` 的端到端 stdin 回归：安全地板 11 例 + doc-lifecycle 15 例，
  2026-07-13 实跑 26/26 PASS——安全地板旧行为零弱化，fresh review PoC 全部转红）。
- Claude 与 Codex 表面共用同一物理 hook 文件（`.claude/settings.json` 与 `.codex/config.toml`
  分别挂 PreToolUse），synthetic 探针对两侧等价；差异只剩 runtime 接线/trust，见 checklist。
- **证据边界不变：**本记录不把 synthetic 结果冒充 runtime PASS；真实 Claude/Codex
  fresh/clear/compact 与 guard trust 已另行 8/8 执行并落 raw evidence，见
  `evidence-20260713-runtime-probes.md`。
