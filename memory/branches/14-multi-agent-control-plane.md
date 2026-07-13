# Branch Status: 14-multi-agent-control-plane

## Purpose
issue #14：repo-native、runtime-neutral 的多 agent 状态/通信/handoff 控制面第一版
（Paseo-first，坐在 spawn skill 之上；plan：`plans/20260712-multi-agent-control-plane.zh.md`，
human 已逐条拍板、零 open question）。

## Parent session
监控员编排 → worker「干将·改·控制面」（in-session subagent，本 worktree 内实现）。

## Branch / base
`feat/14-multi-agent-control-plane` / base：main（v1.3.0，含 spawn skill + agent-identity）。

## Worktree
`.claude/worktrees/14-multi-agent-control-plane`

## Linked issue / PR
issue #14；PR 待 human gate（不由 worker 开）。

## Owned paths
`.agent/multi-agent-control-plane.md`、`scripts/agent-{state,status,mailbox}.py`、
`scripts/check-agent-conflicts.py`、`.claude/hooks/pre_tool_guard.py`（增量接线）、
`.claude/hooks/agent_name_set.py`（roster state 列 + 状态初始化）、`.claude/skills/spawn/SKILL.md`
（新增 list/status 节）、`memory/agents|mailbox/README.md`、相关 ANATOMY/DESIGN/模板/清单。

## Forbidden paths
lab bytes 红线、其他 worktree、生成物手改（`.agents/skills/**` 走生成器）、不 push/PR/merge。

## Anatomy impact
scripts/ANATOMY（+4 脚本 + importlib 连接）、memory/ANATOMY（agents/ mailbox/ roster 行）、
.claude/ANATOMY（pre_tool_guard 行）、DESIGN §10（validators 13、doctrine 22、hooks 描述）。

## Claim / evidence impact
无实验 claim。变更登记：`memory/change-control.yaml` `chg-20260713-multi-agent-control-plane`。

## Plan doc
`plans/20260712-multi-agent-control-plane.zh.md`（任务树勾选留给监控员随 PR 收口）。

## Current state
实现完成：schema doctrine + 四脚本（自带 --self-test）+ hook 薄接线（仿 #13
check-doc-lifecycle 的 importlib 模式）+ spawn skill 查询节 + agent_name_set 挂接 +
gitignore 运行时规则 + Codex adapters 已再生成。

## Commands run
- `python3 scripts/agent-state.py --self-test`（17 ok）
- `python3 scripts/agent-status.py --self-test`（10 ok）
- `python3 scripts/agent-mailbox.py --self-test`（17 ok）
- `python3 scripts/check-agent-conflicts.py --self-test`（16 ok）
- synthetic JSON 回归（旧地板 13 用例零回归：sudo/rm/push-main/pip/curl|sh/.env/
  lab 写入/benign 全对），hook e2e：conflict deny（Edit + apply_patch 两形状）、own-path
  allow、AGENT_CONFLICT_SKIP=1 放行、wrong-worktree deny（exit 2）
- repo-native 双 agent smoke（/tmp git repo + linked worktree）：共享锚定→互相发现→mailbox→
  handoff ack ownership 转移→冲突 scan exit 1→写错-worktree exit 1→fresh 进程恢复归属+未读
- `python3 scripts/validate-governance.py --strict` 等（见最新 commit 信息）

## Latest result
全部通过（详见 worker 报告）。

## Open risks
- 真实 Paseo-tab 双 agent smoke（plan 3.3 主路径）与真实 Codex 表面 smoke（plan 6.4c）
  **未跑**：worker 是 in-session subagent，受 spawn skill 已记录的嵌套沙箱限制
  （`paseo run` 在工具沙箱 shell 里静默失败）。留给监控员/human 在非沙箱环境执行，
  fixture smoke 只是兜底证据，不冒充完成。
- 与 #13 分支在 `pre_tool_guard.py` 同位置各自插入薄接线，merge 到 main 时有一次
  可预期的 trivial 冲突（两段 `reason = ..._reason(...)` 需并存），交监控员处理。
- `.gitignore` 新增 memory/agents|mailbox 运行时忽略规则：plan Allowed paths 未列
  `.gitignore`，但沿用 `memory/agents-roster.md` gitignored 先例（同一决策块的
  「运行时内容不入 git」语义），已在 worker 报告标注为轻微越界项待确认。

## Exit condition
监控员确认：真实 Paseo/Codex smoke 补跑或明确记为 open item → human gate 开 PR。
