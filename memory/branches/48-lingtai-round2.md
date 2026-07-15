# Branch Status: 48-lingtai-round2

## Purpose

issue #48 v4：任务 A = S2（变更自检清单，挂进 `worktree-pr-flow` / `pr-review`）；任务 B = S3
（ANATOMY↔CONTRACT 配对）**只写 plan doc**，不实现。

## Parent session

都督·统·治理路线（主 agent，Paseo id `c0675fdd-f8d8-44fb-81df-cc21031a1b5d`）

## Branch / base

- 实际分支名：`feat/48-checklist-contract`（worktree 落位时已预置此名，与授权指令中写的
  `feat/48-lingtai-round2` 不一致；working tree clean、单一 commit 与 origin/main 一致，判断为
  launcher 命名差异，非他人未提交工作冲突；不重命名——本地 ref rename 属额外无必要风险）。
- base：`main` @ `327e76aa6aaf1f822ee9e588cd799589c66509e0`（当时 == `origin/main`）。
- **exact-base 双检（开始时）**：本地主 worktree（`/home/user/Projects/ml-project-repo-agent-native-template`）
  的 `main` 已推进到 `072af38`（领先本分支 base 7 commit，未 push）。diff 范围：
  `.agents/skills/spawn/SKILL.md`、`.claude/skills/spawn/SKILL.md`、
  `memory/branches/18-anatomy-semantic-parity.md`、`memory/current-status.md`。与本任务计划改动路径
  （`worktree-pr-flow`/`pr-review`/`plans/`/`memory/doc-lifecycle.yaml`/本文件）**无重叠**，故不
  rebase（`git rebase` 属 action-boundary「需问」动作，且无必要）；commit/push 前将重新核对 live
  base 是否进一步移动（G1 双检，S2 正文即以此为例）。

## Worktree

`/home/user/.paseo/worktrees/1kaz3672/48-lingtai-round2`

## Linked issue / PR

issue #48（v4，唯一任务合同）；本轮不开 PR——push topic 分支后由上级 agent/human 决定后续。

## Owned paths

- `.claude/skills/worktree-pr-flow/SKILL.md`
- `.claude/commands/pr-review.md`（+ 若触发 `.agents/skills/command-pr-review/SKILL.md` 同步）
- `plans/`（S3 plan doc 新文件）+ `memory/doc-lifecycle.yaml`（注册新 plan）
- `memory/branches/48-lingtai-round2.md`（本文件）

## Forbidden paths

- `lab/data|runs|models` bytes、`checkpoints/`、`wandb/`、`lab/infra/private/`
- 不新增 validator、不新增 `.agent/*.md` doctrine 文件、不新增 skill 文件
- S3：只写 plan doc，不实现代码/CONTRACT 文件迁移

## Anatomy impact

预期无结构性增删移动：S2 是对既有两个文件的正文追加；S3 只新增一份 `plans/*.md`（登记方式遵循
`plans/ANATOMY.md` 既有 plan 登记模式，非新增 ANATOMY 节点类型）。若触发 anatomy 变化会在此补记。

## Claim / evidence impact

无实验 claim；S2/S3 均为治理文档，证据即 validator 输出与本文件的 Commands + results。

## Plan doc

S3 交付：`plans/20260715-anatomy-contract-pairing.zh.md`（待写，按 `interactive-plan-doc` 流程，
`memory/doc-lifecycle.yaml` 注册）。S2 不需要独立 plan doc——issue #48 v4 本身已是 approved scope。

## Current state

任务 A（S2）与任务 B（S3 plan doc）均已完成并各自 commit。等待 human / 都督·统·治理路线 review。

## Invariant（本次自检声明，dogfood S2 正文）

- 既有治理文档「单一规范 owner」不能被打破：任何被链接到别处的规则正文只能有一处正文所有者。
- `.agent/action-boundary.md` 继续是副作用授权分级的唯一权威源，S2 清单只能链接、不能复制其内容。

## Variation axis

- 仅新增/编辑 `.claude/skills/worktree-pr-flow/SKILL.md` 与 `.claude/commands/pr-review.md` 的正文
  （新增变更自检清单段落 + 双向互链）；S3 只产出一份新 plan doc + doc-lifecycle 注册，不动任何实现代码。

## Non-goals

- 不新增 validator、不新增 doctrine 文件、不新增 skill 文件（S2 硬边界）。
- 不实现 S3（CONTRACT.md 落地 / TS-1..TS-9 迁移 / `paired_contract` validator 扩展）——只写 plan doc。
- 不处理 S1（明确随 #46 阶段，本轮不碰）。
- 不批量迁移任何既有 policy 到 CONTRACT 形态；S3 plan 只设计「第一个试点」。

## Commands run

| command | 结论 |
| --- | --- |
| `python3 scripts/sync-codex-adapters.py` | 写入 38 个 adapter file（S2 改动触发 `worktree-pr-flow`/`command-pr-review` adapter 重生成） |
| `uv run --with pyyaml python scripts/validate-governance.py --strict` | `OK — 0 error(s), 0 warning(s)`（S2 提交前） |
| `python3 scripts/check-anatomy-drift.py` | `OK — 扫描 17 个 ANATOMY.md，0 处结构漂移` |
| `python3 scripts/sync-codex-adapters.py --check` | `OK — 0 issue(s)` |
| `python3 scripts/check-same-commit.py --staged`（S2） | `OK —— 0 处结构改动，对应 anatomy 已同变更集更新` |
| `git diff --check --staged`（S2） | 通过，无空白错误 |
| `python3 scripts/check-doc-lifecycle.py`（S3 新 plan 条目登记后） | `OK — 0 error(s), 0 warning(s)` |
| `uv run --with pyyaml python scripts/validate-governance.py --strict`（S3 提交前） | `OK — 0 error(s), 0 warning(s)` |
| `python3 scripts/check-same-commit.py --staged`（S3） | `FAIL`：新增 `plans/20260715-anatomy-contract-pairing.zh.md` 触发通用「拥有自己 ANATOMY.md 的目录新增文件」启发式；`plans/ANATOMY.md` 本身不枚举单个 plan doc（只描述生命周期状态模型），历史上其他纯 plan doc 新增提交（如 `287ab56`）同样未touch `plans/ANATOMY.md`——判断为已知误报，按 doctrine 文档化的 `SAME_COMMIT_SKIP=1` 逃生跳过，已在 commit message 里如实记录理由 |
| `git diff --check --staged`（S3） | 通过，无空白错误 |
| 裸 `python3 scripts/validate-governance.py --strict`（无 uv/PyYAML 环境） | `0 error(s), 4 warning(s)`（全部为既有 PyYAML 缺失 warning，非本轮改动引入，`uv run --with pyyaml` 绕过后 0 warning） |

## Latest result

- S2 commit `9079b5f`：`docs(worktree-pr-flow,pr-review): add change self-check checklist (G1 gate)`。
  4 files changed（`.claude/skills/worktree-pr-flow/SKILL.md`、`.claude/commands/pr-review.md`
  + 2 个 Codex adapter 同步生成物）。
- S3 commit `25812cb`：`plan(S3): draft ANATOMY<->CONTRACT pairing plan doc`。2 files changed
  （`plans/20260715-anatomy-contract-pairing.zh.md` 新建、`memory/doc-lifecycle.yaml` 登记）。
- 两次 commit 前均重新核对 live base（本地主 worktree `main`）——始终停在 `072af38`，未进一步移动，
  无需重放。
- 未新增 validator、未新增 `.agent/*.md` doctrine 文件、未新增 skill 文件，符合硬边界。
- S3 严格按「不实现」执行：只写 plan doc + 登记生命周期状态为 `draft`，未触碰任何
  `CONTRACT.md`/`check-anatomy-drift.py` 实现代码。
- plan doc 中记录了一个关键发现：check-anatomy-drift.py 在 #34→#42 已实现通用
  `contracts`/`contract_for` component 级双向 owner 校验，issue 描述的「paired_contract 扩展」
  不需要发明新字段——真正的设计缺口只是「root CONTRACT.md 受治理索引 ↔ 已有图」的交叉校验，
  已在 plan doc 中给出具体设计（`governed_components` 字段 + 三类 finding）。

## Open risks

- 分支名与授权指令不一致（`feat/48-checklist-contract` vs `feat/48-lingtai-round2`）：已记录、判断
  不影响功能，未处理。
- S3 plan doc 有两个未拍板问题需要 human 批注：(1) `.agent/template-versioning-policy.md` 除
  TS 表外其余章节是否也算 template-sync 可观察行为承诺，是否一并迁移；(2)
  `governed_components` 字段名是否合适。均已在 plan doc「未解决问题」一节列出，未擅自下结论。
- 本次 S3 commit 使用了 `SAME_COMMIT_SKIP=1`（理由见上「Commands run」表），提醒 review 时确认
  该判断成立。

## Exit condition

S2 落地且 validator 全绿（已达成）；S3 plan doc 完成并登记 `memory/doc-lifecycle.yaml`（已达成，
状态 `draft`，等待 human 批注 → approved）；本文件更新收尾（本次）；mailbox 汇报
都督·统·治理路线；agent 状态置 idle。
