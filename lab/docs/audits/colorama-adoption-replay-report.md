# Colorama adoption replay report

Date: 2026-07-12

## Case

- Source repo: `https://github.com/tartley/colorama`
- Replay clone: `/tmp/colorama-adoption-replay/Colorama`
- Source commit tested: `841634e` (`841634ed2a0da5d5ac2d867db533da8131266cb2`, 2026-05-13,
  shallow clone `--depth 1`)
- Template branch tested: `feat/12c-smoke-contract` (worktree
  `.claude/worktrees/12c-smoke-contract`)
- Feature under test: `scripts/adopt-existing-repo.py` `prove` phase +
  `scripts/check-adoption-integrity.py`, both updated with the runtime/smoke
  contract from `plans/20260712-bootstrap-adoption-proof.zh.md` (task tree C).

Colorama is a small, dependency-light Python package (ANSI terminal color
handling) with a `Makefile` `test:` target rather than a root `tests/`
directory or `pytest.ini`. It was chosen specifically because it is **not**
Agent-R1 (`lab/docs/audits/agent-r1-adoption-replay-report.md`, whose native
test command was undetectable) and because it exercises the
`detect_test_command()` `Makefile`-based detection path, giving this replay
a different native-test-command shape than the previous case.

## Commands

```bash
rm -rf /tmp/colorama-adoption-replay
mkdir -p /tmp/colorama-adoption-replay
git clone --depth 1 https://github.com/tartley/colorama.git \
  /tmp/colorama-adoption-replay/Colorama
git -C /tmp/colorama-adoption-replay/Colorama rev-parse --short HEAD

python scripts/adopt-existing-repo.py /tmp/colorama-adoption-replay/Colorama \
  --phase all \
  --policy conservative \
  --project-name colorama
echo "adopt exit: $?"

python scripts/check-adoption-integrity.py /tmp/colorama-adoption-replay/Colorama
echo "integrity exit: $?"

python scripts/check-adoption-integrity.py /tmp/colorama-adoption-replay/Colorama --json
```

## Results

`adopt-existing-repo.py --phase all` completed:

| Phase | Result |
| --- | --- |
| discover | `root_entries=23`, `conflicts=2` |
| baseline | `tracked_files=49` |
| scaffold | `copied=237`, `same=0`, `skipped=0` |
| normalize | `moved=21`, `blockers=0` |
| prove | `integrity=ok`, `governance_rc=1`, `smoke=fail` |

Process exit code: **`0`** (adoption's own integrity was `ok`; the smoke
result being `fail` does **not** flip this exit code -- decided, open
question 5).

Integrity checker:

```text
[check-adoption-integrity] OK -- present 49/49
SMOKE WARNING original_test: result=fail reason=command exited with returncode 2
```

Exit code: **`0`**.

`--json` output:

```json
{
  "baseline_files": 49,
  "ok": true,
  "present": 49,
  "schema": "template-adoption-integrity-v1",
  "smoke_warnings": [
    {
      "item": "original_test",
      "reason": "command exited with returncode 2",
      "result": "fail"
    }
  ],
  "unresolved_blockers": []
}
```

Generated target report:

```text
lab/docs/audits/template-adoption-report.md
```

Key target report facts (new C-part smoke/warning fields):

- `integrity`: `ok`
- `baseline_files_present`: `49/49`
- `moved_root_entries`: `21`
- `normalize_blockers`: `0`
- `remaining_root_pollution`: `0`
- `smoke_result`: `fail`
- smoke `command_source`: `auto-detected` (via `Makefile` `test:` target --
  the alternative detection path to Agent-R1's undetected case)
- smoke `command`: `make test`
- smoke `unverified_reason`: `command exited with returncode 2`
- `warnings`: one explicit entry -- `original_test: result=fail
  reason="command exited with returncode 2"`

The native `make test` command failed because Colorama's `Makefile` invokes
a project-managed virtualenv interpreter (`~/.virtualenvs/colorama/bin/python`)
that only exists after running `make bootstrap`; the conservative adoption
tool does not install target-repo dependencies or provision virtualenvs
(explicitly out of scope, see plan doc "非目标"). This is exactly the
"detected but failed" smoke state the contract exists to make visible rather
than silently swallow.

`governance_returncode: 1` inside the adopted target repo is a **known,
separate** limitation: `adopt-existing-repo.py` copies the template control
plane (including `.claude/**`) but does not itself run
`scripts/sync-codex-adapters.py` inside the target repo (that is a bootstrap
concern, `scripts/bootstrap-project.py`, not an adoption concern), so the
target repo's `.codex/agents/*.toml` / `.agents/skills/*` are stale relative
to its freshly-copied `.claude/**` until a human runs
`sync-codex-adapters.py` there. This is orthogonal to the C-part
runtime/smoke contract under test here (tracked-byte integrity was `ok`) and
is out of scope for this replay; noted here only for completeness/honesty,
consistent with this plan's "不猜测、不吞掉负面结果" doctrine.

## Normalized Layout

The original Colorama root content was moved under:

```text
lab/code/imported/colorama/
```

Moved root entries:

- `CHANGELOG.rst`
- `ENTERPRISE.md`
- `LICENSE.txt`
- `Makefile`
- `README-hacking.md`
- `README.rst`
- `SECURITY.md`
- `bootstrap.ps1`
- `build.ps1`
- `clean.ps1`
- `colorama` (the package, including its own nested `colorama/tests/*_test.py`)
- `demos`
- `pyproject.toml`
- `release.ps1`
- `requirements-dev.txt`
- `requirements.txt`
- `screenshots`
- `test-release`
- `test-release.ps1`
- `test.ps1`
- `tox.ini`

No conflicting root files needed preserving this time (`human/imported/adoption-conflicts/`
was not populated) and there were zero unresolved normalize blockers.

## Findings

### C4-1: Smoke contract holds end-to-end on a real repo with a detectable-but-broken native command

This is the first real-repo replay where a native test command **is**
detected (`make test`, `command_source=auto-detected`) but genuinely fails
when run without prior environment setup. The contract worked exactly as
designed: `prove` and `check-adoption-integrity.py` both stayed exit `0`
(adoption's own tracked-byte integrity was intact), while the report and
`--json` output both carried an explicit, non-empty, machine-readable
warning naming the failed item and the reason. Nothing was silently dropped
or misrepresented as a pass.

### C4-2: Detection-type diversity vs. Agent-R1

Agent-R1 (`agent-r1-adoption-replay-report.md`) had no detectable native
test command at all (`original_test_returncode: None`, pre-C-part schema).
Colorama exercises the other branch of `detect_test_command()` (`Makefile`
`test:` regex match) and produces a `fail` result with a concrete
returncode/reason, rather than a `skipped`/undetected state. Together the
two replays now cover three of the four smoke-contract `result` states in
real-world evidence: `skipped` (Agent-R1, pre-dating the new schema but
structurally equivalent to today's undetected case), `fail` (this replay).
`pass` and `unknown` remain covered by the synthetic negative fixtures in
`lab/evals/adoption/run-adoption-smoke.py` (which also cover the same
`skipped` and `fail` states plus the blocked-normalize integrity-failure
case), not yet by a real-repo replay.

### C4-3: Blocker/integrity layer stayed silent (as expected) for this case

Colorama had zero protected-path or destination-conflict blockers, so this
replay does not exercise the `unresolved_blockers`-driven non-zero-exit path
of `check-adoption-integrity.py`; that path is covered by the
`scenario_blocked_normalize` synthetic fixture instead (deliberately, since
constructing a real public repo that hits `lab/data/**`-style protected
paths or destination collisions is neither realistic nor necessary here).

## Follow-ups

- If a future replay is done against a repo that already has `pytest`
  installed in the execution environment (this replay's environment lacks
  it), it would additionally exercise the `pytest.ini`/`tests/`-directory
  detection branch with a real `pass` result end-to-end.
- Consider (out of scope for this plan) whether `adopt-existing-repo.py`
  should offer an opt-in flag to also run `sync-codex-adapters.py` inside
  the target repo during `scaffold`, to avoid the `governance_returncode: 1`
  noted above; left as a `bootstrap-project.py`-vs-`adopt-existing-repo.py`
  boundary question for a later increment, not blocking for this plan's
  smoke-contract scope.
