# memory/mailbox/ — agent 间消息落盘（运行时，gitignored）

每个活 agent 一对 `<name>/inbox.md` + `<name>/outbox.md`，由 `scripts/agent-mailbox.py`
维护（send / mark-read / handoff / ack）。发送 = 写自己 outbox + 追加对方 inbox；
`decision`/`handoff` 类关键消息必须带 `ref` 指向 tracked 的 repo 落盘记录。

- schema 与协议：`.agent/multi-agent-control-plane.md`
- 低延迟提醒走 `paseo send <id>`（可选）；这里是可恢复、可查的结构化真相层。
- 内容是每 project 运行时状态，不入 git、不随 template sync（本 README 除外）。
