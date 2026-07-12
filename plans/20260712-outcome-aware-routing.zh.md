# outcome-aware 路由 交互式计划

> Claude 写初稿 → human 在文件里批注 → Claude 读 diff、收敛计划 → 每次采纳的修订做一个小 commit。
> 实现只在 scope / forbidden paths / verification 清楚后开始。

## 当前目标

在现有 `coding-agent-quota`（额度快照 + provider preference）与 `subagent-routing`（launch packet 生成）之上，
增量建立一层 **outcome-aware** 路由：让 route decision 除了 quota 之外，还能引用价格/速度来源和历史任务结果
（成功率、延迟、返工、失败原因），在相同预算下给出可解释、可离线复现的候选路线比较，并在数据缺失/过期时
保守回退到当前 quota-aware 行为。这是 issue #15 的第一版落地：可解释启发式 + 离线校准，不是在线学习调度器。

**双 runtime 定位（issue #15「注意」条款）**：这层路由不只服务 Claude Code 派 subagent，也要能服务
Codex 侧编排（`codex exec`、`codex-rescue`、`ccg` 这类跨 provider 场景）。因此 schema 从第一版起就必须
provider-neutral，把 Claude 生态（Opus/Sonnet/Haiku tier + Claude effort）与 Codex 生态（`gpt-5.5`、
`gpt-5.6-luna/terra/sol` 等 + Codex `model_reasoning_effort`）纳入**同一张**决策/结果表，而不是只按
Opus/Sonnet/Haiku tier 建模、把 Codex 当附注。证据：现有 `read_agent_quota.py` 的 `model_for()` 已经为两
个生态各自维护了 model 清单与 effort 阶梯（`{0:none,1:low,2:medium,3:high,4:xhigh}`），新 ledger 应**复用**
这份映射作为受控词表的单一来源，而不是另造一套只认 Claude tier 的枚举。

## 非目标

- 不实现在线强化学习 / 自适应 bandit 调度器；不在运行中根据实时反馈静默切换 policy（issue #15「边界」条款）。
- 不改变 `coding-agent-quota` 现有 `route_recommendation` 字段的既有语义或默认输出（`--format table/json` 向后兼容），
  只做加法式扩展。
- 不读取任何 credential / token / API key 文件；不新增需要联网认证的价格抓取（本版只做本地/公开、可标注来源与新鲜度的价格与速度表）。
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

- `.claude/skills/outcome-aware-routing/**`（新 skill：`SKILL.md`、`scripts/`、`fixtures/`、schema 文档、tests）—— 待 human 确认是否新开 skill（见「未解决问题」）。
- `.agents/skills/outcome-aware-routing/**`（**adapter 同步生成物，不可手改**）：`sync-codex-adapters.py` 会为每个
  `.claude/skills/*/SKILL.md` 生成对应 Codex adapter。**新开 skill 必须跑 `python scripts/sync-codex-adapters.py`
  并把生成的 `.agents/skills/outcome-aware-routing/SKILL.md` 一并提交**，否则 `sync-codex-adapters.py --check`
  会报 `missing generated adapter`（Codex 侧根本看不到这个能力）。初稿完全漏掉了这一步与这条路径。
- 若最终新开 skill 目录，需确认是否触发 `check-anatomy-drift.py`（结构清单漂移）；如触发则同步更新对应
  `ANATOMY.md`，否则 `validate-governance.py` 会因 anatomy drift 失败（见未解决问题 6）。
- `.claude/skills/coding-agent-quota/**`（增量扩展：暴露必要字段/CLI 参数给 outcome-aware 层消费，不破坏既有输出）。
- `.claude/skills/subagent-routing/SKILL.md`（补充「需要读取的 ledger」一节，引用新增 outcome ledger）。
- `.agent/model-routing-policy.md`（补充 outcome-aware 整合小节：何时参考 outcome 证据、benchmark 冻结规则位置）。
- `scripts/`（新增只读 validator，如 `check-outcome-ledger-schema.py`；同步更新 `scripts/README.md`）。
- `.gitignore`（若采用本地落盘 ledger，需要新增对应忽略条目）。
- `plans/20260712-outcome-aware-routing.zh.md`（本文件自身）。

## Forbidden paths

- 任何 credential / token / secret 存放位置：`~/.codex/auth.json`、`~/.claude/**`（除已被 `coding-agent-quota` 白名单的
  `~/.claude/.search-index/usage.db` 只读路径外，不新增读取范围）、`.env*`、`~/.paseo/**` 中任何看起来像密钥的字段。
  硬约束：脚本只读本地非敏感 usage/price/outcome 快照，不打印、不上传、不联网认证。
- `lab/data/**`、`lab/runs/**`、`lab/models/**` 权重、`checkpoints/**`、`wandb/**`、`lab/infra/private/**`。
- 不改 `coding-agent-quota/scripts/read_agent_quota.py` 中 `route_recommendation` 的既有打分逻辑与默认行为
  （只允许新增可选字段/参数），避免破坏依赖它的 `subagent-routing` 现有流程。
- 不引入任何形式的在线学习/强化学习调度循环代码。
- push `main`/`master`、开 PR/merge/release、改远端基础设施：遵循项目通用边界，需 human 批准。

## 任务树

- [ ] Parent: 建立 outcome-aware 路由第一版（启发式 + 离线校准）
  - [ ] Child A：定义 route decision + outcome ledger schema
    - 字段草案：`decision_id`、`ts`、`task_class`、`role`、`tier`、`provider`、`model`、`effort`、
      `orchestrator`/`launch_surface`（**新增，Codex 侧关键**：谁发起并执行——`claude_subagent` /
      `codex_exec` / `codex_rescue` / `ccg` / `paseo_lane`；同一个 `provider/model` 可经不同编排面启动，
      不记录就无法把 Codex 侧结果和 Claude 侧结果做同口径比较，也无法回答「这条路线给谁用」），
      `tokens_in`/`tokens_out`、`latency_wall_clock_s`、
      `outcome_quality`（首版用 verifier pass/fail 或测试通过率等可自动信号）、`rework_count`、
      `failure_reason`（枚举，可空）、`quota_snapshot_ref`（关联 `read_agent_quota.py` 输出的
      `generated_at`/`source`，用于追溯）。
    - **成本字段拆分（rigor，初稿把两种成本混成一个 `cost` 字段是错的）**：
      - `quota_cost`：本次消耗的当前窗口/周额度百分比——对 Claude Code、Codex 这类**订阅制** runtime，
        这才是真正稀缺、可解释的预算（`usage_velocity` 已明确 cost proxy「burn proxy, not metered billing」）。
      - `metered_price_estimate`（可选，含 `source`/`as_of`/货币）：只对**按量计费/假设 API 路线**有意义的
        公开 $/token 估算，必须标为 estimate，不得和订阅额度相加或伪装成实际账单。
    - **受控词表单一来源**：`provider`/`model`/`effort` 的合法取值必须复用 `read_agent_quota.py::model_for()`
      现有映射（同时覆盖 Codex 与 Claude 两个生态），schema 文档显式引用它，避免只列 Opus/Sonnet/Haiku。
      注意对齐现有 `route_recommendation` 已产出的 `codex/<model>` / `claude/<model>` 字符串约定，两层可互通。
    - **effort 词表需对账**：现脚本对 tier 4 造了合成值 `"xhigh"`，但 `.agent/model-routing-policy.md` 的
      tier 表最高只到「high effort」，且 Codex 真正的旋钮是 `model_reasoning_effort`。schema 的 `effort` 枚举
      要么对齐 Codex 原生取值、要么显式标注「跨生态抽象档 → 各 provider 原生 effort」的映射，别让 `xhigh`
      这种未对账的值进 ledger（见未解决问题 7）。
    - 输出：`.claude/skills/outcome-aware-routing/schema.md`（或 JSON Schema 文件）+ 至少 3 条示例记录，
      其中**至少 1 条为 Codex 生态路线**（如 `codex_exec` + `gpt-5.6-sol` + 某 `model_reasoning_effort`），
      证明 schema 不是只能装 Claude 记录。
  - [ ] Child B：汇总价格/速度/历史 outcome 来源
    - 本地/公开 provider 价格表 + 速度基准，每条来源必须带 `source`、`fetched_at`/`as_of`、
      `staleness_policy`（超过多久算过期，过期后如何降级）。
    - 输出：一份可版本化的价格/速度参考文件（如 `.claude/skills/outcome-aware-routing/price-speed-reference.yaml`），
      与 outcome ledger 的历史统计口径分开存放，避免把「静态参考价」和「实测结果」混为一谈。
    - **订阅 vs 计费的建模张力（rigor）**：本 repo 两侧 runtime 目前都是订阅/额度制，$/token 参考价对它们
      不是真实边际成本。价格表要显式区分「订阅额度视角」（真实约束，来自 quota snapshot）与「按量计费估价」
      （仅供假设/跨 provider 对照），并覆盖 Codex 模型行（`gpt-5.5`、`gpt-5.6-*`），别只列 Claude 三档。
      候选路线比较的默认排序键应是 `quota_cost` 而非美元估价（见未解决问题 3）。
  - [ ] Child C：离线 fixture + replay
    - `.claude/skills/outcome-aware-routing/fixtures/` 下放冻结的 quota 快照 + price/speed 参考 + outcome ledger 样本。
    - replay 脚本：输入同一份 fixture 应产出确定性相同的路由决策；改变价格/额度/成功率后能展示路线切换与理由差异。
    - 覆盖「验收标准」第 2 条。
  - [ ] Child D：与现有 quota-aware 路由整合
    - `route_agent_quota.py`（或新脚本）在 `route_recommendation` 之外新增可选 `outcome_route_recommendation`
      字段（不改既有字段），说明其相对现有 quota-only 推荐的差异与理由。
    - `subagent-routing/SKILL.md` 步骤 3-4 更新：读取 quota 证据后，若 outcome 证据可用则一并读取，
      launch packet 增补「outcome evidence + 不确定性」字段（沿用 `.agent/templates/launch-packet.md` 扩展，而非另起模板）。
    - **Codex 可消费性（初稿只从 Claude subagent 视角写，缺这块）**：能力必须**脚本优先**——核心逻辑落在
      `.claude/skills/outcome-aware-routing/scripts/*.py`，可用「repo root 下 plain `python ...`」从两个 runtime
      等价调用（现有 `read_agent_quota.py` 就是这么被两侧共用的，这是 Codex 平价的关键杠杆）。SKILL.md 只当薄文档。
      证据：`sync-codex-adapters.py::_skill_adapter()` 只是把 SKILL.md 正文加个 note 复制到 `.agents/skills/`，
      **不会**把 scripts、slash 触发、statusLine 搬过去；所以凡是要 Codex 也能跑的行为，都不能只写在 SKILL.md
      的叙述里、更不能依赖 Claude 专属的 slash command 或 subagent 工具集，必须能由 CLI 直接跑脚本得到。
    - launch-packet 扩展字段要保持 provider-neutral：`recommended_provider` 已支持 `codex`，新增的 outcome 字段
      不能引入只有 Claude 才有的假设（如「必然经 Task subagent 派发」）。
  - [ ] Child E：Fallback 与保守回退行为
    - 明确「缺数据 / 数据过期」判定阈值（复用 `read_agent_quota.py` 现有 `freshness_warning` 思路）。
    - 触发条件下：outcome 层直接标注 `degraded: true` + 原因，路由结果回退为当前 quota-aware 推荐，
      不得用缺失/过期数据伪装成精确数字。覆盖「验收标准」第 5 条。
  - [ ] Child F：正式 benchmark 冻结机制
    - 定义「冻结」产物：模型池、路由 policy 版本、预算上限、fixture 版本一次性锁定，运行期间不因中途
      quota/价格变化切换（沿用 `.agent/model-routing-policy.md` 里 transfer experiment 的冻结先例）。
    - 输出：冻结记录落在哪（待定，见未解决问题），至少包含 policy 版本号/hash、冻结时间、涉及字段清单。
  - [ ] Child G：报告拆分
    - 路由结果能分别报告 token、费用、wall-clock、昂贵模型（如 opus/xhigh effort）用量、任务结果，
      不合并成单一「分数」掩盖构成。覆盖「验收标准」第 4 条。
  - [ ] Child H：Validator / tests
    - `scripts/check-outcome-ledger-schema.py`（只读、无第三方硬依赖，风格对齐现有三个 validator 脚本）：
      校验 ledger schema、fixture 可解析、fallback 路径确实触发、且脚本不读取 credential 文件。
    - **新增校验：schema 的 `provider`/`model`/`effort` 取值不得越出 `model_for()` 词表**（防 Claude-only 漂移），
      并断言 fixture 中至少有一条 Codex 生态记录，保证跨 provider schema 不退化成只装 Claude。
    - 接入 `scripts/validate-governance.py` 或独立运行，更新 `scripts/README.md`。覆盖「验收标准」第 6 条。
    - **不要漏跑 adapter 同步门禁**：改动收尾必须 `python scripts/sync-codex-adapters.py`（生成/更新
      `.agents/skills/outcome-aware-routing/SKILL.md`），并让 `sync-codex-adapters.py --check` 通过——否则
      Codex 侧看不到该 skill，且 harness/治理检查会因 missing/stale adapter 失败。

## Human 批注区

<!-- human 在此直接写批注/修改，Claude 下一轮读 diff 收敛 -->

## 当前决策

- 默认新开 `.claude/skills/outcome-aware-routing/` 作为独立 skill，与 `coding-agent-quota` 组合而非合并进后者，
  理由：关注点分离（quota 是「还剩多少」，outcome 是「值不值得」），且 `coding-agent-quota` 现有 SKILL.md 已经
  相当聚焦，不希望把它变成大而全的路由脚本。**待 human 确认**（见未解决问题 1）。
- 第一版「任务结果质量」信号只用可自动获取的代理指标（verifier pass/fail、测试通过率、返工次数），不引入
  人工主观评分体系。
- outcome ledger 的历史统计明细默认不进 Git（属于运行时可能增长、含具体任务细节的本地日志），只有 schema
  与少量冻结 fixture 样本进 Git。**具体落盘路径待 human 确认**（见未解决问题 2）。

## 未解决问题

1. **新 skill vs 扩展现有 skill**：是否同意新开 `.claude/skills/outcome-aware-routing/`，还是希望直接在
   `coding-agent-quota` 内加字段/脚本以避免 skill 数量膨胀？
2. **ledger 实际存储位置**：真实累积的 outcome 记录（非 fixture 样本）应该放在哪？候选：
   (a) repo 内新增 `.gitignore` 条目、类似 `lab/artifacts` 的「只存 index 不存明细」模式；
   (b) 完全镜像 `read_agent_quota.py` 的做法，落在 repo 外的用户目录（如 `~/.claude/.search-index/`）；
   (c) `memory/` 下（但 `memory/` 目前是全量入 Git 的活状态层，不适合放会持续增长的运行时日志）。
   默认倾向 (a) 或 (b)，需要 human 拍板。
3. **价格/速度来源的更新方式**：第一版是否只允许人工维护的 YAML（无联网抓取），还是希望留一个可选的、
   不涉及 credential 的公开价格页抓取脚本（若抓取失败则保守回退，标注 stale）？
4. **benchmark 冻结产物落在哪**：是否需要类似 `.agent/templates/experiment-card.md` 的新模板
   （如 `.agent/templates/routing-benchmark-card.md`），还是直接用一份带版本号的 YAML/JSON 文件即可？
5. **验收标准第 1 条「每次路由输出可追溯」的落地形式**：是否要求 launch packet 必须内嵌完整证据链
   （quota snapshot + price/speed source + outcome 摘要），还是允许只给出可查询的 `decision_id` 由 ledger 另存明细？
   影响 launch-packet 模板改动幅度。
6. **新 skill 是否触发 anatomy drift**（需人/后续核实）：`validate-governance.py` 会跑 `check-anatomy-drift.py`。
   我没读该脚本，不确定新增 `.claude/skills/outcome-aware-routing/` 目录是否需要在某个 `ANATOMY.md` 登记。
   落地前应先跑一次 anatomy-drift 确认，若报漂移则把该 skill 纳入结构清单。**标为需核实，不臆断。**
7. **Codex `effort` 到底是不是可控路由旋钮（关键 Codex 不确定性，我无一手运行经验）**：
   - 证据：本 repo 的 `.codex/config.toml` **并没有**设 `model_reasoning_effort`；而 `read_agent_quota.py` 却按
     tier 输出 effort（还含合成值 `xhigh`）。所以「effort」在 Codex 侧当前更像**被记录的属性**，未必是每次 spawn
     可覆盖的**控制旋钮**。
   - 需 human/后续核实：Codex 能否按 `codex exec`/custom-agent 逐次覆盖 `model_reasoning_effort`（类似 Claude
     的 per-call effort），还是只能全局 config 设定？这决定 router 输出的 `effort` 对 Codex 是「建议值」还是
     「可执行指令」，也决定要不要给 Codex 路线的 `effort` 加 `advisory_only: true` 标记。**我不臆断，标为 open。**
8. **成本口径以谁为准**：候选路线排序默认用订阅 `quota_cost`，`metered_price_estimate` 仅作参考——是否认可？
   还是希望在两侧都是订阅制时，本版**根本不引入** $/token 价格表、只做 quota + outcome 两维，把「价格」推迟到
   真有按量计费路线时再加（可能更贴合 issue #15「缺数据保守」的精神，也少一处 false precision 风险）？
9. **是否需要真正的双 runtime smoke**：验证里我加了「脚本从 repo root plain python 调用、两 runtime 等价」的
   要求；但我没有 Codex 一手环境去实跑。是否需要在收敛后安排一次真实 `codex exec` 跑一遍新脚本的 smoke，
   还是接受「脚本 runtime-neutral + adapter --check 通过」作为本版的 Codex 证据下限？

## 验证标准

- `python scripts/validate-governance.py` 通过（含新增的 outcome ledger schema 检查）。
- `python .claude/skills/coding-agent-quota/scripts/read_agent_quota.py --role impl --tier 2 --format json`
  行为不变（向后兼容回归）。
- 新增的 replay 脚本：同一份冻结 fixture 两次运行输出完全相同（决策确定性）；改变 fixture 中的价格/额度/
  成功率任一项后，输出的推荐路线与理由随之变化，且能指出是哪个信号导致变化。
- 新增 validator 能检测出：(a) ledger 记录缺字段、(b) 价格/速度来源缺 `fetched_at`/`source`、
  (c) fallback 未在过期数据场景下触发、(d) 脚本尝试读取 credential 类路径。
- 手工检查：`subagent-routing/SKILL.md` 更新后仍可无破坏地走完既有 launch packet 生成流程（quota-only 场景下
  行为等同现状）。
- `python scripts/sync-codex-adapters.py --check` 通过（新 skill 的 `.agents/skills/outcome-aware-routing/SKILL.md`
  已生成且不 stale）。**这是初稿验证里完全缺失的一条 Codex 门禁。**
- Codex 平价下限：新 routing/replay/validator 脚本能从 repo root 以 plain `python ...` 直接调用（不依赖 Claude
  专属 Task/subagent 工具或 slash command），fixture 场景下的输出与 runtime 无关。是否升级为真实 `codex exec`
  smoke 见未解决问题 9。
- fixture 中至少一条 Codex 生态记录能被 schema 校验通过，且 `model`/`effort` 取值不越出 `model_for()` 词表。

## 下一步

- 等待 human 在本文件内批注，尤其是「未解决问题」1-5。
- 收敛后按任务树 Child A → H 顺序拆 launch packet，逐个交给 subagent-routing 派发实现（每个 child 独立 tier/scope）。

## Plan revision log

- 2026-07-12 初稿。
- 2026-07-12 第二意见审查（由 Claude Opus 4.8 代替额度耗尽的 Codex 二审执行，审查重点不变）：补齐 Codex
  侧缺口——双 runtime schema 定位、adapter 同步生成物与门禁、`orchestrator`/`launch_surface` 字段、成本口径拆
  分（quota_cost vs metered_price_estimate）、effort/`model_reasoning_effort` 对账、脚本优先的 Codex 可消费性、
  validator 覆盖跨 provider 词表、验证加 `sync-codex-adapters.py --check`；新增未解决问题 6-9。人类最终批准仍待定。
