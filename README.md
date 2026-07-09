# ml-project-repo-agent-native-template

> 面向 AI PhD 的「agent-native」ML 研究 repo 模板。所有未来的 `ml-project-repo` 都从这里派生。

这个模板把 Claude Code 当作**实验仪器**而不是聊天窗口：短上下文做当前判断，repo 文件做长期控制面，subagent 做隔离任务，worktree 做并行边界，hook/permission 做硬约束，anatomy/ledger/validator 做防漂移，测试与实验记录做事实来源。

设计精神与实践依据见 `.reference-docs/`（`claude_code_optimization_spirit_zh.md` 与 `claude_code_practice_for_ai_phd_zh.md`）。

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
| 采用了哪些 Claude Code 工作流 | `memory/current-practices.md` |

## agent 入口

agent 从 `AGENTS.md` 开始读；Claude Code 从 `CLAUDE.md`（薄路由）开始。

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

1. 填写 `PROJECT.md`：研究对象、active family、trunk、remote/worktree 策略。
2. 把 `.github/CODEOWNERS` 里的 `@a-green-hand-jack` 换成该项目真实 owner。
3. 启用 same-commit git hook：`git config core.hooksPath .githooks`
   （per-clone，不随 `git clone` 复制；换机器/重新 clone 要重跑。CI 那道始终生效）。
4. 删掉用不到的目录（模板是「一次建好，按需删减」，不是「一定全用」）。
5. 跑 `python scripts/validate-governance.py` 确认 harness 仍然自洽。
6. 在 `.reference-docs/` 里保留或更新你信奉的 doctrine 版本。

## 快速门禁

```bash
python scripts/validate-governance.py     # 总门禁：harness + anatomy + 治理 + 证据链
python scripts/check-agent-harness.py     # 结构/必需文件/根污染/权限 deny 覆盖
python scripts/check-anatomy-drift.py     # ANATOMY 引用/行号漂移 + 120 行上限
python scripts/check-same-commit.py --staged  # 结构改动 <-> ANATOMY 同变更集（pre-commit + CI 自动跑）
```
