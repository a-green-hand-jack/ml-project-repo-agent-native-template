---
name: subagent-routing
description: 当要为一个 child task 派 subagent 时，用来选定 model/effort/tools 并产出 launch packet；不要凭直觉直接开 general-purpose worker。
---

> Codex adapter: generated from `.claude/skills/subagent-routing/SKILL.md`. Do not edit this copy by hand; run `python scripts/sync-codex-adapters.py`.

# subagent-routing

为一个待派发的 child task 挑选 model、reasoning effort、允许的 tools，并落成一份 launch packet。核心原则：**派发前先路由**，不直接甩一个广义 general-purpose worker 上去。

## 适用边界

适用：需要把一段可界定的子任务交给 subagent（搜索、实现、review、监控等）时。
不适用：任务尚未拆清 scope（先去写 plan doc）；只是主 agent 顺手能做的一步；需要人类副作用（走 human gate）。

## 输入 / 输出 artifact

- 输入：child task 的目标、scope、forbidden、验收标准（来自 plan doc 或上游指令）。
- 输出：一份 launch packet，落在 launch 现场（issue/PR 描述或 `memory/branches/<slug>.md` 内引用），模板见 `.agent/templates/launch-packet.md`。

## 需要读取的 ledger

- `.agent/model-routing-policy.md`（tier 0-4 的 model/effort/tool 预算）。
- `.agent/tool-skill-interface.md`（何时 shell / skill / subagent / MCP）。
- 当前 `memory/session-tree.md`（避免与已在跑的分支冲突）。

## 允许修改的路径

- `memory/branches/<slug>.md`（写入本次 launch packet 引用）。
- 派发现场的 issue/PR 文本。
- 其余一律只读。

## 步骤

1. 归类 tier：按 model-routing-policy 的 tier 0-4 判定任务难度与风险（0=最轻只读检索，4=高风险高推理）。
2. 选 model + effort：按该 tier 的预算取默认值；越高 tier 才允许越贵的 model / 更高 effort。
3. 收紧 tools：只授予完成该 task 必需的工具；只读任务不给 Edit/Write。
4. 明确 scope 与 forbidden：写清允许写路径、禁止触碰的文件、验收标准与回报格式。
5. 用 `.agent/templates/launch-packet.md` 填出 launch packet；确认没有隐含的 general-purpose 兜底授权。
6. 派发，并在 `memory/branches/<slug>.md` 记一行引用。

## 验证命令

```
python scripts/validate-governance.py
python scripts/check-anatomy-drift.py
```

## 失败时的 handoff

- 路由不确定（tier 边界模糊 / 需要更高预算）：写入 `.agent/templates/handoff.md` 的 handoff note，升级给人类决定预算。
- 若 child task scope 无法界定，停止派发，转 interactive-plan-doc 先收敛 scope。
