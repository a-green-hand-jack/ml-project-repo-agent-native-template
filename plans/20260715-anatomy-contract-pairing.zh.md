# ANATOMY↔CONTRACT 配对文件（S3）交互式计划

Status: implementing · 2026-07-15 · ref: issue #48 v4 S3 + human 2026-07-15 批注原话「S3 plan
doc 里面提到的问题我希望都一步到位，不要搞什么 MVP 或者最小实现」（见下方「Human 批注区」）；
worktree-pr-flow 实现分支 `feat/s3-anatomy-contract-pairing`

> 这是 human 与 agent 的协商界面：agent 写初稿 → human 在文件里批注 → agent 读 diff、收敛计划 →
> 每次采纳的修订做一个小 commit。**本 plan 原计划只覆盖设计，approved 后才移交 `worktree-pr-flow`
> 实现**——human 2026-07-15 批注要求「一步到位」，本轮收敛与全量实现合并在同一
> `worktree-pr-flow` 分支完成，不再分两轮 PR；下方标注「只设计」的条目已随此批注升级为
> 「设计+实现」，具体见 Plan revision log。

## 当前目标

按 issue #48 v4 S3 的红线（不批量 / 不造双 owner / 每片试点自带证据）设计：

1. root `CONTRACT.md` 的形态——只做「受治理承诺」索引 + 新增边界的约定，不装治理正文本身。
2. 第一个真实试点：把 template-sync 的 TS-1..TS-9 从 `.agent/template-versioning-policy.md`
   的「template-sync 可观察 Contract」一节，迁移为 `scripts/CONTRACT.md`（对应组件 `scripts/`），
   原文件该节改为链接。
3. `scripts/check-anatomy-drift.py` 的 typed relations 如何扩展，让 root `CONTRACT.md` 的受治理
   索引与实际双向声明一致——**只设计，不写代码**。
4. 每条迁入 Contract rule 的证据指针盘点；写不出证据的标 `unverified`。
5. 明确 non-goals，避免落地阶段 scope 蔓延。

## 关键发现（先说清楚，避免重新发明已有机制）

`scripts/check-anatomy-drift.py` 在 #34→#42（本分支 base commit `327e76a` 就是 #42）已经实现了
**通用的 component 级双向 owner 校验**：`contracts` / `contract_for` typed relation 字段
（`.agent/anatomy-protocol.md` 第 49-70 行），带 schema 校验、path-safety、全局唯一 owner、
双向一致性、orphan 检测——且**已经把 `template-sync` 这个 component 接好线**：
`scripts/ANATOMY.md` 的 `contracts:` 声明 owner 是 `.agent/template-versioning-policy.md`，后者
尚未反向声明 `contract_for`（因为它现在是 policy 文件而不是 `CONTRACT.md`，`anatomy-protocol.md`
第 40-47 行明确说「未出现第二个真实独立边界前不建根级承诺 registry，此时不建 CONTRACT.md」——
这正是 v3「弃」的产物，本轮要推翻）。

结论：issue 描述里说的「扩展 paired_contract 双向链接检查」**不需要发明新字段**——
`contracts`/`contract_for` 已经是这个双向链接机制。真正缺的只有两样：

- 一份真实的 `CONTRACT.md` 文件（而不是塞在 `.agent/template-versioning-policy.md` 里的一节），
  让 `template-sync` 这个 component 的 `contract_for` 反向声明有地方落。
- 一份 root `CONTRACT.md`，扮演 guide A 机制 4「显式受治理集合」的角色——这个角色目前完全不存在，
  也完全没有被 `validate_typed_relations()` 校验过。

## 非目标

- 不批量：本 plan 只落地 root `CONTRACT.md` + `scripts/CONTRACT.md`（template-sync）一个试点；
  不为其余 `.agent/*.md` policy 逐一建 `CONTRACT.md`。
- 不在本 plan 里选定「第二个边界」——按红线，等出现真实争议/事故再另开 plan，一个迁一个。
- ~~不实现 validator 扩展代码~~——superseded：human 2026-07-15 批注要求一步到位，
  `validate_governed_index()` 随本轮实现落地，见「决策 3」与 Plan revision log。
- 不改变任何已批准的 TS-1..TS-9 规则语义——纯搬家，不弱化不加强承诺，不重新讨论规则内容。
- S1（承诺→证据闭环机制）不在本 plan 范围，随 #46。
- 不新增独立 validator 文件（扩展写进已有 `scripts/check-anatomy-drift.py`，不新建第二个脚本）、
  不新增 doctrine 文件（`.agent/` 现有文件原地修订，不新建）。

## Branch / worktree

草稿阶段在 `feat/48-checklist-contract`（与 S2 共用同一分支，plan doc 与 S2 分别单独 commit）。
S3 获批（human 2026-07-15「一步到位」批注）后，实现阶段按 `worktree-pr-flow` 惯例另开独立
branch/worktree：`feat/s3-anatomy-contract-pairing`（本 worktree），不复用草稿分支——本次
plan 收敛 commit 与实现 commit(s) 都在这个新分支完成。

## Linked issue / PR

issue #48（v4）。无 PR：实现完成、验证全绿后由执行官起草 PR，PR/merge 走 human gate
（见 `.agent/human-gates.md`），本轮不自行开 PR。

## Allowed paths

plan 收敛：`plans/20260715-anatomy-contract-pairing.zh.md` 与 `memory/doc-lifecycle.yaml`。

实现阶段（本轮，同分支）：

- 新建 `CONTRACT.md`（root，索引受治理组件）；同 commit 更新 root `ANATOMY.md`
  （分层地图 + related_files）与 `scripts/check-agent-harness.py` 的 `ROOT_WHITELIST`。
- 新建 `scripts/CONTRACT.md`（template-sync 试点，正文 owner）。
- `.agent/template-versioning-policy.md`：移除 `contract_for` frontmatter，
  「template-sync 可观察 Contract」一节改为链接。
- `scripts/ANATOMY.md`：`contracts:` 的 owner 路径、related_files、正文反向链接文字改指向
  `scripts/CONTRACT.md`。
- `.agent/anatomy-protocol.md`：改写「未出现第二个真实边界前不建根级承诺 registry」前提段，
  补充 root `CONTRACT.md` 的 `governed_components` typed relation 字段说明。
- `.agent/repo-documentation-topology.md`：truth-direction 表第二行 owner 改为「该边界的
  `CONTRACT.md`（已迁移边界）或 `.agent/` policy 文件（未迁移边界）」，同步 template-sync
  举例路径与「不建根级承诺 registry」段落现状。
- `scripts/check-anatomy-drift.py`：实现 `validate_governed_index()` + 三组对抗 fixture +
  一组正例，接入 `main()`/`self_test()`。
- `memory/doc-lifecycle.yaml`：本条目状态 approved → implementing（branch/worktree 对齐）。

## Forbidden paths

- `lab/data|runs|models` bytes、`checkpoints/`、`wandb/`、`lab/infra/private/`（一贯边界）。
- 不为 template-sync 之外的目录新造任何其他 `CONTRACT.md`（human 批注「一步到位」指做完本 plan
  提到的问题，不等于批量——`.agent/anatomy-protocol.md` 的「不批量」红线继续有效）。
- 不删除、不弱化 TS-1..TS-9 任何一条规则的可观察义务。

## 任务树

- [x] root `CONTRACT.md` 形态定稿（结构、frontmatter、索引字段名）
- [x] `scripts/CONTRACT.md`（template-sync 试点）内容定稿（TS-1..TS-9 迁移映射）
- [x] `.agent/template-versioning-policy.md` 改链接的确切文字定稿
- [x] `check-anatomy-drift.py` 扩展设计定稿并实现（字段名、校验函数、self-test fixture 清单）
- [x] 证据指针盘点表（TS-1..TS-9 逐条确认 evidence 位置不变）
- [x] 需同步更新的既有文档清单确认（anatomy-protocol.md / repo-documentation-topology.md /
      scripts/ANATOMY.md）
- [x] human 批注收敛 → 状态转 approved → 一步到位实现（同分支，见 worktree-pr-flow）

## Human 批注区

> 2026-07-15，human 原话（面向执行官「干将·铸·契约配对」的任务授权，转录留档）：
>
> 「S3 plan doc 里面提到的问题我希望都一步到位，不要搞什么 MVP 或者最小实现。」
>
> [OK] 采纳。解读边界（主 agent 已与 human 对齐，随任务授权一并转录）：本 plan 提到的**所有**
> 问题一次做完——包括原本「只设计不实现」的 `check-anatomy-drift.py` 扩展、root `CONTRACT.md`、
> `scripts/CONTRACT.md`（TS-1..TS-9 全量迁移、原 policy 文件改链接不留双 owner）、
> `anatomy-protocol.md` 前提段改写、证据指针全部落实（失效的标 `unverified` 并显式说明）、以及
> 「未解决问题」节里的项就地拍板记录，不再留给下一阶段。**但**「一步到位」不等于批量：不为
> template-sync 之外的目录新造 `CONTRACT.md`——那不是 plan 提到的问题，超出授权边界。

## 当前决策

### 1. root `CONTRACT.md` 形态

只做索引 + 新增边界约定，不装任何具体组件的治理正文（对应 guide A §6.2 模板，但大幅裁剪——
root 不是某个具体组件的契约，不需要 Purpose/Behavior/Port/Adapters 这些面向单一边界的章节）：

```markdown
---
related_files:
  - ANATOMY.md
  - .agent/anatomy-protocol.md
  - scripts/CONTRACT.md
maintenance: |
  新增/移除受治理组件时，同 commit 更新本索引与对应组件的 contracts/contract_for 声明。
  只登记已通过 human 批准、有真实 owner 文件的边界；不为尚无 CONTRACT.md 的组件占位。
---

# repo CONTRACT（root，受治理组件索引）

## 这是什么

列出当前**显式纳管**的行为承诺边界（guide A 机制 4「显式受治理集合」）。只有出现在下表的
component 才承担完整 CONTRACT 约束；未出现的目录/组件维持现状（承诺正文留在 `.agent/` policy
文件，或尚无独立承诺），不受本索引影响。

## 受治理组件

| component | 归属 ANATOMY | Contract owner | contract_version | 状态 |
| --- | --- | --- | --- | --- |
| `template-sync` | `scripts/ANATOMY.md` | `scripts/CONTRACT.md` | 1 | active |

## 如何新增一条

1. 边界必须真实、独立、已出现过争议或反复问题——不批量、不预建。
2. 新建组件目录下的 `CONTRACT.md`（模板见 `.reference-docs/...Governance_Guide_zh.md` §6.2，
   按本 repo 载体裁剪）。
3. 在对应 `ANATOMY.md` 声明 `contracts:`，在新 `CONTRACT.md` 声明 `contract_for:`
   （字段语义见 `.agent/anatomy-protocol.md`，本文件不复制判定逻辑）。
4. 在本文件表格加一行。
5. 走 `worktree-pr-flow` 的变更自检清单（分类：这属于「改承诺」，需要证据指针）。
```

### 2. template-sync 试点迁移映射

- `scripts/CONTRACT.md` frontmatter：`name: template-sync`、`contract_version: 1`、
  `root_contract: ../CONTRACT.md`、`related_files` 列
  `scripts/template-sync.py`、`scripts/ANATOMY.md`、
  `lab/evals/template-sync/run-template-sync-smoke.py`、`template-manifest.toml`。
- 正文 `Contract rules` 一节：TS-1..TS-9 表格原样迁入，规则 id/描述/evidence kind/evidence
  函数名**逐字保留**（这是本 repo 目前唯一「每条规则配精确 evidence」的先例，已满足 guide A
  机制 5，不需要重新盘点）。
- `contract_for:` 声明：`component: template-sync`，`anatomy: scripts/ANATOMY.md`
  （复用已有字段，不新增语法）。
- `.agent/template-versioning-policy.md` 的「template-sync 可观察 Contract」整节替换为一行：
  「本组件可观察行为承诺的唯一正文 owner 见 `scripts/CONTRACT.md`；本文件不再复制规则正文。」
- `scripts/ANATOMY.md` 第 26-27 行 `contracts:` 的 `owner:` 路径与第 61 行反向链接文字，
  同步指向 `scripts/CONTRACT.md`。

### 3. `check-anatomy-drift.py` 扩展设计与实现

- 新增窄字段，只用在 root `CONTRACT.md`：`governed_components:`（复用 `contracts` 已有的
  `- component: <id>` / `owner: <path>` 缩进 block 语法与 parser，不发明新语法）。
- 新增校验函数 `validate_governed_index()`（或并入 `validate_typed_relations()`），逻辑：
  1. 若 root `CONTRACT.md` 不存在，跳过（当前状态，向后兼容）。
  2. 解析其 `governed_components:` → `index_owner: dict[component, Path]`（复用现成的
     `_extract_dict_list` + `_classify_relation_target`，不重写 path-safety）。
  3. 与已经从 `contracts`/`contract_for` 图算出的 `component_owner`（真实双向声明）做集合对比：
     - 有真实双向声明但未出现在索引 → `rule=governed-index-missing`。
     - 索引声称受治理但无真实双向声明 → `rule=governed-index-orphan`。
     - 两边都有但 owner 路径不一致 → `rule=governed-index-mismatch`。
  4. `--self-test` 补三组对抗 fixture（missing/orphan/mismatch）+ 一组正例（root CONTRACT.md
     索引与真实双向声明一致，不产生 finding），复用现有 self-test 框架，只测这一种新关系，
     不批量扩展其他检查。
- **实现落点**：`validate_governed_index()`，在 `main()` 与 `self_test()` 里与
  `validate_typed_relations()` 的既有 governance 输出合并上报，沿用同一 `GOVERNANCE ...` 行格式
  与 non-strict report / `--strict` fail 语义，不新增第二套输出通道。
- 明确排除项：不做 A§8.2 的符号级/AST 校验、不做 Port 签名比对（issue #48 v4「弃」清单已排除，
  本次不重新讨论）。

## 证据指针盘点

TS-1..TS-9 全部已有 evidence 列（`.agent/template-versioning-policy.md` 现表格第 3-4 列），
迁移时原样带走，逐条核对：

| 规则 | evidence | 迁移后是否变化 |
| --- | --- | --- |
| TS-1..TS-9 | `lab/evals/template-sync/run-template-sync-smoke.py` 内对应 `check_*` 函数 | 不变，只搬家 |

若实现阶段发现某条规则的证据实际已经失效（函数改名/删除），**不得**沿用旧引用蒙混，必须标注
`unverified` 并在 PR 里显式说明——这是本 plan 交给实现阶段的红线，不在此提前下结论。

## 未解决问题（已拍板，不留到实现阶段）

按 human「一步到位」批注，以下三条不再等下一轮 human 批注，由 agent 在本轮就地拍板并执行；
理由与结论如下（后续若有真实反证，走正常 plan 修订，不在此摇摆）：

1. **版本判级章节是否也迁移** → **不迁移，维持现状**。`.agent/template-versioning-policy.md`
   除 TS 表外的 semver 判级/四站闭环/哨兵约定等章节，描述的是「template repo 自身版本策略与
   sync 流程 doctrine」，不是「`template-sync.py` 单次调用的可观察行为承诺」（TS-1..TS-9 的
   范畴）——两者主语不同：TS 表答的是「这次 sync 跑起来会不会做出某个具体承诺内的行为」，
   版本判级答的是「这次改动该打几级 tag」。只迁移「template-sync 可观察 Contract」一节，
   避免把一个不相关的边界一起卷进 `scripts/CONTRACT.md`（会违反「不批量」红线：那等于顺带
   新开了第二个契约边界）。
2. **`governed_components` 字段名** → **保留 `governed_components`，不改名 `governed:`**。
   `governed_components` 与 `contracts`/`contract_for` 的 `component` 语义直接对应，改名不
   带来额外清晰度，且会让「决策 1」草稿里已经写好的字段名和实现脱节，无收益的改名不做。
3. **root `CONTRACT.md` 是否需要 children（多层索引）** → **不需要，现在不建**。当前只有
   一个试点（`template-sync`），多层索引没有真实消费者；`.agent/anatomy-protocol.md`「不批量」
   同一原则：出现第二层治理需求（多个 root 级索引互相嵌套）时再设计，不预建。

## 验证标准

S3 实现阶段（本轮，一步到位）：

- `python scripts/check-anatomy-drift.py --self-test`（含新增三组对抗 fixture + 一组正例）。
- `python scripts/validate-governance.py`
- `python scripts/check-doc-lifecycle.py`
- 人工核对 `.agent/template-versioning-policy.md` 与 `scripts/CONTRACT.md` 无重复正文
  （只保留一行链接）。
- TS-1..TS-9 的 `lab/evals/template-sync/run-template-sync-smoke.py` 回归跑一遍，确认迁移未
  影响任何 evidence 的可执行性。

本 plan 阶段本身：`python scripts/check-doc-lifecycle.py`、`python scripts/validate-governance.py`。

## 下一步

1. ~~human 批注本文档~~ — 已完成：human 2026-07-15 批注「一步到位」，见「Human 批注区」。
2. ~~收敛后状态转 approved~~ — 已完成（本 commit）。
3. 移交 `worktree-pr-flow` 同分支一步到位实现（不再分两轮 PR）：root `CONTRACT.md` +
   `scripts/CONTRACT.md` + `check-anatomy-drift.py` 扩展 + 相关 doctrine 同步，验证全绿后
   PR 走 human gate（PR/merge 由 human 另行批准）。

## Plan revision log

- 2026-07-15 初稿（干将·改·灵台缺口，issue #48 v4 S3）。
- 2026-07-15 收敛：转录 human 批注原话「S3 plan doc 里面提到的问题我希望都一步到位，不要搞什么
  MVP 或者最小实现」；据此取消原「只设计不实现」的分阶段安排，`check-anatomy-drift.py` 扩展与
  「未解决问题」三条并入本轮一次性实现；状态 draft → approved（干将·铸·契约配对，
  issue #48 v4 S3，分支 `feat/s3-anatomy-contract-pairing`）。
