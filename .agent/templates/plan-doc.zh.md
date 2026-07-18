# <topic> 交互式计划

Status: draft · <YYYY-MM-DD> · <ref：approval 证据/初稿说明>

> 复制到 `plans/<YYYYMMDD>-<topic>.zh.md`。这是 human 与 Claude Code 的协商界面：
> Claude 写初稿 → human 在文件里批注 → Claude 读 diff、收敛计划 → 每次采纳的修订做一个小 commit。
> 实现只在 scope / forbidden paths / verification 清楚后开始。
> 状态锚点（上面一行）+ `memory/doc-lifecycle.yaml` 注册表登记，语义见 `plans/ANATOMY.md`；
> 起草即登记，human 批准后才可转 approved。

## 当前目标

## 非目标

## Branch / worktree

## Linked issue / PR

- parent issue：<拆分自哪个 parent；无则填 none>
- child issue / phase：<本 plan 对应的 child issue 与阶段：prepare/freeze | execute/observe | 单阶段>

## Allowed paths

## Forbidden paths

## 实验冻结面（仅实验类 plan；非实验填 n/a）
- frozen commit：<freeze commit hash；未冻结填 pending>
- allowed writes：<执行阶段允许写入的路径，如 trace/result/state/log>
- forbidden writes：<冻结面：config/prompt/schema/adapter/strategy/runner/产品源码>
- on drift：需改冻结面时——把 run 标 `calibration/invalid`、停止评分、转 child issue，不现场修补后继续

## 任务树
- [ ] Parent task
- [ ] Child task A
- [ ] Child task B

## Human 批注区

## 当前决策

## 未解决问题

## 验证标准

## 下一步

## Plan revision log
- <YYYY-MM-DD> 初稿
