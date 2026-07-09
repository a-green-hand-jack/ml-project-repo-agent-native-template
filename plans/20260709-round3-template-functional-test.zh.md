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

Q1-Q5 已由 human 批注给出方向（见「未解决问题」区的引用块）。汇总：

- Q1：subagent 可以程序化触发 slash command（human 信任现有 SOTA coding agent 能力）——P2 不需要
  「human 亲自跑 + agent 事后审阅日志」的降级方案，可以照搬 P0/P1 的自包含探针模式。
- Q2：对抗性压测尽量全面，照搬旧 `stress-probe-catalog.md` 方法论——采纳「保留完整仪式感」的取舍，
  不适用的行也要显式记 `N/A + 原因`，而不是静默丢弃（P4-1 的映射表已经是这个形态，只是要在最终产出里
  把 N/A 行也留着，不要因为「不适用」就删掉）。
- Q3：round 3 等 round 2 完全收尾再开工——round 2 已经在 2026-07-09 完成（见
  `memory/current-status.md`、本报告 F10-F14），round 3 现在可以开工。
- Q4：要做真实端到端调用；且**任何需要 human 介入/过目的产出都要用中文**（PR 标题/正文、静态审阅
  报告等）——这条超出 round 3 本身，是对整个协作模式的补充规则，见下方「Track 0」。
- Q5：要沉淀，且要按本模板自己的形式沉淀，产出应该是**一组文档**而不是一份；human 的心智模型是
  「模板每次做出不同程度的调整，都应该对应不同程度的压力测试」，而且以后会有更多 case——这已经不是
  「round 3 的一个可选任务」，而是要把「压力测试」本身变成模板的一个持久能力。见下方「Track 3」，
  这部分设计需要 human 先对整体形状拍板，再进入实现。

## Track 0 — 人类可读产出默认中文（补充规则，适用于本计划之后的所有轨道）

human 明确要求：**PR 标题/正文、任何需要 human 过目批准的静态审阅报告，都要用中文**——这是对已有
`.agent/behavior-contract.md`「文档默认语言」一节的补充：那一节列了「报告、review、memory 状态文件、
ANATOMY 正文、commit message 正文」，但**没有明确列出 PR/issue 标题与正文**，而 PR #1（F2 修复）
的标题和正文实际上是英文写的——这是一个真实的疏漏，需要在扩大 F11 修复范围时一并补上 doctrine 措辞。

human 还提出一个可选机制：**开一个小的 sub-agent、用便宜的模型（如 haiku）作翻译器**。两种方案都可行，
不互斥：

- **方案 A（默认、零新增机制）**：起草 PR/报告时直接用中文写，不英文起草再翻译——这对*新写*的内容
  零成本，本计划的 Track 1-3 所有产出默认走这条路。
- **方案 B（安全网，捕捉遗漏）**：一个轻量翻译 subagent/skill，用便宜模型扫描即将面向 human 的产出
  （PR 正文、`human/reviews/`、`lab/docs/audits/` 报告），发现非中文内容就翻译或提醒——用于兜底
  「写的时候忘了」这种情况（就像这次 PR #1 那样）。

**待 human 确认**：是否需要方案 B 作为常设机制（例如做成一个 `.claude/hooks/` PostToolUse advisory，
或一个 `.claude/skills/zh-review-gate/` skill），还是方案 A（直接用中文写 + 人工偶尔抽查）已经够用。
如果需要方案 B，这本身也是一次模板能力变更，应该走 Track 3 的「变更幅度 → 压力测试深度」映射来验收。

## Track 1 — 扩大 F2 修复范围到 F11 发现的其余实例（独立于 round 3，off `main`）

repo-researcher（round 2）发现的未修实例，按 human「扩大修复范围」的批注，全部纳入：

- `.githooks/pre-commit:9` —— 裸相对路径 `python scripts/check-same-commit.py --staged`。
- `.claude/hooks/pre_compact_memory_check.py:14` —— `STATUS_FILE = "memory/current-status.md"` 裸路径。
- `.claude/hooks/subagent_report_index.py:18-19` —— `REPORTS_DIR`/`INDEX_FILE` 裸路径。
- `.claude/settings.example.json` —— 仍是修复前的裸路径版本，会把 bug 传播给新 fork 项目。
- `.claude/hooks/pre_tool_guard.py` 的 `_current_branch()` —— `git branch --show-current` 没有传 `cwd`，
  cwd 漂移时可能悄悄检查错仓库分支（hook-maker-agent 发现）。
- `hook-maker-agent` 起草的 `nested_repo_cd_guard.py`（暂存在本 case 分支的
  `.claude/hooks/drafts/`）—— human review 后决定是否启用；如果启用，也应该在这次修复里一并接线。

执行方式沿用上次的模式：独立 subagent 在 off `main` 的新分支上做修复 → 跑 validator →
**PR 标题/正文用中文**（吸取 Track 0 的教训）→ human 视情况批准 merge。

## Track 2 — F2 修复的独立复验

在这个仍在运行的 session 里，主 session 的 hook 配置已确认是启动时缓存、不会中途刷新（见 F10）。
两步走，先低成本再升级：

1. **先试：派一个全新的 subagent（Agent 工具新起的进程）**，让它 `cd` 进 `lab/code/external/ELF`
   之类的嵌套仓库，看它的 hook 配置是不是也是「主 session 启动时」就固定的，还是 subagent 进程有
   自己独立、更新鲜的加载时机。如果 subagent 级别的新鲜度就足够验证修复生效，就不需要劳烦 human 开一个
   全新的顶层 session。
2. **如果第 1 步也复现旧 bug**：说明只有一个真正全新的顶层 Claude Code session 才能验证，需要 human
   自己开一个新 session（不是这个对话里的 `/clear`）来做这个复验，我会把复验步骤写清楚交接。

## Track 3 — 把「模板压力测试」沉淀成一个持久能力（提案，需要 human 先对形状拍板）

这是这一轮反馈里最大的一块，直接回应 Q5。core idea：**压力测试不该是这次 case 分支里的一次性产出，
应该变成模板自己的一部分**，可以被未来的模板调整反复触发，也可以接纳未来更多的 case。提案形状
（仿照旧 `.harness` 世代的 `research-template-case-harness-test` skill + `stress-probe-catalog.md`，
但适配到新模板自己的 `.claude/skills/` + `lab/docs/` + `.agent/` 约定）：

1. **新 skill**：`.claude/skills/template-stress-test/SKILL.md`——把这次从头到尾做的事情（挑/建一个
   case → 迁移进模板结构 → 跑 governance validator → 演练 subagent/skill/command → 对抗性探针矩阵 →
   写发现 → 决定修复范围 → 独立复验）formalize 成可重复的流程，供以后任何一次模板大改之后照做。
2. **探针目录**：`.claude/skills/template-stress-test/references/stress-probe-catalog.md`——本轮
   P4-1 已经做的映射表（旧 15 行 probe matrix → 新模板 4 个 validator + N/A 说明）作为起点，长期维护，
   每次模板新增机制（新 validator/新 hook/新 subagent 类别）就补一行探针。
3. **变更幅度 → 测试深度 的映射 doctrine**：新增一份 `.agent/` doctrine（暂定
   `.agent/template-stress-test-policy.md`，或并入 `anatomy-protocol.md`/`repo-editing-guardrails.md`），
   给出类似这样的分级（具体阈值待 human 确认）：
   - 纯文档/措辞改动 → 不需要压力测试。
   - 新增/改一个 subagent、skill、command → 只需要针对该表面的定向 smoke（不需要整个 case 回放）。
   - 改 validator、hook、`settings.json` 权限面 → 需要完整的对抗性探针矩阵（本轮 P0/P1 这种规模）。
   - 改 `lab/`/`deliverables/`/`memory/` 的结构形状本身 → 需要完整的 case-based 回放（本轮 round 1-3
     这种规模），且应该用**不止一个** case 来验证（见下条）。
4. **多 case 登记账**：一份 ledger（暂定 `lab/docs/audits/stress-test-ledger.yaml` 或
   `memory/` 下某个文件），记录「哪个模板 commit，被哪个 case，测到什么深度，什么时候，结果如何，
   报告在哪」。ELF 是第一条记录；以后加新 case 时registry 增长，而不是每次都散落成独立、互相不知道
   彼此存在的 case 分支。
5. **case 分支命名/流程约定**：把「`case/<name>` 分支 + worktree + 迁移 + 报告」这一整套本轮走出来的
   流程写成文档（可能是 `template-stress-test` skill 本身的一部分），让以后加新 case 的人（或 agent）
   不用从头摸索。

**这是提案，不是既成设计**——需要 human 确认：

- 形状本身是否认可（skill + catalog + policy + ledger 四件套，还是想要更简单/更复杂的形态）？
- 落地位置是否认可（`.claude/skills/`、`.agent/`、`lab/docs/`）？
- 这次要不要现在就动手实现（走一次它自己的 Track 1 式流程：新分支 off `main`、subagent 实现、PR、
  中文正文），还是先只把这份提案定稿，实现留到下一次专门的时间？
- 变更幅度分级的具体阈值/例子是否需要调整？

## 当前决策

- round 3 的核心排序原则：**同一脚本内「补完尚未测过的分支」（P0）> 同类但需要先读源码的「另外三个 validator 的反例」（P1）> 需要新交互面（slash command 的 live invocation 是否可行）或依赖 round 2 结果才知道剩多少的（P2/P3）> 可选的沉淀产物（P4）**。理由：P0/P1 都是对已经存在、round 1/2 已验证过「正例」的机制做「反例」补测，零新增基础设施、风险可控（沿用 round 1 证明过安全的 mutate→assert→revert 模式），信息增量最大（4 个 validator 目前只有 1 个被反例测过、且只测了其中一条分支）。P2/P3 价值同样真实，但要么依赖一个还没确认的能力（subagent 能否程序化触发 slash command，见未解决问题 Q1），要么依赖并行进行中的 round 2 的实际产出（避免重复劳动），排在后面更稳妥。
- P4（沉淀成正式 catalog 文档）标记为可选：如果 human 只想要「这轮测试过什么、结果如何」的记录，P0-P1 的探针本身在执行时按现有 round 1/2 的习惯写进 `memory/current-status.md` 的 Commands+results 表即可，不一定需要单独建立一份新的 `stress-probe-catalog.md`。是否值得建这份持久文档，留给 human 在批注区拍板（见未解决问题 Q2）。
- 默认继续遵守「先测试、不修模板」的既定策略：P0-P4 任何探针如果意外发现真实的 validator/文档缺口（例如 P1-4 的 release-gates 疑点），一律只记录、不顺手修复。

## 未解决问题（Q1-Q5 已获 human 批注，状态见下；新增 Q6-Q9 待确认）

1. **Q1 — slash command 能否被 subagent 程序化触发？** ✅ 已确认：可以，human 信任现有 SOTA coding
   agent 能力。P2 照搬 P0/P1 的自包含探针模式，不需要「human 亲自跑」的降级方案。
2. **Q2 — 对抗性压测要不要照搬旧 `stress-probe-catalog.md` 的方法论？** ✅ 已确认：要尽量全面，
   不适用的行也要显式留 `N/A + 原因`，不要因为「不适用」就静默丢弃。
3. **Q3 — round 3 该不该等 round 2 完全收尾再开工？** ✅ 已确认：等 round 2 收尾——round 2 已于
   2026-07-09 完成（见 `memory/current-status.md`、报告 F10-F14），round 3 现在可以开工。
4. **Q4 — 涉及人类闸门的 command 要不要做真实端到端调用？** ✅ 已确认：要做端到端测试；额外规则：
   任何需要 human 介入的产出（含 PR）都要用中文——已展开为「Track 0」，需要 human 再确认是否要方案 B
   （翻译 subagent 安全网）常设化。
5. **Q5 — P4 要不要做？** ✅ 已确认：要做，而且要扩大成一个持久能力（不只是一份文档）——已展开为
   「Track 3」，需要 human 对提案形状拍板（见 Track 3 末尾的 4 个待确认项）。

> 1. `slash command` 可以被 subagent 程序化触发(我很信任现在的SOTA coding agent的能力)
> 2. `对抗性压测`可以照搬`stress-probe-catalog.md 的方法论`.我希望压力测试是尽可能全面,免得真实的project上问题一大堆
> 3. round3 等 round2 完工了再开工
> 4. 需要做端到端测试,而且pr 也要写成中文的(因为我英语不好,所以,凡是需要让我介入的部分都应该写中文.这里甚至可以开一个小的sub-agent或者什么别的方案;用一个便宜的模型,作为翻译器)
> 5. 需要沉淀,需要根据本模板的形式来沉淀;这个文档应该变成一组文档.我理解每对template进行一次大的调整,我们都需要进行压力测试.或者说,进行不同程度的调整都要对应不同程度的压力测试.甚至我们后面还会添加更多的case 来做压力测试.

6. **Q6（新）— Track 1/2/3 的执行顺序？** 建议顺序：Track 1（F11 修复，off `main`，风险最低、范围最
   明确）→ Track 2（F2 复验，先用 subagent 试，不行再交给 human 开新 session）→ Track 3 形状拍板
   （human 决策，不需要执行资源）→ Track 3 落地（如果 human 批准现在做）与 round 3 本体（P0-P4）
   可以并行，因为一个改 `main`、一个改 case 分支，互不冲突。是否认可这个顺序？
7. **Q7（新）— Track 0 的方案 B（翻译 subagent 安全网）要不要现在就做？** 还是先只用方案 A（直接
   中文起草），方案 B 留到真的发现「又忘了写英文」的时候再补。
8. **Q8（新）— Track 3 现在就实现，还是先定稿提案、之后再挑时间实现？** 这是一个模板能力变更，
   体量不小（skill + catalog + policy + ledger 四件套），如果现在做，会占用相当篇幅的执行时间。
9. **Q9（新）— round 3 本体（P0-P4）现在开工，还是等 Track 1/2/3 的决策都有着落之后再开工？**
   P0-P4 在 case 分支里做，理论上和 Track 1/2/3（在 `main` 或需要 human 决策）互不阻塞，可以立刻开工。

> 6. 认可这个顺序
> 7. 现在就做
> 8. 先定稿提案,后面在实现,现在template还在第一版本,这件事情不是很着急
> 9. 立刻开工

## 验证标准

本轮（plan 阶段）的验证标准：

- human 在本文件批注区留下明确反馈（认可 / 调整优先级 / 回答 Q1-Q9）。
- Track 1-3 与 round 3 本体（P0-P4）各自的验证标准已在对应章节写明；执行阶段完成后统一更新
  `memory/current-status.md` 的 Commands+results 表 + Open issues，格式延续 round 1/2 已经建立的
  表格惯例。

## 下一步

1. 等待 human 对本次更新（Track 0-3 + Q6-Q9）的批注。
2. 读批注 + `git diff`，收敛范围，可能需要的话把 Track 3 拆成独立的 plan doc（如果 human 觉得体量
   已经超出「round 3」这个标题该装的范围）。
3. human 明确批准后，才开始真正执行：Track 1/2 走 subagent + PR 流程；round 3 本体（P0-P4）走
   mutate→assert→revert 探针；Track 3 视 Q8 答案决定现在做还是定稿后另找时间做。本 plan-writer /
   本轮回应角色本身不在 human 批准前执行任何一项。

## Plan revision log

- 2026-07-09 初稿（round 3 提案，基于 round 1/2 现状梳理 + 对 `scripts/validate-governance.py`、`lab/research/ANATOMY.md`、旧 `stress-probe-catalog.md` 的实读核对）。
- 2026-07-09 第二版（本次）：收敛 human 对 Q1-Q5 的批注；新增 Track 0（人类可读产出默认中文）、
  Track 1（扩大 F2 修复到 F11 其余实例）、Track 2（F2 独立复验）、Track 3（把压力测试沉淀成模板
  持久能力的提案）；新增 Q6-Q9 待 human 拍板。尚未执行任何一项——仍在等待 human 批准。
