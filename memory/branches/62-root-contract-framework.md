# Branch Status: 62-root-contract-framework

## Purpose

Issue #62 P2b: classify the root `CONTRACT.md` as template framework so the
real template-sync path creates or overwrites it downstream and no longer
reports it as unclassified.

## Branch / base

- Actual Paseo branch: `root-contract-template-framework` (the task's requested
  `fix/62-root-contract-framework` name is not used).
- Worktree: `/home/user/.paseo/worktrees/1kaz3672/62-root-contract-framework`.
- Base: `origin/main` @ `e3d89a812058d56647df34171cc9c8f9b0c32d7a`.
- Start state: `HEAD == origin/main`; worktree clean.

## Declaration

- Invariant: `CONTRACT.md` remains an upstream-owned governed-component index;
  template-sync retains its existing dry-run, receipt, and idempotency
  contracts.
- Variation axis: one explicit manifest rule classifies only root
  `CONTRACT.md` as `framework`, with production-path missing/stale regression
  coverage.
- Non-goals: no adoption-scaffold changes, no `.template.toml` anchor work,
  no root `CONTRACT.md` content changes, and no work on #60, #63, #54--#59,
  adapters, hooks, or other manifest kinds.

## Expected paths

- `template-manifest.toml`
- `lab/evals/template-sync/run-template-sync-smoke.py`
- `scripts/CONTRACT.md` only if its production-path evidence pointer changes
- `memory/branches/62-root-contract-framework.md`

## Validation

- `uv run --no-project python3 lab/evals/template-sync/run-template-sync-smoke.py` — OK.
- `uv run --no-project python scripts/sync-codex-adapters.py --check` — OK, 0 issue(s).
- `uv run --no-project python scripts/check-anatomy-drift.py --strict` — OK,
  17 ANATOMY files, 0 drift, 0 governance findings.
- `uv run --no-project python scripts/validate-governance.py` — OK, 0 errors;
  4 existing PyYAML-absence warnings.
- `git diff --check` — exit 0.
