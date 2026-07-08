# Session Tree

> 记录当前 session 的父/子拓扑，让并行/派生工作可被追踪与合并。
> 与 `current-status.md` 配合：status 记「现在做什么」，tree 记「有哪些并行分支、怎么合」。

## Parent objective

（顶层目标：整个 session 树在追求什么。）

## Current phase

（当前处于 `phase-dashboard.yaml` 的哪个 phase id，以及本阶段焦点。）

## Children

| id | purpose | branch/worktree | plan doc | status | next prompt |
| --- | --- | --- | --- | --- | --- |
|  |  |  | `plans/<YYYYMMDD>-<slug>.zh.md` | planned/active/blocked/done |  |

## Merge / review order

（子 session 完成后合并/评审的顺序与依赖。谁先合、谁挡谁。）

1.

## Global forbidden paths

（所有子 session 都禁止改动的路径。任何 agent 越界前必须先取得 human gate。）

-

## Open risks

（跨分支的风险：冲突、竞态、共享文件、易漂移的契约。）

-
