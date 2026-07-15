# Branch Status: 61-codex-adapter-ownership

## Purpose

Issue #61 P1: make Codex adapter ownership exact so template-sync treats only
`.codex/agents/**` and `.agents/skills/**` as generated.

## Branch / base

- Branch: `61-codex-adapter-ownership`
- Worktree: `/home/user/.paseo/worktrees/1kaz3672/61-codex-adapter-ownership`
- Base: `origin/main` @ `2eaf02408ecdea6d086cc6648e4933511ee64b31` (verified before edits).
- Implementation commit: `53262c6` (`fix(template-sync): classify Codex adapters by owner`),
  pushed to `origin/61-codex-adapter-ownership`.

## Declaration

- Owned: `template-manifest.toml`, adapter/template-sync regression surfaces,
  designated ANATOMY/CONTRACT files, this branch status, and the agent report.
- Forbidden: root `CONTRACT.md`, `.template.toml`, lifecycle/current-status files,
  #60/#62/#63 scope, runtime-hook parity, protected artifact/env paths, PR/merge/release.

## Changed files

- `template-manifest.toml`: concrete generated rules precede `.codex/**` and
  `.agents/**` framework fallbacks.
- `scripts/sync-codex-adapters.py`: `--check` uses the production
  `template-sync.py` classifier and tracked paths to require the manifest
  generated set to equal `expected_files()` exactly.
- `lab/evals/template-sync/run-template-sync-smoke.py`: production-path
  fixture uses the real adapter generator to prove framework overwrite,
  generated-only rebuild, exact set, and no-op rerun.
- `ANATOMY.md`, `.codex/ANATOMY.md`, `.agents/ANATOMY.md`, `scripts/ANATOMY.md`,
  `scripts/CONTRACT.md`: ownership and TS-5 evidence references synchronized.

## Validation

Passed:

| command | result |
| --- | --- |
| `./scripts/sync-codex-adapters.py --check` | `OK — 0 issue(s)` |
| `./scripts/check-agent-harness.py` | `OK — 0 error(s), 0 warning(s)` |
| `./scripts/check-anatomy-drift.py --strict` | `OK — 17 ANATOMY, 0 drift, 0 governance findings` |
| `uv run --no-project python3 lab/evals/template-sync/run-template-sync-smoke.py` | `OK`，完整 production-path smoke（含 #61 adapter ownership scenario） |
| `git diff --check` and `git diff --cached --check` | exit 0 |
| `./scripts/check-same-commit.py --staged` | `OK —— 1 处结构改动，对应 anatomy 已同变更集更新` |

`./scripts/validate-governance.py` reached the new adapter checks successfully
but failed on the pre-existing active `#48` lifecycle entry, whose branch and
worktree are absent in this checkout. It also emitted four existing PyYAML
absence warnings. This worker was forbidden to modify lifecycle state.

The initial #61 fixture run exposed a missing `root/scripts/` parent before
`copy2()`. Both fixture builders now create that parent explicitly; all other
fixture file writes use the local `write()` helper, which creates parents.
The prescribed `uv run --no-project python3 ...` rerun passed.

## Risk / handoff

The implementation has complete #61 regression evidence and is ready for an
independent verifier. The sole governance blocker is the pre-existing #48
lifecycle record and must not be masked in this issue.
