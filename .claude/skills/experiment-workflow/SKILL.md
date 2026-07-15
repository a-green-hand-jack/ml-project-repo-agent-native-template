---
name: experiment-workflow
description: 当要跑一个实验或复现一篇 paper 时，用来写 experiment card、登记状态机 ledger、准备（但不擅自运行）launch 命令、只读监控与 alert、校验并交接 human 恢复提案、写 run summary 并把达标结果收进 evidence。
---

# experiment-workflow

实验的全生命周期：先立卡登记（状态机 ledger），human 批准进 approved，再准备 launch 命令交人类运行，用只读 watcher 看 bounded 快照，异常走 alert → fail-closed 校验 → human 在 agent 外恢复，跑完写 run summary，达到证据门槛才进 evidence / 论文。paper 复现同样适用。

## 适用边界

适用：训练/评测实验、消融、paper reproduction。
不适用：无需计算的分析；擅自启动长任务（launch 是 human gate，见 `.agent/human-gates.md` launch 门禁一节）。

## 输入 / 输出 artifact

- 输入：实验假设 / 待复现的 claim。
- 输出：
  - experiment card（`.agent/templates/experiment-card.md`）
  - `lab/research/experiment-ledger.yaml` 登记条目（含 status/status_history/alerts）
  - run summary（`.agent/templates/run-summary.md`）
  - 达标后进 `evidence/` 或论文素材。

## 需要读取的 ledger

- `lab/research/experiment-ledger.yaml`（现有实验、避免重复；状态机与字段约定见文件头注释）。
- `lab/infra/launch/registry.yaml`（launch adapter 与门禁前缀的单一真源）。
- `.agent/human-gates.md`（launch/resume 审批点）。
- `.agent/artifact-policy.md`（产出如何登记，衔接 artifact-indexing）。

## 允许修改的路径

- `lab/research/experiment-ledger.yaml`
- experiment card / run summary 文件
- `evidence/`（仅达标后）
- **不得擅自执行 launch/kill/restart 命令**（registry gated_prefixes 三层门禁拦截）。

## 步骤

1. 写 experiment card：假设、变量、成功判据、预算（approved 前必填字段见模板）。
2. 登记 `lab/research/experiment-ledger.yaml`（status: planned，status_history 起步）；
   跑 `python scripts/validate-experiment-state.py` 确认字段齐备。
3. 三层目标（对 paper 复现同样适用）：读懂 claim → 找到对应实现 → 跑最小 smoke 验证链路。
4. human 审阅后进 approved（human 落 approved_by/approved_at）。用
   `python lab/infra/launch/expctl.py plan --action launch --run-id <id>` 生成命令草案，
   交人类（human gate）启动；启动后状态转 running。
5. 只读监控：用 experiment-monitor 跑一次性快照
   `python lab/infra/launch/expctl.py watch --run-id <id> --workdir <dir>`（bounded，不常驻），
   不改运行中的 job。
6. 异常路径：watcher 的结构化 alerts 由 experiment-orchestrator 并入 ledger `alerts` 字段；
   approved_by/approved_at/approved_action 只作审计。orchestrator 用
   `expctl.py validate-recovery` 只读校验同 run/workdir 的 fake/local 提案，再交 human
   在 agent hook 外亲自执行；repo-local provenance 不受信，actual apply-recovery fail-closed。
7. 跑完写 run summary（`.agent/templates/run-summary.md`）；状态转 done/failed；
   产出物交 artifact-indexing 登记（done 的闭环由 validate-experiment-state 校验）。
8. 达到证据门槛才收进 `evidence/` 或论文；未达标只记结论不夸大。

## 验证命令

```
python scripts/validate-experiment-state.py
python scripts/validate-governance.py
```

## 失败时的 handoff

- 实验失败/结果异常：在 run summary 如实记录，按 `.agent/templates/handoff.md` 升级。
- smoke 都跑不通（复现受阻）：停在第三层，记录卡点，不伪造结果。
