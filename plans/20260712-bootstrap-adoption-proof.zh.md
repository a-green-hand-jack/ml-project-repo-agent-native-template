# 自动化项目 bootstrap 并增强 existing-repo adoption proof

> 复制到 `plans/<YYYYMMDD>-<topic>.zh.md`。这是 human 与 Claude Code 的协商界面：
> Claude 写初稿 → human 在文件里批注 → Claude 读 diff、收敛计划 → 每次采纳的修订做一个小 commit。
> 实现只在 scope / forbidden paths / verification 清楚后开始。

## 当前目标

把 issue #12 提出的三类生命周期缺口，收敛成可独立验证的实现子任务：

1. **新项目 bootstrap**：`README.md`「派生后的落地步骤」目前是 7 步人工清单（填 `PROJECT.md`、换
   `CODEOWNERS` owner、`git config core.hooksPath`、trust Codex + `sync-codex-adapters.py`、删无用目录、
   `validate-governance.py`、`.reference-docs` 版本）。新增一个可重复、幂等执行的 bootstrap 命令，把能
   自动化的部分收敛成脚本，写使用报告，且能安全跳过需要 human 信息的步骤（不猜）。
2. **existing-repo adoption 语义归类**：当前 `adopt-existing-repo.py` 的 `normalize` phase 只有二元逻辑
   ——命中 `CONTROL_ITEMS` 且 hash 未变则留在原处，其余全部整体移到 `lab/code/imported/<slug>/`，没有
   per-entry 的目标位置/理由。给 discover/normalize 加一份可读、可配置的语义归类计划 + dry-run + 冲突说明。
3. **adoption proof 的原生 runtime/smoke 合同**：`prove` phase 目前只是 best-effort 跑
   `detect_test_command()` 猜出的命令，猜不到就把 `original_test` 记为 `None`（已在 Agent-R1 真实 replay
   中复现：`original_test_returncode: None`，`lab/docs/audits/agent-r1-adoption-replay-report.md:83-86`）。
   需要一份统一的 smoke 合同：命令从哪来、结果怎么记、"未验证"必须写明确原因，且失败/未验证不能被
   静默当成通过。

## 非目标

- 不在本轮实现语言/框架特定的原生构建修复（例如自动装依赖跑测试）；smoke 合同只负责"跑什么、记什么、
  失败/未知时怎么表态"，不负责让任意语言项目的测试变绿。
- 不移动/操作 `lab/data/**`、`lab/runs/**`、`lab/models/**`、checkpoints、wandb、`lab/infra/private/**`
  等受保护 bytes；语义归类遇到这些路径仍然只登记 blocker，不猜测搬移策略。
- 不做「新建项目」与「迁移已有 repo」的合并重写；bootstrap 命令服务全新/空 Git repo，
  `adopt-existing-repo.py` 服务已有内容的 repo，两者共享哪些底层工具（如 `.template.toml` 写入）在下面
  任务树里单独标注，但不强行合并成一个入口。
- 不在本 plan 内做版本发版（`bump-template-version.py` / `VERSION` / `CHANGELOG.md`）；发版按
  `.agent/template-versioning-policy.md` 的③站，在功能落地 merge 后单独走。
- 不新增第三方依赖；沿用 repo 现有「validator/脚本无第三方硬依赖」的惯例（`scripts/CLAUDE.md`）。
  注意：若 B3 走「外部规则文件」路线，只能用 `tomllib`（Python 3.11+ stdlib）读 TOML；**YAML 无 stdlib 解析器，
  选它就违反 no-deps 底线**——这条约束直接收窄开放问题 4 的可选项。

术语澄清（防歧义）：本 plan 里「runtime/smoke 合同」的 "runtime" 指**被迁移项目自身的语言运行时/测试命令**
（pytest、`npm test`、`make` 等），**不是** Claude vs Codex 的 agent runtime。C 部分的 smoke 合同是
runtime-agnostic 的命令执行与记录，Claude 或 Codex 谁来跑 adoption 都走同一条合同；而 Claude/Codex 双 agent
runtime 的对等，是 A4 加载清单 + D2b adapter 同步在管，两者不要混为一谈。

## Branch / worktree

- branch：`feat/12-bootstrap-adoption-proof`
- worktree：`.claude/worktrees/12-bootstrap-adoption-proof`
- base：`main`（已从 main 切出，干净）

## Linked issue / PR

- `#12`（feat: 自动化项目 bootstrap 并增强 existing-repo adoption proof）
- 暂无关联 PR。

## Allowed paths

预计涉及：

- `scripts/bootstrap-project.py`（新，命名待 human 拍板，见「未解决问题」）
- `scripts/adopt-existing-repo.py`（语义归类 + smoke 合同增强）
- `scripts/check-adoption-integrity.py`（若 smoke 合同结果需要独立校验入口）
- `scripts/ANATOMY.md`
- `.claude/skills/bootstrap-project/SKILL.md`（新）
- `.claude/skills/adopt-existing-repo/SKILL.md`（更新语义归类 + smoke 合同说明）
- `.claude/commands/bootstrap-project.md`（新，若采用 slash command 形态）
- `.claude/commands/adopt-existing-repo.md`
- `.claude/ANATOMY.md`
- `README.md`（「派生后的落地步骤」章节改写为 bootstrap 命令；adoption 章节补语义归类/smoke 合同说明）
- `DESIGN.md`（§10 能力清单数量若新增 script/skill/command 需同步）
- `ANATOMY.md`（root router，若新增顶层受管路径）
- `lab/evals/adoption/run-adoption-smoke.py`（既有 smoke，扩展或新增负向 fixture）
- `lab/evals/bootstrap/`（新，bootstrap 命令的 synthetic fixture/smoke，路径待定）
- `lab/docs/audits/`（真实 existing repo replay 报告，续写第二个案例或复跑 Agent-R1 验证新合同）
- `memory/current-status.md`、`memory/session-tree.md`
- `plans/20260712-bootstrap-adoption-proof.zh.md`（本文件）

如实现中新增/搬动结构，需要同 commit 更新对应 `ANATOMY.md`（same-commit rule）。

## Forbidden paths

- `lab/data/**`、`lab/runs/**`、`lab/models/**` 权重/产物 bytes、`checkpoints/**`、`wandb/**`、
  `lab/infra/private/**`、`.env` —— 不编辑、不删除、不移动，语义归类命中即登记 blocker 并停下。
- `.git/**` 内部对象、`.githooks/**` 之外的 git 机制文件不直接改写（`git config core.hooksPath` 这类
  命令式操作允许，但不手改 `.git/config` 文件本身）。
- 不新建/合并 PR、不 push 到 `main`/`master`（除非拿到显式放行环境变量）、不打 release tag、不动远端
  CI/infra 配置以外的仓库设置。
- 不在本 repo 之外的真实 replay 目标 repo 里做破坏性操作（复用 `adopt-existing-repo.py` 已有的
  「先 clone 到临时目录/worktree 再操作」纪律）。
- 不修改 `plans/20260709-adopt-existing-repo.zh.md`（上一个 feature 的历史记录，除非新增内容明确需要
  回链引用；默认新增独立小节而不是编辑其历史决策）。

## 任务树

- [ ] Parent：issue #12 三类生命周期增强
  - [ ] A. 新项目 bootstrap 命令
    - [ ] A1：设计 bootstrap 的幂等 state 模型（第二次运行不重复写、不报错、给出「已确认」而非「已执行」）
    - [ ] A2：实现自动化子步骤：`.template.toml` 生成/确认（origin+version 锚点）、
          `git config core.hooksPath .githooks`、`sync-codex-adapters.py`、`validate-governance.py`
    - [ ] A3：实现「需 human 信息才能做」的子步骤上报（CODEOWNERS owner、PROJECT.md 填写、
          要不要删无用目录）——不猜测、只在使用报告里列成 blocker/待办
    - [ ] A4：Codex/Claude 项目配置加载清单（bootstrap 完成后打印/写入）。这条不是「抄一遍验收标准」，
          必须落成两侧**可执行差异**的清单，至少覆盖：
          - **Claude Code 侧**：cwd 下自动发现 `.claude/settings.json`（权限/hooks）、`.claude/agents/*.md`、
            `.claude/skills/*/SKILL.md`、`.claude/commands/*.md`（slash command）、`statusLine`（Claude 专属）。
          - **Codex 侧**：`.codex/config.toml`（hooks/agents 设置）、`.codex/agents/*.toml`、
            `.agents/skills/*/SKILL.md`（含由 `.claude/commands/*` 生成的 `command-<name>` skill）。
          - **两侧非对等的运行前提（必须显式标注，不能默认已生效）**：① Codex 的 `config.toml` hooks
            需 human 先 **trust 本 repo** 才加载（`.codex/config.toml:1` 注释），bootstrap 脚本无法代替这步，
            只能在清单里列成 blocker/待办（同 CODEOWNERS 类）；② `git config core.hooksPath .githooks` 是
            两侧共用的 pre-commit 前提，bootstrap 可自动做；③ Codex custom-agent TOML 不强制 Claude 的
            tools allowlist、不 pin model、sandbox_mode 只有 read-only/workspace-write 粗粒度（见
            `sync-codex-adapters.py:47-51,71-84`）——清单要说明这是「行为边界靠自觉」而非硬隔离。
          - 清单的**文件就位/静态一致性不能靠手写维护**：以 `check-agent-harness.py`（检查项 #5 配置可解析、
            #6 Codex adapters 同步）为机器事实源，清单文案与该 validator 的判定保持一致。注意该 validator
            只能证明文件可解析、引用存在、adapter 新鲜，**不能证明当前 Codex session 已加载 project config/hooks**；
            runtime 加载证据由 A5 的 fresh-session smoke 单独负责，避免把静态检查误写成端到端结论。
    - [ ] A5：synthetic fixture：在空 Git repo 上跑两次，断言第二次幂等 + 在**该 bootstrapped repo 内**
          跑 `validate-governance.py --strict`、`check-agent-harness.py --strict`、`sync-codex-adapters.py --check`
          三者全绿，证明两侧配置/adapter **静态自洽**。另在实现完成后从该 repo 启动一个 **fresh Codex session**，
          记录最小 runtime smoke：repo `AGENTS.md` guidance 可见、repo-local `.agents/skills` 可发现，并用一个无副作用
          的受保护路径 synthetic probe 或 hook 诊断证据确认 project `PreToolUse` 地板已加载。当前这次真实 Codex session
          能证明现有 repo 的 guidance/skills 已被发现，但它启动时 bootstrap 功能尚不存在，不能替代该验收。
    - [ ] A6：README「派生后的落地步骤」改写，指向新命令；仍保留人工兜底步骤说明，并保留「Codex 需先 trust
          repo」这条无法脚本化的手工前提
  - [ ] B. existing-repo 语义归类增强
    - [ ] B1：定义归类维度（例如：template control item / 项目代码 / 项目文档 / 受保护 bytes /
          未知-需人工），写进 discover 输出的 per-entry 结构
    - [ ] B2：`--dry-run` 模式：只打印/写归类计划（目标位置 + 理由 + blocker），不落盘
    - [ ] B3：归类规则可配置（至少支持通过参数或规则文件覆盖默认判断），并向后兼容现有
          `--policy conservative` 行为
    - [ ] B4：`normalize` 消费归类计划而不是硬编码的二元判断；冲突/受保护路径仍然停下报告
    - [ ] B5：更新 `lab/evals/adoption/run-adoption-smoke.py` 或新增 fixture，覆盖「多种归类结果」
          与「归类失败/blocker 不静默继续」两类断言
    - [ ] B6：adoption 完成报告复用 A4 的双 agent surface 加载清单/诊断逻辑，至少报告 Claude/Codex
          文件就位状态、adapter 静态一致性、`core.hooksPath` 状态与 Codex trust 的 out-of-band 前提；不在
          adoption 内假装已替 human 完成 trust。
  - [ ] C. 统一 runtime/smoke 验证合同
    - [ ] C1：定义 smoke 合同 schema：`command_source`（auto-detected/explicit/none）、`command`、
          `result`（pass/fail/skipped/unknown）、`unverified_reason`（未验证时必填）
    - [ ] C2：`prove` phase 按合同写 adoption report，明确区分「未检测到测试命令」与「检测到但失败」
          与「跑通过」三种状态，且非 pass 状态要在 exit code / report 里可被程序判定为「未证明」
    - [ ] C3：`check-adoption-integrity.py`（或新增校验点）在 smoke 状态非 pass 时不能被上游流程当作
          静默通过；至少要有一个负向 fixture 断言这一点
    - [ ] C4：至少一个真实 existing repo replay，同时报告 tracked-byte integrity 与新 smoke 合同结果
          （复用/续写 `lab/docs/audits/agent-r1-adoption-replay-report.md`，或新开一个真实 repo 案例
          ——由 human 决定，见「未解决问题」）
  - [ ] D. 文档/结构同步
    - [ ] D1：`scripts/ANATOMY.md`、`.claude/ANATOMY.md`、root `ANATOMY.md`（如涉及新顶层路径）
    - [ ] D2：`.claude/skills/adopt-existing-repo/SKILL.md` 更新步骤说明；`bootstrap-project` skill 新增
    - [ ] D2b：**Codex adapter 同步（canonical 改动的必做尾步）**：新增/改动任何 `.claude/skills/*`、
          `.claude/commands/*`、`.claude/agents/*` 后，跑 `python scripts/sync-codex-adapters.py` 生成对应
          `.agents/skills/*/SKILL.md`（skill）、`.agents/skills/command-*/SKILL.md`（若 bootstrap 采用 slash
          command 形态）与 `.codex/agents/*.toml`，并把生成物纳入**同一 commit**（`--check` 是 CI 门禁，
          不同步会红）。这是本 plan 里最容易被「只从 Claude 视角写」漏掉的一步。
    - [ ] D2c：bootstrap 与 adoption 共用同一份 agent-surface postflight 数据结构/渲染函数，避免两套
          Claude/Codex 加载清单发生文案和判定漂移。
    - [ ] D3：`README.md`、`DESIGN.md` §10 能力清单数量同步（新增 script/skill/command 时 Claude 侧与
          Codex 生成侧的计数都要对上）
    - [ ] D4：`memory/current-status.md` / `session-tree.md` 记录本 feature 落地状态
    - [ ] D5：`scripts/CLAUDE.md` 措辞更新——现文案「三个脚本只读、无副作用、无第三方硬依赖」已与现实不符
          （`adopt-existing-repo.py` 已有写副作用，本轮 `bootstrap-project.py` 再加一个 mutating 脚本）；需把
          「只读/无副作用」收敛为「只读校验脚本 vs 有副作用的 mutating 脚本」两类描述，保留「无第三方硬依赖」底线。
    - [ ] D6：`python scripts/validate-governance.py --strict` + `check-agent-harness.py --strict` +
          `sync-codex-adapters.py --check` 全绿

## Human 批注区

（human 可在这里直接改 plan；agent 读取 diff 后收敛。）

## 当前决策

- 三类增强共享同一个 plan doc 与分支，因为它们都服务 issue #12 的同一验收标准集合，且 B/C 都改
  `adopt-existing-repo.py` 同一文件，拆分反而增加合并冲突面。
- bootstrap 命令服务「全新/空 repo」场景，与 `adopt-existing-repo.py`（服务「已有内容 repo」）保持
  两个入口，不合并成一个大命令——两者的安全边界和输入形状不同（空 repo 无冲突可言，adoption 处处要
  防冲突/防覆盖）。
- 语义归类与 smoke 合同都遵守「不能安全判断就停下报告」的既有 conservative 策略，不因为增强而放宽
  「无损、不猜测」的底线。
- **双 runtime 对等是本 feature 的一等公民，不是事后补丁**：任何 canonical（`.claude/**`）能力改动都要经
  `sync-codex-adapters.py` 生成 Codex 侧并 same-commit 提交。静态门禁与 runtime smoke 分层表态：adapter 齐全、
  harness/sync 全绿只证明静态自洽；「Codex 可实际发现 guidance/skills、project hook 已加载」需要实现后的 fresh
  Codex session 证据。当前真实 Codex App session 已直接看到本 repo 注入的 `AGENTS.md` 指令与 repo-local
  `interactive-plan-doc` 等 `.agents/skills`，证明现有 repo 的 guidance/skill discovery 路径可用；但当前 surface
  没有暴露可归因到 `.codex/config.toml` 的 trust 状态或 hook provenance，不能据此宣称 project hooks 已加载。
- **Codex trust 是 out-of-band 前提，不是 bootstrap/adoption 可代做的状态**：两个入口都报告「配置文件已就位」
  与「仍需 human trust」；除非 Codex 提供稳定、可脚本读取的 trust/provenance API，否则不猜测、不把 trust 状态
  当作脚本可自动确认的布尔值。本轮检查到的环境变量也没有可用的 Codex trust 标志。
- bootstrap 与 adoption 都会产出同源的双 surface postflight。理由是两条路径最终都交付可被 Claude/Codex 使用的
  repo；只给空 repo bootstrap 清单，会让 existing-repo adoption 在同一验收目标下缺少对等的落地诊断。

## 未解决问题

以下问题 issue 原文未给出足够细节，需要 human 拍板：

1. **bootstrap 命令的名字/形态**：`scripts/bootstrap-project.py`（对齐 `adopt-existing-repo.py` 命名
   风格）是否合适？是否需要 slash command（`.claude/commands/bootstrap-project.md`）还是只靠脚本 +
   skill 文档即可？**双 runtime 考量**：若做成 slash command，Codex 不会把 `.claude/commands/*.md` 当 slash
   command 加载，`sync-codex-adapters.py` 会为它生成一个 `command-bootstrap-project` skill（多一个 Codex 表面 +
   多一份需 same-commit 提交的生成物，见 `sync-codex-adapters.py:118-141`）。若只做「脚本 + skill」，两侧调用
   路径更对称、生成损耗更小。倾向：除非确有「在 Claude 会话里敲 `/` 触发」的强需求，否则优先 skill 形态。
2. **`.template.toml` 的 origin 从哪来**：新建项目时脚本无法凭空知道上游 template repo 的 slug——是
   要求用户传 `--origin <owner/repo>`，还是尝试从 `git remote -v` / GitHub template 关系推断（若能推断，
   置信度不足时如何降级为「需人工确认」）？
3. **bootstrap 的「幂等」定义边界**：第二次运行如果发现 `.template.toml` 已存在但 origin 与传入参数
   不一致，应该报错阻止，还是当作「重新指认」直接覆盖？（关系到会不会误覆盖别人已经手工填好的版本
   锚点）
4. **语义归类的分类粒度**：issue 只说「较粗」，没给出目标分类表。是否需要区分「项目代码」vs
  「项目文档」vs「CI/构建配置」等更细类别，还是维持「template control item / 保守导入 / 受保护 /
   冲突」四类、只是把移动前的计划显式化即可？分类规则要不要支持外部配置文件？若要外部化，
   **只能选 TOML（`tomllib` stdlib）不能选 YAML**（YAML 需第三方依赖，违反 no-deps 底线）。二审倾向：v1
   先 only 内置规则 + `--dry-run` 可见，足以满足验收标准 3；外部规则文件作为后续增量，避免过早引入配置
   schema 与解析面（防过度设计）。
5. **smoke 合同判定为"未验证"的处理策略**：`prove` phase 检测不到测试命令时，除了在 report 里写明
  `unverified_reason`，是否需要让整体 `prove` 的 exit code 也非 0（目前 `prove` 只在 integrity 失败
   时才算 failed）？如果原生测试跑失败（例如原 repo 本身测试就有已知失败），是否应该硬 block 整个
   adoption，还是记录为 warning 并允许 human 决定是否继续？
6. **验收标准 4「至少一个真实 existing repo replay」**：是否要求一个新的、之前没测过的真实 repo（覆盖
   更多样的原生测试命令类型），还是可以复用 Agent-R1 案例、在新合同下重跑并补充 smoke 结果说明即可？
7. **B/C 落地顺序**：B（语义归类）与 C（smoke 合同）都改 `adopt-existing-repo.py` 的不同 phase，是否
   要求分两个可独立 review 的 commit/PR，还是可以在同一 PR 里一起交付（本 plan 默认视为可在同一分支
   分阶段提交，但最终是否拆 PR 由 human 决定）？
8. **【本轮真实 Codex 二审已收敛】双 runtime 验证深度**：静态 validator **不够**支持「Codex 侧可等价执行」
   的强结论，只能支持「配置/adapter 静态自洽」。本轮真实 Codex App session 已一手确认现有 repo 的 `AGENTS.md`
   guidance 与 `.agents/skills` 可发现；bootstrapped/adopted repo 的端到端结论仍必须等实现落地后，从目标 repo 启动
   fresh session 再测，原因是当前 session 的启动时点早于待实现产物，无法跨时间替未来产物背书。已据此改写 A5。
9. **【本轮真实 Codex 二审已收敛】Codex trust 表态**：输出应同时列「`.codex/config.toml` 已就位」与
   「trust 是 out-of-band、需 human 完成」，不能把前者表述成 hooks 已生效。本轮能看到 repo guidance/skills，
   但当前 surface 未暴露可归因的 trust 状态、hook provenance 或 trust 环境变量，因此不能可靠自动判定 trust；
   实现应保守报告 prerequisite，而不是伪造 detected=true/false。
10. **【本轮真实 Codex 二审已收敛】adoption 也要报告 Codex/Claude 落地状态**：不要求 adoption 擅自完成 trust，
    但要求它与 bootstrap 共用 postflight，报告 adapters、hooksPath 与 trust 前提。已新增 B6/D2c，避免 existing-repo
    路径成为双 surface 验收盲区。

## 验证标准

对应 issue 验收标准，逐条给出要跑的命令/fixture：

- [ ] **bootstrap 幂等 + 双 runtime 静态自洽 + Codex fresh-session smoke**：在空 Git repo 上跑两次
      `scripts/bootstrap-project.py`，
      第二次不报错、不重复写入，且在 **bootstrapped repo 内**三个 validator 全绿（Claude 侧配置 + Codex
      adapters 都自洽）。命令示例（占位，待 A1/A2 落地后定稿）：
      ```bash
      python scripts/bootstrap-project.py <empty-repo> --origin <owner/repo>
      python scripts/bootstrap-project.py <empty-repo> --origin <owner/repo>   # 第二次，应幂等
      python <empty-repo>/scripts/validate-governance.py --strict
      python <empty-repo>/scripts/check-agent-harness.py --strict     # 覆盖 Claude/Codex 配置可解析(#5) + adapter 同步(#6)
      python <empty-repo>/scripts/sync-codex-adapters.py --check      # 证明 Codex adapters 已就位且新鲜
      ```
      三个静态检查通过后，另从 `<empty-repo>` 启动 fresh Codex session，保存 guidance/skill discovery 与
      project hook 加载的最小证据；若执行 surface 不暴露 hook provenance，则明确记录该项 `unknown`，不能用
      validator 结果替代。
- [ ] **模板版本锚点 + 加载清单**：bootstrap 后 `<empty-repo>/.template.toml` 存在且可被
      `scripts/template-sync.py` 的 `read_template_toml()` 解析；bootstrap 输出的 Codex/Claude 加载清单
      须与 `check-agent-harness.py` 的实际判定一致（不是手写、易漂移的静态文案），且清单显式区分：
      - **自动可就位**：`.claude/settings.json`、`.claude/agents|skills|commands/*`、`.codex/config.toml`、
        `.codex/agents/*.toml`、`.agents/skills/*/SKILL.md`（后两者由 `sync-codex-adapters.py` 生成）。
      - **需 human out-of-band**：Codex trust 本 repo（`config.toml` hooks 生效前提）——清单里必须标成待办，
        不能默认已生效（见未解决问题 9）。
- [ ] **adoption dry-run 归类计划**：
      ```bash
      python scripts/adopt-existing-repo.py <fixture> --phase discover --dry-run
      ```
      输出/写入的归类计划里，每个 root entry 都能读到目标位置、理由、是否 blocker。
- [ ] **真实 repo replay（tracked-byte integrity + smoke）**：
      ```bash
      python scripts/adopt-existing-repo.py <real-repo> --phase all --policy conservative --project-name <slug>
      python scripts/check-adoption-integrity.py <real-repo>
      ```
      生成的 `lab/docs/audits/template-adoption-report.md`（在目标 repo 内）需同时含 integrity 结果与
      smoke 合同结果（pass/fail/unknown + reason），并在本模板仓库留一份 replay 报告存档
      （`lab/docs/audits/*.md`，格式对齐 `agent-r1-adoption-replay-report.md`）。
- [ ] **负向 fixture 不静默通过**：新增/扩展 `lab/evals/adoption/run-adoption-smoke.py`（或新脚本），
      覆盖至少三类负向场景并断言非 0 exit 或明确 blocker：冲突文件、受保护路径命中、smoke 命令失败/
      未检测到。
- [ ] **文档/结构同步**：
      ```bash
      python scripts/validate-governance.py --strict
      python scripts/check-anatomy-drift.py
      python scripts/check-agent-harness.py --strict
      python scripts/sync-codex-adapters.py --check
      git diff --check
      ```

## 下一步

1. Human 在本文件批注，优先回答「未解决问题」里的 1/2/5（直接决定实现形状，其余可后置）。
2. 收敛设计后，先落地 A（bootstrap，风险最小、无既有代码冲突），再落地 C（smoke 合同，改动集中在
   `prove`），最后 B（语义归类，改动面最大、需要重新设计 `normalize` 的消费方式）。
3. 每个子任务落地后跑对应验证标准命令，再进入下一个。

## Plan revision log

- 2026-07-12 初稿：根据 issue #12 正文与现状代码（`scripts/adopt-existing-repo.py`、
  `.claude/skills/adopt-existing-repo/SKILL.md`、`.agent/template-versioning-policy.md`、
  `template-manifest.toml`、`lab/docs/audits/agent-r1-adoption-replay-report.md` 里
  `original_test_returncode: None` 的真实缺口）整理，标出 bootstrap 缺口、归类粗粒度缺口、
  smoke 合同缺口三条主线，并列出 7 个待 human 拍板的开放问题。
- 2026-07-12 二审（Claude Opus 4.8，代替额度耗尽的 Codex gpt-5.6-sol 承接第二意见审查）：补齐双 runtime
  缺口——把 A4「加载清单」从抄验收标准落成两侧可执行差异（含 Codex trust 前提、tools/model/sandbox 损耗），
  A5/D6 在 bootstrapped repo 内加 `check-agent-harness.py --strict` + `sync-codex-adapters.py --check` 作为静态
  双 runtime 冒烟，新增 D2b（canonical 改动后 same-commit 重生成 Codex adapters）与 D5（`scripts/CLAUDE.md`
  「无副作用」措辞已与现实冲突）；澄清「runtime/smoke」指被迁移项目自身运行时而非 agent runtime；给开放问题
  1/4 补双 runtime 与 no-deps 约束，新增开放问题 8/9/10（双 runtime 验证深度、Codex trust 表态、adoption 是否
  也产加载清单）。所有判断基于读到的 `sync-codex-adapters.py`、`.codex/config.toml`、`check-agent-harness.py`
  证据；无一手 Codex 运行经验之处均已标为 open question。人类最终批准仍待定。
- 2026-07-12 真实二审（Codex gpt-5.6-sol，medium）：在真实 Codex App session 中复核 Opus 留下的 8/9/10；
  一手确认当前 repo 的 `AGENTS.md` guidance 与 `.agents/skills` discovery 可用，同时确认当前 surface 不暴露可归因的
  trust/hook provenance，故把「静态自洽」与「fresh-session runtime smoke」拆开，要求 bootstrap/adoption 共用
  postflight，并新增 A5、B6、D2c 与相应验收修订。人类最终批准仍待定。
