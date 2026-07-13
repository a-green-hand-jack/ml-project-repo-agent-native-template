# Local issue integration handoff — 2026-07-13

Objective:
Integrate the nine human-selected features into local `main` only after exact-head fresh Codex
`APPROVE`; delete only merged local feature branches/worktrees; do not push, open/merge remote PRs,
release, restart Paseo, or touch protected bytes.

Current status:
- Feature-integration HEAD before this durable-status commit: `405c5421d7721111e14a4f9e7a745c41ec83630f`.
- Expected after committing this handoff: `origin/main...main` behind 0 / ahead 66. Remote main was not changed.
- Integrated and retired: #12, #12b, #12c, #14, #15, #16, #17.
- Retained and not merged: #13 at `02626c3`; #18 at `2bfef30`.
- Root status is clean except expected untracked `.claude/worktrees/` container noise.

Integrated sources / local commits:
- #12 source `6182630`, merge `3bad60d`.
- #12c source `35c6196`, merge `1a72762`.
- #12b source `f33ff9c`, merge `36ce42a`; combined B+C adoption smoke has 27 scenarios.
- #14 source `e0a32b5`, fast-forwarded earlier; harness follow-up `e24a652`.
- #15 source `94cb678`, merge `8b2bb93`.
- #16 source `ecf0c80`, merge `cbf6ab6`.
- #17 source `52f83aa`, merge `405c542`; staged integration candidate received a new `APPROVE`.

#16 integration evidence:
- `python{,3} [-S] lab/infra/launch/launch_gate.py --self-test`: 66/66 in all four modes.
- `python{,3} [-S] lab/infra/launch/fake_job.py --self-test`: 12/12 in all four modes.
- `python{,3} [-S] lab/infra/launch/expctl.py --self-test`: OK in all four modes.
- Experiment-state self-test passed in all four modes; normal strict: 0 errors / 0 warnings.
- Exact hook probes rejected attached `python -c...` and `nice -n10 sbatch`; safe controls passed.
- Adapter sync, strict harness/anatomy/governance, same-commit, diff and pycompile passed.

#17 integration evidence:
- `python scripts/check-provenance-chain.py --self-test` and `python -S ...`: OK.
- Normal and `python -S` strict provenance: 0 fail / 0 unknown / 13 pass.
- Integration fix accepts all #16 run states, but only `done + run_summary` closes provenance.
- Experiment-state strict, outcome strict, adapter sync, strict harness/anatomy/governance passed.
- Post-commit `expctl --self-test` also passed; source commit is an ancestor of local main.

Open blockers:
- #13 is not final-approved. Code HEAD `02626c3` is clean; synthetic evidence passes
  `check-doc-lifecycle --self-test` 47/47, guard regression 26/26, continuity probes 3/3.
  `lab/evals/doc-lifecycle/runtime-smoke-checklist.md` still has C1-C3/X1-X3/G1-G2 all unrun.
  These require real fresh Claude/Codex startup, clear/compact and hook evidence; do not fabricate.
- #18 final verdict is `REQUEST_CHANGES` at `2bfef30`. C1-C7/X1-X6 are `unknown`, X7 is
  `unavailable`; `python scripts/smoke-hook-guards.py --evidence-status --require-fresh` exits 1.
  Reviewer also found the evidence validator accepts status-only `pass` with placeholder/empty raw
  evidence; fix this code MAJOR and then collect real isolated runtime evidence before re-review.
- `feat/spawn-paseo-launch-notes` at `6862977` is unique, unreviewed, outside the nine-feature release
  set, and intentionally retained. `research/paper-positioning` was untouched.

Release decision / hard gate:
- Human semver override: each of the nine features counts as one PATCH from `v1.3.0`; target is
  `v1.3.9`, but only after all nine are implemented, fresh-approved, and merged locally.
- Only then run per-feature regressions, cross-feature integration/smoke, all related self-tests,
  adapter sync, strict harness/anatomy/governance, and diff/clean checks.
- After that matrix passes, update `VERSION`/`CHANGELOG` in the final release commit and create exactly
  one local annotated tag `v1.3.9`. No intermediate tags. Never push main/tag or create a release
  without new explicit authorization.
- Current `VERSION` remains `v1.3.0`; no tag points at current HEAD. Release/tag is blocked by #13/#18.

Exact next prompt:
Resume #13/#18 only when the required real Claude/Codex fresh-session and isolated X7 environment
are available. Fix #18 evidence-validator fail-closed semantics first, gather non-placeholder evidence,
obtain fresh exact-head APPROVE for both branches, then integrate #13 before #18 and run the authorized
release-level matrix. Do not update version or tag before all gates pass.

Forbidden paths / actions:
Protected data/run/model/checkpoint bytes and private env; push `main` or tags; remote PR/merge/release;
real training/scheduler launch/kill/restart; Paseo daemon restart.
