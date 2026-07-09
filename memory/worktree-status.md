# Worktree / Branch Status Overview

> Snapshot by branch-reporter (read-only git inventory: `git worktree list`,
> `git branch -a -vv`, `git log`, `git show --stat`, `git diff`, `git status`;
> no git write operations performed). Written from within the
> `worktree-case+elf-template-replay` worktree's own `memory/` tree (this repo
> tracks `memory/` per-branch as ordinary files, so this snapshot lives on this
> branch; a human may copy/adapt a version of it into `main`'s `memory/` if a
> repo-wide canonical copy is wanted).

Generated: 2026-07-09
Repo: `ml-project-repo-agent-native-template`

## Active worktrees (`git worktree list`)

| worktree path | branch | HEAD (last commit) |
| --- | --- | --- |
| `/home/user/Projects/ml-project-repo-agent-native-template` | `main` | `fc18318` |
| `/home/user/Projects/ml-project-repo-agent-native-template/.claude/worktrees/case+elf-template-replay` | `worktree-case+elf-template-replay` | `fdfa519` (working tree currently dirty — see below) |

## Active branches (`git branch -a`)

| branch | tracks | notes |
| --- | --- | --- |
| `main` | `origin/main` (up to date) | trunk; the template itself |
| `worktree-case+elf-template-replay` | none (not pushed to any remote) | 2 commits ahead of the branch point on `main` (`fc18318`); standalone case branch; **uncommitted in-progress changes present** |

No other local or remote branches found. No stale/orphan worktrees found.

## IMPORTANT: live/moving working tree at snapshot time

While compiling this report, `git status` on `worktree-case+elf-template-replay`
showed **real, uncommitted changes appearing between consecutive checks in the
same few minutes** — i.e. another agent/subagent is concurrently active in
this same worktree right now, doing real work (not something this reporter
produced). This reporter did not create or modify any of these; it only wrote
this file and `memory/branches/case-elf-template-replay.md`.

Observed dirty/untracked paths (snapshot, likely incomplete/still moving):

- `lab/artifacts/result-index.yaml`, `lab/artifacts/trace-index.yaml` — new
  `result-*`/`trace-*` entries recording a fresh, local, CPU-only replay of
  the ELF `pytorch_elf` runtime smoke (dependency install/import, config
  load, tiny synthetic forward pass) plus a `compileall`/`pytest` check of
  the migrated `lab/code/` scaffold.
- `lab/research/claims.yaml`, `lab/research/evidence.yaml`,
  `lab/research/experiment-ledger.yaml` — a new evidence entry
  `ev-elf-pytorch-runtime-smoke-replay-claude` (grade `log`) and ledger entry
  `run-elf-pytorch-runtime-smoke-replay-claude`, linked onto the existing
  `claim-elf-pytorch-runtime-smoke` (status stays `partial`, not promoted).
- `memory/current-status.md` — "Commands + results" table extended with the
  replay's commands/outcomes.
- `lab/AGENTS.md`, `lab/README.md`, `lab/code/AGENTS.md`, `lab/code/README.md`
  and a new untracked `lab/docs/README.md` — anatomy/doc-sync edits
  documenting the `docs/`, `eval/`, `external/` surfaces that this branch's
  migration commit added but that these guidance docs hadn't caught up to yet.
- On disk (gitignored, confirmed present, not part of git history):
  `lab/code/external/ELF` (fresh clone, `pytorch_elf` branch, commit
  `b29d8833609e9ab7f67cd9da39435ac5cea04837`) and
  `lab/code/external/.venv-elf-cpu` (disposable CPU-only uv env).

This activity appears to correspond to steps 2–3 of this branch's own planned
"Exact next steps" (re-clone ELF + CPU-only replay; register via an
artifact-librarian-style pass) plus an anatomy-drift-style doc-sync pass —
i.e. real progress, just not yet committed or reconciled. **Recommendation:
let the concurrent work finish, then have a human (or a dedicated follow-up
session) review the full diff and commit it deliberately, rather than
committing mid-flight.** This reporter did not commit, stage, or otherwise
touch any of these files.

## Per-branch summary

### `main`

- purpose: the `ml-project-repo-agent-native-template` template itself
  (doctrine, validators, hooks, skills, subagents).
- base: n/a (trunk).
- merge target: n/a (is the trunk).
- latest validation: not re-run by this reporter (out of scope: read-only
  inventory only). Recent commits (`fc18318`, `4437be0`, `70029db`, `b3ec84e`,
  `d706d31`) are governance/validator-hardening work on the template itself.
- sibling dependencies: is the base of `worktree-case+elf-template-replay`.
- detail file: not created — `main` is the trunk, not a feature/case branch;
  per this task's scope only the case branch gets a
  `memory/branches/<slug>.md`.

### `worktree-case+elf-template-replay`  (slug: `case-elf-template-replay`)

- purpose: standalone functional-test case branch — migrates the older
  `ELF-template-case` repo (built around the public `lillian039/ELF`
  PyTorch/JAX project) into this template's structure, to exercise the
  template's own validators/hooks/skills/subagents.
  **Not intended to merge into `main`.**
- base: `main` @ `fc18318`.
- worktree path: `.claude/worktrees/case+elf-template-replay/`.
- committed history: 2 commits beyond base — `c164232` (migration baseline),
  `fdfa519` (fix: two missed `lab/code/tests` files).
- working tree: **currently dirty** with real, apparently-concurrent,
  uncommitted follow-up work (see "IMPORTANT" section above).
- merge target: **none — standalone case/example branch; human decides
  whether to push/keep it, this does not follow a normal feature-branch merge
  flow.**
- full detail: `memory/branches/case-elf-template-replay.md`.

## Cross-branch relationships

- Only 2 branches/worktrees exist in this repo. No siblings compete for the
  same paths, no circular dependencies, no merge conflicts detected between
  `main` and `worktree-case+elf-template-replay`. **No cross-branch
  escalation needed.**
- `worktree-case+elf-template-replay` is a leaf: it depends on `main` as its
  base only; nothing depends on it, and it is not planned to merge back.
- Within the single case worktree, there is apparent **concurrent multi-agent
  activity** (this reporter + at least one other subagent editing files
  live) — not a branch-level conflict, but worth human awareness so the
  eventual commit is reviewed as a whole rather than assumed to be only this
  reporter's output.

## Open items for human attention

1. `.claude/worktrees/` shows as untracked (`??`) in `main`'s `git status` and
   is not listed in `.gitignore` — a minor repo-hygiene note, not blocking
   anything.
2. On `worktree-case+elf-template-replay`: the migration commit message
   (`c164232`) narratively asserts "All four governance validators pass
   clean," but as of the last committed state of
   `memory/current-status.md` the "Commands + results" table said validators
   had **not yet** been run. The now-uncommitted follow-up work adds a real
   CPU-only ELF replay + scaffold compile/test check, but still does not
   itself contain a fresh run of
   `validate-governance.py`/`check-anatomy-drift.py`/`check-agent-harness.py`/
   `check-same-commit.py` against the current (dirty) tree. Recommend running
   those before any commit of the currently-uncommitted changes.
3. The working tree is a **moving target** at report time (untracked/modified
   file set changed between two `git status` checks a few minutes apart).
   Whoever picks this up next should re-run `git status`/`git diff` rather
   than trusting this snapshot as final, and should coordinate with whatever
   other agent/session is still active before committing.
