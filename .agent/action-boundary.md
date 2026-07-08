# 动作边界

三档：**禁止 / 需问 / 可做**。这是 doctrine 层的解释；机器强制在 `.claude/settings.json`（permissions + hooks），漂移检查在 `scripts/`。三者必须对齐。

## 禁止（deny，除非 human 明确要求并解除）

- 编辑/删除数据与产物 bytes：`lab/data/**`、`lab/runs/**`、`lab/models/**` 权重、`checkpoints/**`、`wandb/**`。
- 编辑私有 overlay 与密钥：`lab/infra/private/**`、`.env`。
- 破坏性 shell：`rm -rf`、`sudo`、`curl ... | sh`。
- 派发无边界的 `general-purpose` 大 agent。

## 需问（ask，先说明意图与影响，等确认）

- git 状态改变：`git commit`、`git checkout`、`git worktree remove`、`git push`（推到已跟踪远端，agent 可触发但每次确认）。
- 依赖变更：`uv add`、`uv sync`、任何 install。
- 计算副作用：`kill`、`sbatch`、`runai`、启动/重启训练。
- 协作副作用：`gh pr create`、`gh pr merge`、release、改远端基础设施。
- 促销结果：把普通结果 promote 成 paper claim。

## 可做（allow，read-only 或低风险）

- `git status` / `git diff*`、`pytest*`、`ruff*`、`mypy*`。
- `tail` / `grep` / `rg` / glob / 只读探索。
- 跑 repo validator：`python scripts/*.py`。

## 副作用半径原则

选择动作时按「错了会怎样」判断：浪费 GPU、污染数据、误导论文、影响导师/合作者可见材料 —— 半径越大越要走 `human-gates.md`。checkpoint / data / remote 至少四层保护：permissions + hook + validator + artifact index。
