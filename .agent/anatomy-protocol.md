# ANATOMY 协议

`ANATOMY.md` 是给 coding agent 的结构地图，不是 README、不是教程、不是设计长文。它防止 repo 膨胀、结构漂移和 ownership 误判。

## 回答的问题

```
这个目录代表什么概念？哪些文件拥有关键行为？谁调用谁？
哪些状态会持久化？结构变化时哪些地图必须同步更新？
```

## 规则

- 根 `ANATOMY.md` 只做 router：列复杂目录及其子 anatomy，不解释全系统。
- **只有复杂目录**才有自己的 `ANATOMY.md`：多文件协作、跨模块调用、持久状态、生命周期、路由、schema、workflow、权限、或 agent 需独立推理的目录。
- single-file trivial helper、空目录、静态资源、无独立概念边界的 leaf 目录**不要**写 placeholder anatomy。
- 每个结构 claim 尽量引用代码坐标：`path/to/file.py:42` 或 `:42-90`。
- 目标 ~80 行，硬上限 ~120 行。写不短通常是代码边界不清，不是文档该加长。
- **same-commit rule**：移动/改名/拆分/合并/删除文件或函数、改 ownership/调用关系/持久状态 shape/lifecycle/routing/workflow，都算结构改动，必须同 commit 更新相关 anatomy。
  由 `scripts/check-same-commit.py` 机器强制（在「有自己 anatomy 的目录」里 A/D/R 文件却没同变更集更新该 anatomy → 拦）：pre-commit hook（`.githooks/`）+ CI 各查一道。逃生 `SAME_COMMIT_SKIP=1` / `--no-verify`（文档卫生，非安全地板）。
- refactor 前先 grep 被动文件名在所有 `ANATOMY.md`、index YAML、ledger 里的引用。

## 模板

见 `.agent/templates/anatomy.md`。

## Drift checker 的边界

`scripts/check-anatomy-drift.py` 只能挡 missing file / out-of-range line；语义是否仍正确要 agent 打开代码行验证。

## 模板 repo 的特例

本模板里许多目录是**空脚手架**。它们的 `ANATOMY.md` 描述**意图结构**并显式标注「template scaffold」，暂不放指向不存在代码的 `file:line` 引用——等真实代码落地再补 line-addressed citation，避免 citation rot。

## Truth direction：结构地图不持有行为承诺（见 issue #33）

`ANATOMY.md` 只回答「是什么、在哪、谁调用谁、状态归谁」——结构现实的 truth direction 是代码本身：
现实变了改地图，不是改地图去要求现实迁就旧结构。

若某个组件已经拥有独立的、已获批的**可观察行为承诺**（输入输出、错误、顺序、兼容性、breaking
判级），承诺正文只归属承诺 owner（例：`template-sync.py` 的行为承诺归 `.agent/template-versioning-policy.md`
的「template-sync 可观察 Contract」一节），本文件不建对应 `CONTRACT.md`。此时该组件的 `ANATOMY.md`：

- 只反向链接承诺 owner，不复制 rule 正文（详见 `repo-documentation-topology.md` 的 truth-direction 表）；
- 实现与该承诺不一致时以承诺为准，实现视为 bug，不得为变绿而弱化承诺。

未出现第二个真实、独立的行为承诺边界前，不为此建根级承诺 registry；一次只纳管一个真实边界。

## typed relation schema（静态图，由 `scripts/check-anatomy-drift.py` 强制）

只认四个固定 frontmatter 字段，与通用 `related_files` 完全分离。窄 restricted parser 只支持下面
这种缩进 block 语法，**不支持 inline/flow 写法**（如 `children: [a, b]`）；顶层每个 key 只能出现
一次，重复声明与不支持的 shape 都会被 fail closed 成 schema 违规：

```yaml
parent: <repo-root-relative path>       # 单值，本 ANATOMY 的父 ANATOMY
children:                                # 本 ANATOMY 的子 ANATOMY 列表
  - <repo-root-relative path>
contracts:                               # 本 ANATOMY 承认某 component 的行为承诺归 owner 文件
  - component: <id>                      # （truth direction 见上一节），必须 component 全局唯一 owner
    owner: <repo-root-relative path>
contract_for:                            # 承诺 owner 文件反向声明自己治理哪个 ANATOMY 的哪个
  - component: <id>                      # component；必须与对应 contracts 双向一致
    anatomy: <repo-root-relative path>
```

target 一律 repo-root-relative（不是相对当前文件），拒绝空值/绝对路径/`..`/repo 外逃逸/不存在的路径。
只纳管**显式声明**这些字段的节点；未声明的目录是合法 ungoverned leaf，不受影响。当前唯一纳管的
静态图：root `ANATOMY.md` ↔ `scripts/ANATOMY.md`（parent/children）与 component `template-sync`
的双向 contract（`scripts/ANATOMY.md` ↔ `.agent/template-versioning-policy.md`，schema 见上一节）。

字段语义、fail-closed 规则细节以 `scripts/check-anatomy-drift.py` 的
`validate_typed_relations()`/`--self-test` 为准，本节不复制判定逻辑，只说明字段形状与当前纳管范围。
