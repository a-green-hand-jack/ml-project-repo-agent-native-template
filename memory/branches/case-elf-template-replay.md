# 分支状态：case-elf-template-replay

> 由 branch-reporter 通过只读 git 清点生成（`git log`、
> `git show --stat`、`git diff`、`git status`）。生成过程未执行任何 git 写操作。

> **Round 2 补记（session-boundary-agent, 2026-07-09）**：此文件下方的正文是 round 1 结束时的
> 快照，round 2 期间发生的事按时间顺序补记如下，不重写正文：
> 1. `hook-self-lock-fix` 分支（off `main`）诊断并修复了正文提到的 hook 自锁隐患，PR #1 已
>    squash-merge 进 `main`（commit `6fed240`），worktree 已清理；同时新增了「书面文档默认中文」
>    doctrine（`.agent/behavior-contract.md` + ADR）。
> 2. `main` 已合并回本分支（clean merge），`validate-governance.py` 复跑仍全过，解决了正文
>    「Merge 目标」一节提到的两处遗留：validator 已针对最终树跑过、commit message 与
>    current-status.md 的矛盾已在后续 commit 里修正。
> 3. 在**同一个仍在运行的 session** 里现场复验该修复：真实 `cd` 进 `lab/code/external/ELF`
>    再跑后续命令，**仍复现修复前的旧报错**；用 ExitWorktree/EnterWorktree 重进也未刷新。
>    结论：hook 配置在 session 启动时缓存，不随磁盘改动或 worktree 重进而刷新；此修复要在
>    **全新 session** 里才能验证是否真的生效。详见
>    `lab/traces/human-cc/2026-07-09/hook-cwd-drift-stuck-recovery/trace.md`。
> 4. round 2 正在派生剩余约 9 个 subagent + 部分 skill；其中 `repo-researcher` 的审计发现同一类
>    「裸相对路径假设 cwd==repo 根」的 bug 在 `.githooks/pre-commit`、两个 hook 脚本内部路径、
>    `.claude/settings.example.json` 里还有未修复的实例——是否扩大这次修复范围待人类决定。
> 5. 本次 round 2 的 `session-boundary-agent` 调用本身把 `memory/session-tree.md` 与两份
>    `memory/branches/*.md` 误写进了**主仓库**（`/home/user/Projects/ml-project-repo-agent-native-template`）
>    而不是本 worktree——因为该 agent 没有 Bash 工具，只能靠 prompt 里的文字路径而非实际 `cd`；
>    已发现并手工搬回本 worktree、主仓库已还原干净。这本身是一条值得记录的多 agent 编排发现。

## 用途

`ml-project-repo-agent-native-template` 仓库自身的独立功能测试 **case** 分支。它把
`~/Projects/ELF-template-case` 的持久研究内容——一个更早的 `.harness`/`research-project-template`
谱系的实例，本身是围绕公开的 `lillian039/ELF` PyTorch/JAX 训练项目搭建的压力测试 case——迁移进
本模板当前的 `lab/` + `deliverables/` + `human/` 结构，然后用来实测（而非修复）模板的
validators、hooks、skills 和 subagents。按本分支自己 `PROJECT.md` 的说法："这不是一个真正的研究
项目，而是 `ml-project-repo-agent-native-template` 自身的功能测试 case。"

**本分支有意不打算合回 `main`。** 它是一个用完即弃或长期保留的 case/示例分支，用于供人类 review
diff，而非用于集成。

## 父 session

通过 Claude Code 的 `EnterWorktree` 工具从 `main` 的 `fc18318`（"docs: explain why the
template has no dedicated docs/ folder"）创建。

## 分支 / base

- 分支：`worktree-case+elf-template-replay`
- base：`main` @ `fc18318`
- base 之外已提交历史（2 个 commit）：
  - `c164232` —— "case: migrate ELF-template-case content into agent-native
    template shape"
  - `fdfa519` —— "fix: migrate the two lab/code/tests files missed in the
    first migration pass"
- **工作树状态：报告撰写时为 dirty**——见下文"实时/进行中的工作树状态"。这是真实的、看起来是
  并发的、未提交的工作，不是本报告产生的。

## Worktree

- 路径：`.claude/worktrees/case+elf-template-replay/`（相对于仓库根
  `/home/user/Projects/ml-project-repo-agent-native-template`）
- 未 push 到任何远端；未配置跟踪分支。

## 关联 issue / PR

未发现。未 push 到任何远端；两个 commit 信息里、以及本分支的 `PROJECT.md` 里都没有引用任何
issue/PR 编号。

## 拥有的路径

2 个已提交 commit 触碰过的所有内容（迁移 commit 改了 86 个文件，fix commit 又改了 2 个），
主要包括：

- `lab/code/**`（src、eval、experiments、configs、scripts、tests、pyproject、
  pre-commit 配置）
- `lab/infra/{launch,paths}/**`
- `lab/docs/**`（reference、research-narrative、audits、code/{dev,ops,
  outlines,src}、designs、experiments、timelines、updates、overview.md）
- `deliverables/paper/**`（bib、figures、macros、main.tex、sections、tables）
- `human/reviews/results/elf-case-smoke-result.md`
- `lab/research/{claims,evidence,experiment-ledger}.yaml`
- `PROJECT.md`、`.gitignore`
- `memory/current-status.md`（本分支自己的活状态文档）
- ANATOMY 更新：`lab/ANATOMY.md`、`lab/code/ANATOMY.md`、
  `lab/infra/ANATOMY.md`

另外，**当前未提交**（见下文）：对
`lab/artifacts/{result,trace}-index.yaml`、
`lab/research/{claims,evidence,experiment-ledger}.yaml`、
`memory/current-status.md`、`lab/AGENTS.md`、`lab/README.md`、
`lab/code/AGENTS.md`、`lab/code/README.md` 的进一步编辑，以及一个新的未跟踪文件
`lab/docs/README.md`。

## 禁止路径

- 仓库全局硬边界（各处一致，见 `.agent/action-boundary.md`）：不得编辑/删除
  `lab/data/**`、`lab/runs/**`、`lab/models/**` 权重、`checkpoints/**`、`wandb/**`、
  `lab/infra/private/**`、`.env` 下的 bytes。
- 分支专属约束（来自本分支自己 `memory/current-status.md` 的 Constraints 一节）：不得修改
  `~/Projects/ELF-template-case`——它是仓库外部的一个只读参考源。
- 未经人类明确要求，不得 push 到任何远端（本分支 `PROJECT.md` 的"Remote / worktree 策略"一节
  声明）。
- 仅 CPU 本地执行；本环境无 GPU / EPFL 集群访问（声明的约束，不是硬性的工具层边界）。

## Anatomy / ledger 影响

- `lab/ANATOMY.md`：+`docs/` leaf。
- `lab/code/ANATOMY.md`：+`eval/`、+`external/`（gitignored 的 vendor-clone
  位置，不属于已跟踪历史的一部分）。
- `lab/infra/ANATOMY.md`：`launch/`、`paths/` 被记录为已落地。
- `lab/research/{claims,evidence,experiment-ledger}.yaml`：已填充（在已提交的迁移中）来自旧
  仓库 `memory/boards/claims.yaml` 迁移过来的 4 条 claim。刻意把全部 4 条从
  `status: supported` **重新降级**为 `status: partial`，因为支撑证据只是 log 级别（clone /
  py_compile / 依赖导入 / 一次 CPU 前向 smoke），而新模板的证据阶梯
  （`lab/research/ANATOMY.md`）要求 `supported` 至少是 `>= metric`。这次重新降级本身（在本分支
  自己的笔记里）就被当作一条正面的测试发现：新的证据链检查比它取代的旧自由文本 `certainty`
  字段更严格。
- 旧仓库的 `risks.yaml`/`actions.yaml`/`provenance.yaml`/`source-visibility.yaml`
  在新 schema 里没有对应的 YAML 位置；以散文形式迁移进
  `lab/docs/research-narrative/project-board-risks-actions.md`
  和 `lab/docs/reference/provenance.md`（不受 validator 检查，按本分支自己的
  Decisions 日志）。
- 本分支的 `memory/change-control.yaml` **仍然只有模板自带的示例条目**——尽管这次迁移在 3 个
  地方触碰了 `ANATOMY.md`，却没有正式登记任何 `structure` 类型的变更。值得人类判断：一个测试
  case 分支在最终 push 之前，是否需要这份正式手续，还是可以跳过。
- **当前未提交，进行中**：又一轮证据/台账/产物索引登记（新的
  `ev-elf-pytorch-runtime-smoke-replay-claude` 证据条目、
  `run-elf-pytorch-runtime-smoke-replay-claude` 台账条目，两条新的
  `lab/artifacts/result-index.yaml`/`trace-index.yaml` 条目）加上对
  `lab/AGENTS.md`、`lab/README.md`、
  `lab/code/AGENTS.md`、`lab/code/README.md` 的 anatomy/文档同步编辑，以及一个新的
  `lab/docs/README.md`，用来记录 `docs/`/`eval/`/`external/` 这几个面。见下文"实时/进行中的
  工作树状态"——这部分还没有整合或提交。

## 最近验证

- 本分支 `memory/current-status.md` 最后一次**已提交**状态里，"Commands + results" 表是空的，
  注明了"（迁移阶段尚未跑 validator，见 Exact next steps）"——也就是说，截至迁移基线 commit，
  仓库自己的治理 validator 还没有针对已迁移的树运行过。
- 然而，迁移 commit 信息（`c164232`）在叙述中声称："All four governance validators pass
  clean (validate-governance, check-agent-harness, check-anatomy-drift,
  check-same-commit --staged)"，并且还描述了一次刻意的负向探测（临时把一条 claim 改回
  `status: supported`、只留 log 级证据，确认 overclaim 检查正确地拒绝了它，然后恢复）。
  **这两份已提交的来源互相矛盾**（commit 信息说已验证且通过；而活状态文件在提交时说的是尚未
  运行）——这是一个值得调和的内部文档不一致，不是跨分支冲突。
- 另外，本分支上已提交的大部分"validation"文字——`lab/docs/audits/complete-template-verification-report.md`、
  `lab/docs/audits/elf-template-case-report.md`、
  `lab/docs/audits/pytorch-elf-runtime-smoke-plan.md`、
  `human/reviews/results/elf-case-smoke-result.md`——是**从旧的 `ELF-template-case` 仓库原样
  导入的历史内容**（日期为 2026-07-08，引用旧的 `research_project_harness` CLI 和
  `/Users/jieke/...`/EPFL 远端路径）。它记录的是那个*旧*框架对*旧* case 仓库的验证，不是这个
  *新*模板的 validator 对已迁移内容的实测。不要把这些文件当作本分支自身治理-validator 状态的证据。
- **本报告开始撰写之后新出现的（未提交，实时）：** 工作树现在显示出一次真实的、全新的、本地
  CPU-only 回放确实已经发生——`lab/code/external/ELF`（clone，`pytorch_elf` 分支，commit
  `b29d8833609e9ab7f67cd9da39435ac5cea04837`）和
  `lab/code/external/.venv-elf-cpu`（一次性 uv 环境）已存在于磁盘上（gitignored，已通过
  `ls` 确认存在），并且
  `lab/research/evidence.yaml`/`experiment-ledger.yaml`/
  `lab/artifacts/{result,trace}-index.yaml` 有未提交的新条目，描述了：依赖安装/导入成功
  （torch 2.13.0+cpu、transformers 4.44.2、datasets 2.19.1、einops、
  huggingface-hub、sacrebleu、rouge-score、wandb、muon-optimizer）、一次 config 加载 +
  override 的 smoke、一次微型合成 CPU 前向传播，复现了旧审计记录的形状
  （`(2,4,8)` / `(2,4,32)`），以及一次 `lab/code/` scaffold 检查
  （`compileall` exit 0、`pytest -q tests` → 2 passed）。这**尚未提交**，也不是本报告产生的——
  看起来是同一个共享 worktree session 里另一个 agent/subagent 的并发工作（一次
  artifact-librarian 式的登记，加上一次 repo-doc-steward 式的 anatomy/文档同步，触碰了
  `lab/{AGENTS,README}.md`、`lab/code/{AGENTS,README}.md`，以及一个新的
  `lab/docs/README.md`）。
- 仍然**未观察到**：真正针对当前（dirty）树重新跑一次本仓库自己的
  `scripts/validate-governance.py` / `check-anatomy-drift.py` /
  `check-agent-harness.py` / `check-same-commit.py`，并留下记录的输出。本报告也没有跑这些
  （超出范围：只做只读 git 清点）。建议在提交当前未提交的改动之前先跑这些，以补上上面提到的
  缺口，并验证新的 anatomy/文档同步编辑。

## Merge 目标

**无——这有意是一个独立的 case/示例分支，不打算合并进 `main`。** 按本分支自己 `PROJECT.md` 的
说法："不打算合回 main——它是一个用完即弃/长期保留的 case 分支，供人类 review diff。" 是否要
push 到远端和/或长期保留用于 review，由人类决定；在常规模板工作流下，本分支不应该向 `main`
开 PR。

## Sibling 依赖

- 单向依赖 `main` 作为 base（`fc18318`）；没有任何东西反过来合并回去。
- 清点时刻，本仓库不存在其他活跃的本地或远端**分支**/worktree——分支层面没有 sibling，没有
  路径/所有权重叠，分支之间也没有循环依赖可标记。
- 不过，在这个单一 worktree 内部，存在明显的**此刻正在进行的并发 agent 活动**（见"实时/进行中的
  工作树状态"）：看起来有另一个 subagent 正在同一个工作树里、与本报告同时主动编辑文件。不是
  分支冲突，但值得让人类知道这是一个同一 worktree 内的并发性提示，任何人提交之前都该留意。

## 实时/进行中的工作树状态（报告撰写时）

`git status --porcelain` 在这次报告撰写过程中、相隔几分钟的两次检查之间显示出一个**在变化**的
已修改/未跟踪文件集合——也就是说工作树是一个移动目标，不是静态快照。最后一次检查观察到：

```
 M lab/AGENTS.md
 M lab/README.md
 M lab/artifacts/result-index.yaml
 M lab/artifacts/trace-index.yaml
 M lab/code/AGENTS.md
 M lab/code/README.md
 M lab/research/claims.yaml
 M lab/research/evidence.yaml
 M lab/research/experiment-ledger.yaml
 M memory/current-status.md
?? lab/docs/README.md
?? memory/branches/case-elf-template-replay.md   (this report)
?? memory/worktree-status.md                      (this report)
```

上面的 `M`/第一批 `??` 条目都不是本报告产生的——本报告全程只跑过只读的
`git`/shell 检查命令，并写了自己那两份报告文件。建议：不要把这份快照当作最终结论；提交前请
重新跑 `git status`/`git diff`，让任何并发中的 agent 先完成，并让人类把合并后的完整 diff 当作
一个整体来 review。

## 退出条件

由于没有 merge 目标，这里的"退出"不代表"可以合并"。建议的退出条件，取自本分支自己
`memory/current-status.md` 的"Exact next steps"（现在被上面描述的未提交工作部分地、但还不是
完全或可验证地覆盖了）：

1. 让当前活跃的并发工作先完成，然后整合并真正对最终的树跑一遍 4 个治理 validator；把真实结果
   记录进 `memory/current-status.md`（补上上面"最近验证"一节提到的缺口）。
2. 重新 clone `lillian039/ELF`（`pytorch_elf` 分支），回放一次 CPU-only 依赖导入 + 微型前向
   smoke ——**看起来已经做了**（未提交；核实并定稿，而不是重做）。
3. 通过一次 artifact-librarian 式的操作，把 smoke 结果登记进
   `lab/artifacts/*-index.yaml` ——**看起来已经做了**（未提交；核实并定稿，而不是重做）。
4. 实测剩下的代表性 subagent/skill（experiment-orchestrator、
   checkpoint-writer、repo-doc-steward——上面已部分佐证——、
   branch-reporter——本报告——、test-runner + `worktree-pr-flow`/
   `experiment-workflow`/`artifact-indexing`/`anatomy-drift-control` skill），
   确认每一个都按自己的 `SKILL.md`/agent 定义行事。
5. 跑几个安全的 hook/权限探测（尝试编辑受保护路径、尝试 push 到 main），确认它们按预期被阻止。
6. 把发现写成一份 `lab/docs/audits/` 报告加一份 `human/reviews/results/` 摘要，并相应更新
   `memory/current-status.md`。
7. 一旦发现写完、工作树稳定下来，由人类把整个分支当作一个整体来 review（diff review，不是
   merge review），并决定：把它保留为一个长期存在的参考/示例分支（不合并也不删除），可以选择
   push 到远端做归档/分享。

除了继续这份已记录的下一步清单之外，不需要任何自主 agent 动作；本分支不需要达到"可合并"状态，
因为合并从来就不是目标。

## 别忘了（沿用自本分支自己的 current-status.md）

- 如果这个 worktree 是通过 Claude Code 的 `ExitWorktree` 工具退出的，使用
  `action: keep`——测试产物应该保留，而不是删除。
- `~/Projects/ELF-template-case` 是本仓库外部的一个只读参考源；不要修改它。任何真实的
  执行/回放都必须保持本地 CPU-only（本环境无 EPFL/GPU 访问）。
- 本报告撰写期间工作树在主动变化（并发 agent）——在把这份文件当作最终/静态结论采取行动之前，
  请重新核实状态。
