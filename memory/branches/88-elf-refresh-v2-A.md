# Branch Status: 88-elf-refresh-v2-A（ELF case v2 冻结 adoption baseline，更新者 A）

## 三项前置声明

- **Invariant**：外部 case 内容与模板 framework 分层清楚，project-owned 内容不被模板覆盖；不
  编辑/删除 `lab/data|runs|models` bytes、`checkpoints/`、`wandb/`、`lab/infra/private/`、`.env`；
  不启动训练/远程作业/真实外部服务；case 分支只记录 case/adoption baseline，发现模板 bug 只登记
  blocker、不在本分支修模板；不把聊天结论当证据——独立测试者必须能只凭 repo artifact 从 exact
  SHA 接手。
- **Variation axis**：仅把 ELF v2 从当前 main 落成可审计、冻结的 adoption baseline。
- **Non-goals**：#84 targeted smoke（validator/TS-12/#78/#79/#80）、#85 full replay / mutation
  matrix / ledger v2 收口、模板 bug 修复、release。本阶段不做其中任何一项。

## Purpose

#83 ELF case 刷新的第一阶段（#88 更新者 A）：重新 clone 公共仓 `lillian039/ELF`，迁移进模板
vendor 面，落成一份**可由独立测试者 B 从 exact SHA 复验的冻结 adoption baseline**。

## Parent session

总调度（#83 → #88/#84/#85 顺序推进）。本 session 只做 #88；#84 交测试者 B，#85 后续。

## Branch / base

- branch：`case/elf-refresh-v2`（Paseo 实际返回的 worktree/branch = 权威）。
- base（handoff base，模板侧）：`7c09e90e79c083de1f5db24c593ca40c929cf370`
  - 开始时核对：HEAD = origin/main = live `git ls-remote origin main` = `7c09e90`，**无漂移**。
- 等价 template anchor：本仓是 upstream 模板，无 `.template.toml`；VERSION = **v1.3.8**。
- handoff SHA（B 接手点）：本 baseline commit 后的 `case/elf-refresh-v2` tip；B 直接
  `git fetch && git checkout case/elf-refresh-v2`。精确 tip SHA 在最终 handoff 汇报给主调度。

## Worktree

`/home/user/.paseo/worktrees/1kaz3672/elf-refresh-v2`（Paseo 托管，绑定 `case/elf-refresh-v2`）。
所有写入均在此 worktree 内（`pwd` + `git rev-parse --show-toplevel` 已自查一致）。

## Linked issue / PR

- issue：#88（#83 的第一阶段；#83 是 #82 的原生 sub-issue）。
- PR：**无**。本阶段不开 PR / 不 merge / 不 close，验收留主调度。

## Owned paths（本 commit 实际改动）

Tracked（进 Git）：

- `.gitignore`（+ `lab/code/external/*` 忽略 + README 例外）
- `lab/code/external/README.md`（新增，external 平面说明）
- `lab/docs/reference/README.md` + `lab/docs/reference/provenance.md`（新增，reference 平面首次落地 + ELF provenance）
- `lab/docs/audits/elf-refresh-v2-baseline.md`（新增，冻结 baseline + migration manifest + classification）
- `lab/ANATOMY.md`、`lab/code/ANATOMY.md`（同 commit anatomy 同步：reference/ 落地 + external/ 登记）
- `plans/20260718-83-elf-case-refresh.zh.md`（draft→implementing + 任务树 + revision log）
- `memory/doc-lifecycle.yaml`（plan 条目升 implementing + branch/worktree/approval）
- `memory/branches/88-elf-refresh-v2-A.md`（本文件）

Untracked / gitignored（不进 Git）：

- `lab/code/external/ELF/`（ELF 完整 clone，`git check-ignore` 确认忽略；B 按 provenance 重 clone）

## Forbidden paths（本阶段未触碰）

模板源码（`scripts/`、`.agent/`、`.claude/hooks/` 等）；`lab/data|runs|models` bytes、
`checkpoints/`、`wandb/`、`lab/infra/private/`、`.env`；不 push main、不 PR、不 merge、不 close。

## Anatomy impact

物理新建 `lab/docs/reference/`（provenance）与 `lab/code/external/`（vendored 面）→ 同 commit 更新：

- `lab/ANATOMY.md`：`reference/`（provenance 记录）与 `audits/` 已落地；仅 `research-narrative/` 仍未物理创建。
- `lab/code/ANATOMY.md`：Children 表新增 `external/` 行（gitignored vendored 源，README only，按需出现）。

`external/` 与 `reference/` 均为 README-only leaf，无 typed-relation 字段 → `check-anatomy-drift.py`
视为合法 ungoverned leaf，不拉入 governed set。

## Claim / evidence impact

- 无对外实验 claim。ELF provenance/checksum 是可复现证据，非结果宣称。
- **未写** `stress-test-ledger.yaml` v2 条目，**未把**旧条目 `elf-template-case-replay` 标 `superseded`
  （ledger 收口 = #85 step 9；提前写即 overclaim，明确不做）。

## Plan doc

`plans/20260718-83-elf-case-refresh.zh.md`（#83），status = `implementing`（本阶段推进）。

## ELF 冻结源（provenance 摘要，详见 `lab/docs/reference/provenance.md#elf`）

| 维度 | 值 |
| --- | --- |
| source | `https://github.com/lillian039/ELF`（public，MIT） |
| branch / commit | `main` / `5098bf28b5e9b52c329970a7e4e1cc28251c76e6`（2026-06-26 "update"，clone 时 clean） |
| tree SHA | `19cd64ec64537d6eee1df50971c0626f29ffb58a` |
| tracked-file 指纹 | `bf7ba438f148484bf5d7319400b290b047191053`（`git ls-files -s \| git hash-object --stdin`） |
| 规模 | 29 tracked 文件（16 .py + 7 .yml + 3 图片 asset + LICENSE/README/requirements）；无 LFS；~14M（~13M 图示） |
| 项目 | ELF: Embedded Language Flows，JAX/TPU 扩散语言模型（arXiv:2605.10938） |

## Commands run（exact）

```bash
# 状态核对
pwd; git rev-parse --show-toplevel; git rev-parse HEAD; git rev-parse origin/main
git ls-remote origin main            # 7c09e90 —— 无漂移

# 身份
python3 .claude/hooks/agent_name_set.py "干将·迁·ELF基线"

# clone（网络 clone 已获总调度批准；skip LFS smudge）
mkdir -p lab/code/external
GIT_LFS_SKIP_SMUDGE=1 git clone https://github.com/lillian039/ELF lab/code/external/ELF
# provenance 采集
( cd lab/code/external/ELF && git rev-parse HEAD; git rev-parse HEAD^{tree}; \
  git status --porcelain | wc -l; git ls-files | wc -l; git ls-files -s | git hash-object --stdin )
git check-ignore -v lab/code/external/ELF     # IGNORED

# ownership/classification（read-only dry-run，clone 保持 pristine）
python scripts/adopt-existing-repo.py lab/code/external/ELF \
  --phase discover --dry-run --project-name elf --origin lillian039/ELF
# -> root_entries=5 template_control_item=0 conservative_import=4 protected=0 conflict=1

# 验证（见 Latest result）
python scripts/check-doc-lifecycle.py
python scripts/validate-governance.py
python scripts/check-anatomy-drift.py
python scripts/check-same-commit.py --staged
git diff --check
```

## Latest result

提交前最终验证轮（base 无漂移，live origin/main 仍 `7c09e90`）——全绿：

- `check-doc-lifecycle` → OK 0 error/0 warning
- `check-anatomy-drift` → OK 扫描 17 个 ANATOMY.md，0 结构漂移，0 governance 发现
- `check-same-commit --staged` → OK，5 处结构改动对应 anatomy 已同变更集更新
- `git diff --cached --check` → 干净（exit 0）
- `validate-governance`（含 strict）→ OK 0 error/0 warning（check-agent-harness /
  check-anatomy-drift / check-doc-lifecycle / check-outcome-ledger-schema /
  validate-experiment-state / check-provenance-chain 13 pass / check-capability-catalog 47 项 全绿）

## 未执行的测试 / 检查（诚实标注，非遗漏）

- **ELF 原生测试 / 训练未跑**：ELF 是 JAX/TPU + `train.py` 训练项目，跑测试/训练涉计算副作用，
  违反动作边界（不启动训练/作业/真实外部服务）。baseline 只做只读 provenance + classification。
  B/#85 若需，只做只读或轻量 smoke，并如实标注。
- **未跑 adopt 的 `scaffold`/`normalize`/`prove`**：会 mutate；属 #85 replay 演练。本阶段只跑
  read-only `discover --dry-run`。
- **未跑对抗性探针**（3 新 validator / TS-12 / #78 / #79 / #80）：#84/#85 范围。

## Open risks / blockers

- **无 release-blocking blocker**。ELF `protected=0` 证实无受保护 bytes，vendoring 安全。
- 诚实边界（B 必须继承，见 baseline 文档与 plan「诚实边界」段）：**#78 D1/D4** —— Codex 表面
  project hook 未进用户级信任表，`pre_tool_guard`/formatter/identity 在 Codex 表面 inert；保护
  路径类/identity 类探针在 Codex 表面须标「hook 未加载，无 Codex 侧技术地板」，不得记双表面等价。
  当前 Codex 表面真正生效的技术地板是 git 层 `.githooks/pre-push`（#80 D2）。取证见
  `memory/branches/78-codex-hook-trust-finding.md`。本阶段不修 #78 D1/D4（需 human P8 决策）。
- 可复现性依赖 `provenance.md` 准确：external/ bytes gitignored，B 在 fresh worktree 检出为空是
  预期，须按 provenance exact commit 重 clone。

## B 的接手说明（ready_for_B）

1. `git fetch && git checkout case/elf-refresh-v2`（handoff SHA = 该分支 tip）。
2. `lab/code/external/ELF/` 为空（gitignored）→ 按 `lab/docs/reference/provenance.md#elf` 的复现命令
   重新 `git clone` + `git checkout 5098bf2`，核对 tree/指纹一致，即得逐字节相同的 ELF 源。
3. 冻结坐标与 classification 见 `lab/docs/audits/elf-refresh-v2-baseline.md`；据此做 #84 targeted
   smoke（3 新 validator + TS-12 + #78/#79/#80 修复点），各写各报告（硬分工 A≠B）。
4. 发现模板 bug → 独立修复分支/PR（`worktree-pr-flow`），**不在 case 分支改**（记录与修复分离）。
5. 涉 session-cached 配置（hook/settings/Codex 信任表）的复验用**全新顶层 session**（F10/F15）。

## Exit condition

- [x] base 无漂移、记录 HEAD/base/clean
- [x] 重新 clone ELF + provenance/checksum/license/dirty 齐全
- [x] vendored bytes gitignored、只 track provenance/README
- [x] ownership/classification 证据（adopt discover dry-run）
- [x] migration manifest + 等价 template anchor
- [x] plan draft→implementing（doc-lifecycle 一致）
- [x] 门禁全绿（validate-governance 含 strict / check-anatomy-drift / check-doc-lifecycle / check-same-commit / git diff --check）
- [ ] 冻结 baseline commit 已 push、可被独立 worktree checkout（提交后立即 push topic branch）
- ready_for_B：门禁全绿已达成；push 成功后 = **true**（精确 handoff SHA 在最终汇报给主调度确认）
