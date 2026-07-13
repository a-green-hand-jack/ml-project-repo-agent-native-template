# lab/evals/doc-lifecycle/ — doc-lifecycle 冒烟（issue #13）

`plans/20260712-plan-lifecycle-state.zh.md` 验证标准里「双 runtime 冒烟」的落盘处，
拆成两半（plan 已定案：synthetic 不能替代 runtime，两者都要留证据）：

| 半边 | 载体 | 谁跑 |
| --- | --- | --- |
| synthetic 探针（可复跑） | `run-continuity-probes.py`（对 `context_continuity.py` 喂 startup/clear/PostCompact stdin）+ `run-guard-regression.py`（对 `pre_tool_guard.py` 的端到端 stdin 回归：安全地板 + doc-lifecycle 拦截面，含初审 4 个 PoC 负向用例）；判定层单元 fixtures 另见 `scripts/check-doc-lifecycle.py --self-test` | 任何 agent / CI，随时 |
| 真实 fresh session runtime 冒烟 | `runtime-smoke-checklist.md`（待跑清单 + 证据模板） | **监控员 / human**（agent worker 不启动新 session） |

已跑过的 synthetic 证据记录在 `evidence-20260713-synthetic-probes.md`。
输出都是小文本，直接进 Git；无大 bytes。
