# 实验运行/监控/告警/恢复控制面 交互式计划

> Claude 写初稿 → human 在文件里批注 → Claude 读 diff、收敛计划 → 每次采纳的修订做一个小 commit。
> 实现只在 scope / forbidden paths / verification 清楚后开始。

## 当前目标

把现有「experiment card + ledger + human launch gate + 只读 monitor + run summary + artifact promotion」流程，从「有文档说明的手工纪律」升级为一个**可检查、可监控、可恢复，且 launch/kill/restart 仍严格受 human gate 约束**的实验生命周期控制面：

1. 给 experiment card / ledger / run summary 定义结构化状态机（`planned → approved → running → done|failed|superseded`）与必填引用字段，非法状态转换与缺字段能被脚本拦截，而不只是靠人读文档自觉遵守。
2. 定义 launch registry / adapter contract：一层抽象把「本地 fake job」与「可选的 Slurm / RunAI 等后端」统一成同一套 launch/status/kill/restart 描述，adapter 缺失时优雅 fallback，不引入硬依赖；**adapter 本身不代替 human 按下启动键**。scheduler adapter 的具体做法先经任务 C3a 调研 `Zhangyanbo/hpc-skills` 后再定（直接安装 vs 参考自研）。
3. 建一个 bounded（有界、不无限追加、不常驻失控）watcher，检查日志尾部、metric、checkpoint 新鲜度、资源、config drift、failure signal，输出结构化 alert。
4. 定义 stale run 判定与 resume/recovery 提案格式：watcher 生成「建议 + 待批准的确切命令」；human 在 `.agent/human-gates.md` 流程下对某条具体提案给出明确批准后，`experiment-orchestrator` 可半自动执行该条已批准的 resume/recovery 动作（本 issue 范围内仅限 fake/local job，不触达真实 GPU/Slurm/RunAI）——agent 不自主判断"是否要恢复"，只执行 human 已圈定的那一条（2026-07-12 human 拍板，见「未解决问题」4）。
5. 把状态机与 `memory/current-status.md`、`lab/artifacts/*-index.yaml`、evidence promotion 打通，使「run 完成 → summary → artifact → ledger」闭环可自动核对。

> **双 runtime 对等要求（本轮二审补充）**：这个控制面会被 Claude Code 和 Codex 两侧 agent 都用来发起/监控实验。issue 里点名的 `experiment-orchestrator` 是 Claude 专属 subagent，但 Codex 侧通过 `.codex/agents/*.toml`（由 `scripts/sync-codex-adapters.py` 从 `.claude/agents/*.md` 生成）拿到等价角色。因此控制面的**触发路径必须是 runtime-neutral 的**——以 CLI 脚本 + repo 内文件（YAML 状态）+ validator 为主干，而不是绑死在 Claude 专属的 hook 事件、slash command 或 statusline 上。任何只有 Claude 侧能走通、Codex 侧走不通的机制，都要么补上 Codex 对等路径，要么标成 open question，不能默认。

## 非目标

- **不实现任何具体 ML / 量化 / 科学训练器逻辑**：本 issue 只做控制面（schema、校验、adapter contract、watcher、alert/resume 流程），不碰 `lab/code/` 下具体训练脚本或领域 pipeline。
- **不真实启动 / kill / restart 长训练或远端作业**，包括在测试与 smoke 环节。所有验证只能用 fake/local job（例如 `sleep` + 写 status 文件模拟的进程），不得触达真实 GPU/Slurm/RunAI 队列。**（对齐本轮决策 4）**human 批准后 `experiment-orchestrator` 可半自动执行的 resume/recovery，同样只限于此 fake/local 范围，不构成对本条非目标的例外。
- **不给 scheduler adapter 引入硬依赖**：不安装 Slurm/RunAI 官方 SDK 或增加新的 Python 依赖；adapter 通过检测可执行文件是否存在 + 生成命令文本草案的方式工作，缺失时清晰 fallback 到「仅本地 / 仅提案」模式。
- **不做告警通知渠道集成**（Slack/邮件/webhook 等）：alert 先落地为 repo 内文件（人可读的 alert/state 记录），不接外部通知系统。
- **不新建 Web UI / dashboard**：控制面先是 CLI + 文件 + validator 脚本的形态，与现有 `scripts/validate-governance.py` 风格一致。
- **不改变现有证据门槛**：`.agent/artifact-policy.md` 的 evidence 分层与 promote 门槛不变，本 issue 只打通「状态与索引是否闭环」的检查，不放宽或收紧证据标准。
- **不放宽 `.agent/action-boundary.md` 的硬边界**：控制面的设计本身必须体现"启动/kill/restart 走 human gate"，不能在实现或测试里绕开。

## Branch / worktree

- Branch: `feat/16-experiment-control-plane`
- Worktree: `.claude/worktrees/16-experiment-control-plane`

## Linked issue / PR

- Issue: `#16` — feat: 完整化实验运行、监控、告警与恢复控制面

## Allowed paths

- `lab/research/experiment-ledger.yaml`（schema 演进：新增/细化状态字段，非改 data bytes）
- `.agent/templates/experiment-card.md`、`.agent/templates/run-summary.md`
- `.agent/human-gates.md`（如状态机新增门禁点，需要补充说明）
- `lab/infra/launch/`（adapter 草案脚本/文档，仍不代替人执行启动）
- `.claude/agents/experiment-orchestrator.md`、`.claude/agents/experiment-monitor.md`（**已决策（2026-07-12 human 拍板）：扩展这两个既有 agent 的职责边界，不新增 agent 文件**——bounded watcher/alert 归入 `experiment-monitor`（保持严格只读、无 Edit/Write）；resume/recovery 提案与「human 批准后半自动执行」归入 `experiment-orchestrator`（已有 Write/Edit/Bash 与「未经批准不得 launch/kill/restart，只能产出待批准提案」边界，本轮只是把「批准后可执行」的既有模式显式扩展到 resume/recovery 场景））
- `.claude/skills/experiment-workflow/SKILL.md`
- **`.codex/agents/*.toml`、`.agents/skills/experiment-workflow/SKILL.md`（Codex 侧生成产物）**：这些不是手改目标，而是**改完上面 canonical 后必须跑 `python scripts/sync-codex-adapters.py` 重新生成、并与 canonical 同 commit 提交**。`check-agent-harness.py` 会跑 `sync-codex-adapters.py --check`，不同步会直接 FAIL。**已决策**：本 issue 不新增 agent 文件（扩展既有两个 agent，见上一条），因此预期不会新生成 `.codex/agents/<new-name>.toml`；若 `experiment-orchestrator.md`/`experiment-monitor.md` 的 `tools`/`description` 有调整，仍需 sync 后确认对应的 `.codex/agents/experiment-orchestrator.toml`、`.codex/agents/experiment-monitor.toml` 同步更新并同 commit 提交。
- `scripts/validate-experiment-state.py`（**已决策（2026-07-12 human 拍板）**：新建独立脚本，不整合进 `validate-governance.py` 现有函数体，仿 `scripts/check-same-commit.py` 先例，由 `validate-governance.py` 通过 `run_subcheck` 拉起——与 #17/#18 已定的独立脚本政策一致）
- **`DESIGN.md`（§10 能力清单表）**：若新增 agent / hook / skill / command，`check-agent-harness.py` 的 `check_design_inventory` 会按数量比对，需同步更新计数，否则 WARN。
- `lab/research/ANATOMY.md`、`lab/infra/ANATOMY.md`、`scripts/ANATOMY.md`（新增 `validate-experiment-state.py` 需同 commit 登记进 `related_files`）等相关结构文档（结构改动需同 commit 更新）
- 测试目录（若仓库已有 `tests/` 布局，新增针对 fake/local job smoke 的测试）
- `plans/20260712-experiment-control-plane.zh.md`（本文件）

## Forbidden paths

- `lab/data/**`、`lab/runs/**`、`lab/models/**` 权重/字节、`checkpoints/**`、`wandb/**`（bytes 层，只能碰 index/summary）
- `lab/infra/private/**`（永不读取/写入/提交）
- `.env`
- 真实调用 `sbatch`、`runai`、`kill`、进程 restart 等命令——测试与 smoke 只能用 fake/local 模拟进程
- `deliverables/`、`human/decisions/`（除非走既有 gate 流程，本 issue 不涉及）
- `.claude/settings.json`、`.codex/config.toml`、`.codex/rules/default.rules` 的权限地板：默认禁止做与本 issue 无关的权限面调整。**例外（human 已于 2026-07-12 明确授权）**：本 issue 范围内可以为 launch registry 新增的命令类型追加权限规则——Claude 侧 `.claude/settings.json` 的 `ask`/`deny`、Codex 侧 `.codex/rules/default.rules` 的 execpolicy `prompt`/`forbidden`——不需要在实现阶段再单独申请一次批准；但**仅限**新增 launch 命令识别相关的最小必要规则，不得借机做无关的权限面调整，且改动仍要按 repo 正常流程走 PR review（这不代表跳过审查）。**注意：这三处不在 `sync-codex-adapters.py` 的覆盖范围内**——sync 只生成 `.codex/agents/*.toml` 与 `.agents/skills/**`，权限规则是**手工双写**：Claude 侧 `.claude/settings.json`（`ask`/`deny`）与 Codex 侧 `.codex/rules/default.rules`（execpolicy `prompt`/`forbidden`）语法不同、无自动同步。现状 execpolicy 已有 `kill|sbatch|runai → prompt`；本 issue 新增 launch 命令模式的门禁必须两侧对齐同 commit 提交，否则会出现「一侧拦、另一侧放行」的不对等漏洞。

## 任务树

- [ ] Parent: 实验控制面 v1（状态机 + 字段校验 + launch adapter + fake job smoke + bounded watcher + alert/resume）
  - [ ] A. 状态机 schema 设计
    - [ ] A1. 定义状态枚举与合法转换表：`planned → approved → running → done | failed`，以及 `done|failed → superseded`；写清楚哪些转换非法（如 `planned → running` 跳过审批）
    - [ ] A2. 更新 `experiment-ledger.yaml`、`experiment-card.md`、`run-summary.md`：新增 `status`、`approved_by`/`approved_at`（human 批准记录）等字段；保持对现有 `run-000` 占位条目的兼容或给出迁移说明
    - [ ] A2a.（新增，2026-07-12 human 拍板）把 `lab/research/experiment-ledger.yaml` 里的 `run-000` 占位条目**同步升级为新 schema 的真实可参考样例**：填齐 `status`、`approved_by`/`approved_at` 及 A2 定义的其余新字段，使其成为「新 schema 长什么样」的活样例，而不是留一个仍是旧结构的占位符；成本低、避免实现完后没人知道字段怎么填。
  - [ ] B. 必填字段校验
    - [ ] B1. 定义「进入 `approved` 前必须齐备」的字段集合：commit、config、data_split、budget（expected_runtime 或算力预算）、success_metric
    - [ ] B2. 写校验脚本：**新建独立脚本 `scripts/validate-experiment-state.py`**（2026-07-12 human 拍板：按"独立脚本"政策执行，不整合进 `validate-governance.py` 现有函数体，仿 `scripts/check-same-commit.py` 先例），由 `validate-governance.py` 通过 `run_subcheck` 拉起（与任务 H 已定的 sync/harness 检查同一模式）；缺字段 / 非法转换时给出明确报错，不静默通过
  - [ ] C. launch registry / adapter contract
    - [ ] C1. 定义 adapter 抽象接口（launch/status/kill/restart 的命令描述 schema），明确这是「生成命令草案」而非「执行」。**接口必须 runtime-neutral**：以 CLI 脚本 + YAML registry 文件为载体，Claude 与 Codex 两侧调用同一入口，不依赖任一 runtime 专属的 hook/subagent 触发机制。
    - [ ] C1b. launch 命令识别单一真源：让 registry（而非散落的字符串匹配）成为「哪条命令是 launch」的权威来源，供**两侧共享的** `pre_tool_guard.py` hook 消费（config.toml 与 settings.json 都指向同一份 `.claude/hooks/pre_tool_guard.py`）。这正面回应 issue「任意领域训练命令也难以仅靠字符串 hook 识别」——不要在 hook 里写死 Claude 专属的识别逻辑。
    - [ ] C2. local/fake adapter：用于 smoke 测试，模拟一个本地"job"（如后台睡眠脚本 + 写 pid/status 文件），不消耗真实算力
    - [ ] C3a.（前置任务，2026-07-12 human 拍板新增）调研外部项目 `Zhangyanbo/hpc-skills`（https://github.com/Zhangyanbo/hpc-skills），评估是**直接安装/引入其作为 scheduler adapter 的基础**，还是**只参考其设计自行实现** Slurm/RunAI adapter；产出结论与理由（许可证兼容性、是否符合"不引入硬依赖"非目标、与本项目 skill/agent 目录结构的契合度），作为 C3 的输入。本任务只调研判断，本轮 plan 阶段不臆测该 repo 具体内容、不展开实现。
    - [ ] C3. 可选 Slurm/RunAI adapter：基于 C3a 的调研结论（直接安装该 skill 或参考其设计自研），仅在检测到对应 CLI 存在时生成命令草案；不存在时清晰 fallback（不报错崩溃，只降级提示"未检测到 X，回退到 local-only"）
  - [ ] D. fake/local job 全流程 smoke
    - [ ] D1. 走通：card 齐备字段 → 校验通过 → human 模拟批准（approved）→ 生成 local adapter launch 命令草案 → 人工/脚本确认后启动 fake job → 状态转 running
    - [ ] D2. smoke 覆盖异常路径：watcher 检出 fake job 异常 → alert → human 批准恢复 → resume 后状态回到 running/done
    - [ ] D3. smoke 覆盖停止路径：human 批准 kill fake job → 状态转 failed/superseded，ledger 记录终止原因
  - [ ] E. bounded watcher
    - [ ] E1. 检查项：日志尾部（有界行数）、最新 metric、checkpoint 新鲜度、资源/进程存活、config drift、failure signal（复用 experiment-card 里的 `failure_signals` 列表）
    - [ ] E2. bounded 保证：日志只 tail 固定行数；**已决策（2026-07-12 human 拍板）**watcher 是**一次性快照检查**——每次调用检查一次、检查完退出，不常驻、不做后台轮询/循环（排除"带超时的有限循环"选项）；输出摘要不贴长日志
    - [ ] E3. **已决策（2026-07-12 human 拍板）**：watcher 是扩展现有 `experiment-monitor` agent 的职责（新增日志/metric/checkpoint/资源/config drift/failure signal 的一次性快照检查能力），不拆出新的 `experiment-watcher` agent；继续保持只读、无 Edit/Write、无 kill/restart 权限不变。**Codex 对等性（本轮实核，结论保留）**：`sync-codex-adapters.py:47-51` 按 tools 是否含 Edit/Write/NotebookEdit 生成 `sandbox_mode`；纯 `Read/Bash/Grep` 的现有 monitor 已生成 `sandbox_mode = "read-only"`（`.codex/agents/experiment-monitor.toml:4`）。但 `read-only` 主要约束文件系统写入，不能据此宣称它必然阻止进程信号；共享 `pre_tool_guard.py` 当前也不拦 `kill/sbatch/runai`。Codex 侧真正可实测的命令门禁是 execpolicy：三者均命中 `prompt`。因此 watcher 的不干预边界应由「read-only 限制写文件 + execpolicy 对已登记副作用命令 prompt/forbidden + agent 行为契约」共同承担，不能把它描述成三层都独立拦 kill/restart；新增 wrapper/launch 入口还必须显式登记，避免绕过前缀规则。
  - [ ] H. Codex 适配层同步与对等验证（每次动 canonical agent/skill 后必做）
    - [ ] H1. 改完 `.claude/agents/*.md`、`.claude/skills/experiment-workflow/SKILL.md`、新增 agent 后，跑 `python scripts/sync-codex-adapters.py`，把生成的 `.codex/agents/*.toml`、`.agents/skills/**` 与 canonical 同 commit 提交。
    - [ ] H2. 跑 `python scripts/check-agent-harness.py` 确认 adapter 同步（内含 `--check`）+ 受保护路径权限地板 + hook 脚本存在；若新增 agent/hook/skill，同步更新 `DESIGN.md` §10 能力清单计数。
    - [ ] H3. 补齐 launch 门禁权限规则（**human 已于 2026-07-12 明确授权，本项在本 issue 范围内直接做，无需实现阶段再单独申请批准**）：为最终选定的 fake/local launch 命令前缀，在 `.claude/settings.json`（`ask`/`deny`）与 `.codex/rules/default.rules`（execpolicy `prompt`/`forbidden`）**两侧手工对齐**，与 launch registry / adapter contract（任务 C）同 commit 提交；仅新增 launch 命令识别相关的最小必要规则，不做无关权限面调整；改动仍按 repo 正常 PR review 流程走，不代表跳过审查。
  - [ ] F. alert → stale run → resume/recovery（human gate）
    - [ ] F1. 定义 stale run 判定规则（如：超过预期 runtime 若干倍、或心跳/metric 长时间无更新）
    - [ ] F2. **已决策（2026-07-12 human 拍板）**：alert 记录并入 `lab/research/experiment-ledger.yaml` 对应实验条目的新增字段（如 `alerts: [...]`，含时间戳、异常类型、证据引用），不新开独立文件（不建 `experiment-alerts.yaml`，不用 `human/inbox` 风格条目）；不接外部通知系统。
    - [ ] F3. 定义 resume/recovery 提案格式：动作类型（重跑/从 checkpoint 续跑/放弃标记 failed）+ 确切命令 + 影响半径 + 期望批准范围。**已决策（2026-07-12 human 拍板）**：human 对某条具体提案给出明确批准后，`experiment-orchestrator` 可半自动执行该条已批准的动作（本 issue 范围内仅限 fake/local job，不触达真实 GPU/Slurm/RunAI）；这不是让 agent 自主判断"要不要恢复"，而是执行 human 已圈定的那一条具体动作。批准记录格式对齐 `.agent/human-gates.md` 现有约定：在 ledger `alerts`/相应字段或 run summary 中记录 `approved_by`、`approved_at`、`approved_action`（具体到提案 ID 或确切命令），使批准范围可审计、不可被误用为"永久授权"。与 `.agent/action-boundary.md` 的对齐：该硬边界禁止在没有明确要求时启动/kill/restart 长训练或远端作业；本处"半自动执行"正是硬边界允许的"明确要求"情形——一次性、针对具体提案的 human 批准，不构成对边界的放宽，也不授予 agent 自主启停真实作业的权限。
  - [ ] G. 与 memory / artifact index / evidence 打通
    - [ ] G1. run 完成（`done`）后的闭环校验：ledger status=done ⇒ run_summary 文件存在 ⇒ 对应 artifact index（`lab/artifacts/*-index.yaml`）有条目 ⇒ 缺任一环节时报告缺口而非静默
    - [ ] G2. 明确控制面状态与 `memory/current-status.md` 的联动方式（如：activate run 列表、stale run 提醒是否写入 current-status）

## Human 批注区

<!-- human 在此行以下直接写批注/修改，Claude 读 diff 收敛计划 -->

## 当前决策

- 状态机固定为 issue 给出的五态：`planned / approved / running / done|failed / superseded`，新增 `approved` 作为独立于 `planned` 的显式 human 批准态（对齐验收标准第一条）。
- launch/kill/restart 在任何实现路径下都保持 human gate，不因为「控制面自动化」而放宽 `.agent/action-boundary.md`。
- scheduler adapter（Slurm/RunAI）按「可选、无硬依赖、检测不到就 fallback」设计，避免给 repo 引入环境耦合。
- 领域训练命令识别（issue 提到"任意领域训练命令也难以仅靠字符串 hook 识别"）在本轮不解决具体识别算法，只保证 adapter contract 层面能描述"这是一条 launch 命令"，具体领域 launch 命令注册机制留给下游（对齐"边界"一节）。
- **控制面走 runtime-neutral 主干（二审新增）**：状态机、校验、adapter contract、watcher、alert/resume 都以 CLI 脚本 + repo 内 YAML 文件 + validator 实现，Claude 与 Codex 调用同一入口。Claude 专属的 subagent/skill/hook 只是这套 CLI/文件的**调用者与包装**，不是唯一入口——保证 Codex 侧经 `.codex/agents/*.toml` 拿到的等价角色能走同一条路。
- **Codex adapter 同步是硬步骤（二审新增）**：任何 canonical agent/skill 改动都要跑 `sync-codex-adapters.py` 并同 commit 提交生成物；`check-agent-harness.py` 会 gate 这一点。权限规则（settings.json / execpolicy）不在 sync 范围，需两侧手工对齐。
- **新增 launch 入口必须先补双侧显式门禁（Codex 真实二审确认）**：本轮 `codex execpolicy check` 证明 `kill 123`、`sbatch train.sh`、`runai submit ...` 都返回 `prompt`；但示例 `python scripts/launch-experiment.py ...` 与 `bash lab/infra/launch/run-local.sh ...` 均为 `matchedRules: []`。共享 `pre_tool_guard.py` 也没有 launch/kill 检查。因此不能用「控制面只生成草案」替代机器门禁：一旦选定可执行入口，先把精确命令前缀加入 `.claude/settings.json` 的 `ask` 与 `.codex/rules/default.rules` 的 `prompt`，再允许 fake smoke。
- **recovery 提案生成与批准后执行合并进 `experiment-orchestrator`（2026-07-12 human 拍板：不拆新 agent，取代此前"recovery-advisor 拆分且保持只读"的二审设想）**：resume/recovery 提案的生成，以及 human 批准后的半自动执行，都在既有 `experiment-orchestrator`（已是 workspace-write，已有"未经批准不得 launch/kill/restart，只能产出待批准提案"的边界）内完成，不再需要一个独立、权限更低的 recovery-advisor 子角色来隔离风险面；`experiment-monitor` 仍严格只读，只负责 watcher/alert 侦测，不生成也不执行 resume 提案——二者按"侦测 vs 提案+执行"清楚切分职责。
- **launch 权限规则改动已获 human 授权（2026-07-12 human 亲自拍板）**：针对上面「新增 launch 入口必须先补双侧显式门禁」的需求——原先这是一条待批的 open item（Forbidden paths 里标注为「需在计划里单独列出并等待 human 批准」）——human 现已明确同意：本 issue 范围内可以新增/调整 launch 相关的权限规则（Claude 侧 `.claude/settings.json` 的 `ask` 门禁 + Codex 侧 `.codex/rules/default.rules` 的 execpolicy `prompt` 规则），不需要在实现阶段再单独申请一次批准。限定：改动范围仅限 launch 命令识别相关的最小必要规则，不做无关的权限面调整；实际改权限文件时仍按 repo 正常流程走 PR review，这不代表可以绕开审查。已同步更新 Forbidden paths 与任务 H3。
- **本轮（2026-07-12）human 逐条拍板收敛剩余 5 个 open question（选择题形式）**：
  1. scheduler adapter：先调研 `Zhangyanbo/hpc-skills`（https://github.com/Zhangyanbo/hpc-skills），据其结论决定"直接安装/引入"还是"参考自研"（新增前置任务 C3a）。
  2. watcher 形态：**一次性快照检查**，不做带轮询的后台常驻进程（任务 E2/E3）。
  3. alert 存储：**并入 `lab/research/experiment-ledger.yaml` 字段**，不新开独立文件（任务 F2）。
  4. resume/recovery 边界：**human 批准后 `experiment-orchestrator` 可半自动执行该条已批准的具体动作**，不止步于生成命令草案；仍与 `.agent/action-boundary.md` 硬边界对齐——半自动执行仅限已获明确批准的单条动作，agent 不自主判断是否恢复（任务 F3）。
  5. agent 组织：**扩展现有 `experiment-orchestrator`/`experiment-monitor`**，不拆新 agent（Allowed paths、任务 E3）。
- **本轮（2026-07-12）human 续拍板收敛剩余 2 个 open question**：
  6. `run-000` 占位条目：**同步升级为新 schema 的真实样例**（不只更新模板/文档），顺带给新 schema 留一个可参考的活样例，成本低、避免实现完后没人知道新字段怎么填（新增任务 A2a）。
  7. 校验脚本落点：**新建独立脚本 `scripts/validate-experiment-state.py`**，不整合进 `validate-governance.py` 现有函数体，仿 `scripts/check-same-commit.py` 先例，由 `validate-governance.py` 通过 `run_subcheck` 拉起——对齐 #17/#18 已定的独立脚本政策（任务 B2、Allowed paths）。

## 未解决问题

1. ~~scheduler adapter 范围~~ **已决策（2026-07-12 human 拍板）**：不预先争论"要不要做两个具体 adapter 草案"，而是先调研外部项目 `Zhangyanbo/hpc-skills`（https://github.com/Zhangyanbo/hpc-skills），由调研结论决定"直接安装/引入其作为 scheduler adapter 基础"还是"只参考其设计自研"；已新增前置任务 C3a，C3 的具体范围依赖该调研结果，不在本轮 plan 阶段展开。
2. ~~watcher 运行形态~~ **已决策（2026-07-12 human 拍板）**：watcher 是**一次性快照检查**（人/agent 手动触发一次，检查完退出），不是带轮询的后台常驻进程；issue 里的"后台告警"若需要 cron/CI 之类的重复调用机制，属于后续 issue 范围，本 issue 只交付「可被重复调用的一次性检查」这个原语。任务 E2/E3 已按此改写。
3. ~~alert 存储位置与格式~~ **已决策（2026-07-12 human 拍板）**：并入 `lab/research/experiment-ledger.yaml` 对应实验条目的字段（不新开独立文件）。任务 F2 已按此改写；具体字段 schema（如 `alerts: [{type, ts, evidence}]`）留给实现阶段细化。
4. ~~resume/recovery 动作集合~~ **已决策（2026-07-12 human 拍板）**：不止步于"生成命令草案"——human 对某条具体提案明确批准后，`experiment-orchestrator` 可半自动执行该条已批准动作（仅限 fake/local 范围）；批准记录为**一次性、针对具体提案**（含 `approved_by`/`approved_at`/`approved_action`），不是本 session 级或持久级的泛授权，与 `.agent/human-gates.md`「明确批准」的既有精神一致，也不违反 `.agent/action-boundary.md` 的硬边界。任务 F3 已按此改写。
5. ~~agent 组织方式~~ **已决策（2026-07-12 human 拍板）**：扩展现有 `experiment-orchestrator`/`experiment-monitor`，不拆新 agent。watcher/alert 侦测归入只读的 `experiment-monitor`；resume 提案生成 + 批准后半自动执行归入已有 workspace-write 边界的 `experiment-orchestrator`。Allowed paths、任务 E3、当前决策已按此改写。
6. ~~现有 `run-000` 占位条目~~ **已决策（2026-07-12 human 拍板）**：同步把 `lab/research/experiment-ledger.yaml` 里的 `run-000` 占位条目升级为新 schema 的真实样例（不是只更新模板/文档、留待第一个真实实验时再落地）。理由：成本低，且给新 schema 留一个可参考的活样例，避免实现完后没人知道新字段该怎么填。新增任务 A2a。
7. ~~校验脚本落点~~ **已决策（2026-07-12 human 拍板）**：新建独立脚本 `scripts/validate-experiment-state.py`，不整合进 `scripts/validate-governance.py` 现有函数体，仿 `scripts/check-same-commit.py` 先例，由 `validate-governance.py` 通过 `run_subcheck` 拉起。理由：human 已确认这类问题统一按"独立脚本"政策执行，与 #17/#18 已定模式一致；同时要求同 commit 在 `scripts/ANATOMY.md` 登记该脚本，避免遗漏。任务 B2、Allowed paths 已按此改写。
8. **双 runtime 的完整业务 smoke 仍待实现后验证**：本轮已经在真实 Codex session 里验证现有 policy，而不是继续保留“缺 Codex 一手证据”的泛问：`kill/sbatch/runai` 均命中 `prompt`，两个假设的 fake launch 入口均未命中规则。由于控制面脚本、registry 与 fake adapter 尚未实现，现在无法诚实地跑「审批→监控→告警→停止→恢复」端到端 smoke。实现后应对同一 CLI/文件流程跑一次业务 smoke，并分别对 Claude/Codex 做权限层定向测试；不需要仅为 runtime 名称重复两套完全相同的业务测试。
9. **read-only sandbox 的进程干预边界仍需实现期定向验证**：本轮能确认生成器与产物把 monitor 配成 `read-only`，也能确认当前 Codex App 根 session 是 `workspace-write`，不能冒充 monitor 子 agent 的端到端运行证据。更重要的是，文件系统 read-only 不等价于“不能发 signal”。实现期应启动真实 `experiment-monitor` custom agent，分别验证工作区写入失败、`kill` 触发门禁且未执行；测试只针对受控 fake process，不触达真实训练。当前结论只写到已证明的配置生成与 execpolicy 判定，不硬凑 sandbox 的 syscall 结论。

## 验证标准

- 状态转换：`planned→approved→running→done/failed/superseded` 的合法转换可通过校验脚本验证；非法转换（如跳过 approved、done 后又转回 running）被脚本明确拒绝并给出可读报错。
- 必填字段：缺 commit / config / data split / budget / success metric 中任一项的实验卡片/ledger 条目不能进入 `approved` 状态，校验脚本报出缺失字段清单。
- 全流程 smoke（仅 fake/local job）：能走通「card 齐备 → 校验通过 → 模拟 human 批准 → local adapter 生成并执行 fake 启动 → watcher 对 fake job 做一次快照检查、检出一次人为制造的异常 → alert 写入 `experiment-ledger.yaml` 对应字段 → 模拟 human 对该条 alert 的 resume 提案给出明确批准 → `experiment-orchestrator` 半自动执行该条已批准动作 → 状态收敛到 done/failed」，全程不触达真实 GPU/远端队列。
- watcher bounded 性质：可展示/断言其读取日志有行数上限；每次调用是**一次性快照检查**（检查完即退出，不常驻、不做后台轮询）；不产生无限增长的输出；也不在未经批准时执行 kill/restart（可通过代码审查 + 测试用例证明其只读特性，与 `experiment-monitor.md` 现有边界一致）。
- resume/recovery 半自动执行审计：给定一条已批准的 resume 提案（含 `approved_by`/`approved_at`/`approved_action`），`experiment-orchestrator` 实际执行的动作应与提案完全匹配（同一 fake job、同一命令）；批准字段缺失或与执行动作不匹配时，应拒绝执行并报错，而非静默跳过检查。
- 闭环检查：给定一个状态为 `done` 的 fake 实验，能检测出 run summary / artifact index / ledger 是否三方一致，缺失任一环节时给出明确报告而非静默通过。
- scheduler adapter fallback：在未安装/检测不到 Slurm、RunAI 等 CLI 的环境下（本仓库当前环境即是），adapter 层能优雅降级为 local-only 模式，不报错、不阻断其余流程、不引入新的 Python 依赖。
- 运行 `python scripts/validate-governance.py`（以及新增的针对性校验脚本/测试）全部通过，并在报告中给出确切命令与输出。
- **（二审新增）Codex 适配层验证**：跑 `python scripts/sync-codex-adapters.py`（重生成）+ `python scripts/check-agent-harness.py`（内含 `--check`），确认 `.codex/agents/*.toml`、`.agents/skills/**` 与 canonical `.claude/` 同步、无 stale/unexpected/missing adapter；新增 agent/hook/skill 时 `DESIGN.md` §10 计数无 WARN。
- **双 runtime 门禁对等（本轮改严）**：为最终确定的 fake/local launch、kill、restart 入口逐条做权限测试；Claude 侧应命中 `.claude/settings.json` 的 `ask`，Codex 侧应由 `codex execpolicy check --pretty --rules .codex/rules/default.rules -- <command>` 明确返回 `prompt`/`forbidden`。`matchedRules: []` 视为验收失败。共享 `pre_tool_guard.py` 只作为红线地板，不得误报成已覆盖这些计算副作用命令。
- 结构性改动（ledger schema、agent 职责、脚本新增）同 commit 更新相关 `ANATOMY.md`。

## 下一步

- 未解决问题 1-7 已由 human 于 2026-07-12 逐条拍板收敛（scheduler adapter 调研路径、watcher 一次性快照形态、alert 并入 ledger 字段、resume 半自动执行边界、agent 组织不拆分、`run-000` 升级为新 schema 样例、校验脚本独立落点），对应任务树、Allowed paths、验证标准已同步改写。未解决问题 8、9 本质是「实现阶段才能验证的事项」（需要控制面脚本/registry/fake adapter 实际存在、需要真实拉起 custom agent 才能测），不是需要 human 现在拍板的分歧点，不算 blocking open question——留在文件里作为实现完成前必须补的验收动作。截至本轮，**本文件没有剩余需要 human 现在拍板的 open question**；若无进一步批注，可视为计划收敛，等待 human 明确批准后进入实现阶段。
- 收到批注后 Read diff + `git status`，收敛计划为 v2，若涉及范围变化同步更新 Allowed/Forbidden paths 与任务树。
- 计划收敛且 human 明确批准后，再进入实现阶段（不在本轮 plan 文档任务中开始写代码）。

## Plan revision log

- 2026-07-12 初稿（基于 issue #16 + `.agent/action-boundary.md`、`.claude/skills/experiment-workflow/SKILL.md`、`.claude/agents/experiment-orchestrator.md`、`.claude/agents/experiment-monitor.md`、`.agent/templates/{experiment-card,run-summary}.md`、`.agent/human-gates.md`、`.agent/artifact-policy.md`、`lab/research/experiment-ledger.yaml`、`lab/infra/launch/README.md`、`lab/infra/AGENTS.md` 现状梳理）
- 2026-07-12 二审修订（由 Claude Opus 4.8 代替额度耗尽的 Codex gpt-5.6-sol 做第二意见审查）。重点补 Codex 侧对等缺口：runtime-neutral 控制面主干、`sync-codex-adapters.py` 硬同步步骤（新增任务 H）、`check-agent-harness.py`/`DESIGN.md §10` 验证、权限地板两侧手工对齐、launch 命令识别以 registry 为单一真源供共享 hook 消费、只读 watcher 的 Codex `read-only` sandbox 语义；新增 open questions 8-10（双 runtime smoke 深度、launch 门禁新规则、recovery-advisor sandbox）。人类最终批准仍待定。
- 2026-07-12 Codex（gpt-5.6-sol, medium）真实二审：实测 `kill/sbatch/runai` 的 execpolicy 均为 `prompt`，而两个示例 fake launch 入口均未命中规则；据此把新增 launch 双侧显式门禁定为前置条件，纠正“read-only sandbox + hook + execpolicy 都能拦 kill”的过强表述，收敛 recovery-advisor 为只读提案角色，并把暂时无法完成的 custom-agent sandbox / 全业务 smoke 明确推迟到实现期受控 fake process 验证。人类最终批准仍待定。
- 2026-07-12 human 亲自拍板：授权本 issue 范围内新增 launch 相关权限规则（仍走正常 PR review）。
- 2026-07-12 human 亲自逐条拍板（选择题形式）：scheduler adapter 先调研 `Zhangyanbo/hpc-skills`（新增前置任务 C3a）、watcher 定为一次性快照检查（非常驻轮询）、alert 记录并入 `experiment-ledger.yaml` 字段（不新开文件）、resume/recovery 在 human 批准后 `experiment-orchestrator` 可半自动执行已批准的具体动作（与 `.agent/action-boundary.md` 对齐，非自主判断）、新能力扩展现有 `experiment-orchestrator`/`experiment-monitor`（不拆新 agent）。未解决问题 1-5 相应标记为已决策，任务树/Allowed paths/验证标准同步改写。
- 2026-07-12 human 续拍板剩余 2 条 open question：(1) `run-000` 占位条目同步升级为新 schema 真实样例，不只更新模板/文档（新增任务 A2a）；(2) 校验脚本落点按"独立脚本"政策执行，新建 `scripts/validate-experiment-state.py`（仿 `scripts/check-same-commit.py` 先例，由 `validate-governance.py` 通过 `run_subcheck` 拉起），不整合进 `validate-governance.py` 现有函数体，对齐 #17/#18 已定模式。未解决问题 6、7 已标记为已决策；任务 A2/A2a、B2、Allowed paths（含 `scripts/ANATOMY.md` 登记要求）同步改写。核实结果：未解决问题 8、9 本质是实现阶段才能验证的事项（依赖控制面脚本/registry/fake adapter 实际存在、依赖真实拉起 custom agent 才能测得 sandbox 行为），不构成需要 human 现在拍板的分歧点，不算 blocking open question；截至本次修订，本文件**没有**剩余需要 human 现在拍板的 open question。
