# 多 Agent 状态/通信/Handoff 控制面 —— 交互式计划

> 这是 human 与 Claude Code 的协商界面：Claude 写初稿 → human 在「Human 批注区」批注 → Claude 读 diff、收敛 → 每次采纳的修订做一个小 commit。实现只在 scope / forbidden paths / verification 清楚后开始。
>
> 触发背景：GitHub issue #14。这是这批 issue 里范围最大、最容易发散的一个（涉及 Paseo 集成、agent identity/lease/mailbox schema、冲突检测）。本文刻意把「第一版最小可用范围」与「明确推迟」分开写，不在这一份计划里设计完整分布式系统。

## 当前目标

给模板加一层 **repo-native、runtime-neutral、可持久化、可恢复** 的多 agent 协作控制面（第一版，最小可用）：

1. **状态可发现**：任意 agent 能读到「现在有哪些 agent、在做什么、状态如何」（只读 list/status），不必依赖人工问或临时消息。
2. **消息可持久化**：agent 间的关键消息/决定/交接摘要**回写 repo**（不只留在 Paseo 临时会话里），fresh session 也能读到。
3. **Handoff 可验证**：任务所有权从一个 agent 转移到另一个 agent 时，有明确的 schema 与接收确认，而不是「聊天里说了一声」。
4. **冲突可检测**：两个 agent 声明/试图写同一 ownership 路径时，在写入或 merge 前给出明确信号（不是事后才发现）。
5. **写错 worktree 可自动检测**：有负向 fixture 覆盖，不只靠 prompt 自检（`launch-packet.md` 里的 `self-check` 字段目前只是文档提醒，不是机器检查）。
6. **Paseo-first，直接复用 spawn skill 已交付的机制**（human 拍板，见「当前决策」）：第一版**不是 abstract-adapter-first**，而是直接依赖 PR #21 已 merge 的 `.claude/skills/spawn/SKILL.md` 提供的 launcher（`paseo run --json --detach ...` 起持久可交互的 Paseo-tab agent）、`memory/agents-roster.md` 花名册（name↔paseo-id 解析）与 `paseo send <id>` 通信原语。本 issue #14 在这套既有地基上补 list/status 查询、结构化 inbox/outbox、冲突检测、handoff 摘要回写、heartbeat/stale 检测，**不重新发明 spawn/命名/通信机制**。抽象出跨 runtime 的统一 adapter contract、支持其它 runtime（如 issue 原文提到的 LingTai）是**未来工作**，不在本版范围（见「非目标」）。

> **runtime-neutral 在本 repo 的具体含义（issue #14 标题即「runtime-neutral」，是硬约束不是口号）**：本模板同时被 Claude Code 与 Codex 两个 runtime 消费，canonical 能力在 `.claude/`，Codex 侧 `.codex/agents/*.toml`、`.agents/skills/**` 由 `python scripts/sync-codex-adapters.py` 生成，`.codex/config.toml`、`.codex/rules/default.rules` 则是手维护。因此「runtime-neutral」在这里**不只**指「不依赖 Paseo」，还必须满足：(a) 控制面的核心是**纯 `python scripts/...` + repo 文件读写**，Claude 与 Codex 都能等价调用，不走 Claude 专属的 Task/subagent 机制；(b) 任何机器强制（hook 层冲突/写错 worktree 检测）要么折进两侧**已共享**的 `.claude/hooks/pre_tool_guard.py`（`.codex/config.toml` 已挂同一脚本，一处改两侧生效），要么新起 hook 时**必须同时**手工接进 `.claude/settings.json` 与 `.codex/config.toml`；(c) 新增 skill 必须跑生成器同步出 `.agents/skills/**`，否则 `check-agent-harness.py` 会 FAIL；(d) 控制面实现后至少有一次「真实 Codex 表面跑通」的 smoke 证据，不能只用合成 JSON 代替。本轮 Codex 真实二审已验证现有 Codex/Paseo/trust/hook 配置基座，但新控制面尚未实现，故功能级 smoke 仍属于步骤 6.4 的验收项。

## 非目标（明确推迟，不在本轮设计/实现）

- **不实现完整分布式调度系统**：不做任务队列、不做自动任务分配、不做跨 agent 的自动重试/失败转移。
- **不做重型分布式锁**：不引入真正的互斥锁/共识协议；ownership 冲突处理停在「检测 + 明确信号」，不做自动排队/自动抢占。
- **不做 merge queue 自动化**：本轮只做「写入前/merge 前的冲突预警」，不做自动排序合并、不做自动 rebase/resolve。
- **不做实时低延迟通信**：repo 是 eventually-consistent 的可信状态层；低延迟通信继续交给 runtime（Paseo `send`），repo 只保证「关键内容最终落盘、可恢复」。
- **不做 abstract-adapter-first**：第一版是 Paseo-first（human 拍板），直接用 spawn skill 的 Paseo 机制，不先抽象出一层 runtime-neutral adapter 再往下填 Paseo 实现。
- **不实现 LingTai 或其他 runtime 的具体 adapter**：支持其它 runtime 是未来工作；本版最多在 doctrine 里留一句「后续可评估其它 runtime adapter」的方向说明，不写实现、不设计 contract 形状。
- **不重造 spawn skill 已交付的机制**：PR #21（`feat/agent-identity` 史上 Phase 3）已交付 `.claude/skills/spawn/SKILL.md`，实现了「`paseo run` 起持久可交互 agent + 出生即命名（Paseo tab + statusline 双表面）+ `memory/agents-roster.md` 花名册登记（`agent_name_set.py --register --paseo-id ... --worktree ...`）+ `paseo send <id>` agent↔agent 通信（send 认 id 不认 name）+ 非 Paseo 表面退回 in-session 兜底」。本 issue #14 **只在此之上增量**，不重写起 agent / 命名 / 通信这条链路。分工边界：**spawn skill 负责「起 agent + 命名 + 通信原语（`paseo send`）」；#14 负责「在此之上建 list/status 查询、结构化 inbox/outbox、冲突检测、handoff 摘要回写、heartbeat/stale 检测」**。
- **不做自动冲突解决/自动合并**：检测到冲突后如何处理（谁让路、怎么改）仍是人或 agent 的决策，不自动化。
- **不做跨 repo / 跨 project 的控制面**：范围限定在单 repo 内的多 agent 协作。
- **不与已交付的 spawn skill（PR #21，`.claude/skills/spawn/SKILL.md`）重复设计「唤起/命名/通信 agent」**：spawn skill 是「怎么方便地起一个新 agent 并让它可被命名、可通信」，已经 merge、是本计划直接依赖的地基；本计划是「已经在跑的多个 agent 之间怎么互相发现（list/status）、结构化落盘通信、交接、避免冲突」。两者共享 identity/roster 基础设施，#14 是 spawn skill 的上层增量，不重写它的 launcher/命名/`paseo send` 链路。
- **不重造已有机制**：identity/命名（`.agent/agent-identity.md`，Phase 1/2 已落地）、spawn skill（`.claude/skills/spawn/SKILL.md`，PR #21 已交付的 launcher/roster 登记/`paseo send` 通信）、session tree（`memory/session-tree.md`）、branch status（`memory/branches/<slug>.md`）、handoff 模板（`.agent/templates/handoff.md`）、task packet（`.agent/templates/launch-packet.md`）已存在，本计划是在这些之上**补齐**「实时状态查询、结构化 mailbox、heartbeat/lease、冲突检测、handoff 摘要回写」，不是重写它们，也不重造 spawn skill 的起 agent/命名/通信原语。

## Branch / worktree

- Branch：`feat/14-multi-agent-control-plane`
- Worktree：`.claude/worktrees/14-multi-agent-control-plane`

## Linked issue / PR

- Issue：`#14`
- PR：待计划收敛后开（human gate，需明确批准才 `gh pr create`）。

## Allowed paths

- `.agent/multi-agent-control-plane.md`（新 doctrine 文件，主 schema/协议定义）
- `.agent/AGENTS.md`（索引登记）
- `.agent/templates/handoff.md`（扩展 agent-to-agent handoff 变体）
- `.agent/templates/launch-packet.md`（若需要补充 ownership 声明字段）
- `.agent/checklists/pre-parallel.md`（若冲突检测机制改变了「并行前先问」的清单）
- `.agent/agent-identity.md`、`.claude/hooks/agent_identity.py`、`agent_identity_hook.py`、`agent_name_set.py`（在已有身份层上扩展 status/heartbeat 字段，不推翻 Phase 1/2 已落地设计）
- `.claude/skills/spawn/SKILL.md`（**既有基础设施，只读/复用为主**：PR #21 已交付的 launcher/命名/`paseo send` 机制。#14 在其之上建控制面；仅当需要为它补一个「起 agent 后如何登记结构化状态/mailbox」的挂接说明时才轻量增改，不重写其 spawn/通信逻辑）
- `memory/agents-roster.md`（**既有花名册，spawn skill 与 `agent_name_set.py` 已在写**：name↔paseo-id↔worktree 的真相源。#14 复用它做 name 解析与 presence，扩展字段或旁挂结构化状态文件，须与既有维护逻辑对齐，避免双份真相源）
- `memory/mailbox/**` 或等价的新 mailbox 存储路径（新增，路径形状待收敛）
- `.claude/skills/`（若需要新增 `agent-status` / `agent-message` 一类 skill）
- `.agents/skills/**`（**生成物**：新增 skill 后由 `python scripts/sync-codex-adapters.py` 生成的 Codex 侧 skill；不手改，跑生成器产出）
- `.codex/config.toml`（**手维护，非生成物**：若冲突/写错-worktree 检测走「新起独立 hook」而非折进 `pre_tool_guard.py`，需在此手工挂上，与 `.claude/settings.json` 平行；否则 Codex 侧不触发该检查）
- `.claude/hooks/pre_tool_guard.py`（若把写前冲突/写错-worktree 检测折进已被两侧共享的地板 hook——优先此路线，一处改两侧生效）
- `.claude/settings.json`（若新增 hook 需在 Claude 表面挂接）
- `scripts/agent-status.py`、`scripts/check-agent-conflicts.py` 等新校验/查询脚本（具体命名待收敛；须为纯 `python`、无 runtime 依赖，Claude/Codex 等价可跑）
- `scripts/sync-codex-adapters.py`（一般不改逻辑；新增 skill 后**跑它**同步 `.agents/skills/**`，`check-agent-harness.py` 内部会 `--check`）
- `scripts/validate-governance.py`、`scripts/check-agent-harness.py`（挂接新检查，若适用）
- `scripts/tests/**` 或等价目录（wrong-worktree 负向 fixture、冲突检测测试、双 agent smoke、Codex `apply_patch` 工具形状测试）
- `DESIGN.md`、`ANATOMY.md`、各子目录 `ANATOMY.md`（同 commit 同步结构变化）
- `memory/current-status.md`、`memory/session-tree.md`、`memory/branches/14-multi-agent-control-plane.md`（本分支自身状态记录）
- `CHANGELOG.md`、`VERSION`（若发版，走 human gate）

## Forbidden paths

- `lab/data/**`、`lab/runs/**`、`lab/models/**` bytes、`checkpoints/**`、`wandb/**`、`lab/infra/private/**`、`.env`（标准红线）
- **不改远端 Paseo 基础设施配置**：不碰用户全局 Paseo 安装/配置（如 `~/.paseo/**` 之外或其内部的可执行文件/服务配置），只允许**只读**调用其已安装的 CLI（`paseo ls`/`paseo send`/`paseo agent update` 等）；不新增/不修改 Paseo 自身的运行时行为。
- 不碰其他不相关的 worktree（`.claude/worktrees/case+agent-r1-adoption-replay/`、`.claude/worktrees/case+elf-template-replay/` 等）。
- **不手改生成物**：`.codex/agents/*.toml`、`.agents/skills/**` 由 `sync-codex-adapters.py` 生成，只能改 canonical（`.claude/`）后重跑生成器，不手动编辑（见 `.codex/CLAUDE.md`）。`.codex/config.toml` 与 `.codex/rules/default.rules` 是手维护 canonical，可改，但改动须与 `.claude/settings.json` / `.agent/action-boundary.md` 对齐。
- 不实现/不引入真正的分布式锁、消息队列中间件或额外的常驻服务进程（与「非目标」一致）。
- 不在本轮改 `lab/` 下与本功能无关的内容。
- 不 push `main`、不开 PR/merge/release，除非 human 明确批准（`.agent/action-boundary.md`）。

## 任务树

> **Paseo-first（human 拍板）**：本任务树从头到尾直接坐在 spawn skill（PR #21）已交付的 Paseo 机制上——list/status 读的是 spawn skill 已在写的 `memory/agents-roster.md`（name↔paseo-id），通信复用 `paseo send <id>`，起第二个 agent 复用 `paseo run --json --detach`。**不先做一轮「不依赖 Paseo 的 repo-native fixture smoke」再决定要不要接 Paseo**；双 agent smoke 用**真实 Paseo-tab agent**跑（见 3.3）。原「步骤 5 Paseo adapter 放最后」的排法作废：Paseo 集成前移到贯穿 2–4 步，步骤 5 收敛为「确认复用面 + 无 Paseo 兜底测试」而非从零造 adapter。

- [ ] 0. 收敛本计划（human 批注 → 定 storage 介质、拦截点顺序、TTL 数值等 open questions；Paseo 接入时机已由 human 拍板，见「当前决策」，不再是 open item）
- [ ] 1. Schema 设计（doctrine，不涉及运行时代码）
  - [ ] 1.1 定义 agent state schema：复用 identity（persona/动作/focus），新增 `task`、`owned_paths`/`forbidden_paths`、`worktree`、`status`（active/idle/blocked/done/stale）、`heartbeat`（timestamp + TTL）、`inbox_ref`/`outbox_ref`
  - [ ] 1.2 决定存储介质：扩展 `memory/agents-roster.md`（markdown 表格）vs 新增每 agent 结构化状态文件（供脚本读写）——open question，见下
  - [ ] 1.3 定义 mailbox schema：inbox/outbox 的最小字段（from/to/timestamp/kind/summary/ref/read-state）
  - [ ] 1.4 定义 agent-to-agent handoff schema（扩展 `.agent/templates/handoff.md`，区分「session handoff（同一 agent 跨 session）」与「ownership handoff（任务转移给另一个 agent，需接收方 ack）」）
  - [ ] 1.5 写 `.agent/multi-agent-control-plane.md` doctrine 文件，登记进 `.agent/AGENTS.md` 索引。**doctrine 用 runtime-neutral 语言**：接口一律描述为「跑 `python scripts/...`」而非「用 Claude 的 subagent/Task」，明确标注哪些字段/命令在 Claude 与 Codex 下等价、哪些是 runtime 特有（如 statusline `🤖` 仅 Claude 表面渲染，Codex 无 statusLine，见 open question）。
- [ ] 2. 只读 list/status（先落最小可用、无写副作用）
  - [ ] 2.1 查询脚本（如 `scripts/agent-status.py`）：读 spawn skill 已在维护的 `memory/agents-roster.md`（name↔paseo-id↔worktree）+ 新增状态文件，输出「谁在跑、做什么、状态、心跳新鲜度」。可选叠加 `paseo ls --json` 做「roster 里登记的 agent 当前 Paseo 是否还活着」的实时校验（缺 Paseo 时降级为纯 repo 视图）
  - [ ] 2.2 staleness 判定：心跳超过 TTL → 标记 stale，供后续冲突检测复用
  - [ ] 2.3 定向测试：正常/stale/无心跳字段等场景
- [ ] 3. 双 agent 发现 + 消息 + handoff smoke（对应验收标准 #1 #2）
  - [ ] 3.1 mailbox 读写：发送方写 outbox + 追加对方 inbox；关键决策回写规则（哪些消息类型必须落盘，不能只留在临时会话）。**低延迟通知复用 spawn skill 的 `paseo send <id>`**（送达提醒），mailbox 落盘负责「可恢复、可查」的结构化真相层——二者分工，不重造消息传输
  - [ ] 3.2 handoff 流程：发起方声明转移 → 写 handoff 记录 → 接收方读取并 ack（状态从 pending 到 accepted）
  - [ ] 3.3 端到端 smoke：**用真实 Paseo-tab agent（不是 fixture 模拟）**——用 spawn skill 的 `paseo run --json --detach` 起第二个 agent（自动进花名册），两个真实 agent 互相发现状态（`agent-status.py`）、经 `paseo send` + mailbox 落盘发消息、完成一次 handoff。纯 repo-native fixture 双 agent 仅作为「无 Paseo 环境也能跑 smoke」的兜底测试（对应步骤 5.3 的 fallback 证据），不作为主验收路径
  - [ ] 3.4 重启恢复测试：清掉 session 上下文后，fresh session 仅凭 repo 文件恢复「谁拥有这个任务」+「有哪些未读消息摘要」（对应验收标准 #2）
- [ ] 4. 冲突检测 + 写错 worktree 检测（对应验收标准 #3 #4）
  - [ ] 4.1 owned/forbidden path 重叠检测：扫描当前活跃（非 stale）agent 声明的路径，发现重叠给出明确信号
  - [ ] 4.2 拦截点：写入前（`pre_tool_guard.py` 层，轻量检查）与 merge/PR 前（validator 层，全量检查）——顺序与优先级待 human 拍板（见 open questions）。**两侧对等强约束**：`pre_tool_guard.py` 已被 `.claude/settings.json` 与 `.codex/config.toml` **共同**挂载，所以**首选把写前检测折进这个已共享的地板 hook**（一处改、两侧生效）；若不得不新起独立 hook，必须同时手工接进 `.claude/settings.json` 与 `.codex/config.toml`，否则 Codex 侧静默不触发。另注：Codex 写文件走 `apply_patch` 工具（`pre_tool_guard.py` 已对其单列分支），故任何基于 tool_input 的路径提取必须同时覆盖 Claude 的 `Edit`/`Write` 与 Codex 的 `apply_patch`（含 `*** Add/Update/Delete/Move` patch 头），不能只认 `file_path`。
  - [ ] 4.3 写错 worktree 负向 fixture：declared worktree（状态文件）vs 实际 `git rev-parse --show-toplevel` 不符时，自动检测并报错（不依赖 prompt 自检）。检测逻辑放**纯 python 脚本**（Claude/Codex 都能 `python` 调）；若同时想在 hook 层拦，遵循 4.2 的两侧挂载约束。
  - [ ] 4.4 轻量 file lease 评估：heartbeat+TTL 是否足以防「陈旧 agent 误判为仍持有 ownership」；若不够，加一个最小锁文件（谁在写、何时过期），明确不做 merge queue
- [ ] 5. Paseo 复用面收敛 + 无 Paseo 兜底（Paseo-first，**不从零造 adapter**；本步是把 2–4 步已贯穿使用的 Paseo 机制统一收口，不是「最后才接 Paseo」）
  - [ ] 5.1 复用面梳理：明确本控制面直接调用的 spawn skill Paseo 原语——`paseo run --json --detach`（起 agent）、`paseo ls --json`（presence 实时校验）、`paseo send <id>`（通信）、`memory/agents-roster.md`（name↔paseo-id 解析）。列出 #14 新增的薄封装（若有，如把 `paseo ls` 结果与 roster 对账的小函数），与 spawn skill 已有函数（如 `agent_name_set.py._paseo_rename` 的降级先例）对齐，不重复实现。
  - [ ] 5.2 无 Paseo 兜底：缺 Paseo（无 CLI / 非 Paseo 表面 / 缺 `PASEO_AGENT_ID`）时，list/status/mailbox 退回纯 repo 视图、`paseo send` 通知退回「只落盘不实时提醒」，全程不 raise——沿用 spawn skill「非 Paseo 表面退回 in-session」的兜底策略。**本轮 Codex-under-Paseo 实测已确认**：当前真实 Codex companion session 同时有 `CODEX_THREAD_ID`、`CODEX_COMPANION_SESSION_ID` 与 `PASEO_AGENT_ID`，且 `CHROME_DESKTOP=Paseo.desktop`；但仍不得把该 env 当成所有 runtime/启动方式的唯一判据，缺 env 走 fallback、不 raise，并用测试覆盖。
  - [ ] 5.3 Paseo integration smoke test（真实 `paseo` CLI + 真实 Paseo-tab agent，对应 3.3 主路径）+ Paseo unavailable fallback test（无 `paseo` 时优雅降级、不 raise；该 fallback 路径即等价于「Codex 侧若无 Paseo env 也能跑」的证据，二者复用同一 no-Paseo 分支）
  - [ ] 5.4 （**未来工作，非本版**）doctrine 里留一句方向说明：后续若要支持其它 runtime（如 issue 原文提到的 LingTai），可评估把这些 Paseo 原语抽象成统一 runtime adapter contract。本版不写该 contract、不做 Paseo 之外的实现。
- [ ] 6. 多 agent 对抗测试 + 治理收尾
  - [ ] 6.1 对抗场景测试：两个 agent 同时声明同一 ownership 路径、其中一个 stale 后另一个接手、消息未读堆积等
  - [ ] 6.2 `ANATOMY.md`/`DESIGN.md`/`.agent/AGENTS.md` 同步；`memory/branches/14-multi-agent-control-plane.md` 落地。若新增了 skill：`python scripts/sync-codex-adapters.py` 生成 `.agents/skills/**`，并同步 `DESIGN.md §10` 能力清单计数（否则 `check-agent-harness` 告警）。
  - [ ] 6.3 `python scripts/validate-governance.py --strict` / `check-agent-harness.py --strict`（内部含 `sync-codex-adapters.py --check`，会捕获 Codex adapter 漂移）/ `check-anatomy-drift.py` 通过
  - [ ] 6.4 **双 runtime 对等收尾**：(a) `python scripts/agent-status.py` 等新脚本以裸 `python` 跑通（证明不依赖任一 runtime 的 Task/subagent 机制）；(b) 若冲突/写错-worktree 走 hook 层，验证其在 `.codex/config.toml` 里已挂载、且对 `apply_patch` tool_input 形状能触发（先用喂 JSON 到 hook 的定向测试证明路径解析/deny，再在真实 Codex session 做一次无副作用或临时 fixture 的 end-to-end deny smoke）；(c) 在本轮已证实 Codex/Paseo/trust 基座可用的前提下，记录一条「实现后的控制面在真实 Codex 表面跑通」的命令与输出。若届时环境确实不可得，才降级为明确 open item，不能用 Claude 或合成测试冒充。
  - [ ] 6.5 起草 PR（human gate，需明确批准才 `gh pr create`）

## Human 批注区

> Paseo 接入时机已由 human 拍板（Paseo-first，见「当前决策」），不再需要批注。剩余可批注项：storage 介质选哪种、TTL 数值、拦截点顺序、mailbox 粒度、是否把 `agent-status` 独立成 skill 还是并入 spawn skill；以及 Codex 侧相关问题（是否要求真实 Codex smoke、冲突检测走「折进 pre_tool_guard」还是「新起独立 hook」）。

## 当前决策

- **Paseo 接入时机 —— 已由 human 亲自拍板（2026-07-12）：现在就直接对接 Paseo，Paseo-first。**
  - **决策**：第一版就是 Paseo-first，直接依赖 PR #21（已 merge，`.claude/skills/spawn/SKILL.md`）已交付的 launcher（`paseo run --json --detach`）、`memory/agents-roster.md` 花名册（name↔paseo-id 解析）与 `paseo send <id>` 通信原语。**不**把 Paseo adapter 推到最后一步，**也不**要求先做一轮「不依赖 Paseo 的 repo-native fixture smoke」再决定要不要接。双 agent smoke 用真实 Paseo-tab agent 跑，fixture 仅作无-Paseo 兜底测试。
  - **理由（human 原话）**：「现在就要对接 Paseo，它确实是给我们提供了很多方便的；比如可以看这个 pr（PR #21）通过 Paseo 可以很方便的实现 multi agent 的通话；后面我们可以再考虑别的实现方案」。即：spawn skill 已把「起 agent + 命名 + 花名册登记 + `paseo send` 通信」的地基打好，#14 只需在其上补 list/status、结构化 inbox/outbox、冲突检测、handoff、heartbeat/stale，不重造轮子。
  - **未来工作（非本版）**：支持其它 runtime（如 issue 原文提到的 LingTai）、抽象统一 adapter contract，后续可评估，第一版不做。

## 未解决问题

1. **状态存储介质**：继续扩展 `memory/agents-roster.md`（markdown 表格，人类可读但程序解析脆）；还是新增结构化状态文件（如每 agent 一个 `memory/agents/<name>.status.yaml`/`.json`，roster 表格降级为聚合视图）？后者利于脚本读写与冲突检测，但多了一层文件、需要与现有 roster 维护逻辑（`agent_name_set.py`）对齐，避免双份真相源。
2. **mailbox 落盘粒度**：每 agent 一个 `inbox.md`/`outbox.md`（人读友好，但并发追加需处理）；还是单一 append-only log（如 `memory/mailbox.log`，机器友好，需要脚本生成 per-agent 视图）？
3. **heartbeat/TTL 具体数值与触发时机**：多久没心跳算 stale（如 30 分钟/2 小时）？由谁触发心跳更新——每次工具调用太重，session boundary（compact/clear/结束）触发是否够用，还是需要更高频的机制？
4. **冲突检测拦截点的优先级**：写入前（`pre_tool_guard.py`，轻量、实时但只能看到当前 hook 调用瞬间的状态）与 merge/PR 前（validator，全量但发现晚）都要做，还是先做一个、验证有效后再加另一个？
5. **与 spawn skill（PR #21）的关系**：Paseo-first 已定；剩下的是 skill 边界——是否把「只读 list/status（`agent-status`）」独立成新 skill，还是并入/紧贴 spawn skill（后者已管起 agent + 命名 + 通信）？倾向独立 skill（关注点：spawn 起 agent，agent-status 查已在跑的），但需避免两者对 `memory/agents-roster.md` 的写入逻辑打架，须与 `agent_name_set.py` 的既有 roster 维护对齐。

### Codex / 双 runtime 相关（本轮二审新增）

6. **冲突/写错-worktree 检测的落点：折进 `pre_tool_guard.py` 还是新起独立 hook？** 前者一处改、`.claude/settings.json` 与 `.codex/config.toml` 都已挂它、两侧自动生效，但会让本已复杂的地板 hook 更重；后者关注点清晰，但必须记得**手工**在两个表面各挂一次（漏挂 Codex 侧就是「设计成 Claude-only」的典型坑）。倾向哪种？（本审查建议：写前实时检测折进 `pre_tool_guard`；全量检测放独立 validator 脚本，两侧都用 `python` 调。）
7. **已由本轮 Codex 实测回答：`PASEO_AGENT_ID` 在 Codex-under-Paseo 表面存在。** 当前 session 的 `/home/user/.codex/sessions/.../<CODEX_THREAD_ID>.jsonl` 证明这是 Codex thread；同一进程环境同时含 `PASEO_AGENT_ID=6ab41037-...`、`CHROME_DESKTOP=Paseo.desktop`、`CODEX_COMPANION_SESSION_ID`。结论仅覆盖当前 Paseo desktop → Codex companion 启动路径，不外推到所有 Codex 启动方式；adapter 仍须「缺 env → fallback、不 raise」。
8. **本轮审查结论：实现验收应要求一次真实 Codex smoke，合成测试只作为前置证据。** 当前真实 Codex session 已能读取 repo-local skills/config，并完成对本计划文件的 `apply_patch`，说明 Codex 表面和普通写路径可用；但普通允许写入不能证明 `pre_tool_guard.py` 的 deny 分支确实被 native hook 调用。现有实锤分三层：(a) 用户级 config 将项目根标为 `trusted`；(b) repo `.codex/config.toml` 把 `PreToolUse` 的 `apply_patch` 挂到 `pre_tool_guard.py`；(c) synthetic Codex JSON 对受保护路径返回 exit 2。三者仍不能替代实现后以临时 fixture 做一次真实 end-to-end deny smoke，因此步骤 6.4 保留该硬验收；若当时不可得，必须明确记录缺口及原因。
9. **本轮审查结论：doctrine 应显式写清 statusline 不对等。** `.claude/settings.json` 有 `statusLine`，`.codex/config.toml` 没有对应展示面；故 roster/结构化状态文件 + `agent-status.py` 才是 presence 的 runtime-neutral 真相源，statusline 只能是 Claude 侧派生便利视图，不能参与 ownership、staleness 或 lease 判定。

## 验证标准

- **Schema（步骤 1）**：`.agent/multi-agent-control-plane.md` 通过 `.agent/AGENTS.md` 索引可发现；`validate-governance` 不因新文件报错。
- **list/status（步骤 2）**：模拟 ≥2 个 agent 状态文件/roster 行，脚本输出的 active/stale 判定与人工核对一致。
- **双 agent smoke（步骤 3）**：对应验收标准 #1——**用 spawn skill 的 `paseo run` 起两个真实 Paseo-tab agent**，能互相发现状态（`agent-status.py`）、经 `paseo send` + mailbox 落盘发送并读取消息、完成一次 handoff（发起 → 接收方 ack → 状态更新）。纯 repo-native fixture 双 agent 仅作为无-Paseo 兜底测试路径。
- **重启恢复（步骤 3.4）**：对应验收标准 #2——清空临时上下文/新开 session 后，仅读 repo 文件即可复述「谁拥有这个任务」+「有哪些未读消息」。
- **冲突检测（步骤 4）**：对应验收标准 #3——构造两个 agent 声明重叠 owned path 的 fixture，检测脚本/hook 在写入或 merge 前给出明确、可读的冲突信号（非静默失败）。
- **写错 worktree（步骤 4.3）**：对应验收标准 #4——构造 declared worktree 与实际 cwd 不符的负向 fixture，自动检测报错，且此检测在测试中可重复触发（不依赖某次 prompt 自检是否被执行）。
- **回写规则（步骤 3.1）**：对应验收标准 #5——针对「关键决策」类消息，有测试验证其必须存在对应的 repo 落盘记录（而非只在临时消息里）。
- **Paseo 复用面 + 兜底（步骤 5）**：对应验收标准 #6——Paseo integration smoke（真实 `paseo` CLI + 真实 Paseo-tab agent 跑通 list/send/status，复用 spawn skill 原语而非新造 adapter）+ runtime unavailable fallback（无 `paseo` 时优雅降级、不 raise）+ 多 agent 对抗测试（步骤 6.1）三类测试都有对应命令与结果记录。
- **双 runtime 对等（步骤 6.4，issue #14 的 runtime-neutral 核心）**：
  - 新查询/检测脚本以裸 `python scripts/...` 跑通，输出与经 Claude/Codex 调用时一致（证明核心不绑任一 runtime）。
  - 若走 hook 层：喂 Codex 形状的 tool_input（`apply_patch` + `*** Update File:` patch 头）到 hook，能触发写前冲突/写错-worktree 检测；且 `.codex/config.toml` 里确有该 hook 的挂载条目（可用 `check-agent-harness` 的 Codex hook 脚本存在性检查兜底）。
  - 若新增 skill：`python scripts/sync-codex-adapters.py --check` 退出码 0（`.agents/skills/**` 与 canonical 同步）。
  - Codex 真实 smoke：实现后在 Codex-in-Paseo 下记录命令/输出；至少覆盖查询脚本与一个临时 fixture 上的 hook deny 路径。只有环境客观不可得时才允许降级为 `memory/branches/14-...md` 中的 open item，并写明原因；**不以 Claude 侧或 synthetic JSON 结果冒充 Codex 端到端验证**。
- **全局**：`python scripts/validate-governance.py --strict`、`python scripts/check-agent-harness.py --strict`（内部 `sync-codex-adapters.py --check`）、`python scripts/check-anatomy-drift.py` 通过；新增/改动的 Python 通过 `python -m py_compile`（或 repo 既有的 lint/format 钩子）。

## 下一步

- Paseo 接入时机已由 human 拍板（Paseo-first，直接复用 PR #21 spawn skill 机制）。仍待 human 批注：storage 介质、TTL、拦截点顺序、mailbox 粒度、`agent-status` 与 spawn skill 的 skill 边界；Codex/双 runtime 项中 #7–#9 已由本轮真实审查给出证据或验收结论，#6（hook 落点）的最终选择仍待 human 与实现复杂度共同确认。
- 批注收敛后，把「当前决策」补全，任务树按最终顺序做小步 commit 式实现，每步验证通过再进下一步。
- 涉及新增依赖（如需要 YAML/JSON schema 校验库）先问，不无理由新增。

## Plan revision log

- 2026-07-12 初稿：按 issue #14 收敛出 6 步任务树（schema → 只读 list/status → 双 agent 发现/消息/handoff smoke → 冲突检测/写错 worktree 检测 → Paseo adapter → 对抗测试/治理收尾）；非目标明确排除完整分布式调度、重型锁、merge queue 自动化、实时通信、LingTai 具体实现；6 个待 human 拍板的 open question（storage 介质、mailbox 粒度、TTL、拦截点顺序、Paseo 接入时机、与 Phase 3 spawn skill 的关系）。
- 2026-07-12 二审修订（Claude Opus 4.8，代替额度耗尽的 Codex gpt-5.6-sol 二审；**人类最终批准仍待定**）：补齐 issue #14「runtime-neutral」硬约束下的 Codex 侧缺口——① 目标区新增 runtime-neutral 的四条具体含义（纯 python 核心 / hook 两侧共享挂载 / skill 须跑生成器 / 需 Codex 侧证据）；② Allowed/Forbidden paths 增列 `.codex/config.toml`（手维护）、`.agents/skills/**`（生成物）、`sync-codex-adapters.py`，并厘清生成物不手改；③ 任务树 1.5/4.2/4.3/5.2/6.2 补 Codex 侧要点（doctrine 用 runtime-neutral 语言、hook 折进 `pre_tool_guard` 或两侧手工挂载、覆盖 Codex `apply_patch` tool 形状、`PASEO_AGENT_ID` 对等存疑走 fallback、新增 skill 跑生成器）；④ 新增步骤 6.4「双 runtime 对等收尾」（PR 顺延为 6.5）；⑤ 验证标准新增「双 runtime 对等」小节（含 `sync-codex-adapters.py --check`、喂 `apply_patch` JSON 到 hook 的形状测试、不以 Claude 结果冒充 Codex 验证）；⑥ 新增 4 条 Codex/双 runtime open question（#7 hook 落点、#8 `PASEO_AGENT_ID` 对等、#9 是否要求真实 Codex smoke、#10 statusline 呈现不对等是否入 doctrine）。未改动初稿的核心任务分解与既有 6 个 open question。
- 2026-07-12 Codex 真实二审（Codex gpt-5.6-sol，medium；区别于上一轮 Claude Opus 4.8 代打；**人类最终批准仍待定**）：在真实 Codex-under-Paseo companion session 核验并收敛 #8–#10——确认当前启动路径注入 `PASEO_AGENT_ID`，确认项目 trust 与 repo Codex hook 挂载配置存在，同时明确 synthetic hook deny 与普通 `apply_patch` 成功仍不足以冒充 native end-to-end deny；因此把实现后的真实 Codex 查询 + 临时 fixture deny smoke 设为硬验收，并将 statusline 明确降级为 Claude 侧派生视图。#7 保留 human/实现阶段最终选择，核心任务分解不变。
- 2026-07-12 **human 亲自拍板（不是 agent 二审）**：定「Paseo 接入时机」这条最大 open question——**现在就直接对接 Paseo，Paseo-first**，第一版直接复用 PR #21（已 merge，`.claude/skills/spawn/SKILL.md`）的 launcher（`paseo run`）/花名册（`memory/agents-roster.md`，name↔paseo-id）/`paseo send` 通信机制，不再把 Paseo adapter 推到最后、也不再要求先做「不依赖 Paseo 的 repo-native fixture smoke」。落地：① 当前目标 #6 改写为 Paseo-first + 明确与 spawn skill 的分工边界（spawn 负责起 agent/命名/通信原语，#14 负责其上的 list/status/结构化 mailbox/冲突检测/handoff/heartbeat）；② 非目标新增「不做 abstract-adapter-first」「不重造 spawn skill 机制」，LingTai/统一 adapter contract 降级为未来工作；③ Allowed paths 补 `.claude/skills/spawn/SKILL.md`、`memory/agents-roster.md` 为既有基础设施（复用/只读为主，非从零新建）；④ 任务树加 Paseo-first 前言，3.3 改为真实 Paseo-tab agent smoke（fixture 降为无-Paseo 兜底），步骤 5 从「造 adapter」收敛为「复用面梳理 + 无 Paseo 兜底」，5.4 明确标注 LingTai/统一 contract 为未来工作；⑤「当前决策」写入 Paseo-first 决策/理由（human 原话）/引用 PR #21；⑥ 原 open question「Paseo 接入时机」删除，其余 open question 重新编号（storage→#1 … spawn skill 关系→#5，Codex 项→#6–#9）。
