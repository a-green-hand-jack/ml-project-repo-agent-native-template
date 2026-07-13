---
related_files:
  - ../ANATOMY.md
  - checkpoint-index.yaml
  - ../artifacts/ANATOMY.md
maintenance: |
  Template scaffold. checkpoint-index schema/字段变化时同 commit 更新本文件。
  checkpoint bytes 永不进 Git，本文件只描述索引角色与引用关系。
---

# lab/models/ ANATOMY

## What this is

checkpoint 索引层。checkpoint bytes 永不进 Git（根 `.gitignore` 覆盖），
`checkpoint-index.yaml` 是其唯一逻辑真相来源。当前为 template scaffold。

## Components

| 文件 | 角色 |
| --- | --- |
| `checkpoint-index.yaml` | checkpoint 逻辑索引（`location` + 来源三元组 + checksum） |

## Connections（意图）

- `../artifacts/model-index.yaml` 的 `checkpoint_ref` 指向这里的条目 id（`ckpt-*`）。
- 条目 `run_id` 指向 `../research/experiment-ledger.yaml` 的已闭环 run。
- `../research/evidence.yaml` 的 `checkpoint` 字段按 id 引用这里的条目。

## State

| 路径 | 写入者 | 含义 |
| --- | --- | --- |
| `checkpoint-index.yaml` | agent + human | checkpoint 指针与校验信息，非 bytes |

## Notes

- 共同 provenance 字段（`schema_version` / checksum 三件套，统一 sha256）见
  `.agent/artifact-policy.md`；由 `scripts/check-provenance-chain.py` 校验。
- 删除/移动 checkpoint bytes 走 human gate；agent 只写 `archive_after` 归档提案。
- 校验：`python scripts/validate-governance.py`。
