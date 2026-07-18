# lab/runs/ — 运行记录

单次运行的记录与 summary。

- 运行的原始输出 **bytes 不进 Git**（受根 `.gitignore` 覆盖，含 wandb 等）：只保留 summary。
- 结果/轨迹的完整索引见 `../artifacts/`（`result-index.yaml`、`trace-index.yaml`）。
- 实验结论登记到 `../research/experiment-ledger.yaml`。

## 定义 vs 产物（冻结纪律）

这里放的是**运行产物**（单次 run 的记录 / summary），是两阶段协议（`../../plans/README.md`）里执行观测阶段允许写入的东西；实验**定义文件**在 `../code/experiments/`（冻结面）。评分 run 途中发现定义缺陷时，正确处理是**停止 + 建 child issue**、把该 run 标 `calibration/invalid`，而非现场修补定义后继续评分。
