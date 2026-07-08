# .claude/ — Claude Code 入口

薄路由。

- 需要隔离/并行/限工具 → 看 `agents/`（先经 `.agent/model-routing-policy.md` 选 tier）。
- 反复出现的流程 → 看 `skills/`。
- 权限与 lifecycle 约束 → `settings.json` + `hooks/`。
- subagent 长报告写 `agent-reports/`，主线程只接摘要。

不要用 user 全局能力承载本项目行为。
