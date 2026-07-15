# Branch Status: 18-anatomy-semantic-parity（已归档删除）

## Purpose
实现 issue #18（ANATOMY 语义漂移检查 + Claude/Codex enforcement parity）的完整范围：
静态语义漂移检测扩展 + 运行时 hook enforcement parity 证据。

## Parent session
2026-07-12 起多轮本地 issue 集成（见 `memory/handoffs/20260713-local-issue-integration-codex.md`）。

## Branch / base
`integrate/18-anatomy-semantic-parity`（在 `feat/18-anatomy-semantic-parity` 基础上 merge + 继续开发，
merge-base 落后 main 20 commits，自身领先 21 commits）。

## Worktree
`.claude/worktrees/18-integration`（已 `git worktree remove`）。

## Linked issue / PR
- 原 issue #18 — **CLOSED as deferred**（2026-07-14，human 关闭）：独立 fresh dual-runtime 复核显示
  protected-path 写入（X1）与 main push guard（X2）在真实 Paseo/Codex session 里未生效，C5（ruff 缺失）
  /C6（无真实 compact/clear 触发）无法采集证据。本分支的 C1-C7/X1-X7 "全 pass" 证据是同一隔离环境的
  self-attestation，与独立复核结果不一致，未被采信。
- 静态可判定的那部分范围已拆分为 #34（CLOSED, merged，全新实现，未复用本分支代码）→ 落地为
  `e38a21e` / `8d1def4` / `327e76a`（#42）。
- 运行时 hook enforcement parity 部分重新开为新 issue **#46**（open，待 human review）。

## Owned paths
`scripts/check-anatomy-drift.py`、`scripts/check-same-commit.py`、`scripts/check-agent-harness.py`、
`scripts/validate-governance.py`、`scripts/smoke-hook-guards.py`、`plans/evidence/issue-18/*`。

## Forbidden paths
`lab/data/`、`lab/runs/`、`lab/models/` bytes、远端 push/PR/release。

## Anatomy impact
无——分支未合入 main，anatomy 未受影响。

## Claim / evidence impact
分支内 C1-C7/X1-X7 evidence（`plans/evidence/issue-18/`）**不可信为已验证结论**——已被独立 fresh 复核
推翻，不得在后续工作中引用为"已通过"的证据。

## Plan doc
`plans/20260712-anatomy-semantic-parity.zh.md`（status 应随本次归档更新为 abandoned/superseded，未随本
commit 一并改，因为该文件只存在于已删除分支，不在 main 上）。

## Current state
分支与 worktree 已删除（`git branch -D` + `git worktree remove`），本地无残留引用。

## Commands run
- `git worktree remove .claude/worktrees/18-integration`
- `git branch -D integrate/18-anatomy-semantic-parity`

## Latest result
删除前 worktree `git status --short` 为空（无未提交改动），删除安全。

## Open risks
`.claude/worktrees/18-runtime-codex-62086fb` 是一个**独立 git clone**（非本仓库 linked worktree），
指向一个已不在 `origin` 上的 `integrate/18-anatomy-semantic-parity` 远端引用，疑似此前 Codex rescue
session 遗留产物。本次归档未触碰它，需要单独确认是否清理。

## Exit condition
已达成：分支删除，工作或被 #34/#42 吸收、或被拆分重开为 #46，无悬空引用。
