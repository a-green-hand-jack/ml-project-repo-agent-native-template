# adoption evals

Synthetic smoke tests for `scripts/adopt-existing-repo.py` (`run-adoption-smoke.py`).

Two fixtures, both build temporary Git repositories and drive `--phase all`:

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
   untouched (never moved, never overwritten) — see plan B4/B5.
