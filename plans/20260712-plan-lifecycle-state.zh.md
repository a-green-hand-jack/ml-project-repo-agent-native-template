# Plan 生命周期状态（issue #13）交互式计划

> 这是 human 与 Claude Code 的协商界面：Claude 写初稿 → human 在「Human 批注区」批注 → Claude 读 diff、收敛 → 每次采纳的修订做一个小 commit。实现只在 scope / forbidden paths / verification 清楚后开始。
>
> 触发背景：issue #13 —— human brief / plan doc 批注 / review / decision / human gate 已存在，但"计划是否真的收敛、何时获准进入实现"主要靠 human 与 main agent 的判断，fresh session、不同 runtime 或后续 agent 可能误读阶段。目标是加最小的、可检查的状态，同时不把研究协作压成僵硬表单。
>
> **[2026-07-12 human 亲自拍板，见 Plan revision log 末条]** 覆盖范围与拦截强度两条最大分歧已由 human 直接定案：(1) brief / plan / review / decision **四类都做**生命周期状态，用 YAML 注册表统一登记；(2) **要写机械拦截 hook**（不只 validator advisory），拦"状态/引用完整性"这类可判定事实。以下正文已按此收敛，不再作为 open question。

## 当前目标

给 **brief / plan / review / decision 四类文档**建立**轻量、可解析的生命周期状态**与**审批证据链**，用一份 YAML 注册表把四类文档的状态与关联关系统一登记，并用一个机械拦截点（hook）+ validator 双层守住"防漂移"目标，且：

- 四类文档天然相互关联——一条 brief 牵出一个 plan，plan 收敛后有 review，review 产出 decision。分开做各自的状态机反而制造割裂，所以本轮统一为**一套**状态语义与注册表（human 拍板：四类不是相互独立的，要有统一的审核机制防止 human/agent 不断漂移、反复返工）。
- 每类文档的状态锚点仍是文档正文里一行人类可读的文本（不是 human 要手填的复杂 YAML front-matter）；机器可解析的关联/证据集中在 YAML 注册表里、由 agent 维护。
- 机器可校验的部分（谁批准的、依据哪份 review/decision、approved 前必填字段是否齐全、注册表里的关联引用是否指向真实存在的实体）由 agent 维护、由 validator 校验，复用本 repo 已有的"结构化 ledger + 占位符容忍校验"范式（见下方「现状盘点」），而不是新发明一套平行机制。
- **在 validator（事后强制）之外，新增一个机械拦截点（hook）**：当四类文档的状态跃迁到 approved 之类的"进阶"态、但状态/引用完整性不成立（如缺 scope/forbidden/verification、注册表引用悬空）时，在编辑动作阶段就拦下并提示。理由是 template 结构本该稳定，但项目开发中 human 与 agent 出于各种原因总会想去破坏它——防漂移必须有 hook 兜底，不能只靠事后 validator。
- 最终"是否收敛、是否批准、研究方向/风险是否可接受"仍是 human 判断；机器（无论 hook 还是 validator）只负责**发现遗漏/冲突/过期/悬空引用**这类**可判定的事实**并停下来提示，绝不替 human 做主观判断。

## 非目标

- **不要求 human 编辑复杂 YAML。** plan doc 正文保持纯 Markdown，人类只需要读、批注、以及（若采用状态锚点方案）改一行文本或在 Human 批注区写"批准"。
- 不新造一套与 `DECISIONS.md` / `memory/change-control.yaml` 平行且语义重复的记录系统——新增的 YAML 注册表要与既有结构衔接（引用而非复制其内容），除非评估后证明不可行（见已决策 2）。
- 不实现 issue #14（多 agent 状态/通信/handoff 控制面）——本 issue 只给四类文档加"可检查状态"元数据 + 注册表；#14 未来若要跨 agent 消费这些状态，是它自己的范围。这里只留出稳定、可读的锚点与注册表 schema，不设计通信协议。
- 不实现 issue #12（bootstrap/adoption proof）——只保证新机制不破坏 `adopt-existing-repo.py` / `check-adoption-integrity.py` 现有校验；不去碰 adoption 自身的 phase 状态设计。
- **新增的机械拦截 hook 只拦"可判定的事实"，不做主观判断。** hook 会在编辑动作阶段拦截"状态/引用完整性不成立"的写入（如某文档标 approved 前缺 scope/forbidden/verification、注册表里的关联引用指向不存在的实体、状态跃迁与注册表记录矛盾）。但它**绝不**替 human 判断"研究方向对不对、风险能不能接受、计划是否真的收敛"——这类主观判断仍然是 human gate，hook 不碰。这条边界（机器只判事实、不判主观）从头到尾保留；**变化的只是**：此前"本 issue 不加任何阻断类 hook、强制点只放 validator"的表述已被 human 推翻（见已决策 1 中的 hook 决策），改为"新增一个针对状态/引用完整性的有意义拦截点"。
- 不做 NLP/语义分类器去"读懂"人类批注意图。「提取已确认/待修改/未决问题」的辅助能力止步于**格式约定 + 简单模式匹配**（例如可选前缀 `[OK]` / `[改]` / `[?]`），最终判断仍由 human 在批注区写清楚、agent 读 diff 确认，不自动下结论。
- 本轮（写这份 plan doc）范围只到"方案收敛"，不写实现代码、不改 skill/validator/anatomy/hook 正文。

## 现状盘点（为什么这样设计）

repo 里已经有好几套相邻但不统一的"状态/审批"机制，设计新方案前先盘点，避免重造：

| 机制 | 位置 | 状态枚举/字段 | validator 是否校验内容 |
| --- | --- | --- | --- |
| 轻量 ADR | `DECISIONS.md` 索引 + `human/decisions/*.md` | `proposed · accepted · superseded · rejected` | 否（只有人读） |
| 变更登记账 | `memory/change-control.yaml` | `kind` + `anatomy_updated` / `validator_passed` / `human_approved`（bool） | 否（validator 未解析此文件） |
| 研究证据链 | `lab/research/{claims,evidence,release-gates,regression-matrix}.yaml` | 多枚举 + "离开占位默认状态后必须引用真实、已存在实体" | **是**——`scripts/validate-governance.py` 的 `check_release_gates` / `check_regression_matrix` / `check_evidence_chain` 正是本 issue 想要的范式：占位符默认状态天然通过，一旦状态"进阶"（如 `gate_status` 从 `open` 变成 `passed`），就强制要求它引用的 claim/evidence 真实存在，否则报错。 |
| 分支状态 | `memory/branches/<slug>.md` 模板 | 无枚举，但已有 `Plan doc` 字段（指回 plan doc） | 否 |
| session 锚点 | `.agent/session-protocol.md` | 把 plan doc 列为 session 的状态文件之一 | 否 |
| plan doc 本身 | `plans/*.zh.md` | **无任何机器可解析状态**，只有自由格式的「当前决策」「未解决问题」「Plan revision log」 | 否 |
| `plans/` 目录 | — | 无 README/AGENTS/CLAUDE/ANATOMY 四件套；根 `ANATOMY.md` 分层地图**没有 `plans/` 这一行** | — |

结论：

1. `check_release_gates` / `check_regression_matrix` 的"占位符容忍 + 非默认态需真实证据"模式已经被验证可行、且零依赖，应直接复用到四类文档 lifecycle 校验上（含新 YAML 注册表的引用完整性校验），而不是重新设计一套语义。
2. `plans/` 目录本身缺路由——这是"fresh session 可能误读阶段"风险的直接成因之一：没有地方明确写"哪个 plan 是当前的、哪个已 superseded"。统一注册表正好补上这个路由（不止 plan，brief/review/decision 同理）。
3. 究竟四类文档的状态证据/关联落在扩展的 `change-control.yaml`（已存在但未被校验）、`human/decisions/`（已有状态枚举但语义是"决策"）、还是**新增专属 YAML 注册表**，是证据落点的细节分歧（见已决策 2 的落点方向 + 未解决问题 2 的三选一细化）。human 已锁死"要有一份注册表 + 审核机制"，只余具体落哪个文件的实现取舍。
4. **状态载体必须是 runtime-neutral 的**（见下节）：本 issue 的核心风险之一就是"不同 runtime 误读阶段"，任何依赖 Claude 专属注入通道的方案都会在 Codex 侧留缺口。**新增的拦截 hook 同样受此约束**：hook 要在 `.claude/settings.json` 与 `.codex/config.toml`/`.codex/rules/` 两侧各手写挂一份、不会自动同步（上一轮 Codex 已确认），因此 hook 的**判定逻辑**必须集中在一个 runtime-neutral 的 `python scripts/...` 校验函数里，两侧 hook 只做薄接线去调它，避免逻辑在两 runtime 漂移。

### 双 runtime（Claude / Codex）一致性 —— Codex 侧检查

本 issue 原文点名"不同 runtime 或后续 agent 误读阶段"，即 Claude Code 与 Codex 双 runtime 场景。设计时按以下证据处理：

- **状态锚点走纯文本、runtime-neutral。** 四类文档正文里一行 `Status: ...` 是纯 Markdown，Claude 与 Codex 用完全相同的方式（读文件）解析，不依赖任何 runtime 专属的结构化注入。这是刻意选择：任何"靠 hook 往上下文注入当前状态"的方案都要在两侧各配一份，adapter 生成有已知损耗，反而制造分歧。
- **拦截 hook 的判定逻辑本体走 runtime-neutral 的 `python scripts/...`。** human 已拍板要新增机械拦截 hook（见已决策 1）。为了不在双 runtime 间留缺口：把"状态/引用完整性是否成立"的判定收敛成一个可独立调用的 Python 校验函数（与 validator 复用同一份逻辑），Claude 侧 `.claude/settings.json` 的 PreToolUse 与 Codex 侧 `.codex/config.toml`/`.codex/rules/` 的对等挂点各**手写一份薄接线**去调它。两侧挂点必须同 commit 手动对齐（上一轮 Codex 已确认 hook 不会被 `sync-codex-adapters.py` 自动同步），并纳入 `check-agent-harness.py` 的 parity 检查。
- **Codex 的 hook 事件存在，但当前接线不覆盖真正的 fresh startup。** 本次 Codex（gpt-5.6-sol, medium）一手读配置并实跑 hook：`.codex/config.toml:53-59` 挂了 `UserPromptSubmit`，`:61-68` 只挂 `SessionStart(clear)`，`:70-77` 另挂 `PostCompact`；并没有 `SessionStart(startup|resume)`。`context_continuity.py:23-25` 唯一读取 `memory/current-status.md`，`:37-42` 只接受 `source ∈ {compact, clear}` 或 `PostCompact`，不会读 `plans/`、`plans/ANATOMY.md`，也不会从 plan doc 提取 `Status`。定向探针进一步确认：`source=startup` 输出 0 bytes，`source=clear` 与 `PostCompact` 会回注 `memory/current-status.md`。因此现状只能保证 **clear/compact 后**的状态恢复，不能声称 fresh session 自动感知当前 plan；而且当前 `memory/current-status.md` 没有本 issue plan 的指针/状态，即使 clear/compact 触发也 surface 不出来。实现应把当前 plan 指针写入 `memory/current-status.md`（由现有共享 hook 回注），或另行明确扩展 startup/读取面；`plans/ANATOMY.md` 仅作为 schema/router 时不会被现有 hook自动读取。
- **本次会话对 trust / 自动触发的证据边界。** 当前确为真实 Codex `codex exec` 会话（可见 `CODEX_THREAD_ID`、`CODEX_CI=1`，且项目级 AGENTS/skills 已进入会话），但没有可读的“project hook trust 已批准”状态字段，也没有 hook 执行日志；`UserPromptSubmit` 在低占用时本来就静默，故“未看到提示”既不能证明未触发，也不能单独证明已触发。上述结论依赖已加载的项目配置源码与对同一 hook 的定向实跑，不把 trust 状态或本次 startup 自动触发硬写成已证实。
- **skill / command 是 canonical-in-`.claude/`、sync 到 Codex。** `interactive-plan-doc`、`worktree-pr-flow` 的 canonical 源在 `.claude/skills/`，Codex 侧消费的是 `sync-codex-adapters.py` 生成的 `.agents/skills/<name>/SKILL.md`（见 `scripts/sync-codex-adapters.py:106-115`）。**只要本 issue 改这两个 skill，就必须重跑 sync 并把 `--check` 纳入验证**，否则 Codex 侧拿到的是过期步骤——这是初稿遗漏的一步（已补进任务树与验证收口）。
- **权限面是双份的。** Claude 走 `.claude/settings.json`，Codex 走 `.codex/config.toml` + `.codex/rules/default.rules`。本 issue 既要把新 validator 脚本注册进 allowlist，**又要新增拦截 hook**（human 拍板），因此必须同时更新两侧、且两侧 hook 各手写一份、不会自动同步，不能只改 Claude 侧（否则 Codex 侧留缺口）。

## Branch / worktree

- `feat/13-plan-lifecycle-state` / `.claude/worktrees/13-plan-lifecycle-state`（已切出，干净）。

## Linked issue / PR

- `#13`（本 plan 对应的 issue）。
- 与 `#14`（多 agent 状态/通信/handoff 控制面）、`#12`（bootstrap/adoption proof）有交叉，本 plan 只在「未解决问题」标注边界，不替它们决定范围切分或先后顺序——等 human 拍板。

## Allowed paths（本轮：仅写这份 plan doc）

- `plans/20260712-plan-lifecycle-state.zh.md`（本文件）

### Allowed paths（实现阶段草案，待批注/锁定）

- `.agent/templates/plan-doc.zh.md`（加状态锚点行）；以及 brief / review / decision 三类的模板（若已存在则加同款状态锚点行，若缺模板则视需要新建，路径按 `.agent/templates/` 现有命名）
- `.agent/human-gates.md`（补"四类文档 approved 的证据要求"）
- `.agent/session-protocol.md`、`.agent/anatomy-protocol.md`（视状态机制落地方式，补引用）
- `.claude/skills/interactive-plan-doc/SKILL.md`（canonical；改后必须重跑 sync）
- `.claude/skills/worktree-pr-flow/SKILL.md`（canonical；改后必须重跑 sync）
- `.agents/skills/interactive-plan-doc/SKILL.md`、`.agents/skills/worktree-pr-flow/SKILL.md`（**生成产物，不手改**——由 `python scripts/sync-codex-adapters.py` 重生成；仅当上面两个 canonical skill 改动时同 commit 一起更新）
- `scripts/validate-governance.py`（扩展）或新增 `scripts/check-doc-lifecycle.py`（四类统一，判定逻辑作为可被 hook 复用的函数）
- **新增拦截 hook**：`.claude/hooks/<新文件>.py`（如 `doc_lifecycle_guard.py`，或折进已有 `pre_tool_guard.py`——二选一见任务树）+ `.claude/hooks/README.md`（登记新 hook）
- `.claude/settings.json`（挂载 PreToolUse 拦截点 + 注册新脚本进 allowlist）
- `.codex/config.toml` + `.codex/rules/default.rules`（Codex 侧**手写**对等挂点，不自动同步）
- `scripts/ANATOMY.md`（若新增脚本，登记）
- `plans/ANATOMY.md`（新建——`plans/` 目前缺这个文件，且一旦有 lifecycle/schema 就满足 anatomy-protocol"复杂目录"门槛）；视注册表落点，可能还需 brief/review/decision 所在目录的 ANATOMY 补状态说明
- 根 `ANATOMY.md`（补 `plans/` 一行进分层地图，并让注册表文件在地图里可见）
- **新增 YAML 注册表**（四类文档统一登记，落点见已决策 2；候选如 `memory/doc-lifecycle.yaml` 或扩展 `memory/change-control.yaml`）
- `memory/change-control.yaml`（若方案选择扩展它作为审批证据落点）
- `DECISIONS.md` / `human/decisions/`（decision 类本身就是这里的产物；若方案复用它，或需要新增一条 ADR 记录本次机制决策）
- fixtures 存放路径（新建目录，路径待定，见未解决问题 7）
- 现有 `plans/*.zh.md` 及既有 brief/review/decision 文档（若决定回填 Status 锚点，只加一行，不改正文语义）
- `template-manifest.toml`（若新增/改动文件判定为模板框架层，需登记）

## Forbidden paths

- `lab/data/**`、`lab/runs/**`、`lab/models/**`、`checkpoints/**`、`wandb/**`、`lab/infra/private/**`
- `lab/research/{claims,evidence,release-gates,regression-matrix}.yaml` 的既有条目语义——只参考其校验*模式*，不改研究证据链本身的内容
- **新增的拦截 hook 只判"可判定的事实"（状态/引用完整性），严禁扩张成替 human 做主观判断**（研究方向、风险接受、"是否真的收敛"仍是 human gate）——这条边界是硬约束（见已决策 1 与「非目标」）
- 改 `.claude/settings.json` 权限面/挂 hook 时，**`.codex/config.toml` + `.codex/rules/default.rules` 必须同 commit 手写对齐**，不能只动 Claude 侧（否则 Codex 侧权限/hook 漂移）；两侧 hook 不会被 `sync-codex-adapters.py` 自动同步
- 不手改 `.codex/agents/*.toml` 与 `.agents/skills/**` 生成产物（只经 `sync-codex-adapters.py` 重生成）
- 不 push / 开 PR / merge（human gate）
- 不动 `.claude/worktrees/` 之外的其他 in-flight 分支/worktree

## 任务树（草案，供批注；实现顺序/取舍待收敛）

- [ ] 状态模型设计（四类统一）
  - [ ] 定四类文档（brief / plan / review / decision）共用的状态锚点格式（例如正文开头一行：`Status: <enum> · <date> · <approver/ref>`）；确认四类是否共用同一枚举，还是各类有少量差异态
  - [ ] 定统一枚举：`draft · in-review · approved · implementing · verified · superseded`（覆盖四类，允许某类不经过某些态）
  - [ ] 定四类之间的关联语义（brief → plan → review → decision 的牵引关系如何在注册表里表达）
- [ ] YAML 注册表设计（新增，四类统一登记）
  - [ ] 定注册表 schema：每条记录 = 文档路径 + 类型（brief/plan/review/decision）+ 当前状态 + 关联引用（linked issue / branch / worktree / human approval 引用 / 上游 brief / 下游 review·decision）
  - [ ] 定注册表落点：新增专属 `memory/doc-lifecycle.yaml` / 扩展 `memory/change-control.yaml` / 复用 `human/decisions/`（三选一细化，见未解决问题 2；human 已锁死"要有一份注册表 + 审核机制"）
  - [ ] 复用"占位符容忍 + 非默认态需真实证据"范式：状态一旦"进阶"（如转 approved），强制其引用的 issue/branch/approval/上下游文档真实存在
  - [ ] 明确注册表由 agent 维护、human 不手填复杂 YAML
- [ ] 校验规则设计
  - [ ] 定义"approved 前必填"字段清单（Allowed paths / Forbidden paths / 验证标准 非空、非占位符）
  - [ ] 定义注册表"引用完整性"规则（关联的 issue/branch/worktree/approval/上下游文档必须指向真实存在的实体，悬空即报错）
  - [ ] 定义"过期 approval"判定规则（见未解决问题 5）
  - [ ] 定义"互相冲突批注"时的行为（不自动选边，升级为未解决问题，阻止误判为已收敛）
  - [ ] 仿 `check_release_gates` / `check_regression_matrix` 模式实现四类 doc lifecycle 校验（新脚本 `check-doc-lifecycle.py` 或扩展 `validate-governance.py`）；**判定逻辑抽成可被 hook 复用的函数**
- [ ] 机械拦截 hook 设计（新增，human 拍板）
  - [ ] 定拦截触发面：拦哪个 tool_input 阶段（Write/Edit 目标命中四类文档、或写注册表）、拦什么（状态跃迁到 approved 等进阶态但完整性不成立、注册表引用悬空、状态与注册表矛盾）
  - [ ] 定实现方式：折进已有 `pre_tool_guard.py` 还是独立新增 `doc_lifecycle_guard.py`（二选一，权衡耦合度与可维护性）
  - [ ] hook 只调 runtime-neutral 的 `python scripts/...` 判定函数，逻辑不在 hook 内重复实现
  - [ ] **双 runtime 挂载纪律**：Claude 侧 `.claude/settings.json` PreToolUse + Codex 侧 `.codex/config.toml`/`.codex/rules/` 对等挂点各手写一份、同 commit 对齐、纳入 `check-agent-harness.py` parity（不会被 sync 自动同步）
  - [ ] 明确 hook 的边界护栏：只判可判定事实，拦截信息里明确指向"缺哪个字段/哪个引用悬空"，不输出主观评价，不阻断 human 覆盖（human 可显式绕过）
- [ ] skill / 流程接线
  - [ ] `interactive-plan-doc`：起草时写 `Status: draft` 并在注册表登记；human 批注收敛并明确批准后转 `approved` 并回填 approval 引用；plan revision commit 前跑新校验
  - [ ] `worktree-pr-flow`：进入实现前读 linked plan doc 状态，必须 `≥ approved`；开始实现时状态转 `implementing`（谁来标记见未解决问题 9）；merge 后视验证结果转 `verified`
  - [ ] brief / review / decision 三类的产出/收敛流程如何写各自的状态与注册表条目（若已有对应 skill/流程则接线，若无则在文档里约定谁维护）
  - [ ] 同 topic 出新版 plan 时：旧 plan 顶部标 `superseded` 并指向新文件（不删除、不移动，保留历史）；注册表同步标 superseded
  - [ ] 改动上述 skill 后重跑 `python scripts/sync-codex-adapters.py`，同 commit 更新 `.agents/skills/**` 生成产物
- [ ] 双 runtime 状态感知接线
  - [ ] 把 fresh session 与 compact/clear 恢复拆开验收：已确认现有 `context_continuity.py` 只在 clear/compact 后回注 `memory/current-status.md`，且不读 plan；实现时把“当前 plan / 已 superseded”指针接入 `memory/current-status.md`，并另行决定是否扩展 Codex `SessionStart(startup|resume)`（见未解决问题 10）
  - [ ] 明确状态锚点格式对两 runtime 完全等价、不依赖 runtime 专属注入（写进 `plans/ANATOMY.md`）
- [ ] 结构文档
  - [ ] 新建 `plans/ANATOMY.md`（状态枚举、必填字段、注册表 schema、与 change-control/decisions/branch-status 的连接关系）
  - [ ] 根 `ANATOMY.md` 分层地图补 `plans/` 与注册表文件一行
  - [ ] 视需要补 brief/review/decision 所在目录的 ANATOMY 状态说明
  - [ ] 视需要补 `.agent/session-protocol.md` / `.agent/human-gates.md` 引用（含 hook 与注册表说明）
- [ ] fixtures
  - [ ] 正向（approved 且字段齐全、注册表引用真实）
  - [ ] 缺字段（approved 但 forbidden paths / 验证标准 为空）
  - [ ] 悬空引用（注册表条目引用不存在的 issue/branch/上下游文档）
  - [ ] 过期 approval（approved 但引用的 decision/review 已变为 superseded/rejected，或内容漂移未重新批注）
  - [ ] 互相冲突批注（Human 批注区出现自相矛盾的两条意见，验证不会被误判为"已收敛"）
  - [ ] hook 拦截样本（模拟"标 approved 但完整性不成立"的写入，验证 hook 会拦下并给出精确提示，且 human 显式覆盖可放行）
  - [ ] 定 fixtures 存放路径（本 repo 无先例，见未解决问题 7）
- [ ] 迁移
  - [ ] 现有 `plans/*.zh.md` 及既有 brief/review/decision 文档是否回填 Status 锚点、回填成什么状态（见未解决问题 8）
  - [ ] 现有文档回填进注册表（初始状态）
  - [ ] 若判定为模板框架层能力，登记 `template-manifest.toml`
- [ ] 验证收口
  - [ ] `python scripts/validate-governance.py`
  - [ ] 对 fixtures 跑新校验：正向通过，异常（缺字段/悬空引用/过期 approval/冲突批注）各自精确报错
  - [ ] hook 冒烟：构造"违规写入"确认 Claude 侧与 Codex 侧 hook 都能拦下并给出一致提示；构造 human 显式覆盖确认可放行
  - [ ] `python scripts/check-anatomy-drift.py`
  - [ ] `python scripts/sync-codex-adapters.py --check`（若改了 skill / 新增脚本，确认 Codex adapter 不 stale）
  - [ ] `python scripts/check-agent-harness.py`（本轮必跑——新增 hook + 权限面双侧改动，确认 Claude/Codex 权限/hook 对齐无漂移）
  - [ ] 双 runtime 冒烟：至少分别覆盖 fresh startup 与 compact/clear 恢复；确认两者读到同一当前 plan 指针与 `Status`，且遵守同一 draft/approved/superseded 语义（现状 Codex startup 探针已证明不会由 continuity hook 回注，不能用 clear/compact 冒烟替代）

## Human 批注区

> 在这里批注：改状态覆盖范围、定证据落点、砍某个未解决问题的选项、加约束。我读 diff 后收敛。

## 当前决策

**已由 human 亲自拍板（2026-07-12，非 agent 二审）：**

1. **覆盖 brief / plan / review / decision 四类**（不再只做 plan doc 一类），用一份 YAML 注册表统一登记四类文档的状态与关联。理由：四类本来就相互关联，分开做状态机制造割裂；核心目的是有统一审核机制防止 human/agent 不断漂移、反复返工。
2. **新增机械拦截 hook**（不只 validator advisory）。理由：template 结构本该稳定，但项目开发中 human/agent 总会想破坏它，防漂移必须有 hook 在编辑动作阶段兜底。hook 只拦"状态/引用完整性"这类可判定事实，不替 human 做主观判断（研究方向/风险接受/是否真收敛仍是 human gate）。

**起草时的倾向（仍成立，供 human 推翻或确认的实现细节）：**

- 复用 `check_release_gates` / `check_regression_matrix` 的"占位符容忍 + 非默认态需真实证据"校验范式，而非发明新语义；hook 与 validator 复用同一份判定逻辑。
- 状态锚点走 runtime-neutral 的纯文本 `Status` 行；拦截 hook 的判定逻辑本体也走 `python scripts/...`，两侧 hook 只做薄接线，刻意不依赖 Claude 专属注入，以消除"不同 runtime 误读阶段"的成因（见现状盘点「双 runtime 一致性」）。
- 注册表落点倾向新增专属 `memory/doc-lifecycle.yaml`（vs 扩展 `change-control.yaml` / 复用 `human/decisions/`），但这是实现取舍，仍待 human 确认（见未解决问题 2）。

## 未解决问题

> 编号保持稳定（其他段落按编号引用）。1 与 6 已被 human 拍板收敛，保留在此仅作可追溯记录，不再需要拍板。

1. **[已决策——2026-07-12 human 拍板] 覆盖范围**：原问题是"本轮统一四类状态机，还是先只做 plan doc"。**决定：四类（brief/plan/review/decision）都做**，用统一 YAML 注册表登记。理由：四类相互关联，分开做制造割裂；要有统一审核机制防漂移、防返工。详见「当前决策」1。
2. **审批证据落地位置**：三个候选——(a) 扩展 `memory/change-control.yaml`（已存在但目前 validator 不解析其内容）；(b) 复用 `human/decisions/`（已有状态枚举，但语义是"决策"不是"计划审批"，套用是否牵强）；(c) 新增专属 ledger（如 `memory/plan-status.yaml`）。三者都不要求 human 写复杂 YAML（agent 维护），但决定了后续所有引用怎么连，需要 human 定。
3. **与 #14 边界**：本 issue 只产出"可检查状态"元数据；#14（多 agent 状态/通信/handoff 控制面）未来可能要跨 agent 读取/协调这些状态。本轮是否要为它预留稳定的读取接口（固定路径 + 稳定 schema），还是完全不考虑外部消费者、等 #14 立项时再对齐？谁先做、边界怎么切？
4. **与 #12 边界**：`adopt-existing-repo.py` 的 phase 本质上也是"计划执行到哪一步"，是否也要挂上同一套状态枚举？还是完全独立，本轮只保证不破坏它现有校验（`check-adoption-integrity.py`）？
5. **"过期 approval"判定标准**：按时间窗口（approved 超过 N 天未转 implementing 视为过期）？按内容漂移（plan 正文在 approved 快照之后又被改动但未重新走批注，用 hash/git blame 判定）？还是仅"引用的 decision/review 被 superseded/rejected"这一种触发？可能需要多种规则并存，但本轮是否全做需要 human 拍板优先级。
6. **[已决策——2026-07-12 human 拍板] 是否要更强的机械拦截**：原问题是"validator 非零退出码 + skill 文档步骤是否足够，还是要新增拦编辑动作的 PreToolUse hook"。**决定：要新增 hook**（不只 validator advisory）。理由：template 结构本该稳定，但项目开发中 human/agent 总会想破坏它，防漂移必须有 hook 兜底。此前 context-orchestration 阶段"hook 只发信号"的约束在此**有意破例**——但破例范围严格限定为"拦可判定的状态/引用完整性事实"，不扩张到主观判断。具体拦什么、拦哪个 tool_input 阶段、折进 `pre_tool_guard.py` 还是独立新增，是实现设计（见任务树「机械拦截 hook 设计」），不再是拍板项。详见「当前决策」2。
7. **fixtures 存放路径**：repo 目前没有 `tests/`/pytest 先例，现有 validator 脚本走"直接对 repo 本身 dogfood + 手工构造反例跑一次"的验证方式，没有外部 fixture 文件目录。新建 `scripts/fixtures/plan-lifecycle/` 放人造 plan doc 样本？还是像现有脚本一样把测试用例内联在校验脚本自身（docstring/self-test），不建外部目录？
8. **存量迁移**：现有 `plans/*.zh.md`（如 `20260711-context-orchestration.zh.md`、adopt-existing-repo 的 plan）是否要回填 Status 锚点？如果要，回填成什么状态（多数已实现完成，应标 `verified` 还是 `implementing`）？这算不算触发 anatomy same-commit 规则？
9. **状态转换的 owner**：`draft → in-review → approved` 由 human 批注驱动（清楚）。`approved → implementing` 是否需要 human 二次确认，还是 agent 进入 `worktree-pr-flow` 时可自主标记（现状 `worktree-pr-flow` 的 human gate 只卡在 push/PR/merge，implementing 阶段本身不属于外部副作用）？`implementing → verified` 由谁写、依据什么证据（merge 后自动写，还是要走 fresh reviewer 确认后才写）？
10. **[Codex 侧，已一手核实事实；设计选择仍待 human] fresh session 的状态感知路径**：事实结论是：`context_continuity.py` 只读 `memory/current-status.md`，不读任何 plan 文件；Codex 配置只在 `SessionStart(clear)` 与 `PostCompact` 调它，真实 startup 不调用。定向实跑 `source=startup` 无输出，`clear`/`PostCompact` 才回注 status；当前 status 又没有本 plan 指针。因此“fresh Codex session 自动 surface 当前/superseded plan”目前**不成立**。待 human 选择最小修复：(a) 要求 session 入口纪律主动读 `memory/current-status.md`，plan workflow 同步维护其中的当前 plan 指针；或 (b) 在 (a) 基础上把 Codex `SessionStart(startup|resume)`、Claude 对等事件也接到共享 hook。不要把 `plans/ANATOMY.md` 当成已存在的注入源，除非同时改 hook 读取面。
11. **[Codex 侧，已回答] 双 runtime 冒烟应作为验收证据。** 本次真实 Codex 审查已经证明“配置里有 hook”与“fresh startup 会获得状态”不是同一件事：静态 parity / `sync --check` 无法发现 matcher 未覆盖 startup，也无法证明运行时 trust 与注入结果。因此实现后至少做一次 Claude + Codex 的双 runtime 冒烟，并把 **fresh startup** 与 **compact/clear 恢复**分成两个 case；validator/adapter parity 仍必跑，但不能替代 runtime smoke。受本次会话边界限制，项目 hook trust 是否已批准、`UserPromptSubmit` 是否自动执行没有可读日志可实锤，冒烟记录应显式保存可见注入输出或 hook 日志，而不是以“session 能启动”代替。

## 验证标准（本轮：方案文档本身）

- 本 plan doc 经 human 拍板收敛：问题 1（覆盖范围）、6（是否要机械拦截）已由 human 亲自定案；余下需明确答案的是问题 2（证据/注册表落点）、3（#14 边界）、10（Codex startup 状态感知的修复选项）；问题 11 已由真实 Codex 审查收敛为"必须做双 runtime、双边界冒烟"。
- Allowed paths / Forbidden paths 从"实现阶段草案"收敛为确定清单（含 Codex 侧生成产物与权限面的处理约定）。
- （进入实现阶段后追加，见任务树"验证收口"）：`python scripts/validate-governance.py` 通过；新校验对 fixtures 的正向/三类异常各自给出正确结果；`python scripts/check-anatomy-drift.py` 通过；若改了 skill/脚本/权限面，`python scripts/sync-codex-adapters.py --check` 与（视情况）`python scripts/check-agent-harness.py` 通过，Codex adapter 无 stale/漂移。

## 下一步

- 问题 1（覆盖范围=四类都做）、6（新增机械拦截 hook）已由 human 拍板，不再待批注。等 human 就余下分歧落笔：问题 2（注册表/证据落点三选一）、3（#14 边界）、10（采用主动入口纪律，还是同时扩展 startup hook）；问题 11 不再待拍板。
- 实现阶段按问题 10 的选择接入当前 plan 指针；无需再把“读 `context_continuity.py` 源码”列为探索任务，本轮已完成源码核实与 startup/clear/PostCompact 定向探针。
- 收敛后：决定是先出一个"仅状态模型 + 校验脚本"的最小实现 PR，还是把 skill 接线 / anatomy 更新一次性做完；随后转 `worktree-pr-flow`。

## Plan revision log

- 2026-07-12 初稿。盘点现状（`DECISIONS.md` 状态枚举、`change-control.yaml`、`release-gates`/`regression-matrix` 的占位符容忍校验范式、`branch-status.md` 的 Plan doc 字段、`plans/` 目前无 ANATOMY/根路由），据此起草状态模型草案与任务树；未解决问题聚焦覆盖范围切分、证据落点三选一，以及与 #12/#14 的边界。
- 2026-07-12 第二意见审查（Claude Opus 4.8，代替额度耗尽的 Codex gpt-5.6-sol 二审；人类最终批准仍待定）。补 Codex 侧缺口：新增「双 runtime 一致性」子节（状态锚点/validator 走 runtime-neutral、Codex SessionStart/UserPromptSubmit 挂点证据、skill canonical→`.agents/` sync 义务、两侧权限面对称）；Allowed/Forbidden paths 补 `.agents/skills/**` 生成产物与 `.codex/` 权限面处理约定；任务树加 sync 重生成、双 runtime 状态感知接线；验证收口加 `sync-codex-adapters.py --check` / `check-agent-harness.py` / 可选双 runtime 冒烟；新增未解决问题 10（`context_continuity.py` 是否 surface 当前 plan 状态，待读源码核实）、11（是否要双 runtime 冒烟作为验收证据）；强化"不加阻断类 hook"非目标的 runtime 论据。
- 2026-07-12 Codex（gpt-5.6-sol, medium）真实二审（区别于上一轮 Opus 代打；人类最终批准仍待定）。一手核实 `context_continuity.py` 只读 `memory/current-status.md`，Codex 仅在 `SessionStart(clear)`/`PostCompact` 接线，startup 探针无输出且当前 status 无 plan 指针，故否定“fresh session 已自动感知 plan”的原推断；问题 10 收敛为两个待选修复路径，问题 11 收敛为必须分别验证 startup 与 compact/clear 的双 runtime smoke；同时记录本会话无法从可读日志实锤 hook trust 与静默 `UserPromptSubmit` 自动触发，避免过度声称。
- 2026-07-12 **human 亲自拍板**（非 agent 二审）。对两个最大 open question 直接定案并落地整合：(1) **覆盖范围=四类都做**——brief/plan/review/decision 统一生命周期状态，用一份 YAML 注册表登记各文档的 draft/in-review/approved/implementing/verified/superseded 状态及其关联的 issue/branch/worktree/human approval/上下游引用（理由：四类相互关联，分开做制造割裂，要有统一审核机制防漂移防返工）；(2) **新增机械拦截 hook**——不只靠事后 validator，在编辑动作阶段拦"状态/引用完整性"这类可判定事实（如 approved 前缺 scope/forbidden/verification、注册表引用悬空），并明确修正此前"本 issue 不加阻断类 hook"的非目标（改为有意破例、但严格限定拦可判定事实、不替 human 做主观判断）。据此扩写「当前目标/范围/非目标/现状盘点结论/Allowed·Forbidden paths/任务树/验证标准」，任务树新增「YAML 注册表设计」与「机械拦截 hook 设计」两个顶层分组，并把 hook 的双 runtime 手写挂载纪律写进设计约束；原未解决问题 1、6 就地改写为「已决策」保留可追溯性。
