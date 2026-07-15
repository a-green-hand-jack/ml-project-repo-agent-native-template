# ANATOMY↔CONTRACT 配对文件（S3）交互式计划

Status: draft · 2026-07-15 · ref: issue #48 v4 S3（human 2026-07-15 拍板加入，推翻 v3 对成对
CONTRACT.md 的「弃」）

> 这是 human 与 agent 的协商界面：agent 写初稿 → human 在文件里批注 → agent 读 diff、收敛计划 →
> 每次采纳的修订做一个小 commit。**本 plan 只覆盖设计，不实现**——approved 后才移交
> `worktree-pr-flow`，开新 branch/worktree 落地。

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
- 不实现 validator 扩展代码——「设计 root 索引 ↔ 已有 contracts/contract_for 图交叉校验」这条
  本身也只到设计，代码留给 approved 后的实现阶段。
- 不改变任何已批准的 TS-1..TS-9 规则语义——纯搬家，不弱化不加强承诺，不重新讨论规则内容。
- S1（承诺→证据闭环机制）不在本 plan 范围，随 #46。
- 不新增 validator 文件、不新增 doctrine 文件（S2 的硬边界延续到 S3 的实现阶段，本 plan 阶段
  更是零代码改动）。

## Branch / worktree

`feat/48-checklist-contract`（本 worktree；与 S2 共用同一分支，plan doc 与 S2 分别单独 commit）。
S3 若获批，实现阶段应另开独立 branch/worktree（`worktree-pr-flow` 惯例），不复用本轮。

## Linked issue / PR

issue #48（v4）。无 PR：本轮不开 PR，push topic 分支后由上级 agent/human 决定后续。

## Allowed paths

本 plan 阶段：仅 `plans/20260715-anatomy-contract-pairing.zh.md` 与
`memory/doc-lifecycle.yaml`（登记本条目）。

S3 若获批，实现阶段预期涉及（供 human 批注时评估范围，非本轮改动）：

- 新建 `CONTRACT.md`（root，索引受治理组件）。
- 新建 `scripts/CONTRACT.md`（template-sync 试点，正文 owner）。
- `.agent/template-versioning-policy.md`：「template-sync 可观察 Contract」一节改为链接。
- `scripts/ANATOMY.md`：`contracts:` 的 owner 路径与正文反向链接文字改指向新文件。
- `.agent/anatomy-protocol.md`：更新第 40-47 行「未出现第二个真实边界前不建根级承诺 registry」——
  现在已经出现（human 拍板 + 一个真实试点），需要改写这段前提，同时补充 root `CONTRACT.md`
  index 字段的 typed relation 说明。
- `.agent/repo-documentation-topology.md`：truth-direction 表第二行（已获批的可观察行为承诺唯一
  owner）从「该边界的 `.agent/` policy 文件」改为「该边界的 `CONTRACT.md`（已迁移边界）或
  `.agent/` policy 文件（未迁移边界）」，并同步 template-sync 举例路径。
- `scripts/check-anatomy-drift.py`：若「root 索引交叉校验」设计获批，实现该扩展 + self-test
  对抗 fixture。

## Forbidden paths

- `lab/data|runs|models` bytes、`checkpoints/`、`wandb/`、`lab/infra/private/`（一贯边界）。
- 不新建与 template-sync 试点无关的任何其他 `CONTRACT.md`。
- 不删除、不弱化 TS-1..TS-9 任何一条规则的可观察义务。
- 不在本 plan 阶段动 `scripts/check-anatomy-drift.py` 代码本身。

## 任务树

- [ ] root `CONTRACT.md` 形态定稿（结构、frontmatter、索引字段名）
- [ ] `scripts/CONTRACT.md`（template-sync 试点）内容定稿（TS-1..TS-9 迁移映射）
- [ ] `.agent/template-versioning-policy.md` 改链接的确切文字定稿
- [ ] `check-anatomy-drift.py` 扩展设计定稿（字段名、校验函数、self-test fixture 清单）——只设计
- [ ] 证据指针盘点表（TS-1..TS-9 逐条确认 evidence 位置不变）
- [ ] 需同步更新的既有文档清单确认（anatomy-protocol.md / repo-documentation-topology.md /
      scripts/ANATOMY.md）
- [ ] human 批注收敛 → 状态转 approved → 移交 worktree-pr-flow

## Human 批注区

（等待 human 批注；可选前缀 `[OK]` 采纳 / `[改]` 要求修改 / `[?]` 未决）

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

### 3. `check-anatomy-drift.py` 扩展设计（只设计）

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
  4. `--self-test` 补三组对抗 fixture（missing/orphan/mismatch），复用现有 self-test 框架，
     只测这一种新关系，不批量扩展其他检查。
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

## 未解决问题

- `.agent/template-versioning-policy.md` 除 TS 表外还有版本判级（MAJOR/MINOR/PATCH）等其他章节，
  这些描述的是「template repo 自身版本策略」还是「`template-sync.py` 工具的可观察行为承诺」的
  一部分——决定它们留在 policy 文件还是也一起迁入 `scripts/CONTRACT.md`，需要 human 在批注里
  定；本 plan 默认**只迁移「template-sync 可观察 Contract」这一节**，其余章节不动，避免
  过度扩大试点范围。
- `governed_components` 字段名是否合适（对齐 guide A「受治理集合」，也可以叫 `governed:`）——
  由 human 定夺。
- root `CONTRACT.md` 是否需要像 `ANATOMY.md` 一样支持 children（多层索引）？初版建议不需要
  （只有一个试点），出现第二层治理需求时再设计，不预建。

## 验证标准

S3 若获批进入实现阶段：

- `python scripts/check-anatomy-drift.py --self-test`（含新增三组对抗 fixture，若 validator
  扩展本身也在该实现批次内获批）。
- `python scripts/validate-governance.py`
- `python scripts/check-same-commit.py --staged`
- 人工核对 `.agent/template-versioning-policy.md` 与 `scripts/CONTRACT.md` 无重复正文
  （只保留一行链接）。
- TS-1..TS-9 的 `lab/evals/template-sync/run-template-sync-smoke.py` 回归跑一遍，确认迁移未
  影响任何 evidence 的可执行性。

本 plan 阶段本身：`python scripts/check-doc-lifecycle.py`、`python scripts/validate-governance.py`。

## 下一步

1. human 批注本文档（scope、root CONTRACT.md 形态、未解决问题里的两个待拍板项）。
2. 收敛后状态转 `approved`（锚点 + `memory/doc-lifecycle.yaml` 同步）。
3. 移交 `worktree-pr-flow`：开新 branch/worktree，按上面「Allowed paths」落地，PR 走 human gate。

## Plan revision log

- 2026-07-15 初稿（干将·改·灵台缺口，issue #48 v4 S3）。
