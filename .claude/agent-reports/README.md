# .claude/agent-reports/

subagent 把长报告写到这里（`<task>.md`），主线程只接摘要——避免大段日志污染主上下文。

- `feature-worker` 写 changed files / tests / risks / merge notes。
- 其他 subagent 按需落报告。
- 这些是**过程产物**，非研究事实；研究事实进 `lab/research/` 与 `lab/artifacts/`。可定期归档。
