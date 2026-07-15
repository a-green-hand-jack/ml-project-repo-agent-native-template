---
name: spawn
description: 当要唤起一个 subagent（in-session 跑完汇报，或起一个持久可交互的 Paseo 标签页 agent）时用；串起「发现有哪些 agent → 选型/packet → 人+主 agent 两层交代 → 出生即好名并入 roster」，替代凭直觉直接开 general-purpose worker。
---

# spawn —— 唤起 subagent（发现 + 选型 + 两层交代 + 命名）

把「派 subagent」从零散多步收敛成一条流程，并与 agent 身份 doctrine（`.agent/agent-identity.md`）打通：
子 agent **出生即有好名**（`persona·动作·focus`）、登记进花名册，而不是事后补 rename。

> keystone：launcher 是「易唤起」与「好命名」的交汇点——起 agent 时顺手 `--title` 好名 + 建 worktree +
> 选 profile + 入 roster，一次做对。

## 适用边界

- 适用：有一段可界定的子任务要交出去——搜索/实现/审查/监控/规划等。
- 不适用：scope 还没拆清（先 `interactive-plan-doc` 写 plan）；主 agent 顺手一步能做完；需要人类副作用（走 human gate）。

## 两种 spawn（先选一种）

| 模式 | 何时用 | 载体 | 命名 |
| --- | --- | --- | --- |
| **in-session 子 agent** | 一次性、跑完把结果汇报回主线程（如一轮 review、一次搜索） | `Task`/`Agent` 工具 | 主 agent 在交代里给它一个 doctrine 名（便于报告署名）；不占 Paseo 标签 |
| **Paseo-tab launcher（keystone）** | 需要**持久、可与 human 交互**的并行 agent（一个标签页一个 agent） | `paseo run` | **出生即命名**：`--title` + `--env AGENT_NAME=` 双表面命名 + 入 roster |

### Paseo 术语：Project / Workspace / Agent tab / Terminal tab / Worktree

选 Paseo-tab 模式前先分清这五个概念，避免"新 tab"和"新 worktree"混用：

- **Project**：Paseo sidebar 里登记的目录根，可以是 Git repo 或普通目录。
- **Workspace**：Project 下的持久工作上下文，记 cwd/agents/terminals/状态；同一份代码可以有多个 Workspace，不必开 worktree。
- **Agent tab**：一个 Workspace 里的一次 agent 会话 + 其 UI tab。**默认不创建**新 Project/Workspace/worktree。
- **Terminal tab**：一个 Workspace 里的终端，不是 agent。
- **Worktree**：Git 级独立目录 + 分支；Paseo 会为它关联一个 Workspace，用于需要文件/分支隔离的任务。

本 skill 的「Paseo-tab launcher」默认对应 **Agent tab**（`paseo run` 起一次会话），是否带 worktree 由下面
`--worktree`/`--cwd` 的选择决定，不等同于"新建 Workspace"或"新建 Project"。

### 已知限制：嵌套 sandbox 挡住 `paseo run`

`paseo run` 是 Paseo 的 Electron CLI，**不能在已经被 Claude Code / Codex 自身工具沙箱隔离的 shell 里初始化**
（无论调用方是 Claude 的 Bash 工具还是 Codex 的 `bwrap`），会在联系上 daemon 之前静默失败——不返回错误，
也不建出 agent，容易被误判成"daemon 没起"或"网络问题"。已实测确认：`paseo ls`/`paseo status`/`paseo
inspect`/`paseo send` 等只读/操作既有 agent 的命令不受影响，只有"创建"动作（`paseo run`）会被挡。

**后果**：主 agent 自己在 in-session Bash 工具里跑 `paseo run` 大概率起不来。遇到这种情况：
1. 不要反复重试同一条 `paseo run`（重试不会绕开沙箱限制）。
2. 退回「in-session 子 agent」模式（用 `Task`/`Agent` 工具），继续走本 skill 的两层交代 + 命名流程，只是不占 Paseo 标签。
3. 如果确实需要持久 Paseo tab（比如需要 human 后续在标签页里继续交互），把准备好的 `paseo run` 命令原样交给
   human，在他们的真实终端里跑；跑完后的 agent id 仍可以用 `agent_name_set.py --register` 登记进花名册，
   后续查状态/发消息（`paseo ls`/`paseo send`）本 agent 可以正常代劳。

## 流程

### 1. 发现（有哪些 agent 能派）
```
python3 .claude/skills/spawn/scripts/list_agents.py         # name / 一句话用途 / tools / model
```
据「一句话用途」挑最贴合的 canonical agent（`.claude/agents/*.md`）。不确定就先看这张表，别默认 general-purpose。

### 2. 选型 + packet
走 `subagent-routing` skill：按 `.agent/model-routing-policy.md` 定 tier，读 quota 证据，选 provider/model/effort、收紧 tools、写清 scope/forbidden/验收/停止条件，产出 launch packet（模板 `.agent/templates/launch-packet.md`）。**派发前先路由**。选 Paseo provider 时，若本机存在 `~/.paseo/orchestration-preferences.json`，先读它——这是 Paseo 官方按角色（impl/ui/research/planning/audit）定默认 provider 的入口，不要在有偏好文件时硬编码 `claude/opus`、`codex/gpt-5.4` 这类选择。

### 3. 两层交代（合成 launch prompt）
- **第一层 human brief**：human 启动本 skill 时给的意图（「去调查 X」「实现 Y」）。
- **第二层 main-agent brief**：主 agent 补齐 human 没说但子 agent 必需的——相关文件、scope、forbidden 路径、验收标准、回报格式、停止条件（多来自第 2 步 packet）。
- 两层拼成最终 launch prompt。保留人与主 agent 各自的意图注入，是本 skill 做成 skill（而非一键 command）的原因。

### 4. 命名（出生即好名）
据 `.agent/agent-identity.md` 的 `<persona·动作字·focus>`，按**子任务**选名：
- 调查→`斥候·查·<focus>`、实现→`干将·改·<focus>`、审查→`师爷·审·<focus>`、规划→`都督·统·<focus>`、
  文档→`主簿·记·<focus>`、测试→`巡检·测·<focus>`、实验→`博士·验·<focus>`、设计→`画师·设·<focus>`、git/整合→`校书·并·<focus>`。
- 唯一性靠 focus 区分；仍冲突加短 id。

### 5. 启动

**A. in-session 子 agent**：用 `Task`/`Agent` 工具，`subagent_type` = 第 1 步选的 agent，prompt = 第 3 步 launch prompt（开头点明「你是 `<第4步名>`，据此署名回报」）。跑完把摘要收回主线程，长报告落 `.claude/agent-reports/`。

**B. Paseo-tab launcher**：出生即双表面命名 + 入 roster。先受上面「已知限制」约束——本 agent 若跑在被沙箱
隔离的 shell 里，`paseo run` 大概率起不来，按那节的降级路径处理。
```bash
NAME="师爷·审·窗口感知"            # 第 4 步选的名
SLUG="review-window"              # worktree 短名（kebab）
# --detach：持久并行 agent 必须后台起，否则 paseo run 会阻塞主 agent（还会把流式输出灌进 json.load）
# --title 命名 Paseo 标签；--env AGENT_NAME 让子 agent 的 statusline/身份 hook 认得自己
# 新建独立 worktree 用 --worktree "$SLUG"；接进一个已经存在的 worktree/目录用 --cwd "<绝对路径>"
# （两者互斥——--worktree 会新建 worktree，不是把已有目录接进去；接错会平白多一份重复 worktree）
CHILD=$(paseo run --json --detach \
  --title "$NAME" \
  --env "AGENT_NAME=$NAME" \
  --worktree "$SLUG" \
  --provider claude \
  "<第3步的最终 launch prompt>" \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("id") or d.get("agent",{}).get("id","")) if isinstance(d,dict) else print("")')
# 若 $CHILD 为空说明没取到 id（run --json 形状异常/未起成功）——先排查，别拿空 id 登记
if [ -z "$CHILD" ]; then echo "paseo run 未返回 agent id，检查 daemon/输出"; fi
# 把子 agent 登记进花名册（子 agent 已出生即命名，故只登记、不 rename）
python3 .claude/hooks/agent_name_set.py "$NAME" --register --paseo-id "$CHILD" --worktree "$SLUG"
```
- `--detach` 让 `paseo run` 立即返回子 agent 元数据（含 `id`）而不阻塞；id 提取对
  `{"id":…}` 与 `{"agent":{"id":…}}` 两种形状都稳。
- `--env AGENT_NAME=` 让子 agent 的 `agent_identity.py` 立刻解析到名字 → statusline 显示 `🤖 <name>`、
  身份 hook 认为「已命名」而**不再**注入自命名指令（与 Phase 2 一致）。
- 需要主 agent 等子 agent 跑完可用 `--wait-timeout <dur>`（那属于「同步子任务」，多数场景用 in-session 模式更合适）。
- runtime-agnostic：非 Paseo 表面就只用 in-session 模式；命名仍靠 `AGENT_NAME`/`.agent-identity`。
- **relationship（组织关系，非 Workspace）**：当前对话派生的任务默认按 `subagent` 关系处理（属于本次任务，
  方便监督/汇总）；只有明确要把任务整个交接出去、不再归本次对话管，才用 `detached`（对应 handoff 场景）。

### 6. 收尾
- agent↔agent 通信：用花名册（`memory/agents-roster.md`）把 name 解析成 paseo-id，再 `paseo send <id> "<消息>"`（`send` 认 id 不认 name）。
- 子 agent 结束/归档：在 roster 该行标 done（不立即删，留痕），并
  `python scripts/agent-state.py set-status "<name>" done`（控制面状态同步终态）。

## 查询已在跑的 agent（list/status，issue #14 控制面）

起新 agent 前先看现有的（human 拍板：查询能力并入本 skill，不独立成新 skill）：

```
python scripts/agent-status.py            # 谁在跑 / 做什么 / active|idle|blocked|done|stale / 心跳 / 未读数
python scripts/agent-status.py --json     # 机器可读
python scripts/check-agent-conflicts.py scan   # 活跃 agent owned_paths 有无重叠（并行前必查）
```

- 数据源：roster（本 skill 维护的总览）+ `memory/agents/<name>.yaml` 状态明细；有 `paseo` CLI 时
  自动叠加 `paseo ls --json` 校验「登记的 paseo-id 是否还活着」，缺 Paseo 降级纯 repo 视图。
- 30 分钟无心跳 → `stale`（该 agent 的 owned_paths 声明不再被冲突检测强制）。
- 与控制面的挂接（schema/协议见 `.agent/multi-agent-control-plane.md`）：`agent_name_set.py`
  自命名/`--register` 时已自动初始化 `memory/agents/<name>.yaml` + mailbox；派发方在 launch packet
  里让子 agent 开工先 `python scripts/agent-state.py register "<name>" --task ... --owned ... --forbidden ...`
  声明边界，session boundary 跑 `agent-state.py heartbeat`；关键消息/交接走
  `python scripts/agent-mailbox.py send/handoff/ack`（`paseo send` 只做实时提醒，mailbox 落盘才是真相层）。

## 允许修改的路径

- `memory/agents-roster.md`（登记/更新活 agent 行——经 `agent_name_set.py` 维护）。
- `memory/branches/<slug>.md`（第 2 步 launch packet 引用）。
- 派发现场 issue/PR 文本、新建的 worktree。其余只读。

## 验证命令

```
python3 .claude/skills/spawn/scripts/list_agents.py           # 发现表能列全 16 个 agent
python3 .claude/hooks/agent_name_set.py "斥候·查·smoke" --register --paseo-id demo-id --worktree "b (wt)"
grep "demo-id" memory/agents-roster.md                        # 确认已登记该行
python scripts/validate-governance.py
```

## 失败时的 handoff

- 选不定 agent / tier 边界模糊：回 `subagent-routing` 的 handoff（升级人类定预算）。
- scope 无法界定：停止派发，转 `interactive-plan-doc` 先收敛。
- `paseo run` 不可用（非 Paseo 表面、daemon 未起、或跑在被沙箱隔离的 shell 里）：退回 in-session 模式，
  命名仍生效；需要持久 Paseo tab 时把命令交给 human 在真实终端里跑（见「已知限制」节）。
