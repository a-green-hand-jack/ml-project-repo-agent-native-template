---
name: worktree-pr-flow
description: 当要落地一处代码改动时，用来走 issue→branch→worktree→实现→更新anatomy/ledger→测试+validator→PR→review→merge→归档的标准流程；push/PR/merge 走 human gate。
---

# worktree-pr-flow

把一次改动放进受控流程：从 issue 到归档，每一步留证据。默认在 fresh worktree 里实现，隔离工作区。push/PR/merge 是外部副作用，走 human gate。

## 适用边界

适用：任何需要进入版本历史的代码/结构改动。
不适用：纯本地探索、尚未通过 plan 的 scope（先走 interactive-plan-doc）。

## 输入 / 输出 artifact

- 输入：已锁定 scope 的 plan doc / issue。
- 输出：feature branch、fresh worktree、更新的 anatomy/ledger、PR（含 evidence + risks）、归档记录。

## 需要读取的 ledger

- `.agent/repo-editing-guardrails.md`（门禁流程）。
- `.agent/human-gates.md`（push/PR/merge 审批）。
- `.agent/anatomy-protocol.md`（同 commit 更新地图）。
- `memory/doc-lifecycle.yaml`（linked plan doc 的生命周期状态，语义见 `plans/ANATOMY.md`）。

## 允许修改的路径

- worktree 内的目标源码
- 受影响的 `ANATOMY.md` / index / ledger
- push/PR/merge 前不越过 human gate。

## 步骤

1. issue：先有一个可追溯的 issue/plan。linked plan doc 的状态必须 **≥ approved**
   （查 `memory/doc-lifecycle.yaml` 与文档 `Status:` 锚点）；未 approved 先回 interactive-plan-doc。
   开始实现时 **agent 自主**把状态转 `implementing`（锚点+注册表同 commit 对齐）。
2. branch on correct base：按模式选 base——
   - 单 trunk（pairwise-diffusion 式）：`git worktree add ../wt-<slug> -b <slug> <trunk>`。
   - branch-local mainline（DOLoop 式）：base 为 `mainline/<domain>`，如 `git worktree add ../wt-<slug> -b <domain>/<slug> mainline/<domain>`。
   记录 exact base（见下方「变更自检清单」第 3 块）。
3. fresh worktree：在隔离 worktree 内实现，避免污染主工作区。cwd 不保证跨 Bash 调用稳定持久，每次写操作前先跑 `pwd` + `git rev-parse --show-toplevel` 核对确实在分配的 worktree 里，不要只在任务开头 `cd` 一次就假设之后都对。
4. 实现前先过一遍「变更自检清单」第 1、2 块（分类矩阵 + 三项前置声明），实现 + 同 commit 更新
   anatomy/ledger（见 anatomy-drift-control）。
5. 定向测试 + validator：按「变更自检清单」第 4 块的验证纪律执行。
6. commit/push/开 PR 等有副作用动作前，重新过一遍第 3 块（live base 双检 + 路径自报自查）与第 5 块
   （授权分级）；PR 正文开头带上三项前置声明，写清 evidence（跑了什么、结果）与 risks；**human gate**。
7. review → merge（human gate）→ 归档：更新索引，清理 worktree（`git worktree remove ../wt-<slug>`）。
   merge 后据验证证据（测试/validator/PR 合入）**agent 自主**把 plan doc 状态转 `verified`；
   human 审 PR 时复核这些状态流转（`approved` 本身始终是 human gate）。

## 变更自检清单（G1 流程门）

本清单是 `worktree-pr-flow` 与 `pr-review`（`.claude/commands/pr-review.md`）共用的唯一正文
owner；`pr-review` 只链接到这里，不复制。来源：issue #48，对照
`.reference-docs/LingTai_ANATOMY_CONTRACT_Project_Governance_Guide_zh.md`（下称指南 A）§7/§10 与
`.reference-docs/LingTai_Code_Drift_Bloat_Control_Guide_zh.md`（下称指南 B）§4.1/§3/§12.1、附录 A
改写而成——按本 repo 实际载体名裁剪，不逐字照搬。

### 1. 变更分类矩阵

先判断这次改动属于哪一类，再决定该同 commit 更新哪个载体（可能不止一类）：

| 变更类型 | 判断问题 | 落点 |
| --- | --- | --- |
| 改结构 | 有没有改变「东西在哪」「谁负责」（文件/目录移动、职责划分、组件增删）？ | 对应目录 `ANATOMY.md` 同 commit 更新（见 `anatomy-drift-control`） |
| 改承诺 | 有没有改变别人可以依赖的行为（对外可观察语义、边界、SLA、错误语义）？ | 对应 `.agent/*.md` policy 正文同 commit 更新，并补一条可核验证据指针（validator/测试/命令输出）；写不出证据先标 unverified，不写空承诺 |
| 改操作 | 只是步骤/命令变了，行为和边界没变？ | 对应 `.claude/skills/*/SKILL.md` 或 `.claude/commands/*.md` 正文更新 |
| 改决策 | 这次选择以后可能被回头问「当初为什么这样选」？ | 记一条 `DECISIONS.md` |

同一条规则永远只有一个正文 owner——发现要复制已有正文，先改成链接。

### 2. 三项前置声明

动手前想清楚，写进 branch status（`memory/branches/<slug>.md`）或 PR 描述开头：

| 声明 | 要回答的问题 |
| --- | --- |
| Invariant | 哪些行为、顺序或安全属性必须保持不变？ |
| Variation axis | 本次允许改变的唯一维度是什么？ |
| Non-goals | 本次明确不解决什么？ |

这是 #13「初审后被追加防御性扩展」的真实教训：没写清 Non-goals，scope 会在实现过程中悄悄膨胀。

### 3. exact-base 双检 + 路径自报自查

- **开始时**：记录 base SHA（`git rev-parse HEAD`）、worktree 是否 clean、HEAD 是否等于声明的
  base；不等于要显式说明差异（例如本地 base 领先 origin，且已确认改动路径无重叠）。
- **commit / push / 开 PR 等有副作用动作前**：重新核对 live base 是否移动。移动了就检查新增 diff
  是否与本次改动路径重叠——重叠则重放/复核受影响部分，不重叠可继续但要记下复核结论。
- **预期改动路径自报自查**：动手前列出预期会碰的文件/路径；改完后对照最终 `git diff --stat`，
  核对「没有多余路径，也没有漏掉预期路径」，如实报告差异。**这是 G1 自查声明，不是机械门**——
  #32/#43/#44 两轮试图把 exact path scope 做成自动化硬门都被证伪（agent 自报路径集合与实际需要
  对不齐、或机械比对产生大量误报、拖慢真正需要扩围的合法改动），因此退回为「自己写、自己对照、
  如实报告差异」的流程性自检，**不新增 validator 强制比对**。

### 4. 验证纪律

- 只跑与改动相关的定向测试，不跑无关的全量 suite。
- 超时、被中断、或未完整跑完的 suite **不得报告为「通过」**——如实说「未完成」，不得靠推断补全。
- 优先跑 `python scripts/validate-governance.py`；改了 `.claude/` 下的 agent/skill/command/hook 先跑
  `python scripts/sync-codex-adapters.py`。
- 报告时给确切命令与输出，不给无 run id / commit / 输出摘要的结论。

### 5. 副作用授权分级

涉及 commit/push/PR/merge/依赖变更/有损 git 操作等有副作用的动作前，对照
`.agent/action-boundary.md` 的三档（禁止 / 需问 / 可做）判断这次动作属于哪一档——本清单不复制其
内容，`.agent/action-boundary.md` 是唯一权威源。

## 验证命令

```
python scripts/validate-governance.py
python scripts/check-anatomy-drift.py
python scripts/check-doc-lifecycle.py
```

## 失败时的 handoff

- 测试/validator 红：不 push，在 branch 修；无法定位则按 `.agent/templates/handoff.md` 升级。
- base 选择存疑（哪种 mainline 模式）：停下问人类，不擅自选 base。
