# current-status.md

> **活文件**。这是当前状态的单一真相源。每次 session 结束、compact 前、完成小目标时更新。
> fresh session 应能只读本文件 + `session-tree.md` 就接续工作。
> 下面是模板骨架，逐项填写，不要留空占位而不说明。

## 当前 objective

维护 Agent-R1 adoption replay case branch：把 `AgentR1/Agent-R1` 作为真实 agent-RL /
ML-research case 保存在 template repo 的隔离 branch/worktree 中，并用于后续压力测试。

## Constraints

- 当前 worktree：`.claude/worktrees/case+agent-r1-adoption-replay`
- 当前 branch：`worktree-case+agent-r1-adoption-replay`
- Base：`93fabae feat: add existing repo adoption workflow`
- 本 branch 是 case/replay branch，不是功能开发 mainline；默认不合并完整 case 内容回 `main`。
- 主工作区有未提交文档改动；不要在主工作区写本 case。
- 禁改路径以 `session-tree.md` 的 Global forbidden paths 为准。
- 外部副作用仍走 human gate：不 push main、不开 PR、不 merge、不 release。

## Files inspected

- `AGENTS.md`
- `.agent/AGENTS.md`
- `memory/current-status.md`
- `memory/session-tree.md`
- `lab/code/ANATOMY.md`
- `lab/code/README.md`

## Files modified

- `.github/workflows/docs.yml`：保留 Agent-R1 原有 docs workflow。
- `human/imported/adoption-conflicts/`：保留 Agent-R1 原 root 冲突文件（`.gitignore`、`README.md`）。
- `lab/code/imported/agent-r1/`：导入 Agent-R1 原 repo root。
- `lab/docs/audits/template-adoption-report.md`：目标 repo adoption proof。
- `lab/docs/audits/template-adoption/state/`：discover/baseline/phase-log state。
- `lab/code/ANATOMY.md`、`lab/code/README.md`：登记 `imported/agent-r1/` case 内容。
- `memory/current-status.md`、`memory/session-tree.md`：记录 case branch 状态。

## Decisions

- Agent-R1 case 采用 conservative imported-unit 策略：原 repo root 保存在
  `lab/code/imported/agent-r1/`。
- Agent-R1 无轻量 native test command；本 case 证明 hash integrity 与 template governance，
  不声称训练/运行时行为已验证。
- Case branch 用来压力测试 template/adoption workflow；完整外部 case 内容默认不合并回 `main`。

## Commands + results

| command | 结论 |
| --- | --- |
| `git worktree add .../case+agent-r1-adoption-replay -b worktree-case+agent-r1-adoption-replay 93fabae` | 创建 case branch/worktree 成功。 |
| `cp -a /tmp/agent-r1-adoption-replay/Agent-R1/...` | 将迁移后的 Agent-R1 imported content、conflicts、proof/state、docs workflow 复制进 case branch。 |
| `python scripts/check-adoption-integrity.py .` | 通过：`present 178/178`。 |
| `python scripts/validate-governance.py --strict` | 通过，0 error / 0 warning。 |
| `git diff --check` | 通过，无输出。 |
| `python lab/evals/adoption/run-adoption-smoke.py` | 通过，输出 `[adoption-smoke] OK`。 |

## Subagent reports

无。

## Open issues / blockers

- 还需要跑 same-commit staged check，并提交 case branch。
- 后续压力测试应检查：validator/harness 是否仍通过；case 内容是否触发 tracked bytes
  或 root pollution；adoption integrity 是否可复验。

## Exact next steps

1. 跑 `python scripts/check-same-commit.py --staged`。
2. 提交 `worktree-case+agent-r1-adoption-replay`。
3. 回到 feature branch/main branch 做最终压力测试总结。

## Do-not-forget

- 本 case 的原始来源是 AgentR1/Agent-R1 commit `85e0099`。
- `/tmp/agent-r1-adoption-replay/Agent-R1` 是临时 replay clone；持久 case 内容在当前 branch。
