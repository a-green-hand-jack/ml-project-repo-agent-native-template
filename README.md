# ml-project-repo-agent-native-template

> 面向 AI PhD 的「agent-native」ML 研究 repo 模板。所有未来的 `ml-project-repo` 都从这里派生。

这个模板把 Claude Code / Codex 当作**实验仪器**而不是聊天窗口：短上下文做当前判断，repo 文件做长期控制面，subagent 做隔离任务，worktree 做并行边界，hook/permission 做硬约束，anatomy/ledger/validator 做防漂移，测试与实验记录做事实来源。

设计精神与实践依据见 `.reference-docs/`：两份来源文档
`claude_code_optimization_spirit_zh.md` / `claude_code_practice_for_ai_phd_zh.md`，以及当前实现覆盖说明
`implementation-coverage-note.md`。

## 这个 repo 是什么

- 一个可复制的**研究控制根**：一进 repo，human 和 agent 都能读到可信信息，并通过 repo 改变可信信息。
- Chat 是临时控制台；repo 是共同可信平面。目标、批注、plan、结果、决策、反例都落到文件里。

## 现在怎么看（human 入口）

| 想知道 | 去哪里 |
| --- | --- |
| 模板本身怎么设计、怎么实现 | `DESIGN.md` |
| 项目研究对象、trunk、worktree 策略 | `PROJECT.md` |
| 当前在做什么、下一步 | `memory/current-status.md` |
| 有哪些 claim、哪些 evidence 支持 | `lab/research/claims.yaml` · `lab/research/evidence.yaml` |
| 我该怎么和 agent 协作 | `human/README.md` |
| repo 结构地图 | `ANATOMY.md` |
| 采用了哪些 agent 工作流 | `memory/current-practices.md` |

## agent 入口

agent 从 `AGENTS.md` 开始读；Claude Code 从 `CLAUDE.md`（薄路由）开始；Codex 会读取 `AGENTS.md`，
并在信任项目后加载 `.codex/` config/custom agents 与 `.agents/skills`。

## 用这个模板开新项目（Use this template）

本仓库已设为 GitHub **template repository**，派生新 `ml-project-repo` 有三种方式：

**A. 网页一键（推荐）** — 在仓库页点 **"Use this template" → Create a new repository**，填新项目名即可。

**B. `gh` CLI**

```bash
gh repo create <new-project> \
  --template a-green-hand-jack/ml-project-repo-agent-native-template \
  --private --clone
cd <new-project>
```

**C. 直接 clone 再改 remote**（不想保留派生关系时）

```bash
git clone git@github.com:a-green-hand-jack/ml-project-repo-agent-native-template.git <new-project>
cd <new-project> && rm -rf .git && git init
```

### 派生后的落地步骤

派生出的新 repo 已经拥有完整模板目录形态（"Use this template" 本身就会复制整棵树，包括
`scripts/bootstrap-project.py` 自己）。剩下能自动化的部分收敛成一条幂等命令，在**新 repo 内**
运行它自己的脚本（self-bootstrap），用 `bootstrap-project` skill 调用：

```bash
cd <new-project>
python scripts/bootstrap-project.py . --origin <owner/repo>
```

`--origin` 必须显式传入（不推断上游 template repo slug），第二次以相同 `--origin` 重跑是幂等的
（state/report 内容不变则不改写；`state/run-log.jsonl` 是追加式审计日志，每次运行追加一行）。
脚本会拒绝把**上游模板 repo 自身**当目标（判据只看**身份 remote `origin`**：其 URL 归一化后
——大小写不敏感、剥 `.git` 后缀——与 `--origin` 是同一个 slug 就拒绝；`upstream` 等其它 remote
不参与判定，所以派生 repo 保留指回模板的 `upstream` remote 不会被误拒）。注意这只是 best-effort
的防呆护栏、不是安全边界：模板 checkout 没有 remote、或 `origin` 被改名/改指向时不会被识别，
属已知残余风险。
这一条命令会自动做：

1. 写/确认 `.template.toml`（origin + version 锚点；已存在且 origin 不一致时报错停止，需要覆盖
   显式加 `--force`）。
2. 启用 same-commit git hook：`git config core.hooksPath .githooks`
   （per-clone，不随 `git clone` 复制；换机器/重新 clone 要重跑。CI 那道始终生效）。
3. 运行 `python scripts/sync-codex-adapters.py` 同步 `.codex/` 与 `.agents/`。
4. 跑 `python scripts/validate-governance.py` 确认 harness 仍然自洽。

命令输出与 `lab/docs/audits/template-bootstrap-report.md` 会列出剩下**必须由 human 完成、脚本不
猜测**的步骤：

- 填写 `PROJECT.md`：研究对象、active family、trunk、remote/worktree 策略。
- 把 `.github/CODEOWNERS` 里的 `@a-green-hand-jack` 换成该项目真实 owner。
- 删掉用不到的目录（模板是「一次建好，按需删减」，不是「一定全用」）。
- 若使用 Codex，**信任本 repo 的 `.codex/` project config**——这一步无法脚本化，Codex 的 hooks
  要先被 human trust 才会加载；`bootstrap-project.py` 只能把这一步列成待办，不能代做。
- 在 `.reference-docs/` 里保留或更新你信奉的 doctrine 版本。

## 迁移已有 repo（Adopt existing repo）

如果不是新建项目，而是要把一个已经存在的 Git repo 收敛成本模板形态，使用：

```bash
python scripts/adopt-existing-repo.py /path/to/existing-repo \
  --phase all \
  --policy conservative \
  --project-name <slug> \
  --origin <owner/repo> \
  --test-command "<original test command>"
python scripts/check-adoption-integrity.py /path/to/existing-repo
```

迁移是分 phase 的：`discover → baseline → scaffold → normalize → prove`。`discover` 会给每个
root entry 打内置保守四类标签（`template_control_item` / `conservative_import` / `protected` /
`conflict`，v1 不做外部规则文件覆盖，`--dry-run` 只打印/写归类计划、不落盘）；`normalize` 消费
这份归类计划——`protected`/`conflict` 命中即登记 blocker 并停下，不静默继续。默认策略不删除、
不覆盖、不移动受保护 bytes；冲突文件会保存在 `human/imported/adoption-conflicts/`，原 repo
root 会收敛到 `lab/code/imported/<slug>/`，proof（含 Claude/Codex 双 agent surface 加载清单）
写入目标 repo 的 `lab/docs/audits/template-adoption-report.md`。

所有 phase 都要求显式 `--origin <owner/repo>`，不从 remote 或路径猜测。只有无 blocker 的成功
`normalize` 才会在完成所有 move 后原子创建/确认 `.template.toml`；dry-run、scaffold-only 和
`--allow-blocked-normalize` 不写锚点。同 origin 的已有锚点保留 version；异源、malformed 或
symlink 锚点在 move 前 fail-closed。

`prove`/`check-adoption-integrity.py` 的 exit code 只反映 adoption 工具自身的完整性（tracked-byte
hash 是否一致、是否有未解决的 conflict/受保护路径 blocker）；被迁移项目自身原生测试命令的结果
（`command_source`/`result`：`pass`/`fail`/`skipped`/`unknown`/`unverified_reason`）与这个 exit code
解耦——测试未检测到或跑失败不会让这两个命令看起来"失败"，但会在 report 与
`check-adoption-integrity.py --json` 的 `warnings`/`smoke_warnings` 字段里显式列出，不会被静默吞掉。

## 快速门禁

```bash
python scripts/validate-governance.py     # 总门禁：harness + anatomy + 治理 + 证据链
python scripts/check-agent-harness.py     # 结构/必需文件/根污染/权限 deny 覆盖
python scripts/check-anatomy-drift.py     # ANATOMY 引用/行号漂移 + 120 行上限
python scripts/check-same-commit.py --staged  # 结构改动 <-> ANATOMY 同变更集（pre-commit + CI 自动跑）
python scripts/sync-codex-adapters.py --check # Codex adapters 是否与 .claude canonical 能力同步
python lab/evals/adoption/run-adoption-smoke.py  # existing-repo 迁移 smoke
python lab/evals/bootstrap/run-bootstrap-smoke.py  # 新项目 bootstrap smoke
```
