# Branch Status: #89 Codex project-hook trust/runtime closure

- branch: `fix/89-codex-hook-trust`
- base: `origin/main@3114443d4ffefbec40a7c9288280f9da0c5736ef`
- issue: #89

## 前置声明

- **Invariant**：不解析或改写 `~/.codex/config.toml` 的内部 trust schema；用户必须在 Codex `/hooks`
  中显式审阅、信任或撤销；缺运行时证据时不得宣称已受保护。
- **Variation axis**：把“静态配置存在”升级成“exact hook/script bundle 可审计 + fresh SessionStart
  receipt 可观察”的仓内闭环。
- **Non-goals**：不自动接受用户级 trust，不用 synthetic receipt 冒充真实 Codex session，不在本分支
  发布 v1.4.0。

## 实现

- `scripts/check-codex-hook-runtime.py` 提供 bundle manifest/check/refresh、runtime status 与 receipt 写侧；
- 所有 `.codex/config.toml` hook command 嵌入共享 script-bundle SHA，引用脚本变化后静态门禁失败，
  刷新 SHA 会改变 hook definition，交由 Codex `/hooks` 重新审阅；
- `codex_runtime_receipt.py` 仅在 Codex `SessionStart` 真加载 project hook 时写 gitignored receipt；
- bootstrap/adoption/README 明示 `/hooks` trust、fresh session 验证与撤销路径；
- harness/capability/anatomy/adapter 同步更新。

## 验证

- `python scripts/check-codex-hook-runtime.py --check` → OK
- `python lab/evals/codex-hooks/run-codex-hook-trust-smoke.py` → PASS：untrusted → loaded → changed/stale
- `python scripts/check-agent-harness.py --strict` → 0 error / 0 warning
- `python scripts/check-capability-catalog.py` → 47 项，0 error / 0 warning
- `python scripts/sync-codex-adapters.py --check` → OK
- `python scripts/check-anatomy-drift.py` → OK
- `python scripts/check-doc-lifecycle.py` → OK
- `python scripts/validate-governance.py --strict` → OK
- `git diff --check` → OK

## 剩余 human gate

候选 commit 合入后，在 fresh clone/worktree 启动真实 Codex：`/hooks` 逐项审阅并信任，退出后重新
启动 fresh session；确认 `--status` 为 `TRUSTED_AND_LOADED`、受保护路径负例被 PreToolUse 拒绝、
允许路径正例成功、identity 状态可观察。该证据完成前 #89 不关闭、#90 不发布。
