# .outcome-ledger/ — 本地累积的路由决策 / 结果明细

真实累积数据落盘处（gitignored，只有本 README 与 `.gitkeep` 入 Git）。
决策来源见 `plans/20260712-outcome-aware-routing.zh.md`「未解决问题 2：已决策」。

- 明细文件：`ledger.jsonl`（append-only JSONL，两类记录 `decision` / `outcome`，
  以 `decision_id` 关联）。schema 见 `../schema.md`。
- 写入方式：`python .claude/skills/coding-agent-quota/scripts/outcome_ledger.py record-decision|record-outcome ...`，
  或 `outcome_route.py --record`。不要手改历史行（append-only；修正用新 outcome 记录覆盖语义）。
- 查询：`outcome_ledger.py show --decision-id d-xxxx`；launch packet 只嵌 `decision_id`，
  完整证据链按 ID 在这里查。
- 校验：`python scripts/check-outcome-ledger-schema.py`（本目录存在 `ledger.jsonl` 时会一并校验）。
- 本目录不含任何 credential / token；只存路由决策与可自动获取的结果代理信号。
