# Routing Benchmark Card 模板

路由 benchmark 不是「换着模型跑跑看」。与 `experiment-card.md` 同构：开跑前填写并**冻结**——
模型池、路由 policy 版本、预算上限、fixture 版本一次性锁定，运行期间不因中途 quota 变化切换
（沿用 `.agent/model-routing-policy.md` transfer experiment 的冻结先例）。本版只有 quota + outcome
两维，无 $ 价格维度。

实际填写的 card 存 `.claude/skills/coding-agent-quota/benchmarks/<freeze-id>.md`，
并在 `.claude/skills/coding-agent-quota/benchmarks/README.md` 的索引表登记一行。

```markdown
# Routing Benchmark Card

## Question
这次路由比较要回答什么？（如：role=impl tier=2 下 codex vs claude_code 谁更值）

## Hypothesis

## Freeze（运行期间锁定，不得中途切换）
- freeze_id:
- frozen_at: <ISO-8601 UTC>
- policy_version: <catalog policy_version，如 routing-policy-v1>
- catalog hash: <sha256 of fixtures/outcome/model-catalog.v*.json>
- model pool: <逐条 provider/model/native effort>
- budget cap: <quota 预算上限，如「codex weekly burn <= 10%」；订阅额度口径，非 $>
- fixture version: <quota snapshot + outcome ledger fixture 路径与 commit>
- code commit:

## Frozen fields（本次比较涉及的 schema 字段清单）
- <如 outcome_quality / rework_count / quota_cost.delta_percent / latency_wall_clock_s>

## Baseline / comparison
<quota-only baseline vs outcome-aware，或路线 A vs B>

## Success metric
<按维度分报，不合并单一分数：outcome / quota_cost / tokens / wall-clock / 昂贵路线占比>

## Failure signals
- degraded fallback 频发（数据缺失/过期）
- 样本量不足（min_samples 未达标）
- 词表漂移（validator 报 catalog 越界）
- 中途切换 provider/model（冻结被破坏）

## Artifact paths
<replay 输出 JSON、ledger 切片、decision_id 列表>
```
