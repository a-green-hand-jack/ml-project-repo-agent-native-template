# ANATOMY — memory/ 结构图

模板骨架（template scaffold）。以下描述该目录的**预期结构**与状态流，非已存在的运行代码；文件按名引用，不含 `file:line` 引用。

## 组件

```
memory/
├── current-status.md        活状态单一真相源（single source of truth）
├── session-tree.md          父/子 session 拓扑 + 合并顺序 + 禁改路径
├── worktree-status.md       跨分支/worktree 状态总览（由 branch-reporter 生成，非持续维护）
├── current-practices.md     采用中的 CC recipe 索引（→ lab/recipes/claude-code/）
├── deprecated-practices.md  失效技巧账
├── phase-dashboard.yaml     phase 看板（结构化，validator 可读）
├── change-control.yaml      变更登记账（结构化，validator 可读）
├── doc-lifecycle.yaml       brief/plan/review/decision 生命周期注册表（schema 见 plans/ANATOMY.md，由 check-doc-lifecycle.py 校验）
├── gc/                      过期状态/handoff 归档区
├── branches/                <slug>.md 单分支状态
├── handoffs/                <YYYYMMDD>-<slug>.md 交接文档
├── agents-roster.md         活 agent 花名册总览（运行时，gitignored；agent_name_set.py 维护）
├── agents/                  <name>.yaml 每 agent 状态明细（运行时，gitignored；agent-state.py 维护）
└── mailbox/                 <name>/inbox.md+outbox.md agent 间消息落盘（运行时，gitignored）
```

`agents-roster.md` / `agents/` / `mailbox/` 是多 agent 控制面（`.agent/multi-agent-control-plane.md`，
issue #14）：格式/脚本随 template 继承，内容是每 project 运行时状态、不入 git（README 除外）。

`worktree-status.md` 由 `branch-reporter` subagent（见 `.claude/agents/branch-reporter.md`）盘点所有 active branch/worktree 后写入，不是每个 session 都会更新的活文件——只在派生 branch-reporter 生成一次汇总报告时才出现/刷新。

## 状态流

```
session 开始
  read current-status.md + session-tree.md
      │
  工作 / 派生子 session（登记 session-tree.md children）
      │
  完成小目标 → checkpoint 到 current-status.md
      │
  session 边界 / compact 前
      ├─ 更新 current-status.md
      ├─ 写 handoffs/<date>-<slug>.md（跨 session 交接）
      └─ 更新 branches/<slug>.md
      │
  过期状态 → 移入 gc/
```

## 持久状态归属

- **活状态**（会频繁变）：`current-status.md`、`session-tree.md`、`branches/`。
- **登记账**（追加为主）：`phase-dashboard.yaml`、`change-control.yaml`、`doc-lifecycle.yaml`、`handoffs/`。
- **归档**（只读历史）：`gc/`。

## 与其它层的边界

- 实验事实 → `lab/research/`、`lab/artifacts/`（不在此）。
- 对外 claim / 交付物 → `deliverables/`（不在此）。
- human 决策 / brief → `human/`（不在此）。
- doctrine / 模板 / 政策 → `.agent/`（不在此）。
