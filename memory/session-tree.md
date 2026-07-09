# Session Tree

> 记录当前 session 的父/子拓扑，让并行/派生工作可被追踪与合并。
> 与 `current-status.md` 配合：status 记「现在做什么」，tree 记「有哪些并行分支、怎么合」。

## Parent objective

实现 `adopt-existing-repo`：把已有 repo 分步、可验证、尽量无人值守地收敛成模板完整形态。

## Current phase

Phase 7 complete：Agent-R1 真实 repo replay 已通过、登记并固化为独立 case branch。

## Children

| id | purpose | branch/worktree | plan doc | status | next prompt |
| --- | --- | --- | --- | --- | --- |
| feature | adopt-existing-repo workflow | `worktree-adopt-existing-repo` / `.claude/worktrees/adopt-existing-repo` | `plans/20260709-adopt-existing-repo.zh.md` | done | Review/push feature branch if desired. |
| case-agent-r1 | Agent-R1 adoption replay case | `worktree-case+agent-r1-adoption-replay` / `.claude/worktrees/case+agent-r1-adoption-replay` | `plans/20260709-adopt-existing-repo.zh.md` | done | Keep as case branch; do not merge full external case into main by default. |

## Merge / review order

1. 当前 worktree 内完成 plan、implementation、tests、ANATOMY/DESIGN/README 同步。
2. 跑定向测试与 `python scripts/validate-governance.py --strict`。
3. Human review 后再决定是否 push / PR / merge。

## Global forbidden paths

- `lab/data/**`
- `lab/runs/**`
- `lab/models/**` bytes
- `checkpoints/**`
- `wandb/**`
- `lab/infra/private/**`
- `.env`

## Open risks

- 主工作区已有未提交改动；本 feature 分支基于 `main` 的 clean HEAD，不包含那些改动。
- 新增脚本、skill、command 会触发能力清单/ANATOMY/validator 同步需求。
- 迁移工具若默认动作过激，可能破坏目标 repo；第一版必须 conservative，不能删除或覆盖。
