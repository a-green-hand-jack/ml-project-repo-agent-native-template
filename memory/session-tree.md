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
| issue-12-bootstrap | Issue #12 part A: new-project bootstrap command (`scripts/bootstrap-project.py` + `bootstrap-project` skill) | `feat/12-bootstrap-adoption-proof` / `.claude/worktrees/12-bootstrap-adoption-proof` | `plans/20260712-bootstrap-adoption-proof.zh.md` | impl done, awaiting human review/merge | Human review + decide on `--allow-major`-style push/PR gate; then start issue #12 parts B (semantic classification) and C (smoke contract) in their own worktrees per plan decision 6. |
| issue-12b-semantic-classification | Issue #12 part B: adopt-existing-repo 语义归类（B1-B6，四类保守归类 + normalize 消费计划 + 共享 postflight） | `feat/12b-semantic-classification` / `.claude/worktrees/12b-semantic-classification` | `plans/20260712-bootstrap-adoption-proof.zh.md` | impl + review-fix done, awaiting human review/merge | Human review（正式合并前 Codex gpt-5.6-sol review 的 5 条 findings 已在 fix commit 中逐条修复）；merge 决定权在 human。 |

### Handoff note — issue-12b-semantic-classification（2026-07-13）

- 原实现 worker 在 `feat/12b-semantic-classification` 上被中途停止；实现 commit `909cbbf`
  由监控员验证后代收（worker 未走到自行收尾/自检那一步）。
- 正式合并前 review（Codex gpt-5.6-sol，high）提出 5 条 findings（1 BLOCKER / 2 MAJOR / 2 MINOR：
  嵌套保护路径漏检、B1 hash 语义被篡改、normalize 盲信持久化计划、harness 字段伪装、
  session-tree 缺本条 handoff 记录）。
- 由后续 fix worker（干将·修·归类）在同一 worktree 内单独一个 fix commit 逐条修复，
  并为每条 BLOCKER/MAJOR 补负向 smoke fixture；未 push、未开 PR，等 human review/merge。

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
- `issue-12-bootstrap`'s A5 fresh-Codex-session runtime smoke is now complete (2026-07-12, orchestrated
  by the monitor role, real Codex gpt-5.6-sol session against a repo bootstrapped from a `git archive
  main` snapshot): guidance (`AGENTS.md`) and `.agents/skills/` (21 skills) discovery both confirmed
  visible; project hooks (`format_changed_python.py`/`zh_review_advisory.py`) showed no attributable
  trigger evidence even though the target was `trusted` — recorded as unknown, not confirmed-firing or
  confirmed-broken. See the plan doc's A5 entry and latest revision-log line for full detail.
