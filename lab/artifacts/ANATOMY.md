---
related_files:
  - ../ANATOMY.md
  - ../research/ANATOMY.md
maintenance: |
  Template scaffold. index schema/字段变化时同 commit 更新本文件。
  index YAML 由治理流程维护，此处只描述角色与引用关系。
---

# lab/artifacts/ ANATOMY

## What this is

产物索引层。把「产物在哪、是什么、由哪次 run 产生」结构化为一组 index YAML。**只存 index，bytes 在外部存储**。当前为 template scaffold。

## Components（index YAML）

| 文件 | 索引 |
| --- | --- |
| `result-index.yaml` | 结果 |
| `model-index.yaml` | 模型 checkpoint |
| `trace-index.yaml` | 轨迹 |
| `table-index.yaml` | 表 |
| `figure-index.yaml` | 图 |

## Connections（意图）

- 索引条目由 `../runs/`、`../models/` 的产出登记而来（bytes 不进 Git）。
- `../research/evidence.yaml` 引用这些 index 作为证据（table/figure/result 层）。
- 条目 `run_id` 指向 `../research/experiment-ledger.yaml` 的已闭环 run；
  `model-index` 的 `checkpoint_ref` 指向 `../models/checkpoint-index.yaml`。

## State

| 路径 | 写入者 | 含义 |
| --- | --- | --- |
| `*-index.yaml` | agent + human | 产物指针（`location` + checksum + 来源三元组），非 bytes |

## Notes

- 共同最小 schema（`schema_version` / `location` / `how_to_inspect` /
  `commit`+`config`+`run_id` / `status` / checksum 三件套）见 `.agent/artifact-policy.md`。
  三元组全部 7 类统一必填；确无 run 来源（如 human-cc/agent trace）须显式豁免
  （`provenance_unavailable_reason` 固定枚举 + 非占位理由），不允许静默留空。
- 悬空索引 / 未闭环 run / checksum 不匹配由 `scripts/check-provenance-chain.py` 拦截
  （由 `validate-governance.py` 拉起；checksum 统一 sha256，无法校验需固定枚举 reason +
  非占位人工理由）。
- 校验：`python scripts/validate-governance.py`。
