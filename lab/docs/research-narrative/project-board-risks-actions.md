# 迁移自 ELF-template-case：risks / actions / decisions board

新模板没有为 risk/action board 单独设 YAML 槽位（`lab/research/*.yaml` 只覆盖
claims/evidence/experiment-ledger/regression-matrix/release-gates）。这是一条
迁移发现：见 `lab/docs/audits/` 下本轮功能测试报告。以下原样保留旧
`memory/boards/{risks,actions,decisions,human-gates}.yaml` 的事实内容，供追溯。

`decisions.yaml` 与 `human-gates.yaml` 在旧仓库里为空（`decisions: []` /
`human_gates: []`），未迁移具体内容。

## Risks

- **RSK-ELF-TPU-ASSUMPTION** — ELF main 分支面向 TPU/JAX，而 EPFL smoke 只做轻量检查。
  status: open, severity: medium。
  mitigation: 只记录 clone/read/py_compile 证据，未经批准环境计划前不声称模型执行或指标复现。
  关联 claim: `claim-elf-source-identity`。

- **RSK-ELF-PYTORCH-DEPS** — ELF `pytorch_elf` 运行时需要持久化 PyTorch 依赖环境。
  status: mitigated, severity: medium。
  mitigation: 用 EPFL PVC 持久化 `.venv-pytorch` + 持久 uv cache。已完成的 smoke 仅支持
  依赖导入与合成 CPU 前向，仍不支持 checkpoint 加载、数据集执行、GPU 训练或指标复现。
  关联 claim: `claim-elf-pytorch-smoke`, `claim-elf-pytorch-runtime-smoke`。

## Actions

- **ACT-ELF-CASE-BASELINE** — done (2026-07-08)：记录 ELF 案例 baseline（源 provenance、
  EPFL 远端路径、smoke 命令、validate 输出、模板摩擦）。
- **ACT-ELF-DEPENDENCY-SMOKE** — blocked：ELF main 依赖面向 JAX/TPU 且偏重，需先有环境决策才装依赖。
- **ACT-ELF-PYTORCH-BRANCH-SMOKE** — done (2026-07-08)：切到 `pytorch_elf` 并跑非破坏性检查。
- **ACT-ELF-PYTORCH-RUNTIME-SMOKE** — done (2026-07-08)：建持久 PyTorch 环境并跑依赖导入 smoke。
