---
related_files:
  - ../ANATOMY.md
  - ../artifacts/ANATOMY.md
maintenance: |
  Template scaffold. YAML schema/字段/证据链关系变化时同 commit 更新本文件。
  YAML 本体由治理流程维护，本文件只描述其角色与关系。
---

# lab/research/ ANATOMY

## What this is

研究事实层。以一组 YAML 承载项目的结构化真相：主张、证据、台账、回归、发布闸门。是「能不能这样说 / 能不能发布」的单一裁决面。当前为 template scaffold。

## Components（YAML，由治理流程创建）

| 文件 | 角色 |
| --- | --- |
| `claims.yaml` | 能力级 / 论文级主张 |
| `evidence.yaml` | 分层证据：`log < metric < table < figure < paper claim` |
| `experiment-ledger.yaml` | 实验台账 |
| `regression-matrix.yaml` | 关键指标回归矩阵 |
| `release-gates.yaml` | 发布/交付闸门 |

## Connections（意图）

- `claims.yaml` 的每条主张指向 `evidence.yaml` 的证据条目；claim 强度 ≤ 最强证据。
- `evidence.yaml` 引用 `../artifacts/` 的 index（table/figure/result）与 `../runs/` 的 summary；
  `run_id` 必须指向 `experiment-ledger.yaml` 中已闭环 run（`status: done` + `run_summary`）。
- `release-gates.yaml` 汇总 claims + regression-matrix，产出可否交付的判定。
- deliverables 正文经 claim marker（`<!-- claim: id=... -->`）反向引用 `claims.yaml` /
  `evidence.yaml`，构成 run→artifact→evidence→claim→deliverable 全链。

## State

| 路径 | 写入者 | 含义 |
| --- | --- | --- |
| `*.yaml` | agent + human | 结构化研究事实，validate-governance 校验一致性 |

## Notes

- overclaim = claim 强度超出其 evidence，属违规；`validate-governance.py` 会拦截（引用可解析 + claim 强度 ≤ 最强证据）。
- `release-gates.yaml` / `regression-matrix.yaml` 枚举字段与 claim 引用一致性，已由
  `validate-governance.py` 强制校验（占位默认状态天然通过，仅在 gate/regression 离开占位
  状态后才校验 claim 引用是否真实存在）。
- provenance 链（引用完整性 / run 闭环 / checksum / claim marker / gate 结构化检查）由
  子检查 `scripts/check-provenance-chain.py` 校验；本目录 5 个 YAML 均带 `schema_version`
  （整数，字段结构不兼容变更时递增）。`release-gates.yaml` 的 `structured_checks` 只
  结构化可机械验证的 kind（artifact-exists / checksum-verified / run-closed /
  regression-status / evidence-grade-min），结果仅建议信号，`gate_status` 翻转仍是
  human 动作；artifact-exists 查 location 文件/manifest 记录真实存在，
  checksum-verified 只认真算 sha256 比对通过（waived ≠ verified）；passed gate 的
  placeholder/unknown 一律 fail-closed。claim→evidence 还核对 `supports_claim` 归属，
  只有完整且归属匹配的 evidence 才贡献强度；evidence 引用的 artifact
  不得是 archived/unknown，dataset split 必须已登记；deliverable marker 必须覆盖索引该行全部 claim。
  字段与枚举定义见
  `.agent/artifact-policy.md`。
- 校验：`python scripts/validate-governance.py`。
