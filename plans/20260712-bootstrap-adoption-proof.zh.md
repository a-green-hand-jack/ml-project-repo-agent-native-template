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
   per-entry 的目标位置/理由。给 discover/normalize 加一份可读的语义归类计划（v1 内置保守四类，不做外部
   可配置规则文件，已决策，见开放问题 4）+ dry-run + 冲突说明。
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
  **已决策（开放问题 4，2026-07-12 human 拍板）**：v1 语义归类只内置保守四类判断逻辑，不做外部规则
  文件/参数覆盖入口，本轮不涉及 TOML/YAML 解析选型问题；若未来确有需求引入外部规则文件，届时只能选
  `tomllib`（Python 3.11+ stdlib）读 TOML，YAML 需第三方依赖、违反 no-deps 底线——该约束留作后续增量的
  前提记录，不是本轮要实现的功能。

术语澄清（防歧义）：本 plan 里「runtime/smoke 合同」的 "runtime" 指**被迁移项目自身的语言运行时/测试命令**
（pytest、`npm test`、`make` 等），**不是** Claude vs Codex 的 agent runtime。C 部分的 smoke 合同是
runtime-agnostic 的命令执行与记录，Claude 或 Codex 谁来跑 adoption 都走同一条合同；而 Claude/Codex 双 agent
runtime 的对等，是 A4 加载清单 + D2b adapter 同步在管，两者不要混为一谈。

## Branch / worktree

- branch：`feat/12-bootstrap-adoption-proof`（当前分支，承载 A：bootstrap 命令，第一个 PR）
- worktree：`.claude/worktrees/12-bootstrap-adoption-proof`
- base：`main`（已从 main 切出，干净）
- **PR 拆分（已决策，2026-07-12 human 拍板，见开放问题 7）**：B（语义归类）与 C（smoke 合同）拆成两个
  独立 PR 交付，不在本分支内以「同分支分阶段提交」的方式合并进同一个 PR。后续需要为 B、C 各自新切一个
  分支 + worktree（建议 `feat/12b-semantic-classification` / `feat/12c-smoke-contract`，具体命名在对应
  PR 启动时再定），遵守本 repo「并行 session 用独立 worktree 隔离」的既有惯例，避免与本分支互相冲突。
  A（bootstrap）仍用本分支/worktree 交付；D（文档/结构同步）里的子项按其改动归属分别并入 A/B/C 对应
  PR，不单独开分支。

## Linked issue / PR

- `#12`（feat: 自动化项目 bootstrap 并增强 existing-repo adoption proof）
- 暂无关联 PR。

## Allowed paths

预计涉及（下列路径按 A/B/C 三个子任务列出；决策 6 后 B、C 分别在各自独立 PR 中改动，本文件继续作为
三者共享的 plan doc，不拆成三份文档）：

- `scripts/bootstrap-project.py`（新；调用形态为 skill，非独立 slash command，见开放问题 1 已决策）
- `scripts/adopt-existing-repo.py`（语义归类 + smoke 合同增强；B、C 各自 PR 内改动此文件的不同 phase）
- `scripts/check-adoption-integrity.py`（若 smoke 合同结果需要独立校验入口）
- `scripts/ANATOMY.md`
- `.claude/skills/bootstrap-project/SKILL.md`（新，唯一交互入口，见开放问题 1 已决策）
- `.claude/skills/adopt-existing-repo/SKILL.md`（更新语义归类 + smoke 合同说明）
- `.claude/commands/adopt-existing-repo.md`
- `.claude/ANATOMY.md`
- `README.md`（「派生后的落地步骤」章节改写为 bootstrap 命令；adoption 章节补语义归类/smoke 合同说明）
- `DESIGN.md`（§10 能力清单数量若新增 script/skill/command 需同步）
- `ANATOMY.md`（root router，若新增顶层受管路径）
- `lab/evals/adoption/run-adoption-smoke.py`（既有 smoke，扩展或新增负向 fixture）
- `lab/evals/bootstrap/`（新，bootstrap 命令的 synthetic fixture/smoke，路径待定）
- `lab/docs/audits/`（真实 existing repo replay 报告；新找一个真实 repo 案例产出新报告，不复用/复跑
  Agent-R1 案例，见开放问题 6 已决策）
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
    - [ ] A1：设计 bootstrap 的幂等 state 模型（第二次运行不重复写、不报错、给出「已确认」而非「已执行」；
          origin 冲突时默认报错停止、`--force` 才覆盖，见开放问题 3 已决策）
    - [ ] A2：实现自动化子步骤：`.template.toml` 生成/确认（origin+version 锚点）——**origin 由调用方通过
          `--origin <owner/repo>` 显式传入，脚本不自动推断（不猜 `git remote -v`/GitHub template 关系）、
          不做交互式确认**（开放问题 2 已决策）；若目标 repo 已存在 `.template.toml` 且其中 origin 与传入
          `--origin` 不一致，**默认报错并停止，不静默覆盖**，需要覆盖必须显式加 `--force`（开放问题 3
          已决策，纳入 A1 的幂等 state 模型设计）；`git config core.hooksPath .githooks`、
          `sync-codex-adapters.py`、`validate-governance.py`
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
  - [ ] B. existing-repo 语义归类增强（开放问题 7 已决策：独立 PR，不与 C 合并）
    - [ ] B1：归类维度**已决策为内置保守四类**（开放问题 4，2026-07-12 human 拍板）：`template control
          item`（命中 CONTROL_ITEMS 且 hash 未变，留在原处）/ `保守导入`（其余项目代码、文档等整体归入
          `lab/code/imported/<slug>/`）/ `受保护`（命中 `lab/data/**` 等 forbidden paths，登记 blocker
          不移动）/ `冲突`（目标位置已存在不一致内容，登记 blocker 停下）；四类写进 discover 输出的
          per-entry 结构（目标位置 + 理由 + 是否 blocker）
    - [ ] B2：`--dry-run` 模式：只打印/写归类计划（目标位置 + 理由 + blocker），不落盘
    - [ ] B3：**（已决策，开放问题 4：不做外部规则文件/参数覆盖）** 四类判断逻辑全部内置在
          `adopt-existing-repo.py` 内，v1 不提供规则文件或额外 CLI 参数覆盖入口；仍需向后兼容现有
          `--policy conservative` 行为（四类判断是该 policy 下的具体化，不新增 policy 值）
    - [ ] B4：`normalize` 消费归类计划而不是硬编码的二元判断；冲突/受保护路径仍然停下报告
    - [ ] B5：更新 `lab/evals/adoption/run-adoption-smoke.py` 或新增 fixture，覆盖「多种归类结果」
          与「归类失败/blocker 不静默继续」两类断言
    - [ ] B6：adoption 完成报告复用 A4 的双 agent surface 加载清单/诊断逻辑，至少报告 Claude/Codex
          文件就位状态、adapter 静态一致性、`core.hooksPath` 状态与 Codex trust 的 out-of-band 前提；不在
          adoption 内假装已替 human 完成 trust。
  - [ ] C. 统一 runtime/smoke 验证合同（开放问题 7 已决策：独立 PR，不与 B 合并）
    - [ ] C1：定义 smoke 合同 schema：`command_source`（auto-detected/explicit/none）、`command`、
          `result`（pass/fail/skipped/unknown）、`unverified_reason`（未验证时必填）。**已决策（开放
          问题 5，2026-07-12 human 拍板）**：`result` 与 `prove` 的 process exit code **解耦**——
          `result` 为 `fail`/`skipped`/`unknown`（即「检测到但失败」或「未验证」）时，exit code 仍为
          `0`，但 report 必须生成一个显式、机器可读的 warning 字段（列出该条目 + 原因），不能被静默省略；
          exit code 非 0 只保留给 adoption 自身的 integrity 失败（例如 tracked-byte hash 不匹配）。
    - [ ] C2：`prove` phase 按合同写 adoption report，明确区分「未检测到测试命令」与「检测到但失败」
          与「跑通过」三种状态。**已决策（开放问题 5）**：非 pass 状态**不**改变 `prove` 的 exit code
          （仍为 0），但必须在 report 里可被程序判定为「未证明/未通过」——这个判定由显式、结构化的
          warning 字段承载（而非靠 exit code），供上游流程/human 读取。
    - [ ] C3：`check-adoption-integrity.py`（或新增校验点）在 smoke 状态非 pass 时不能被上游流程当作
          静默通过。**已决策（开放问题 5）**：该校验点自身的 exit code 语义与 `prove` 一致（只在
          tracked-byte integrity 不一致等 adoption 自身失败时非 0；smoke 非 pass 不触发非 0），断言点
          改为「report 中存在显式 warning 字段且不可被忽略」而不是要求 exit code 非 0；至少要有一个
          负向 fixture 专门断言这个「exit 0 + 显式 warning」组合，防止未来实现把 warning 字段默默丢掉、
          伪装成全绿。
    - [ ] C4：至少一个真实 existing repo replay，同时报告 tracked-byte integrity 与新 smoke 合同结果。
          **已决策（开放问题 6，2026-07-12 human 拍板）：新找一个此前未测过的真实 repo，不复用/复跑
          Agent-R1 案例**（覆盖更多样的原生测试命令类型），产出独立于
          `agent-r1-adoption-replay-report.md` 的新 replay 报告存档
  - [ ] D. 文档/结构同步
    - [ ] D1：`scripts/ANATOMY.md`、`.claude/ANATOMY.md`、root `ANATOMY.md`（如涉及新顶层路径）
    - [ ] D2：`.claude/skills/adopt-existing-repo/SKILL.md` 更新步骤说明；`bootstrap-project` skill 新增
    - [ ] D2b：**Codex adapter 同步（canonical 改动的必做尾步）**：新增/改动任何 `.claude/skills/*`、
          `.claude/commands/*`、`.claude/agents/*` 后，跑 `python scripts/sync-codex-adapters.py` 生成对应
          `.agents/skills/*/SKILL.md`（skill）与 `.codex/agents/*.toml`；`.agents/skills/command-*/SKILL.md`
          这条生成路径只对应本 repo 既有的 slash command（如 `adopt-existing-repo`）——**bootstrap 已决策
          为 skill 形态（开放问题 1），不产生对应的 command-* skill**。所有生成物纳入**同一 commit**
          （`--check` 是 CI 门禁，不同步会红）。这是本 plan 里最容易被「只从 Claude 视角写」漏掉的一步。
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
- **【human 逐条拍板，2026-07-12】以下 6 条为 human 通过选择题形式给出的最终决策，直接落地，不再作为
  open question 讨论**（详见「未解决问题」1/2/3/4/6/7 的已决策条目）：
  1. **bootstrap 命令形态：skill（非独立 slash command/脚本）**。理由：Codex 侧会把
     `.claude/commands/*.md` 同步生成一个 `command-<name>` skill，多一层损耗；直接做成 skill，
     Claude/Codex 两侧从一开始就用同一份 `.claude/skills/bootstrap-project/SKILL.md` →
     `.agents/skills/bootstrap-project/SKILL.md`，不产生额外的 command-* 生成物。
  2. **`.template.toml` 的 origin 必须显式传参，不做自动推断/交互确认**。调用方须传
     `--origin <owner/repo>`，脚本不猜测上游 template repo slug。
  3. **origin 冲突默认报错停止，`--force` 才覆盖**。防止误覆盖他人已手工确认的版本锚点；纳入 A1
     幂等 state 模型。
  4. **语义归类 v1 只内置保守四类，不做外部规则文件/参数覆盖**。四类：template control item /
     保守导入 / 受保护 / 冲突。Codex 二审此前已确认外部规则文件若要做只能选 TOML；本轮 human 进一步
     决定第一版干脆不做该功能，避免过早引入配置 schema 与解析面。
  5. **真实 existing repo replay 用新找的 repo，不复用/复跑 Agent-R1 案例**，覆盖更多样的原生测试
     命令类型。
  6. **B（语义归类）与 C（smoke 合同）拆成两个独立 PR 交付**，不在同分支分阶段提交同一个 PR。见
     「Branch / worktree」新增说明。
- **【human 拍板，2026-07-12，单独批注】开放问题 5（smoke 合同「未验证」/「检测到但失败」时的 exit code
  语义）**：`prove` 命令 exit code **只在 adoption 自身 integrity 失败**（例如 tracked-byte hash 不匹配）
  时非 0；smoke 合同判定为「未验证」或「检测到但失败」时，exit code 仍为 0，但 report 必须**显式列出
  warning**（未验证/失败条目 + 原因），不能被静默当作已通过。理由：`prove`/smoke 合同验证的是「被迁移
  项目自身的测试是否可跑/通过」，这与 `adopt-existing-repo.py` 这个工具本身有没有正确、无损地完成搬移
  是两件事——后者才是这个命令「成功/失败」该负责的范围，前者只是关于目标项目健康度的信息，用显式
  warning 承载即可，不应该让「目标 repo 测试没过」伪装成「adoption 操作本身失败」而阻断整条流程。已
  同步落地到任务树 C1/C2/C3 与验证标准对应命令示例。

## 未解决问题

以下问题 issue 原文未给出足够细节，需要 human 拍板：

1. **【已决策 2026-07-12，human 逐条拍板】bootstrap 命令的名字/形态**：做成 **skill**
   （`.claude/skills/bootstrap-project/SKILL.md`），**不做独立 slash command**，也不是「只有脚本、
   无 skill 包装」的裸脚本形态。理由：Codex 侧对 `.claude/commands/*.md` 的 slash command 同步会生成
   一个 `command-<name>` skill，多一层生成损耗（`sync-codex-adapters.py:118-141`）；直接做成 skill，
   Claude/Codex 两侧从一开始就是同一份生成路径，不产生额外的 command-* skill。底层实现脚本仍可以是
   `scripts/bootstrap-project.py`（对齐 `adopt-existing-repo.py` 命名风格），由 skill 引导调用。
   原始问题（保留存档）：`scripts/bootstrap-project.py` 命名是否合适？是否需要 slash command 还是只靠
   脚本 + skill 文档即可？**双 runtime 考量**：若做成 slash command，`sync-codex-adapters.py` 会为它
   生成一个 `command-bootstrap-project` skill（多一个 Codex 表面 + 多一份需 same-commit 提交的生成物）。
   若只做「脚本 + skill」，两侧调用路径更对称、生成损耗更小。
2. **【已决策 2026-07-12，human 逐条拍板】`.template.toml` 的 origin 从哪来**：要求调用方**显式传
   `--origin <owner/repo>` 参数**，脚本**不做自动推断**（不猜 `git remote -v` / GitHub template 关系），
   **不做交互式确认**。
   原始问题（保留存档）：新建项目时脚本无法凭空知道上游 template repo 的 slug——是要求用户传参，还是
   尝试从 `git remote -v` / GitHub template 关系推断（若能推断，置信度不足时如何降级为「需人工确认」）？
3. **【已决策 2026-07-12，human 逐条拍板】bootstrap 的「幂等」定义边界**：第二次运行若发现
   `.template.toml` 已存在但 origin 与传入 `--origin` 不一致，**默认报错并停止**，不静默覆盖；需要
   覆盖必须显式加 `--force`。
   原始问题（保留存档）：应该报错阻止，还是当作「重新指认」直接覆盖？（关系到会不会误覆盖别人已经
   手工填好的版本锚点）
4. **【已决策 2026-07-12，human 逐条拍板】语义归类的分类粒度**：v1 **只内置保守四类**（template
   control item / 保守导入 / 受保护 / 冲突），**不做外部可配置规则文件**这个功能——不是「暂缓到后续
   增量」，而是第一版明确不做。
   原始问题（保留存档）：issue 只说「较粗」，没给出目标分类表。是否需要区分「项目代码」vs「项目文档」
   vs「CI/构建配置」等更细类别？分类规则要不要支持外部配置文件？若要外部化，只能选 TOML
   （`tomllib` stdlib）不能选 YAML（YAML 需第三方依赖，违反 no-deps 底线）。
5. **【已决策 2026-07-12，human 拍板】smoke 合同判定为「未验证」/「检测到但失败」时的 exit code
   语义**：`prove` 命令的 exit code **仍为 0**（不算 failed），但 report 里必须**显式标注 warning**，
   列出「未验证项 + 原因」，不能静默当作已通过。exit code 非 0（failed）**只**保留给真正的 adoption
   自身 integrity 失败（例如 tracked-byte hash 不匹配）。也就是说 exit code 实际只有两档取值
   （`0` / 非 0），但 report 要能承载三个可辨识状态：① `result=pass`（无 warning）；② `result` 为
   `fail`/`skipped`/`unknown`（exit 仍为 0，但 report 必须显式列出 warning + 原因）；③ integrity 失败
   （exit 非 0）。
   原始问题（保留存档）：`prove` phase 检测不到测试命令时，除了在 report 里写明 `unverified_reason`，
   是否需要让整体 `prove` 的 exit code 也非 0（目前 `prove` 只在 integrity 失败时才算 failed）？如果
   原生测试跑失败（例如原 repo 本身测试就有已知失败），是否应该硬 block 整个 adoption，还是记录为
   warning 并允许 human 决定是否继续？
6. **【已决策 2026-07-12，human 逐条拍板】验收标准 4「至少一个真实 existing repo replay」**：用**新找
   一个此前未测过的真实 repo**，不复用/复跑 Agent-R1 案例。
   原始问题（保留存档）：是否要求一个新的、之前没测过的真实 repo（覆盖更多样的原生测试命令类型），
   还是可以复用 Agent-R1 案例、在新合同下重跑并补充 smoke 结果说明即可？
7. **【已决策 2026-07-12，human 逐条拍板】B/C 落地顺序**：B（语义归类）与 C（smoke 合同）**拆成两个
   独立 PR**，不是同分支分阶段提交同一个 PR。见「Branch / worktree」新增说明。
   原始问题（保留存档）：B 与 C 都改 `adopt-existing-repo.py` 的不同 phase，是否要求分两个可独立
   review 的 commit/PR，还是可以在同一 PR 里一起交付？
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
      `scripts/bootstrap-project.py`（经由 `.claude/skills/bootstrap-project/SKILL.md` 引导调用，见开放
      问题 1 已决策），`--origin <owner/repo>` **必须显式传入**（开放问题 2 已决策，不接受省略/自动推断），
      第二次不报错、不重复写入，且在 **bootstrapped repo 内**三个 validator 全绿（Claude 侧配置 + Codex
      adapters 都自洽）。命令示例（占位，待 A1/A2 落地后定稿）：
      ```bash
      python scripts/bootstrap-project.py <empty-repo> --origin <owner/repo>
      python scripts/bootstrap-project.py <empty-repo> --origin <owner/repo>   # 第二次，应幂等
      python scripts/bootstrap-project.py <empty-repo> --origin <other/repo>   # origin 不一致，应报错停止
      python scripts/bootstrap-project.py <empty-repo> --origin <other/repo> --force  # 加 --force 才允许覆盖
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
- [ ] **真实 repo replay（tracked-byte integrity + smoke，新 repo，不复用 Agent-R1）**：`<real-repo>`
      须是本轮新找的一个此前未做过 adoption replay 的真实 repo（开放问题 6 已决策，不复用/复跑
      `agent-r1-adoption-replay-report.md` 对应案例）：
      ```bash
      python scripts/adopt-existing-repo.py <real-repo> --phase all --policy conservative --project-name <slug>
      python scripts/check-adoption-integrity.py <real-repo>
      echo $?   # 已决策（开放问题 5）：若该 repo 的 smoke result 为 fail/skipped/unknown，此处仍应输出 0；
                # 只有 tracked-byte integrity 不一致等 adoption 自身失败时才非 0
      ```
      生成的 `lab/docs/audits/template-adoption-report.md`（在目标 repo 内）需同时含 integrity 结果与
      smoke 合同结果（pass/fail/unknown + reason），并在本模板仓库留一份**新的** replay 报告存档
      （`lab/docs/audits/*.md`，格式可参考 `agent-r1-adoption-replay-report.md`，但内容对应新 repo 案例，
      不是对已有报告的覆盖或续写）。若该真实 repo 的原生测试命令检测不到或跑了但失败，`prove`/
      `check-adoption-integrity.py` 的 exit code 仍应为 `0`（已决策，开放问题 5），报告里必须能看到
      显式 warning，列出该条目与原因；不能因为 smoke 未通过就让 replay 的整体命令看起来「失败」。
- [ ] **负向 fixture 不静默通过**：新增/扩展 `lab/evals/adoption/run-adoption-smoke.py`（或新脚本），
      覆盖至少三类负向场景，断言方式按类型分层（**已决策，开放问题 5，2026-07-12 human 拍板**）：
      - 冲突文件 / 受保护路径命中：这两类是 adoption **integrity 层面**的阻塞，断言
        `check-adoption-integrity.py` 非 0 exit，且 blocker 在报告中可读。
      - smoke 命令失败（检测到命令但跑失败）/ 未检测到测试命令：**不**是 integrity 失败，`prove` 与
        `check-adoption-integrity.py` 的 exit code 仍为 `0`；断言点改为报告里存在显式、机器可读的
        warning 字段（列出该条目 + `unverified_reason`/失败原因），且该字段不能被静默省略——负向
        fixture 要专门断言「exit 0 但 warning 字段确实存在且非空」，防止未来实现把这个状态悄悄吞掉。
- [ ] **文档/结构同步**：
      ```bash
      python scripts/validate-governance.py --strict
      python scripts/check-anatomy-drift.py
      python scripts/check-agent-harness.py --strict
      python scripts/sync-codex-adapters.py --check
      git diff --check
      ```

## 下一步

1. ~~Human 在本文件批注，优先回答「未解决问题」里的 1/2/5~~ **已完成**：human 于 2026-07-12 通过选择题
   逐条拍板了「未解决问题」1/2/3/4/6/7（见 Plan revision log）；同日又对「未解决问题」5（smoke 合同
   unverified/fail 时的 exit code 语义）单独拍板（见 Plan revision log 最新条目）。至此本文件「未解决
   问题」1-7 均已决策，8/9/10 已在真实二审阶段收敛并落地为具体任务项（A5/B6/D2c），**已无剩余需要
   human 裁决的 open question**。
2. 落地顺序（决策 6 已确定 B/C 拆两个独立 PR）：先在本分支/worktree（`feat/12-bootstrap-adoption-proof`）
   交付 A（bootstrap，风险最小、无既有代码冲突）；随后 C（smoke 合同，改动集中在 `prove`）与 B（语义
   归类，改动面最大、需要重新设计 `normalize` 的消费方式）各自新开分支 + worktree、分别提独立 PR，
   C 先于 B（改动面更小、依赖更少）。「未解决问题」5 已拍板，C 的 PR 可直接按该 exit code 语义落地，
   不再有前置拍板阻塞。
3. 每个子任务/PR 落地后跑对应验证标准命令，再进入下一个。

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
- 2026-07-12 human 逐条拍板（选择题形式）：human 亲自对剩余开放问题中的 6 条给出最终决策，直接落地、
  不再作为 open question 讨论：① bootstrap 命令形态定为 skill（非独立 slash command/脚本），理由是
  Codex 侧 slash command 同步会多生成一层 `command-*` skill，做成 skill 从一开始就双侧一致；②
  `.template.toml` 的 origin 要求调用方显式传 `--origin` 参数，不做自动推断、不做交互式确认；③ 幂等
  冲突处理改为「origin 不一致时报错停止，需要覆盖必须显式加 `--force`」，不静默覆盖；④ existing-repo
  语义归类粒度 v1 只内置保守四类（template control item / 保守导入 / 受保护 / 冲突），不做外部可配置
  规则文件，第一版明确不做该功能；⑤ 验收标准「至少一个真实 existing repo replay」要求新找一个此前
  未测过的真实 repo，不复用/复跑 Agent-R1 案例；⑥ B（语义归类）与 C（smoke 合同）拆成两个独立 PR 交付，
  不在同分支分阶段提交同一个 PR。已同步更新「当前目标」隐含约束、「Allowed paths」（去掉
  `.claude/commands/bootstrap-project.md`）、「Branch / worktree」（新增 PR 拆分说明）、任务树 A1/A2/
  B1/B3/C4/D2b、「当前决策」（新增汇总小节）、「未解决问题」1/2/3/4/6/7（改写为已决策、保留原始问题
  存档）与「验证标准」相应命令示例。「未解决问题」5（smoke 合同 unverified 处理策略）本轮未被 human
  拍板，仍保留为待决问题。人类最终批准仍待定（本轮批注生效，但整体计划仍需 human 最终 approve 才能
  进入 commit gate）。
- 2026-07-12 human 补充拍板（开放问题 5）：human 就本文件最后一条剩余 open question——smoke 合同判定
  为「未验证」时 `prove` 命令的 exit code 语义——给出决策：exit code 仍为 0（不算 failed），但报告
  必须显式标注 warning，列出「未验证项 + 原因」，不能静默当作已通过；exit code 非 0（failed）只保留
  给真正的 adoption 自身 integrity 失败（如 tracked-byte hash 不匹配）。已同步更新任务树 C1/C2/C3、
  验证标准「负向 fixture 不静默通过」与「真实 repo replay」两条命令示例、「当前决策」新增小节、
  「未解决问题」5（改写为已决策、保留原始问题存档）与「下一步」第 1/2 点。核对全文后确认：本文件
  「未解决问题」1-7 均已由 human 拍板决策，8/9/10 已在真实 Codex 二审阶段收敛并落地为具体任务项
  （A5/B6/D2c），**本文件目前没有剩余需要 human 裁决的 open question**。人类最终批准仍待定（本轮
  批注生效，但整体计划仍需 human 最终 approve 才能进入 commit gate）。
