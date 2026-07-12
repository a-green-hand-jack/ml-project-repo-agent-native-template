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
- 不新造一套与 `DECISIONS.md` / `memory/change-control.yaml` 平行且语义重复的记录系统——新增的 YAML 注册表要与既有结构衔接（引用而非复制其内容）。**human 已拍板**：注册表落点为新建 `memory/doc-lifecycle.yaml`，不扩展 `memory/change-control.yaml`、不复用 `human/decisions/`（见已决策 3）。
- 不实现 issue #14（多 agent 状态/通信/handoff 控制面）——本 issue 只给四类文档加"可检查状态"元数据 + 注册表；#14 未来若要跨 agent 消费这些状态，是它自己的范围。**human 已拍板**：`memory/doc-lifecycle.yaml` 就是本 issue 自用的普通文件，不为 #14 预留专用跨 agent 读取接口/协议——#14 需要时自己直接读这份 YAML，不需要 #13 提前设计稳定 schema 或通信协议（见已决策 5）。
- 不实现 issue #12（bootstrap/adoption proof）——只保证新机制不破坏 `adopt-existing-repo.py` / `check-adoption-integrity.py` 现有校验；不去碰 adoption 自身的 phase 状态设计。**human 已拍板**：#12 的 adoption phase（discover/baseline/scaffold/normalize/prove）与 #13 的文档 lifecycle 状态**各自独立、不强行统一成一套状态机**（语义不同：一个是迁移流程阶段，一个是文档生命周期状态）——见已决策 6、已解决问题 4。
- **新增的机械拦截 hook 只拦"可判定的事实"，不做主观判断。** hook 会在编辑动作阶段拦截"状态/引用完整性不成立"的写入（如某文档标 approved 前缺 scope/forbidden/verification、注册表里的关联引用指向不存在的实体、状态跃迁与注册表记录矛盾）。但它**绝不**替 human 判断"研究方向对不对、风险能不能接受、计划是否真的收敛"——这类主观判断仍然是 human gate，hook 不碰。这条边界（机器只判事实、不判主观）从头到尾保留；**变化的只是**：此前"本 issue 不加任何阻断类 hook、强制点只放 validator"的表述已被 human 推翻（见已决策 2 中的 hook 决策），改为"新增一个针对状态/引用完整性的有意义拦截点"。
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
3. 四类文档的状态证据/关联落点已由 human 拍板：**新建专属 `memory/doc-lifecycle.yaml`**（不扩展 `change-control.yaml`，不复用 `human/decisions/`）——见已决策 3、未解决问题 2（已决策）。
4. **状态载体必须是 runtime-neutral 的**（见下节）：本 issue 的核心风险之一就是"不同 runtime 误读阶段"，任何依赖 Claude 专属注入通道的方案都会在 Codex 侧留缺口。**新增的拦截逻辑同样受此约束**：human 已拍板（见已决策 4）把逻辑折进现有 `.claude/hooks/pre_tool_guard.py`，而不是新建独立 hook 文件——`.claude/settings.json` 的 PreToolUse 与 `.codex/config.toml` 的 `[[hooks.PreToolUse]]` **已经**各挂了一份对同一个物理文件的调用（matcher 均覆盖 `Edit|Write`），因此**不需要新增两侧挂载点**，这是相比"独立新建 hook 文件"方案的直接优势：省掉一次"两侧手写挂载点、同 commit 对齐、纳入 harness parity"的工作量。仍需坚持的约束是：doc-lifecycle 的判定逻辑本体要写成一个 runtime-neutral 的 `python scripts/...` 函数，`pre_tool_guard.py` 内部只做薄接线去调它，避免逻辑直接堆进 hook 脚本、在未来演化中失控。

### 双 runtime（Claude / Codex）一致性 —— Codex 侧检查

本 issue 原文点名"不同 runtime 或后续 agent 误读阶段"，即 Claude Code 与 Codex 双 runtime 场景。设计时按以下证据处理：

- **状态锚点走纯文本、runtime-neutral。** 四类文档正文里一行 `Status: ...` 是纯 Markdown，Claude 与 Codex 用完全相同的方式（读文件）解析，不依赖任何 runtime 专属的结构化注入。这是刻意选择：任何"靠 hook 往上下文注入当前状态"的方案都要在两侧各配一份，adapter 生成有已知损耗，反而制造分歧。
- **拦截逻辑折进现有 `pre_tool_guard.py`，判定本体走 runtime-neutral 的 `python scripts/...`。** human 已拍板：(a) 要新增机械拦截（见已决策 2）；(b) 具体实现是扩展现有 `.claude/hooks/pre_tool_guard.py`，不新建独立 hook 文件（见已决策 4）。实测确认 `.claude/settings.json`（PreToolUse，matcher `Bash|Edit|Write`）与 `.codex/config.toml`（`[[hooks.PreToolUse]]`，matcher `^(Bash|apply_patch|Edit|Write)$`）**已经**各自挂了一份对同一物理文件 `.claude/hooks/pre_tool_guard.py` 的调用，因此本轮**不需要新增两侧挂载点**——这是折进既有 hook 相比独立新建 hook 文件的直接优势。仍需做的：把"状态/引用完整性是否成立"的判定收敛成一个可独立调用的 Python 校验函数（与 validator 复用同一份逻辑），`pre_tool_guard.py` 内部新增分支调用它；改动仍要跑 `check-agent-harness.py` 确认双侧 parity 未破坏（两侧共享同一物理文件，理论上天然一致，parity 检查用于兜底确认）。
- **Codex 的 hook 事件存在，但当前接线不覆盖真正的 fresh startup。** 本次 Codex（gpt-5.6-sol, medium）一手读配置并实跑 hook：`.codex/config.toml:53-59` 挂了 `UserPromptSubmit`，`:61-68` 只挂 `SessionStart(clear)`，`:70-77` 另挂 `PostCompact`；并没有 `SessionStart(startup|resume)`。`context_continuity.py:23-25` 唯一读取 `memory/current-status.md`，`:37-42` 只接受 `source ∈ {compact, clear}` 或 `PostCompact`，不会读 `plans/`、`plans/ANATOMY.md`，也不会从 plan doc 提取 `Status`。定向探针进一步确认：`source=startup` 输出 0 bytes，`source=clear` 与 `PostCompact` 会回注 `memory/current-status.md`。因此现状只能保证 **clear/compact 后**的状态恢复，不能声称 fresh session 自动感知当前 plan；而且当前 `memory/current-status.md` 没有本 issue plan 的指针/状态，即使 clear/compact 触发也 surface 不出来。实现应把当前 plan 指针写入 `memory/current-status.md`（由现有共享 hook 回注），或另行明确扩展 startup/读取面；`plans/ANATOMY.md` 仅作为 schema/router 时不会被现有 hook自动读取。
- **本次会话对 trust / 自动触发的证据边界。** 当前确为真实 Codex `codex exec` 会话（可见 `CODEX_THREAD_ID`、`CODEX_CI=1`，且项目级 AGENTS/skills 已进入会话），但没有可读的“project hook trust 已批准”状态字段，也没有 hook 执行日志；`UserPromptSubmit` 在低占用时本来就静默，故“未看到提示”既不能证明未触发，也不能单独证明已触发。上述结论依赖已加载的项目配置源码与对同一 hook 的定向实跑，不把 trust 状态或本次 startup 自动触发硬写成已证实。
- **skill / command 是 canonical-in-`.claude/`、sync 到 Codex。** `interactive-plan-doc`、`worktree-pr-flow` 的 canonical 源在 `.claude/skills/`，Codex 侧消费的是 `sync-codex-adapters.py` 生成的 `.agents/skills/<name>/SKILL.md`（见 `scripts/sync-codex-adapters.py:106-115`）。**只要本 issue 改这两个 skill，就必须重跑 sync 并把 `--check` 纳入验证**，否则 Codex 侧拿到的是过期步骤——这是初稿遗漏的一步（已补进任务树与验证收口）。
- **权限面是双份的。** Claude 走 `.claude/settings.json`，Codex 走 `.codex/config.toml` + `.codex/rules/default.rules`。本 issue 要把新 validator/判定脚本注册进 allowlist（若判定函数所在脚本需要被单独 `python scripts/...` 调用，两侧 allowlist 都要有）；**拦截逻辑本身**由于折进了已挂载的 `pre_tool_guard.py`（见已决策 4），不需要新增 PreToolUse 挂载点，但改动 `pre_tool_guard.py` 内部逻辑后仍建议跑一次 `check-agent-harness.py` 确认两侧权限面/hook parity 无意外漂移。

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
- **扩展现有 `.claude/hooks/pre_tool_guard.py`**（human 拍板：不新建独立 hook 文件，见已决策 4）+ `.claude/hooks/README.md`（登记新增的判定逻辑）
- `.claude/settings.json`、`.codex/config.toml`：两侧**已经**挂载了 `pre_tool_guard.py`（PreToolUse，matcher 均含 `Edit|Write`），本轮**不需要新增挂载点**；若判定脚本需要单独注册进 `python scripts/*` allowlist，两侧对应位置各补一条即可
- `scripts/ANATOMY.md`（若新增脚本，登记）
- `plans/ANATOMY.md`（新建——`plans/` 目前缺这个文件，且一旦有 lifecycle/schema 就满足 anatomy-protocol"复杂目录"门槛）；视注册表落点，可能还需 brief/review/decision 所在目录的 ANATOMY 补状态说明
- 根 `ANATOMY.md`（补 `plans/` 一行进分层地图，并让注册表文件在地图里可见）
- `memory/doc-lifecycle.yaml`（**新增**——四类文档统一登记的 YAML 注册表，落点已拍板确定，见已决策 3；不扩展 `memory/change-control.yaml`、不复用 `human/decisions/`）
- `DECISIONS.md` / `human/decisions/`（decision 类本身就是这里的产物；若需要新增一条 ADR 记录本次机制决策，可能触碰，但**不**承载 lifecycle 状态记录本身——见已决策 3）
- fixtures 存放路径（新建目录，路径待定，见未解决问题 7）
- 现有 `plans/*.zh.md` 及既有 brief/review/decision 文档（若决定回填 Status 锚点，只加一行，不改正文语义）
- `template-manifest.toml`（若新增/改动文件判定为模板框架层，需登记）

## Forbidden paths

- `lab/data/**`、`lab/runs/**`、`lab/models/**`、`checkpoints/**`、`wandb/**`、`lab/infra/private/**`
- `lab/research/{claims,evidence,release-gates,regression-matrix}.yaml` 的既有条目语义——只参考其校验*模式*，不改研究证据链本身的内容
- **新增的拦截 hook 只判"可判定的事实"（状态/引用完整性），严禁扩张成替 human 做主观判断**（研究方向、风险接受、"是否真的收敛"仍是 human gate）——这条边界是硬约束（见已决策 2 与「非目标」）
- 改 `.claude/settings.json` 权限面/挂 hook 时，**`.codex/config.toml` + `.codex/rules/default.rules` 必须同 commit 手写对齐**，不能只动 Claude 侧（否则 Codex 侧权限/hook 漂移）；两侧 hook 不会被 `sync-codex-adapters.py` 自动同步。（本轮不新增挂载点——机械拦截折进已挂载的 `pre_tool_guard.py`，见已决策 4——但此约束对未来任何新增/改动 PreToolUse 挂点的场景仍然有效，不因本轮不触发就删除）
- 不手改 `.codex/agents/*.toml` 与 `.agents/skills/**` 生成产物（只经 `sync-codex-adapters.py` 重生成）
- 不 push / 开 PR / merge（human gate）
- 不动 `.claude/worktrees/` 之外的其他 in-flight 分支/worktree

## 任务树（草案，供批注；实现顺序/取舍待收敛）

- [ ] 状态模型设计（四类统一）
  - [ ] 定四类文档（brief / plan / review / decision）共用的状态锚点格式（例如正文开头一行：`Status: <enum> · <date> · <approver/ref>`）；确认四类是否共用同一枚举，还是各类有少量差异态
  - [ ] 定统一枚举：`draft · in-review · approved · implementing · verified · superseded`（覆盖四类，允许某类不经过某些态）
  - [ ] 定四类之间的关联语义（brief → plan → review → decision 的牵引关系如何在注册表里表达）
- [ ] YAML 注册表设计（新增 `memory/doc-lifecycle.yaml`，四类统一登记；落点已拍板，见已决策 3）
  - [ ] 定注册表 schema：每条记录 = 文档路径 + 类型（brief/plan/review/decision）+ 当前状态 + 关联引用（linked issue / branch / worktree / human approval 引用 / 上游 brief / 下游 review·decision）
  - [ ] [已决策] 注册表落点 = 新增专属 `memory/doc-lifecycle.yaml`（不扩展 `memory/change-control.yaml`，不复用 `human/decisions/`）——human 拍板，见已决策 3 / 未解决问题 2（已决策）
  - [ ] 复用"占位符容忍 + 非默认态需真实证据"范式：状态一旦"进阶"（如转 approved），强制其引用的 issue/branch/approval/上下游文档真实存在
  - [ ] 明确注册表由 agent 维护、human 不手填复杂 YAML
- [ ] 校验规则设计
  - [ ] 定义"approved 前必填"字段清单（Allowed paths / Forbidden paths / 验证标准 非空、非占位符）
  - [ ] 定义注册表"引用完整性"规则（关联的 issue/branch/worktree/approval/上下游文档必须指向真实存在的实体，悬空即报错）
  - [ ] [已决策] 实现"过期 approval"判定 = **仅"引用被标为 superseded 就算过期"**这一种触发（不做时间窗口、不做内容漂移 hash 判定）：某文档引用的 issue/branch/前置 plan/review/decision 被标 superseded 时，级联把本条 approval 判为失效——human 拍板，见已决策 7 / 已解决问题 5
  - [ ] 定义"互相冲突批注"时的行为（不自动选边，升级为未解决问题，阻止误判为已收敛）
  - [ ] 仿 `check_release_gates` / `check_regression_matrix` 模式实现四类 doc lifecycle 校验（新脚本 `check-doc-lifecycle.py` 或扩展 `validate-governance.py`）；**判定逻辑抽成可被 hook 复用的函数**
- [ ] 机械拦截 hook 设计（扩展现有 `.claude/hooks/pre_tool_guard.py`，human 拍板，见已决策 2 / 4）
  - [ ] 定拦截触发面：拦哪个 tool_input 阶段（Write/Edit 目标命中四类文档、或写注册表）、拦什么（状态跃迁到 approved 等进阶态但完整性不成立、注册表引用悬空、状态与注册表矛盾）
  - [ ] [已决策] 实现方式 = 折进已有 `pre_tool_guard.py`（不新增独立 hook 文件）——human 拍板，见已决策 4；两侧 `.claude/settings.json`/`.codex/config.toml` 已挂载同一物理文件，本轮不需要新增挂载点，这是相比独立新建 hook 方案的优势
  - [ ] hook 只调 runtime-neutral 的 `python scripts/...` 判定函数，逻辑不在 hook 内重复实现
  - [ ] **双 runtime 挂载纪律（已简化）**：由于折进的是已挂载的 `pre_tool_guard.py`，两侧无需新增挂点；只需确认改动后重跑 `check-agent-harness.py` 确认现有 parity 未被破坏；若未来判定脚本需要新的 `python scripts/*` allowlist 条目，两侧手写同 commit 对齐（这条通用纪律保留，仅本轮触发面缩小）
  - [ ] 明确 hook 的边界护栏：只判可判定事实，拦截信息里明确指向"缺哪个字段/哪个引用悬空"，不输出主观评价，不阻断 human 覆盖（human 可显式绕过）
- [ ] skill / 流程接线
  - [ ] `interactive-plan-doc`：起草时写 `Status: draft` 并在注册表登记；human 批注收敛并明确批准后转 `approved` 并回填 approval 引用；plan revision commit 前跑新校验
  - [ ] `worktree-pr-flow`：进入实现前读 linked plan doc 状态，必须 `≥ approved`；开始实现时 **agent 自主**将状态转 `implementing`；merge 后视验证证据 **agent 自主**转 `verified`（[已决策] `approved→implementing→verified` 由 agent 据证据自主标记、human 审 PR 时复核，不逐次问 human——见已决策 10 / 已解决问题 9）
  - [ ] **[决策 1（a）新增] 入口纪律接线**：在 `CLAUDE.md` / `AGENTS.md`（及 `.agent/` 相关入口文档）补一条——session 开始时主动查当前 approved plan（读 `memory/current-status.md` 指针 + `memory/doc-lifecycle.yaml` 注册表），不依赖 hook 自动注入；这是 fresh startup 无机械兜底时的纪律补位，与决策 1（b）的 hook 侧修复叠加使用
  - [ ] brief / review / decision 三类的产出/收敛流程如何写各自的状态与注册表条目（若已有对应 skill/流程则接线，若无则在文档里约定谁维护）
  - [ ] 同 topic 出新版 plan 时：旧 plan 顶部标 `superseded` 并指向新文件（不删除、不移动，保留历史）；注册表同步标 superseded（并据已决策 7 级联把引用旧 plan 的下游 approval 判为过期）
  - [ ] 改动上述 skill 后重跑 `python scripts/sync-codex-adapters.py`，同 commit 更新 `.agents/skills/**` 生成产物
- [ ] 双 runtime 状态感知接线
  - [ ] **[决策 1（b）已定]** 把 fresh session 与 compact/clear 恢复拆开验收：已确认现有 `context_continuity.py` 只在 clear/compact 后回注 `memory/current-status.md`、且不读 plan；实现时把"当前 approved plan / 已 superseded"指针写入 `memory/current-status.md`（由现有共享 hook 回注），并**评估是否扩展 hook 覆盖 `startup` 场景**（Codex `SessionStart(startup|resume)` + Claude 对等事件）——见已决策 11 / 已解决问题 10。此项与 skill 分组的"入口纪律接线"（决策 1 a）两者都做，不是二选一
  - [ ] 明确状态锚点格式对两 runtime 完全等价、不依赖 runtime 专属注入（写进 `plans/ANATOMY.md`）
- [ ] 结构文档
  - [ ] 新建 `plans/ANATOMY.md`（状态枚举、必填字段、注册表 schema、与 change-control/decisions/branch-status 的连接关系）
  - [ ] 根 `ANATOMY.md` 分层地图补 `plans/` 与注册表文件一行
  - [ ] 视需要补 brief/review/decision 所在目录的 ANATOMY 状态说明
  - [ ] 视需要补 `.agent/session-protocol.md` / `.agent/human-gates.md` 引用（含 hook 与注册表说明）
- [ ] fixtures（[已决策] **脚本内嵌 / 无依赖断言，不新开 `tests/` 目录**——与 #17 风格一致，测试样本随校验脚本自身内联，见已决策 8 / 已解决问题 7）
  - [ ] 正向（approved 且字段齐全、注册表引用真实）
  - [ ] 缺字段（approved 但 forbidden paths / 验证标准 为空）
  - [ ] 悬空引用（注册表条目引用不存在的 issue/branch/上下游文档）
  - [ ] 过期 approval（approved 但引用的 issue/branch/前置 plan/review/decision 已被标为 superseded —— 按已决策 7，只测这一种触发，不测时间窗口/内容漂移）
  - [ ] 互相冲突批注（Human 批注区出现自相矛盾的两条意见，验证不会被误判为"已收敛"）
  - [ ] hook 拦截样本（模拟"标 approved 但完整性不成立"的写入，验证 hook 会拦下并给出精确提示，且 human 显式覆盖可放行）
- [ ] 迁移
  - [ ] **[决策 5 已定] 批量回填存量 plan doc 状态**：对 `20260709/20260711/20260712` 这批已写好的 `plans/*.zh.md`（及既有 brief/review/decision 文档）逐份按**实际真实进展**回填 Status 锚点——已实现→`verified`、已归档/被取代→`superseded`、进行中→`implementing`，不留"未知状态"历史数据（见已决策 9 / 已解决问题 8）
  - [ ] 现有文档回填进注册表（初始状态与上一步回填的 Status 一致）
  - [ ] 回填触碰 anatomy/router 时按 same-commit 规则同步处理
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
3. **YAML 注册表落点 = 新建 `memory/doc-lifecycle.yaml`**（不扩展 `memory/change-control.yaml`，不复用 `human/decisions/`）。理由：`change-control.yaml` 语义是"变更登记"且当前 validator 不解析其内容；`human/decisions/` 语义是"决策"，套用到四类文档的 lifecycle 状态上牵强；专属新文件语义最干净，由 agent 维护、不要求 human 手填复杂 YAML。
4. **机械拦截逻辑折进现有 `.claude/hooks/pre_tool_guard.py`**，不新建独立 hook 文件。理由：`.claude/settings.json`（PreToolUse）与 `.codex/config.toml`（`[[hooks.PreToolUse]]`）已经各挂了一份对同一物理文件 `pre_tool_guard.py` 的调用（matcher 均覆盖 `Edit|Write`），折进去意味着**不需要新增两侧挂载点**——省掉"两侧手写对齐 + 纳入 harness parity"这一整块工作，是相比独立新建 hook 文件更省事、更不易漂移的方案。
5. **不为 #14（多 agent 状态/通信/handoff 控制面）预留跨 agent 读取接口**。`memory/doc-lifecycle.yaml` 是普通文件，#14 未来需要时自己直接读，不需要 #13 提前设计专用 schema/协议。

**第二批 human 拍板（2026-07-12，逐条覆盖此前余下的全部 open question）：**

6. **#12 adoption phase 不挂 #13 这套 lifecycle 状态，两者各自独立**。理由：#13 的状态是"文档生命周期状态"，#12 的 phase（discover/baseline/scaffold/normalize/prove）是"迁移流程阶段"，语义不同，不强行统一成一套状态机。本轮只保证不破坏 `check-adoption-integrity.py`。对应未解决问题 4。
7. **"过期 approval" = 引用被标为 superseded 就算过期**，不引入时间窗口、不做内容漂移 hash 判定。规则：某 plan 引用的 issue/branch/前置 plan（或 review/decision）一旦被标为 superseded，本条 approval 跟着失效。理由：这是唯一"可判定的事实"型触发，与 hook/validator 只判事实的边界一致；时间窗口/内容漂移都带主观阈值或误报风险。对应未解决问题 5。
8. **fixtures 采用脚本内嵌 / 无依赖断言，不新开 `tests/` 目录**。与 #17 已定风格一致，测试样本随校验脚本自身内联（docstring/self-test/内嵌构造反例）。理由：本 repo validator 一贯 dogfood + 内联反例，没有外部 fixture 目录先例，保持一致最省维护。对应未解决问题 7。
9. **存量 plan doc 批量回填 Status 锚点**，按每份文档实际真实进展填对应状态（已实现→`verified`、已归档/被取代→`superseded`、进行中→`implementing` 等），不留"未知状态"的历史数据。覆盖 `20260709/20260711/20260712` 这批已写好的文档。理由：注册表/校验若要成立，历史数据必须有真实状态，否则第一天就带一批悬空/未知条目。对应未解决问题 8。
10. **状态 `approved→implementing→verified` 由 agent 自主标记，human 审 PR 时复核**。不要求每次流转停下来问 human——`implementing`/`verified` 是可由证据判断的事实（有没有对应 commit、测试是否通过）。`draft→in-review→approved` 仍由 human 批注驱动（approved 本身是 human gate）。理由：把 human gate 集中在 approved 与 PR review 两个真正需要主观判断的点，中间的事实性流转交给 agent + 证据，避免流程过度停顿。对应未解决问题 9。
11. **fresh session 状态感知修复 = 方案 a+b 两者都做**：(a) 主动入口纪律——CLAUDE.md/AGENTS.md 等入口文档要求 session 开始时主动查当前 approved plan；(b) 同时把当前 approved plan 指针写进 `memory/current-status.md`（`context_continuity.py` 已读此文件），并评估是否扩展 hook 覆盖 `startup` 场景。理由：单靠纪律在 fresh startup 无机械兜底，单靠 hook 又受 Codex startup 未接线约束，两者叠加才能同时覆盖"有 hook 时机械回注、无 hook 时纪律补位"。对应未解决问题 10。

**起草时的倾向（仍成立，供 human 推翻或确认的实现细节）：**

- 复用 `check_release_gates` / `check_regression_matrix` 的"占位符容忍 + 非默认态需真实证据"校验范式，而非发明新语义；hook 与 validator 复用同一份判定逻辑。
- 状态锚点走 runtime-neutral 的纯文本 `Status` 行；拦截逻辑的判定本体也走 `python scripts/...`，`pre_tool_guard.py` 内部只做薄接线，刻意不依赖 Claude 专属注入，以消除"不同 runtime 误读阶段"的成因（见现状盘点「双 runtime 一致性」）。

## 未解决问题

> 编号保持稳定（其他段落按编号引用）。**1–10 全部已被 human 拍板收敛**（1/2/3/6 于首轮，4/5/7/8/9/10 于 2026-07-12 逐条拍板），11 已由真实 Codex 审查收敛为验收纪律。全部保留在此仅作可追溯记录，不再需要拍板——本文件当前无剩余待决 open question。

1. **[已决策——2026-07-12 human 拍板] 覆盖范围**：原问题是"本轮统一四类状态机，还是先只做 plan doc"。**决定：四类（brief/plan/review/decision）都做**，用统一 YAML 注册表登记。理由：四类相互关联，分开做制造割裂；要有统一审核机制防漂移、防返工。详见「当前决策」1。
2. **[已决策——2026-07-12 human 拍板] 审批证据落地位置**：原三个候选——(a) 扩展 `memory/change-control.yaml`（已存在但目前 validator 不解析其内容）；(b) 复用 `human/decisions/`（已有状态枚举，但语义是"决策"不是"计划审批"，套用牵强）；(c) 新增专属 ledger。**决定：(c) 新建专属 `memory/doc-lifecycle.yaml`**，不扩展 (a)、不复用 (b)。理由：(a) 语义是"变更登记"且当前 validator 未解析其内容；(b) 语义是"决策"，套用到 brief/plan/review 的 lifecycle 状态上牵强；专属新文件语义最干净、由 agent 维护、不要求 human 手填复杂 YAML。详见「当前决策」3。
3. **[已决策——2026-07-12 human 拍板] 与 #14 边界**：原问题是"本轮是否要为 #14（多 agent 状态/通信/handoff 控制面）预留稳定的读取接口（固定路径 + 稳定 schema），还是完全不考虑外部消费者、等 #14 立项时再对齐"。**决定：不预留**。`memory/doc-lifecycle.yaml` 就是一份普通文件，不为 #14 设计专用跨 agent 读取接口/协议；#14 立项后若要跨 agent 消费这些状态，自己直接读这份 YAML 即可，不需要 #13 提前设计。详见「当前决策」5。
4. **[已决策——2026-07-12 human 拍板] 与 #12 边界**：原问题是"#12 的 adoption phase（discover/baseline/scaffold/normalize/prove）是否也要挂上同一套 lifecycle 状态枚举，还是完全独立"。**决定：不挂，两者各自独立**——#13 的状态是"文档生命周期状态"，#12 的 phase 是"迁移流程阶段"，语义不同，不强行统一成一套状态机。本轮只保证新机制不破坏 `check-adoption-integrity.py` 现有校验，不去碰 adoption 自身的 phase 设计。详见「当前决策」6。
5. **[已决策——2026-07-12 human 拍板] "过期 approval"判定标准**：原三类候选——时间窗口（approved 超过 N 天未转 implementing）、内容漂移（正文在 approved 快照后被改但未重新批注，用 hash/git blame 判定）、引用被 superseded/rejected。**决定：只保留"引用被标为 superseded 就算过期"这一种触发**，不引入时间窗口机制、不做内容漂移 hash 判定。规则：只要该 plan 引用的 issue/branch/前置 plan（或 review/decision）被标为 superseded，本条 approval 就跟着失效。详见「当前决策」7。
6. **[已决策——2026-07-12 human 拍板] 是否要更强的机械拦截**：原问题是"validator 非零退出码 + skill 文档步骤是否足够，还是要新增拦编辑动作的 PreToolUse hook"。**决定：要新增 hook**（不只 validator advisory）。理由：template 结构本该稳定，但项目开发中 human/agent 总会想破坏它，防漂移必须有 hook 兜底。此前 context-orchestration 阶段"hook 只发信号"的约束在此**有意破例**——但破例范围严格限定为"拦可判定的状态/引用完整性事实"，不扩张到主观判断。具体拦什么、拦哪个 tool_input 阶段、折进 `pre_tool_guard.py` 还是独立新增，是实现设计（见任务树「机械拦截 hook 设计」），不再是拍板项。详见「当前决策」2。
7. **[已决策——2026-07-12 human 拍板] fixtures 存放路径**：原问题是"新建 `scripts/fixtures/plan-lifecycle/` 外部目录，还是像现有脚本一样把测试用例内联"。**决定：脚本内嵌 / 无依赖断言**，不新开 `tests/` 目录——与 #17 已定的风格保持一致，测试样本随校验脚本自身内联（docstring/self-test/内嵌构造），不建外部 fixture 目录。详见「当前决策」8。
8. **[已决策——2026-07-12 human 拍板] 存量迁移**：原问题是"现有 `plans/*.zh.md` 等文档是否回填 Status 锚点、回填成什么状态"。**决定：要批量回填**——对 `20260709/20260711/20260712` 这批已写好的存量文档，按每份文档的实际真实进展（已实现 → `verified`、已归档/被取代 → `superseded`、进行中 → `implementing` 等）填对应状态，不留一批"未知状态"的历史数据。回填触碰 anatomy 时按 same-commit 规则同步处理。详见「当前决策」9。
9. **[已决策——2026-07-12 human 拍板] 状态转换的 owner**：原问题是"`approved → implementing` / `implementing → verified` 是否要 human 每次流转确认，还是 agent 可自主标记"。**决定：agent 自主标记，human 审 PR 时复核**——不要求每次流转停下来问 human；`implementing`/`verified` 是可由证据判断的事实（有没有对应 commit、测试是否通过），agent 据证据自主标记，human 在 PR review 环节统一把关。`draft → in-review → approved` 仍由 human 批注驱动（approved 本身是 human gate，不变）。详见「当前决策」10。
10. **[已决策——2026-07-12 human 拍板] fresh session 的状态感知路径**：事实结论（Codex 三审一手核实）是：`context_continuity.py` 只读 `memory/current-status.md`、不读任何 plan 文件；Codex 配置只在 `SessionStart(clear)` 与 `PostCompact` 调它，真实 startup 不调用（`source=startup` 定向实跑无输出）；且当前 status 无本 plan 指针。**决定：方案 a+b 两者都做**（不是二选一）——(a) **主动入口纪律**：CLAUDE.md / AGENTS.md 等入口文档要求 session 开始时主动查当前 approved plan；(b) **同时**把当前 approved plan 的指针写进 `memory/current-status.md`（`context_continuity.py` 已经读这个文件），并**评估是否要扩展 hook 覆盖 `startup` 场景**（Codex `SessionStart(startup|resume)`、Claude 对等事件）。不要把 `plans/ANATOMY.md` 当成已存在的注入源，除非同时改 hook 读取面。详见「当前决策」11。
11. **[Codex 侧，已回答] 双 runtime 冒烟应作为验收证据。** 本次真实 Codex 审查已经证明“配置里有 hook”与“fresh startup 会获得状态”不是同一件事：静态 parity / `sync --check` 无法发现 matcher 未覆盖 startup，也无法证明运行时 trust 与注入结果。因此实现后至少做一次 Claude + Codex 的双 runtime 冒烟，并把 **fresh startup** 与 **compact/clear 恢复**分成两个 case；validator/adapter parity 仍必跑，但不能替代 runtime smoke。受本次会话边界限制，项目 hook trust 是否已批准、`UserPromptSubmit` 是否自动执行没有可读日志可实锤，冒烟记录应显式保存可见注入输出或 hook 日志，而不是以“session 能启动”代替。

## 验证标准（本轮：方案文档本身）

- 本 plan doc 经 human 拍板**完全收敛**：问题 1（覆盖范围）、2（注册表落点）、3（#14 边界）、4（#12 边界）、5（过期 approval 判定）、6（是否要机械拦截）、7（fixtures 落点）、8（存量回填）、9（状态转换 owner）、10（fresh session 状态感知修复）均已由 human 亲自定案；问题 11 已由真实 Codex 审查收敛为"必须做双 runtime、双边界冒烟"。**当前无剩余待拍板 open question。**
- Allowed paths / Forbidden paths 从"实现阶段草案"收敛为确定清单（含 Codex 侧生成产物与权限面的处理约定）。
- （进入实现阶段后追加，见任务树"验证收口"）：`python scripts/validate-governance.py` 通过；新校验对 fixtures 的正向/三类异常各自给出正确结果；`python scripts/check-anatomy-drift.py` 通过；若改了 skill/脚本/权限面，`python scripts/sync-codex-adapters.py --check` 与（视情况）`python scripts/check-agent-harness.py` 通过，Codex adapter 无 stale/漂移。

## 下一步

- **全部 open question（1–10）已由 human 拍板，11 为验收纪律；本文件无剩余待批注分歧。** 计划已具备进入实现的收敛条件，只等 human 批准转入实现 / 提交 plan revision commit。
- 实现阶段按已决策 11（方案 a+b）接入当前 plan 指针：入口纪律写进 CLAUDE.md/AGENTS.md，指针写进 `memory/current-status.md`，并评估扩展 startup hook；无需再把"读 `context_continuity.py` 源码"列为探索任务，本轮已完成源码核实与 startup/clear/PostCompact 定向探针。
- 实现前决定：是先出一个"仅状态模型 + 校验脚本"的最小实现 PR，还是把 skill 接线 / anatomy 更新 / 存量回填一次性做完；随后转 `worktree-pr-flow`。

## Plan revision log

- 2026-07-12 初稿。盘点现状（`DECISIONS.md` 状态枚举、`change-control.yaml`、`release-gates`/`regression-matrix` 的占位符容忍校验范式、`branch-status.md` 的 Plan doc 字段、`plans/` 目前无 ANATOMY/根路由），据此起草状态模型草案与任务树；未解决问题聚焦覆盖范围切分、证据落点三选一，以及与 #12/#14 的边界。
- 2026-07-12 第二意见审查（Claude Opus 4.8，代替额度耗尽的 Codex gpt-5.6-sol 二审；人类最终批准仍待定）。补 Codex 侧缺口：新增「双 runtime 一致性」子节（状态锚点/validator 走 runtime-neutral、Codex SessionStart/UserPromptSubmit 挂点证据、skill canonical→`.agents/` sync 义务、两侧权限面对称）；Allowed/Forbidden paths 补 `.agents/skills/**` 生成产物与 `.codex/` 权限面处理约定；任务树加 sync 重生成、双 runtime 状态感知接线；验证收口加 `sync-codex-adapters.py --check` / `check-agent-harness.py` / 可选双 runtime 冒烟；新增未解决问题 10（`context_continuity.py` 是否 surface 当前 plan 状态，待读源码核实）、11（是否要双 runtime 冒烟作为验收证据）；强化"不加阻断类 hook"非目标的 runtime 论据。
- 2026-07-12 Codex（gpt-5.6-sol, medium）真实二审（区别于上一轮 Opus 代打；人类最终批准仍待定）。一手核实 `context_continuity.py` 只读 `memory/current-status.md`，Codex 仅在 `SessionStart(clear)`/`PostCompact` 接线，startup 探针无输出且当前 status 无 plan 指针，故否定“fresh session 已自动感知 plan”的原推断；问题 10 收敛为两个待选修复路径，问题 11 收敛为必须分别验证 startup 与 compact/clear 的双 runtime smoke；同时记录本会话无法从可读日志实锤 hook trust 与静默 `UserPromptSubmit` 自动触发，避免过度声称。
- 2026-07-12 **human 亲自拍板**（非 agent 二审）。对两个最大 open question 直接定案并落地整合：(1) **覆盖范围=四类都做**——brief/plan/review/decision 统一生命周期状态，用一份 YAML 注册表登记各文档的 draft/in-review/approved/implementing/verified/superseded 状态及其关联的 issue/branch/worktree/human approval/上下游引用（理由：四类相互关联，分开做制造割裂，要有统一审核机制防漂移防返工）；(2) **新增机械拦截 hook**——不只靠事后 validator，在编辑动作阶段拦"状态/引用完整性"这类可判定事实（如 approved 前缺 scope/forbidden/verification、注册表引用悬空），并明确修正此前"本 issue 不加阻断类 hook"的非目标（改为有意破例、但严格限定拦可判定事实、不替 human 做主观判断）。据此扩写「当前目标/范围/非目标/现状盘点结论/Allowed·Forbidden paths/任务树/验证标准」，任务树新增「YAML 注册表设计」与「机械拦截 hook 设计」两个顶层分组，并把 hook 的双 runtime 手写挂载纪律写进设计约束；原未解决问题 1、6 就地改写为「已决策」保留可追溯性。
- 2026-07-12 **human 逐条拍板**（选择题形式，覆盖此前余下的全部 open question）。三项决定：(1) 四类文档的 YAML 注册表落点 = 新建 `memory/doc-lifecycle.yaml`（不扩展 `memory/change-control.yaml`，不复用 `human/decisions/`）；(2) 新增的机械拦截逻辑折进现有 `.claude/hooks/pre_tool_guard.py`（不新建独立 hook 文件——实测确认 `.claude/settings.json`/`.codex/config.toml` 已挂载同一物理文件，本轮不需要新增两侧挂载点，这是相比独立新建 hook 方案的直接优势）；(3) 不为 #14（多 agent 状态控制面）预留跨 agent 读取接口，`memory/doc-lifecycle.yaml` 就是普通文件，#14 需要时自己直接读，不需要 #13 提前设计专用协议。据此把「当前决策」扩至 5 条、任务树「YAML 注册表设计」「机械拦截 hook 设计」两组落定具体文件名/实现方式并同步简化双 runtime 挂载纪律、Allowed/Forbidden paths 去掉"待定候选/二选一"表述、未解决问题 2/3 标记已决策、验证标准与下一步同步收窄为只剩问题 10 待拍板。
- 2026-07-12 **human 拍板剩余全部 open question**（4/5/7/8/9/10，权威决定直接落地）。六项决定：(4) #12 adoption phase 与 #13 lifecycle 状态各自独立、不统一成一套状态机；(5) "过期 approval" 仅按"引用被标 superseded"这一种触发，不做时间窗口/内容漂移；(7) fixtures 采用脚本内嵌/无依赖断言、不新开 `tests/`（与 #17 一致）；(8) 存量 plan doc（20260709/20260711/20260712）按实际真实进展批量回填 Status；(9) `approved→implementing→verified` 由 agent 自主标记、human 审 PR 时复核；(10) fresh session 状态感知修复采用方案 a+b（入口纪律 + `memory/current-status.md` 指针并评估扩展 startup hook）。据此把「当前决策」扩至 11 条、未解决问题 4/5/7/8/9/10 全部改写为「已决策」、非目标补记 #12 独立判定、任务树「校验规则设计」落定过期判定规则，「skill/流程接线」新增"入口纪律接线"子任务并把状态 owner 收敛为 agent 自主、「双 runtime 状态感知接线」落定 a+b、「fixtures」标注内嵌无外部目录、「迁移」新增"批量回填存量 plan doc 状态"具体子任务，验证标准/下一步收窄为"无剩余待拍板"。**核实结论：本文件现已无剩余 open question——问题 1–10 全部由 human 拍板，11 为真实 Codex 审查收敛的验收纪律，无一处仍标"待拍板/待 human 落笔"。**
