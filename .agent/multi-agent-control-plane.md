# multi-agent-control-plane —— 多 agent 状态/通信/handoff 控制面

> issue #14（plan：`plans/20260712-multi-agent-control-plane.zh.md`，human 已逐条拍板）。
> repo-native、runtime-neutral、可持久化、可恢复的多 agent 协作控制面（第一版最小可用）。
> 接口一律是「跑 `python scripts/...` + repo 文件读写」，Claude 与 Codex 等价调用，
> 不走任一 runtime 的 Task/subagent 机制。

## 与既有机制的分工（不重造轮子）

- **spawn skill**（`.claude/skills/spawn/SKILL.md`，Paseo-first 地基）：起 agent（`paseo run
  --json --detach`）、出生即命名、roster 登记、`paseo send <id>` 通信原语。
- **本控制面（#14 增量）**：其上的 list/status 查询、结构化 mailbox、ownership handoff、
  heartbeat/stale 检测、写入前冲突/写错-worktree 拦截。
- identity/命名见 `.agent/agent-identity.md`；session handoff 模板见 `.agent/templates/handoff.md`。

## 状态锚定（重要）

控制面状态默认落在**主 checkout**（linked worktree 的 `.git` 文件指回主仓库；解析逻辑
`scripts/agent-state.py:control_plane_root`）：所有 worktree 里的 agent 共享同一份
`memory/agents/` + `memory/mailbox/`，否则互相发现与冲突检测失效。显式覆盖：`--root` 或
`AGENT_CONTROL_PLANE_ROOT` env（测试/特殊布局用）。内容是**运行时状态**（gitignored，
同 `memory/agents-roster.md` 先例）：格式/机制随 template 继承，谁在跑不入 git、不跨 project。

## Agent state（`memory/agents/<name>.yaml`，每 agent 一份——human 拍板）

由 `scripts/agent-state.py` 维护（该脚本是格式唯一 owner，其余脚本 importlib 复用其解析）：

| 字段 | 含义 |
| --- | --- |
| `name` / `task` | agent 名（`.agent/agent-identity.md` 格式）+ 一句话任务 |
| `status` | 存储态：`active` / `idle` / `blocked` / `done`（终态） |
| `heartbeat` / `ttl_minutes` | UTC ISO 心跳 + TTL（默认 30）。**超 TTL 派生为 `stale`**（不落盘） |
| `worktree` / `branch` | 该 agent 的 worktree 绝对路径 + 分支（写错-worktree 检测用） |
| `owned_paths` / `forbidden_paths` | repo-relative 声明；目录尾随内容前缀匹配，冲突检测消费 |
| `paseo_id` | Paseo 表面才有；`paseo send` / presence 校验用 |
| `inbox_ref` / `outbox_ref` | 指向 mailbox 一对文件 |

`memory/agents-roster.md`（spawn skill 维护）保持「花名册总览」：name↔paseo-id↔worktree 索引，
尾列 `state` 指向对应 yaml——roster 管「有哪些 agent、怎么连上」，yaml 管状态明细，不重复字段。
**heartbeat 触发时机**：session boundary（开始/checkpoint/结束）跑
`python scripts/agent-state.py heartbeat "<name>"`；自命名/登记（`agent_name_set.py`）自动初始化。

## Mailbox（`memory/mailbox/<name>/inbox.md` + `outbox.md`——human 拍板）

`scripts/agent-mailbox.py` 维护；发送 = 写自己 outbox + 追加对方 inbox（inbox 副本是
read/state 权威副本）。消息块字段：`id`/`kind`/`from`/`to`/`time`/`read`/`state`/`ref`/`summary`。
`kind`：`info` / `question` / `decision` / `handoff` / `ack`。

- **回写规则**：`decision`/`handoff` 是关键消息，**必须**带 `ref` 指向真实存在的 repo 落盘文件
  （handoff 文档、branch status、plan、decision），脚本强制、拒绝只留临时消息。
- **与 Paseo 的分工**：mailbox 是可恢复的结构化真相层；`paseo send <id>` 只做低延迟送达提醒
  （发送时自动尝试，缺 Paseo/无 paseo_id 优雅降级、不 raise）。

## Ownership handoff（区别于同 agent 跨 session 的 handoff）

1. 发起方先写 handoff 文档（`memory/handoffs/<date>-<slug>.md`，模板见
   `.agent/templates/handoff.md` 的 agent-to-agent 变体）；
2. `python scripts/agent-mailbox.py handoff --from A --to B --task "..." --ref <文档> [--paths P ...]`
   → B 的 inbox 出现 `state: pending`；
3. 接收方 `python scripts/agent-mailbox.py ack B --id <msgid>` → `pending→accepted`、
   `--paths` 从 A 的 owned_paths 转移进 B、B 的 task 更新、A 收到 `ack` 回执。
   未 ack 之前 ownership 不转移，冲突检测仍按原声明强制。

## 只读 list/status

```
python scripts/agent-status.py [--json] [--no-paseo]   # 谁在跑/做什么/状态/心跳/未读数
python scripts/check-agent-conflicts.py scan           # 活跃 agent owned_paths 两两重叠扫描
python scripts/check-agent-conflicts.py worktree       # declared worktree vs 实际 toplevel
```

`agent-status.py` 读 roster + `memory/agents/*.yaml`，可选叠加 `paseo ls --json` 做
「登记的 paseo-id 是否还活着」的实时校验（缺 Paseo 降级纯 repo 视图）。查询无写副作用。

## 冲突检测（写入前 hook 层——human 拍板：折进 `pre_tool_guard.py`，本轮只做这一层）

判定本体在 `scripts/check-agent-conflicts.py:pretooluse_reason`，由两侧共享的
`.claude/hooks/pre_tool_guard.py` 薄接线调用（`.claude/settings.json` 与 `.codex/config.toml`
已共同挂载，一处改两侧生效）。覆盖 Claude `Edit`/`Write`/`NotebookEdit` 与 Codex
`apply_patch`（patch 头提取）。拦三类可判定事实：

1. 写入**其他活跃 agent**（active/idle/blocked 且心跳未超 TTL）声明的 owned path；
2. 写入**自己声明的** forbidden path；
3. declared worktree 与实际写入 checkout 不符（写错 worktree，机器检查、不靠 prompt 自检）。

保守边界：判定层异常、当前身份未知（无 `AGENT_NAME`/`.agent-identity`）、路径在 repo 外、
无任何状态文件 → 放行（不误伤未纳管 session）；stale/done 的声明不强制（防陈旧 agent 卡路）。
显式绕过：`AGENT_CONFLICT_SKIP=1`（先与对方 agent/监控员协调）。merge/PR 前的 validator
第二层**明确推迟**，待写入前 hook 被验证有效后再评估（human 拍板，不在本轮）。

## 已知限制 / runtime 不对等

- repo 是 eventually-consistent 真相层：控制面锚定主 checkout 解决了 worktree 间发现，但
  **owned_paths 是 repo-relative 语义**——两个 worktree 各改各的物理文件、merge 才相撞，本层
  给的是 merge 前预警信号，不是互斥锁（非目标：不做分布式锁/merge queue）。
- statusline `🤖 <name>` 只是 Claude 表面的派生便利视图（Codex 无 statusLine）；presence 的
  runtime-neutral 真相源是 roster + `memory/agents/*.yaml` + `agent-status.py`，statusline
  不参与 ownership/staleness/lease 判定。
- `PASEO_AGENT_ID` 只在 Paseo 启动路径存在：所有 Paseo 调用缺 env/CLI 一律 fallback、不 raise。
- 未来工作（非本版）：若要支持其它 runtime（如 LingTai），再评估把 `paseo run/ls/send` 这些
  原语抽象成统一 runtime adapter contract。
