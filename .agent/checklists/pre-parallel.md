# 并行前清单

并行前先问（隔离先于并行）：

```
- 这些任务是否真的独立？
- 每个 agent 拥有什么文件/模块？
- 哪些路径绝对不能碰？
- 谁负责 merge 和最终验证？
```

不要并行：需求不清、文件边界不清、共享同一核心模块、没时间审查 merge、只是「感觉很强」。

适合并行：A 读论文 / B 读 repo；A 实现 dataset / B 写测试；边界清楚的 backend/frontend；A 跑 baseline / B 整理 table；A 实现 / B 在 fresh context review。

真正能并行的前提：branch base、owned/forbidden paths、issue/PR target、anatomy impact、evidence/release-gate impact、validator command、merge order 都提前分清。

并行开工前把边界变成机器可强制（见 `.agent/multi-agent-control-plane.md`）：

```
- 每个 agent：python scripts/agent-state.py register "<name>" --task "..." --owned <paths> --forbidden <paths>
- 派发方：python scripts/check-agent-conflicts.py scan   # owned_paths 无重叠才开工
- 之后写入其他活跃 agent 的 owned path 会被 pre_tool_guard 写入前拦截（AGENT_CONFLICT_SKIP=1 显式绕过）
```
