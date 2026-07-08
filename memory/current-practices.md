# current-practices.md — 采用中的 Claude Code recipe

当前**已采用**的 Claude Code 工作流（recipe）索引。每条 recipe 的完整内容存在 `lab/recipes/claude-code/`，本文件只做索引与状态跟踪。

采用 / 失效流程见 `.agent/claude-code-recipe-policy.md`；失效的 recipe 记到 `deprecated-practices.md`。

| id | title | status | evidence | expires |
| --- | --- | --- | --- | --- |
| _(空)_ |  |  |  |  |

## 说明

- **id**：与 `lab/recipes/claude-code/<id>.md` 对应。
- **status**：`trial`（试用中）/ `adopted`（已采用）/ `review`（待复审）。
- **evidence**：为什么采用——指向 `human/reviews/recipes/` 的 review 或实测证据路径。
- **expires**：复审到期日；到期未复审的 recipe 应降级或移入 `deprecated-practices.md`。
- 新 recipe 必须先经 recipe review（小 diff，见 `.agent/claude-code-recipe-policy.md`）才能进本表。
