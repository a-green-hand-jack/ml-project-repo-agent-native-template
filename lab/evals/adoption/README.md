# adoption evals

Synthetic smoke tests for `scripts/adopt-existing-repo.py` (`run-adoption-smoke.py`).

All fixtures build temporary Git repositories and drive the adopter's phases. The
authoritative, per-review-round list of the 21 test cases lives in
`run-adoption-smoke.py`'s module docstring; the two anchor fixtures are:

1. `test_conservative_migration` — a clean fixture, asserts:
   - original tracked bytes are still present by content hash;
   - the discover-time per-entry classification (plan B1: `template_control_item` /
     `conservative_import` / `protected` / `conflict`) assigned the right bucket to
     each root entry, and each entry has a readable `target_path` + `reason`;
   - root project files are moved under `lab/code/imported/<slug>/` per that plan;
   - template governance passes after scaffold/normalize;
   - the original project test command can still run from the imported root.
2. `test_blocker_fixture` — a fixture with one `protected` root entry (a `checkpoints/`
   dir) and one `conflict` root entry (an import destination pre-seeded with unrelated
   content). Asserts blockers are not silently swallowed: `--phase all` exits non-zero,
   both blocked entries are named in the CLI output, `adoption-plan.json`'s
   `normalize_blockers` is non-empty, and the blocked entries are left byte-for-byte
   untouched (not moved, not overwritten) — see plan B4/B5.

The remaining cases are negative tests for review findings: nested/`.venv`-hidden
protected content, divergent control items, stale/tampered plans (`..`, escaping or
tampered `target_path`, forged category/blocker combinations), root entries added after
discover, and a non-control `src` entry forged to `template_control_item` after gaining
nested protected content. Both current-tree drift cases assert that normalize's full
preflight stops before any move or external write. Other cases cover symlinks at
protected / control-item / state-dir / state-leaf / conflict-archive positions. Canonical state
symlinks redirect to a deterministic `/tmp` location plus an explicit blocker;
pre-positioned symlinks at the fallback root, an absolute-path intermediate, or any
state leaf fail closed without touching their external targets. The suite also covers
over-long slugs and tracked files inside walk-excluded dirs vs the integrity proof's
"tracked ⇒ covered" contract.

## Residual risk (accepted)

The adopter's symlink and containment checks (`lstat` / `resolve`) and the writes
that follow them (`mkdir` / `copy2` / `move`) are **not atomic**. All of its
"refuses to write through / refuses to move" guarantees — and all of the
assertions in this smoke — hold under the assumption that the target repo is not
being concurrently and adversarially modified while a phase runs. Adoption is a
single-operator migration tool, not a defense against an attacker racing its
checks (TOCTOU); do not run it against a repo another process is mutating.
