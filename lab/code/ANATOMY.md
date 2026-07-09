---
related_files:
  - ../ANATOMY.md
  - src/ANATOMY.md
maintenance: |
  Template scaffold. 子目录结构变化时同 commit 更新本文件与 src/ANATOMY.md。
  真实代码落地前不放 file:line 引用。
---

# lab/code/ ANATOMY

## What this is

实现层。承载全部可执行代码，按职责分五个子目录；case branch 可额外挂载
`imported/<slug>/`，保存 adoption replay 的原 repo 内容。

## Composition

Parent: `lab/`（见 `../ANATOMY.md`）
Children:

| 子目录 | 职责 | 独立 anatomy |
| --- | --- | --- |
| `src/` | 模型/数据/训练/评估源码 | `src/ANATOMY.md` |
| `configs/` | 配置文件 | README only |
| `scripts/` | 脚本 | README only |
| `tests/` | 测试 | README only |
| `experiments/` | 实验入口 | README only |
| `imported/agent-r1/` | AgentR1/Agent-R1 adoption replay 的原 repo root（保守 imported-unit 策略） | README/report only |

## Connections（意图）

- `experiments/` 与 `scripts/` 调用 `src/` 的模块，读取 `configs/`。
- `tests/` 覆盖 `src/`。
- `imported/agent-r1/` 是迁移 case 内容，不由模板源码直接 import；迁移证据见
  `../docs/audits/template-adoption-report.md` 与
  `../docs/audits/agent-r1-adoption-replay-report.md`。
- 运行时的路径/存储由 `../infra/` 提供，不在本层硬编码。

## State

本层不持久化运行产物；产物索引在 `../artifacts/`、`../runs/`、`../models/`。

## Notes

- 具体调用关系与 line-addressed citation 落在 `src/ANATOMY.md`，待真实代码补全。
