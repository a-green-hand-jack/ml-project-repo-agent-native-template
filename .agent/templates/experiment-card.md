# Experiment Card 模板

实验不是「跑一下看看」。开跑前填写；存 `lab/code/experiments/<id>.md` 并登记 `lab/research/experiment-ledger.yaml`。

状态机（`scripts/validate-experiment-state.py` 机器强制）：`planned → approved → running → done|failed`，`done|failed → superseded`。进入 `approved` 前，Commit / Config / Data split / Expected runtime / Success metric 必须齐备（非占位），并由 human 落 `approved_by` / `approved_at`；每次状态转换在 ledger 的 `status_history` 追加一条。

```markdown
# Experiment Card

## Question
What claim does this test?

## Hypothesis

## Status
planned | approved | running | done | failed | superseded
（与 ledger status/status_history 保持一致）

## Approval
approved_by: / approved_at:（human 批准进入 approved 时填写）

## Code commit

## Config

## Data split

## Baseline / comparison

## Expected runtime
（budget：预计时长或算力预算——approved 前必填）

## Success metric

## Failure signals
- OOM
- NaN
- metric stall
- missing checkpoint
- data mismatch

## Launch
（launch 命令草案用 `python lab/infra/launch/expctl.py plan --action launch --run-id <id>` 生成；
执行是 human gate，见 `.agent/human-gates.md`）

## Artifact paths
```
