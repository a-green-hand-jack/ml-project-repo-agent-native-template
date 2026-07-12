# plans/

交互式中文 plan doc 的家。这是 human 与 Claude Code 的协商界面（比纯聊天 plan 更可恢复、可 review）。

- 命名：`<YYYYMMDD>-<topic>.zh.md`
- 模板：`.agent/templates/plan-doc.zh.md`
- 由 `interactive-plan-writer` subagent / `interactive-plan-doc` skill 维护。

操作流：Claude 写初稿 → human 在文件里批注 → Claude 读 git diff、收敛计划 → 每次采纳的修订做一个小 commit（若项目要求可追溯）。实现只在 scope / forbidden paths / verification 清楚后开始。

plan doc 是当前 session 的锚点：防止 Claude 漂移到额外动作，也防止 human 只凭记忆追踪「刚才到底决定了什么」。

## 当前论文定位与投稿计划

- 唯一当前真源：`plans/20260711-paper-positioning-v5.zh.md`。
- 旧版定位草稿与替代投稿 outline 不保留在当前 tree；需要审计演进时使用 Git 历史或 review 中的固定 revision 链接。
- 后续直接修订这一个文件，不再并行新增 v6、v7 等版本文件；版本演进由 Git 记录。
