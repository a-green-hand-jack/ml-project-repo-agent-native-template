# lab/infra/launch/ — 启动命令与实验控制面

存放**可复现的启动命令**与实验运行控制面（issue #16）。

- **启动/kill/restart 是人类闸门**：命令由人审阅后执行（或对已批准的单条 resume 提案
  半自动执行），agent 不自动运行。机器层见 `registry.yaml` 的 `gated_prefixes` +
  共享 hook 地板 + 两侧 permission 规则（详见 `.agent/human-gates.md` launch 门禁一节）。
- 命令应可复现：固定配置、数据版本、环境。
- 产出 bytes 不进 Git；index/summary 见 `../../runs/`、`../../models/`、`../../artifacts/`。

## 控制面文件

| 文件 | 角色 |
| --- | --- |
| `registry.yaml` | launch adapter 描述（local-fake / slurm / runai）+ 门禁命令前缀的单一真源 |
| `expctl.py` | 控制面 CLI：`detect`（adapter 可用性/降级）/ `plan`（命令草案，不执行）/ `watch`（一次性有界快照检查，只读）/ `apply-recovery`（执行 ledger 里已获 human 批准的单条恢复动作，批准缺失/不匹配即拒绝） |
| `fake_job.py` | local-fake 后端：本地小进程模拟 job（零算力），供 smoke 与恢复演练；支持注入 NaN/stall 异常 |
| `launch_gate.py` | 门禁判定模块：被共享 `pre_tool_guard.py` hook 加载，按 registry 前缀拦截未放行的 launch 类命令（`CLAUDE_ALLOW_LAUNCH=1` / `CODEX_ALLOW_LAUNCH=1` 单次放行） |

远端 scheduler（Slurm/RunAI）无硬依赖：CLI 不存在时 `expctl.py` 清晰降级 local-only。
设计参考了 [Zhangyanbo/hpc-skills](https://github.com/Zhangyanbo/hpc-skills) 的 preflight
探测与「集群 quirks 集中一处」模式（评估结论：参考自研，见 plans/20260712 plan doc）。

每个脚本自带 `--self-test`（fixture 内嵌，全部 fake/local，不触达真实算力）。
