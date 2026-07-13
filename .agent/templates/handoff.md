# Handoff 模板

保持 < 120 行。存 `memory/handoffs/<YYYYMMDD>-<slug>.md`。两种变体：

## A. session handoff（同一 agent/任务跨 session，给 fresh session）

```
Objective:
Current status:
Decisions:
Modified files:
Commands / results:
Open blockers:
Exact next prompt:
Forbidden paths:
```

## B. ownership handoff（任务转移给另一个 agent，需接收方 ack）

协议见 `.agent/multi-agent-control-plane.md`：先写本文档，再
`python scripts/agent-mailbox.py handoff --from <A> --to <B> --task "..." --ref <本文档> [--paths ...]`，
接收方 `ack` 后 ownership 才转移（pending → accepted，owned_paths 随之迁移）。

```
From agent / To agent:
Task:
Transferred owned paths:
Current status / remaining work:
Decisions & constraints:
Commands / results:
Open blockers:
Acceptance criteria:
Forbidden paths:
Ack: pending | accepted（由 agent-mailbox.py ack 翻转，消息 id: <msgid>）
```
