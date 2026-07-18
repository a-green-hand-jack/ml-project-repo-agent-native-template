# #83 ELF case 端到端验证 + 变异压测：刷新方案 交互式计划

Status: draft · 2026-07-18 · ref: 方案设计定稿（human「按默认走」采纳全部 6 项默认）；正式 approved + case 分支创建留待执行阶段 kickoff

> 这是 human 与 Claude Code 的协商界面：agent 写初稿 → human 在文件里批注 → agent 读 diff、
> 收敛计划 → 每次采纳的修订做一个小 commit。**本 plan 只覆盖「执行前的刷新方案」的设计与决策
> 收敛，approved 后才移交执行**——本轮不 clone、不建 case 分支、不跑 replay、不动任何 case 内容。
> 状态锚点（上面一行）+ `memory/doc-lifecycle.yaml` 登记，语义见 `plans/ANATOMY.md`。

## 当前目标

给 issue #83（#82 的原生 sub-issue）设计一份**可执行、边界清楚、接进既有
`template-stress-test` 机器**的 ELF case 刷新方案，供 human 批注定稿。核心是：用真实外部 ML
项目 case（`lillian039/ELF`）对**当前 main** 重跑一次 `full-case-replay`，验证自旧 case 以来
新增的约 4 万行治理机制在真实 case 上确实生效，产出一份干净的 v2 baseline，并把旧 ledger 条目
标 `superseded`。

**动机——为什么旧 case 已过时（本 plan 的核心理由）**：

- `lab/docs/audits/stress-test-ledger.yaml` 里 `id: elf-template-case-replay` 条目
  `status: complete`，但 `template_commit_range` 停在 `fc18318..18281c1`（2026-07-09）。
- 此后 main 新增大量治理机制，旧 case **从未测过**它们，包括（非穷举）：
  - 新 validator：`check-provenance-chain.py`、`check-doc-lifecycle.py`、
    `check-capability-catalog.py`。
  - template-sync 事务合同 TS-1..TS-12（`scripts/CONTRACT.md`，含 #75 新增的 TS-12
    typed-relation 传播）。
  - G1–G6 资格测试体系（tracker #52）与其 runner。
  - #78/#79/#80/#81 的一批真修（#79 绿灯幻觉、#80 D2/D3 git 层 + Claude guard 死代码、
    #81 issue topology、#78 P0 大半）。
- 结论：**旧 case 测的是一个早已不存在的模板版本**。刷新 = 对当前 main 像旧 case round 1-3
  那样完整回放，检验这些新机制在一个真实外部 case 上成立，而非空模板自测蒙混。

## 非目标

- **本轮不执行 replay**。full-case-replay 是多轮、多 session 的工程；且按 skill F10/F15 教训，
  凡涉及 session 启动时加载的配置（hook / `settings.json` / Codex 信任表）的验证，必须在**全新
  顶层 session** 里做，同一持续 session 无法自证。本 plan 只产出「执行前的方案」。
- 不改模板源码、不改 case 内容、不建 case 分支/worktree、不 clone（clone 是执行阶段动作）。
- 不修复本轮（或未来 replay）发现的任何 bug——记录与修复分离（skill 步骤 7），修复走独立
  分支/PR，不在 case 分支里顺手改。
- 不承诺修 #78 D1/D4（Codex hook 信任注册）——那是需 human 拍板的用户机器全局动作，本方案只在
  探针设计里如实标注其现状，不冒充双表面等价（见「诚实边界」段）。

## Branch / worktree

- **草稿阶段（本轮）**：不建分支，只写 `plans/` 与 `memory/doc-lifecycle.yaml` 两个文件。
  draft 态不要求 branch 为现存 Git ref（`plans/ANATOMY.md` 强制层：branch 现存性只对
  approved/implementing 活跃 plan 生效）。
- **执行阶段（approved 后，供参考、非本 plan 验收范围）**：按 `template-stress-test` skill
  步骤 1，建 `case/elf-refresh-v2`（命名待 human 定，见未解决问题），worktree 建在
  `.claude/worktrees/elf-refresh-v2/`，**从当前 main 分出**。修复分支另开（步骤 7），不复用
  case 分支。

## Linked issue / PR

- parent issue：**#83**（《ELF case 端到端验证 + 变异压测》），其本身是 **#82**
  （《本模板提供了什么 & 怎么实现的》）的原生 sub-issue。
- child issue / phase：本 plan 是**单阶段**（执行前方案设计）；replay 执行阶段若发现缺陷，按
  skill 步骤 7 各开独立修复 child issue。
- 相关既有证据：旧 case ledger 条目 `elf-template-case-replay`、旧报告
  `lab/docs/audits/agent-native-template-functional-test-report.md`、探针历史
  `lab/docs/audits/stress-probe-catalog.md`；旧 case 分支内容以远端 tag
  `archive/elf-replay-v14rc` 存档（旧模板形态，仅历史参考，不直接复用）。

## Allowed paths

本 plan 草稿阶段只写：

- `plans/20260718-83-elf-case-refresh.zh.md`（本文件）
- `memory/doc-lifecycle.yaml`（本 plan 条目登记 / 状态流转）

执行阶段（approved 后，按 skill「允许修改的路径」）：

- `case/elf-refresh-v2` 分支 / 对应 worktree 内任意路径（隔离，不影响 main）
- `lab/code/external/`（外部 vendor 源码落位，依
  `human/decisions/20260709-lab-docs-reference-and-external-vendor-placement.md`）
- `lab/docs/audits/`（case 报告、probe catalog、`stress-test-ledger.yaml` v2 条目）

## Forbidden paths

- 模板源码（`scripts/`、`.agent/`、`.claude/hooks/` 等）——replay 只读记录，发现的 bug 走
  独立修复分支，**不在 case 分支里改**。
- `lab/data|runs|models` bytes、`checkpoints/`、`wandb/`、`lab/infra/private/`、`.env`（一贯边界）。
- 本轮不 clone、不 push、不 merge、不建 PR、不启动/kill 任何作业。

## 实验冻结面（仅实验类 plan；非实验填 n/a）

- frozen commit：**n/a**（本 plan 非训练/评测实验类；replay 测试对象是"当前 main 的模板
  commit"，其精确 hash 在执行冻结时以 `git rev-parse main` 为准并回填 v2 ledger 条目的
  `template_commit_range`，见未解决问题）
- allowed writes：n/a（见上方 Allowed paths）
- forbidden writes：n/a（见上方 Forbidden paths）
- on drift：n/a

## 执行步骤（按 `template-stress-test` skill 10 步映射；供 approved 后执行，非本轮动作）

> 词汇一律沿用既有机器：depth 四档、F1-F19 发现分类、`probe-surface-catalog.md` 探针清单、
> 「记录与修复分离」。严禁另造平行系统。

1. **挑/建 case（skill 步骤 1）**：case = `lillian039/ELF`（外部公开仓，本机旧副本已删）。
   建分支 `case/elf-refresh-v2` + worktree `.claude/worktrees/elf-refresh-v2/`，**从当前 main
   分出**。先查 ledger：旧条目 `elf-template-case-replay` 就是相近 case——本次是它的刷新，不是
   重复劳动（旧的测的是 `fc18318..18281c1` 旧模板，已过时）。
   - **clone 是 human-gate 动作**：执行时 `git clone lillian039/ELF` 属外部网络访问，**该 clone
     步骤本身已获 human 批准**（见「已定决策」①）。
2. **迁移/复现进模板结构（skill 步骤 2）**：把 ELF 外部 vendor 源码放
   `lab/code/external/`，依
   `human/decisions/20260709-lab-docs-reference-and-external-vendor-placement.md` 的落位约定。
   注意 skill F13/F19 教训——不带 Bash 或 cwd 不持久化的 subagent 易误写主仓库，迁移时先
   `pwd` + `git rev-parse --show-toplevel` 自查。
3. **判断测试深度（skill 步骤 3）**：**full-case-replay 全量重跑**（见「已定决策」②）。理由：
   自旧 case 以来 main 改动幅度触及 `.agent/template-versioning-policy.md` 分级表最深一档
   （改 validator/hook + 改 `lab/`/`memory/` 结构 + 新机制类别），按分级表落 full-case-replay。
4. **演练 subagent / skill / command（skill 步骤 4）**：真实派发/调用（不只读契约），至少覆盖：
   `template-stress-test` 自身、`worktree-pr-flow`、`interactive-plan-doc`、
   `bootstrap-project` / `adopt-existing-repo`（ELF 是外部 existing repo，走 adoption 面）、
   `subagent-routing`、涉 human-gate 的 slash command（正面验证该拒绝的真被拒）。记录实际行为
   vs 声明边界。
5. **对抗性探针（skill 步骤 5，深度达标才做，本档达标）**：对每个 validator/hook 做
   `mutate→assert→revert`，参照 `references/probe-surface-catalog.md` 起点。**重点覆盖"自旧
   case 以来的新增机制"**（旧 case round 3 未测过的面）：
   - `check-provenance-chain.py`、`check-doc-lifecycle.py`、`check-capability-catalog.py`
     三个新 validator 各造负例，确认真拦 + 错误信息准确 + revert 后 `git status` 无残留。
   - template-sync 合同 TS-1..TS-12：尤其 **TS-12 typed-relation 传播**（#75 修复）——在真实
     ELF 下游场景复现"追平前 `--strict` FAIL → 追平后转绿"，确认 #75 修复在真实 case 上生效。
   - **专门验证 #78/#79/#80 修复在真实 case 上生效**：
     - #79（绿灯幻觉）：在**无 PyYAML** 环境跑 `validate-governance.py`，确认三项核心语义检查
       （证据链/overclaim、发布闸门、回归矩阵）真跑而非静默放绿。
     - #80 D3：Claude 表面对受保护路径的绝对路径 `Edit`/`Write` 真被 `pre_tool_guard.py` 拦
       （旧为死代码）；`_check_bash` 拦 `>`/`>>`/`tee`/`touch`/`ln` 写受保护路径向量。
     - #80 D2：`.githooks/pre-push` 在真实 `git push origin main` 时拦（surface-agnostic 地板）。
   - 探针的真实 Mutation/Actual/Classification/Follow-up 写进本 case 报告，**不改**
     `probe-surface-catalog.md` 的 Mutation/Expected 两列（那是面向未来的清单）；若发现新机制
     缺一行探针，往清单对应分区补一行（该文件"随模板演化维护"的方式）。
6. **写发现（skill 步骤 6）**：分类沿用 F1-F19 惯例——`template gap`（模板缺一种机制）/
   `validator 按预期工作` / `case ledger 债务` / `文档摩擦` / `迁移执行失误`（自己的失误，
   非模板 bug）。写进 `lab/docs/audits/elf-refresh-v2-report.md`（+ 必要时
   `elf-refresh-v2-probe-catalog.md`）。
7. **记录与修复分离（skill 步骤 7）**：发现的 bug/漂移**不在 case 分支里顺手改**——开独立
   分支/PR 修，走 `worktree-pr-flow`。case 分支只读记录，保持"case 测的是哪个模板版本"可追溯。
8. **独立复验（skill 步骤 8）**：凡涉及 session 启动时加载的配置（hook/`settings.json`/Codex
   信任表）的验证与修复复验，**用全新顶层 session**，不能只用同 session 内 subagent 进程替代
   （F10/F15 教训）。
9. **登记（skill 步骤 9）**：`stress-test-ledger.yaml` **追加一条 v2 条目**（`case_source` /
   `template_commit_range`=当前 main 冻结 hash / `depth: full-case-replay` / rounds / date /
   findings_summary / report 路径 / `status`），并把旧条目 `elf-template-case-replay` 的
   `status: complete` 改为 **`superseded`**（ledger 已定义该取值）。是否保留旧条目原文见未解决
   问题。
10. **决定 case 分支去留（skill 步骤 10）**：默认 case 分支**不合并回 main**（避免外部 case
    内容污染模板）；若产出中有可沉淀成模板永久内容的部分（通用探针、可复用 recipe），原样
    `git checkout <case-branch> -- <path>` promote，不改内容（PR #5/#6 先例）。执行结束按清理
    惯例打 `archive/*` tag 后再删 worktree/分支（全可恢复）。

## 已定决策（human 已拍板，非待决——不要再列为开放问题）

1. **case 源 = 重新 `clone lillian039/ELF`**（外部公开仓；本机旧副本 `~/Projects/ELF-template-case`
   已删）。这是外部网络 clone，属 human-gate 动作——**执行阶段的 clone 步骤本身已获 human
   批准**。迁移落位：外部 vendor 源码进 `lab/code/external/`（依
   `human/decisions/20260709-lab-docs-reference-and-external-vendor-placement.md`）。
2. **测试深度 = `full-case-replay` 全量重跑**（对当前 main 像旧 case round 1-3 那样完整回放，
   产出干净 v2 baseline）。

**以下 6 项由 human 2026-07-18「按默认走」定稿（原「未解决问题」Q1-Q6 收敛为正式决策）：**

3. **Q1 深度分阶段 = 是**：先跑一轮 targeted-smoke gate（只验 3 个新 validator + #78/#79/#80
   修复点），通过后再进完整多轮 full-case-replay。早暴露卡点、省 session。
4. **Q2 探针优先级**：本轮必覆盖 `check-provenance-chain.py` / `check-doc-lifecycle.py` /
   `check-capability-catalog.py` 三个新 validator + TS-12 + #79 无 PyYAML 回退 + #80 D2/D3 +
   #78 D1/D4 现状核实。
5. **Q3 ledger = 追加 v2 条目 + 旧条目 `elf-template-case-replay` 标 `superseded`**（保留旧模板
   版本测试历史，不覆盖）。
6. **Q4 case 分支命名 = `case/elf-refresh-v2`**（skill 惯例 `case/<name>`）。
7. **Q5 = 单建 `elf-refresh-v2-probe-catalog.md`**（full replay 探针量大、有历史价值）。
8. **Q6 = 硬分工双 agent**：更新者 A ≠ 测试者 B、各写各报告（沿用本仓 writer/verifier doctrine +
   G4/G5 先例，防自证据）。

## 诚实边界（必须写进探针设计与预期，不冒充双表面等价）

- **#78 D1/D4——Codex 表面 hook 地板当前不自动加载**：项目 `.codex/config.toml` 的 PreToolUse
  hook 未进用户级 Codex 信任表（`~/.codex/config.toml [hooks.state]` 逐路径 sha256 信任），故
  `pre_tool_guard.py` / formatter / identity 等在 Codex 表面**全部 inert，Codex 从不调用**。
  取证见 `memory/branches/78-codex-hook-trust-finding.md`（本机真机取证，非只读推断）。
- **对 replay 探针的含义**：保护路径类 / identity 类探针在 **Codex 表面**的结果须**如实标注为
  "hook 未加载，无 Codex 侧技术地板"**，不得记成"双表面等价通过"。#78 D1/D4 不是脚本 bug，是
  hook 未信任/未加载——改脚本修不了没被调用的 hook。
- **当前 Codex 表面真正生效的技术地板**：git 层 `.githooks/pre-push`（#80 D2）是
  **surface-agnostic** 地板，Codex 真实 `git push origin main` 也会被 git 拦（与 Codex hook
  是否加载无关）。探针要把"git 层地板生效"与"Codex hook 地板 inert"分开如实记录。
- 本 plan 不承诺、也不在 replay 中自动做 #78 D1/D4 的真修（改用户机器全局 Codex 信任状态需
  human 拍板，属发版门 P8 决策）。

## 任务树

- [x] 读 skill / policy / ledger / probe-catalog / 诚实边界取证 / doc-lifecycle 惯例
- [x] 起草刷新方案初稿（10 步映射 + 已定决策 + 诚实边界 + 批注 slot）
- [x] 登记 `memory/doc-lifecycle.yaml`
- [x] human 批注/定稿（2026-07-18「按默认走」采纳全部 6 项默认）
- [x] 收敛开放问题为正式决策（Q1-Q6 全落定）
- [ ] 执行阶段 kickoff：建 `case/elf-refresh-v2` 分支 + 升 approved + clone ELF（多轮多 session replay）

## Human 批注区

（批注前缀约定：`[OK]` 采纳 / `[改]` 要求修改 / `[?]` 未决；请直接在对应行后批注）

6 项开放问题已由 human 2026-07-18「按默认走」全部采纳默认（正式决策见「已定决策」3-8）：

- Q1 深度分阶段 `[OK] 按默认走`：先 smoke gate 再全量回放
- Q2 探针优先级 `[OK] 按默认走`：3 新 validator + TS-12 + #79 + #80 D2/D3 + #78 现状
- Q3 ledger `[OK] 按默认走`：追加 v2 + 旧条目标 superseded
- Q4 分支命名 `[OK] 按默认走`：case/elf-refresh-v2
- Q5 probe-catalog `[OK] 按默认走`：单建
- Q6 双 agent `[OK] 按默认走`：硬分工 A≠B

## 当前决策

- 全部决策已定（human 2026-07-18「按默认走」）：case 源 = 重 clone `lillian039/ELF`（clone 已获批）；
  深度 = full-case-replay；Q1-Q6 六项默认全部采纳（见「已定决策」3-8）。
- 方案设计定稿。正式 lifecycle `approved` + `case/elf-refresh-v2` 分支创建留待执行阶段 kickoff
  （多轮多 session replay 工程；届时按 doc-lifecycle 要求补 branch 字段再升 approved）。

## 未解决问题

全部 6 项已由 human 2026-07-18「按默认走」收敛为正式决策（见「已定决策」3-8）：Q1 先 smoke
gate 再全量、Q2 探针优先级、Q3 追加 v2 + 旧标 superseded、Q4 `case/elf-refresh-v2`、Q5 单建
probe-catalog、Q6 硬分工双 agent。**本 plan 设计阶段无剩余未决问题**；执行阶段（approved 后）
若出现新问题，届时在对应 case 报告或新 plan 记录。

## 验证标准

**本 plan 阶段（本轮）**：

- `python scripts/check-doc-lifecycle.py`（本 plan 条目登记 + 锚点/注册表一致）
- `python scripts/validate-governance.py`（有 uv 用 `uv run --with pyyaml`）
- `python scripts/check-same-commit.py --staged`

**执行阶段（approved 后，供参考、非本 plan 验收范围）**：

- skill「验证命令」：`validate-governance.py` + `check-same-commit.py --staged`
- 三个新 validator 各自 `--self-test`（若有）+ 对抗探针 mutate→assert→revert 全部按预期
- #79 无 PyYAML 回退真跑、#80 D2/D3 真拦、TS-12 真实 ELF 场景 strict FAIL→OK
- ledger v2 条目登记完整 + 旧条目 superseded
- 涉 session-cached 配置的复验在全新顶层 session 完成（F10/F15）

## 下一步

1. 方案设计已定稿（human「按默认走」采纳全部默认）。执行阶段 kickoff（另起多 session replay
   工程）时：建 `case/elf-refresh-v2` 分支 + 补 doc-lifecycle branch 字段 + 升 approved（human gate）。
2. 执行按本 plan「执行步骤」10 步走：先 targeted-smoke gate，通过后 full-case-replay；硬分工双 agent；
   记录与修复分离；涉 session-cached 配置的复验用全新顶层 session。

## Plan revision log

- 2026-07-18 初稿（狗头军师·拟·ELF刷新方案，issue #83，#82 的 sub-issue）。接进既有
  `template-stress-test` skill / policy / ledger 机器；已定决策两条（重 clone ELF + full-case-replay）；
  诚实边界据 `memory/branches/78-codex-hook-trust-finding.md`；留六条 human 批注 slot。
- 2026-07-18 收敛（都督·统·治理路线）：human「按默认走」采纳全部 6 项默认（Q1 先 smoke gate
  再全量、Q2 探针优先级、Q3 追加 v2 + 旧标 superseded、Q4 `case/elf-refresh-v2`、Q5 单建
  probe-catalog、Q6 硬分工双 agent）；`[?]` 全清、方案设计定稿。正式 approved + 建 case 分支
  留待执行 kickoff（doc-lifecycle 对 approved 要求 branch 现存，本轮不建分支故 status 暂留 draft）。
