# Worktree / 分支状态总览

> branch-reporter 生成的快照（只读 git 清点：`git worktree list`、
> `git branch -a -vv`、`git log`、`git show --stat`、`git diff`、`git status`；
> 未执行任何 git 写操作）。是在
> `worktree-case+elf-template-replay` worktree 自己的 `memory/` 树内写的（本仓库把
> `memory/` 当作按分支存在的普通文件跟踪，所以这份快照就存在这个分支上；如果需要一份
> 仓库全局的规范副本，人类可以把它的一个版本 copy/adapt 进 `main` 的 `memory/`）。

生成时间：2026-07-09
仓库：`ml-project-repo-agent-native-template`

## 活跃 worktree（`git worktree list`）

| worktree 路径 | 分支 | HEAD（最新 commit） |
| --- | --- | --- |
| `/home/user/Projects/ml-project-repo-agent-native-template` | `main` | `fc18318` |
| `/home/user/Projects/ml-project-repo-agent-native-template/.claude/worktrees/case+elf-template-replay` | `worktree-case+elf-template-replay` | `fdfa519`（工作树当前 dirty——见下文） |

## 活跃分支（`git branch -a`）

| 分支 | 跟踪 | 备注 |
| --- | --- | --- |
| `main` | `origin/main`（已是最新） | 主干；模板本体 |
| `worktree-case+elf-template-replay` | 无（未 push 到任何远端） | 领先 `main` 分支点（`fc18318`）2 个 commit；独立 case 分支；**存在未提交的进行中改动** |

未发现其他本地或远端分支。未发现残留/孤立 worktree。

## 重要：快照时刻工作树是活的/在变化

在整理这份报告期间，`worktree-case+elf-template-replay` 上的 `git status` 显示**同一几分钟内、
连续两次检查之间出现了真实的、未提交的改动**——也就是说，此刻有另一个 agent/subagent 正在这同一个
worktree 里并发地做真实工作（不是这份报告本身产生的）。本报告没有创建或修改这些内容中的任何一项；
只写了这份文件和 `memory/branches/case-elf-template-replay.md`。

观察到的 dirty/未跟踪路径（快照，很可能不完整/仍在变化）：

- `lab/artifacts/result-index.yaml`、`lab/artifacts/trace-index.yaml` —— 新增的
  `result-*`/`trace-*` 条目，记录了一次全新的、本地的、CPU-only 的 ELF `pytorch_elf` 运行时
  smoke 回放（依赖安装/导入、config 加载、微型合成前向传播），以及对已迁移 `lab/code/` scaffold
  的一次 `compileall`/`pytest` 检查。
- `lab/research/claims.yaml`、`lab/research/evidence.yaml`、
  `lab/research/experiment-ledger.yaml` —— 新增了一条证据条目
  `ev-elf-pytorch-runtime-smoke-replay-claude`（grade `log`）和台账条目
  `run-elf-pytorch-runtime-smoke-replay-claude`，挂接到已有的
  `claim-elf-pytorch-runtime-smoke` 上（status 仍是 `partial`，未提升）。
- `memory/current-status.md` —— "Commands + results" 表扩展了这次回放的命令/结果。
- `lab/AGENTS.md`、`lab/README.md`、`lab/code/AGENTS.md`、`lab/code/README.md`
  以及一个新的未跟踪文件 `lab/docs/README.md` —— anatomy/文档同步编辑，记录本分支迁移 commit
  新增的 `docs/`、`eval/`、`external/` 这几个面，而这些指引文档此前还没跟上。
- 磁盘上（gitignored，确认存在，不属于 git 历史的一部分）：
  `lab/code/external/ELF`（新鲜 clone，`pytorch_elf` 分支，commit
  `b29d8833609e9ab7f67cd9da39435ac5cea04837`）以及
  `lab/code/external/.venv-elf-cpu`（一次性的 CPU-only uv 环境）。

这些活动看起来对应本分支自己 "Exact next steps" 计划的第 2-3 步（重新 clone ELF + CPU-only 回放；
以 artifact-librarian 式的方式登记）加上一次 anatomy-drift 式的文档同步。也就是说——这是真实的
进展，只是尚未提交或整合。**建议：让并发的工作先完成，然后由人类（或专门的后续 session）review 完整
diff 并有意识地提交，而不是在中途提交。** 本报告没有提交、stage，或以其他方式触碰过这些文件中的
任何一项。

## 分支概要

### `main`

- 用途：`ml-project-repo-agent-native-template` 模板本体（doctrine、validators、hooks、
  skills、subagents）。
- base：无（主干）。
- merge 目标：无（是主干本身）。
- 最近验证：本报告未重新运行（超出范围：只做只读清点）。最近的 commit（`fc18318`、`4437be0`、
  `70029db`、`b3ec84e`、`d706d31`）是对模板本体的治理/validator 强化工作。
- sibling 依赖：是 `worktree-case+elf-template-replay` 的 base。
- 详情文件：未创建——`main` 是主干，不是功能/case 分支；按本任务范围，只有 case 分支才有
  `memory/branches/<slug>.md`。

### `worktree-case+elf-template-replay`（slug：`case-elf-template-replay`）

- 用途：独立的功能测试 case 分支——把更早的 `ELF-template-case` 仓库（围绕公开的
  `lillian039/ELF` PyTorch/JAX 项目搭建）迁移进本模板的结构，以此实测模板自身的
  validators/hooks/skills/subagents。**不打算合并进 `main`。**
- base：`main` @ `fc18318`。
- worktree 路径：`.claude/worktrees/case+elf-template-replay/`。
- 已提交历史：base 之外 2 个 commit —— `c164232`（迁移基线）、
  `fdfa519`（fix：两个漏迁移的 `lab/code/tests` 文件）。
- 工作树：**当前 dirty**，有真实的、看起来是并发的、未提交的后续工作（见上文"重要"一节）。
- merge 目标：**无——独立 case/示例分支；是否 push/保留由人类决定，不走常规功能分支的 merge
  流程。**
- 完整详情：`memory/branches/case-elf-template-replay.md`。

## 跨分支关系

- 本仓库只有 2 个分支/worktree。没有 sibling 争抢相同路径，`main` 与
  `worktree-case+elf-template-replay` 之间未检测到循环依赖或 merge 冲突。**无需跨分支升级。**
- `worktree-case+elf-template-replay` 是叶子节点：只依赖 `main` 作为 base；没有任何东西依赖它，
  也不打算合并回去。
- 在这个单一的 case worktree 内部，存在明显的**并发多 agent 活动**（本报告 + 至少一个其他
  subagent 在实时编辑文件）——不是分支层面的冲突，但值得让人类知道，以便最终提交时把它当作一个
  整体来 review，而不是想当然地认为只是本报告的产出。

## 需要人类关注的事项

1. `.claude/worktrees/` 在 `main` 的 `git status` 里显示为未跟踪（`??`），且没有列在
   `.gitignore` 里——一个轻微的仓库卫生问题，不阻塞任何事情。
2. 在 `worktree-case+elf-template-replay` 上：迁移 commit 的信息（`c164232`）在叙述中断言
   "所有四个治理 validator 都干净通过"，但截至 `memory/current-status.md` 最后一次提交的状态，
   "Commands + results" 表里写的是 validator **尚未**运行。现在未提交的后续工作新增了一次真实的
   CPU-only ELF 回放 + scaffold 编译/测试检查，但它本身仍然不包含针对当前（dirty）树重新跑一次
   `validate-governance.py`/`check-anatomy-drift.py`/`check-agent-harness.py`/
   `check-same-commit.py`。建议在提交当前未提交的改动之前先跑这些。
3. 报告撰写时工作树是一个**移动目标**（两次相隔几分钟的 `git status` 检查之间，未跟踪/已修改的
   文件集合发生了变化）。接手的人应该重新跑 `git status`/`git diff`，而不是把这份快照当作最终
   结论来信任，并且应该在提交前与仍在活动的其他 agent/session 协调。
