# 真实 runtime 证据 - 2026-07-13（issue #13 doc-lifecycle）

> continuity / context hook 目标 commit：`68f1d43fdc6a1767fb890ab67d482bd414f9c64a`；
> 最终 guard/parser exact code target：
> `654af4c11aafc2b769b7a824ba460bca25a3fb38`。
> 所有 session 都在 `/tmp/issue-13-18-fresh.UBWQdD/` 或
> `/tmp/issue13-g12-654af4c.jc4Yrm/` 下的隔离 HOME 与 disposable clone 中启动；未修改真实
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
| G1 | Claude Code 2.1.207 · Opus 4.8 | reject `15133371-9528-4b6c-9e1d-b76e7289cf2b`; skip `e4f8985b-be89-426f-b50e-96e9d931c279` | PASS（目标 `654af4c`）：两份 raw 内嵌 wrapper 全文+SHA、exact HEAD、空 pre-status 与 registry present；默认进程明确记录 SKIP=UNSET，同一 malformed-draft Write 被 `doc-lifecycle:` deny，post-status 仍空且 probe missing；独立进程明确记录 SKIP=1，唯一 Write hook exit 0，post-status 只含该 probe及其 SHA256/正文 | `raw/13-G1-reject-claude-654af4c.typescript.gz`, `raw/13-G1-reject-claude-debug-654af4c.log.gz`, `raw/13-G1-skip-claude-654af4c.typescript.gz`, `raw/13-G1-skip-claude-debug-654af4c.log.gz` |
| G2 | Claude Code 2.1.207 · Opus 4.8 | opaque delete `cdfa4fcc-84ed-46c5-863f-d4719d55eb7d`; cp target-directory `d616729b-17ac-414e-beee-6b1a17a8061a` | PASS（目标 `654af4c`）：opaque `git rm --pathspec-from-file` 与本轮 MAJOR 的真实 `cp --target-directory=memory .../doc-lifecycle.yaml` 各由独立顶层 session 唯一 Bash 调用并被 deny；两份 raw 均内嵌 wrapper、环境、exact HEAD 与 pre/post clean，前者 registry/pathspec 保持，后者 registry SHA256 `16e6168f...35b81c` 前后不变 | `raw/13-G2-delete-claude-654af4c.typescript.gz`, `raw/13-G2-delete-claude-debug-654af4c.log.gz`, `raw/13-G2-cp-target-claude-654af4c.typescript.gz`, `raw/13-G2-cp-target-claude-debug-654af4c.log.gz` |

## 隔离与真实性边界

- Claude probe 使用临时 `HOME` / `CLAUDE_CONFIG_DIR`；Codex probe 使用临时 `CODEX_HOME`。
- C1-C3 与 X1-X3 都由独立顶层 CLI session 产生，不是 hook 脚本直接 stdin 模拟；其协议代码从
  `68f1d43` 到 `654af4c` 未变化；`.claude/settings.json` 的差异只增加 #16 Bash permission
  规则，未改变 SessionStart matcher。G1/G2 因 guard/parser 代码在 exact-head review 后变化，
  已在 `654af4c` 的四个新 disposable clones 中重跑；wrapper 全文/SHA、进程环境、pre/post shell
  输出与顶层 Claude stream-json/hook events 写进同一 typescript，避免把 prompt 自述或临时
  wrapper 的外部存在冒充可持久核验事实。
- G1/G2 使用 `--dangerously-skip-permissions` 只绕过 Claude 的交互权限提示，使 repo
  `PreToolUse` hook 成为实际裁决面；默认 G1 与 G2 仍由该 hook 拒绝。
- `DOC_LIFECYCLE_SKIP=1` 只存在于 G1 allow half 的单个 fresh process；wrapper 的 `env` 调用是
  可核验的进程事实，Claude 在无 Bash 工具时声称“未设置”的自我推断不改变该事实；hook exit 0
  与文件落盘构成 runtime 结果。该变量未写入任何用户配置。
- G1 allow half 留下的无效 plan 只存在于 disposable clone，不进入 feature worktree。
- 历史首次 G1 override 尝试（session `5a29d38b-4040-47a6-bbc0-a2ab4c6ca718`）在 tool call 前由
  模型拒绝，不计 PASS；raw 以 `13-G1-skip-attempt-refused-*` 保留。随后用中性 malformed-draft
  fixture 在两个新 clones 复跑同一 default/skip payload，才形成上表 G1 PASS。
- 原始转录未包含 credential；凭据只在隔离 HOME 内供 CLI 认证，未复制进 repo。

## 可核验断言

```text
C2 debug: Hook SessionStart:clear (SessionStart) success
C3 debug: Hook SessionStart:compact (SessionStart) success
C3 model: [continuity] compact 后回注 ... / plans/20260712-plan-lifecycle-state.zh.md / implementing
X3 TUI: Context compacted -> SessionStart hook (completed) -> [continuity] compact 后回注
G1 reject: PreToolUse:Write exit_code=2, permissionDecision=deny, reason starts doc-lifecycle:
G1 skip: PreToolUse:Write exit_code=0, File created successfully
G1 raw wrapper: EVIDENCE_HEAD=654af4c...; reject SKIP=UNSET, post-status empty/probe missing;
    skip SKIP=1, post-status only probe present with recorded SHA256/text; both registry present
G2: git rm --pathspec-from-file=<file naming registry> -> PreToolUse:Bash exit_code=2,
    permissionDecision=deny; raw wrapper records 26-byte pathspec text+SHA256 and empty post-status,
    registry present, pathspec SHA256 unchanged
G2 cp: cp --target-directory=memory <source/doc-lifecycle.yaml> -> PreToolUse:Bash exit_code=2;
    raw wrapper records source text/SHA256 and identical pre/post registry SHA256
```

本文件只证明真实 runtime 接线、上下文 continuity 与 guard enforcement；synthetic fixtures、
严格门禁与 adapter parity 由 evidence-only symbolic `HEAD` 的验证记录补足，且不能替代 code review。
