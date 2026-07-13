# 真实 runtime 证据 - 2026-07-13（issue #13 doc-lifecycle）

> 目标 commit：`68f1d43fdc6a1767fb890ab67d482bd414f9c64a`。所有 session 都在
> `/tmp/issue-13-18-fresh.UBWQdD/` 下的隔离 HOME 与 disposable clone 中启动；未修改真实
> 用户 trust 配置。原始转录与 debug log 以无时间戳 gzip 落在 `raw/`，完整性见
> `raw/SHA256SUMS`；`gzip -cd <file>.gz` 可直接核验原文。

## 结果

| case | runtime | session / thread | 结果 | raw evidence |
| --- | --- | --- | --- | --- |
| C1 | Claude Code 2.1.202 · Opus 4.8 | `13130000-0000-4000-8000-000000000001` | PASS：fresh startup 的 SessionStart stdout 为空；agent 按入口纪律读取 current-status + registry，报告 #13 plan 与 `implementing` | `raw/13-C1-claude-fresh-68f1d43.typescript.gz` + `raw/13-C1-claude-debug-68f1d43.log.gz` |
| C2 | Claude Code 2.1.202 · Opus 4.8 | interactive session，最终 resume id `6dda23e1-ea88-4aa6-9288-8f9bd4f6d60f` | PASS：`/clear` 后 debug 记录 `Hook SessionStart:clear (SessionStart) success`，additionalContext 以 `[continuity] clear 后回注` 开头，agent 复述 plan/status | `raw/13-C2-C3-claude-tui-68f1d43.typescript.gz` + `raw/13-C2-C3-claude-debug-68f1d43.log.gz` |
| C3 | Claude Code 2.1.202 · Opus 4.8 | 与 C2 同一隔离顶层 session | PASS：首次 `/compact` 因消息不足诚实返回 `Not enough messages to compact`；继续只读多轮后第二次真实完成，debug 记录 `Hook SessionStart:compact (SessionStart) success`，agent 复述 compact continuity、plan 与 status | 同 C2 |
| X1 | Codex 0.144.0 · gpt-5.6-sol | `019f5b9c-ff75-7251-81bd-404c69bd5345` | PASS：fresh startup 无 continuity；agent 按入口纪律报告 #13 plan、`implementing` 与目标 commit | `raw/13-X1-codex-fresh-68f1d43.typescript.gz` |
| X2 | Codex 0.144.0 · gpt-5.6-sol | interactive TUI | PASS：`/clear` 后出现 `SessionStart hook (completed)` 与 `[continuity] clear 后回注` | `raw/13-X2-X3-codex-tui-68f1d43.typescript.gz` |
| X3 | Codex 0.144.0 · gpt-5.6-sol | interactive TUI | PASS：`Context compacted` 后出现 `SessionStart hook (completed)` 与 `[continuity] compact 后回注`；无 invalid hook JSON / hook failed | 同 X2 |
| G1 | Claude Code 2.1.207 · Opus 4.8 | reject `d9f7a21c-6fd7-4e48-915d-47328ccb6319`; skip `2a237d0b-c28f-4319-a839-6cb0a6899f6a` | PASS：默认 fresh session 的真实 Write 被 `doc-lifecycle:` 拒绝且文件未创建；独立 fresh session 仅设置 `DOC_LIFECYCLE_SKIP=1` 后同一无效 Write 成功 | `raw/13-G1-reject-claude-68f1d43.typescript.gz`, `raw/13-G1-reject-claude-debug-68f1d43.log.gz`, `raw/13-G1-skip-claude-68f1d43.typescript.gz`, `raw/13-G1-skip-claude-debug-68f1d43.log.gz` |
| G2 | Claude Code 2.1.207 · Opus 4.8 | `1cecf47b-6901-477b-a87d-cbc3d299e1e8` | PASS：真实 Bash `rm memory/doc-lifecycle.yaml` 被 `doc-lifecycle: 禁止删除/移走` 拒绝；disposable clone 中注册表仍存在 | `raw/13-G2-delete-claude-68f1d43.typescript.gz` + `raw/13-G2-delete-claude-debug-68f1d43.log.gz` |

## 隔离与真实性边界

- Claude probe 使用临时 `HOME` / `CLAUDE_CONFIG_DIR`；Codex probe 使用临时 `CODEX_HOME`。
- C1-C3 与 X1-X3 都由独立顶层 CLI session 产生，不是 hook 脚本直接 stdin 模拟。
- G1/G2 使用 `--dangerously-skip-permissions` 只绕过 Claude 的交互权限提示，使 repo
  `PreToolUse` hook 成为实际裁决面；默认 G1 与 G2 仍由该 hook 拒绝。
- `DOC_LIFECYCLE_SKIP=1` 只存在于 G1 allow half 的单个 fresh process；未写入任何用户配置。
- G1 allow half 留下的无效 plan 只存在于 disposable clone，不进入 feature worktree。
- 原始转录未包含 credential；凭据只在隔离 HOME 内供 CLI 认证，未复制进 repo。

## 可核验断言

```text
C2 debug: Hook SessionStart:clear (SessionStart) success
C3 debug: Hook SessionStart:compact (SessionStart) success
C3 model: [continuity] compact 后回注 ... / plans/20260712-plan-lifecycle-state.zh.md / implementing
X3 TUI: Context compacted -> SessionStart hook (completed) -> [continuity] compact 后回注
G1 reject: PreToolUse:Write exit_code=2, permissionDecision=deny, reason starts doc-lifecycle:
G1 skip: PreToolUse:Write exit_code=0, File created successfully
G2: PreToolUse:Bash exit_code=2, permissionDecision=deny, registry remains present
```

synthetic fixtures、严格门禁与 adapter parity 仍需在 evidence-only HEAD 上重跑；本文件只证明
真实 runtime 接线、上下文 continuity 与 guard enforcement，不替代 code review。
