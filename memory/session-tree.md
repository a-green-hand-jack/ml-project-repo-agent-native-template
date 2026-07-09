# Session Tree

> 记录当前 session 的父/子拓扑，让并行/派生工作可被追踪与合并。
> 与 `current-status.md` 配合：status 记「现在做什么」，tree 记「有哪些并行分支、怎么合」。

## Parent objective

收尾 `ml-project-repo-agent-native-template` v1 治理面：补齐 main 活状态，确认功能测试覆盖与
`.reference-docs` 覆盖关系，把必要结论落盘。

## Current phase

无 `phase-dashboard.yaml` 具体 phase id；本轮处于 **v1 coverage/status hardening**。

已知背景：

- ELF case 压力测试已经完成并登记为 `lab/docs/audits/stress-test-ledger.yaml` 首条 case。
- 最新 main 为 `f2f1dee`，已把 `template-stress-test` skill、policy、probe catalog、ledger 落进模板。
- main 的历史空状态文件是当前需要修复的小问题。

## Children

| id | purpose | branch/worktree | plan doc | status | next prompt |
| --- | --- | --- | --- | --- | --- |
| _none_ | 本轮不派生子 session | `main` / repo root | _n/a_ | active | _n/a_ |

## Merge / review order

1. 本轮只在 main 工作树做本地文档/状态改动。
2. 运行 validator 与 same-commit 检查。
3. 由 human 决定是否提交、保留/移动/清理 ELF case 本地 worktree，或继续做新 case。

## Global forbidden paths

- `lab/data/**`
- `lab/runs/**`
- `lab/models/**` bytes
- `checkpoints/**`
- `wandb/**`
- `lab/infra/private/**`
- `.env`
- `.claude/worktrees/**`（本轮只读，不清理/改写 ELF case branch 的本地 worktree checkout）

## Open risks

- `.claude/worktrees/case+elf-template-replay/` 是 `worktree-case+elf-template-replay` branch 的本地
  worktree checkout；它在 main 视角显示为 untracked，是嵌套 worktree 的表现，不是孤立残留目录。
- `agent-native-template-functional-test-report.md` 是历史报告正文，不是最新状态总览；最新摘要看
  `stress-test-ledger.yaml` 与本文件。
- reference coverage 是语义核对，不是机器自动证明；后续参考文档更新时应同步更新 coverage note。
