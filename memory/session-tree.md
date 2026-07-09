# Session Tree

> 记录当前 session 的父/子拓扑，让并行/派生工作可被追踪与合并。
> 与 `current-status.md` 配合：status 记「现在做什么」，tree 记「有哪些并行分支、怎么合」。

## Parent objective

维护 Agent-R1 adoption replay case branch，用真实 agent-RL repo 压力测试模板迁移能力。

## Current phase

Case branch complete：Agent-R1 imported content 已提交并通过 pressure matrix。

## Children

| id | purpose | branch/worktree | plan doc | status | next prompt |
| --- | --- | --- | --- | --- | --- |
| case-agent-r1 | preserve Agent-R1 adoption replay | `worktree-case+agent-r1-adoption-replay` / `.claude/worktrees/case+agent-r1-adoption-replay` | `plans/20260709-adopt-existing-repo.zh.md` | done | Keep branch for future stress testing; do not merge full case into main by default. |

## Merge / review order

1. 提交 case branch，不合并完整 case 内容回 `main`。
2. 若 case 发现通用 template bug，回到 `worktree-adopt-existing-repo` 或新修复分支修。
3. Human review 后再决定是否 push remote branch。

## Global forbidden paths

- `lab/data/**`
- `lab/runs/**`
- `lab/models/**` bytes
- `checkpoints/**`
- `wandb/**`
- `lab/infra/private/**`
- `.env`

## Open risks

- Case branch 体积包含 Agent-R1 images/docs/examples/recipes；默认不要合并回 `main`。
- Agent-R1 runtime 行为未验证，因为没有轻量 native test command。
