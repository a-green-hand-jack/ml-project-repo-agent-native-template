# #89 Codex hooks fresh-session D1/D4 复验

## 结论

**PASS**。PR #91 合入后的 exact candidate `4d1d598229dd3063b9a084b4f488ca71ce15f40a`
在真实 Codex CLI 0.144 fresh session 中，经 `/hooks` 人工信任后：

- 项目 hook bundle 被识别为 `TRUSTED_AND_LOADED`；
- D4 identity hook 注入的自命名流程通过规定脚本完成，身份可观察；
- D1 对 `lab/data/**` 的真实写入被 hook 拒绝；
- 同一 session 对允许路径的写入成功，证明不是 blanket deny。

## 环境与候选

- repo：`a-green-hand-jack/ml-project-repo-agent-native-template`
- worktree：`/home/user/Projects/wt-89-codex-hooks-fresh`
- branch：`test/89-codex-hooks-fresh`
- exact candidate：`4d1d598229dd3063b9a084b4f488ca71ce15f40a`
- Codex：`codex-cli 0.144.0`
- fresh verification session：`019f763c-9301-7d70-93db-a15b1a801808`
- sandbox / approval：`workspace-write` / `on-request`

## `/hooks` 信任与 fresh-session receipt

首次真实 TTY session 中，`/hooks` 显示 10 个项目 hooks 待 review；按界面提示执行
`t`（trust all）后，各事件组显示 active。退出后重新启动全新 Codex session，启动时不再出现
review 提示，说明信任状态已持久化。

fresh session 第一次提交用户 prompt 后，界面显示 `SessionStart hook (completed)`；repo-local
receipt 落在 `.codex/runtime/hook-receipt.json`：

```json
{
  "bundle_sha256": "d7e28f2bdb1d53f9759fd0029c4c0d53772afb8ddd5e453320ed3dd41f7d89f9",
  "event": "SessionStart",
  "repo_root": "/home/user/Projects/wt-89-codex-hooks-fresh",
  "schema": "codex-project-hook-receipt-v1",
  "session_id": "019f763c-9301-7d70-93db-a15b1a801808"
}
```

外部独立读取：

```text
$ python scripts/check-codex-hook-runtime.py --status
[codex-hook-trust] TRUSTED_AND_LOADED
bundle_sha256: d7e28f2bdb1d53f9759fd0029c4c0d53772afb8ddd5e453320ed3dd41f7d89f9
identity_observable: true
```

注：Codex 0.144 的 `SessionStart` receipt 在 TUI 首屏绘制时尚不可见，在 fresh session 的第一个
用户 turn 提交后才可观察；因此验收点是“首个 turn 后 loaded”，不是“首屏前 loaded”。

## D4：identity 链

真实 Codex 按 `UserPromptSubmit` hook 注入的规则，执行唯一规定入口：

```text
python3 .claude/hooks/agent_name_set.py "师爷·验·D4复验"
```

外部独立读取证据：

```text
.agent-identity: 师爷·验·D4复验
memory/agents-roster.md: status=active, focus=D4复验
check-codex-hook-runtime.py: identity_observable: true
```

一次使用 `approval_policy=never` 的预探针被 Codex 自身审批策略拒绝，未被计作 PASS；随后在
`on-request` 的全新 session 中重做并成功落盘。该区分防止把“hook 注入了文字”误报为“身份链已完成”。

## D1：保护路径正负探针

在同一真实 fresh Codex session 中，要求 Codex 使用自己的写文件工具：

1. 尝试写 `lab/data/codex-d1-deny-probe.txt`，内容 `DENY`；
2. 再写允许路径 `.codex/runtime/codex-d1-allowed-probe.txt`，内容 `ALLOWED`。

Codex 报告第一步被 PreToolUse hook 拒绝、第二步成功。主 agent 从 session 外独立核对：

```text
protected_absent=1
allowed_content_ok=1
git status --short: <empty>
```

因此结论不是模型自述：受保护文件实际不存在，允许路径文件实际存在且内容精确为 `ALLOWED`。

## Stop condition

- [x] `/hooks` 信任通过真实交互完成并在 fresh session 持久化；
- [x] exact candidate receipt 为 `TRUSTED_AND_LOADED`；
- [x] D4 身份通过规定脚本落盘且 checker 可观察；
- [x] D1 保护路径真实拒绝 + 允许路径真实成功；
- [x] Codex TTY session 已 `/exit` 正常退出；
- [ ] 本证据经 PR 合入 main、#89 关闭、topic branch/worktree 清理。
