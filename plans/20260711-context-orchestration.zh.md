# 主动上下文调配（context orchestration）交互式计划

> 这是 human 与 Claude Code 的协商界面：Claude 写初稿 → human 在「Human 批注区」批注 → Claude 读 diff、收敛 → 每次采纳的修订做一个小 commit。实现只在 scope / forbidden paths / verification 清楚后开始。
>
> 触发背景：GPT-5.6 在 Codex 里因窗口变大更容易越过 272K 长上下文计费线（全请求 2× 输入 / 1.5× 输出）。结论是**不硬限窗口**，而是靠"主动调配"把 context 稳在合适区间。本模板本就按 [gist optimization spirit](https://gist.github.com/a-green-hand-jack/c5ffc265f41763f2c58837e1a0b8b037) 建立，但"主动调配"那半边缺失。

## 当前目标

补齐让上下文"停在合适区间"的**主动调配链**，不硬限窗口。具体三块：

1. **statusline context 表** —— 让 context 占用可见（补上唯一缺的那块仪表盘）。
2. **阈值触发 hook** —— 跨过阈值时把"该 checkpoint / 考虑压缩"注入上下文，把主动压缩从"自觉"变成"信号驱动"。
3. **短上下文连续性 hook** —— compact/clear 后自动回注 `memory/current-status.md` 摘要，接续不断档。

本轮 scope：**只出方案文档**（human 已选）。不写实现代码。

## 非目标

- 不硬性设 `model_context_window` / auto-compact token 限制（那是降概率，不是调配，且损失能力）。
- 不改 Codex 侧 `~/.codex/config.toml`（本模板管的是 Claude Code harness）。
- 不改现有 `pre_tool_guard.py` 的安全边界逻辑。
- 不引入第三方依赖（hook 保持零依赖、可审计）。

## Branch / worktree

- 建议分支：`feat/context-orchestration`（topic 分支，push 走 allow）。
- 本轮只写 `plans/`，可直接在 `main` 上做 doc commit，或等实现阶段再开分支。待批注。

## Linked issue / PR

- 待定。若认为该能力应回流上游 template，可走 `template-feedback` skill 开 `from-downstream` issue。

## Allowed paths（实现阶段）

- `.claude/statusline.sh`
- `.claude/hooks/`（新增 hook + `README.md`）
- `.claude/settings.json`（注册 hook）
- `.agent/`（若需补 principle / checklist）
- `scripts/validate-governance.py` 或 `check-agent-harness.py`（若要把新 hook 纳入校验）
- `plans/`（本文件）

## Forbidden paths

- `lab/data/**`、`lab/runs/**`、`lab/models/**`、`checkpoints/**`、`wandb/**`、`lab/infra/private/**`
- 任何远端产物 / 长训练作业

## 诊断（为什么现在"看不到压缩被触发"）

现有 context 相关机制（`settings.json` 已注册）：

| 机制 | 触发时机 | 局限 |
|---|---|---|
| `pre_compact_memory_check.py` | **PreCompact**：压缩真发生的那一刻 | 反应式、末端、仅提醒(exit 0)。不撞 auto-compact / 不手动 `/compact` 就永不 fire。 |
| `checkpoint-writer` / `session-boundary-agent` subagent | 主 agent 主动调用时 | 没有信号"戳"主 agent 去调，于是从不主动派。 |
| `statusline.sh` | 每次刷新 | 显示 model/dir/branch/worktree/**cost**，**唯独没有 context 占用%**。 |

**根因**：gist #4/#16 与 `.agent/principles.md`「没有仪表盘就别开长途」要求阈值仪表盘 + 阈值触发，但**仪表盘上恰恰缺 context 那块表** → 主 agent 和人都感知不到临界点 → 没人主动派 checkpoint/boundary → 只剩 auto-compact 末端那一下。整条"主动调配"链断在最前端。

对照 gist 18 条：已落地 = repo 控制面(#1-3)、report 隔离(#8)、worktree 所有权(#9)、anatomy(#13)、PreToolUse guard(#14)、validator(#15)、artifact 索引(#17)、model/effort 分级(#18)、checkpoint/boundary/session-tree 的 subagent 本身(#5/#10/#11)。**缺 = #4/#16 的阈值仪表盘与触发点，以及短上下文连续性回注。**

### Codex 复核补充（2026-07-11）

Codex 独立查了一遍，确认「配置存在、`validate-governance.py --strict` 通过，但没有常驻自动压缩守护」，并补了两条我原稿没覆盖的关键约束：

- **硬约束：repo hook 只能发信号，不能可靠替你按 `/compact`。** `PreCompact` 只在宿主 agent 真的进入 compact lifecycle 时才触发；它不会自己监控 token 到 60/70% 然后自动压缩。`pre_compact_memory_check.py` 永远 `exit 0`、只提醒，不会自动调 `checkpoint-writer` 也不会执行 compact。`session-boundary-agent` 同理——没有任何 hook 在每轮 turn 后自动启动它，除非主 agent 遵守协议或人显式说 `Use $session-boundary-control before continuing`。**真正"按下 compact"要宿主 CLI 支持；本方案三块的定位因此全部是"信号/提示"，不是"自动执行"。**
- **运行表面不等价（surface parity）。** `.codex/config.toml` 已确认挂了对等的 `PreCompact` / `PreToolUse` / `PostToolUse` / `SubagentStop`（同样指向 `.claude/hooks/*.py`），所以 Claude 与 Codex 两个表面对齐。但**实际是否触发取决于运行表面**：Claude 要信任 `.claude/settings.json`、Codex 要信任 `.codex/config.toml`；Paseo 启动的 agent 是否继承这些 hook，取决于 provider / mode / cwd / worktree、以及它是否以真正的 project session 启动。已知 `~/.paseo/config.json` 的 `mcp.injectIntoAgents = false`，Paseo 启动的 agent 默认不自动拿到编排能力。→ 这解释了"看不到触发"的另一半：不只是机制被动，某些表面下 hook 根本没接上。

**一句话**：现状是"compact 前提醒 + 人/主 agent 主动调用边界 subagent"，不是"后台自动压缩系统"。本方案不试图违背这条硬约束去"自动 compact"，而是把**信号做强、做可见、做早**，让主动压缩有据可依。

## 过渡缓解（实现前立即可用，来自 Codex 建议）

在长任务开头固定加一句提示，把"主动调配"从模型自觉临时抬成显式协议：

```text
每完成一个阶段或 context 变长时，先运行 $session-boundary-control；
若建议 compact/clear/handoff，先用 checkpoint-writer 更新 memory/current-status.md。
```

这不需要任何代码改动，是三块 hook 落地前的 stopgap。三块做的事，本质就是把这句话从"人每次记得贴"变成"仪表盘可见 + 阈值自动注入"。

## 方案细节（三块）

> 定位统一：三块都是**信号/提示**层，不试图自动执行 `/compact`（见 Codex 硬约束）。目标是让主动压缩"看得见、提醒得早、有据可依"，最终按下 compact 的仍是宿主 CLI + 主 agent 的判断。

### 块 1：statusline context 表（最高杠杆）

- **做什么**：`statusline.sh` 增一段，从 stdin JSON 的 `transcript_path` 读当前 session transcript，估算已用 token，换算成占窗口百分比，拼进现有 ` | ` 面板。
- **估算法**：累加 transcript 里各 message 的字符数 / 4 近似 token（零依赖、够用于阈值判断），或若 JSON 已含 `.cost` 之外的 token 字段则优先用官方字段。窗口大小从环境/常量取（可配 `CLAUDE_CTX_WINDOW`，默认按当前 model）。
- **展示**：`🧠 62%`；≥60% 黄、≥75% 红（终端色码，无色环境降级为 `[!]` 前缀）。
- **降级**：无 `jq`、无 transcript、解析失败 → 不显示这段，绝不报错阻断（沿用现有防御式风格）。
- **对应精神**：#4/#16「没有仪表盘就别开长途」。
- **未决**：token 估算精度 vs 复杂度；是否读官方 token 字段（需确认 statusline JSON 到底给不给 token 计数——见「未解决问题」）。

### 块 2：阈值触发 hook（把主动压缩变信号驱动）

- **事件**：`UserPromptSubmit`（每轮用户输入时触发，能向上下文注入文本）。
- **做什么**：读同一 transcript 估算占用；跨阈值时 `stderr`/stdout 注入建议，例如：
  - ≥60%：`[context] 已用 ~62%。建议：派 checkpoint-writer 落盘 current-status.md；接近任务边界可考虑 /compact。`
  - ≥75%：升级措辞为"现在就 checkpoint 并 compact/clear"。
- **纪律**：纯建议（不 block、不自动 compact）——压缩时机仍由主 agent 在任务边界判断，hook 只提供信号。避免每轮刷屏：同一 session 内每档阈值只提醒一次（用 transcript 目录旁的 marker 文件去重）。
- **对应精神**：#4/#16 阈值操作、#5 在任务边界主动压缩。
- **未决**：阈值数值（60/75 还是 65/80）；去重 marker 放哪（`.omc/` 已是忽略产物区，或 transcript 同目录）。

### 块 3：短上下文连续性 hook（你提的第一个点）

- **事件**：`SessionStart`，`source ∈ {compact, clear}`（Claude Code 会在 compact/clear 后以该 source 触发 SessionStart）。
- **做什么**：读 `memory/current-status.md`，把其摘要（objective / 最近决策 / changed files / next steps）注入新上下文开头，让压缩/清空后立刻恢复"我在干什么、下一步"，不断档。
- **配合 PreCompact**：`pre_compact_memory_check.py` 保证压缩前 status 已落盘（提醒）；本 hook 保证压缩后 status 被读回。一前一后闭环。
- **对应精神**：#5 compact 前更新 status、#11 handoff 文档、你说的「优化短上下文连续性」。
- **未决**：是否只在 status 文件"新鲜"时回注（旧的可能误导）；注入长度上限（避免回注本身吃掉太多 context）。

## 任务树（实现阶段，供本轮批注确认拆分）

- [ ] Parent：主动上下文调配链
  - [ ] 块 1 statusline context 表（独立、可先落地、最高杠杆）
  - [ ] 块 2 UserPromptSubmit 阈值 hook（依赖块 1 的 token 估算，可抽公共函数）
  - [ ] 块 3 SessionStart 连续性 hook（独立于 1/2）
  - [ ] 更新 `.claude/hooks/README.md` 的 hook 表 + `settings.json` 注册
  - [ ] （可选）纳入 validator / 补 `.agent/principles.md` 一条

## Human 批注区

> 在这里批注：改优先级、调阈值、砍某块、加约束。我读 diff 后收敛。

## 当前决策

- 不硬限窗口，走主动调配。（human 已定）
- 本轮只出方案文档，不写实现。（human 已选）
- token 估算走零依赖字符近似，除非确认 statusline/hook JSON 提供官方 token 计数。（初稿默认，待批注）
- 三块定位为"信号/提示"，不追求 hook 自动执行 compact（Codex 硬约束：按下 compact 需宿主 CLI）。（复核已定）
- 本文件所在分支：`feat/context-orchestration`（已从 `main` 拉出，不含 template-upstream-sync 的改动）。

## 未解决问题

1. statusline / hook 的 stdin JSON 是否直接提供 context token 计数？若提供则块 1/2 不必自己估算——**实现前需实测一次 JSON 字段**。
2. 阈值取值：60/75 vs 65/80？
3. 三块的落地顺序：建议 块1 → 块3 → 块2（先仪表盘、再连续性、最后信号注入），还是并行？
4. 这套能力是否回流上游 template（走 `template-feedback`）？
5. **运行表面**：这三块只在 Claude/Codex 真正的 project session 下才生效。Paseo 启动的 agent（`injectIntoAgents=false`）默认接不上——是否需要在方案里显式声明"仅覆盖 Claude/Codex project session 表面"，Paseo 表面另作说明或改配置？

## 验证标准（实现阶段）

- 块 1：构造含 `transcript_path` 的假 JSON 喂 `statusline.sh`，输出含 `🧠 NN%` 且颜色随阈值变；无 transcript 时优雅降级。
- 块 2：喂高/低占用 transcript，验证跨阈值注入、同档只提醒一次。
- 块 3：模拟 `source=compact` 的 SessionStart，验证 status 摘要被注入。
- 全局：`python scripts/validate-governance.py` 通过；hook 零依赖；受保护路径边界不变。

## 下一步

- 等 human 在批注区落笔（尤其"未解决问题 1/2/3"）。
- 批注收敛后：确认是否进入实现阶段、是否开 `feat/context-orchestration` 分支。

## Plan revision log

- 2026-07-11 初稿（诊断 + 三块方案 + 未决问题）
- 2026-07-11 并入 Codex 复核（硬约束：hook 只发信号不执行 compact；运行表面不等价 / Paseo injectIntoAgents=false；.codex 侧 hook 对等已确认）+ 过渡缓解句 + 未决问题 5
