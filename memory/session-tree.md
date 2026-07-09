# Session Tree

> 记录当前 session 的父/子拓扑，让并行/派生工作可被追踪与合并。
> 与 `current-status.md` 配合：status 记「现在做什么」，tree 记「有哪些并行分支、怎么合」。

_Last touched by session-boundary-control skill, 2026-07-09（round 2 + anatomy-drift-control 已跑完；本次是收尾判定）。_

## Parent objective

把一个真实的 ELF case repo 迁移进本 agent-native 模板，并在真实素材上端到端验证模板的治理面（4 个 governance validators、真实 ELF 代码的 re-clone/smoke test、hooks/permissions、~14 个 subagents、部分 skills）是否成立；迁移过程中顺带发现并修复了一个真实的 hook 自锁（self-locking）bug。

## Current phase

`.agent/phase-dashboard.yaml` 在本 repo 中不存在（未实例化具体 phase id），因此用自由文本记录：

**round 2 已完成**（9 个 subagent 中 8 个跑完、1 个被 auto-mode classifier 拦下；`anatomy-drift-control` skill 已跑，修了一处真实 gap：`.claude/hooks/drafts/` 未登记进 `.claude/ANATOMY.md`，现已补上）。此前已完成：case 迁移 → 4 个 governance validators → ELF 真实代码 re-clone + smoke test → hooks/permissions 探测 → round 1（5 个 subagent）→（独立分支）诊断并修复 hook 自锁 bug → PR 合并 → 修复同步回本分支 → 现场复验（发现新问题：session 内 hook 配置不会中途刷新）→ round 2。

**边界决策（本次 session-boundary-control 调用）**：**continue**——不做 compact/clear。理由：只剩一个收尾任务（把 round 2 发现写进报告 + commit + push），属于当前工作的自然延续，此刻打断/压缩上下文没有收益。**但收尾之后建议开一个全新 session**（不是 `/clear` 同一 session）专门做两件事：(a) 独立、干净地复验 `hook-self-lock-fix`（本 session 的 hook 配置是启动时缓存的，无法自证该修复对新 session 生效）；(b) 视 human 决定是否启动 `plans/20260709-round3-template-functional-test.zh.md` 提出的 round 3（剩余 skills + slash commands + 对抗性 validator 探针）。

## Children

| id | purpose | branch/worktree | plan doc | status | next prompt |
| --- | --- | --- | --- | --- | --- |
| `case-elf-template-replay` | 迁移真实 ELF case repo 进模板 + 跑 governance validators + ELF smoke test + hooks 探测 + 全量 subagent/skill 演练 | `worktree-case+elf-template-replay`（本 worktree，off `main`） | 未在本次检查中定位到对应 `plans/<YYYYMMDD>-<slug>.zh.md`；需确认是否存在或需要补写 | active（round 2 与本记录并行进行中，未完成） | round 2 跑完后再触发边界动作，见下方「next prompt」 |
| `hook-self-lock-fix` | 诊断并修复迁移过程中暴露的真实 hook 自锁 bug | 短生命周期修复分支，off `main`（具体分支名/PR 号未经 git 独立核实——本次检查无 shell/git 工具访问，系据 session 叙述重建） | 未定位到 | done — 已开 PR 并合并入 `main`，worktree 已清理，修复已同步回 `case-elf-template-replay` | 无（已关闭）；如需追溯，建议下次有 git 访问时补上 commit hash / PR 链接 |

## Merge / review order

1. `hook-self-lock-fix` → `main`（已完成：PR 已合并，worktree 已清理）。
2. `main` → `case-elf-template-replay`（已完成：修复已同步回本分支）。
3. 现场复验该修复（已尝试；因 session 内 hook 配置缓存不刷新，本次复验只能算「部分/未决」——见 Open risks）。
4. `case-elf-template-replay` round 2（剩余 subagent + skills）跑完 → 汇总 pass/fail → 决定是否需要独立 fresh session 对 hook 修复做干净复验。

## Global forbidden paths

- `lab/data/`、`lab/runs/`、`lab/models/` 的 bytes/checkpoints/wandb/远端产物，`lab/infra/private/`——除非明确要求，不编辑/删除。
- 不启动/kill/restart 长训练或远端作业。
- 不开新的 PR / merge / release / 改远端基础设施，除非拿到 human 批准（`hook-self-lock-fix` 的 PR 已按叙述完成合并，视为已获批准，但本记录未见到批准的直接证据文件——如有疑问建议核实）。
- `git push` 到 `main`/`master` 需 `CLAUDE_ALLOW_PUSH_MAIN=1` 显式放行。
- 不无理由新增依赖。

## Open risks

- **Session 内 hook 配置不会中途刷新**：现场复验 `hook-self-lock-fix` 时发现，当前 session 进程启动时缓存的 hook 配置不会因为 `main`/本分支拿到新 commit 而中途刷新。这意味着在*同一个仍在运行的 session* 里对该修复做的任何「已验证生效」的结论都是不可靠的——真正的确认需要在一个全新启动的 session/进程里重跑触发路径。这条风险目前挂在 `case-elf-template-replay` 名下，因为后续复验很可能还在这个 worktree 里进行。
- `hook-self-lock-fix` 的确切分支名/PR 号未经独立 git 核实（本次记录工具集无 shell/git 访问，纯据上游 session 叙述重建）——不影响当前判断，但建议在下次有 git 访问的场合补全，便于审计。
- round 2（剩余 subagent + skills）与本次记录**并行**进行中：本文件是快照，`case-elf-template-replay` 的实际状态可能在写入后继续变化，不构成锁定。
- ~~`current-status.md` 目前仍是空模板骨架~~ —— 已由 checkpoint-writer 补全（round 2 期间），此风险已解除。
- 一个不带 Bash 工具的 subagent（session-boundary-agent，round 2）曾把 `memory/session-tree.md` 与两份 `memory/branches/*.md` 误写进主仓库而非本 worktree（因为它只能靠 prompt 里的文字路径，没有 `cd` 能力）；已发现并手工搬回、主仓库已还原干净。教训：给不带 Bash 的 subagent 派任务时，即使写了「Working directory: X」，也不能保证它真的在那里读写——需要更谨慎地验证，或考虑给这类 subagent 明确的绝对路径而非依赖文字约定。
- `repo-researcher`（round 2）发现同一类「裸相对路径假设 cwd==repo 根」的 bug 在 `.githooks/pre-commit`、`.claude/hooks/pre_compact_memory_check.py` 与 `subagent_report_index.py` 内部路径、`.claude/settings.example.json` 里还有未修复的实例——`hook-self-lock-fix` 只覆盖了 `settings.json` 的 hook 映射本身。是否扩大修复范围待 human 决定。
