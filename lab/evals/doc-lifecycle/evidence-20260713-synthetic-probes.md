# synthetic 探针证据 — 2026-07-13（issue #13 doc-lifecycle）

> 初审（Codex gpt-5.6-sol high）MAJOR-4 的整改：此前 startup/clear/PostCompact 冒烟只在
> commit message 声称，未落 diff。本文件是可复跑脚本的实跑记录；真实 fresh session 的
> runtime 冒烟**不在本文件范围**，见 `runtime-smoke-checklist.md`（留给监控员）。

## continuity 探针（startup / clear / PostCompact）

- 日期：2026-07-13 · 基线 commit：7ba9588（fix commit 前实跑；合并前监控员可复跑核对）
- 命令：`python3 lab/evals/doc-lifecycle/run-continuity-probes.py --record`
- 结果：3/3 PASS

| 事件 | payload | exit | stdout | 断言 |
| --- | --- | --- | --- | --- |
| fresh startup | `{"hook_event_name": "SessionStart", "source": "startup"}` | 0 | 0 chars（空） | 不注入（决策 11b：startup 靠入口纪律，不靠 hook） |
| clear 恢复 | `{"hook_event_name": "SessionStart", "source": "clear"}` | 0 | 4146 chars | 含 `[continuity] clear 后回注` 与「当前 plan 指针」节（指向 `plans/20260712-plan-lifecycle-state.zh.md` · implementing） |
| compact 恢复（Codex 独立事件） | `{"hook_event_name": "PostCompact"}` | 0 | 4148 chars | 含 `[continuity] compact 后回注` 与同一「当前 plan 指针」节 |

clear 探针 stdout 头部（截取）：

```
[continuity] clear 后回注 memory/current-status.md（已 767 分钟未更新，可能滞后——请对照当前 git 状态）。以下为压缩/清空前的工作状态，据此接续，不要从零重建：

# current-status.md
…
## 当前 plan 指针（doc-lifecycle，fresh session 先看这里）

- 当前活跃 plan：`plans/20260712-plan-lifecycle-state.zh.md`（issue #13）· status: **implementing** ·
```

## hook 拦截面探针（pre_tool_guard × doc-lifecycle）

- 命令：`python3 scripts/check-doc-lifecycle.py --self-test`（判定层，内嵌 fixtures，47/47 PASS，
  含初审 4 个 PoC + fresh review 的 `@@ <anchor>` 重复片段、wrapper/global-option 删除绕过、
  活跃 plan issue/branch/worktree 关联负向用例）+
  `python3 lab/evals/doc-lifecycle/run-guard-regression.py`（对
  `.claude/hooks/pre_tool_guard.py` 的端到端 stdin 回归：安全地板 11 例 + doc-lifecycle 15 例，
  2026-07-13 实跑 26/26 PASS——安全地板旧行为零弱化，fresh review PoC 全部转红）。
- Claude 与 Codex 表面共用同一物理 hook 文件（`.claude/settings.json` 与 `.codex/config.toml`
  分别挂 PreToolUse），synthetic 探针对两侧等价；差异只剩 runtime 接线/trust，见 checklist。
- **证据边界不变：**真实 Claude/Codex fresh/clear/compact 与 hook trust 冒烟仍未执行，属于
  `runtime-smoke-checklist.md` 明示的 merge blocker；本记录不把 synthetic 结果冒充 runtime PASS。
