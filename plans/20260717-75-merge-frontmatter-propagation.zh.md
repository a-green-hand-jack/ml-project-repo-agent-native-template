# #75 缺口① merge 分类锚文件 frontmatter 结构键传播 交互式计划

Status: draft · 2026-07-17 · ref: issue #75 缺口①；human 已拍板「真修，走 plan」（PR #76 合入说明，
块 C 由 `memory/branches/74-75-strict-gaps.md` 转本 plan 深化）

> 这是 human 与 agent 的协商界面：agent 写初稿 → human 在文件里批注 → agent 读 diff、收敛计划 →
> 每次采纳的修订做一个小 commit。**本 plan 只覆盖设计与决策收敛，approved 后才移交
> `worktree-pr-flow` 另开分支实现**——本轮任何 commit 都不改 `scripts/`、`.agent/`、
> `scripts/CONTRACT.md` 本体。

## 当前目标

为 #75 缺口①（merge 分类锚文件的 frontmatter schema 新增不随 `template-sync.py` 传播，导致
`--strict` 下 `check-anatomy-drift.py` 的 `parent-child-bidirectional` 判定 FAIL）设计一条
可实现、可测试、边界清楚的修复路径，供 human 批注定稿后移交实现。

## 问题陈述

- 根 `ANATOMY.md` 在 `template-manifest.toml` 里是 `merge` 分类（导航文件，骨架与下游自定义
  内容混排）。`template-sync.py` 对 merge 文件的合同（`scripts/CONTRACT.md` TS-3）是「只替换
  `<!-- template:begin -->…<!-- template:end -->` 哨兵块内的字节，块外内容——含 frontmatter——
  原样保留」（`scripts/template-sync.py:254-259`，`down_text.replace(down_block, up_block, 1)`，
  完全不touch frontmatter 段）。
- `.agent/anatomy-protocol.md:54-79` 定义的 typed relation schema（`parent`/`children`/
  `contracts`/`contract_for`）**写在 frontmatter 里**，被 `check-anatomy-drift.py` 的
  `validate_typed_relations()` 读取，强制 `parent-child-bidirectional`：declare `parent: X`
  的节点必须出现在 `X` 的 `children:` 列表里，反之亦然（`scripts/check-anatomy-drift.py:474-491`）。
- 上游 v1.3.8 根 `ANATOMY.md` frontmatter 新增了 `children: [scripts/ANATOMY.md, ...]`
  （与既有 `related_files:` 并存，不是改名）。任何用 `merge` 分类同步这次上游更新的下游，
  拿到新的哨兵块正文，但 frontmatter 原地不动——若下游根 `ANATOMY.md` 此前没有 `children:`
  字段，追平后依然没有，`--strict` 直接 FAIL；若下游此前**已经**手工声明了自己的
  `children:`（比如加了一条下游专属子 anatomy），也不会被上游新增的条目追平，双向声明可能
  部分缺失。
- 严重度：**MINOR**——只在 `--strict` 口径拦截，出厂默认门禁（非 strict）不受影响，
  `memory/branches/58-g5-replay-*.md` 与 G5 replay 已确认默认门禁全绿。但两个模板组件（
  「frontmatter 结构性变更不传播」 vs 「anatomy checker 要求 frontmatter 双向声明」）此刻
  互相矛盾，且矛盾对下游沉默——sync receipt 可以是 `result=pass`，不提示这个已知边界。
  受影响面：所有把根 `ANATOMY.md`（及未来任何 merge 分类且声明了 typed relation 的锚文件）
  当作 merge 追平的下游 repo。

## 已有设计基础（深化 `memory/branches/74-75-strict-gaps.md` 块 C 的调查，不重复从零核查）

- `.agent/template-versioning-policy.md:72-73` 已明文记录这是「已知边界」：「frontmatter 在块外，
  不随 sync 更新……frontmatter 的结构性变更需人工同步或把该文件改判为 framework」——问题不是
  没被想到，是从未被操作化成可观察行为。
- `scripts/CONTRACT.md` TS-3 是**锁定合同**，页脚明文「弱化/删除 TS-1..TS-11 任一规则……默认
  视为实现 bug，不得为让测试变绿而改弱本文件；改变承诺需 human 在 issue/PR 明确批注批准」。
  同表另一行把「五类 ownership 语义变化（如……merge 哨兵约定改变）」判为 **MAJOR**。
  → 任何触碰「merge 文件块外内容原样保留」这句话本身的方案，都要过这道 human gate。
- 前一执行官（干将·修·门禁缺口，PR #76）已评估四个候选并推荐："不建议现在实现 ①/③（都需要
  单独 human 批准 + 更细致设计），排除②；推荐把④从纯 prose 升级成主动 WARN 信号"——但**未**
  深入到"①能不能设计成不需要改 TS-3 措辞的加法式新增规则"这一步，本 plan 在此基础上补上这层
  设计，并把 human 已经拍板"真修"这件事纳入考虑（不是继续停在④）。

## 候选方案对比

### ① 让 typed relation 结构键跟着 sync 传播

进一步拆成两个语义不同、human-gate 成本不同的子路径：

**①a：直接放宽 TS-3——对 merge 文件整体 frontmatter 做合并**

- 做法：`plan_sync()`/`apply_plan()` 对 `kind=merge` 文件，除了哨兵块，也 diff/合并整个
  frontmatter 段。
- 问题：这直接修改「merge 文件块外内容原样保留」这句被锁定的承诺文字本身，按 TS-3 变更矩阵
  判 **MAJOR**，且改变的不只是 typed relation 四个字段——任何下游在 frontmatter 里塞的其他
  自定义键（`related_files` 之外的私货）都可能被波及，`related_files:` 本身语义是否也要
  合并没有定论。**blast radius 不可控，不推荐**。

**①b（推荐子路径）：新增一条独立、加法式规则，只对四个 typed relation 窄字段做结构化追平**

- 做法：不改「merge 文件块外保留」这句话的适用范围——把 typed relation 追平设计成一个
  **正交于 kind 分类的新增步骤**，只对声明了 `parent`/`children`/`contracts`/`contract_for`
  这四个窄字段（`.agent/anatomy-protocol.md:56-70` 的 restricted schema，`children`/
  `contracts` 是 list、其余是 scalar/dict-list）的文件生效，独立于 framework/merge/scaffold
  哪一类：
  - `children` / `contracts`（list 语义）：**union，不覆盖**——下游列表 ∪ 上游列表，去重，
    保留下游独有的条目（否则会吞掉下游自己声明的子 anatomy，例如下游在 `lab/` 下自建了
    `lab/ANATOMY.md` 并让根 `ANATOMY.md` 声明 `children` 包含它——覆盖式合并会丢掉这条）。
  - `parent` / `contracts.owner`（scalar 语义）：下游已声明则保留（下游可能因为项目结构不同
    而合法地指向不同 owner），下游缺失才从上游补齐。
  - 这不属于「弱化 TS-3」——TS-3 说的是 merge 文件**哨兵块外的内容**保留，这里新增的是一个
    **独立于哨兵机制之外的窄字段追平通道**，性质更接近「新增受管路径」（变更矩阵里 MINOR
    那一档：「新增可选参数/新受管路径」），不需要改写 TS-3 措辞本身——但**需要新增一条规则
    编号**（候选 TS-12）写清楚这个新通道的可观察行为，且需要 human 确认这个定性成立
    （见下方「需要 human 拍板」）。
  - 实现耦合点：`check-anatomy-drift.py` 已经有这四个字段的 restricted parser
    （`_frontmatter`/`_extract_scalar`/`_extract_scalar_list`/`_extract_dict_list`，
    `scripts/check-anatomy-drift.py:160-234`）。`template-sync.py` 若要读同一批字段，
    要么导入/复用这份 parser（避免两份语法实现分叉），要么独立实现一份并靠测试保证等价——
    这是一个真实的架构决策，两个脚本目前分属不同治理边界（`template-sync` 有
    `scripts/CONTRACT.md`；`check-anatomy-drift.py` 目前无独立 CONTRACT），需要 human 认可
    "共享 parser" 是否要提炼成第三个模块，还是接受两份实现+一组一致性测试。
- 改动面：`scripts/template-sync.py`（新增一个 `sync_typed_relations()` 步骤，`plan_sync()`
  产出的 action 里加一个新枚举，如 `merge-typed-relation-update`）、`scripts/CONTRACT.md`
  新增 TS-12（需 human 批准新规则文字）、`.agent/anatomy-protocol.md` 补一节说明这个新通道、
  `.agent/template-versioning-policy.md:72-73` 的「已知边界」段落改写为「已操作化，见 TS-12」。
- 测试成本：中——需要 `lab/evals/template-sync/run-template-sync-smoke.py` 新增至少 4 组
  fixture（上游新增 upstream-only 字段/下游有额外自定义条目需保留/下游完全无 typed relation
  frontmatter 应 no-op/上游与下游同时声明但值冲突的 scalar 字段如何提示），以及
  `check-anatomy-drift.py --self-test` 侧确认追平后双向声明确实转绿。
- 风险：中——设计本身不复杂，但触及两个锁定文档（CONTRACT.md 新规则 + anatomy-protocol.md），
  且是本 repo 第一次让 `template-sync.py` 读 frontmatter 语义（此前它对 merge 文件完全
  frontmatter-blind），需要谨慎收窄字段集合，避免变成事实上的①a。

### ② 把 `ANATOMY.md` 类锚文件从 `merge` 改判 `framework`

- 复核前一轮排除理由：根 `ANATOMY.md` 正文含「分层地图」表格，各下游实际子目录结构、
  是否有 `lab/`、`deliverables/` 拆分等**天然不同**，这部分内容是下游按自己仓库现实填写的，
  不是模板骨架——`framework` 分类的语义是「仅字节不同就整体覆盖」（TS-3），会在下一次 sync
  直接冲掉下游改过的分层地图表格与任何下游在块外自定义区写的说明。
- 复核结论：**维持排除**。这不是「重新考虑一下」能改变结论的问题——`framework` 分类的
  「整体覆盖」语义与「块内骨架/块外下游内容混排」的文件结构根本冲突，除非先把 body
  也拆成哨兵块（那就是重新发明 merge 机制，等于绕了一圈回到①）。**不推荐，本 plan 不再展开**。

### ③ anatomy checker 从 body 内容/repo 全局扫描派生 `children`，不依赖 frontmatter 显式声明

- 做法：`validate_typed_relations()` 不要求父节点 frontmatter 显式声明 `children:`，改为
  反向扫描全仓库所有 `ANATOMY.md` 的 `parent:` 声明，自动推导双向关系（子节点单侧声明即生效）。
- 收益：彻底消除"上游新增 children 需要传播到下游"这个需求本身——sync 完全不用碰
  frontmatter，缺口①从根上消失。
- 代价：改变 `.agent/anatomy-protocol.md` 与 `.agent/anatomy-protocol.md` 隐含的既定设计
  意图——该文档目前把「父节点显式声明 children」视为**故意的 opt-in 治理确认**（父节点知情
  同意有这个子节点，不是子节点单方面认领就算数）。改成纯反向派生会移除这层显式确认语义，
  这是治理哲学层面的变化，不是 bug 修复，需要 human 单独就"要不要放弃双向显式声明"表态——
  与①的"新增字段"性质不同，这是"移除既有确认机制"，说服成本更高。
- 附带效果：若采纳③，`children:` 字段本身在 root/scripts 这类已纳管节点上会变得冗余（
  可派生），需要决定字段是否保留（向后兼容 vs 精简 schema）。
- 测试成本：低到中——`check-anatomy-drift.py` 本身改动集中、self-test fixture 复用度高，
  但需要新增"父节点完全没声明 children、子节点声明了 parent"的正例（目前这是负例，见
  `scripts/check-anatomy-drift.py:671-672` 的 `oneway_pc` fixture，需要反转语义）。
- **不推荐作为本轮方案**：改变既定治理设计意图的决策成本高于问题本身的严重度（MINOR），
  且与①相比不能减少"要不要接受设计变化"这层 human 决策，只是换了个位置（从 template-sync
  换到 anatomy checker）。

### ④ 折中：sync 时对 merge 文件 frontmatter 漂移主动 WARN（不自动改）

- 做法：`template-sync.py` 的 `plan_sync()` 对 `kind=merge` 文件额外做一次 frontmatter
  顶层 key 的 diff（上游 vs 下游），若上游新增了下游没有的顶层 key，在 dry-run/apply 输出与
  receipt `warnings` 里显式提示，指向 `.agent/template-versioning-policy.md` 的既有说明，
  但**不改写任何字节**。
- 改动面最小：只读 diff + 输出提示，不涉及合并语义歧义，不touch TS-3 措辞，receipt 新增字段
  按变更矩阵是 MINOR（「receipt schema 增字段，向后兼容」）。
- 局限：**不解决 `--strict` FAIL**本身——下游拿到 WARN 后仍要手工编辑 frontmatter 补
  `children:`，`parent-child-bidirectional` 检查依旧会 FAIL 直到人工介入。这是"让已知边界
  可观察"，不是"消除已知边界"。
- 与①b 不冲突，可以是①b 落地前的**过渡态**，或者作为①b 的一个子步骤（①b 的
  "typed relation 追平"本身就隐含了在 union 后仍需要报告"哪些字段是从上游自动补的"）。

### 方案对比小结

| 方案 | 是否消除 `--strict` FAIL | 是否需要改锁定合同 | blast radius | 推荐度 |
| --- | --- | --- | --- | --- |
| ①a 整体合并 frontmatter | 是 | 改 TS-3 措辞（MAJOR） | 高，不可控 | 不推荐 |
| ①b 窄字段加法式追平（新 TS-12） | 是 | 新增规则，不改 TS-3 措辞（但需 human 认可"不算弱化"） | 中，字段集合收窄可控 | **推荐** |
| ② merge 改判 framework | 是（但引入新问题） | 改分类本身 | 高，冲掉下游分层地图 | 排除 |
| ③ checker 反向派生 | 是 | 改 anatomy-protocol.md 治理哲学 | 中，但决策成本高 | 不推荐（本轮） |
| ④ 主动 WARN，不改字节 | 否（仍需人工） | 不改任何合同 | 低 | 作为①b 的过渡/子步骤，不单独作为终态 |

## 推荐方案（供 human 批准，非最终结论）

**推荐 ①b**：新增独立加法式 TS-12（typed relation 窄字段追平，union 语义、scalar 缺失才补），
不改写 TS-3 既有措辞，`template-sync.py` 新增一个与哨兵机制正交的追平步骤。同时把④的「WARN
可观察」并入①b 的 receipt 输出（追平动作本身要在 receipt/dry-run 里如实报告改了哪些 typed
relation 字段，不静默）——④不再作为独立终态，而是①b 的一部分。

理由：human 已明确"真修，走 plan"（不是继续停在纯文档④），①b 是唯一在不触碰 TS-3 措辞本身
的前提下能真正让 `--strict` 转绿的路径；②排除、③决策成本高且是换个地方的同类问题，本轮
不比①b 更优。①b 的核心风险（union 语义歧义、parser 复用）是可通过测试收敛的工程问题，
不是需要另一层 human 决策的设计哲学问题——但 TS-12 的确切规则文字仍需 human 过目定稿
（TS 表是锁定合同，即便是"新增"也要写进 `scripts/CONTRACT.md` 并获批）。

## 实现计划（若批准）

1. `scripts/CONTRACT.md`：新增 **TS-12**（typed-relation-propagation）规则行——精确措辞由
   human 批注定稿，草案：「对声明了 `parent`/`children`/`contracts`/`contract_for` 的下游文件
   （不限 kind），sync 额外做一次 typed relation 窄字段追平：list 字段（`children`/`contracts`）
   取上游∪下游去重 union；scalar 字段（`parent`/`contract_for.anatomy` 等）下游已声明则保留，
   缺失才从上游补齐；此追平不改写 frontmatter 其余字段与任何 body 内容；receipt 新增
   `typed_relation_sync` 字段如实报告改了哪些文件的哪些字段」。
2. `scripts/template-sync.py`：
   - 新增 `_read_typed_relations(text) -> dict`（复用/移植 `check-anatomy-drift.py` 的
     restricted parser，具体复用方式见下方待决问题）。
   - `plan_sync()` 对**所有** kind（不只 merge）的下游已存在文件，额外算一次 typed relation
     diff，产出新 action（如 `typed-relation-update`）与既有 merge/framework action 并存
     （同一文件可能既是 `merge-update` 又需要 `typed-relation-update`，需理清 action 叠加
     还是互斥的执行顺序）。
   - `apply_plan()` 新增对应写入逻辑：只重写 frontmatter 里这四个字段对应的行/块，不touch
     其余 frontmatter 内容与 body。
   - receipt 新增 `typed_relation_sync` 字段（changed file → field → old/new 值），走
     `governance_data_gap` 同款「新增字段、旧字段语义不变」MINOR 判级。
3. `.agent/anatomy-protocol.md`：typed relation schema 一节补充说明"这四个字段现在有独立于
   `kind` 分类的 sync 追平通道，见 `scripts/CONTRACT.md` TS-12"。
4. `.agent/template-versioning-policy.md:72-73`「已知边界」段落改写：不再说"结构性变更需人工
   同步"，改为"结构性变更由 TS-12 自动追平（union/补齐），见 scripts/CONTRACT.md"。
5. 测试：
   - `lab/evals/template-sync/run-template-sync-smoke.py` 新增 fixture 组（清单见①b 分析，
     至少 4 组：新增字段传播/下游自定义条目保留/无 typed relation 时 no-op/parser 一致性）。
   - `check-anatomy-drift.py --self-test` 现有 16 组全部保持绿，另加一组"经 template-sync
     追平后的 frontmatter 应转绿"回归（可复用 ELF 或搭一个最小 downstream fixture）。
   - **ELF replay 复验**（呼应 human 交办里提到的验收方式）：找一份此前在 `--strict` FAIL 的
     ELF 下游 replay（`memory/branches/58-g5-replay-*.md` 提到的 ELF 场景），跑一次改造后的
     `template-sync.py`，确认 `check-anatomy-drift.py --strict` 从 FAIL 转绿，且不产生
     `unexpected`/`content_mismatches`。
6. `memory/doc-lifecycle.yaml`：本条目 approved → implementing（绑定新 branch/worktree）。

## 风险与非目标

- **非目标**：本轮不处理"contract_for/contracts 的合并语义"以外的任何 frontmatter 字段
  （如 `related_files:`）——那不在 typed relation schema 内，维持 TS-3 原状不动。
- **非目标**：不解决"上游删除/改名某个 typed relation 目标路径"这种更复杂的场景（如上游把
  `scripts/ANATOMY.md` 拆分成两个文件），本轮只做"新增/保留"方向的 union+补齐，删除/改名
  场景留给 MAJOR 判级路径（TS-2 已有 MAJOR gate，人工 reconcile）。
- **风险 1**：若 TS-12 措辞不够精确，可能被下一次实现悄悄放宽成①a——实现阶段的 self-test
  必须包含"下游声明了本地专属 children 条目，追平后必须仍在"这一负例，防止 union 退化成覆盖。
- **风险 2**：`template-sync.py` 从"对 merge 文件 frontmatter-blind"变成"读四个字段"，
  是一个真实的行为面扩展，需要在 PR 里显式对照 TS-12 逐条给出 evidence（本 repo 的
  evidence-chain doctrine 要求），不能只靠"看起来对"就合并。
- **风险 3**：`check-anatomy-drift.py` 与 `template-sync.py` 的 parser 复用方式若选"各自
  实现+一致性测试"，两份实现长期可能漂移——需要在实现阶段选定后写进两个脚本各自的头部注释
  互相指向，防止未来只改一边。

## 需要 human 拍板的具体问题

1. **是否批准新增 TS-12（而不是修改 TS-3 措辞本身）**——本 plan 的核心前提是"新增窄通道
   不算弱化 TS-3"，但这个定性本身需要 human 明确认可，因为 TS-3 变更矩阵里没有专门条目
   覆盖"新增一个与 merge 哨兵机制并行的字段级追平通道"这种情况。
   `[?]`
2. **`children`/`contracts` 的 union 语义是否接受**（下游自定义条目永久保留、只增不删）——
   还是希望有明确的"上游权威覆盖"选项（例如上游显式删除某条目时应该怎么处理，本 plan 当前
   排除为非目标）。`[?]`
3. **parser 复用方式**：`template-sync.py` 直接 `import` `check-anatomy-drift.py` 的 restricted
   parser 函数，还是各自独立实现 + 一致性测试？前者引入脚本间依赖（目前两者互相独立、分属
   `scripts/CONTRACT.md` 与尚无 CONTRACT 的 `check-anatomy-drift.py`），后者有长期漂移风险。
   `[?]`
4. **实现阶段是否跟 #75 缺口②同分支**（缺口②已在 PR #76 修完并合入 main）——本 plan 建议另开
   独立 branch/worktree（`worktree-pr-flow` 惯例），不复用已关闭的 `fix/74-75-qualification-
   strict-gaps`。`[?]`

## Branch / worktree

草稿阶段：`plan/75-merge-frontmatter`（本 worktree）。approved 后按 `worktree-pr-flow` 另开
独立实现分支（建议 `fix/75-typed-relation-propagation`，具体命名由实现阶段执行官定）。

## Linked issue / PR

issue #75（父 #52 P5，源 #58，round1 前例 #60–#63）；块 A/B 已由 PR #76 合入 main
（commit `c681a18`）；本 plan 承接块 C（缺口①）。

## Allowed paths

- `plans/20260717-75-merge-frontmatter-propagation.zh.md`
- `memory/doc-lifecycle.yaml`（本条目登记/状态流转）

## Forbidden paths

- `scripts/template-sync.py`、`scripts/CONTRACT.md`、`.agent/anatomy-protocol.md`、
  `.agent/template-versioning-policy.md`、`scripts/check-anatomy-drift.py` ——均只读，
  待 approved 后移交实现阶段修改。
- `lab/data|runs|models` bytes、`checkpoints/`、`wandb/`、`lab/infra/private/`（一贯边界）。
- 不 push main、不 merge、不建 PR（本轮只是 plan 草稿）。

## 任务树

- [x] 读 #75 缺口①全文 + 块 C 既有调查 + TS-3 + anatomy-protocol.md + template-sync.py 实现
- [x] 深化四候选方案对比（新增①a/①b 拆分，明确 union 语义与 parser 复用两个待决问题）
- [x] 给出推荐方案与理由
- [x] 起草实现计划（供 approved 后移交）
- [ ] human 批注收敛
- [ ] 状态 draft → in-review → approved
- [ ] 移交 `worktree-pr-flow` 另开分支实现

## Human 批注区

（待 human 批注；批注前缀约定：`[OK]` 采纳 / `[改]` 要求修改 / `[?]` 未决）

## 当前决策

（尚无——待 human 批注后填写，收敛时把「需要 human 拍板的具体问题」逐条落成决策记录于此）

## 未解决问题

见「需要 human 拍板的具体问题」四条，均标 `[?]`，收敛前不得转 approved。

## 验证标准

本 plan 阶段：`python scripts/check-doc-lifecycle.py`、`python scripts/validate-governance.py`。

实现阶段（approved 后，供实现分支参考，非本 plan 验收范围）：

- `lab/evals/template-sync/run-template-sync-smoke.py`（新增 TS-12 fixture 全绿）
- `python scripts/check-anatomy-drift.py --self-test`
- ELF 下游 replay：追平前 `--strict` FAIL → 追平后 `--strict` 转绿，且无
  `unexpected`/`content_mismatches`
- `python scripts/validate-governance.py --strict`

## 下一步

1. 等待 human 批注本文档（四个 `[?]` 决策点 + 整体方案是否认可①b）。
2. 读 diff 收敛，状态转 in-review → approved。
3. approved 后移交 `worktree-pr-flow`，另开分支按「实现计划」落地。

## Plan revision log

- 2026-07-17 初稿（师爷·谋·frontmatter传播，issue #75 缺口①，分支
  `plan/75-merge-frontmatter`，深化自 `memory/branches/74-75-strict-gaps.md` 块 C）。
