# PROJECT

> 研究控制根的顶层描述。派生新项目时**第一件事**就是填写本文件。

## 研究对象（一句话）

这不是一个真正的研究项目，而是 `ml-project-repo-agent-native-template` 自身的功能测试
case：把 `ELF-template-case`（旧 `.harness`/`research-project-template` 世代的案例仓库，
真实案例源是公开的 `lillian039/ELF` PyTorch/JAX 训练项目）迁移进本模板的结构，然后逐项
验证 validators / hooks / skills / subagents / ANATOMY 防漂移是否如预期工作。

## 当前 active family

`case/elf-template-replay` —— 单一 family：模板功能压测 + ELF 案例迁移与 CPU-only smoke 复测。

## Trunk 与协作模式

- **单 trunk 模式**：本 case 是 `ml-project-repo-agent-native-template` 主仓的一个 worktree 分支
  （`worktree-case+elf-template-replay`，位于 `.claude/worktrees/case+elf-template-replay/`），
  from `main`。不打算合回 `main`——它是一个用完即弃/长期保留的 case 分支，供人类 review diff。
  - trunk 分支：`main`（模板自身）

## Remote / worktree 策略

- 远端：`git@github.com:a-green-hand-jack/ml-project-repo-agent-native-template.git`；本轮测试全程本地，push 与否由 human 事后决定。
- 本 case 本身就是一个 fresh worktree；不再嵌套新建 worktree。
- 旧案例源仓库：`~/Projects/ELF-template-case`（clone 自 GitHub，只读参考，未改动）。

## 计算与存储

- 本机（Linux，CPU only，无 GPU / 无 EPFL 集群访问）：`lab/infra/launch/envs/local.yaml`。
  `lab/infra/launch/envs/cluster.yaml.example` 是旧周期 EPFL 记录，仅供参考，本机不可执行。
- 大 bytes（data / checkpoint / runs / wandb）不进 Git，只留 index；vendored 的 `lillian039/ELF`
  clone 放 `lab/code/external/`（gitignore）。

## 是否包含「内层 release agent」

- [ ] 否：这是普通 ML 研究 repo。忽略 `.agent/release-agent-boundary.md`。
- [ ] 是：本 repo 要交付一个 agent 产品。严格区分外层开发 harness 与内层 release agent，见 `.agent/release-agent-boundary.md`。

## 关联文档

- 决策台账：`DECISIONS.md` -> `human/decisions/`
- 结构地图：`ANATOMY.md`
- 当前状态：`memory/current-status.md`
