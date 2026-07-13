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
  `.claude`/`.codex`/`.agents`/`scripts`/`lab`/`AGENTS.md` 等）**且**（对单文件）与模板同名
  文件 hash 一致——留原处，无需 reconcile；目录也留原处（`scaffold` 逐文件合并内容）。
  单文件 hash 不一致/不可比**不算** control item，按 `conflict` 登记 blocker（见下），
  **永远不会**被整体移入 `lab/code/imported/`，也不会被模板版本覆盖。
- `conservative_import`：既不是 control item 也不受保护，且导入目标位置尚无内容——整体
  移入 `lab/code/imported/<slug>/<name>`。
- `protected`：entry 本身**或其内部任意嵌套路径**命中 `lab/data/**`、`lab/runs/**`、
  `lab/models/**`、`lab/infra/private/**`、`checkpoints`、`wandb`、`.env` 等受保护路径
  （例如 `src/checkpoints/model.bin`、目标 repo 自带的 `lab/data/**`）——整个 entry 登记
  blocker，不移动、不编辑、不做部分移动。保护边界扫描覆盖 entry 的**全部后代**，不复用
  性能排除规则（`.venv`/`__pycache__` 等也扫，`src/.venv/**/checkpoints/**` 一样命中）；
  若命中来自 virtualenv/缓存等非数据 artifact，reason 里给出可读的 per-hit 路径交 human
  判断（删掉后重跑 discover），绝不静默跳过。保护位置上的 **symlink 一律算命中**（不解
  引用、不跟随，比如 `lab/data` 是指向外部目录的 symlink）。`scaffold` 对内含保护内容的
  同名 control 目录（如 `lab`）先检测后跳过，不写入也不搬走其中文件，且每次写入前用
  lstat 确认目标位置不是 symlink（绝不透过 symlink 写出 repo）。与模板同 hash 的模板
  自带占位文件（scaffold 合入的 `lab/data/README.md` 等）不算保护命中——该豁免只按完整
  相对路径锚定在 `lab/data`、`lab/runs`、`lab/models`、`lab/infra/private` 前缀之下，且
  永不适用于 symlink，重跑保持幂等。
- `conflict`：root 同名 control 单文件与模板内容不一致/不可比（B1「目标位置已存在不一致
  内容」分支），control-item 位置本身是 symlink（scaffold 绝不透过它写入），或导入目标
  位置（`lab/code/imported/<slug>/<name>`）已经有不一致内容（例如上一次部分失败的运行
  留下的）——登记 blocker，不覆盖、留原处交 human 处理。

每个 entry 都能在 `adoption-plan.json` 的 `classification` 字段（或 `--dry-run` 的
stdout）里读到 `category` / `target_path` / `reason` / `blocker`。`normalize` 消费的正是
这份归类计划，不是硬编码的二元判断（B4），但计划只是提案不是授权：执行前会按当前
文件树重新校验安全不变量——保护路径重扫（同样覆盖全部后代）、category 白名单、
category/blocker 组合不变量（`protected`/`conflict` 必须 `blocker=true`，篡改成 false
直接拒绝）、path 必须是单个真实存在的 root entry（带分隔符/`..`/绝对路径/不存在的
一律拒绝）、`target_path` 必须**精确等于**按当前规则从 entry 名推导出的
`lab/code/imported/<slug>/<name>` 且 resolve 后仍在目标 repo 内、路径上不允许出现
symlink——计划与现状不符（陈旧/被篡改）即拒绝该 entry 并登记 blocker；
`protected`/`conflict` 命中时仍然停下报告（`--allow-blocked-normalize` 才允许记录后
继续）。

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

4. 运行 scaffold，把模板 control plane 写入目标 repo。control 目录**内部**逐文件合并时，
   不一致的内部文件会先搬到 `human/imported/adoption-conflicts/`，不会覆盖丢失；root
   同名 control 单文件不一致则登记 blocker、原样留下（不搬走、不装模板版本）；内含保护
   内容的 control 目录整个跳过并登记 blocker；control-item 位置或其内部任何写入目标
   位置是 symlink 时同样登记 blocker 并跳过（写入前 lstat 检查，绝不透过 symlink 写入）。
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
- `check-agent-harness.py --strict` 与 `sync-codex-adapters.py --check`（两者都由本
  phase 在目标 repo 内单独只读各跑一次）这两个 validator 的 ground-truth 状态——
  `validate-governance.py --strict` 的聚合结果是 report 里独立的 `governance` 字段，
  不再冒充 harness 字段；
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
