# 自动化项目 bootstrap 并增强 existing-repo adoption proof

Status: verified · 2026-07-13 · fresh APPROVE 6182630/35c6196/f33ff9c；本地 merges 3bad60d/1a72762/36ce42a；27 场景 smoke 全绿

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
  - [x] A. 新项目 bootstrap 命令（实现见 `scripts/bootstrap-project.py` + `.claude/skills/bootstrap-project/SKILL.md`，
        2026-07-12，`feat/12-bootstrap-adoption-proof`；A5 含 fresh Codex session runtime smoke，已补齐，见下）
    - [x] A1：设计 bootstrap 的幂等 state 模型（第二次运行不重复写、不报错、给出「已确认」而非「已执行」；
          origin 冲突时默认报错停止、`--force` 才覆盖，见开放问题 3 已决策）。
          **语义定稿（2026-07-13，Codex review MAJOR-2 修复）**：幂等分两层——①
          `state/state.json` + `template-bootstrap-report.md` 是**内容稳定**的：确认性运行
          （去除时间戳、把 created/confirmed/overwritten 归一为「锚点在位」后无实质差异）
          **不改写**这两个文件，字节级不变，`created_at` 语义是「内容最后一次变化的时间」而非
          「最后一次运行时间」；② `state/run-log.jsonl` 是**追加式审计日志**：每次非 dry-run
          运行必追加一行（运行时间戳 + 本次 transition + `content_changed` 标记），追加式增长是
          审计日志的天然语义，不算破坏幂等。smoke 对第二次运行做「前后文件状态快照对比」严格断言
          （state/report 字节相同、run-log 恰好 +1 行）。
    - [x] A2：实现自动化子步骤：`.template.toml` 生成/确认（origin+version 锚点）——**origin 由调用方通过
          `--origin <owner/repo>` 显式传入，脚本不自动推断（不猜 `git remote -v`/GitHub template 关系）、
          不做交互式确认**（开放问题 2 已决策）；若目标 repo 已存在 `.template.toml` 且其中 origin 与传入
          `--origin` 不一致，**默认报错并停止，不静默覆盖**，需要覆盖必须显式加 `--force`（开放问题 3
          已决策，纳入 A1 的幂等 state 模型设计）；`git config core.hooksPath .githooks`、
          `sync-codex-adapters.py`、`validate-governance.py`
    - [x] A3：实现「需 human 信息才能做」的子步骤上报（CODEOWNERS owner、PROJECT.md 填写、
          要不要删无用目录）——不猜测、只在使用报告里列成 blocker/待办
    - [x] A4：Codex/Claude 项目配置加载清单（bootstrap 完成后打印/写入）。这条不是「抄一遍验收标准」，
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
    - [x] A5：synthetic fixture：在空 Git repo 上跑两次，断言第二次幂等 + 在**该 bootstrapped repo 内**
          跑 `validate-governance.py --strict`、`check-agent-harness.py --strict`、`sync-codex-adapters.py --check`
          三者全绿，证明两侧配置/adapter **静态自洽**。另在实现完成后从该 repo 启动一个 **fresh Codex session**，
          记录最小 runtime smoke：repo `AGENTS.md` guidance 可见、repo-local `.agents/skills` 可发现，并用一个无副作用
          的受保护路径 synthetic probe 或 hook 诊断证据确认 project `PreToolUse` 地板已加载。当前这次真实 Codex session
          能证明现有 repo 的 guidance/skills 已被发现，但它启动时 bootstrap 功能尚不存在，不能替代该验收。
          **实现状态（2026-07-12）**：synthetic fixture 部分已完成并绿——`lab/evals/bootstrap/run-bootstrap-smoke.py`
          断言幂等/origin 冲突拒绝/`--force` 覆盖，并在 bootstrapped repo 内跑通三个 validator。**fresh Codex
          session 的 runtime smoke 部分本轮已补齐（2026-07-12，真实 Codex gpt-5.6-sol session，medium effort）**：
          用 `git archive main` 铺出真实模板内容（非空壳）到 `/tmp/bootstrap-smoke-target2`，跑
          `scripts/bootstrap-project.py --origin ...` 完成 bootstrap（`.template.toml`/`core.hooksPath`/
          `sync-codex-adapters`/`validate-governance` 全部 `ok`），随后从该 bootstrapped repo 启动一个真实
          Codex fresh top-level session 做观察，结果：① `AGENTS.md` guidance **可见**——system context 启动即
          注入，非事后读取；② `.agents/skills/` **可发现**——枚举出 21 个 skill，抽查 `anatomy-drift-control/SKILL.md`
          内容完整可读；③ project hook **未观察到触发痕迹**——`.codex/config.toml` 确实挂了
          `format_changed_python.py`/`zh_review_advisory.py`，但用 `apply_patch` 在仓库根新建
          `SMOKE_PROBE.md`（无害探针，事后已删）时，工具只返回空结果，没有任何可归因到这两个 hook 的
          输出/副作用；④ trust 状态**已确认 trusted**（`~/.codex/config.toml` 里 `/tmp` 与
          `/tmp/bootstrap-smoke-target2` 均标 `trust_level = "trusted"`），启动时没有 trust 提示/警告。
          **结论**：guidance/skill discovery 两项证据确凿为「可用」；hook 加载证据仍然只能到「trusted 状态下
          也没观察到可归因的 hook 副作用」——这与本文件此前反复强调的"工具调用成功不等于 PreToolUse/PostToolUse
          确实执行"完全一致，本轮没有推翻这个保守结论，只是把它从"没测过"变成了"测过、仍是 unknown/未观察到"，
          不冒充"hook 已确认生效"。这条 runtime 证据已经是本 issue 范围内能拿到的最真实结果，不再是遗留空项。
          **更正（2026-07-13，Codex review MAJOR-4，原记录保留如上、不删改）**：上述 runtime smoke 用
          `git archive main` 铺底，而 main **不含本分支新增的 bootstrap 产物**——被 bootstrap 的目标 repo
          内容（含其 `scripts/`、`.claude/`、validators）来自 main，不是候选实现；该证据只能证明「本分支的
          bootstrap 脚本能把一份 main 内容的 repo 落地 + Codex 在其中能发现 guidance/skills」，不能证明候选
          commit 的完整树可用。正确方法已定：**从候选 commit（HEAD）`git archive` 构建目标、在派生副本内跑
          它自己的 `scripts/bootstrap-project.py`（self-bootstrap，README 真实路径），并在证据记录里写明被测
          commit hash**——`lab/evals/bootstrap/run-bootstrap-smoke.py` 已改为此法并打印被测 hash。fresh Codex
          session 的 runtime smoke 需按新方法**重跑**；该步需要真实 Codex runtime，本 worker 无法执行，
          **留给监控员**（步骤：① 在模板 repo 候选 commit 上 `git archive HEAD | tar -x -C /tmp/<dir>`；
          ② `cd /tmp/<dir> && git init && git add . && git commit`；③ 在副本内跑
          `python scripts/bootstrap-project.py . --origin <owner/repo>` 至全 `ok`；④ 记录被测 commit hash；
          ⑤ 从该副本启动 fresh Codex session，复核 guidance 可见 / `.agents/skills` 可发现 / hook 触发痕迹三项）。
    - [x] A6：README「派生后的落地步骤」改写，指向新命令；仍保留人工兜底步骤说明，并保留「Codex 需先 trust
          repo」这条无法脚本化的手工前提
  - [x] B. existing-repo 语义归类增强（开放问题 7 已决策：独立 PR，不与 C 合并）
    - [x] B1：归类维度**已决策为内置保守四类**（开放问题 4，2026-07-12 human 拍板）：`template control
          item`（命中 CONTROL_ITEMS 且 hash 未变，留在原处）/ `保守导入`（其余项目代码、文档等整体归入
          `lab/code/imported/<slug>/`）/ `受保护`（命中 `lab/data/**` 等 forbidden paths，登记 blocker
          不移动）/ `冲突`（目标位置已存在不一致内容，登记 blocker 停下）；四类写进 discover 输出的
          per-entry 结构（目标位置 + 理由 + 是否 blocker）
    - [x] B2：`--dry-run` 模式：只打印归类计划（目标位置 + 理由 + blocker），不落盘
    - [x] B3：**（已决策，开放问题 4：不做外部规则文件/参数覆盖）** 四类判断逻辑全部内置在
          `adopt-existing-repo.py` 内，v1 不提供规则文件或额外 CLI 参数覆盖入口；仍需向后兼容现有
          `--policy conservative` 行为（四类判断是该 policy 下的具体化，不新增 policy 值）
    - [x] B4：`normalize` 消费归类计划而不是硬编码的二元判断；冲突/受保护路径仍然停下报告
    - [x] B5：更新 `lab/evals/adoption/run-adoption-smoke.py` 或新增 fixture，覆盖「多种归类结果」
          与「归类失败/blocker 不静默继续」两类断言
    - [x] B6：adoption 完成报告复用 A4 的双 agent surface 加载清单/诊断逻辑，至少报告 Claude/Codex
          文件就位状态、adapter 静态一致性、`core.hooksPath` 状态与 Codex trust 的 out-of-band 前提；不在
          adoption 内假装已替 human 完成 trust。
  - [x] C. 统一 runtime/smoke 验证合同（开放问题 7 已决策：独立 PR，不与 B 合并；实现见
        `feat/12c-smoke-contract`，2026-07-12，详见本文件 Plan revision log 最新条目）
    - [x] C1：定义 smoke 合同 schema：`command_source`（auto-detected/explicit/none）、`command`、
          `result`（pass/fail/skipped/unknown）、`unverified_reason`（未验证时必填）。**已决策（开放
          问题 5，2026-07-12 human 拍板）**：`result` 与 `prove` 的 process exit code **解耦**——
          `result` 为 `fail`/`skipped`/`unknown`（即「检测到但失败」或「未验证」）时，exit code 仍为
          `0`，但 report 必须生成一个显式、机器可读的 warning 字段（列出该条目 + 原因），不能被静默省略；
          exit code 非 0 只保留给 adoption 自身的 integrity 失败（例如 tracked-byte hash 不匹配）。
          **实现**：`scripts/adopt-existing-repo.py` 的 `evaluate_smoke()`，schema 名
          `template-adoption-smoke-v1`。
    - [x] C2：`prove` phase 按合同写 adoption report，明确区分「未检测到测试命令」与「检测到但失败」
          与「跑通过」三种状态。**已决策（开放问题 5）**：非 pass 状态**不**改变 `prove` 的 exit code
          （仍为 0），但必须在 report 里可被程序判定为「未证明/未通过」——这个判定由显式、结构化的
          warning 字段承载（而非靠 exit code），供上游流程/human 读取。**实现**：`prove()` 写
          `report["smoke"]` + `report["warnings"]`；`write_report()` 渲染 Smoke/Warnings 小节；
          `main()` 改为按 `prove` 返回的 `integrity.ok` 决定 process exit code（**发现并修复一个真实
          既有 bug**：此前 `prove` 从不让整体进程非 0 退出，即使 integrity 失败）。
    - [x] C3：`check-adoption-integrity.py`（或新增校验点）在 smoke 状态非 pass 时不能被上游流程当作
          静默通过。**已决策（开放问题 5）**：该校验点自身的 exit code 语义与 `prove` 一致（只在
          tracked-byte integrity 不一致等 adoption 自身失败时非 0；smoke 非 pass 不触发非 0），断言点
          改为「report 中存在显式 warning 字段且不可被忽略」而不是要求 exit code 非 0；至少要有一个
          负向 fixture 专门断言这个「exit 0 + 显式 warning」组合，防止未来实现把 warning 字段默默丢掉、
          伪装成全绿。**实现**：`integrity_result()` 新增 `unresolved_blockers`（读最近一次
          `normalize` phase-log 的 blockers，未解决时纳入 `ok` 判定——conflict/受保护路径属于
          adoption 自身完整性失败，不是 smoke）；`check-adoption-integrity.py` 新增
          `latest_smoke_warnings()`，文本/`--json` 输出都显式呈现 `smoke_warnings`/`BLOCKED <path>`，
          exit code 不受影响。负向 fixture：`lab/evals/adoption/run-adoption-smoke.py` 的
          `scenario_blocked_normalize`（断言两脚本均非 0 exit + blocker 可读）、
          `scenario_smoke_failing_command` / `scenario_smoke_undetected`（均断言 exit 0 + 显式非空
          warning，防止被静默吞掉）。
    - [x] C4：至少一个真实 existing repo replay，同时报告 tracked-byte integrity 与新 smoke 合同结果。
          **已决策（开放问题 6，2026-07-12 human 拍板）：新找一个此前未测过的真实 repo，不复用/复跑
          Agent-R1 案例**（覆盖更多样的原生测试命令类型），产出独立于
          `agent-r1-adoption-replay-report.md` 的新 replay 报告存档。**实现**：选用
          `tartley/colorama`（`841634e`，2026-07-12 拉取），命中 `detect_test_command()` 的
          `Makefile` `test:` 检测分支（与 Agent-R1「完全未检测到」不同），原生测试因目标 repo
          未 bootstrap venv 而真实失败——两脚本均 exit 0，report/`--json` 均带显式非空 warning。
          报告见 `lab/docs/audits/colorama-adoption-replay-report.md`。
  - [x] D. 文档/结构同步（A/B/C 各分支均已落地其归属子项；本地 B+C 集成继续保留 smoke
        schema/真实 replay、语义归类 skill、共享 postflight、ANATOMY 与状态证据）
    - [x] D1：`scripts/ANATOMY.md`、`.claude/ANATOMY.md`、root `ANATOMY.md`（如涉及新顶层路径）——
          本轮未新增顶层路径，root `ANATOMY.md` 不需要改动
    - [x] D2：`.claude/skills/adopt-existing-repo/SKILL.md` 已随 B1-B4 更新语义归类步骤；
          `bootstrap-project` skill 已随 A 新增（`.claude/skills/bootstrap-project/SKILL.md`）
    - [x] D2b：**Codex adapter 同步（canonical 改动的必做尾步）**：新增/改动任何 `.claude/skills/*`、
          `.claude/commands/*`、`.claude/agents/*` 后，跑 `python scripts/sync-codex-adapters.py` 生成对应
          `.agents/skills/*/SKILL.md`（skill）与 `.codex/agents/*.toml`；`.agents/skills/command-*/SKILL.md`
          这条生成路径只对应本 repo 既有的 slash command（如 `adopt-existing-repo`）——**bootstrap 已决策
          为 skill 形态（开放问题 1），不产生对应的 command-* skill**。所有生成物纳入**同一 commit**
          （`--check` 是 CI 门禁，不同步会红）。这是本 plan 里最容易被「只从 Claude 视角写」漏掉的一步。
          实现确认：`.agents/skills/bootstrap-project/SKILL.md` 已生成，未生成 `command-bootstrap-project`。
    - [x] D2c：bootstrap 与 adoption 共用 `scripts/_agent_surface.py` 的 agent-surface postflight
          数据结构/渲染函数，避免两套 Claude/Codex 加载清单发生文案和判定漂移（随 B6 落地）。
    - [x] D3：`README.md`、`DESIGN.md` §10 能力清单数量同步（新增 script/skill/command 时 Claude 侧与
          Codex 生成侧的计数都要对上）。**C 补充（2026-07-12）**：C 未新增 script/skill/command，
          `DESIGN.md` §10 数量不变；`README.md`、`scripts/README.md` 补充 smoke 合同的 exit-code/
          warning 解耦说明。
    - [x] D4：`memory/current-status.md` / `session-tree.md` 记录本 feature 落地状态。**C 补充
          （2026-07-12）**：两文件均新增 issue #12 part C 专属小节（分支、决策、命令结果、遗留问题、
          下一步）。
    - [x] D5：`scripts/CLAUDE.md` 措辞更新——现文案「三个脚本只读、无副作用、无第三方硬依赖」已与现实不符
          （`adopt-existing-repo.py` 已有写副作用，本轮 `bootstrap-project.py` 再加一个 mutating 脚本）；需把
          「只读/无副作用」收敛为「只读校验脚本 vs 有副作用的 mutating 脚本」两类描述，保留「无第三方硬依赖」底线。
    - [x] D6：`python scripts/validate-governance.py --strict` + `check-agent-harness.py --strict` +
          `sync-codex-adapters.py --check` 全绿。**C 补充（2026-07-12）**：对应 C 的改动集重跑
          `validate-governance.py --strict`（本机需 `uv run --with pyyaml` 绕过预置环境缺 PyYAML 的
          问题，非本轮引入，已用 `git stash` 核对）、`check-anatomy-drift.py`、
          `sync-codex-adapters.py --check`、`check-same-commit.py --staged`、`git diff --check`，
          全绿；另跑 `lab/evals/adoption/run-adoption-smoke.py`（2026-07-13 两轮复审修正后为七场景全过；
          初版「四场景全过」声明不成立，见「负向 fixture 不静默通过」条目的修正记录）与
          `lab/evals/bootstrap/run-bootstrap-smoke.py`（回归，确认未破坏 A）。

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

- [~] **bootstrap 幂等 + 双 runtime 静态自洽 + Codex fresh-session smoke**：在空 Git repo 上跑两次
      `scripts/bootstrap-project.py`（经由 `.claude/skills/bootstrap-project/SKILL.md` 引导调用，见开放
      问题 1 已决策），`--origin <owner/repo>` **必须显式传入**（开放问题 2 已决策，不接受省略/自动推断），
      第二次不报错、不重复写入，且在 **bootstrapped repo 内**三个 validator 全绿（Claude 侧配置 + Codex
      adapters 都自洽）。命令（2026-07-12 已跑通，见 `lab/evals/bootstrap/run-bootstrap-smoke.py` 与
      `memory/current-status.md` Commands+results）：
      ```bash
      python scripts/bootstrap-project.py <empty-repo> --origin <owner/repo>
      python scripts/bootstrap-project.py <empty-repo> --origin <owner/repo>   # 第二次，应幂等
      python scripts/bootstrap-project.py <empty-repo> --origin <other/repo>   # origin 不一致，应报错停止
      python scripts/bootstrap-project.py <empty-repo> --origin <other/repo> --force  # 加 --force 才允许覆盖
      python <empty-repo>/scripts/validate-governance.py --strict
      python <empty-repo>/scripts/check-agent-harness.py --strict     # 覆盖 Claude/Codex 配置可解析(#5) + adapter 同步(#6)
      python <empty-repo>/scripts/sync-codex-adapters.py --check      # 证明 Codex adapters 已就位且新鲜
      ```
      三个静态检查已全绿（**静态自洽部分完成**）。**Codex fresh-session smoke 部分已补齐（2026-07-12）**：
      用 `git archive main` 铺出真实模板内容到临时 repo、跑 `bootstrap-project.py`，再从该 bootstrapped
      repo 启动一次真实 Codex gpt-5.6-sol session 观察——guidance/skill discovery 均可见/可发现；project
      hook 在 trusted 状态下仍未观察到可归因的触发痕迹（见本文件 A5 状态记录的完整结论）。
      **更正（2026-07-13，Codex review MAJOR-4）**：该次证据用的是 main 内容铺底，验证的不是候选实现；
      需按 A5 更正段的新方法（`git archive HEAD` + self-bootstrap + 记录被测 commit hash）重跑，
      fresh Codex session 一步留给监控员执行。另：MAJOR-1 修复后，主流程命令形态为在派生 repo 内
      `python scripts/bootstrap-project.py . --origin <owner/repo>`（self-bootstrap，smoke 已按此路径断言）。
- [x] **模板版本锚点 + 加载清单**：bootstrap 后 `<empty-repo>/.template.toml` 存在且可被
      `scripts/template-sync.py` 的 `read_template_toml()` 解析；bootstrap 输出的 Codex/Claude 加载清单
      须与 `check-agent-harness.py` 的实际判定一致（不是手写、易漂移的静态文案），且清单显式区分：
      - **自动可就位**：`.claude/settings.json`、`.claude/agents|skills|commands/*`、`.codex/config.toml`、
        `.codex/agents/*.toml`、`.agents/skills/*/SKILL.md`（后两者由 `sync-codex-adapters.py` 生成）。
      - **需 human out-of-band**：Codex trust 本 repo（`config.toml` hooks 生效前提）——清单里必须标成待办，
        不能默认已生效（见未解决问题 9）。
      已验证：`.template.toml` 可被 `read_template_toml()` 正确解析（手工冒烟确认）；
      `bootstrap-project.py` 的 `agent_surface_checklist()` 把「文件计数」标注为辅助展示，明确以
      `check-agent-harness.py --strict` / `sync-codex-adapters.py --check` 的返回码为机器事实源，
      Codex trust 固定标 `needs-human`/`unknown`，不猜测已生效。
- [ ] **adoption dry-run 归类计划**：
      ```bash
      python scripts/adopt-existing-repo.py <fixture> --phase discover --dry-run
      ```
      输出/写入的归类计划里，每个 root entry 都能读到目标位置、理由、是否 blocker。
- [x] **真实 repo replay（tracked-byte integrity + smoke，新 repo，不复用 Agent-R1）**：`<real-repo>`
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
      **实现（2026-07-12，`feat/12c-smoke-contract`）**：`<real-repo>` = `tartley/colorama`
      @ `841634e`（新找，未测过；命中 `Makefile` `test:` 检测分支，与 Agent-R1 不同）。两条命令
      均 `exit 0`；`present 49/49`、`unresolved_blockers=[]`；`smoke_warnings` 非空
      （`original_test` fail + reason）。存档报告：
      `lab/docs/audits/colorama-adoption-replay-report.md`。
- [x] **负向 fixture 不静默通过**：新增/扩展 `lab/evals/adoption/run-adoption-smoke.py`（或新脚本），
      覆盖至少三类负向场景，断言方式按类型分层（**已决策，开放问题 5，2026-07-12 human 拍板**）：
      - 冲突文件 / 受保护路径命中：这两类是 adoption **integrity 层面**的阻塞，断言
        `check-adoption-integrity.py` 非 0 exit，且 blocker 在报告中可读。
      - smoke 命令失败（检测到命令但跑失败）/ 未检测到测试命令：**不**是 integrity 失败，`prove` 与
        `check-adoption-integrity.py` 的 exit code 仍为 `0`；断言点改为报告里存在显式、机器可读的
        warning 字段（列出该条目 + `unverified_reason`/失败原因），且该字段不能被静默省略——负向
        fixture 要专门断言「exit 0 但 warning 字段确实存在且非空」，防止未来实现把这个状态悄悄吞掉。
      **实现（2026-07-12；2026-07-13 按 Codex 初审 2 条 MAJOR 修正）**：
      `lab/evals/adoption/run-adoption-smoke.py` 现为七场景（happy-path 之外六个负向）：
      - `scenario_blocked_normalize`（受保护路径 `checkpoints/`，断言两脚本均非 0 exit + blocker
        文本/`--json unresolved_blockers` 可读）。
      - `scenario_blocked_conflict`（**2026-07-13 补**：destination-exists 冲突——目标位置
        `lab/code/imported/<slug>/data.txt` 已存在不一致内容；断言 adopter 非 0 exit 停下、冲突
        两侧字节均未被动、`BLOCKED destination exists: ...` 文本与 `--json unresolved_blockers`
        均可读。初版声称一个 fixture 同时覆盖「冲突文件/受保护路径」两个子类，实际只测了受保护
        路径，该声明不成立，现分拆为两个独立 fixture）。
      - `scenario_smoke_failing_command`（检测到但跑失败，断言两脚本 exit 0 + report/`--json
        smoke_warnings` 非空。**2026-07-13 修**：初版 fixture 是 pytest 风格模块级函数，
        `unittest discover` 不收集，实际 Ran 0 tests——Python ≤3.11 下 exit 0 会被记成 `pass`
        且场景自身断言失败，≥3.12 下靠 NO_TESTS_RAN exit 5 才「碰巧」记成 fail——从未真正验证过
        「检测到且真实跑失败」；现改为必然被 unittest 收集且失败的 `unittest.TestCase`，并新增
        从 phase-log 的 smoke exec 断言 `Ran 1 test` + `FAILED`，防止 fixture 再退化成
        Ran 0 tests 而不被发现）。
      - `scenario_smoke_undetected`（无可探测命令，断言 `skipped` + 同样的 exit-0-with-warning
        组合）。
      - `scenario_smoke_timeout`（显式命令超时，断言 `unknown`、`timeout=true`、exit 0 且 warning
        非空，补齐 C1 的第四种结果态）。
      - `scenario_legacy_phase_state_rejected`（旧 `template-adoption-plan-v1` 缺少
        `test_command_source` 时，`prove` fail-closed 并要求重新执行 `discover`，不再产生
        `command_source=none` 但命令实际存在的矛盾记录）。
      `python3 lab/evals/adoption/run-adoption-smoke.py` 七场景全过（2026-07-13 真实重跑，
      Python 3.12.3）；此前「四/五场景全过」的证据声明已被后续复审扩充，以本条为准。
- [x] **文档/结构同步**（针对本分支 A 的改动集验证；B/C 落地后各自分支还需再跑一遍）：
      ```bash
      python scripts/validate-governance.py --strict
      python scripts/check-anatomy-drift.py
      python scripts/check-agent-harness.py --strict
      python scripts/sync-codex-adapters.py --check
      git diff --check
      ```
      2026-07-12 在 `feat/12-bootstrap-adoption-proof` 全部跑通，另加
      `python scripts/check-same-commit.py --staged`（`OK —— 5 处结构改动，对应 anatomy 已同变更集更新`）。
      **C 补充（2026-07-12，`feat/12c-smoke-contract`）**：对应 C 的改动集重跑同一组命令 +
      `check-same-commit.py --staged`，全绿（本机预置环境缺 PyYAML，用 `uv run --with pyyaml`
      跑 `validate-governance.py --strict`，已用 `git stash` 核对该 warning 与本轮改动无关）；
      另跑 `lab/evals/adoption/run-adoption-smoke.py`（2026-07-13 两轮复审修正后为七场景全过；初版
      「四场景全过」声明不成立，见「负向 fixture 不静默通过」条目的修正记录）与
      `lab/evals/bootstrap/run-bootstrap-smoke.py`（回归，确认未破坏 A）。

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
- 2026-07-12 实现（Claude, `feat/12-bootstrap-adoption-proof` worktree）：落地任务树 A（A1-A6）+
  D 里归属 A 的子项（D1、D2 的 bootstrap 新增部分、D2b、D3、D4、D5、D6）。新增
  `scripts/bootstrap-project.py`（幂等：`.template.toml` origin+version 锚点、`core.hooksPath`、
  `sync-codex-adapters.py`、`validate-governance.py`；origin 冲突默认报错停止、`--force` 才覆盖；
  human-only 步骤只报告不代做；输出 Claude/Codex 加载清单，以 `check-agent-harness.py --strict` /
  `sync-codex-adapters.py --check` 为机器事实源）+ `.claude/skills/bootstrap-project/SKILL.md`
  （已生成对应 `.agents/skills/bootstrap-project/SKILL.md`，未生成 command-* skill）+
  `lab/evals/bootstrap/run-bootstrap-smoke.py` synthetic fixture（幂等/冲突拒绝/`--force`/三个
  validator 全绿全部验证通过）；同步更新 `scripts/ANATOMY.md`、`.claude/ANATOMY.md`、`lab/ANATOMY.md`、
  `README.md`、`DESIGN.md` §10（skills 12→13、Codex adapter skills 20→21、scripts 9→10）、
  `scripts/README.md`、`scripts/CLAUDE.md`（D5 措辞修正）、`memory/current-status.md`、
  `memory/session-tree.md`。`validate-governance.py --strict`、`check-agent-harness.py --strict`、
  `sync-codex-adapters.py --check`、`check-anatomy-drift.py`、`check-same-commit.py --staged`、
  `git diff --check` 全绿。**A5 fresh-Codex-session runtime smoke 已补齐**（2026-07-12，真实 Codex
  gpt-5.6-sol，medium effort，对着用 `git archive main` 铺出的真实内容 bootstrap 出的临时 repo 跑）：
  guidance/skill discovery 均确认可用；project hook 在 trusted 状态下仍未观察到可归因触发痕迹（如实
  记录为 unknown，非"已确认失效"，也非"已确认生效"）。B（语义归类）、C（smoke 合同）与 D2c 按既有
  决策/上层任务边界未在本分支涉及。未 push、未开 PR、未 merge——按边界交由上层/human 决定后续 gate。
- 2026-07-12 A5 runtime smoke 补齐（监控员编排，真实 Codex gpt-5.6-sol，medium effort）：A 部分实现落地后，
  用 `git archive main` 铺出真实模板内容到临时 repo（非空壳），跑 `scripts/bootstrap-project.py` 完成
  bootstrap（三项 `ok`），随后从该 bootstrapped repo 启动一次真实 Codex fresh top-level session 观察：
  ① `AGENTS.md` guidance 确认可见（启动即注入 system context）；② `.agents/skills/`（21 个）确认可发现、
  内容可读；③ project hook（`format_changed_python.py`/`zh_review_advisory.py`）在 trusted 状态下**未观察到**
  可归因的触发痕迹（`apply_patch` 写入探针文件后工具仅返回空结果）；④ trust 状态本次确认为 `trusted`
  （`~/.codex/config.toml` 里 `/tmp` 与目标临时 repo 均为 trusted）。结论与本文件此前"工具调用成功不等于
  hook 已执行"的保守立场一致，未推翻，只是把 A5 从"未测"变成"已测、hook 部分仍是 unknown"。A5 任务勾选为
  已完成；相应更新了 A5 任务描述、验证标准对应条目、任务 A 顶部状态注记与本轮实现落地小节。人类最终批准
  仍待定。
- 2026-07-13 Codex review（gpt-5.6-sol，high，正式合并前审查）5 findings 修复（干将·修·bootstrap，
  `feat/12-bootstrap-adoption-proof`）：① MAJOR-1 README 主流程（派生 repo 内 self-bootstrap `.`）此前被
  `target == TEMPLATE_ROOT` 防护直接拒绝——防护判据改为「目标的 git remote 指向与 `--origin` 相同的
  slug ⇒ 目标是上游模板 repo 自身 ⇒ 拒绝」（见 `refuse_upstream_template()` 注释；remote 只用于
  自污染检测，`--origin` 仍不做推断），smoke 改为调用目标副本自己的脚本验证真实路径，并补「上游
  checkout 被拒且零改动」负向断言；② MAJOR-2 幂等语义定稿为两层（state/report 内容稳定不改写、
  run-log 追加审计），见 A1 语义定稿段，smoke 补第二次运行前后文件快照严格断言；③ MAJOR-3 缺
  `.githooks` 由 skipped 改为硬失败（exit 非零），补负向测试；④ MAJOR-4 A5 runtime smoke 证据更正
  （原用 main 铺底，非候选实现；新方法 `git archive HEAD` + 记录被测 hash，fresh Codex session 重跑
  留给监控员，见 A5 更正段）；⑤ MINOR-5 `human_todo_items()` 补第五项 `.reference-docs` doctrine
  版本，对齐 README/plan A3。
- 2026-07-13 A5 重跑（监控员编排，按 fix commit 058dc3e 的更正方法）：`git archive HEAD`（被测 commit
  058dc3e340c2eea9363c02246550b54b74cadc91）铺底 `/tmp/bootstrap-a5-rerun`，目标副本内 self-bootstrap 路径
  全 ok（state/report written、.template.toml created、hooksPath ok、sync ok、governance ok、todo 5 项——
  MINOR-5 修复后的第五项已出现）。随后真实 fresh Codex（gpt-5.6-sol）session 观察：① `AGENTS.md` guidance
  启动即注入，可见；② `.agents/skills/` 枚举 21 个，抽查 `bootstrap-project/SKILL.md` 可读——**候选实现新增
  的 skill 出现在被测副本里**，修正了上一轮"验证的是 main 内容"的缺陷；③ hook 无可归因触发痕迹（与此前
  观察一致，仍记 unknown）。A5 证据链此次闭合于候选 commit。复审 verdict 另行等待中。
- 2026-07-12 实现（Claude，`feat/12c-smoke-contract` worktree，base 是 `feat/12-bootstrap-adoption-proof`）：
  落地任务树 C（C1-C4）+ D 里归属 C 的子项（D1、D3、D4、D6；D2/D2c 仍留给 B）。
  `scripts/adopt-existing-repo.py`：`detect_test_command()` 改返回 `(command, command_source)`；新增
  `evaluate_smoke()` 按 C1 schema（`command_source`/`command`/`result`/`unverified_reason`）跑并分类
  被迁移项目自身原生测试；`prove()` 写结构化 `smoke` + `warnings` 到 report；`integrity_result()`
  新增 `unresolved_blockers`（读最近一次 normalize phase-log，未解决的 conflict/受保护路径 blocker
  纳入 adoption 自身完整性判定）；`main()` 改为按 `prove` 返回的 `integrity.ok` 决定 process exit
  code——**过程中发现并修复一个真实既有 bug**：此前 `prove` 从不让 `adopt-existing-repo.py` 整体进程
  在 integrity 失败时非 0 退出。`scripts/check-adoption-integrity.py`：新增
  `latest_smoke_warnings()`，文本/`--json` 输出显式呈现 `smoke_warnings`/`BLOCKED <path>`，exit code
  语义不变（只反映 `integrity_result().ok`，现在天然覆盖未解决 blocker）。
  `lab/evals/adoption/run-adoption-smoke.py` 从单一 happy-path 扩成七场景（happy-path 回归 +
  `scenario_blocked_normalize` + `scenario_blocked_conflict` + `scenario_smoke_failing_command` +
  `scenario_smoke_undetected` + `scenario_smoke_timeout` +
  `scenario_legacy_phase_state_rejected`），冲突文件与受保护路径各自独立 fixture。**2026-07-13 按 Codex 初审
  修正**：初版只有四场景——smoke-fail fixture 是 pytest 风格函数、不被 `unittest discover` 收集
  （实际 Ran 0 tests，从未真正验证「检测到且真实跑失败」），且缺 destination-exists 冲突 fixture
  却声称「一个 fixture 覆盖冲突/受保护两个子类」；两处均已修，详见验证标准「负向 fixture 不静默
  通过」条目的修正记录。真实 repo
  replay 选用 `tartley/colorama`（`841634e`，新找、未测过，命中 `Makefile` 检测分支，与 Agent-R1
  「完全未检测到」不同），报告存 `lab/docs/audits/colorama-adoption-replay-report.md`。同步更新
  `.claude/commands/adopt-existing-repo.md`（步骤 4 汇报清单区分 integrity/blocker 与 smoke 两类
  exit-code 语义）+ 同 commit 重新生成 `.agents/skills/command-adopt-existing-repo/SKILL.md`
  （D2b same-commit rule）、`README.md`、`scripts/README.md`（smoke 合同 exit-code/warning 解耦说明）、
  `lab/docs/audits/README.md`（登记新 replay 报告）、`memory/current-status.md` /
  `memory/session-tree.md`（issue #12 part C 专属小节）。`validate-governance.py --strict`（本机需
  `uv run --with pyyaml` 绕过预置环境缺 PyYAML 的问题，已用 `git stash` 核对该 warning 与本轮改动
  无关）、`check-agent-harness.py --strict`、`check-anatomy-drift.py`、`sync-codex-adapters.py
  --check`、`check-same-commit.py --staged`、`git diff --check`、
  `lab/evals/adoption/run-adoption-smoke.py`（七场景，2026-07-13 两轮复审修正后重跑）、
  `lab/evals/bootstrap/run-bootstrap-smoke.py`（回归）全绿。B（语义归类）与 D2/D2c 未在本分支涉及。未 push、未开 PR、未 merge——按边界交由上层/
  human 决定后续 gate。人类最终批准仍待定。
- 2026-07-13 #12c 二轮 fresh Codex 终审收敛：HEAD `35c6196` 把 plan schema 升为 v2，旧 v1
  缺 `test_command_source` 时 fail-closed 并要求重跑 discover；新增 timeout/`unknown` 与 legacy-state
  regression，修正 Colorama proof 的真实/合成覆盖表述。独立 reviewer verdict 为 `APPROVE`；七场景
  adoption smoke、bootstrap 回归、adapter/harness/anatomy/strict governance 全绿，随后获授权合入本地
  `main`。未 push、未开 PR、未改远端。
- 2026-07-13 B fresh review BLOCKER 修复（Codex executor，`feat/12b-semantic-classification`）：canonical
  adoption state 的三个叶文件纳入 lstat/redirect 决策；确定性 `/tmp/template-adoption-state-<digest>`
  fallback 在使用前检查绝对路径全段、fallback 根与三个状态叶，任一 symlink 命中即 fail-closed，避免预置
  symlink 写穿。adoption smoke 从 15 扩到 19 组，新增 canonical leaf、fallback root、`TMPDIR` 中间段、
  fallback leaf 四组对抗回归，同时保留原有正常 fallback 场景。B1-B6 已实现并勾选完成；未涉及独立 C 分支。
- 2026-07-13 B fresh review MAJOR 修复（Codex executor，`feat/12b-semantic-classification`）：`normalize`
  改为先完整预检、后统一搬移；当前全部 root 必须被 discover classification 或显式
  `scaffold_control_items` 声明覆盖（后者仍须当前重算为安全 `template_control_item`），planned entry 的
  kind/category/blocker/target_path 全部按当前树重算。保护扫描先于任何类别分支，伪造
  `src -> template_control_item, blocker=false` 不能隐藏
  `src/checkpoints/model.bin`；默认模式只要有 blocker 即 `moved=0`。adoption smoke 从 19 扩到 21 组，新增
  discover 后新建 root `checkpoints/model.bin` 与伪造 control-item 两组对抗回归，两组均验证 non-zero、可读
  blocker、无搬移、无 repo 外写，原 19 组保持通过。
- 2026-07-13 B 最终 fresh Codex review 对 `f33ff9c` 给出 `APPROVE`。本地集成以 B 的 21 场景为
  基础，补回 C 的 clean pass 断言与 protected/conflict/fail/skipped/timeout/legacy 六个专项场景，
  合并后 adoption smoke 共 27 场景；合入范围仅本地 `main`，未授权也未执行远端 push/PR/release。
