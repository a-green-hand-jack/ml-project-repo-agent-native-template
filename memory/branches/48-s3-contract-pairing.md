# Branch Status: 48-s3-contract-pairing

## Purpose

issue #48 v4 S3：ANATOMY↔CONTRACT 配对文件——全量实现（human 2026-07-15 批注「一步到位，不要
搞什么 MVP 或者最小实现」）。基于 PR #50 已合入 main 的 plan doc
`plans/20260715-anatomy-contract-pairing.zh.md`，本轮先收敛 plan（draft → approved →
implementing），再在同分支一次性实现全部问题，不分两轮 PR。

## Parent session

都督·统·治理路线（主 agent，Paseo id `c0675fdd-f8d8-44fb-81df-cc21031a1b5d`）

## Branch / base

- 实际分支名：`feat/s3-anatomy-contract-pairing`（worktree 落位时已预置此名，与任务授权指令中
  写的 `feat/48-s3-contract-pairing` 不一致；沿用实际分支，未重命名——本地 ref rename 属额外
  无必要风险，同 `48-lingtai-round2.md` 记录的既有先例判断）。
- base：`main` @ `c4c7de44c22b94a43a7163c155dc39243e66e959`（含 PR #50 merge），确认与
  `origin/main` 一致（`git merge-base --is-ancestor main HEAD` = true，且 HEAD == origin/main
  于任务开始时）。
- 全程未见 live base 进一步移动（未 fetch 到新 origin/main commit），无需重放。

## Worktree

`/home/user/.paseo/worktrees/1kaz3672/48-s3-contract-pairing`

## Linked issue / PR

issue #48（v4）。无 PR：本轮完成实现并验证全绿后，push 已完成（topic 分支，allow），
PR 起草与开 PR/merge 留给 human/上级 agent 决定（human gate）。

## Owned paths（本轮实际改动）

- `plans/20260715-anatomy-contract-pairing.zh.md`（收敛：human 批注转录 + 正文修订 + 三个
  未解决问题拍板 + 状态 draft→approved→implementing）
- `memory/doc-lifecycle.yaml`（同步该 plan 条目状态/branch/worktree）
- `CONTRACT.md`（新建，root 受治理组件索引）
- `scripts/CONTRACT.md`（新建，template-sync 试点，TS-1..TS-9 + 变更矩阵全量迁移）
- `.agent/template-versioning-policy.md`（移除 `contract_for` frontmatter；
  「template-sync 可观察 Contract」节改为一行链接）
- `scripts/ANATOMY.md`（`contracts.owner` 改指向 `scripts/CONTRACT.md`；related_files 加
  `CONTRACT.md`；Components 表反向链接文字同步）
- `ANATOMY.md`（root，related_files + 分层地图加 `CONTRACT.md` 一行）
- `scripts/check-agent-harness.py`（`ROOT_WHITELIST` 加 `CONTRACT.md`）
- `.agent/anatomy-protocol.md`（truth-direction 前提段改写；新增 `governed_components`
  typed relation 字段文档）
- `.agent/repo-documentation-topology.md`（truth-direction 表 + 「不建根级承诺 registry」
  段落同步现状）
- `scripts/check-anatomy-drift.py`（新增 `validate_governed_index()` + 4 组 self-test fixture）
- `memory/branches/48-s3-contract-pairing.md`（本文件）

## Forbidden paths（遵守情况）

- `lab/data|runs|models` bytes、`checkpoints/`、`wandb/`、`lab/infra/private/` —— 未触碰。
- 不为 template-sync 之外的目录新造 `CONTRACT.md` —— 只有 root + `scripts/` 两份，符合。
- 不删除/弱化 TS-1..TS-9 任一规则的可观察义务 —— 逐条核对 evidence 函数仍存在于
  `run-template-sync-smoke.py`，原样迁移，未改语义。
- 未 push main、未开 PR、未 merge、未新增依赖。

## Anatomy impact

结构性新增：root 新增 `CONTRACT.md`、`scripts/` 新增 `CONTRACT.md`。同 commit 更新了
root `ANATOMY.md`（分层地图+related_files）与 `scripts/ANATOMY.md`
（`contracts.owner`+related_files+Components 表），`check-same-commit.py --staged` 确认
2 处结构改动均已同变更集更新对应 anatomy。

## Claim / evidence impact

无实验 claim；本轮是治理文档 + validator 扩展，证据即 validator/self-test/smoke 输出（见下）。

## 「未解决问题」拍板结论（human 一步到位授权，就地决策不再等下一轮）

1. 版本判级（MAJOR/MINOR/PATCH）等章节 **不迁移**，留在
   `.agent/template-versioning-policy.md`——描述的是 template repo 自身版本策略，与
   `scripts/CONTRACT.md` 描述的「`template-sync.py` 单次调用可观察行为承诺」主语不同。
2. `governed_components` 字段名 **保留不改**（对齐 `contracts`/`contract_for` 的
   `component` 语义，改名无收益）。
3. root `CONTRACT.md` **不建 children**（多层索引）——现在只有一个试点，无真实消费者。

## Invariant

- 单一规范正文 owner：`scripts/CONTRACT.md` 是 template-sync 承诺的唯一正文，
  `.agent/template-versioning-policy.md` 只保留链接，不留双 owner。
- TS-1..TS-9 可观察义务不弱化不加强，evidence 指针必须真实可执行（已用
  `run-template-sync-smoke.py` 回归验证）。
- `validate_governed_index()` 与既有 `validate_typed_relations()` 共用同一 `GOVERNANCE ...`
  finding 格式与 non-strict report / `--strict` fail 语义，不新开第二套输出通道。

## Variation axis

本轮允许改变的唯一维度：把 plan doc 里列出的全部问题（root CONTRACT.md、scripts/CONTRACT.md
试点迁移、drift checker 扩展、doctrine 前提段改写、3 个未决问题拍板）在同一分支一次性做完，
不分「设计 commit」与「实现 commit」两轮 PR。

## Non-goals

- 不为 template-sync 之外的目录新建 `CONTRACT.md`（不批量）。
- 不选定第二个真实边界（等真实事故/争议出现再另开 plan）。
- 不实现 S1（承诺→证据闭环），随 #46。
- 不改变 TS-1..TS-9 任何规则语义。

## Commands run

| command | 结论 |
| --- | --- |
| `git status --short --branch` / `git merge-base --is-ancestor main HEAD` | worktree clean，base 含 PR #50，HEAD == origin/main |
| `python3 scripts/check-doc-lifecycle.py`（plan 收敛 commit 前后） | `OK — 0 error(s), 0 warning(s)` |
| `python3 scripts/check-anatomy-drift.py --self-test` | `OK`，16/16 PASS（含新增 4 组 governed_components fixture：正例 + missing/mismatch/orphan） |
| `python3 scripts/check-anatomy-drift.py --strict` | `OK — 扫描 17 个 ANATOMY.md，0 处结构漂移，0 处 governance 发现` |
| `python3 scripts/validate-governance.py` | `OK`（子检查全绿；`--strict` 因本机未装可选 PyYAML 产生预置 WARN → FAIL，与本次改动无关，环境缺依赖，不在本轮授权范围内安装） |
| `python3 scripts/check-same-commit.py --staged` | `OK —— 2 处结构改动，对应 anatomy 已同变更集更新` |
| `python3 lab/evals/template-sync/run-template-sync-smoke.py` | `OK`——TS-1..TS-9 全部 evidence 函数回归通过，迁移未影响可执行性 |
| `python3 scripts/sync-codex-adapters.py --check` | `OK — 0 issue(s)`（本轮未改 `.claude/`，adapters 天然同步） |

## Latest result

- commit `2b4db3b`：`plan(S3): 收敛 ANATOMY↔CONTRACT 配对 plan——human 一步到位批注，状态转
  approved`。2 files changed（plan doc + doc-lifecycle.yaml）。
- commit `66f1718`：`feat(48-S3): ANATOMY↔CONTRACT 配对全量实现...`。11 files changed
  （root/scripts 两份 CONTRACT.md 新建 + 5 处 doctrine/anatomy 同步 + check-anatomy-drift.py
  扩展 + plan doc/doc-lifecycle 状态推进到 implementing）。
- 已 push `feat/s3-anatomy-contract-pairing` 到 origin（topic 分支，allow，无需 human 批准）。
- 全部验证命令见上表，除已知环境缺 PyYAML 的 `--strict` 预置 warning 外全绿。

## Open risks

- 分支名与任务授权指令不一致（`feat/s3-anatomy-contract-pairing` vs
  `feat/48-s3-contract-pairing`）：已记录、判断不影响功能，未处理（同 `48-lingtai-round2.md`
  记录的既有先例）。
- `--strict` 治理门禁在本机因缺可选 PyYAML 产生 warning→fail：这是环境问题非本轮引入，
  review 时如需要 `--strict` 全绿证据，建议在装有 PyYAML 的环境（如 CI）复验。
- PR 未开：按授权边界，PR/merge 留给 human/上级 agent。

## Exit condition

Plan doc 收敛（approved）+ 全量实现（implementing）+ 全部定向验证通过（已达成）；
branch status 文件完成（本次）；mailbox 汇报都督·统·治理路线；agent 状态置 idle。
