# lab/code/experiments/ — 实验入口

每个实验的入口与专属代码。调用 `../src/` 的模块、读取 `../configs/`。

- 实验产出的 bytes（checkpoint、输出）不进 Git；其索引/summary 见 `../../runs/`、`../../models/`、`../../artifacts/`。
- 实验结论登记到 `../../research/experiment-ledger.yaml`。
- 实际启动由人类经 `../../infra/launch/` 执行。

## 定义 vs 产物（冻结纪律）

这里放的是**实验定义文件**（入口、config、prompt、schema、adapter/strategy/runner）——属两阶段协议（`../../../plans/README.md`）里的**冻结面**。运行产物在 `../../runs/`。评分 run（执行观测阶段）**不得**现场修改这些定义文件。运行中若发现定义缺陷：**停止 + 建 child issue** 回准备阶段重新冻结，而不是改一改接着记分。
