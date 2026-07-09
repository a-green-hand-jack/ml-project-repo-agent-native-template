# round 3 模板功能测试 交互式计划

> 复制到 `plans/<YYYYMMDD>-<topic>.zh.md`。这是 human 与 Claude Code 的协商界面：
> Claude 写初稿 → human 在文件里批注 → Claude 读 diff、收敛计划 → 每次采纳的修订做一个小 commit。
> 实现只在 scope / forbidden paths / verification 清楚后开始。

## 当前目标

为 `ml-project-repo-agent-native-template` 的功能测试提出「第三轮」范围，按优先级排序并给出理由，供 human 批注、拍板后再执行。

背景（截至本文写作时）：

- **Round 1**：迁移 ELF-template-case 案例进本模板；跑通 4 个 governance validator；本机 CPU-only 独立 re-clone `lillian039/ELF` 并重放 tiny 前向 smoke；探测 hook/permission 边界（`sudo`/`curl|sh`/受保护路径写入/`git push` 到 main 的 allow-with-flag 逻辑）；派生 5/15 个 subagent（`artifact-librarian`、`experiment-orchestrator`、`repo-doc-steward`、`branch-reporter`、`test-runner`）。见 `memory/current-status.md`。
- **Round 2**（与本文并行进行）：覆盖剩余 subagent（`checkpoint-writer`、`experiment-monitor`、`hook-maker-agent`、`interactive-plan-writer` 即本文档、`repo-researcher`、`session-boundary-agent`、`sub-agent-maker-agent`；`subagent-router-agent` 已完成并产出一份 launch packet）、抽样 1-2 个 `.claude/skills/*` 走 `Skill` 工具端到端调用。
- **仍未覆盖**：`.claude/skills/*` 的绝大多数（8 个 project-local skill 里只抽样了一两个）；`.claude/commands/*` 下 7 个 slash command（`checkpoint`、`experiment-watch`、`feature-split`、`paper-reproduce`、`pr-review`、`result-promote`、`weekly-maintenance`）**一次都没被调用过**；针对 evidence-chain / artifact-index 相关 validator 的**蓄意对抗性压测**，round 1 只做过一个（把 `claim-elf-source-identity` 改成 `status: supported` 但证据仍是 `log` 级，验证 FAIL 后立即 revert，见 `memory/current-status.md:68`）。

本文档只提出 round 3 的范围、优先级与理由，**不执行任何测试**——这是 interactive-plan-writer 角色的边界（只写 `plans/`）。

## 非目标

- 不在本文档内跑任何 validator / 派生 subagent / 调用 skill 或 command——那是下一步、human 批准 gate 之后的事。
- 不修复 round 1/2 已发现的模板问题（例如 `lab/docs/overview.md` 里悬空的 `code/docs/` 引用，见 `memory/current-status.md:92`）——沿用「先测试、不急着修模板本身问题」的既定策略（见 `memory/current-status.md:11`），除非 human 在批注里改变这个决定。
- 不判断这个 case 分支要不要 push 到远程 / 是否合并——这是独立于测试范围的 human 决定（`memory/current-status.md:94`、`:100`）。
- 不重复评估 round 1 已跑过的 4 个 validator 正常路径、5 个 subagent、ELF smoke replay，也不重复 round 2 正在做的 7 个 subagent + skill 抽样——round 3 只接手两轮都没碰过的表面，以及「只做过一次」因而覆盖不足的表面（对抗性压测）。

## Branch / worktree

沿用当前 worktree `.claude/worktrees/case+elf-template-replay/`，分支 `worktree-case+elf-template-replay`——这是同一条 case 测试线的延续，不建议为 round 3 另开 worktree（除非某个 P2 探针本身需要一次性、可丢弃的分支来做破坏性变更，见任务树 P1-3/P2 的说明）。

## Linked issue / PR

无。这个 case 分支不预备合并回 `main`（`memory/current-status.md:94`），round 3 同样只是本地功能测试记录。

## Allowed paths

- 本 plan-writer 角色：仅 `plans/20260709-round3-template-functional-test.zh.md` 本身。
- 一旦 human 批准进入执行阶段（超出本文档范围）：预期会写 `lab/docs/audits/**`（探针报告 / 适配后的 stress-probe catalog）、`memory/current-status.md`、`lab/research/{claims,evidence,experiment-ledger}.yaml`（如需登记新证据/探针发现）、`lab/artifacts/*.yaml`（如探针涉及新 artifact 登记）——这些是执行阶段的范围，不是本 plan-writer 现在能碰的。

## Forbidden paths

- `.agent/action-boundary.md` 里的硬边界原样适用：`lab/data/**`、`lab/runs/**`、`lab/models/**` bytes、`checkpoints/**`、`wandb/**`、`lab/infra/private/**`、`.env`。
- 本 plan-writer 角色额外边界：`plans/` 之外任何路径都不碰（含源码、`.claude/settings.json`、hooks、`ANATOMY.md` 等）——哪怕是为了「顺手」验证某个探针猜想。
- 执行阶段默认边界（待 human 在批注区确认或调整）：任何会触发 `.agent/human-gates.md` 列出动作的探针（真开 PR、真 push 到 main、真 promote 成 paper claim、真 kill/启动作业）一律只能是**演练/起草**，不能真正触发；涉及 `pr-review`、`result-promote`、`checkpoint`（写路径可能touch checkpoint-adjacent 概念）等 command 的探针必须只对**全新、一次性、明显是测试用的 synthetic claim/evidence/PR 目标**操作，绝不能碰真实的 ELF claim/evidence 或触发真实 `gh pr create`。

## 任务树

- [ ] **P0 — 补完 evidence-chain 对抗性探针（最高性价比：零新增机制，复用 round 1 已验证安全的「临时改字段 → 跑 validator → 断言 FAIL → 立即 revert」模式，读 `scripts/validate-governance.py:80-138` 已确认这 4 条分支目前只被验证过 1/4）**
  - [ ] P0-1：某 claim `status: partial` 但 `evidence: []`（无证据）→ 期望 `overclaim：... 但无 evidence 支撑`（对应 `validate-governance.py:127-128`，round 1 未测）
  - [ ] P0-2：某 claim 的 `evidence:` 列表指向一个不存在的 evidence id → 期望 `claim ... 引用未知 evidence`（`validate-governance.py:123-125`，未测）
  - [ ] P0-3：某 evidence 的 `supports_claim` 指向不存在的 claim id → 期望 `evidence ... 的 supports_claim 指向未知 claim`（`validate-governance.py:114-115`，未测）
  - [ ] P0-4：某 claim `verified_by_fresh_reviewer: true` 但没有一条 `grade: paper-claim` 且自身 `verified_by_fresh_reviewer: true` 的 evidence → 期望 overclaim 报错（`validate-governance.py:131-138`，未测；这是四条 overclaim 分支里唯一涉及 paper-grade 的一条，值得单独确认）
  - [ ] P0-5：`.gitignore` 临时删掉一个受保护 token（如 `wandb`）→ 期望 `.gitignore 未提及受保护路径：wandb`（`validate-governance.py:48-50`，未测）
  - [ ] P0-6：`git add`（不 commit）一个占位 `foo.ckpt` 或 `lab/runs/dummy.bin` 路径 → 跑 validator（用的是 `git ls-files`，staged 即可见）→ 期望 `权重 bytes 被误加进 Git` 或 `受保护目录 bytes 被误加进 Git` → 然后 `git reset` + 删除占位文件复原（`validate-governance.py:141-161`，未测）
- [ ] **P1 — 补完另外三个 validator 的对抗性探针（需要先读脚本源码，比 P0 多一步，但仍是同一种自包含的 mutate→revert 模式，不需要新 subagent/skill/command 基础设施）**
  - [ ] P1-1：读 `scripts/check-agent-harness.py` 全文，挑 2-3 个具体 mutation（如临时删掉某目录的 `AGENTS.md` 或 `ANATOMY.md`、往根目录扔一个不在白名单里的文件）→ 跑 validator → 断言按预期报错 → revert。round 1/2 只验证过正常路径（0 error），从未验证过它真的会拦坏结构。
  - [ ] P1-2：读 `scripts/check-anatomy-drift.py` 全文，构造 1-2 个具体漂移（`related_files` 指向一个已改名/删除的文件；某 `ANATOMY.md` 临时撑到 120 行以上）→ 跑 validator → 断言报错 → revert。
  - [ ] P1-3：`scripts/check-same-commit.py --staged` 的反例：临时新增一个子目录或移动一个文件（结构性改动）但**不**同 commit 更新对应 `ANATOMY.md`，跑该脚本，断言它拦下来（round 1 只验证过「已同步更新」的正例，见 `memory/current-status.md:67`）→ revert。
  - [ ] P1-4：核查一个本轮读代码时发现、尚未确认的疑点——`lab/research/release-gates.yaml` 与 `regression-matrix.yaml` 在 `lab/research/ANATOMY.md:24` 被描述为「汇总 claims + regression-matrix，产出可否交付的判定」，但通读 `scripts/validate-governance.py` 全文后**没有找到任何引用这两个文件的检查代码**。round 3 应确认：这是刻意的「人工判断面、不需要机器强制」的设计，还是一个真实的 validator 覆盖缺口。若是后者，记为发现，不擅自修。
- [ ] **P2 — 7 个 slash command：至少每个跑一次（或做静态审阅），有具体拆分（见「未解决问题」Q1，需人拍板执行方式）**
  - [ ] P2-1：低风险、只读/观察类 command 优先做端到端调用（候选：`/experiment-watch`、`/weekly-maintenance`——待确认它们是否触发任何写操作）
  - [ ] P2-2：涉及人类闸门动作的 command（`/pr-review` → `gh pr`、`/result-promote` → promote 成 paper claim、`/checkpoint` → checkpoint 生命周期、`/paper-reproduce`、`/feature-split`）：先做静态审阅（读 `.claude/commands/<name>.md`，检查它引用的路径/skill/subagent 是否在本 repo 这一代真实存在、逻辑是否自洽），只有 human 明确批准且提供一次性 synthetic 目标（假 claim/假 PR 场景）时才做真实端到端调用；否则只记录「静态审阅通过/发现 X」。
- [ ] **P3 — 剩余 project-local skill 的端到端覆盖（依赖 round 2 结果，round 3 开工时先核对 round 2 实际抽样了哪几个，避免重复）**
  - [ ] P3-1：round 3 启动时先读 round 2 落盘的 `memory/current-status.md` / `memory/session-tree.md`，确认哪些 skill 已端到端跑过
  - [ ] P3-2：对剩余未跑的 skill，用低风险/synthetic 输入各跑一次 `Skill` 工具调用，记录实际 vs. 声明的 `Declared Outputs`/`Validators` 是否一致
- [ ] **P4 — 把 P0/P1 的探针沉淀成一份适配后的 stress-probe catalog（可选，视 human 是否想要持久化产物）**
  - [ ] P4-1：参考 `~/Projects/ELF-template-case/.harness/skills/skills/research-template-case-harness-test/references/stress-probe-catalog.md`（旧 v1 `.harness` 世代方法论，15 行 probe matrix + 统一报告格式），逐行判断是否适用于本模板：
    - **可直接映射、值得移植**：evidence link drift → P0-2/P0-3；evidence provenance → P0-1/P0-4；anatomy drift → P1-2/P1-3；generated/private leakage → P0-5/P0-6；missing component file → P1-1
    - **本模板没有对应机制、建议明确记为「不适用」而非沉默丢弃**：template mode（`.harness/manifest.yaml` 的 complete/partial 概念，本模板没有「模式」）、component activation/reactivation `--force`（本模板没有组件激活脚本）、branch CD boundary（旧方法论讲的是 harness 自身 template 分支的同步，不适用于下游 case 仓库）
    - **本模板里降级成纯文档、非 validator 对象，已在 round 1 的迁移决策里记录过（`memory/current-status.md:52-54`）**：source visibility（对应旧 `source-visibility.yaml`，新模板落地为 `lab/docs/reference/provenance.md`，纯文档不校验）——不需要新探针，只需在 round 3 报告里引用这条既有决策即可
    - **需要重新措辞成本模板语言的**：experiment closure → 对应 `lab/research/experiment-ledger.yaml` 字段完整性；artifact index → 对应 `lab/artifacts/*-index.yaml` 与 `.agent/artifact-policy.md` 的软约束（无 validator 强制，靠 `artifact-librarian` 纪律，探针预期结果是「不会被拦，这是已知的软约束，非 bug」）
  - [ ] P4-2：产出 `lab/docs/audits/stress-probe-catalog.md`（新模板版本），用旧目录里同款「Mutation / Expected / Commands / Actual / Classification / Follow-up」报告格式记录 P0/P1 每条探针的真实运行结果

## Human 批注区

（待 human 批注）

## 当前决策

- round 3 的核心排序原则：**同一脚本内「补完尚未测过的分支」（P0）> 同类但需要先读源码的「另外三个 validator 的反例」（P1）> 需要新交互面（slash command 的 live invocation 是否可行）或依赖 round 2 结果才知道剩多少的（P2/P3）> 可选的沉淀产物（P4）**。理由：P0/P1 都是对已经存在、round 1/2 已验证过「正例」的机制做「反例」补测，零新增基础设施、风险可控（沿用 round 1 证明过安全的 mutate→assert→revert 模式），信息增量最大（4 个 validator 目前只有 1 个被反例测过、且只测了其中一条分支）。P2/P3 价值同样真实，但要么依赖一个还没确认的能力（subagent 能否程序化触发 slash command，见未解决问题 Q1），要么依赖并行进行中的 round 2 的实际产出（避免重复劳动），排在后面更稳妥。
- P4（沉淀成正式 catalog 文档）标记为可选：如果 human 只想要「这轮测试过什么、结果如何」的记录，P0-P1 的探针本身在执行时按现有 round 1/2 的习惯写进 `memory/current-status.md` 的 Commands+results 表即可，不一定需要单独建立一份新的 `stress-probe-catalog.md`。是否值得建这份持久文档，留给 human 在批注区拍板（见未解决问题 Q2）。
- 默认继续遵守「先测试、不修模板」的既定策略：P0-P4 任何探针如果意外发现真实的 validator/文档缺口（例如 P1-4 的 release-gates 疑点），一律只记录、不顺手修复。

## 未解决问题

1. **Q1 — slash command 能否被 subagent 程序化触发、还是必须真人在交互式主线程里敲 `/xxx`？** 如果只能后者，P2 的「端到端调用」部分需要改成「human 亲自跑 + agent 事后审阅日志」的协作模式，而不是 agent 独立执行；如果前者可行（例如某种 `SlashCommand` 工具对派生 subagent 也开放），P2 可以照搬 P0/P1 的自包含探针模式。这直接决定 P2 的排期与执行方式，需要 human 确认。
2. **Q2 — 对抗性压测要不要照搬旧 `stress-probe-catalog.md` 的方法论，多大程度上？** 已确认旧文件路径与内容（见任务树 P4-1 的映射表）：15 行 probe matrix 里约 5-6 行能直接映射到本模板的 4 个 validator，3 行（template mode / component activation-reactivation / branch CD boundary）对应的机制本模板压根没有，1 行（source visibility）已经在 round 1 迁移时降级为纯文档、非 validator 目标。建议方案是「记录映射表 + 只对真实存在的机制写新探针」（本文档任务树已经这样做），而不是逐字复制旧 15 行、把不适用的也跑一遍占位。但这是我（plan writer）的判断，需要 human 确认是否认可这个取舍，还是希望保留旧目录里更完整的仪式感（例如哪怕不适用也留一行「N/A + 为什么」）。
3. **Q3 — round 3 该不该等 round 2 完全收尾再开工？** P0/P1 是瞬时 mutate→revert，不改任何持久状态，理论上可以立刻并行做，不会和 round 2 冲突；但如果 P0/P1 的执行也要往 `memory/current-status.md` 追加一行 Commands+results，就有和 round 2 同时写同一个文件的编辑竞态风险。是希望 round 3 的 P0/P1 现在就能开始（只是先不碰 `current-status.md`，探针结果先记别处，回合结束后再合并一次），还是严格等 round 2 关掉这个 worktree 的写权限后再开工？
4. **Q4 — P2 里涉及人类闸门的 command（`/pr-review`、`/result-promote`、`/checkpoint`）要不要做真实端到端调用？** 本文档默认只做静态审阅 + 需要 human 提供 synthetic 目标才做真实调用（见 Forbidden paths）。如果 human 觉得静态审阅信息量不够、想要真实调用，需要明确给出一次性、绝不会被误当真实 claim/PR 的测试目标（例如一个专门为测试造的 `claim-test-round3-throwaway`），并且明确知道这条 claim/evidence 事后要不要清理。
5. **Q5 — P4（沉淀成正式 `lab/docs/audits/stress-probe-catalog.md`）要不要做？** 如果要做，落地位置、命名是否要跟旧仓库保持一致（`docs/audits/` vs 本模板的 `lab/docs/audits/`，命名已经天然不同因为目录结构不同），以及这份文档以后要不要长期维护（每次模板迭代都重跑一遍）还是只是本轮的一次性记录。

> 1. `slash command` 可以被 subagent 程序化触发(我很信任现在的SOTA coding agent的能力)
> 2. 

## 验证标准

本轮（plan 阶段）的验证标准：

- human 在本文件批注区留下明确反馈（认可 / 调整优先级 / 回答 Q1-Q5）。
- Q1-Q4 至少有初步方向后，才允许进入执行阶段；执行阶段本身的验证标准（每条探针的期望 exit code / 报错文案）已经写在任务树里，届时逐条核对「实际输出 == 期望输出」，任何不一致都要如实分类（模板真实 gap / 探针写错 / 预期本来就该是软约束不拦截）而不是含糊带过。
- 执行阶段完成后，`memory/current-status.md` 需要更新 Commands+results 表 + Open issues，格式延续 round 1/2 已经建立的表格惯例。

## 下一步

1. 等待 human 在本文档批注（尤其 Q1-Q5）。
2. 读批注 + `git diff`，收敛任务树的优先级与范围，更新本文档。
3. human 明确批准后，才把 P0（及视 Q3 答案而定的 P1）交给下一个执行 session/subagent 去真正跑；本 plan-writer 角色本身不执行。

## Plan revision log

- 2026-07-09 初稿（round 3 提案，基于 round 1/2 现状梳理 + 对 `scripts/validate-governance.py`、`lab/research/ANATOMY.md`、旧 `stress-probe-catalog.md` 的实读核对）。
