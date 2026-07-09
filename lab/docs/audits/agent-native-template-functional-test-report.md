# Agent-Native 模板功能测试报告

Case：将 `ELF-template-case` 迁移进 `ml-project-repo-agent-native-template`，然后对模板自身的
validators / hooks / skills / subagents 做功能测试。

分支：`worktree-case+elf-template-replay`（worktree 位于
`.claude/worktrees/case+elf-template-replay/`，从 `main` 分出）。不打算合回主干；是一个独立可
review 的 case（见 `memory/branches/case-elf-template-replay.md`）。

## 基线

- 源 case 仓库：`~/Projects/ELF-template-case`（GitHub
  `a-green-hand-jack/ELF-template-case`，分支 `case/elf-template-replay`），是更早一代模板谱系
  （`.harness/` / `research-project-template` / `research_project_harness` CLI）的一个实例，本身是
  为了压力测试那个旧模板而针对真实公开的 `lillian039/ELF` PyTorch/JAX 训练项目搭建的 case。全程只读
  引用，从未修改。
- 目标模板：`ml-project-repo-agent-native-template` `main` @ `fc18318`，是一次重新设计、
  Claude-Code-native 的后继版本（`.agent/` doctrine + `.claude/` capability + `lab/` 研究控制面 +
  `scripts/` validators），与旧的 skill 集合（anatomy-drift-control、artifact-indexing、
  experiment-workflow、session-boundary-control、subagent-routing、worktree-pr-flow、
  interactive-plan-doc、workflow-recipe-harvesting）有清晰的传承关系，但没有 `.harness/`/`rph` CLI。
- 环境：本地 Linux 机器，仅 CPU，无 GPU，无 EPFL 集群访问（旧审计是在一台 Mac + EPFL RunAI 集群、
  配有持久化 PyTorch 环境的机器上跑的）。全程未 push 到任何远端。

## 命令

实际跑过的代表性命令（完整列表见 `memory/current-status.md` 的 Commands + results 表以及本分支的
两个 commit）：

```bash
python3 scripts/validate-governance.py         # includes check-agent-harness, check-anatomy-drift
python3 scripts/check-same-commit.py --staged
git clone --depth 1 --branch pytorch_elf https://github.com/lillian039/ELF lab/code/external/ELF
uv venv --python 3.11 lab/code/external/.venv-elf-cpu
uv pip install --python lab/code/external/.venv-elf-cpu/bin/python \
  --extra-index-url https://download.pytorch.org/whl/cpu -r lab/code/external/ELF/requirements.txt
# config load + apply_config_overrides + tiny synthetic CPU forward (see current-status.md)
(cd lab/code && python3 -m compileall -q src eval experiments scripts tests)
(cd lab/code && uv run --no-project --with pytest --python 3.11 python -m pytest -q tests)
# hook probes: sudo, curl|sh, rm -rf on protected dirs, mv into protected dir, Write to protected path
# synthetic stdin JSON to .claude/hooks/pre_tool_guard.py for git-push-to-main / topic-branch / escape-hatch
```

以及针对已迁移内容 spawn 的 5 个 subagent：`artifact-librarian`、
`experiment-orchestrator`、`repo-doc-steward`、`branch-reporter`、`test-runner`。

## 发现

按照旧 case 测试的分类惯例：**template gap**（新模板缺一种机制）/ **validator/hook 按预期工作** /
**case ledger 债务** / **文档摩擦** / **迁移执行失误**（我自己的失误，不是模板的问题）。

### F1 — 证据链评分比旧的 boards.yaml 更严格，且按预期工作（validator 按预期工作）

旧的 `memory/boards/claims.yaml` 把 4 条 claim 标为 `status: supported` /
`certainty: evidence-backed`，但支撑证据其实只是 clone/py_compile/依赖导入/一次 CPU 前向 shape
smoke。按新的 `grade: log < metric < ...` 阶梯如实迁移后，这些证据够不到 `supported` 的门槛（需要
`>= metric`），所以 4 条全部被降级为 `status: partial`。验证了这个检查确实会触发：临时把一条 claim
改回 `supported`、只留 log 级证据 —— `validate-governance.py` 正确地报错
`overclaim：... 但最强证据低于 metric`；随即恢复。**这是相对旧 schema 的一次真实改进**，旧 schema
在自由文本 `certainty` 与分级证据阶梯之间没有机器强制的关联。

### F2 — 嵌套 vendored git 仓库 + 相对路径 hook = 自锁失败（template gap，中等严重）

把真实的 `lillian039/ELF` 重新 clone 进 `lab/code/external/ELF`（有自己的 `.git`），然后 `cd` 进去
做 smoke 测试，导致 shell 的 cwd 在多次工具调用之间持续停留在那里。`PreToolUse` hook 被配置成一个裸
相对路径（`.claude/settings.json` 里的 `python3 .claude/hooks/pre_tool_guard.py`），是相对当前 cwd
解析的，而不是锚定在仓库根。一旦 cwd 落在这个嵌套仓库内部（它没有 `.claude/hooks/...`），**之后每一个
Bash/Edit/Write 调用都会因 hook 报文件找不到而失败关闭（fail closed）**——包括本应能修好它的
`cd ..`/`cd <worktree-root>` 命令本身，因为这些命令根本没机会执行（hook 在命令体执行前就先报错了）。
只能通过 `ExitWorktree(action=keep)` + `EnterWorktree(path=...)` 这类不受此 hook 约束的工具才恢复。
这是一个真实、可复现的健壮性缺口：任何 vendor 或 `cd` 进嵌套 git 仓库的工作流（这是非常常见的操作）
都可能把整个 session 卡死。建议方向（未实施——按范围要求 test-first）：把 hook 命令锚定到绝对路径或
类似 `$CLAUDE_PROJECT_DIR` 的变量，而不是裸相对路径。

### F3 — same-commit 闸门是「目录名精确匹配」，不感知祖先目录（已记录的缺口，低严重度，属设计如此）

`check-same-commit.py` 只要求更新 `<dirname(changed_file)>/ANATOMY.md`，不要求更新任何祖先目录的。
两个方向都做了确认：
- **漏检**：在一个全新的 `lab/docs/` 子树下新增大量文件（其下任何位置都没有 ANATOMY.md），**没有**
  触发要求更新 `lab/ANATOMY.md`——尽管 `lab/` 是拥有 ANATOMY.md 的目录的新*子级*。`lab/code/eval/`、
  `lab/code/external/`，以及 `lab/infra/launch/envs/` 下两层深的新增内容也是同样情况——都没有强制
  `lab/infra/ANATOMY.md` 更新。我还是主动更新了所有这些 anatomy 文件（出于 doctrine 精神），但闸门
  本身不会强制这么做。
- **拦住了**：直接在 `memory/` 内部（它确实拥有一份 ANATOMY.md）新增 `memory/worktree-status.md`，
  在 `memory/ANATOMY.md` 被更新以列出该文件之前，正确地卡住了闸门。
这与该工具自己文档中声明的「保守/低误报」设计一致，不是 bug，但值得精确知道边界在哪里。

### F4 — `branch-reporter` 自己声明的输出没写进它所在目录的 ANATOMY（文档摩擦，现已修复）

`.claude/agents/branch-reporter.md` 说它会写 `memory/worktree-status.md`，但
`memory/ANATOMY.md` 的组件列表从未提到过这个文件（只有 `current-status.md`、`session-tree.md`、
`branches/` 等）。当 branch-reporter 真正跑起来并 stage 了该文件之后，被 F3 的 same-commit 闸门
抓住了。已在本分支修复。

### F5 — 没有面向文献/参考资料或自由叙事研究记录的专属模板平面（文档摩擦）

旧模板有一等公民级的 `reference/`（source cards、provenance、处理状态）和 `research-artifact/`
（问题陈述、假设、贡献地图、死胡同、负结果、待验证 claim 暂存区）两个平面。新模板没有对应的位置；按
它自己「不设通用 `docs/`，长文档放进嵌套的 `lab/docs/`」的决定，这些内容被折进了
`lab/docs/reference/` 和 `lab/docs/research-narrative/`——合理，但新模板没有针对这类具体内容类型的
明确指引（只在 `DESIGN.md` §12 里对通用 docs/ 决定有隐含暗示）。类似地，旧的
`memory/boards/{risks,actions,provenance,source-visibility}.yaml` 在新 schema 里没有结构化 YAML
归属（只有 `claims`/`evidence`/`experiment-ledger`/`regression-matrix`/`release-gates`）；最终以纯
markdown 形式落进 `lab/docs/`，这意味着它们完全在 `validate-governance.py` 的 YAML/证据链检查范围
之外。

### F6 — `lab/code/external/`（vendored 第三方源码）是一个从旧模板继承下来、始终未解决的未记录约定（case ledger 债务，低严重度）

旧审计（`lab/docs/audits/elf-template-case-report.md`）就已经标出过这个确切的缺口（"一个真实的外部
源码 case 需要一个明确约定：一个嵌套的上游 clone 应该属于 `code/external/`、`reference/sources/`，
还是类似 worktree/submodule 的位置"）。新模板在这一点上同样没有明确态度。我务实地沿用了旧的
`code/external/ELF` 约定（现为 `lab/code/external/ELF`，已 gitignore），并把这个选择记录在
`lab/code/ANATOMY.md` 里，但这仍然是横跨两代模板、被继承下来却从未解决的缺口。

### F7 — `.vscode/` 全局 gitignore 悄悄丢弃了一个旧仓库有意跟踪的文件（行为差异，不是 bug）

旧仓库跟踪了 `code/.vscode/settings.json`。新模板根 `.gitignore` 有一条全局 `.vscode/`
规则（没有路径限定），所以迁移后的 `lab/code/.vscode/settings.json` 被悄悄地不再跟踪。可以算是一个
更严格的合理默认；记录下来是因为这是一个迁移者容易漏掉的静默差异。

### F8 — 治理 validators 与 hook 底线在其余方面完全按设计工作（正面发现）

- `validate-governance.py` / `check-agent-harness.py` / `check-anatomy-drift.py` /
  `check-same-commit.py`：在完全迁移完成、且经过 subagent 触碰的树上全部干净通过。
- Hook 探测全部行为正确：`sudo`、`curl|sh`、对受保护目录的 `rm -rf`、对受保护目录的 `mv`/`cp`、对
  受保护路径的 `Write`/`Edit`（permission-deny 层）——全部被阻止。`git push` 到 `main`/`master` 在
  没有 `CLAUDE_ALLOW_PUSH_MAIN=1` 时被阻止，有则放行，push 到 topic 分支则无条件放行（通过向 hook
  脚本直接送合成 stdin JSON 测试，以避免对真实远端做任何真实网络 push——见 F2 的事故，可知为什么对这个
  具体 case 而言，真实 live 探测感觉风险太高，不值得重复）。
- 真实的 `lillian039/ELF`（`pytorch_elf` @ `b29d8833609e9ab7f67cd9da39435ac5cea04837`）重新 clone、
  全新的 CPU-only 依赖安装，以及一次微型合成前向传播，**精确复现**了旧审计记录的形状——`(2, 4, 8)`
  输出 / `(2, 4, 32)` decoder logits——在一台不同的机器上、用不同（更新、CPU-only）的依赖版本、独立
  完成。对上游 case 和本次迁移的保真度都是很强的可复现性信号。
- 5 个 subagent（共 15 个已定义）行为都在其声明的工具/边界契约之内：没有删除，没有未经授权提升到
  `supported`/paper-claim，是提议而非单方面归档，而且——令人意外地——它们在没有被指示的情况下通过
  共享文件彼此协调一致（experiment-orchestrator 关闭了一个 artifact-librarian 明确标记给"ledger
  owner"的跨引用缺口）。

### F9 — 我自己的迁移失误（不是模板的 bug）

- 第一轮机械式复制漏掉了 `code/tests/{conftest.py,test_placeholder.py}`；在 pytest 回放时发现，
  同一 session 内修复。
- 第一次 commit 的信息声称所有 validator 都通过了，但已提交的 `current-status.md` 表格里还写着
  "尚未运行"——被 `branch-reporter` 发现，在下一个 commit 里修复。

## 覆盖度警示（不做完整性的静默声明）

- 15 个 subagent 里只实测了 5 个（artifact-librarian、experiment-orchestrator、
  repo-doc-steward、branch-reporter、test-runner）。未实测：checkpoint-writer、
  experiment-monitor、feature-worker、hook-maker-agent、interactive-plan-writer、
  repo-researcher、session-boundary-agent、sub-agent-maker-agent、subagent-router-agent、
  workflow-recipe-harvester。
- 没有任何 `.claude/skills/*` workflow 被作为 skill invocation 端到端驱动过（本次 session 直接用了
  底层机制——worktree、validators、subagents——而不是通过 Skill 工具调用例如 `/checkpoint` 或
  `/pr-review` 命令，或 `worktree-pr-flow`/`experiment-workflow` skill）。
- 没有对 ELF 做 GPU、数据集加载、checkpoint 加载、训练/生成循环、指标复现——仅 smoke 级别，与新旧
  两份证据记录明确声明的范围一致。
- 按任务范围，这一轮是纯测试性质：上面记录的发现只是记录，没有在模板本体里修复（本分支只做了迁移
  内容与文档同步方面的修复）。

## 遗留债务

- 如果这个分支的发现要在上游被采纳，F2（hook 路径健壮性）是最值得优先修的候选。
- F5/F6（缺少 reference/research-narrative/外部 vendor 约定）值得在 `DECISIONS.md` 里记录一个
  明确决定，不管最终倾向哪个方向。
- 未测试：checkpoint-writer、session-boundary-agent，以及 skill 层级的入口（commands、
  Skill 工具驱动的 workflow）——如果想再来一轮测试，这是自然的下一片切片。
