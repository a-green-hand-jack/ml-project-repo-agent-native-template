# PROJECT

> 研究控制根的顶层描述。派生新项目时**第一件事**就是填写本文件。

## 研究对象（一句话）

<这个 project 要回答/验证的核心研究问题是什么？>

## 当前 active family

<当前主攻的实验家族 / 论文 / 方向。多家族并行时列出每个 family 及其边界。>

## Trunk 与协作模式

选择一种（见 `.reference-docs` §6）：

- **单 trunk 模式（pairwise-diffusion 式）**：`issue -> branch off <trunk> -> fresh worktree -> PR -> owner review -> merge back`。
  - trunk 分支：`<例如 main / jieke/dev>`
- **branch-local mainline 模式（DOLoop 式）**：每个任务家族一条 `mainline/<domain>`，短分支回各自 mainline，禁止跨 mainline 泄漏 term/dataset/artifact/claim。

## Remote / worktree 策略

- 远端：`<git remote，默认不推送，push 需 human gate>`
- worktree 约定：`Non-trivial edit = fresh worktree`；一个 worktree = 一个 branch purpose = 一个 issue/PR。
- worktree 状态记录：`memory/worktree-status.md` + `memory/branches/<slug>.md`。

## 计算与存储

- GPU / 集群：`<本地 / vast.ai / 集群，见 lab/infra/launch/>`
- 大 bytes（data / checkpoint / runs / wandb）不进 Git，只留 index，见 `lab/infra/storage/`。

## 是否包含「内层 release agent」

- [ ] 否：这是普通 ML 研究 repo。忽略 `.agent/release-agent-boundary.md`。
- [ ] 是：本 repo 要交付一个 agent 产品。严格区分外层开发 harness 与内层 release agent，见 `.agent/release-agent-boundary.md`。

## 关联文档

- 决策台账：`DECISIONS.md` -> `human/decisions/`
- 结构地图：`ANATOMY.md`
- 当前状态：`memory/current-status.md`
