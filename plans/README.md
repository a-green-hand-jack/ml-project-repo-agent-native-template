# plans/

交互式中文 plan doc 的家。这是 human 与 Claude Code 的协商界面（比纯聊天 plan 更可恢复、可 review）。

- 命名：`<YYYYMMDD>-<topic>.zh.md`
- 模板：`.agent/templates/plan-doc.zh.md`
- 由 `interactive-plan-writer` subagent / `interactive-plan-doc` skill 维护。

操作流：Claude 写初稿 → human 在文件里批注 → Claude 读 git diff、收敛计划 → 每次采纳的修订做一个小 commit（若项目要求可追溯）。实现只在 scope / forbidden paths / verification 清楚后开始。

plan doc 是当前 session 的锚点：防止 Claude 漂移到额外动作，也防止 human 只凭记忆追踪「刚才到底决定了什么」。

## 两阶段实验协议（prepare/freeze vs execute/observe）

实验类 plan 把「准备冻结」与「执行观测」硬隔离，别边改边评分。

- **prepare / freeze**：收敛实验定义（config / prompt / schema / adapter / strategy / runner），然后打一个 **freeze commit**。freeze commit 必须记录：
  - **允许写入路径**（trace / result / state / log 等运行产物）；
  - **禁止写入路径**（冻结面：定义文件与产品源码）；
  - config / prompt / schema 的 **hash**；
  - **停止条件**。
- **execute / observe**：只运行、读取、写允许路径、观测。**不得修改冻结面**。一旦需要改 schema / prompt / adapter / strategy / runner，说明冻结面有缺陷：把当前 run 标为 `calibration/invalid`、**停止评分**、转入 child issue 回到准备阶段，而不是现场改完继续记分。
