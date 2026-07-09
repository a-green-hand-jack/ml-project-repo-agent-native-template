# Session Tree

> 记录当前 session 的父/子拓扑，让并行/派生工作可被追踪与合并。
> 与 `current-status.md` 配合：status 记「现在做什么」，tree 记「有哪些并行分支、怎么合」。

## Parent objective

让模板在保留 Claude Code 原生能力的同时，也能被 Codex 直接发现并使用同等 repo-local 能力。

## Current phase

Codex adapter implementation 已完成：`.codex/`、`.agents/`、共享 hooks、生成器、validator 与文档已同步。
治理验证已通过；当前没有派生子 session。

## Children

| id | purpose | branch/worktree | plan doc | status | next prompt |
| --- | --- | --- | --- | --- | --- |
| codex-adapters | Add Codex config/agents/skills/rules adapters | current `main` checkout | _none_ | done | _none_ |
| case-agent-r1 | Agent-R1 adoption replay case | `worktree-case+agent-r1-adoption-replay` / `.claude/worktrees/case+agent-r1-adoption-replay` | `plans/20260709-adopt-existing-repo.zh.md` | keep | Keep as case branch; do not merge full external case into main. |
| case-elf | ELF template replay case | `worktree-case+elf-template-replay` / `.claude/worktrees/case+elf-template-replay` | `memory/branches/case-elf-template-replay.md` | keep/archive | Keep as replay evidence; do not merge into main. |

## Merge / review order

1. Review the Codex adapter diff as one capability change.
2. If accepted, commit together with synced `ANATOMY.md` files and `memory/change-control.yaml`.
3. Do not push main unless human explicitly approves.

## Global forbidden paths

- `lab/data/**`
- `lab/runs/**`
- `lab/models/**` bytes
- `checkpoints/**`
- `wandb/**`
- `lab/infra/private/**`
- `.env`

## Open risks

- `main` remains ahead of `origin/main`; do not push main without explicit human release/push approval.
- `.claude/worktrees/**` appears as untracked from the main checkout because the worktrees live inside the repo directory.
- The two case branches contain full replay evidence and should not be merged into main by default.
- Codex hooks/config require project trust and hook trust review before they run in a fresh Codex session.
