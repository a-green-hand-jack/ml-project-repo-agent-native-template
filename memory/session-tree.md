# Session Tree

> 记录当前 session 的父/子拓扑，让并行/派生工作可被追踪与合并。
> 与 `current-status.md` 配合：status 记「现在做什么」，tree 记「有哪些并行分支、怎么合」。

## Parent objective

整理 main / worktree / GitHub branch：清理已合入分支，把 `adopt-existing-repo` 功能合入 main，
并保留两个 replay case 分支作为独立压测证据。

## Current phase

`worktree-adopt-existing-repo` 已合入 main；memory 文件冲突已按最新决策整理，最终 validator 已通过。
feature worktree/branch cleanup 已完成。

## Children

| id | purpose | branch/worktree | plan doc | status | next prompt |
| --- | --- | --- | --- | --- | --- |
| feature | adopt-existing-repo workflow | merged into `main`; local feature worktree/branch removed | `plans/20260709-adopt-existing-repo.zh.md` | done | _none_ |
| case-agent-r1 | Agent-R1 adoption replay case | `worktree-case+agent-r1-adoption-replay` / `.claude/worktrees/case+agent-r1-adoption-replay` | `plans/20260709-adopt-existing-repo.zh.md` | keep | Keep as case branch; do not merge full external case into main. |
| case-elf | ELF template replay case | `worktree-case+elf-template-replay` / `.claude/worktrees/case+elf-template-replay` | `memory/branches/case-elf-template-replay.md` | keep/archive | Keep as replay evidence; do not merge into main. |

## Merge / review order

1. Reference coverage / live-status fix was committed locally on main as `cb89a6b`.
2. Merged `worktree-adopt-existing-repo` into main.
3. Ran final validation on merged main.
4. Removed only the adopted feature worktree/branch after merge commit completed.
5. Leave both replay case worktrees/branches in place unless human asks to archive/move them separately.

## Global forbidden paths

- `lab/data/**`
- `lab/runs/**`
- `lab/models/**` bytes
- `checkpoints/**`
- `wandb/**`
- `lab/infra/private/**`
- `.env`

## Open risks

- `main` will be ahead of `origin/main` after the local commits; do not push main without explicit human release/push approval.
- `.claude/worktrees/**` appears as untracked from the main checkout because the worktrees live inside the repo directory.
- The two case branches contain full replay evidence and should not be merged into main by default.
