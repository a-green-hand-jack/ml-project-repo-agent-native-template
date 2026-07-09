# Agent-Native Template Functional Test Report

Case: migrate `ELF-template-case` into `ml-project-repo-agent-native-template`, then
functionally test the template's own validators / hooks / skills / subagents.

Branch: `worktree-case+elf-template-replay` (worktree at
`.claude/worktrees/case+elf-template-replay/`, branched from `main`). Not intended to
merge back; a standalone reviewable case (see `memory/branches/case-elf-template-replay.md`).

## Baseline

- Source case repo: `~/Projects/ELF-template-case` (GitHub
  `a-green-hand-jack/ELF-template-case`, branch `case/elf-template-replay`), an instance of
  an older template lineage (`.harness/` / `research-project-template` / `research_project_harness`
  CLI), itself built to stress-test that older template against the real public
  `lillian039/ELF` PyTorch/JAX training project. Read-only reference throughout; never modified.
- Target template: `ml-project-repo-agent-native-template` `main` @ `fc18318`, a redesigned,
  Claude-Code-native successor (`.agent/` doctrine + `.claude/` capability + `lab/` research plane +
  `scripts/` validators), sharing clear lineage with the old skill set (anatomy-drift-control,
  artifact-indexing, experiment-workflow, session-boundary-control, subagent-routing,
  worktree-pr-flow, interactive-plan-doc, workflow-recipe-harvesting) but no `.harness/`/`rph` CLI.
- Environment: local Linux machine, CPU only, no GPU, no EPFL cluster access (the old audits
  were run on a Mac + EPFL RunAI cluster with a persistent PyTorch env). No push to any remote.

## Commands

Representative commands actually run (full list in `memory/current-status.md`'s Commands +
results table and the two commits on this branch):

```bash
python3 scripts/validate-governance.py         # includes check-agent-harness, check-anatomy-drift
python3 scripts/check-same-commit.py --staged
git clone --depth 1 --branch pytorch_elf https://github.com/lillian039/ELF lab/code/external/ELF
uv venv --python 3.11 lab/code/external/.venv-elf-cpu
uv pip install --python lab/code/external/.venv-elf-cpu/bin/python \
  --extra-index-url https://download.pytorch.org/whl/cpu -r lab/code/external/ELF/requirements.txt
# config load + apply_config_overrides + tiny synthetic CPU forward (see current-status.md)
(cd lab/code && python3 -m compileall -q src eval experiments scripts tests)
(cd lab/code && uv run --no-project --with pytest --python 3.11 python -m pytest -q tests)
# hook probes: sudo, curl|sh, rm -rf on protected dirs, mv into protected dir, Write to protected path
# synthetic stdin JSON to .claude/hooks/pre_tool_guard.py for git-push-to-main / topic-branch / escape-hatch
```

Plus 5 subagents spawned against the migrated content: `artifact-librarian`,
`experiment-orchestrator`, `repo-doc-steward`, `branch-reporter`, `test-runner`.

## Findings

Classified per the old case-testing convention: **template gap** (new template lacks a
mechanism) / **validator/hook works as intended** / **case ledger debt** / **documentation
friction** / **migration-execution slip** (my own error, not the template's).

### F1 — Evidence-chain grading is stricter than the old boards.yaml, and it works (validator works as intended)

The old `memory/boards/claims.yaml` marked 4 claims `status: supported` /
`certainty: evidence-backed` on evidence that is really just clone/py_compile/dependency-import/
one CPU-forward-shape smoke. Migrated honestly under the new `grade: log < metric < ...` ladder,
that evidence doesn't clear the `supported` bar (needs `>= metric`), so all 4 were downgraded to
`status: partial`. Verified the check actually fires: temporarily flipped one claim back to
`supported` with only log-grade evidence — `validate-governance.py` correctly failed with
`overclaim：... 但最强证据低于 metric`; reverted immediately. **This is a genuine improvement
over the old schema**, which had no machine-enforced link between free-text `certainty` and a
graded evidence ladder.

### F2 — Nested vendored git repo + relative-path hook = self-locking failure (template gap, moderate severity)

Re-cloning the real `lillian039/ELF` into `lab/code/external/ELF` (its own `.git`) and then
`cd`-ing into it for a smoke test caused the shell's cwd to persist there across tool calls. The
`PreToolUse` hook is configured as a bare relative path (`python3 .claude/hooks/pre_tool_guard.py`
in `.claude/settings.json`), resolved against current cwd rather than an anchored repo root. Once
cwd was inside the nested repo (which has no `.claude/hooks/...`), **every subsequent Bash/Edit/Write
call failed closed** with a file-not-found hook error — including the very `cd ..`/`cd <worktree-root>`
commands that would have fixed it, since those commands never got to run (the hook errors before the
command body executes). Recovered only via `ExitWorktree(action=keep)` + `EnterWorktree(path=...)`,
tools not gated by this hook. This is a real, reproducible robustness gap: any workflow that vendors
or `cd`s into a nested git repository (a very normal thing to do) can wedge the whole session.
Suggested direction (not applied — test-first per scope): anchor the hook command to an absolute
path or a `$CLAUDE_PROJECT_DIR`-style variable instead of a bare relative path.

### F3 — same-commit gate is dirname-exact, not ancestor-aware (documented gap, low severity, by design)

`check-same-commit.py` only requires updating `<dirname(changed_file)>/ANATOMY.md`, not any
ancestor's. Confirmed both sides of this:
- **Missed**: adding many new files under a brand-new `lab/docs/` subtree (no ANATOMY.md anywhere
  under it) did **not** trigger a requirement to update `lab/ANATOMY.md`, even though `lab/` is a
  new *child* of a directory that owns an ANATOMY.md. Same for `lab/code/eval/`, `lab/code/external/`,
  and two-levels-deep additions under `lab/infra/launch/envs/` — none forced `lab/infra/ANATOMY.md`
  to update. I updated all of these anatomy files anyway (doctrine spirit), but the gate wouldn't
  have forced it.
- **Caught**: adding `memory/worktree-status.md` directly inside `memory/` (which does own an
  ANATOMY.md) correctly failed the gate until `memory/ANATOMY.md` was updated to list that file.
This is consistent with the tool's own documented conservative/low-false-positive design, not a bug,
but worth knowing precisely where the line is.

### F4 — `branch-reporter`'s own declared output wasn't in its directory's ANATOMY (documentation friction, now fixed)

`.claude/agents/branch-reporter.md` says it writes `memory/worktree-status.md`, but
`memory/ANATOMY.md`'s component list never mentioned that file (only `current-status.md`,
`session-tree.md`, `branches/`, etc.). Caught by F3's same-commit gate once branch-reporter actually
ran and staged the file. Fixed in this branch.

### F5 — no dedicated template plane for literature/reference or freeform research narrative (documentation friction)

The old template had first-class `reference/` (source cards, provenance, processing status) and
`research-artifact/` (problem statement, assumptions, contribution map, dead-ends, negative
results, unverified-claims staging) planes. The new template has no equivalent slot; per its own
"no generic `docs/`, nested `lab/docs/` for project-specific long docs" decision, these were folded
into `lab/docs/reference/` and `lab/docs/research-narrative/` — reasonable, but the new template
provides no explicit guidance pointing there for this specific content type (only implied by the
general docs/ decision in `DESIGN.md` §12). Similarly, old `memory/boards/{risks,actions,provenance,
source-visibility}.yaml` had no structured-YAML home in the new schema (only `claims`/`evidence`/
`experiment-ledger`/`regression-matrix`/`release-gates`); landed as plain markdown in `lab/docs/`,
which means they're outside `validate-governance.py`'s YAML/evidence-chain checks entirely.

### F6 — `lab/code/external/` (vendored third-party source) is an undocumented convention, inherited unresolved from the old template (case ledger debt, low severity)

The old audit (`lab/docs/audits/elf-template-case-report.md`) already flagged this exact gap
("a real external source case needs a documented convention for whether a nested upstream clone
belongs under `code/external/`, `reference/sources/`, or a worktree/submodule-like surface"). The
new template still has no opinion here either. I reused the old `code/external/ELF` convention
pragmatically (now `lab/code/external/ELF`, gitignored) and documented the choice in
`lab/code/ANATOMY.md`, but this remains an inherited, unresolved gap across both template
generations.

### F7 — `.vscode/` blanket gitignore silently drops a file the old repo intentionally tracked (behavior difference, not a bug)

Old repo tracked `code/.vscode/settings.json`. New template's root `.gitignore` has a blanket
`.vscode/` pattern (no path scoping), so the migrated `lab/code/.vscode/settings.json` is silently
untracked. Arguably a reasonable stricter default; noting it since it's a silent divergence a
migrator could miss.

### F8 — governance validators and hook floor otherwise work exactly as designed (positive)

- `validate-governance.py` / `check-agent-harness.py` / `check-anatomy-drift.py` /
  `check-same-commit.py`: all pass clean on the fully migrated + subagent-touched tree.
- Hook probes all behaved correctly: `sudo`, `curl|sh`, `rm -rf` on protected dirs, `mv`/`cp` into
  protected dirs, `Write`/`Edit` on protected paths (permission-deny layer) — all blocked. `git push`
  to `main`/`master` blocked without `CLAUDE_ALLOW_PUSH_MAIN=1`, allowed with it, and allowed
  unconditionally to a topic branch (tested via synthetic stdin JSON to the hook script directly,
  to avoid any real network push to the real remote — see F2's incident for why a live probe felt
  too risky to repeat for this specific case).
- The real `lillian039/ELF` (`pytorch_elf` @ `b29d8833609e9ab7f67cd9da39435ac5cea04837`) re-clone,
  fresh CPU-only dependency install, and tiny synthetic forward pass **exactly reproduced** the old
  audit's recorded shapes — `(2, 4, 8)` output / `(2, 4, 32)` decoder logits — independently, on a
  different machine, with different (newer, CPU-only) dependency versions. Strong reproducibility
  signal for both the upstream case and the migration's fidelity.
- 5 subagents (of 15 defined) behaved within their declared tool/boundary contracts: no deletions,
  no unauthorized promotions to `supported`/paper-claim, proposals instead of unilateral archiving,
  and — encouragingly — they coordinated coherently through shared files without being told to (
  experiment-orchestrator closed a cross-reference gap artifact-librarian had explicitly flagged for
  "the ledger owner").

### F9 — my own migration slips (not template bugs)

- First mechanical-copy pass missed `code/tests/{conftest.py,test_placeholder.py}`; caught during
  the pytest replay, fixed same session.
- First commit's message claimed all validators passed while the committed `current-status.md`
  table still said "not yet run" — caught by `branch-reporter`, fixed in the next commit.

## Coverage caveats (no silent claims of completeness)

- Only 5 of 15 subagents were exercised (artifact-librarian, experiment-orchestrator,
  repo-doc-steward, branch-reporter, test-runner). Not exercised: checkpoint-writer,
  experiment-monitor, feature-worker, hook-maker-agent, interactive-plan-writer, repo-researcher,
  session-boundary-agent, sub-agent-maker-agent, subagent-router-agent, workflow-recipe-harvester.
- No `.claude/skills/*` workflow was driven end-to-end as a skill invocation (this session used the
  underlying mechanisms directly — worktree, validators, subagents — rather than invoking e.g. the
  `/checkpoint` or `/pr-review` commands or the `worktree-pr-flow`/`experiment-workflow` skills via
  the Skill tool).
- No GPU, no dataset loading, no checkpoint loading, no training/generation loop, no metric
  reproduction was attempted for ELF — smoke-level only, matching both the old and new evidence
  records' explicit scope limits.
- Per the task scope, this pass is test-only: findings above are recorded, not fixed in the
  template itself (only migration-content and doc-sync fixes were made in this branch).

## Remaining debt

- F2 (hook path robustness) is the highest-value fix candidate if this branch's findings get acted
  on upstream.
- F5/F6 (no reference/research-narrative/external-vendor convention) would benefit from an explicit
  decision recorded in `DECISIONS.md`, one way or the other.
- Untested: checkpoint-writer, session-boundary-agent, and the skill-level entry points (commands,
  Skill-tool-driven workflows) — natural next slice if further test rounds are wanted.
