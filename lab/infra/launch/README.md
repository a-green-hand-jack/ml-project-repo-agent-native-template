# lab/infra/launch/ — 启动命令与实验控制面

存放**可复现的启动命令**与实验运行控制面（issue #16）。

- **启动/kill/restart 是人类闸门**：命令由 human 在 agent hook 外亲自审阅并执行；
  caller-set env 与 ledger 字段都不能放行，agent 不自动运行。机器层见 `registry.yaml` 的
  `gated_prefixes` + 共享 hook 地板 + 两侧 permission 规则（详见 `.agent/human-gates.md`）。
- 命令应可复现：固定配置、数据版本、环境。
- 产出 bytes 不进 Git；index/summary 见 `../../runs/`、`../../models/`、`../../artifacts/`。

## 控制面文件

| 文件 | 角色 |
| --- | --- |
| `registry.yaml` | launch adapter 描述（local-fake / slurm / runai）+ 门禁命令前缀的单一真源 |
| `expctl.py` | 控制面 CLI：`detect`（adapter 可用性/降级）/ `plan`（命令草案，不执行）/ `watch`（一次性有界快照检查，只读）/ `validate-recovery`（只读校验 ledger 提案）；`apply-recovery` 因缺可信 provenance/原子 consumer 始终 fail-closed |
| `fake_job.py` | local-fake 后端：仅允许字面 `/tmp/.../<run-id>` workdir；status/受信 worker argv 绑定同一 run，control lock 串行控制动作，pidfd 固定 signal 目标；支持 NaN/stall fixture |
| `launch_gate.py` | 门禁判定模块：被共享 `pre_tool_guard.py` hook 加载；registered launch 命中永拒，路径别名/`python -m`/`_worker` 同样覆盖，env split/shell eval/`python -c` 动态面整体 fail-closed，caller-set env 不放行 |

门禁不是通用进程 sandbox：它只对 registry 已登记的启动入口、已知 wrapper/路径/模块别名
和无法静态证明安全的动态执行面 fail-closed；普通只读命令、测试与
`expctl.py validate-recovery` 仍可直接运行。

远端 scheduler（Slurm/RunAI）无硬依赖：CLI 不存在时 `expctl.py` 清晰降级 local-only。
设计参考了 [Zhangyanbo/hpc-skills](https://github.com/Zhangyanbo/hpc-skills) 的 preflight
探测与「集群 quirks 集中一处」模式（评估结论：参考自研，见 plans/20260712 plan doc）。

每个脚本自带 `--self-test`（fixture 内嵌，全部 fake/local，不触达真实算力）。
