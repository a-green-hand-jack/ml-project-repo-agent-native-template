# ELF case v2 — 冻结 adoption baseline（#88 更新者 A）

> **这是 #88 的冻结基线，不是 replay 报告，也不是任何 PASS 裁决。** 目标只有一个：把
> `lillian039/ELF` 从当前 main 落成一份**可审计、可复现、冻结**的 adoption baseline，供独立
> 测试者 B（#84 targeted smoke）与 #85（full replay/mutation）从 exact SHA 接手。findings /
> 探针 / full-replay 结论与 ledger v2 条目**不在本文件范围**（见「非目标」）。

## 三项前置声明

- **Invariant**：外部 case 内容与模板 framework 分层清楚，project-owned 内容不被模板覆盖；不
  编辑/删除 `lab/data|runs|models` bytes、`checkpoints/`、`wandb/`、`lab/infra/private/`、
  `.env`；不启动训练/远程作业/真实外部服务；case 分支只记录 case/adoption baseline，发现模板
  bug 只登记 blocker 不在本分支修模板；不把聊天结论当证据——B 必须能只凭 repo artifact 从
  exact SHA 接手。
- **Variation axis**：仅把 ELF v2 从当前 main 落成可审计、冻结的 adoption baseline。
- **Non-goals**：#84 targeted smoke（validator/TS-12/#78/#79/#80）、#85 full replay / mutation
  matrix / ledger v2 收口、模板 bug 修复、release。本文件不做其中任何一项。

## 冻结坐标

| 维度 | 值 |
| --- | --- |
| case 分支 | `case/elf-refresh-v2` |
| handoff base（模板侧，= `origin/main`，无漂移） | `7c09e90e79c083de1f5db24c593ca40c929cf370` |
| 模板 VERSION（等价 template anchor；本仓是 upstream 模板，无 `.template.toml`） | `v1.3.8` |
| ELF 源（vendored，gitignored） | `lillian039/ELF` @ `5098bf28b5e9b52c329970a7e4e1cc28251c76e6`（branch `main`） |
| ELF tree SHA | `19cd64ec64537d6eee1df50971c0626f29ffb58a` |
| ELF tracked-file 指纹 | `bf7ba438f148484bf5d7319400b290b047191053` |
| ELF license | MIT |
| 完整 provenance | `lab/docs/reference/provenance.md#elf` |

> handoff SHA（本 baseline 提交后的 case 分支 tip）在本 commit 落定后由报告
> `memory/branches/88-elf-refresh-v2-A.md` 回填。

## 迁移清单（migration manifest）

ELF v2 采用 **F6 vendor 面**（只读复现基线），非 `adopt-existing-repo` 的 `imported/` 收编面。

| 内容 | 落位 | 是否进 Git | 说明 |
| --- | --- | --- | --- |
| ELF 完整 clone（含其 `.git`、`assets/` 图示） | `lab/code/external/ELF/` | 否（gitignored `lab/code/external/*`） | 只读引用；fresh worktree 检出为空是预期，B 按 provenance 重 clone |
| ELF 来源/commit/checksum/license | `lab/docs/reference/provenance.md` | 是 | 唯一可复现真源 |
| external/ 平面说明 | `lab/code/external/README.md` | 是 | 目录规则 |
| reference/ 平面说明 | `lab/docs/reference/README.md` | 是 | leaf 平面首次物理落地 |
| gitignore 规则 | `.gitignore`（`lab/code/external/*` + README 例外） | 是 | vendored bytes 不进 Git |
| 本 baseline / manifest / classification | `lab/docs/audits/elf-refresh-v2-baseline.md` | 是 | 本文件 |
| ANATOMY 同步 | `lab/ANATOMY.md`、`lab/code/ANATOMY.md` | 是 | reference/ 落地 + external/ 登记 |

**未新增大 bytes 进 Git**：ELF 无 data/model/checkpoint/run bytes（见下方 classification
`protected=0`），`assets/` 图示随 clone 留在 gitignored external/，未提交。

## Ownership / classification 证据

`adopt-existing-repo.py` `discover --dry-run`（**read-only，无任何写入；clone 保持 pristine，
dry-run 后 `git status --porcelain` = 0 行**）对 ELF 的 root entry 分类：

```
命令：python scripts/adopt-existing-repo.py lab/code/external/ELF \
        --phase discover --dry-run --project-name elf --origin lillian039/ELF
```

| root entry | 类型 | category | 目标位置（假设收编时） | blocker | 说明 |
| --- | --- | --- | --- | --- | --- |
| `LICENSE` | file | conservative_import | `lab/code/imported/elf/LICENSE` | - | 非 control item、非受保护，整体保守导入 |
| `README.md` | file | **conflict** | `README.md` | BLOCKER | 与模板同名 control item 但内容不同（B1），登记 blocker、原样留置交 human |
| `assets` | dir | conservative_import | `lab/code/imported/elf/assets` | - | 图示，整体保守导入 |
| `requirements.txt` | file | conservative_import | `lab/code/imported/elf/requirements.txt` | - | 依赖清单，整体保守导入 |
| `src` | dir | conservative_import | `lab/code/imported/elf/src` | - | 源码，整体保守导入 |

**汇总**：`root_entries=5 template_control_item=0 conservative_import=4 protected=0 conflict=1`

要点（供 B / #85 参考，本文件不下 PASS 裁决）：

- **`protected=0`**：ELF 不含 `lab/data|runs|models`/`checkpoints`/`wandb`/`.env` 类受保护
  bytes——证实这是纯 code+config+figure 仓，vendoring 安全，未触碰保护路径。
- **`conflict=1`（README.md）**：预期行为——任何真实 repo 的 README 都与模板 README 内容不同，
  discover 正确登记为 blocker、原样留置、不覆盖。这是 adoption 机器**按预期工作**的证据，不是
  缺陷。
- 上表是 `--dry-run` 的**分类计划**（若走 imported 收编面会怎么落位），**本轮未执行任何
  scaffold/normalize/move**；ELF 仍在 `lab/code/external/`（vendor 面）。

## 本轮明确未做（留给 #84 / #85）

- 未跑 `adopt` 的 `scaffold`/`normalize`/`prove`（会 mutate；属 replay 演练，#85）。
- 未跑任何对抗性探针（3 新 validator / TS-12 / #78 / #79 / #80）——那是 #84/#85。
- 未跑 ELF 原生测试 / 训练（JAX/TPU + `train.py`，涉计算副作用，边界禁止；B/#85 若需只做只读或
  轻量 smoke，并如实标注）。
- 未写 `stress-test-ledger.yaml` v2 条目、未把旧条目 `elf-template-case-replay` 标 `superseded`
  （ledger 收口是 #85 的 step 9）。
- 未在本 case 分支修任何模板 bug（记录与修复分离）。

## 诚实边界（沿用 plan「诚实边界」段，B 必须继承）

- **#78 D1/D4**：Codex 表面 project hook 未进用户级信任表，`pre_tool_guard.py`/formatter/
  identity 在 Codex 表面 inert。保护路径类/identity 类探针在 Codex 表面须如实标注「hook 未加载，
  无 Codex 侧技术地板」，不得记成双表面等价。取证见
  `memory/branches/78-codex-hook-trust-finding.md`。
- 当前 Codex 表面真正生效的技术地板是 git 层 `.githooks/pre-push`（#80 D2，surface-agnostic）。

## 参考

- plan：`plans/20260718-83-elf-case-refresh.zh.md`（#83）
- 更新者 A 报告 / 接手说明：`memory/branches/88-elf-refresh-v2-A.md`
- 旧 case（历史，不复用）：`stress-test-ledger.yaml#elf-template-case-replay`、
  远端 tag `archive/elf-replay-v14rc`
