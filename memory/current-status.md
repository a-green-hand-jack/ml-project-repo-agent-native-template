# current-status.md

> **活文件**。这是当前状态的单一真相源。每次 session 结束、compact 前、完成小目标时更新。
> fresh session 应能只读本文件 + `session-tree.md` 就接续工作。

## 当前 objective

收尾 branch hygiene：已把 main 上的 reference coverage / 活状态修复提交到本地 main，正在把
`worktree-adopt-existing-repo` 功能分支合入 main；两个 replay case 分支只作为压测证据保留，不合入 main。
合并后的验证矩阵已通过，adopt feature 的本地 worktree/branch 已清理。

## Constraints

- 遵守 `AGENTS.md` / `.agent/AGENTS.md` / `.agent/action-boundary.md`。
- 不编辑或删除 `lab/data/**`、`lab/runs/**`、`lab/models/**` bytes、`checkpoints/**`、`wandb/**`、
  `lab/infra/private/**`、`.env`。
- 不启动/kill/restart 长训练或远端作业。
- 不 push main、不开 PR、不 release。
- Human 已确认：`worktree-case+agent-r1-adoption-replay` 与 `worktree-case+elf-template-replay` 是测试 case，
  不合并到 main；通过独立 README/报告说明情况。

## Files inspected

- `AGENTS.md`
- `.agent/AGENTS.md`
- `.agent/action-boundary.md`
- `.agent/human-gates.md`
- `ANATOMY.md`
- `memory/current-status.md`
- `memory/session-tree.md`
- `.reference-docs/implementation-coverage-note.md`
- `DESIGN.md`
- `README.md`
- `git branch -a` / `git worktree list --porcelain` / `gh pr list`

## Files modified

- `.reference-docs/implementation-coverage-note.md`：新增参考文档覆盖说明，记录当前实现是工程化超集以及有意不逐字实现的项。
- `README.md`：更新 `.reference-docs/` 描述，提到覆盖说明文档。
- `DESIGN.md`：更新来源说明、能力清单和决策表。
- `memory/current-status.md`：从空骨架/feature handoff 冲突整理为当前 main 状态。
- `memory/session-tree.md`：记录 feature 分支已合并，case 分支保留不合入。
- `.claude/commands/adopt-existing-repo.md`：新增迁移已有 repo 的 slash command。
- `.claude/skills/adopt-existing-repo/SKILL.md`：新增迁移 skill。
- `scripts/adopt-existing-repo.py`：新增 phased adoption CLI。
- `scripts/check-adoption-integrity.py`：新增 baseline hash integrity checker。
- `lab/evals/adoption/`：新增 synthetic existing repo smoke test 与说明。
- `plans/20260709-adopt-existing-repo.zh.md`：新增迁移能力计划。
- `lab/docs/audits/agent-r1-adoption-replay-report.md` / `stress-test-ledger.yaml`：记录 Agent-R1 replay case。
- `.claude/ANATOMY.md`、`lab/ANATOMY.md`、`lab/README.md`、`lab/docs/audits/README.md`、
  `scripts/ANATOMY.md`、`scripts/README.md`：同步新能力路由。

## Decisions

- main 上此前的 `memory/current-status.md` / `memory/session-tree.md` 是空骨架，不足以作为 fresh session
  接续入口；已提交本地 commit `cb89a6b` 修复。
- 当前模板覆盖 `.reference-docs` 的核心控制面，并在 validator、CI、same-commit rule、parser-based hook、
  branch-aware push guard、中文审阅安全网、recipe/eval 流水线、template stress test 层面形成工程化超集。
- `adopt-existing-repo` 合入 main；它是模板功能，不是一次性测试产物。
- `worktree-case+agent-r1-adoption-replay` 与 `worktree-case+elf-template-replay` 是压测 case 分支，不合入 main。
- 已清理两个已合入 main 的重复本地 agent 分支，以及两个已合入的远端 feature 分支。

## Commands + results

| command | 结论 |
| --- | --- |
| `git fetch --all --prune` | 远端分支状态已刷新。 |
| `git branch -d worktree-agent-a91dd3b9da57a8b88 worktree-agent-ac59d517d71e5ae89` | 两个本地重复 agent 分支已删除。 |
| `git push origin --delete feature/release-gates-regression-matrix-validation feature/round4-doctrine-sync` | 两个已 merged 的 GitHub feature 分支已删除。 |
| `python scripts/check-same-commit.py --staged` | reference coverage commit 前通过：1 处结构改动，对应 anatomy 已同变更集更新。 |
| `python scripts/validate-governance.py --strict` | reference coverage commit 前通过：0 error / 0 warning。 |
| `git commit -m "docs: record reference coverage status"` | 本地 main commit `cb89a6b` 已创建；未 push。 |
| `git merge --no-ff worktree-adopt-existing-repo -m "merge: adopt existing repo workflow"` | 自动合并除两个 memory 活状态文件外均完成；memory 冲突已手动整理。 |
| `git diff --check --cached` | 修复 `lab/evals/adoption/README.md` 末尾空行后通过。 |
| `python -m py_compile scripts/adopt-existing-repo.py scripts/check-adoption-integrity.py lab/evals/adoption/run-adoption-smoke.py` | 通过。 |
| `python lab/evals/adoption/run-adoption-smoke.py` | 通过，输出 `[adoption-smoke] OK`。 |
| `python scripts/check-same-commit.py --staged` | 通过：8 处结构改动，对应 anatomy 已同变更集更新。 |
| `python scripts/validate-governance.py --strict` | 通过：0 error / 0 warning。 |
| `git worktree remove .claude/worktrees/adopt-existing-repo && git branch -d worktree-adopt-existing-repo` | 已移除 adopt feature worktree，并删除本地 feature 分支。 |

## Subagent reports

本轮未派生 subagent。

## Open issues / blockers

- main 已有本地 merge commit；尚未 push。
- `.claude/worktrees/case+agent-r1-adoption-replay/` 与 `.claude/worktrees/case+elf-template-replay/` 仍是本地
  worktree checkout；它们在 main 视角显示为 untracked 是嵌套 worktree 的正常表现。
- `origin/worktree-case+elf-template-replay` 仍保留为 ELF replay case 的远端 archive。

## Exact next steps

1. 如需共享当前 main，另行由 human 明确批准 push main。
2. 两个 replay case worktree/branch 继续作为证据保留；如需移动或归档，单独处理。
3. 后续新增/修改 validator、hook、权限面、结构面或能力面时，按 `.agent/template-stress-test-policy.md`
   触发对应深度测试。

## Do-not-forget

- 需要 human 介入/过目的输出默认中文。
- 两个 replay case 分支默认作为证据保留，不合入 main。
- `.reference-docs/implementation-coverage-note.md` 是覆盖说明，不替代两份参考文档本身。
