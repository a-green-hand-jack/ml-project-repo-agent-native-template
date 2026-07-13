# lab/evals/doc-lifecycle/ — doc-lifecycle 冒烟（issue #13）

`plans/20260712-plan-lifecycle-state.zh.md` 验证标准里「双 runtime 冒烟」的落盘处，
拆成两半（plan 已定案：synthetic 不能替代 runtime，两者都要留证据）：

| 半边 | 载体 | 谁跑 |
| --- | --- | --- |
| synthetic 探针（可复跑） | `run-continuity-probes.py`（对 continuity 喂 startup/clear/compact stdin，并回归 identity/threshold 注入的结构化 JSON 协议）+ `run-guard-regression.py`（对 `pre_tool_guard.py` 的端到端 stdin 回归：安全地板 + doc-lifecycle 拦截面，含初审 4 个 PoC 与 fresh review 的 anchor/wrapper/实体关联负向用例）；判定层单元 fixtures 另见 `scripts/check-doc-lifecycle.py --self-test` | 任何 agent / CI，随时 |
| 真实 fresh session runtime 冒烟 | `runtime-smoke-checklist.md`（8/8 完成记录）+ `evidence-20260713-runtime-probes.md` + `raw/` 原始转录/debug log/sha256 | 集成 owner 在隔离 HOME + disposable clone 中执行 |

已跑过的 synthetic 证据记录在 `evidence-20260713-synthetic-probes.md`；真实 session 证据记录在
`evidence-20260713-runtime-probes.md`。`raw/` 只存无时间戳 gzip 压缩的 CLI 文本转录和 debug
log，不含 credential；`SHA256SUMS` 绑定压缩 raw 文件完整性，`gzip -cd` 可读原文。
