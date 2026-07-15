# Branch Status: 61-codex-adapter-ownership

## Purpose

Issue #61 P1: make Codex adapter ownership exact so template-sync treats only
`.codex/agents/**` and `.agents/skills/**` as generated.

## Branch / base

- Branch: `61-codex-adapter-ownership`
- Worktree: `/home/user/.paseo/worktrees/1kaz3672/61-codex-adapter-ownership`
- Base: `origin/main` @ `2eaf02408ecdea6d086cc6648e4933511ee64b31` (verified before edits).

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
| `git diff --check` and `git diff --cached --check` | exit 0 |
| `./scripts/check-same-commit.py --staged` | `OK —— 1 处结构改动，对应 anatomy 已同变更集更新` |

`./scripts/validate-governance.py` reached the new adapter checks successfully
but failed on the pre-existing active `#48` lifecycle entry, whose branch and
worktree are absent in this checkout. It also emitted four existing PyYAML
absence warnings. This worker was forbidden to modify lifecycle state.

The required Python commands could not be started in this Codex App execution
surface. Each was rejected before process creation with:

`Rejected("approval required by policy, but AskForApproval is set to Never")`.

This affected control-plane registration/heartbeat/idle and the requested
`python3 lab/evals/template-sync/run-template-sync-smoke.py` invocation. The
smoke is not executable (`Permission denied` when called directly), while its
specified `python3` form is policy-rejected; no smoke PASS is claimed.

## Risk / handoff

The implementation is ready for a clean verifier run, but is **not yet a
commit candidate with validation evidence**. Re-run the issue's required
commands, inspect the same-commit diff, then commit and push this branch.
