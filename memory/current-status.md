# current-status.md

> **活文件**。这是当前状态的单一真相源。每次 session 结束、compact 前、完成小目标时更新。
> fresh session 应能只读本文件 + `session-tree.md` 就接续工作。

## 当前 objective

收尾 `ml-project-repo-agent-native-template` v1 治理面：补齐 main 上的活状态文件，核对模板功能测试覆盖与
`.reference-docs` 覆盖关系，并把必要结论落盘。

## Constraints

- 遵守 `AGENTS.md` / `.agent/AGENTS.md` / `.agent/action-boundary.md`。
- 不编辑或删除 `lab/data/**`、`lab/runs/**`、`lab/models/**` bytes、`checkpoints/**`、`wandb/**`、
  `lab/infra/private/**`、`.env`。
- 不启动/kill/restart 长训练或远端作业。
- 不做 PR / merge / release / 远端基础设施改动；本轮只做本地文档与状态修复。
- 结构改动若涉及 anatomy/ledger，必须同变更集同步对应记录。

## Files inspected

- `AGENTS.md`
- `.agent/AGENTS.md`
- `ANATOMY.md`
- `memory/current-status.md`
- `memory/session-tree.md`
- `memory/ANATOMY.md`
- `.claude/ANATOMY.md`
- `lab/ANATOMY.md`
- `lab/research/ANATOMY.md`
- `DESIGN.md`
- `README.md`
- `PROJECT.md`
- `DECISIONS.md`
- `.reference-docs/claude_code_optimization_spirit_zh.md`
- `.reference-docs/claude_code_practice_for_ai_phd_zh.md`
- `lab/docs/audits/README.md`
- `lab/docs/audits/agent-native-template-functional-test-report.md`
- `lab/docs/audits/stress-probe-catalog.md`
- `lab/docs/audits/stress-test-ledger.yaml`
- `.claude/skills/template-stress-test/SKILL.md`
- `.claude/skills/template-stress-test/references/probe-surface-catalog.md`
- `scripts/validate-governance.py`
- `scripts/check-agent-harness.py`
- `.github/workflows/governance.yml`

## Files modified

- `memory/current-status.md`：把 main 上的空模板替换为当前真实状态与下一步。
- `memory/session-tree.md`：把空模板替换为当前无并行子 session 的收尾状态。
- `.reference-docs/implementation-coverage-note.md`：新增参考文档覆盖说明，记录当前实现是工程化超集以及有意不逐字实现的项。
- `README.md`：更新 `.reference-docs/` 描述，提到覆盖说明文档。
- `DESIGN.md`：更新来源说明和决策表，避免仍暗示 `.reference-docs/` 只有两份文件。

## Decisions

- main 上此前的 `memory/current-status.md` / `memory/session-tree.md` 是空骨架，不足以作为 fresh session
  接续入口；本轮直接补齐，不再要求下一位 agent 通过 case worktree 和 git log 还原近期状态。
- `lab/docs/audits/agent-native-template-functional-test-report.md` 是 ELF case round 1-3 原样 promote
  的历史报告；round 4 的后续修复不回填正文，已在 `lab/docs/audits/README.md` 与
  `stress-test-ledger.yaml` 说明。
- 当前模板不是逐字实现 `.reference-docs` 里的每个示例 hook / prompt / 可选机制；更准确地说，它覆盖了
  两份参考文档的核心控制面，并在多个关键面做了工程化超集：validators、CI、same-commit rule、
  parser-based hook、branch-aware push guard、中文审阅安全网、recipe/eval 流水线、template stress test
  能力。
- 参考文档中明确标为 TODO 或示例性质的部分（如完整 paper writing workflow、formatter PostToolUse hook、
  组件激活/`.harness` CLI）不作为 v1 必须逐字实现项；当前 repo 用 `deliverables/paper/` writing
  contract、`paper-reproduce` command、human gate 与 evidence chain 覆盖最小必要边界。

## Commands + results

| command | 结论 |
| --- | --- |
| `git status --short --branch` | main 与 origin/main 对齐；`.claude/worktrees/` 在主仓库视角显示为 untracked，但它实际承载 ELF case branch 的本地 worktree checkout。 |
| `git log --oneline --decorate -n 20` | 最新为 `f2f1dee`，已把 template stress test 沉淀进 main。 |
| `find .reference-docs -maxdepth 2 -type f -print` | 参考文档原有两份：spirit + practice；本轮新增 coverage note。 |
| `rg -n "^#{1,4} " .reference-docs/*.md` | 已按参考文档章节核对当前实现覆盖面。 |
| `python scripts/validate-governance.py --strict` | OK — check-agent-harness / check-anatomy-drift / governance 均 0 error、0 warning。 |
| `python scripts/check-same-commit.py --staged`（未 stage 时） | OK — 0 处结构改动；仅作为基线，信号有限。 |
| 临时 `git add` 本轮 5 个路径 → `python scripts/check-same-commit.py --staged` → `git restore --staged ...` | OK — 1 处结构改动，对应 anatomy 要求满足；已 unstage 回普通工作树改动。 |
| `git diff --check` | OK — 无 whitespace error。 |
| `git status --short` | 本轮 4 个 tracked 文件修改 + 1 个新增 coverage note；`.claude/worktrees/` 仍未跟踪且未改动。 |

## Subagent reports

本轮未派生 subagent。原因：任务是 main 活状态修复 + 文档覆盖核对，直接读文件和运行 validator 足够。

## Open issues / blockers

- `.claude/worktrees/case+elf-template-replay/` 是 `worktree-case+elf-template-replay` branch 的本地
  worktree checkout（远端也有 `origin/worktree-case+elf-template-replay`）。它在 main 的 `git status`
  里显示为 untracked 是因为 worktree 被放在主仓库目录内，不代表它不是 template repo 的 branch。
  是否保留这个本地 checkout、移到 repo 外、或仅保留远端 branch，应由 human 决定。本轮不删除。
- ELF case 的完整报告正文只到 round 3；round 4 结论在 ledger/README 中，不回填报告正文。这是有意保留
  promote 原文的选择，但 fresh reader 需要知道以 ledger 为最新摘要。
- v1 功能覆盖已经足够进入“按变更触发压力测试”的维护模式；未来新增 validator/hook/subagent/skill/command
  时，按 `.agent/template-stress-test-policy.md` 决定测试深度。

## Exact next steps

1. 向 human 汇报覆盖结论、修改文件和剩余风险。
2. 等 human 决定是否提交本轮文档/状态修复。
3. `.claude/worktrees/case+elf-template-replay/` 这个本地 worktree checkout 是否保留、移动或清理，单独等 human 指令。

## Do-not-forget

- 需要 human 介入/过目的输出默认中文。
- `.claude/worktrees/case+elf-template-replay/` 是 ELF case branch 的 worktree，不是 main 的当前状态源。
- `.reference-docs/implementation-coverage-note.md` 是覆盖说明，不替代两份参考文档本身。
