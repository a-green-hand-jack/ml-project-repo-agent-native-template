# Session Tree

> 记录当前 session 的父/子拓扑，让并行/派生工作可被追踪与合并。
> 与 `current-status.md` 配合：status 记「现在做什么」，tree 记「有哪些并行分支、怎么合」。

## Parent objective

按 fresh-review 门槛把 human 指定的九个 feature 安全集成到本地 `main`；九个全部完成前禁止
release/version/tag，远端保持不变。

## Current phase

八个 feature 已 APPROVE + integrated；#13 source `3704d33` 已以 local merge `8ee6760` 合入并通过
组合门禁。当前只剩 #18 的 #13 兼容整合、最终 runtime 矩阵与 fresh review；release gate 尚未满足。

## Children

| id | purpose | branch/worktree | plan doc | status | next prompt |
| --- | --- | --- | --- | --- | --- |
| codex-adapters | Add Codex config/agents/skills/rules adapters | current `main` checkout | _none_ | done | _none_ |
| case-agent-r1 | Agent-R1 adoption replay case | `worktree-case+agent-r1-adoption-replay` / `.claude/worktrees/case+agent-r1-adoption-replay` | `plans/20260709-adopt-existing-repo.zh.md` | keep | Keep as case branch; do not merge full external case into main. |
| case-elf | ELF template replay case | `worktree-case+elf-template-replay` / `.claude/worktrees/case+elf-template-replay` | `memory/branches/case-elf-template-replay.md` | keep/archive | Keep as replay evidence; do not merge into main. |
| issue-12-bootstrap | Issue #12 part A: new-project bootstrap command (`scripts/bootstrap-project.py` + `bootstrap-project` skill) | local `main` (`3bad60d` merge); feature branch/worktree retired | `plans/20260712-bootstrap-adoption-proof.zh.md` | APPROVE + integrated | Keep remote unchanged until a separate push-main authorization. |
| issue-12-smoke-contract | Issue #12 part C: structured runtime/smoke contract and real-repo replay | local `main` (`1a72762` merge); feature branch/worktree retired | `plans/20260712-bootstrap-adoption-proof.zh.md` | APPROVE + integrated | Seven original C scenarios were preserved in the combined 27-scenario adoption smoke. |
| issue-12b-semantic-classification | Issue #12 part B: four-way conservative classification, plan revalidation, safe state paths, shared postflight | local `main` (approved source `f33ff9c`); feature branch/worktree retired after this merge | `plans/20260712-bootstrap-adoption-proof.zh.md` | APPROVE + integrated | Validate the combined B+C behavior; do not push `main` without separate authorization. |
| issue-13-plan-lifecycle | Document lifecycle state and runtime continuity enforcement | local `main` merge `8ee6760`; approved source `3704d33`; feature worktree retained pending separate cleanup authorization | `plans/20260712-plan-lifecycle-state.zh.md` | APPROVE + integrated | Keep remote unchanged; do not reopen the frozen Bash-parser non-goal. |
| issue-14-multi-agent | Multi-agent control plane | local `main` source `e0a32b5`; feature branch/worktree retired | `plans/20260712-multi-agent-control-plane.zh.md` | APPROVE + integrated | Keep remote unchanged. |
| issue-15-outcome-routing | Outcome-aware routing | local `main` merge `8b2bb93`; feature branch/worktree retired | `plans/20260712-outcome-aware-routing.zh.md` | APPROVE + integrated | Keep remote unchanged. |
| issue-16-experiment-control | Experiment lifecycle/control plane | local `main` merge `cbf6ab6`; source `ecf0c80`; feature branch/worktree retired | `plans/20260712-experiment-control-plane.zh.md` | APPROVE + integrated | Four-mode interpreter and strict integration checks passed. |
| issue-17-evidence-chain | Artifact→evidence→claim→deliverable provenance | local `main` merge `405c542`; source `52f83aa`; feature branch/worktree retired | `plans/20260712-artifact-evidence-chain.zh.md` | APPROVE + integrated | Integration candidate was freshly re-reviewed after #16 status compatibility fix. |
| issue-18-anatomy-parity | ANATOMY semantic parity and runtime evidence | `feat/18-anatomy-semantic-parity` / `.claude/worktrees/18-anatomy-semantic-parity` at `cebe427` | `plans/20260712-anatomy-semantic-parity.zh.md` | code APPROVE / final runtime pending | Integrate #13 compatibility, complete C1-C7/X1-X7 with `--require-fresh`, then run exact-HEAD fresh review. |
| issue-56-g3-skills | G3 工作流 skills/commands 端到端演练（8 个 T-ID） | local `main` merge `3211825`（PR #73）；分支/worktree 已归档 | _none_（授权来自 issue #56） | APPROVE + integrated | 8/8 有结论（6 PASS + 1 UNAVAILABLE-by-design + T-G3-6 PASS 含真实发现）；独立 verifier 师爷·审·工作流 APPROVE；干跑零泄漏成立。G4 driver 缺陷另开 #74。 |

### Handoff note — issue-12b-semantic-classification（2026-07-13）

- 原实现 worker 在 `feat/12b-semantic-classification` 上被中途停止；实现 commit `909cbbf`
  由监控员验证后代收（worker 未走到自行收尾/自检那一步）。
- 正式合并前 review（Codex gpt-5.6-sol，high）提出 5 条 findings（1 BLOCKER / 2 MAJOR / 2 MINOR：
  嵌套保护路径漏检、B1 hash 语义被篡改、normalize 盲信持久化计划、harness 字段伪装、
  session-tree 缺本条 handoff 记录）。
- 由后续 fix worker（干将·修·归类）在同一 worktree 内单独一个 fix commit 逐条修复，
  并为每条 BLOCKER/MAJOR 补负向 smoke fixture；未 push、未开 PR，等 human review/merge。
- 第二轮 review（Codex，`c891834` 之后）仍报 4 条安全边界级 findings（BLOCKER-A 保护扫描
  复用性能排除规则漏掉 `.venv` 内嵌保护内容、BLOCKER-B target_path 缺 containment/精确
  派生校验、BLOCKER-C 保护/control-item 位置 symlink 漏检、MAJOR-D category/blocker
  组合与 path 合法性未校验），由 fix worker（干将·修·归类二轮）在同一 worktree 内再补
  一个 fix commit 逐条修复，每条配负向 smoke fixture（共 10 个 fixture 全真跑）；
  未 push、未开 PR。
- 后续 fresh reviews 又发现 canonical/fallback state leaf symlink 与 persisted classification 重验缺口；
  分别在 `7ff5720`、`f33ff9c` fail-closed 修复，并把 B smoke 扩到 21 场景。最终独立 Codex reviewer
  对 `f33ff9c` 给出 `APPROVE`；本地集成同时保留 C 的 6 个专项负向场景与 clean pass 断言。

### Boundary note — issue-56-g3-skills（2026-07-17）

- 由 `session-boundary-control` skill 演练触发（issue #56，父 issue #52 P7）：任务树已分叉出
  8 个 T-ID 子任务（T-G3-1~T-G3-8，逐一走查 `.claude/skills/`/`.claude/commands/`），命中
  「任务树出现 ≥2 个子任务」边界信号，判定动作 = branch（登记子任务节点，非 clear/compact）。
- T-G3-1~T-G3-4 已完成（worktree-pr-flow S2 清单起草中、spawn in-session 子 agent 演示、
  subagent-routing launch packet、interactive-plan-doc 隔离干跑），T-G3-5（本 skill）执行中，
  T-G3-6/7/8 待做；无独立 plan doc，授权来自 issue #56 口头交代。
- 未改 `memory/current-status.md`（父 session 都督·统·治理路线维护，本次不动）。
- **收口（2026-07-17，都督·统·治理路线）**：8 个 T-ID 全部走完，PR #73 经独立 verifier
  APPROVE 后 squash-merge `3211825`、#56 关闭；本条 boundary 结束。G4 driver UNAVAILABLE
  死代码缺陷（T-G3-6 发现、verifier 独立坐实）另开跟进 #74。

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
- `issue-12-smoke-contract` (C) found and fixed a real pre-existing gap while implementing C1/C2:
  `adopt-existing-repo.py`'s `prove` phase never actually made the overall process exit non-zero on
  integrity failure (only logged `status="failed"` internally), and unresolved normalize
  conflict/protected-path blockers were invisible to `check-adoption-integrity.py`. Both are now folded
  into `integrity_result().ok`. This branch's local execution environment also lacks PyYAML by default
  (pre-existing, verified via `git stash` to not be introduced by this branch); validators were run via
  `uv run --with pyyaml python ...` to get a clean `--strict` pass — future sessions on a machine
  without PyYAML pre-installed should do the same or accept the pre-existing warning-only degradation.
