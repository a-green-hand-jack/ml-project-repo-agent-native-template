---
related_files:
  - ../memory/doc-lifecycle.yaml
  - ../scripts/check-doc-lifecycle.py
  - ../.claude/hooks/pre_tool_guard.py
  - ../.agent/templates/plan-doc.zh.md
  - ../.agent/human-gates.md
  - 20260712-plan-lifecycle-state.zh.md
maintenance: |
  状态枚举 / 锚点格式 / 注册表 schema 变化时同 commit 更新本文件与
  scripts/check-doc-lifecycle.py。plans/ 下新增/取代 plan doc 时同步 memory/doc-lifecycle.yaml。
---

# plans/ ANATOMY

## What this is

交互式中文 plan doc 的家 + **四类文档（brief/plan/review/decision）统一生命周期状态**的
schema 权威说明（issue #13，`plans/20260712-plan-lifecycle-state.zh.md` human 已拍板）。
brief/review/decision 本体在 `human/`，但状态语义与注册表 schema 以本文件为准。

## 状态模型（四类统一）

```
draft → in-review → approved → implementing → verified
                        └────────────┴──── superseded（终态，任何态可入）
```

- `draft → in-review → approved` 由 **human 批注驱动**（approved 是 human gate）。
- `approved → implementing → verified` 由 **agent 据证据自主标记**（有无对应 commit/测试），
  human 审 PR 时复核。
- 同 topic 出新版：旧文档标 `superseded`（不删除、不移动），注册表 `superseded_by` 指向新条目；
  引用它的下游 approved/implementing 随之判为**过期 approval**（唯一过期触发，无时间窗口）。
- 允许某类不经过某些态（如 decision 通常止于 approved）。

## 状态载体（两层，runtime-neutral，Claude/Codex 完全等价）

1. **状态锚点**：标题后的第一条非空正文必须是一行纯文本
   `Status: <enum> · <date> · <ref>`，全文只能有一条；代码围栏、blockquoted 与四空格缩进
   代码块中的示例不算锚点——两个 runtime 都用同一 parser 读文件，不依赖 runtime 专属注入。
2. **注册表** `memory/doc-lifecycle.yaml`：机器可解析的关联/证据（id/path/kind/status/
   issue/branch/worktree/approval/upstream/downstream/superseded_by），由 agent 维护。
   字段语义与格式约定见该文件头部注释。

## 强制层（只判可判定事实，不替 human 做主观判断）

| 层 | 位置 | 拦什么 |
| --- | --- | --- |
| 机械拦截 | `.claude/hooks/pre_tool_guard.py` → `check-doc-lifecycle.py:pretooluse_reason` | 写入使文档进入 approved/implementing 但 scope/forbidden/verification 缺失、批注区残留 `[?]`/`[改]`、上游已 superseded、注册表引用悬空/kind 与路径类别不符（谎报 kind）；活跃 plan 的 issue/branch/worktree 关联不成立；删除/移走/覆盖注册表（含 `command`/`env` wrapper、git 全局选项、`cp`/`dd`/`tee`）；apply_patch Update 尊重 `@@ <anchor>` 重建 patch 后全文，anchor/上下文不能唯一定位时保守拦截（提示改用 Edit） |
| 事后校验 | `scripts/check-doc-lifecycle.py`（`validate-governance.py` 拉起） | 上述全部 + 锚点/注册表一致 + 四类文档必须登记 + 存在受管文档但注册表缺失 = error（非 strict 也 fail） |

human 显式绕过 hook：`DOC_LIFECYCLE_SKIP=1`（validator 仍会事后校验）。
批注收敛辅助只是格式约定：`[OK]` / `[改]` / `[?]` 可选前缀 + 模式匹配，不做语义分类。
活跃 plan 的 issue 远端存在性不触发网络请求：validator 要求非占位规范 `#N`/GitHub issue URL；
branch 与 implementing worktree 则分别按本地 Git ref、`git worktree list` 真实核验。`worktree: .`
优先绑定本地 branch checkout；独立 exact-review/CI clone 没有本地 branch 时，可用唯一同名 remote
ref 绑定当前 detached exact tip，或以该 tip 为直接父提交的双亲 synthetic merge。普通线性后继与
同名 remote refs 指向不同 commit 都 fail-closed；显式 worktree 路径仍必须精确匹配本地 branch。
verified 是历史态，允许合并后清理临时 branch/worktree，历史事实由 approval 中的 commit/PR/test
引用承担。

## fresh session 状态感知（a+b 叠加）

- (a) 入口纪律：`CLAUDE.md`/`AGENTS.md` 要求 session 开始读 `memory/current-status.md`
  的当前 plan 指针 + 本注册表。
- (b) 机械回注：`context_continuity.py` 在 compact/clear 后回注 `memory/current-status.md`
  （含指针）。已评估**不**扩展到 startup 注入：入口纪律已确定性覆盖 fresh startup，
  每 session 固定注入与 context-orchestration 的边界注入原则冲突（见 plan doc revision log）。

## Notes

- 命名 `<YYYYMMDD>-<topic>.zh.md`；模板 `.agent/templates/plan-doc.zh.md`；流程接线见
  `.claude/skills/interactive-plan-doc/SKILL.md` 与 `.claude/skills/worktree-pr-flow/SKILL.md`。
- 与 `memory/change-control.yaml`（变更登记）、`human/decisions/`（ADR 正文）互补不重复：
  lifecycle 状态只在本注册表；ADR 的 accepted ↔ lifecycle 的 approved。
