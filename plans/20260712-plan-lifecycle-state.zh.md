# Plan 生命周期状态（issue #13）交互式计划

> 这是 human 与 Claude Code 的协商界面：Claude 写初稿 → human 在「Human 批注区」批注 → Claude 读 diff、收敛 → 每次采纳的修订做一个小 commit。实现只在 scope / forbidden paths / verification 清楚后开始。
>
> 触发背景：issue #13 —— human brief / plan doc 批注 / review / decision / human gate 已存在，但"计划是否真的收敛、何时获准进入实现"主要靠 human 与 main agent 的判断，fresh session、不同 runtime 或后续 agent 可能误读阶段。目标是加最小的、可检查的状态，同时不把研究协作压成僵硬表单。

## 当前目标

给 plan doc（优先）及其关联的 brief / review / decision 建立**轻量、可解析的生命周期状态**与**审批证据链**，且：

- 状态锚点是 plan doc 正文里一行人类可读的文本（不是 human 要手填的 YAML front-matter）。
- 机器可校验的部分（谁批准的、依据哪份 review/decision、approved 前必填字段是否齐全）由 agent 维护、由 validator 校验，复用本 repo 已有的"结构化 ledger + 占位符容忍校验"范式（见下方「现状盘点」），而不是新发明一套平行机制。
- 最终"是否收敛、是否批准"仍是 human 判断；机器只负责**发现遗漏/冲突/过期**并停下来提示，不替 human 拍板。

## 非目标

- **不要求 human 编辑复杂 YAML。** plan doc 正文保持纯 Markdown，人类只需要读、批注、以及（若采用状态锚点方案）改一行文本或在 Human 批注区写"批准"。
- 不新造一套与 `DECISIONS.md` / `memory/change-control.yaml` 平行且语义重复的记录系统——优先扩展既有结构，除非评估后证明不可行（见未解决问题 2）。
- 不实现 issue #14（多 agent 状态/通信/handoff 控制面）——本 issue 只给 plan doc 加"可检查状态"元数据；#14 未来若要跨 agent 消费这些状态，是它自己的范围。这里只留出稳定、可读的锚点，不设计通信协议。
- 不实现 issue #12（bootstrap/adoption proof）——只保证新机制不破坏 `adopt-existing-repo.py` / `check-adoption-integrity.py` 现有校验；不去碰 adoption 自身的 phase 状态设计。
- 不新增会**机械拦截**编辑动作的 PreToolUse hook（如"没有 approved plan 就不让你写文件"）。沿用现有纪律：hook 只发信号，强制点是 validator（exit code）+ human/CI 主动跑。是否要更强的机械拦截，留作未解决问题，默认不做。**额外的 runtime 理由**：validator 是 `python scripts/...`，两 runtime 完全等价；而阻断类 hook 要在 `.claude/settings.json` 与 `.codex/config.toml`/`.codex/rules/` 两侧各配一份、且 adapter 生成有已知损耗（matcher 语义、sandbox 粒度不完全等价），更容易在 Codex 侧留缺口——这与本 issue"不同 runtime 一致"的目标相悖。所以把强制点放在 runtime-neutral 的 validator 上是双 runtime 场景下的更稳选择。
- 不做 NLP/语义分类器去"读懂"人类批注意图。「提取已确认/待修改/未决问题」的辅助能力止步于**格式约定 + 简单模式匹配**（例如可选前缀 `[OK]` / `[改]` / `[?]`），最终判断仍由 human 在批注区写清楚、agent 读 diff 确认，不自动下结论。
- 本轮（写这份 plan doc）范围只到"方案收敛"，不写实现代码、不改 skill/validator/anatomy 正文。

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

1. `check_release_gates` / `check_regression_matrix` 的"占位符容忍 + 非默认态需真实证据"模式已经被验证可行、且零依赖，应直接复用到 plan lifecycle 校验上，而不是重新设计一套语义。
2. `plans/` 目录本身缺路由——这是"fresh session 可能误读阶段"风险的直接成因之一：没有地方明确写"哪个 plan 是当前的、哪个已 superseded"。
3. 究竟状态证据落在 `change-control.yaml`（已存在但未被校验）、`human/decisions/`（已有状态枚举但语义是"决策"不是"计划审批"）、还是新 ledger，是本轮要收敛的核心分歧（见未解决问题 2）。
4. **状态载体必须是 runtime-neutral 的**（见下节）：本 issue 的核心风险之一就是"不同 runtime 误读阶段"，任何依赖 Claude 专属注入通道的方案都会在 Codex 侧留缺口。

### 双 runtime（Claude / Codex）一致性 —— Codex 侧检查

本 issue 原文点名"不同 runtime 或后续 agent 误读阶段"，即 Claude Code 与 Codex 双 runtime 场景。设计时按以下证据处理：

- **状态锚点走纯文本、runtime-neutral。** plan doc 正文里一行 `Status: ...` 是纯 Markdown，Claude 与 Codex 用完全相同的方式（读文件）解析，不依赖任何 runtime 专属的结构化注入。这是刻意选择：任何"靠 hook 往上下文注入当前状态"的方案都要在两侧各配一份，adapter 生成有已知损耗，反而制造分歧。**强制点（validator）是 `python scripts/...`，本身 runtime-neutral**——这一点应写进设计约束，作为不选"阻断类 hook"的额外理由（见非目标末条）。
- **Codex 确有 SessionStart / UserPromptSubmit 等价物。** 证据：`.codex/config.toml` 已挂 `SessionStart(startup|resume|clear)` 与 `UserPromptSubmit`，其中 `context_continuity.py` 在 `SessionStart(clear)` 与 `PostCompact` 恢复状态连续性。所以"fresh session 感知当前 plan 状态"的接线在两侧都有挂点——**但这些 hook 实际会不会把「当前/superseded plan」surface 出来，取决于 `context_continuity.py` 读哪些文件**，本轮尚未核实（见未解决问题 10）。倾向：状态感知路径应收敛到已被两侧 hook 共享的 runtime-neutral 文件（`memory/current-status.md` 或新的 `plans/ANATOMY.md` 当前指针），而不是新增 runtime 专属注入。
- **skill / command 是 canonical-in-`.claude/`、sync 到 Codex。** `interactive-plan-doc`、`worktree-pr-flow` 的 canonical 源在 `.claude/skills/`，Codex 侧消费的是 `sync-codex-adapters.py` 生成的 `.agents/skills/<name>/SKILL.md`（见 `scripts/sync-codex-adapters.py:106-115`）。**只要本 issue 改这两个 skill，就必须重跑 sync 并把 `--check` 纳入验证**，否则 Codex 侧拿到的是过期步骤——这是初稿遗漏的一步（已补进任务树与验证收口）。
- **权限面是双份的。** Claude 走 `.claude/settings.json`，Codex 走 `.codex/config.toml` + `.codex/rules/default.rules`。若本 issue 需要把新 validator 脚本注册进 allowlist 或新增 hook，必须同时更新两侧，不能只改 Claude 侧（本轮默认不新增 hook，见非目标）。

## Branch / worktree

- `feat/13-plan-lifecycle-state` / `.claude/worktrees/13-plan-lifecycle-state`（已切出，干净）。

## Linked issue / PR

- `#13`（本 plan 对应的 issue）。
- 与 `#14`（多 agent 状态/通信/handoff 控制面）、`#12`（bootstrap/adoption proof）有交叉，本 plan 只在「未解决问题」标注边界，不替它们决定范围切分或先后顺序——等 human 拍板。

## Allowed paths（本轮：仅写这份 plan doc）

- `plans/20260712-plan-lifecycle-state.zh.md`（本文件）

### Allowed paths（实现阶段草案，待批注/锁定）

- `.agent/templates/plan-doc.zh.md`（加状态锚点行）
- `.agent/human-gates.md`（若需要补一条"approved plan 的证据要求"）
- `.agent/session-protocol.md`、`.agent/anatomy-protocol.md`（视状态机制落地方式，补引用）
- `.claude/skills/interactive-plan-doc/SKILL.md`（canonical；改后必须重跑 sync）
- `.claude/skills/worktree-pr-flow/SKILL.md`（canonical；改后必须重跑 sync）
- `.agents/skills/interactive-plan-doc/SKILL.md`、`.agents/skills/worktree-pr-flow/SKILL.md`（**生成产物，不手改**——由 `python scripts/sync-codex-adapters.py` 重生成；仅当上面两个 canonical skill 改动时同 commit 一起更新）
- `scripts/validate-governance.py`（扩展）或新增 `scripts/check-plan-lifecycle.py`
- `scripts/ANATOMY.md`（若新增脚本，登记）
- `plans/ANATOMY.md`（新建——`plans/` 目前缺这个文件，且一旦有 lifecycle/schema 就满足 anatomy-protocol"复杂目录"门槛）
- 根 `ANATOMY.md`（补 `plans/` 一行进分层地图）
- `memory/change-control.yaml`（若方案选择扩展它作为审批证据落点）
- `DECISIONS.md` / `human/decisions/`（若方案选择复用它，或需要新增一条 ADR 记录本次决策本身）
- fixtures 存放路径（新建目录，路径待定，见未解决问题 7）
- 现有 `plans/*.zh.md`（若决定回填 Status 锚点，只加一行，不改正文语义）
- `template-manifest.toml`（若新增/改动文件判定为模板框架层，需登记）

## Forbidden paths

- `lab/data/**`、`lab/runs/**`、`lab/models/**`、`checkpoints/**`、`wandb/**`、`lab/infra/private/**`
- `lab/research/{claims,evidence,release-gates,regression-matrix}.yaml` 的既有条目语义——只参考其校验*模式*，不改研究证据链本身的内容
- 不新增 PreToolUse/阻断类 hook（见「非目标」）
- 不改 `.claude/settings.json` 权限面，除非明确要注册新脚本到 allow list 且经 human 确认；**若真要改，`.codex/config.toml` + `.codex/rules/default.rules` 必须同步改**，不能只动 Claude 侧（否则 Codex 侧权限漂移）
- 不手改 `.codex/agents/*.toml` 与 `.agents/skills/**` 生成产物（只经 `sync-codex-adapters.py` 重生成）
- 不 push / 开 PR / merge（human gate）
- 不动 `.claude/worktrees/` 之外的其他 in-flight 分支/worktree

## 任务树（草案，供批注；实现顺序/取舍待收敛）

- [ ] 状态模型设计
  - [ ] 定 plan doc 状态锚点格式（例如正文开头一行：`Status: <enum> · <date> · <approver/ref>`）
  - [ ] 定枚举覆盖范围：只做 plan doc，还是 brief/review/decision 一并统一（见未解决问题 1）
  - [ ] 定审批证据落地位置：扩展 `change-control.yaml` / 复用 `human/decisions/` / 新 ledger（三选一，见未解决问题 2）
- [ ] 校验规则设计
  - [ ] 定义"approved 前必填"字段清单（Allowed paths / Forbidden paths / 验证标准 非空、非占位符）
  - [ ] 定义"过期 approval"判定规则（见未解决问题 5）
  - [ ] 定义"互相冲突批注"时的行为（不自动选边，升级为未解决问题，阻止误判为已收敛）
  - [ ] 仿 `check_release_gates` / `check_regression_matrix` 模式实现 plan lifecycle 校验（新脚本或扩展 `validate-governance.py`）
- [ ] skill / 流程接线
  - [ ] `interactive-plan-doc`：起草时写 `Status: draft`；human 批注收敛并明确批准后转 `approved`；plan revision commit 前跑新校验
  - [ ] `worktree-pr-flow`：进入实现前读 linked plan doc 状态，必须 `≥ approved`；开始实现时状态转 `implementing`（谁来标记见未解决问题 9）；merge 后视验证结果转 `verified`
  - [ ] 同 topic 出新版 plan 时：旧 plan 顶部标 `superseded` 并指向新文件（不删除、不移动，保留历史）
  - [ ] 改动上述两个 skill 后重跑 `python scripts/sync-codex-adapters.py`，同 commit 更新 `.agents/skills/**` 生成产物
- [ ] 双 runtime 状态感知接线
  - [ ] 确认 fresh session（Claude 与 Codex 各自）从哪个 runtime-neutral 文件读到"当前 plan / 已 superseded"——核实 `context_continuity.py` 是否 surface 该信息（见未解决问题 10），必要时把 `plans/` 当前指针接入 `memory/current-status.md` 或 `plans/ANATOMY.md`
  - [ ] 明确状态锚点格式对两 runtime 完全等价、不依赖 runtime 专属注入（写进 `plans/ANATOMY.md`）
- [ ] 结构文档
  - [ ] 新建 `plans/ANATOMY.md`（状态枚举、必填字段、与 change-control/decisions/branch-status 的连接关系）
  - [ ] 根 `ANATOMY.md` 分层地图补 `plans/` 一行
  - [ ] 视需要补 `.agent/session-protocol.md` / `.agent/human-gates.md` 引用
- [ ] fixtures
  - [ ] 正向（approved 且字段齐全）
  - [ ] 缺字段（approved 但 forbidden paths / 验证标准 为空）
  - [ ] 过期 approval（approved 但引用的 decision/review 已变为 superseded/rejected，或内容漂移未重新批注）
  - [ ] 互相冲突批注（Human 批注区出现自相矛盾的两条意见，验证不会被误判为"已收敛"）
  - [ ] 定 fixtures 存放路径（本 repo 无先例，见未解决问题 7）
- [ ] 迁移
  - [ ] 现有 `plans/*.zh.md` 是否回填 Status 锚点、回填成什么状态（见未解决问题 8）
  - [ ] 若判定为模板框架层能力，登记 `template-manifest.toml`
- [ ] 验证收口
  - [ ] `python scripts/validate-governance.py`
  - [ ] 对 fixtures 跑新校验：正向通过，三类异常各自精确报错
  - [ ] `python scripts/check-anatomy-drift.py`
  - [ ] `python scripts/sync-codex-adapters.py --check`（若改了 skill / 新增脚本，确认 Codex adapter 不 stale）
  - [ ] 若改了两侧权限面，`python scripts/check-agent-harness.py`（确认 Claude/Codex 权限/hook 对齐无漂移）
  - [ ] 双 runtime 冒烟（若采纳未解决问题 11 的 smoke 选项）：human 在 Codex 侧起一个 fresh session，确认它能读到当前 plan 的 `Status` 且遵守同一 draft/approved/superseded 语义

## Human 批注区

> 在这里批注：改状态覆盖范围、定证据落点、砍某个未解决问题的选项、加约束。我读 diff 后收敛。

## 当前决策

无（初稿阶段，等待 human 批注后收敛）。以下是我起草时的**倾向**，不是已定项，标注供 human 直接推翻或确认：

- 倾向复用 `check_release_gates` / `check_regression_matrix` 的校验范式，而非发明新语义。
- 倾向不新增阻断类 hook，维持"hook 发信号、validator 强制"的既有纪律（双 runtime 场景下这也更稳，见非目标末条）。
- 倾向先把 plan doc 一类做扎实，brief/review/decision 的统一状态机作为可选的第二步（但这与 issue 原文字面要求有张力，需 human 明确选择，见未解决问题 1）。
- 倾向状态锚点与强制点都走 runtime-neutral 通道（纯文本 `Status` 行 + `python scripts/...` validator），刻意不依赖 Claude 专属注入，以直接消除"不同 runtime 误读阶段"的成因（见现状盘点「双 runtime 一致性」）。

## 未解决问题

1. **覆盖范围**：issue 原文要求给 brief/plan/review/decision 都定义可链接状态。是否本轮就统一四类的状态机，还是先只做 plan doc（interactive-plan-doc / worktree-pr-flow 直接消费的那一类），其余留后续 issue？
2. **审批证据落地位置**：三个候选——(a) 扩展 `memory/change-control.yaml`（已存在但目前 validator 不解析其内容）；(b) 复用 `human/decisions/`（已有状态枚举，但语义是"决策"不是"计划审批"，套用是否牵强）；(c) 新增专属 ledger（如 `memory/plan-status.yaml`）。三者都不要求 human 写复杂 YAML（agent 维护），但决定了后续所有引用怎么连，需要 human 定。
3. **与 #14 边界**：本 issue 只产出"可检查状态"元数据；#14（多 agent 状态/通信/handoff 控制面）未来可能要跨 agent 读取/协调这些状态。本轮是否要为它预留稳定的读取接口（固定路径 + 稳定 schema），还是完全不考虑外部消费者、等 #14 立项时再对齐？谁先做、边界怎么切？
4. **与 #12 边界**：`adopt-existing-repo.py` 的 phase 本质上也是"计划执行到哪一步"，是否也要挂上同一套状态枚举？还是完全独立，本轮只保证不破坏它现有校验（`check-adoption-integrity.py`）？
5. **"过期 approval"判定标准**：按时间窗口（approved 超过 N 天未转 implementing 视为过期）？按内容漂移（plan 正文在 approved 快照之后又被改动但未重新走批注，用 hash/git blame 判定）？还是仅"引用的 decision/review 被 superseded/rejected"这一种触发？可能需要多种规则并存，但本轮是否全做需要 human 拍板优先级。
6. **是否要更强的机械拦截**：验收标准写"approved 前缺字段时相关 workflow 明确停止"——这靠 validator 非零退出码 + skill 文档步骤（"失败时的 handoff"）是否足够，还是需要一个真正拦编辑动作的 PreToolUse hook？后者更强但更侵入，且与 context-orchestration 阶段确认的"hook 只发信号"硬约束冲突，需要 human 明确要不要破例。
7. **fixtures 存放路径**：repo 目前没有 `tests/`/pytest 先例，现有 validator 脚本走"直接对 repo 本身 dogfood + 手工构造反例跑一次"的验证方式，没有外部 fixture 文件目录。新建 `scripts/fixtures/plan-lifecycle/` 放人造 plan doc 样本？还是像现有脚本一样把测试用例内联在校验脚本自身（docstring/self-test），不建外部目录？
8. **存量迁移**：现有 `plans/*.zh.md`（如 `20260711-context-orchestration.zh.md`、adopt-existing-repo 的 plan）是否要回填 Status 锚点？如果要，回填成什么状态（多数已实现完成，应标 `verified` 还是 `implementing`）？这算不算触发 anatomy same-commit 规则？
9. **状态转换的 owner**：`draft → in-review → approved` 由 human 批注驱动（清楚）。`approved → implementing` 是否需要 human 二次确认，还是 agent 进入 `worktree-pr-flow` 时可自主标记（现状 `worktree-pr-flow` 的 human gate 只卡在 push/PR/merge，implementing 阶段本身不属于外部副作用）？`implementing → verified` 由谁写、依据什么证据（merge 后自动写，还是要走 fresh reviewer 确认后才写）？
10. **[Codex 侧] fresh session 的状态感知路径**：已知 `.codex/config.toml` 在 `SessionStart(clear)`/`PostCompact` 挂了 `context_continuity.py`，Claude 侧 `.claude/settings.json` 也有等价挂点。但**尚未核实 `context_continuity.py` 具体读哪些文件、会不会把"当前/已 superseded plan"surface 给 fresh session**。若它只读 `memory/current-status.md`，那 plan lifecycle 就应把"当前 plan 指针"写进 current-status（或让 hook 也读 `plans/ANATOMY.md`）；若两者都不读，则 Codex/Claude 的 fresh session 仍要靠 agent 主动去 `plans/` 找——这恰恰是本 issue 要消除的误读风险。需要在实现阶段读 hook 源码确认，并决定是否要小幅扩展该 hook 的读取面（注意：hook 是 canonical-in-`.claude/hooks/`、两 runtime 共用同一份 `.py`，改它是 runtime-neutral 的，但仍属改 hook 行为，需谨慎）。
11. **[Codex 侧] 是否需要双 runtime 冒烟作为验收证据**：本 reviewer 没有 Codex 一手运行经验，只能从 `.codex/config.toml` 判断"挂点存在"。"Codex fresh session 真能读到并遵守同一套状态语义"这一点，是靠 (a) validator/adapter parity（runtime-neutral 的 `python scripts/...` + `sync --check` 通过即视为足够），还是 (b) 要 human 在 Codex 侧实跑一次 fresh session 冒烟确认？后者更硬但需 human 亲自操作。默认倾向 (a) + 一次性 (b) 抽查，请 human 拍板。

## 验证标准（本轮：方案文档本身）

- 本 plan doc 经至少一轮 human 批注收敛，未解决问题 1/2/3/6/10/11 有明确答案（覆盖范围、证据落点、#14 边界、是否要机械拦截、Codex 状态感知路径、是否要双 runtime 冒烟）。
- Allowed paths / Forbidden paths 从"实现阶段草案"收敛为确定清单（含 Codex 侧生成产物与权限面的处理约定）。
- （进入实现阶段后追加，见任务树"验证收口"）：`python scripts/validate-governance.py` 通过；新校验对 fixtures 的正向/三类异常各自给出正确结果；`python scripts/check-anatomy-drift.py` 通过；若改了 skill/脚本/权限面，`python scripts/sync-codex-adapters.py --check` 与（视情况）`python scripts/check-agent-harness.py` 通过，Codex adapter 无 stale/漂移。

## 下一步

- 等 human 在 Human 批注区落笔，优先回应未解决问题 1（覆盖范围）、2（证据落点）、3（#14 边界）、6（是否要机械拦截）、11（是否要双 runtime 冒烟）。
- 实现阶段第一步先读 `.claude/hooks/context_continuity.py` 源码，落地未解决问题 10（Codex/Claude fresh session 的状态感知路径）。
- 收敛后：决定是先出一个"仅状态模型 + 校验脚本"的最小实现 PR，还是把 skill 接线 / anatomy 更新一次性做完；随后转 `worktree-pr-flow`。

## Plan revision log

- 2026-07-12 初稿。盘点现状（`DECISIONS.md` 状态枚举、`change-control.yaml`、`release-gates`/`regression-matrix` 的占位符容忍校验范式、`branch-status.md` 的 Plan doc 字段、`plans/` 目前无 ANATOMY/根路由），据此起草状态模型草案与任务树；未解决问题聚焦覆盖范围切分、证据落点三选一，以及与 #12/#14 的边界。
- 2026-07-12 第二意见审查（Claude Opus 4.8，代替额度耗尽的 Codex gpt-5.6-sol 二审；人类最终批准仍待定）。补 Codex 侧缺口：新增「双 runtime 一致性」子节（状态锚点/validator 走 runtime-neutral、Codex SessionStart/UserPromptSubmit 挂点证据、skill canonical→`.agents/` sync 义务、两侧权限面对称）；Allowed/Forbidden paths 补 `.agents/skills/**` 生成产物与 `.codex/` 权限面处理约定；任务树加 sync 重生成、双 runtime 状态感知接线；验证收口加 `sync-codex-adapters.py --check` / `check-agent-harness.py` / 可选双 runtime 冒烟；新增未解决问题 10（`context_continuity.py` 是否 surface 当前 plan 状态，待读源码核实）、11（是否要双 runtime 冒烟作为验收证据）；强化"不加阻断类 hook"非目标的 runtime 论据。
