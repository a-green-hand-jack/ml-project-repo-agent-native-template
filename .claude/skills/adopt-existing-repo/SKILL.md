---
name: adopt-existing-repo
description: 把一个已有 Git repo 分步、可验证、尽量无人值守地收敛成本模板的完整形态；适用于迁移旧 ML/research repo，而不是从 GitHub template 新建空项目。
---

# adopt-existing-repo

这是 template-converger，不是简单 overlay。目标是让已有 repo 最终拥有本模板的
control plane、目录形态、validator 与 memory/session 纪律，同时保留原 repo 的可追溯
bytes 与测试能力。

## 适用边界

适用：已有 Git repo 想迁移成 `ml-project-repo-agent-native-template` 形态。

不适用：新项目从零开始（直接 Use this template）；需要人工判断的大规模代码重构；需要移动
数据/模型/checkpoint 大 bytes 的迁移。

## 输入 / 输出 artifact

- 输入：已有 Git repo 路径。
- 输出：目标 repo 的 `lab/docs/audits/template-adoption/state/*.json`、`phase-log.jsonl`、
  `lab/docs/audits/template-adoption-report.md`，以及迁移后的 template 目录形态。

## 需要读取的 ledger

- `plans/20260709-adopt-existing-repo.zh.md`：上一轮 feature contract（原始骨架）。
- `plans/20260712-bootstrap-adoption-proof.zh.md`：本轮语义归类（B）+ 双 agent surface
  报告（B6）的 feature contract。
- `.agent/action-boundary.md`：保护路径和外部副作用边界。
- `scripts/ANATOMY.md`：迁移脚本和 validator 的维护点。

## 语义归类（discover phase，B1-B4）

`discover` 会给**每个 root entry**打一个内置保守四类标签（v1 不做外部规则文件/参数
覆盖入口，见 `plans/20260712-bootstrap-adoption-proof.zh.md` 开放问题 4）：

- `template_control_item`：命中 `CONTROL_ITEMS`（模板自身的顶层结构，如
  `.claude`/`.codex`/`.agents`/`scripts`/`lab`/`AGENTS.md` 等）。目录永远留原处（`scaffold`
  逐文件合并内容）；单文件若与模板同名文件 hash 一致，也留原处；若不一致，`scaffold`
  会把原文件搬到 `human/imported/adoption-conflicts/`、在原路径装模板版本——同样留原处，
  **永远不会**被整体移入 `lab/code/imported/`。
- `conservative_import`：既不是 control item 也不受保护，且导入目标位置尚无内容——整体
  移入 `lab/code/imported/<slug>/<name>`。
- `protected`：命中 `lab/data/**`、`lab/runs/**`、`lab/models/**`、`lab/infra/private/**`、
  `checkpoints`、`wandb`、`.env` 等受保护路径——登记 blocker，不移动、不编辑。
- `conflict`：导入目标位置（`lab/code/imported/<slug>/<name>`）已经有不一致内容（例如上
  一次部分失败的运行留下的）——登记 blocker，不覆盖。

每个 entry 都能在 `adoption-plan.json` 的 `classification` 字段（或 `--dry-run` 的
stdout）里读到 `category` / `target_path` / `reason` / `blocker`。`normalize` 消费的正是
这份归类计划，不是硬编码的二元判断（B4）；`protected`/`conflict` 命中时仍然停下报告
（`--allow-blocked-normalize` 才允许记录后继续）。

## 步骤

1. 在隔离分支/worktree 中操作目标 repo。不要直接在用户的 active branch 上做破坏性尝试。
2. 运行 discover，看归类计划（不落盘时用 `--dry-run`）：

   ```bash
   python scripts/adopt-existing-repo.py /path/to/repo --phase discover --project-name <slug>
   python scripts/adopt-existing-repo.py /path/to/repo --phase discover --dry-run --project-name <slug>
   ```

3. 运行 baseline，记录 tracked file hash、root entries、原生测试结果：

   ```bash
   python scripts/adopt-existing-repo.py /path/to/repo --phase baseline \
     --test-command "python -m unittest discover"
   ```

4. 运行 scaffold，把模板 control plane 写入目标 repo。冲突文件会先搬到
   `human/imported/adoption-conflicts/`，不会覆盖丢失。
5. 运行 normalize，按 discover 的归类计划把 `conservative_import` 项移动到
   `lab/code/imported/<slug>/`；`template_control_item` 永不移动。若命中 `protected` 或
   `conflict`，停下并报告（不静默继续）。
6. 运行 prove，检查原 tracked bytes 仍存在、template governance 可跑、原生测试可在
   imported root 中运行；同时生成 Claude/Codex 双 agent surface 加载清单（见下）。
7. 若只想无人值守跑完整保守路径：

   ```bash
   python scripts/adopt-existing-repo.py /path/to/repo --phase all --policy conservative
   python scripts/check-adoption-integrity.py /path/to/repo
   ```

## Claude/Codex 双 agent surface 报告（prove phase，B6/D2c）

`prove` 复用 A4 为 `bootstrap-project.py` 定义、`scripts/_agent_surface.py` 承载的共享
渲染逻辑，写进 `template-adoption-report.md` 的「Claude/Codex loading checklist」小节，
至少报告：

- Claude/Codex 两侧文件就位计数（信息展示，不是判据）；
- `check-agent-harness.py --strict`（经由本 phase 已跑的 `governance` 结果）与
  `sync-codex-adapters.py --check`（本 phase 单独只读跑一次）这两个 validator 的
  ground-truth 状态；
- `core.hooksPath` 当前状态——**adoption 只读取，不代为设置**（是否覆盖 adopted repo 已有
  的 hooksPath 配置由 human 决定，跟 bootstrap 主动 `git config` 的行为不同）；
- Codex trust 是 out-of-band 前提，adoption 不假装已替 human 完成 trust。

## 验证命令

```bash
python lab/evals/adoption/run-adoption-smoke.py
python scripts/validate-governance.py --strict
git diff --check
```

## 失败时的 handoff

- `normalize` blocked：读 `adoption-plan.json` 的 `classification`/`normalize_blockers`
  字段和 `phase-log.jsonl`，看是哪个 entry 命中 `protected` 还是 `conflict`。不要猜；再决定
  是否加新的可证明策略。
- integrity failed：说明 baseline tracked bytes 找不到同 hash 副本，优先当作 P0。
- governance failed：先修目标模板形态或本模板脚本，不要忽略。
