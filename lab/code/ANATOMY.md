---
related_files:
  - ../ANATOMY.md
  - src/ANATOMY.md
maintenance: |
  Case branch（case/elf-template-replay）。子目录结构变化时同 commit 更新本文件与 src/ANATOMY.md。
  真实代码落地前不放 file:line 引用。
---

# lab/code/ ANATOMY

## What this is

实现层。承载全部可执行代码，按职责分子目录。本分支迁移自 ELF-template-case（v1
`.harness` 模板案例）的 `code/` 组件：`src/project_code/`、`eval/`、`experiments/`、
`scripts/`、`configs/base.yaml` 均为迁移落地的真实占位实现（尚未 vendor 真正的
`lillian039/ELF` 运行时代码，见下方 `external/`）。

## Composition

Parent: `lab/`（见 `../ANATOMY.md`）
Children:

| 子目录 | 职责 | 独立 anatomy |
| --- | --- | --- |
| `src/` | 模型/数据/训练/评估源码 | `src/ANATOMY.md` |
| `configs/` | 配置文件（`base.yaml` 迁移自旧案例） | README only |
| `scripts/` | 脚本（`download_data.py` 迁移自旧案例） | README only |
| `tests/` | 测试 | README only |
| `experiments/` | 实验入口（`config.py`/`train.py`/`evaluate.py` 迁移自旧案例） | README only |
| `eval/` | 评测/baseline/指标代码，迁移新增子目录，模板未预定义 | README only |
| `external/` | vendored 上游 clone（如 `lillian039/ELF`），gitignore，不进 Git | 无（provenance 见 `../docs/reference/provenance.md`） |

## Connections（意图）

- `experiments/` 与 `scripts/` 调用 `src/` 的模块，读取 `configs/`。
- `eval/` 提供 baseline 对比与指标计算，供 `experiments/evaluate.py` 调用。
- `tests/` 覆盖 `src/`。
- 运行时的路径/存储由 `../infra/` 提供，不在本层硬编码。
- `external/` 是本次迁移新增的第三方案例源存放位置（沿用 ELF-template-case 旧周期的
  `code/external/ELF` 约定）；新模板本身未定义这个槽位，属于一条迁移发现。

## State

本层不持久化运行产物；产物索引在 `../artifacts/`、`../runs/`、`../models/`。
`external/` 下的 vendored clone 不进 Git，仅在 `../docs/reference/provenance.md` 留 provenance。

## Notes

- 具体调用关系与 line-addressed citation 落在 `src/ANATOMY.md`，待真实代码补全。
- `eval/`、`external/` 是本次迁移相对模板原始 5 子目录表新增的两个子目录；已在此表登记，
  但 `scripts/check-same-commit.py` 只按「直接父目录是否有 ANATOMY.md」判定，不会强制这次
  新增触发上层 `lab/ANATOMY.md` 更新——本次仍手动同步，详见迁移测试报告。
