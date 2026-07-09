# lab/code/ — 实现层

一切**可执行代码**都在这里：源码、配置、脚本、测试、实验入口。想改模型、写训练/评估逻辑、加一个实验，就来这层。

## 子目录

| 目录 | 是什么 |
| --- | --- |
| `src/` | 源码：模型 / 数据 / 训练 / 评估等模块 |
| `configs/` | 配置文件（超参、数据、运行配置） |
| `scripts/` | 一次性 / 运维 / 数据处理脚本 |
| `tests/` | 单元与集成测试 |
| `experiments/` | 实验入口与实验专属代码 |
| `eval/` | 评测 / baseline / 指标代码 |
| `external/` | vendored 第三方源码（如上游 clone）；**gitignore，不进 Git** |

## 常见入口

- 核心逻辑改动在 `src/`；对应结构见 `src/ANATOMY.md`。
- 新实验从 `experiments/` 起步，配置放 `configs/`。
- 评测/baseline 代码放 `eval/`；第三方 vendored 代码放 `external/`（不进 Git，provenance 见 `../docs/reference/provenance.md`）。
- 提交前跑 `tests/`。
