# Result review: agent-native template functional test (ELF-template-case migration)

## Summary

Migrated `~/Projects/ELF-template-case` (an older `.harness/`-lineage template case, built
around the real public `lillian039/ELF` project) into this template's `lab/` + `deliverables/` +
`human/` + `memory/` shape on branch `worktree-case+elf-template-replay`, then exercised the
template's own validators, hooks, and a sample of subagents against it. Full findings:
`lab/docs/audits/agent-native-template-functional-test-report.md`.

## What was run (verifiable)

- `python scripts/validate-governance.py`, `check-anatomy-drift.py`, `check-agent-harness.py`,
  `check-same-commit.py --staged` — all pass clean on commits `c164232`, `fdfa519`, `0828a94`.
- Real `lillian039/ELF` re-clone (`pytorch_elf` @ `b29d8833609e9ab7f67cd9da39435ac5cea04837`) +
  fresh CPU-only dependency install + tiny synthetic forward pass, independently reproducing the
  old audit's recorded output shapes `(2,4,8)` / `(2,4,32)`.
- Hook probes (sudo, curl|sh, protected-path rm/mv/Write, git-push-to-main/topic-branch/escape) —
  all behaved as designed.
- 5 of 15 subagents exercised for real (artifact-librarian, experiment-orchestrator,
  repo-doc-steward, branch-reporter, test-runner); all stayed within their declared boundaries.

## Evidence pointers

- `lab/research/{claims,evidence,experiment-ledger}.yaml` — migrated + one fresh replay entry.
- `lab/artifacts/{result,trace}-index.yaml` — smoke-test index entries (result-001/002, trace-001/002).
- `memory/current-status.md` — full command/result log and decisions.
- `memory/branches/case-elf-template-replay.md`, `memory/worktree-status.md` — branch-reporter's inventory.

## Not yet proven / explicitly out of scope

- No GPU, dataset, checkpoint, training/generation loop, or metric reproduction for ELF (smoke only,
  matching the old evidence's own scope limits).
- 10 of 15 subagents and all `.claude/skills/`/commands entry points not yet exercised this round.
- The 6 findings classified as template gaps/friction (see report F2, F3, F5, F6, F7) are recorded,
  not fixed — this was a test-first pass per the task's scope.

## Human decision needed

- Whether to act on F2 (the nested-vendored-repo + relative hook-path self-locking failure) —
  arguably the most consequential finding, since it can wedge a whole session.
- Whether/when to push this case branch to the remote, and whether a further round should cover the
  remaining 10 subagents and the skill-level (Skill tool / slash command) entry points.

Status: **pending human review** — not yet approved.
