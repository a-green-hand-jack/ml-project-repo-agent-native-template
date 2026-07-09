# current-status.md

> **活文件**。这是当前状态的单一真相源。每次 session 结束、compact 前、完成小目标时更新。
> fresh session 应能只读本文件 + `session-tree.md` 就接续工作。
> 下面是模板骨架，逐项填写，不要留空占位而不说明。

## 当前 objective

在独立 worktree 中设计并实现 `adopt-existing-repo` 迁移能力：把一个已有 repo 分步、
可验证、尽量无人值守地收敛成本模板的完整形态。

## Constraints

- 当前 worktree：`.claude/worktrees/adopt-existing-repo`
- 当前 branch：`worktree-adopt-existing-repo`
- 主工作区有未提交的文档/coverage-note 改动；不要在主工作区实现本 feature。
- 禁改路径以 `session-tree.md` 的 Global forbidden paths 为准。
- 外部副作用仍走 human gate：不 push main、不开 PR、不 merge、不 release。

## Files inspected

- `AGENTS.md`
- `.agent/AGENTS.md`
- `memory/current-status.md`
- `memory/session-tree.md`
- `plans/README.md`
- `.agent/templates/plan-doc.zh.md`
- `.claude/skills/worktree-pr-flow/SKILL.md`
- `scripts/ANATOMY.md`

## Files modified

- `plans/20260709-adopt-existing-repo.zh.md`：新增迁移能力计划文档。
- `scripts/adopt-existing-repo.py`：新增 phased adoption CLI。
- `scripts/check-adoption-integrity.py`：新增 baseline hash integrity checker。
- `lab/evals/adoption/README.md`：新增 adoption smoke eval 说明。
- `lab/evals/adoption/run-adoption-smoke.py`：新增 synthetic existing repo smoke test。
- `.claude/skills/adopt-existing-repo/SKILL.md`：新增迁移 skill。
- `.claude/commands/adopt-existing-repo.md`：新增 slash command。
- `README.md`：新增迁移已有 repo 入口。
- `DESIGN.md`：更新能力清单数量。
- `lab/docs/audits/agent-r1-adoption-replay-report.md`：新增 Agent-R1 真实 replay 报告。
- `lab/docs/audits/stress-test-ledger.yaml`：登记 Agent-R1 adoption replay。
- `lab/docs/audits/README.md`：索引新增 replay 报告。
- `.claude/ANATOMY.md`、`scripts/ANATOMY.md`、`scripts/README.md`、`lab/ANATOMY.md`、`lab/README.md`：同步新脚本/能力/eval 路由。
- `memory/current-status.md`：记录本 worktree 当前目标、边界和下一步。
- `memory/session-tree.md`：记录本 feature 的 session/worktree 拓扑。

## Decisions

- `adopt-existing-repo` 不是简单 overlay，而是 template-converger：最终目标是完整收敛到模板形态。
- 迁移采用 phased gates：discover → baseline → scaffold → normalize → prove。
- 默认 conservative/no-human policy：不删除、不覆盖、不可判断即停下并写报告。
- 实现必须在 `worktree-adopt-existing-repo` 分支进行，隔离主工作区已有改动。
- v1 不做 import/path rewrite；原 repo root 作为一个整体移动到 `lab/code/imported/<slug>/`，
  原测试也在 imported root 中运行。

## Commands + results

| command | 结论 |
| --- | --- |
| `git worktree add .claude/worktrees/adopt-existing-repo -b worktree-adopt-existing-repo main` | 创建 feature worktree 成功，HEAD 为 `f2f1dee`。 |
| `pwd && git rev-parse --show-toplevel` | 确认 cwd/top-level 均为 `.claude/worktrees/adopt-existing-repo`。 |
| `python -m py_compile scripts/adopt-existing-repo.py scripts/check-adoption-integrity.py lab/evals/adoption/run-adoption-smoke.py` | 通过。 |
| `python lab/evals/adoption/run-adoption-smoke.py` | 通过，输出 `[adoption-smoke] OK`。 |
| `python scripts/validate-governance.py --strict` | 通过，`0 error(s), 0 warning(s)`。 |
| `git diff --check` | 通过，无输出。 |
| `python scripts/check-same-commit.py --staged` | 临时暂存后通过：`7 处结构改动，对应 anatomy 已同变更集更新`；随后已取消暂存。 |
| `git clone --depth 1 https://github.com/AgentR1/Agent-R1.git /tmp/agent-r1-adoption-replay/Agent-R1` | 成功，测试 commit `85e0099`。 |
| `python scripts/adopt-existing-repo.py /tmp/agent-r1-adoption-replay/Agent-R1 --phase all --policy conservative --project-name agent-r1` | Agent-R1 replay 全阶段通过：discover 12 root entries；baseline 178 tracked files；scaffold copied 216；normalize moved 9, blockers 0；prove integrity ok, governance rc 0。 |
| `python scripts/check-adoption-integrity.py /tmp/agent-r1-adoption-replay/Agent-R1` | 通过：`present 178/178`。 |
| `python /tmp/agent-r1-adoption-replay/Agent-R1/scripts/validate-governance.py --strict` | 目标 repo 迁移后 governance 通过，0 error / 0 warning。 |
| `python -m py_compile scripts/adopt-existing-repo.py scripts/check-adoption-integrity.py lab/evals/adoption/run-adoption-smoke.py` | Agent-R1 report/ledger 更新后再次通过。 |
| `python lab/evals/adoption/run-adoption-smoke.py` | Agent-R1 report/ledger 更新后再次通过，输出 `[adoption-smoke] OK`。 |
| `python scripts/validate-governance.py --strict` | Agent-R1 report/ledger 更新后再次通过，0 error / 0 warning。 |
| `git diff --check` | Agent-R1 report/ledger 更新后通过，无输出。 |
| `python scripts/check-same-commit.py --staged` | 临时 `git add -A` 后通过：`8 处结构改动，对应 anatomy 已同变更集更新`；随后已取消暂存。 |

## Subagent reports

无。

## Open issues / blockers

- v1 还没有处理受保护 root bytes 的自动收敛；遇到 `.env`、`wandb/`、`checkpoints/`
  等 protected root path 时，`normalize` 会 blocked 并写 phase log。
- Agent-R1 无轻量 native test command；本次 replay 验证 hash integrity 与 template governance，
  不验证 Agent-R1 runtime/training 行为。
- v1 normalize 是 imported-unit 策略；Agent-R1 的 docs/images/examples/recipes 被保守保存在
  `lab/code/imported/agent-r1/`，不是语义最优归档。

## Exact next steps

1. 如要提交，先 review `git diff`，再 commit `worktree-adopt-existing-repo` 分支。
2. 若要增强 v2，优先补 protected root path policy、semantic normalize policy 和更多 fixture。

## Do-not-forget

- Human 明确要求：最终要完全变成 template 形式；可以分步；每步要测试“不破坏”；
  human 最好不用参与其中。
- 对 existing repo 的迁移工具必须保护目标 repo：默认迁移分支/worktree、manifest、
  phase gate、不可判断即停。
