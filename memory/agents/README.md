# memory/agents/ — agent 状态明细（运行时，gitignored）

每个活 agent 一份 `<name>.yaml`（task / owned_paths / forbidden_paths / worktree / status /
heartbeat / inbox_ref / outbox_ref），由 `scripts/agent-state.py` 维护，`agent-status.py` /
`check-agent-conflicts.py` / `pre_tool_guard.py` 消费。

- schema 与协议：`.agent/multi-agent-control-plane.md`
- 花名册总览（name↔paseo-id 索引）：`memory/agents-roster.md`
- 内容是每 project 运行时状态，不入 git、不随 template sync（本 README 除外）。
