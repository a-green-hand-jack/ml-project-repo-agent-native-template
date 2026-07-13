# outcome-aware 路由 交互式计划

> Claude 写初稿 → human 在文件里批注 → Claude 读 diff、收敛计划 → 每次采纳的修订做一个小 commit。
> 实现只在 scope / forbidden paths / verification 清楚后开始。

## 当前目标

在现有 `coding-agent-quota`（额度快照 + provider preference）与 `subagent-routing`（launch packet 生成）之上，
增量建立一层 **outcome-aware** 路由：让 route decision 除了 quota 之外，还能引用历史任务结果（成功率、延迟、
返工、失败原因），在相同预算下给出可解释、可离线复现的候选路线比较，并在数据缺失/过期时保守回退到当前
quota-aware 行为。这是 issue #15 的第一版落地：可解释启发式 + 离线校准，聚焦 **quota + outcome 两维**（本版
不引入 $/token 价格表，见「未解决问题 6：已决策」），不是在线学习调度器。

**落地方式（human 2026-07-12 拍板，已决策）**：这层新能力**扩展现有 `.claude/skills/coding-agent-quota/`**，
不新开独立 skill。此前初稿与三轮审查（Claude Opus / Codex 二审 / Codex 三审）都倾向新开
`.claude/skills/outcome-aware-routing/` 独立目录，理由是「关注点分离」；human 最终推翻该判断，选择合并，
理由：quota（还剩多少）与 outcome（值不值得）两者语义相近，都是路由决策支持，合并能减少概念数量，即使因此
让 `coding-agent-quota` 的职责变重也可接受。详见「未解决问题 1：已决策」。

**双 runtime 定位（issue #15「注意」条款）**：这层路由不只服务 Claude Code 派 subagent，也要能服务
Codex 侧编排（`codex exec`、`codex-rescue`、`ccg` 这类跨 provider 场景）。因此 schema 从第一版起就必须
provider-neutral，把 Claude 生态（Opus/Sonnet/Haiku tier + Claude effort）与 Codex 生态（`gpt-5.5`、
`gpt-5.6-luna/terra/sol` 等 + Codex `model_reasoning_effort`）纳入**同一张**决策/结果表，而不是只按
Opus/Sonnet/Haiku tier 建模、把 Codex 当附注。证据：现有 `read_agent_quota.py` 的 `model_for()` 已经为两
个生态各自维护了 model 推荐与跨生态 effort 阶梯（`{0:none,1:low,2:medium,3:high,4:xhigh}`）。新 ledger 应复用
provider/model 的已有命名约定，但不能把当前启发式函数直接当成历史记录的永久 schema：`model_for()` 会随路由
policy 演化，且其中 `xhigh` 是跨生态抽象值，不等同于所有 provider 的原生旋钮值。ledger 需要同时记录稳定的
`routing_tier`、provider 原生 `effort` 与生成该建议的 `policy_version`。

## 非目标

- 不实现在线强化学习 / 自适应 bandit 调度器；不在运行中根据实时反馈静默切换 policy（issue #15「边界」条款）。
- 不改变 `coding-agent-quota` 现有 `route_recommendation` 字段的既有语义或默认输出（`--format table/json` 向后兼容），
  只做加法式扩展。
- 不读取任何 credential / token / API key 文件；不新增需要联网认证的价格抓取（本版**不引入价格/速度参考表**，
  只做本地可复现的 quota + outcome 两维证据，见「未解决问题 6：已决策」）。
- 不在本轮触碰 `lab/data/`、`lab/runs/`、`lab/models/` bytes、checkpoints、wandb、`lab/infra/private/`。
- 不做「任务质量」的主观人工评分体系设计（第一版用可自动获取的代理信号，如 verifier pass/fail、测试通过率、返工次数），
  更精细的质量度量留待后续迭代。
- 不在本轮修改 `.claude/settings.json` / hooks 的权限边界本身（若发现需要新增 deny 规则，走单独 issue）。

## Branch / worktree

- Branch: `feat/15-outcome-aware-routing`
- Worktree: `.claude/worktrees/15-outcome-aware-routing`

## Linked issue / PR

- Issue #15：建立 outcome-aware 的 agent / model / effort 路由。

## Allowed paths

- `.claude/skills/coding-agent-quota/**`（**已决策：outcome-aware 新能力的落地位置**，扩展现有 skill 而非新开
  独立 skill，见「未解决问题 1：已决策」）。具体新增/改动：
  - `SKILL.md`：更新定位描述，纳入新增的 outcome-aware 能力说明（不只是 quota 快照 + provider preference）。
  - `schema.md`（或 JSON Schema 文件）：route decision + outcome ledger schema。
  - `scripts/`：新增 outcome ledger 相关脚本（如 `outcome_ledger.py`），`read_agent_quota.py` 只做加法式扩展，
    不改既有 `route_recommendation` 默认行为。
  - `fixtures/`（或 `fixtures/outcome/`）：冻结的 quota 快照 + outcome ledger 样本，供 replay/validator 使用。
  - `.outcome-ledger/`：**已决策：真实累积数据的落盘目录**——repo 内、gitignored，只保留少量说明性文件入
    Git（`README.md`/`.gitkeep`），明细日志本地生成、不进 Git；模式参照本 repo 已有的
    `.claude/agent-reports/`（gitignored 明细 + 少量入 Git 的说明文件）与用户级 `.search-index` 的「本地缓存,
    只读汇总入库」思路，但落点选在 repo 内而非仓外用户目录。见「未解决问题 2：已决策」。
  - tests。
- `.agents/skills/coding-agent-quota/SKILL.md`（**adapter 同步生成物，不可手改**）：`SKILL.md` 正文因新增
  outcome-aware 描述而变化后，需重跑 `python scripts/sync-codex-adapters.py` 更新此文件，否则
  `sync-codex-adapters.py --check` 会报 `stale adapter`（Codex 侧看不到最新描述）。因为是扩展既有 skill 而非
  新开 skill，这里是「更新」而不是「新建」adapter 文件。
- `.claude/skills/subagent-routing/SKILL.md`（补充「需要读取的 ledger」一节，引用新增 outcome ledger）。
- `.agent/model-routing-policy.md`（补充 outcome-aware 整合小节：何时参考 outcome 证据、benchmark 冻结规则位置）。
- `.agent/templates/launch-packet.md`（**已决策：只增加 `decision_id` 引用字段**，不内嵌完整证据链——完整证据
  由 ledger 按 `decision_id` 查询，见「未解决问题 5：已决策」）。
- `.agent/templates/routing-benchmark-card.md`（**新增，已决策**：仿 `.agent/templates/experiment-card.md`
  同构，承载 benchmark 冻结产物——模型池、路由 policy 版本、预算上限、fixture 版本、冻结时间、hash，见
  「未解决问题 4：已决策」）。
- `.claude/ANATOMY.md`、`.agents/ANATOMY.md`、`scripts/ANATOMY.md`、`.agent/ANATOMY.md`（本轮不新开 skill 目录，
  预计结构变化较小；若 `coding-agent-quota` 下新增子目录/文件、或 `.agent/templates/` 新增
  `routing-benchmark-card.md` 导致既有 ANATOMY 条目描述过期，按 same-commit rule 同步更新受影响的地图，
  只更新确实发生结构变化的地图）。
- `scripts/`（新增只读 validator，如 `check-outcome-ledger-schema.py`；同步更新 `scripts/README.md`）。
- `.gitignore`（**已决策**：新增 `.claude/skills/coding-agent-quota/.outcome-ledger/**` 之类的忽略条目，
  只放行 `README.md`/`.gitkeep`，模式对齐 `.claude/agent-reports/*` 现有写法）。
- `plans/20260712-outcome-aware-routing.zh.md`（本文件自身）。

## Forbidden paths

- 任何 credential / token / secret 存放位置：`~/.codex/auth.json`、`~/.claude/**`（除已被 `coding-agent-quota` 白名单的
  `~/.claude/.search-index/usage.db` 只读路径外，不新增读取范围）、`.env*`、`~/.paseo/**` 中任何看起来像密钥的字段。
  硬约束：脚本只读本地非敏感 usage/outcome 快照，不打印、不上传、不联网认证。
- `lab/data/**`、`lab/runs/**`、`lab/models/**` 权重、`checkpoints/**`、`wandb/**`、`lab/infra/private/**`。
- 不改 `coding-agent-quota/scripts/read_agent_quota.py` 中 `route_recommendation` 的既有打分逻辑与默认行为
  （只允许新增可选字段/参数），避免破坏依赖它的 `subagent-routing` 现有流程。
- 不引入任何形式的在线学习/强化学习调度循环代码。
- push `main`/`master`、开 PR/merge/release、改远端基础设施：遵循项目通用边界，需 human 批准。

## 任务树

- [x] Parent: 建立 outcome-aware 路由第一版（启发式 + 离线校准）—— 2026-07-12 实现完成，见 Plan revision log 末条
  - [x] Child A：定义 route decision + outcome ledger schema
    - 字段草案：`decision_id`、`decided_at`、`task_class`、`role`、`routing_tier`、`provider`、`model`、
      `effort`（provider 原生值）、`policy_version`、
      `orchestrator`/`launch_surface`（**新增，Codex 侧关键**：谁发起并执行——`claude_subagent` /
      `codex_exec` / `codex_rescue` / `ccg` / `paseo_lane`；同一个 `provider/model` 可经不同编排面启动，
      不记录就无法把 Codex 侧结果和 Claude 侧结果做同口径比较，也无法回答「这条路线给谁用」），
      `tokens_in`/`tokens_out`、`latency_wall_clock_s`、`outcome_observed_at`、`outcome_status`（`pending` /
      `observed` / `unavailable`）、`outcome_quality`（首版用 verifier pass/fail 或测试通过率等可自动信号）、`rework_count`、
      `failure_reason`（枚举，可空）、`quota_snapshot_ref`（关联 `read_agent_quota.py` 输出的
      `generated_at`/`source`，用于追溯）。
    - **决策与结果生命周期不可混淆**：route decision 创建时 outcome 尚不存在；允许先写 `pending`，完成后用同一
      `decision_id` 补 outcome，或拆成 decision/outcome 两类记录。无论选哪种，validator 都必须拒绝“未运行却已有结果”
      和“observed 但没有观测时间/证据来源”的记录。
    - **成本字段拆分（rigor，初稿把两种成本混成一个 `cost` 字段是错的）**：
      - `quota_cost`：本次消耗的当前窗口/周额度百分比——对 Claude Code、Codex 这类**订阅制** runtime，
        这才是真正稀缺、可解释的预算（`usage_velocity` 已明确 cost proxy「burn proxy, not metered billing」）。
        但共享订阅窗口内可能同时有其他 session 消耗，不能把窗口差值无条件归因给单次任务；应记录前后 snapshot、
        采样时间与 `attribution_confidence`，无法隔离时将其标为 estimate，而不是伪装成精确单次成本。
        **本版唯一实现的成本字段。**
      - `metered_price_estimate`**（已决策：本版不实现，见「未解决问题 6」）**：曾设想含 `source`/`as_of`/
        货币的按量计费 $/token 估算字段，供假设 API 路线参考。本版 schema **不落地此字段**——两侧 runtime
        目前都是订阅制，没有真实按量计费路线可对照，强行估价是 false precision 风险；留作未来扩展点，等
        真有按量计费路线时再补。
    - **命名与 policy 来源分层**：`provider`/`model` 要对齐 `read_agent_quota.py::model_for()` 当前输出及
      `route_recommendation` 的 `codex/<model>` / `claude/<model>` 约定；`routing_tier` 保留跨生态抽象档，
      `effort` 记录实际传给 provider 的原生值。不要让 schema 的历史可读性依赖一个会随 policy 改动的函数；
      由带版本的 model catalog/policy snapshot 做校验依据，并记录 `policy_version`。
    - **effort 词表需对账**：现脚本对 tier 4 造了合成值 `"xhigh"`，但 `.agent/model-routing-policy.md` 的
      tier 表最高只到「high effort」，且 Codex 真正的旋钮是 `model_reasoning_effort`。schema 的 `effort` 枚举
      应对齐 provider 原生取值，并另以 `routing_tier` 表达跨生态抽象档；别让 `xhigh` 这种未对账的合成值直接
      进入 Codex 的 `effort` 字段。Codex 每次启动可用 `-c model_reasoning_effort=<value>` 执行路由建议，详见
      「已核实的 Codex / validator 结论」。
    - 输出：`.claude/skills/coding-agent-quota/schema.md`（或 JSON Schema 文件，落在扩展后的
      `coding-agent-quota` skill 内，见「未解决问题 1：已决策」）+ 至少 3 条示例记录，
      其中**至少 1 条为 Codex 生态路线**（如 `codex_exec` + `gpt-5.6-sol` + 某 `model_reasoning_effort`），
      证明 schema 不是只能装 Claude 记录。
  - [x] Child B：本版不做价格表，只汇总 quota + outcome 两维证据（已决策，见「未解决问题 6」）
    - **本版范围**：不引入 $/token 价格表或速度基准来源；只做两类证据——(1) quota 消耗（`quota_cost`，
      来自 `read_agent_quota.py` snapshot）、(2) 历史任务结果（outcome ledger 里的 `outcome_quality`、
      `rework_count`、`failure_reason` 等）。候选路线比较的默认且唯一排序键是 `quota_cost`，不涉及美元估价。
    - 价格/速度参考文件（曾设想的 `.claude/skills/coding-agent-quota/price-speed-reference.yaml`）本版
      不做，留作未来扩展点：等两侧 runtime 出现真实按量计费路线、且有可靠公开价格来源时再单开任务评估。
    - 原「订阅 vs 计费的建模张力」讨论已由 human 拍板收敛：缺数据时保守不引入，聚焦 quota + outcome 两维，
      避免 false precision（理由详见「未解决问题 6：已决策」）。
  - [x] Child C：离线 fixture + replay
    - `.claude/skills/coding-agent-quota/fixtures/`（或其下 `fixtures/outcome/` 子目录）放冻结的 quota 快照 +
      outcome ledger 样本（不含 price/speed 参考，本版未引入该来源）。
    - replay 脚本：输入同一份 fixture 应产出确定性相同的路由决策；改变额度/成功率后能展示路线切换与理由差异。
    - 固定 tie-break 次序、时间输入和浮点/序列化规范；确定性断言比较规范化结构或稳定 JSON，不依赖 map 遍历顺序。
    - 覆盖「验收标准」第 2 条。
  - [x] Child D：与现有 quota-aware 路由整合
    - `route_agent_quota.py`（或新脚本，同落在 `coding-agent-quota` 内）在 `route_recommendation` 之外新增可选
      `outcome_route_recommendation` 字段（不改既有字段），说明其相对现有 quota-only 推荐的差异与理由。
    - `subagent-routing/SKILL.md` 步骤 3-4 更新：读取 quota 证据后，若 outcome 证据可用则一并读取，
      launch packet 增补字段（沿用 `.agent/templates/launch-packet.md` 扩展，而非另起模板）。**已决策
      （见「未解决问题 5：已决策」）：证据链落地形式只给 `decision_id`**——launch packet 里只放
      `outcome_decision_id`（+ 极简的 `degraded`/回退提示，供人一眼看出是否走了保守回退），不内嵌完整 quota
      snapshot / outcome 摘要；需要完整证据时按 `decision_id` 去 outcome ledger（
      `.claude/skills/coding-agent-quota/.outcome-ledger/`）另查。这样 launch-packet 模板改动幅度更小，且
      避免证据在 packet 与 ledger 两处重复维护、容易失步。
    - **Codex 可消费性（初稿只从 Claude subagent 视角写，缺这块）**：能力必须**脚本优先**——核心逻辑落在
      `.claude/skills/coding-agent-quota/scripts/*.py`，可用「repo root 下 plain `python ...`」从两个 runtime
      等价调用（现有 `read_agent_quota.py` 就是这么被两侧共用的，这是 Codex 平价的关键杠杆）。SKILL.md 只当薄文档。
      证据：`sync-codex-adapters.py::_skill_adapter()` 只是把 SKILL.md 正文加个 note 复制到 `.agents/skills/`，
      **不会**把 scripts、slash 触发、statusLine 搬过去；所以凡是要 Codex 也能跑的行为，都不能只写在 SKILL.md
      的叙述里、更不能依赖 Claude 专属的 slash command 或 subagent 工具集，必须能由 CLI 直接跑脚本得到。
    - launch-packet 扩展字段要保持 provider-neutral：`recommended_provider` 已支持 `codex`，新增的
      `outcome_decision_id` 字段不能引入只有 Claude 才有的假设（如「必然经 Task subagent 派发」）。
  - [x] Child E：Fallback 与保守回退行为
    - 明确「缺数据 / 数据过期」判定阈值（复用 `read_agent_quota.py` 现有 `freshness_warning` 思路）。
    - 触发条件下：outcome 层直接标注 `degraded: true` + 原因，路由结果回退为当前 quota-aware 推荐，
      不得用缺失/过期数据伪装成精确数字。覆盖「验收标准」第 5 条。
  - [x] Child F：正式 benchmark 冻结机制
    - 定义「冻结」产物：模型池、路由 policy 版本、预算上限、fixture 版本一次性锁定，运行期间不因中途
      quota 变化切换（本版不涉及价格维度，沿用 `.agent/model-routing-policy.md` 里 transfer experiment 的
      冻结先例）。
    - 输出：**已决策（见「未解决问题 4：已决策」）**——新增 `.agent/templates/routing-benchmark-card.md`
      模板，仿 `.agent/templates/experiment-card.md` 同构（Question/Hypothesis/Config/Baseline/Success
      metric/Failure signals/Artifact paths 一类结构，按 routing 场景替换字段），至少包含 policy 版本号/hash、
      模型池快照、预算上限、fixture 版本、冻结时间、涉及字段清单。实际填写的 card 存放位置沿用该模板注释里
      指定的路径约定（参照 experiment card 存 `lab/code/experiments/<id>.md` 并登记 ledger 的模式，具体登记
      文件留给 Child F 实现时确定，例如落在 `.claude/skills/coding-agent-quota/` 下）。
  - [x] Child G：报告拆分
    - 路由结果能分别报告 token、quota 消耗（`quota_cost`）、wall-clock、昂贵模型（如 opus/xhigh effort）用量、
      任务结果，不合并成单一「分数」掩盖构成。不含 $ 价格维度（本版未引入，见「未解决问题 6：已决策」）。
      覆盖「验收标准」第 4 条。
  - [x] Child H：Validator / tests
    - `scripts/check-outcome-ledger-schema.py`（只读、无第三方硬依赖，风格对齐现有三个 validator 脚本）：
      校验 ledger schema、fixture 可解析、fallback 路径确实触发、且脚本不读取 credential 文件。
    - **新增校验：provider/model/effort 词表不得漂移为 Claude-only**：取值不得越出 fixture 冻结的、带
      `policy_version` 的 model catalog/provider 原生 effort 词表；同时断言
      fixture 中至少有一条 Codex 生态记录，保证跨 provider schema 不退化成只装 Claude。
    - 接入 `scripts/validate-governance.py` 或独立运行，更新 `scripts/README.md`。覆盖「验收标准」第 6 条。
    - **不要漏跑 adapter 同步门禁**：改动收尾必须 `python scripts/sync-codex-adapters.py`（更新既有的
      `.agents/skills/coding-agent-quota/SKILL.md`——因为是扩展现有 skill 而非新开 skill，这里是 update 不是
      create），并让 `sync-codex-adapters.py --check` 通过——否则 Codex 侧看不到新增的 outcome-aware 描述，
      且 harness/治理检查会因 stale adapter 失败。

## Human 批注区

<!-- human 在此直接写批注/修改，Claude 下一轮读 diff 收敛 -->

## 当前决策

- **价格表本版不引入**（human 2026-07-12 拍板，采纳 Codex 三审建议）：只做 quota + outcome 两维，不做
  $/token 价格表或速度基准来源；schema 里 `metered_price_estimate` 字段与
  `price-speed-reference.yaml` 产物本版均不实现，留作未来扩展点。理由：两侧 runtime 都是订阅制、缺乏真实
  按量计费路线和可靠公开价格数据，强行引入是 false precision 风险；聚焦 quota + outcome 两维更符合
  「缺数据保守」的精神。详见「未解决问题 6：已决策」。
- **扩展 `coding-agent-quota` 而非新开独立 skill**（human 2026-07-12 拍板，见「未解决问题 1：已决策」）：outcome-aware
  能力直接落进 `.claude/skills/coding-agent-quota/`。此前初稿与三轮审查都默认新开独立 skill，理由是「关注点
  分离」（quota 是「还剩多少」，outcome 是「值不值得」）；human 最终推翻，选择合并，理由：两者语义相近、都是
  路由决策支持，合并能减少概念数量，即使让 `coding-agent-quota` 职责因此变重也可接受。
- 第一版「任务结果质量」信号只用可自动获取的代理指标（verifier pass/fail、测试通过率、返工次数），不引入
  人工主观评分体系。
- **outcome ledger 落盘位置：repo 内 gitignored 目录**（human 2026-07-12 拍板，见「未解决问题 2：已决策」）：
  真实累积的历史统计明细落在 `.claude/skills/coding-agent-quota/.outcome-ledger/`，参照仓库已有的
  `.claude/agent-reports/` 与用户级 `.search-index` 本地缓存模式——目录本身 gitignored，只留
  `README.md`/`.gitkeep` 入 Git；schema 与少量冻结 fixture 样本单独入 Git（见 Allowed paths）。不采用仓外
  用户目录方案。
- **benchmark 冻结产物用新模板**（human 2026-07-12 拍板，见「未解决问题 4：已决策」）：新增
  `.agent/templates/routing-benchmark-card.md`，仿 `.agent/templates/experiment-card.md` 同构，不用裸
  YAML/JSON 文件。
- **路由输出证据链：只给 `decision_id`**（human 2026-07-12 拍板，见「未解决问题 5：已决策」）：launch packet
  不内嵌完整证据链（quota snapshot + outcome 摘要），只放 `outcome_decision_id`，完整证据按 ID 去 ledger
  查询，减少 launch-packet 模板改动幅度与信息重复维护成本。

## 未解决问题

1. **新 skill vs 扩展现有 skill**——**已决策（human 2026-07-12 拍板，选择题逐条批注）：扩展现有
   `coding-agent-quota`，不新开独立 skill**。此前初稿与三轮 AI 审查（Claude Opus、Codex 二审、Codex 三审）
   均倾向新开独立 skill，理由是关注点分离；human 最终推翻该判断，理由：两者语义相近，都是路由决策支持，
   合并能减少概念数量，即使 `coding-agent-quota` 职责因此变重也可接受。此项不再是 open question。
2. **ledger 实际存储位置**——**已决策（human 2026-07-12 拍板）：repo 内 gitignored 目录**，落在
   `.claude/skills/coding-agent-quota/.outcome-ledger/`，参照仓库现有 `.claude/agent-reports/` 与用户级
   `.search-index` 的「本地缓存/明细不入 Git」模式，但落点选在 repo 内而非仓外用户目录（原候选 (b) 落选）。
   此项不再是 open question。
3. ~~价格/速度来源的更新方式~~ —— **已随「未解决问题 6」的决策一并作废**：本版不引入价格/速度参考文件，
   此问题不再适用；等未来真的要做价格表时再重新提出。
4. **benchmark 冻结产物落在哪**——**已决策（human 2026-07-12 拍板）：新增
   `.agent/templates/routing-benchmark-card.md`**，仿 `.agent/templates/experiment-card.md` 同构，不用裸
   YAML/JSON 文件。此项不再是 open question。
5. **验收标准第 1 条「每次路由输出可追溯」的落地形式**——**已决策（human 2026-07-12 拍板）：launch packet
   只给可查询的 `decision_id`**，不内嵌完整证据链（quota snapshot + outcome 摘要）；完整证据由 outcome
   ledger 按 `decision_id` 另存/查询。launch-packet 模板改动幅度因此更小。此项不再是 open question。
6. **成本口径以谁为准**——**已决策（human 2026-07-12 拍板）：不引入价格表**。候选路线排序默认且唯一用订阅
   `quota_cost`；`metered_price_estimate` 本版不实现，「价格」维度整体推迟到真有按量计费路线时再加。理由：
   两侧 runtime 目前都是订阅/额度制，缺乏真实公开价格数据支撑 $/token 估算，强行引入是 false precision
   风险；聚焦 quota + outcome 两维更贴合 issue #15「缺数据保守」的精神。此项不再是 open question。

## 已核实的 Codex / validator 结论

1. **Codex reasoning effort 是逐次启动可控旋钮，不是只能写全局 config。** 本轮真实 Codex 会话使用
   `gpt-5.6-sol`，并由启动命令显式传入 `-c model_reasoning_effort=medium`；项目 `.codex/config.toml` 未设置该键。
   本机 `codex --help` 与 `codex exec --help` 均把 `-c/--config <key=value>` 定义为覆盖原本从 config.toml 加载的
   配置值，且 `codex -c model_reasoning_effort=medium --strict-config --version` 在 Codex CLI 0.144.0 下通过。
   因而 router 对 Codex 路线可以生成可执行的 `-c model_reasoning_effort=<原生值>`，无需默认标记
   `advisory_only: true`。但“custom agent 的 TOML 是否存在独立 effort 字段”不是本结论所需前提：稳妥的首版执行
   面就是每次 `codex` / `codex exec` 启动时加 `-c`；实际生效值仍应写入 ledger。
2. **新增 skill 必须更新 anatomy，但不能靠 `check-anatomy-drift.py` 自动发现漏登记。** 已读该脚本：它只检查
   `ANATOMY.md` 已有引用是否存在、行号是否越界及行数上限，不扫描“新目录是否已登记”。真正的约束来自
   `.agent/anatomy-protocol.md` 的 same-commit rule：新增 routing/workflow、adapter 和 validator 后，应同步更新
   `.claude/ANATOMY.md`、`.agents/ANATOMY.md`、`scripts/ANATOMY.md` 中实际受影响的结构说明，再跑 anatomy/governance
   门禁。不能以 drift checker 暂时通过作为无需更新 anatomy 的证据。
3. **真实双 runtime smoke 仍需在实现后执行。** 本轮已证明 Codex CLI 可逐次接收 effort override，也证明当前
   Codex agent 能在 repo root 调用 plain Python；但 outcome routing/replay 脚本尚未创建，所以现在验证不了它们的
   真实 `codex exec` 输出。首版把真实 `codex exec` fixture smoke 设为验收项，不再把“是否需要”留作 open question。

## 验证标准

- `python scripts/validate-governance.py` 通过（含新增的 outcome ledger schema 检查）。
- `python .claude/skills/coding-agent-quota/scripts/read_agent_quota.py --role impl --tier 2 --format json`
  行为不变（向后兼容回归）。
- 新增的 replay 脚本：同一份冻结 fixture 两次运行输出完全相同（决策确定性）；改变 fixture 中的额度/成功率
  任一项后，输出的推荐路线与理由随之变化，且能指出是哪个信号导致变化（本版不含价格维度）。
- 新增 validator 能检测出：(a) ledger 记录缺字段、(b) fallback 未在过期数据场景下触发（复用
  `read_agent_quota.py` 的 `freshness_warning` 思路判定 quota 数据过期）、(c) 脚本尝试读取 credential
  类路径。**本版不做价格/速度来源校验**（本版未引入该来源，见「未解决问题 6：已决策」）。
- 手工检查：`subagent-routing/SKILL.md` 更新后仍可无破坏地走完既有 launch packet 生成流程（quota-only 场景下
  行为等同现状）。
- `python scripts/sync-codex-adapters.py --check` 通过（`.agents/skills/coding-agent-quota/SKILL.md` 因
  `SKILL.md` 新增 outcome-aware 描述而更新，且不 stale）。**这是初稿验证里完全缺失的一条 Codex 门禁。**
- Codex 平价下限：新 routing/replay/validator 脚本能从 repo root 以 plain `python ...` 直接调用（不依赖 Claude
  专属 Task/subagent 工具或 slash command），fixture 场景下的输出与 runtime 无关；并以一次显式指定
  `-c model_reasoning_effort=medium` 的真实 `codex exec` 运行冻结 fixture，记录命令、退出码与输出摘要。
- fixture 中至少一条 Codex 生态记录能被 schema 校验通过，且 `model`/provider 原生 `effort` 取值不越出该 fixture
  冻结的、带 `policy_version` 的 model catalog。
- decision/outcome 生命周期校验通过：`pending` 不得伪造结果，`observed` 必须有观测时间与证据来源；输出记录实际
  provider/model/effort 与 `policy_version`，而不只是推荐值。
- `git status` 确认 `.claude/skills/coding-agent-quota/.outcome-ledger/` 下的实际累积明细不被 Git 追踪
  （只有 `.gitignore` 新增条目、`README.md`/`.gitkeep` 入 Git），验证「已决策：repo 内 gitignored 目录」落地正确。
- launch packet 手工抽查：只出现 `outcome_decision_id`（+ 简要 `degraded` 提示），不内嵌完整 quota
  snapshot / outcome 摘要；凭该 ID 能在 `.outcome-ledger/` 中查到完整记录，验证「已决策：只给 decision_id」
  落地正确。

## 下一步

- 「未解决问题」1-6 已全部由 human 拍板收敛（3 因价格表决策一并作废，其余 5 条均已决策）。本文件不再有
  待 human 拍板的 open question。
- 按任务树 Child A → H 顺序拆 launch packet，逐个交给 subagent-routing 派发实现（每个 child 独立 tier/scope）；
  实现前建议先由 human 对本轮改写做一次快速确认（尤其 Allowed paths 是否准确覆盖了 `coding-agent-quota` 扩展
  范围），再正式开工。

## Plan revision log

- 2026-07-12 初稿。
- 2026-07-12 第二意见审查（由 Claude Opus 4.8 代替额度耗尽的 Codex 二审执行，审查重点不变）：补齐 Codex
  侧缺口——双 runtime schema 定位、adapter 同步生成物与门禁、`orchestrator`/`launch_surface` 字段、成本口径拆
  分（quota_cost vs metered_price_estimate）、effort/`model_reasoning_effort` 对账、脚本优先的 Codex 可消费性、
  validator 覆盖跨 provider 词表、验证加 `sync-codex-adapters.py --check`；新增未解决问题 6-9。人类最终批准仍待定。
- 2026-07-12 Codex 真实二审（`gpt-5.6-sol`，`medium` reasoning effort）：以本次
  `-c model_reasoning_effort=medium` 启动和 Codex CLI 0.144.0 帮助/strict-config 验证，确认 effort 可逐次覆盖；
  核实 anatomy checker 边界并将真实 `codex exec` smoke 固化为实现后验收项；补充 decision/outcome 生命周期、
  policy 版本、原生 effort、确定性与 allowed paths 修订。人类最终批准仍待定。
- 2026-07-12 human 亲自拍板（采纳 Codex 三审建议）：价格表本版不引入，聚焦 quota + outcome 两维。落地为
  Child B 改写、`metered_price_estimate` 标记不实现、验证标准与 Child C/G 相应删改、未解决问题 6 标记
  「已决策：不引入」、未解决问题 3 随之作废。此项决策不再是 open question。
- 2026-07-12 human 亲自逐条拍板（选择题形式，一次性决完剩余 4 条 open question）：(1) **outcome-aware 新能力
  扩展现有 `.claude/skills/coding-agent-quota/`，不新开独立 skill**——推翻此前初稿与三轮 AI 审查（Claude
  Opus、Codex 二审、Codex 三审）「倾向新开独立 skill」的判断，理由是两者语义相近、都是路由决策支持，合并
  减少概念数量，即使职责因此变重也可接受；(2) outcome ledger 真实累积数据落盘于 **repo 内 gitignored 目录**
  `.claude/skills/coding-agent-quota/.outcome-ledger/`，参照 `.claude/agent-reports/`/`.search-index` 本地
  缓存模式，不落在仓外用户目录；(3) benchmark 冻结产物新增 **`.agent/templates/routing-benchmark-card.md`**
  模板，仿 `.agent/templates/experiment-card.md` 同构；(4) 路由输出证据链**只给 `decision_id`**，完整证据
  按 ID 存 ledger 查询，不在 launch packet 内嵌完整证据链。落地范围：当前目标、Allowed paths、任务树
  Child A/C/D/F/H、当前决策、未解决问题 1/2/4/5、验证标准均相应改写。未解决问题 1-6 至此全部收敛，本文件
  不再有待拍板的 open question。

- 2026-07-12 分支同步 + 新增信号来源提示（监控员编排）：把 main 最新进展（PR #20/#21、v1.2.0/v1.3.0）merge
  进本分支，确认 `.claude/skills/coding-agent-quota/`（本计划扩展目标）现状不受影响。另外记录一条本轮从
  Paseo 操作中发现、本计划尚未纳入的信号来源：**`~/.paseo/orchestration-preferences.json`** 是 Paseo 官方
  按角色（impl/ui/research/planning/audit）定默认 provider 的偏好文件，`coding-agent-quota`/本计划新增的
  outcome-aware 路由目前完全没有读取它。这不是本轮决策范围内的新 open question（不影响此前已收敛的 6 条），
  而是留给实现阶段的一条具体提示：route decision ledger 在记录"为什么选了这条路线"时，若目标 agent 是走
  Paseo 起的（比如 #14 的 Paseo-first 多 agent 控制面），应该把该文件的角色偏好也纳入可解释性证据链，
  不要只看 `model-routing-policy.md` 一侧。是否要据此新增字段，留给实现者按证据判断。

- 2026-07-12 实现完成（Child A-H 全部落地，worker：干将·改·路由）。要点：(1) schema + 示例落
  `.claude/skills/coding-agent-quota/schema.md`，词表冻结在 `fixtures/outcome/model-catalog.v1.json`
  （`routing-policy-v1`；codex `effort_vocab` 不含 `xhigh`，抽象档走 `routing_tier`）；(2) 脚本
  `scripts/outcome_ledger.py`（append-only JSONL、生命周期校验、summary 分维报告）与
  `scripts/outcome_route.py`（确定性 replay、degraded 回退、`outcome_route_recommendation` 加在
  `route_recommendation` 之外、`--record` 落 decision）；(3) 真实明细落 gitignored
  `.outcome-ledger/`（.gitignore 已加条目）；(4) launch-packet 模板只加 `outcome decision id` +
  `outcome degraded` 两行；(5) 新增 `.agent/templates/routing-benchmark-card.md` 与
  `benchmarks/README.md` 登记索引；(6) validator `scripts/check-outcome-ledger-schema.py` 接入
  `validate-governance.py`；(7) 监控员记录的 Paseo 偏好提示已落为 decision 记录的
  `paseo_preference: {status, role_default}` 字段（复用 `read_agent_quota.py` 既有读取逻辑，文件缺失时
  status=missing 优雅降级，不新增读取面）。验证：14/14 targeted unittest、validate-governance OK、
  `sync-codex-adapters.py --check` OK、真实 `codex exec -c model_reasoning_effort=medium` smoke
  exit 0（gpt-5.6-terra/medium/degraded=false，deterministic decision_id）。
- 2026-07-13 fresh review 门槛修复（worker：干将·改·15结果路由）：移除生产 CLI
  `--allow-test-dir` 任意写逃生口，只允许 canonical `.outcome-ledger/` 与字面 `/tmp`，并拒绝
  repo 根、`.env*`、symlink/realpath 越界；统计与推荐改按 `provider + model + effort + role +
  task_class + routing_tier + policy_version` 完整具体路线隔离；`record-decision` 与
  `outcome_route --record` append 前拒绝重复 `decision_id`；`--min-samples` 收紧为 ≥1，零
  observed outcome 强制 degraded quota-only fallback。对抗回归覆盖四项门槛。
