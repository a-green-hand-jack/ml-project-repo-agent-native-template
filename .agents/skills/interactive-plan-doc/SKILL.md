---
name: interactive-plan-doc
description: 当一个阶段需要在动手前与人类对齐 scope 时，用来写中文 plan doc、收人类批注、收敛并做 plan revision commit（human gate）。
---

> Codex adapter: generated from `.claude/skills/interactive-plan-doc/SKILL.md`. Do not edit this copy by hand; run `python scripts/sync-codex-adapters.py`.

# interactive-plan-doc

把一个阶段的意图写成中文 plan doc，让人类批注，读 diff 收敛，直到 scope/forbidden/verification 清楚后才允许开始实现。

## 适用边界

适用：阶段启动、需要与人类对齐目标与边界、任务足够大值得先规划时。
不适用：微小机械改动；scope 已在既有 plan doc 中锁定且未变。

## 输入 / 输出 artifact

- 输入：阶段目标、上游指令、相关 anatomy/ledger。
- 输出：`plans/<YYYYMMDD>-<slug>.zh.md`（模板见 `.agent/templates/plan-doc.zh.md`，顶部带
  `Status:` 状态锚点）+ `memory/doc-lifecycle.yaml` 注册表条目（状态语义见 `plans/ANATOMY.md`）。

## 需要读取的 ledger

- `.agent/human-gates.md`（plan revision 的审批点）。
- `.agent/repo-editing-guardrails.md`（改 repo 的门禁流程）。
- `memory/doc-lifecycle.yaml`（同 topic 是否已有 plan、是否需要 supersede 旧版）。
- 相关 `ANATOMY.md` 与 index YAML（了解现状）。

## 允许修改的路径

- `plans/<YYYYMMDD>-<slug>.zh.md`
- `memory/doc-lifecycle.yaml`（登记/更新本 plan 的条目）
- 其余一律只读，直到 plan 通过 human gate。

## 步骤

1. 起草：用 `.agent/templates/plan-doc.zh.md` 写出目标、scope、forbidden、验收/verification、风险；
   顶部写 `Status: draft · <date> · <ref>`，并在 `memory/doc-lifecycle.yaml` 登记（kind/path/status/关联引用）。
2. 交人类批注：明确请求 review，不要抢跑实现；进入批注期可把状态转 `in-review`（锚点+注册表同步）。
3. 读 diff：把人类批注逐条读进来，识别被改动的意图（可选前缀约定：`[OK]` 采纳 / `[改]` 要求修改 / `[?]` 未决）。
4. 收敛：更新 plan，直到 scope / forbidden / verification 三者都明确无歧义。批注区仍有 `[改]`/`[?]`
   或互相冲突的批注时**不得**标 `approved`——升级为未解决问题，等 human 落笔，不自动选边。
5. human 明确批准后：状态转 `approved`（锚点+注册表同步），注册表回填 `approval` 证据引用；
   plan revision commit 前跑 `python scripts/check-doc-lifecycle.py`（hook 也会在编辑动作阶段拦完整性不成立的跃迁）。
6. 只有 `approved` 后，才移交实现（转 worktree-pr-flow / experiment-workflow）。
7. 同 topic 出新版 plan：旧 plan 锚点标 `superseded`（不删除、不移动），注册表 `superseded_by`
   指向新条目——引用旧 plan 的下游 approval 随之过期。

## 验证命令

```
python scripts/check-doc-lifecycle.py
python scripts/validate-governance.py
```

## 失败时的 handoff

- 人类批注相互冲突或 scope 无法收敛：记录未决项，按 `.agent/templates/handoff.md` 升级给人类澄清。
- 若在未通过 human gate 前已被要求实现：拒绝，回到步骤 2。
