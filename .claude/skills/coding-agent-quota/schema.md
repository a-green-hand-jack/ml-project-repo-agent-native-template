# Route Decision + Outcome Ledger Schema（v1）

outcome-aware 路由的记录格式。ledger 是 append-only JSONL，两类记录以 `decision_id` 关联。
词表校验依据是**带版本的冻结 catalog**（`fixtures/outcome/model-catalog.v1.json`，
`policy_version: routing-policy-v1`），不是 `read_agent_quota.model_for()`——那是会随
policy 演化的启发式，不当永久 schema 词表。校验实现：`scripts/outcome_ledger.py validate`
与 `scripts/check-outcome-ledger-schema.py`（repo 门禁）。

## 设计不变量

- **provider-neutral**：Claude 生态与 Codex 生态记进同一张表；`effort` 只收 provider
  原生值（Codex 旋钮是 `model_reasoning_effort`，逐次启动可用 `-c model_reasoning_effort=<v>`
  传入），跨生态抽象档由 `routing_tier`（0-4）表达。`model_for()` 的合成值 `xhigh`
  不进 `effort` 字段。
- **生命周期不可混淆**：decision 创建时 outcome 尚不存在——decision 恒为
  `outcome_status: pending` 且不得携带任何结果字段；结果用独立 outcome 记录补写。
- **成本只有 quota 一维**：订阅制下真正稀缺的是窗口/周额度百分比（`quota_cost`）。
  `metered_price_estimate`（$/token 估算）**本版不实现**（保留字段名，写入即校验报错；
  见 plan doc 未解决问题 6 决策）。
- **不读取 credential**：记录来源仅为本地非敏感 usage/outcome 快照。

## decision 记录

| 字段 | 类型 / 枚举 | 说明 |
| --- | --- | --- |
| `record_type` | `"decision"` | 记录类型 |
| `schema_version` | int（当前 `1`） | schema 版本 |
| `decision_id` | string（`d-<hash12>`） | 唯一 ID；launch packet 只嵌此 ID |
| `decided_at` | ISO-8601 UTC | 决策时间 |
| `task_class` | 非空 string | 任务类别（如 `bounded-implementation`） |
| `role` | `impl\|ui\|research\|planning\|audit` | 与 `read_agent_quota.py --role` 同词表 |
| `routing_tier` | int 0-4 | 跨生态抽象档（model-routing-policy tier） |
| `provider` | catalog providers key（`codex\|claude_code`） | 推荐执行 provider |
| `model` | ∈ catalog `providers.<p>.models` | 推荐 model |
| `effort` | ∈ catalog `providers.<p>.effort_vocab` | **provider 原生**值 |
| `policy_version` | == catalog `policy_version` | 生成本建议的 policy 快照版本 |
| `launch_surface` | `claude_subagent\|codex_exec\|codex_rescue\|ccg\|paseo_lane\|main_session` | 谁发起并执行（Codex 侧同口径比较的关键） |
| `quota_snapshot_ref` | `{generated_at, source}` | 关联 quota snapshot 以追溯 |
| `paseo_preference` | `{status: ok\|missing\|unreadable, role_default}` 或 null | `~/.paseo/orchestration-preferences.json` 的角色偏好证据；文件缺失时 status=missing（优雅降级），不阻塞 |
| `degraded` | bool | 是否走了保守回退 |
| `degraded_reason` | string / null | degraded=true 时必填 |
| `baseline_provider` | string | quota-only 基线推荐（可解释性） |
| `signals` | string[] | 决策理由链 |
| `outcome_status` | 恒 `"pending"` | 结果在 outcome 记录里 |

## outcome 记录

| 字段 | 类型 / 枚举 | 说明 |
| --- | --- | --- |
| `record_type` | `"outcome"` | 记录类型 |
| `decision_id` | 必须指向已存在的 decision | 关联键；同一 decision 允许多条（append-only 修正，取 `outcome_observed_at` 最新） |
| `outcome_observed_at` | ISO-8601 UTC，必填 | 观测时间 |
| `outcome_status` | `observed\|unavailable` | `pending` 由「无 outcome 记录」表达，不得写入 |
| `evidence_source` | string | `observed` 必填：结果证据来源（测试命令+退出码、verifier 结论等） |
| `outcome_quality` | `pass\|partial\|fail` | `observed` 必填；首版只用可自动获取的代理信号 |
| `rework_count` | int ≥ 0 | 返工轮数 |
| `failure_reason` | `test_failure\|tooling_error\|scope_misread\|quota_exhausted\|timeout\|escalated\|rework_abandoned\|other` / null | `fail` 时必填 |
| `tokens_in` / `tokens_out` | number ≥ 0 / null | token 用量 |
| `latency_wall_clock_s` | number ≥ 0 / null | wall-clock |
| `actual_provider` / `actual_model` / `actual_effort` | catalog 词表 | **实际生效**的路线（不只是推荐值）；`observed` 必填 |
| `policy_version` | == catalog | `observed` 必填 |
| `quota_cost` | 见下 / null | 订阅额度消耗（估算） |
| `metered_price_estimate` | 保留，**本版不实现** | 写入即校验报错 |

`quota_cost` 对象：`{window, before_used_percent, after_used_percent, delta_percent,
sampled_before_at, sampled_after_at, attribution_confidence: isolated|shared_window|unknown,
is_estimate: bool}`。共享订阅窗口内不能把差值无条件归因单次任务：无法隔离时
`attribution_confidence=shared_window` 且 `is_estimate=true`，不伪装精确单次成本。

## 校验规则（validator 强制）

1. decision 携带任何结果字段 → 拒绝（「未运行却已有结果」）。
2. `observed` 缺 `outcome_observed_at` / `evidence_source` / `outcome_quality` / 实际路线 → 拒绝。
3. outcome 指向未知 `decision_id`、`decision_id` 重复 → 拒绝。
4. provider/model/effort 越出该 `policy_version` catalog 词表 → 拒绝（防漂移为 Claude-only）。
5. sample fixture 必须含 ≥1 条 Codex 生态 decision 记录。
6. required key 缺失 → 拒绝：decision / outcome 各有完整 required-key 清单
   （`DECISION_REQUIRED_KEYS` / `OUTCOME_REQUIRED_KEYS`，key 必须在场，部分值可为
   null）；`schema_version` 必须等于当前版本（1）；`decision_id` 必须匹配
   `d-<id>` 格式；`quota_cost` 若在场必须结构完整（`QUOTA_COST_REQUIRED_KEYS`），
   残缺即拒绝。负向回归：`scripts/check-outcome-ledger-schema.py` 逐个删 key 断言 FAIL。
7. 写入边界：`--ledger` / `--record-ledger` 的**写入**目标 resolve(realpath) 后只允许
   默认 `.outcome-ledger/` 目录内或系统 temp 目录（测试用）；受保护路径
   （`lab/data|runs|models`、`lab/infra/private`、`.env`，对齐 pre_tool_guard）与其他
   任意路径一律拒绝并以非零退出。读取路径不受限（fixtures 可读）。
8. schema-invalid / 损坏 ledger 不参与路由：`outcome_route.py` 遇到 parse/schema
   错误时丢弃全部 ledger 证据，`degraded=true` 回退 quota-only 推荐（缺数据保守
   回退），坏记录绝不进入统计。

## 示例记录（≥3 条，含 Codex 生态路线）

```jsonl
{"record_type":"decision","schema_version":1,"decision_id":"d-fx0003","decided_at":"2026-07-09T14:00:00Z","task_class":"plan-doc-convergence","role":"planning","routing_tier":3,"provider":"codex","model":"gpt-5.6-sol","effort":"medium","policy_version":"routing-policy-v1","launch_surface":"codex_exec","quota_snapshot_ref":{"generated_at":"2026-07-09T14:00:00Z","source":"~/.claude/.search-index/usage.db"},"paseo_preference":{"status":"missing","role_default":"codex/gpt-5.6-sol"},"degraded":false,"degraded_reason":null,"baseline_provider":"codex","signals":["quota-only baseline: codex"],"outcome_status":"pending"}
{"record_type":"outcome","schema_version":1,"decision_id":"d-fx0003","outcome_observed_at":"2026-07-09T15:20:00Z","outcome_status":"observed","evidence_source":"plan doc approved by human review round","outcome_quality":"pass","rework_count":0,"failure_reason":null,"tokens_in":60000,"tokens_out":12000,"latency_wall_clock_s":3100.0,"actual_provider":"codex","actual_model":"gpt-5.6-sol","actual_effort":"medium","policy_version":"routing-policy-v1","quota_cost":{"window":"current","before_used_percent":40.0,"after_used_percent":42.0,"delta_percent":2.0,"sampled_before_at":"2026-07-09T14:00:00Z","sampled_after_at":"2026-07-09T15:20:00Z","attribution_confidence":"shared_window","is_estimate":true}}
{"record_type":"decision","schema_version":1,"decision_id":"d-fx0004","decided_at":"2026-07-10T09:30:00Z","task_class":"bounded-implementation","role":"impl","routing_tier":2,"provider":"claude_code","model":"claude-sonnet-5","effort":"medium","policy_version":"routing-policy-v1","launch_surface":"claude_subagent","quota_snapshot_ref":{"generated_at":"2026-07-10T09:30:00Z","source":"~/.claude/.search-index/usage.db"},"paseo_preference":{"status":"missing","role_default":"codex/gpt-5.5"},"degraded":false,"degraded_reason":null,"baseline_provider":"claude_code","signals":["quota-only baseline: claude_code"],"outcome_status":"pending"}
```

更多样本见 `fixtures/outcome/outcome-ledger.sample.jsonl`（含 pending 生命周期示例
`d-fx0008` 与成功率变体 `outcome-ledger.codex-degraded.jsonl`）。
