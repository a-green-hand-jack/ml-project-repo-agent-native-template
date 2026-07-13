#!/usr/bin/env python3
"""Synthetic smoke test for adopt-existing-repo.

Fixtures (plan B5, plans/20260712-bootstrap-adoption-proof.zh.md):

1. `test_conservative_migration`: a clean fixture that exercises all of
   `--phase all` and asserts the discover-time classification plan
   (plan B1) assigned the right bucket to each root entry — template
   control item / conservative import — and that `normalize` acted on it
   correctly (no blockers, everything landed where classification said it
   would).
2. `test_blocker_fixture`: a fixture with one `protected` root entry and
   one `conflict` root entry (pre-seeded import destination). Asserts
   `normalize`/`--phase all` does *not* silently continue past blockers
   (non-zero exit, blocked entries stay exactly where they started, and
   the blockers are readable in `phase-log.jsonl`/`adoption-plan.json`).
3. `test_nested_protected_fixture` (review BLOCKER-1): nested protected
   content (`src/checkpoints/**`, target's own `lab/data/**`) must block
   the whole entry — including the control-item-named `lab`, which
   scaffold must not write into or stash from.
4. `test_control_item_divergence` (review MAJOR-2): a same-named
   control-item file whose hash differs from the template is a conflict
   blocker (plan B1), not silently reconciled.
5. `test_stale_plan_rejected` (review MAJOR-3): normalize re-verifies the
   tree and refuses stale/tampered persisted plans (protected content
   appearing after discover; unknown categories).
6. `test_excluded_dir_protected_content` (review round 2 BLOCKER-A): the
   protection-boundary scan must not reuse performance dir exclusions —
   `src/.venv/**/checkpoints/model.bin` must still block `src` wholesale.
7. `test_target_path_escape_rejected` (review round 2 BLOCKER-B): a
   tampered plan `target_path` (`../escape`, absolute) is rejected;
   nothing is ever moved outside the target repo.
8. `test_protected_symlink_blocked` (review round 2 BLOCKER-C): a symlink
   at a protected position (`lab/data` -> external dir) or a control-item
   position (`memory` -> external dir) is a blocker; scaffold never writes
   through it and the external tree stays untouched.
9. `test_tampered_category_blocker_rejected` (review round 2 MAJOR-D):
   `protected`/`conflict` entries whose blocker flag was tampered to
   false are rejected by the category/blocker invariant, not moved.
10. `test_non_root_entry_path_rejected` (review rounds 2+3 MAJOR-D): plan
    paths with separators (nested files), naming nonexistent root
    entries, or '..' (which passes `Path(name).name == name`!) are
    rejected; no partial moves, nothing outside the repo is touched.
11. `test_state_dir_symlink_redirected` (review round 3 BLOCKER-C): the
    target's `lab` is a symlink to an external tree — discover/baseline
    must not write plan/log/baseline through it; state goes to the /tmp
    fallback and the redirect is itself a blocker (non-zero exit).
12. `test_state_docs_symlink_redirected` (review round 3 BLOCKER-C): same
    as 11 but with a real `lab` and a symlinked `lab/docs` — an
    intermediate segment on the state path must be caught too.
13. `test_archive_path_symlink_refused` (review round 3 BLOCKER-C): the
    target's `human/imported` is a symlink to an external tree — the
    conflict archive must refuse to stash through it (blocker), the
    existing divergent file is neither stashed nor overwritten, and the
    external tree stays untouched.
14. `test_long_slug_truncated` (review round 3 MAJOR): a 300-char
    `--project-name` must not ENAMETOOLONG at normalize's mkdir —
    `project_slug` caps the slug (hash-suffixed) and `--phase all`
    completes cleanly.
15. `test_tracked_file_in_excluded_dir_integrity` (review round 3 MAJOR):
    a *tracked* file under a `.venv`-named dir is in the baseline
    (`git ls-files` collects everything), so the integrity proof's hash
    index must find it after the move — no false "missing" from pruned
    walk dirs.
16. `test_state_leaf_symlinks_redirected` (fresh review BLOCKER): each
    canonical state leaf (`adoption-plan.json`, `baseline.json`,
    `phase-log.jsonl`) is part of the redirect decision; no leaf symlink is
    followed.
17. `test_fallback_root_symlink_refused` (fresh review BLOCKER): a
    pre-positioned symlink at deterministic fallback root fails closed and
    leaves its external target untouched.
18. `test_fallback_intermediate_symlink_refused` (fresh review BLOCKER):
    the fallback's absolute lstat walk catches an intermediate symlink
    supplied through `TMPDIR`, before creating the deterministic root.
19. `test_fallback_leaf_symlinks_refused` (fresh review BLOCKER): each
    pre-positioned fallback state leaf fails closed rather than being read
    or written through.
20. `test_unplanned_root_entry_rejected` (fresh review MAJOR): a protected
    root entry added after discover (`checkpoints/model.bin`) is absent from
    the persisted classification and must block the complete normalize
    preflight before any otherwise-safe entry moves.
21. `test_forged_template_control_item_rejected` (fresh review MAJOR): a
    persisted `src` row forged to `template_control_item, blocker=false`
    cannot skip current protection scanning and hide
    `src/checkpoints/model.bin`; normalize fails before any move.

The six `test_smoke_contract_*` cases preserve part C's structured smoke
contract after the semantic-classification merge: protected/conflict blockers,
real test failure, undetected tests, timeout/unknown, and legacy-state rejection.

If no writable temp directory is available (sandboxes without /tmp), the
whole smoke prints an explicit SKIP and exits 0 instead of crashing.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
ADOPTER = REPO / "scripts" / "adopt-existing-repo.py"
INTEGRITY = REPO / "scripts" / "check-adoption-integrity.py"


def run(
    cmd: list[str],
    cwd: Path,
    *,
    check: bool = True,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, check=False, env=env)
    if check and proc.returncode != 0:
        print("$ " + " ".join(cmd))
        print(proc.stdout)
        print(proc.stderr)
        raise SystemExit(proc.returncode)
    return proc


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def git_init(target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    run(["git", "init"], target)
    run(["git", "config", "user.email", "adoption@example.test"], target)
    run(["git", "config", "user.name", "Adoption Test"], target)


def read_plan(target: Path) -> dict:
    path = target / "lab" / "docs" / "audits" / "template-adoption" / "state" / "adoption-plan.json"
    return json.loads(path.read_text(encoding="utf-8"))


def state_fallback(target: Path) -> Path:
    """Mirror of the adopter's `state_fallback_root` formula (review round
    3 BLOCKER-C): deterministic /tmp location state is redirected to when
    the canonical state dir path crosses a symlink."""
    digest = hashlib.sha256(str(target.resolve()).encode("utf-8")).hexdigest()[:12]
    return Path(tempfile.gettempdir()) / f"template-adoption-state-{digest}"


def fallback_at(target: Path, temp_root: Path) -> Path:
    digest = hashlib.sha256(str(target.resolve()).encode("utf-8")).hexdigest()[:12]
    return temp_root / f"template-adoption-state-{digest}"


def remove_path(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.exists():
        shutil.rmtree(path)


def classification_by_path(plan: dict) -> dict[str, dict]:
    return {e["path"]: e for e in plan["classification"]}


def make_conservative_fixture(root: Path) -> Path:
    target = root / "sample-existing"
    git_init(target)
    # README.md identical to the template's: plan B1 says a control item is
    # only "left in place" when its hash matches the template (review
    # MAJOR-2); a divergent README is a conflict blocker and is covered by
    # test_control_item_divergence instead.
    write(target / "README.md", (REPO / "README.md").read_text(encoding="utf-8"))
    write(
        target / "pyproject.toml",
        "[project]\nname = \"sample-existing\"\nversion = \"0.0.1\"\n",
    )
    write(
        target / "src" / "sample_existing.py",
        "def answer():\n    return 42\n",
    )
    write(
        target / "tests" / "test_sample.py",
        "import sys\n"
        "import unittest\n"
        "from pathlib import Path\n"
        "sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))\n"
        "import sample_existing\n\n"
        "class SampleTest(unittest.TestCase):\n"
        "    def test_answer(self):\n"
        "        self.assertEqual(sample_existing.answer(), 42)\n",
    )
    run(["git", "add", "."], target)
    run(["git", "commit", "-m", "initial"], target)
    return target


def test_conservative_migration(root: Path) -> None:
    target = make_conservative_fixture(root)
    cmd = [
        sys.executable,
        str(ADOPTER),
        str(target),
        "--phase",
        "all",
        "--test-command",
        "python -m unittest discover -s tests",
        "--project-name",
        "sample-existing",
    ]
    run(cmd, REPO)
    run([sys.executable, str(INTEGRITY), str(target)], REPO)

    # B1: per-entry classification must have landed the expected bucket
    # for each root entry — this is the thing this fixture is actually
    # here to prove, not just the final file layout.
    plan = read_plan(target)
    by_path = classification_by_path(plan)
    expected_categories = {
        "README.md": "template_control_item",
        "pyproject.toml": "conservative_import",
        "src": "conservative_import",
        "tests": "conservative_import",
    }
    mismatches = [
        f"{path}: expected {expected}, got {by_path.get(path, {}).get('category')}"
        for path, expected in expected_categories.items()
        if by_path.get(path, {}).get("category") != expected
    ]
    if mismatches:
        raise SystemExit("classification mismatch: " + "; ".join(mismatches))
    for path in expected_categories:
        entry = by_path[path]
        if not entry.get("target_path") or not entry.get("reason"):
            raise SystemExit(f"classification entry missing target_path/reason: {path} -> {entry}")
        if entry["blocker"]:
            raise SystemExit(f"unexpected blocker on non-blocking entry: {path} -> {entry}")

    imported = target / "lab" / "code" / "imported" / "sample-existing"
    expected_paths = [
        imported / "src" / "sample_existing.py",
        imported / "tests" / "test_sample.py",
        imported / "pyproject.toml",
        target / "lab" / "docs" / "audits" / "template-adoption-report.md",
    ]
    missing = [p for p in expected_paths if not p.exists()]
    if missing:
        raise SystemExit("missing expected path(s): " + ", ".join(str(p) for p in missing))
    root_names = {p.name for p in target.iterdir()}
    polluted = {"src", "tests", "pyproject.toml"} & root_names
    if polluted:
        raise SystemExit(f"root pollution remained: {sorted(polluted)}")
    if not (target / "README.md").exists():
        raise SystemExit("hash-matching README.md must stay at root")
    if (target / "human" / "imported" / "adoption-conflicts" / "README.md").exists():
        raise SystemExit("hash-matching README.md must not be stashed into adoption-conflicts")
    report = (target / "lab" / "docs" / "audits" / "template-adoption-report.md").read_text(
        encoding="utf-8"
    )
    if "smoke_result: `pass`" not in report or "No warnings." not in report:
        raise SystemExit("clean semantic migration must retain the part C pass/no-warning contract")
    integrity_json = run([sys.executable, str(INTEGRITY), str(target), "--json"], REPO)
    if json.loads(integrity_json.stdout).get("smoke_warnings"):
        raise SystemExit("clean semantic migration unexpectedly emitted smoke warnings")
    print("[adoption-smoke] test_conservative_migration OK")


def make_blocker_fixture(root: Path) -> Path:
    target = root / "blocker-existing"
    git_init(target)
    write(target / "README.md", "# Blocker Existing Repo\n")
    # protected: a root-level dir matching PROTECTED_PARTS.
    write(target / "checkpoints" / "model.bin", "not-a-real-checkpoint\n")
    # conflict: intended import destination pre-seeded with unrelated content.
    write(target / "extra" / "seed.txt", "new content from the adopted repo\n")
    write(
        target / "lab" / "code" / "imported" / "blocker-existing" / "extra" / "seed.txt",
        "pre-existing content already at the import destination\n",
    )
    run(["git", "add", "."], target)
    run(["git", "commit", "-m", "initial"], target)
    return target


def test_blocker_fixture(root: Path) -> None:
    target = make_blocker_fixture(root)
    cmd = [
        sys.executable,
        str(ADOPTER),
        str(target),
        "--phase",
        "all",
        "--test-command",
        "none",
        "--project-name",
        "blocker-existing",
    ]
    proc = run(cmd, REPO, check=False)
    if proc.returncode == 0:
        raise SystemExit(
            "blocked normalize should not silently succeed (exit 0) — "
            f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )
    combined = proc.stdout + proc.stderr
    if "checkpoints" not in combined or "extra" not in combined:
        raise SystemExit(
            "blocker output did not mention both blocked entries — "
            f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )

    plan = read_plan(target)
    by_path = classification_by_path(plan)
    if by_path.get("checkpoints", {}).get("category") != "protected":
        raise SystemExit(f"'checkpoints' should classify as protected, got: {by_path.get('checkpoints')}")
    if not by_path["checkpoints"]["blocker"]:
        raise SystemExit("'checkpoints' classification should be a blocker")
    if by_path.get("extra", {}).get("category") != "conflict":
        raise SystemExit(f"'extra' should classify as conflict, got: {by_path.get('extra')}")
    if not by_path["extra"]["blocker"]:
        raise SystemExit("'extra' classification should be a blocker")
    if not plan.get("normalize_blockers"):
        raise SystemExit("discover-time plan.json should predict normalize_blockers, got none")

    # Blocked entries must not have been silently moved — they stay
    # exactly where they started.
    if not (target / "checkpoints" / "model.bin").exists():
        raise SystemExit("protected 'checkpoints/model.bin' must not be moved/deleted")
    if not (target / "extra" / "seed.txt").exists():
        raise SystemExit("conflicting 'extra/seed.txt' must not be moved/deleted")
    pre_existing = target / "lab" / "code" / "imported" / "blocker-existing" / "extra" / "seed.txt"
    if pre_existing.read_text(encoding="utf-8") != "pre-existing content already at the import destination\n":
        raise SystemExit("pre-existing conflicting import destination content must not be overwritten")

    print("[adoption-smoke] test_blocker_fixture OK")


def make_nested_protected_fixture(root: Path) -> Path:
    target = root / "nested-protected"
    git_init(target)
    write(target / "README.md", (REPO / "README.md").read_text(encoding="utf-8"))
    # BLOCKER-1 case A: a plain directory whose *nested* content is protected.
    write(target / "src" / "main.py", "print('hi')\n")
    write(target / "src" / "checkpoints" / "model.bin", "fake-model-bytes\n")
    # BLOCKER-1 case B: a directory sharing its name with a template control
    # directory (`lab`) but holding the target's own protected data.
    write(target / "lab" / "notes.md", "# lab notes owned by the target repo\n")
    write(target / "lab" / "data" / "dataset.csv", "a,b\n1,2\n")
    run(["git", "add", "."], target)
    run(["git", "commit", "-m", "initial"], target)
    return target


def test_nested_protected_fixture(root: Path) -> None:
    """Review BLOCKER-1 negative test: nested protected content must make
    the WHOLE root entry a `protected` blocker — no partial moves, and
    scaffold must not write template files into (or stash files out of) a
    control-item-named directory that holds protected content."""
    target = make_nested_protected_fixture(root)
    cmd = [
        sys.executable,
        str(ADOPTER),
        str(target),
        "--phase",
        "all",
        "--test-command",
        "none",
        "--project-name",
        "nested-protected",
    ]
    proc = run(cmd, REPO, check=False)
    if proc.returncode == 0:
        raise SystemExit(
            "nested protected content must block the pipeline (non-zero exit) — "
            f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )

    plan = read_plan(target)
    by_path = classification_by_path(plan)
    for name in ("src", "lab"):
        entry = by_path.get(name, {})
        if entry.get("category") != "protected" or not entry.get("blocker"):
            raise SystemExit(f"'{name}' should classify as a protected blocker, got: {entry}")

    # Protected entries stay exactly where they started — whole entry, no
    # partial move.
    for rel in ("src/checkpoints/model.bin", "src/main.py", "lab/data/dataset.csv", "lab/notes.md"):
        if not (target / rel).exists():
            raise SystemExit(f"content of a protected entry moved or lost: {rel}")
    if (target / "lab" / "code" / "imported" / "nested-protected" / "src").exists():
        raise SystemExit("'src' must not be imported while it contains protected content")

    # scaffold must have skipped the `lab` control item entirely: no
    # template files written into the target's lab/, nothing stashed away.
    if (target / "lab" / "AGENTS.md").exists():
        raise SystemExit("scaffold wrote template files into a lab/ holding protected content")
    if (target / "human" / "imported" / "adoption-conflicts" / "lab").exists():
        raise SystemExit("scaffold stashed files out of a protected lab/ entry")
    print("[adoption-smoke] test_nested_protected_fixture OK")


DIVERGENT_README = "# Project With Its Own README\n\nNot the template's content.\n"


def make_divergent_readme_fixture(root: Path) -> Path:
    target = root / "divergent-readme"
    git_init(target)
    write(target / "README.md", DIVERGENT_README)
    write(target / "src" / "app.py", "APP = True\n")
    run(["git", "add", "."], target)
    run(["git", "commit", "-m", "initial"], target)
    return target


def test_control_item_divergence(root: Path) -> None:
    """Review MAJOR-2 negative test: plan B1 says a same-named control-item
    file is `template_control_item` only when its hash matches the
    template; divergent content is a `conflict` blocker — left untouched
    at root, never stashed into human/imported/adoption-conflicts/ with
    the template's version installed over it."""
    target = make_divergent_readme_fixture(root)
    cmd = [
        sys.executable,
        str(ADOPTER),
        str(target),
        "--phase",
        "all",
        "--test-command",
        "none",
        "--project-name",
        "divergent-readme",
    ]
    proc = run(cmd, REPO, check=False)
    if proc.returncode == 0:
        raise SystemExit(
            "divergent control-item file must block the pipeline (non-zero exit) — "
            f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )

    plan = read_plan(target)
    entry = classification_by_path(plan).get("README.md", {})
    if entry.get("category") != "conflict" or not entry.get("blocker"):
        raise SystemExit(f"divergent README.md should classify as a conflict blocker, got: {entry}")
    if (target / "README.md").read_text(encoding="utf-8") != DIVERGENT_README:
        raise SystemExit("divergent README.md must stay untouched at root (not replaced by template)")
    if (target / "human" / "imported" / "adoption-conflicts" / "README.md").exists():
        raise SystemExit("divergent README.md must not be stashed into adoption-conflicts")
    print("[adoption-smoke] test_control_item_divergence OK")


def test_stale_plan_rejected(root: Path) -> None:
    """Review MAJOR-3 negative test: normalize must re-verify safety
    invariants against the current tree instead of trusting the persisted
    plan — an entry that gained protected content after discover must not
    be moved, and an entry whose persisted category is not one of the four
    known buckets must be refused."""
    target = make_conservative_fixture(root)
    base_cmd = [
        sys.executable,
        str(ADOPTER),
        str(target),
        "--test-command",
        "none",
        "--project-name",
        "stale-plan",
    ]
    run(base_cmd + ["--phase", "discover"], REPO)

    # Tree drift after discover: src/ gains protected content.
    write(target / "src" / "checkpoints" / "late.bin", "appeared-after-discover\n")
    # Plan drift: tamper 'tests' into an unknown category.
    plan_path = target / "lab" / "docs" / "audits" / "template-adoption" / "state" / "adoption-plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    for entry in plan["classification"]:
        if entry["path"] == "tests":
            entry["category"] = "mystery_bucket"
    plan_path.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    proc = run(base_cmd + ["--phase", "normalize"], REPO, check=False)
    if proc.returncode == 0:
        raise SystemExit(
            "normalize must reject a stale/tampered plan (non-zero exit) — "
            f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )
    combined = proc.stdout + proc.stderr
    if "src" not in combined or "mystery_bucket" not in combined:
        raise SystemExit(
            "stale-plan blockers did not mention both rejected entries — "
            f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )
    if not (target / "src" / "checkpoints" / "late.bin").exists():
        raise SystemExit("'src' moved despite protected content appearing after discover")
    if not (target / "src" / "sample_existing.py").exists():
        raise SystemExit("'src' was partially moved despite the whole-entry blocker")
    if not (target / "tests" / "test_sample.py").exists():
        raise SystemExit("unknown-category entry 'tests' must not be moved")
    print("[adoption-smoke] test_stale_plan_rejected OK")


def test_unplanned_root_entry_rejected(root: Path) -> None:
    """Fresh-review MAJOR: normalize must validate complete current-root
    coverage, not only the rows persisted by discover."""
    target = make_conservative_fixture(root)
    external = root / "unplanned-external"
    write(external / "sentinel.txt", "must stay unchanged\n")
    base_cmd = [
        sys.executable,
        str(ADOPTER),
        str(target),
        "--test-command",
        "none",
        "--project-name",
        "unplanned-root",
    ]
    run(base_cmd + ["--phase", "discover"], REPO)
    write(target / "checkpoints" / "model.bin", "appeared-after-discover\n")

    proc = run(base_cmd + ["--phase", "normalize"], REPO, check=False)
    if proc.returncode == 0:
        raise SystemExit(
            "an unplanned protected root entry must block normalize (non-zero exit) — "
            f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )
    combined = proc.stdout + proc.stderr
    if "checkpoints" not in combined or "not recorded by discover" not in combined or "protected" not in combined:
        raise SystemExit(
            "unplanned-root blocker must name the entry, missing plan coverage, and protection — "
            f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )
    for rel in (
        "checkpoints/model.bin",
        "pyproject.toml",
        "src/sample_existing.py",
        "tests/test_sample.py",
    ):
        if not (target / rel).exists():
            raise SystemExit(f"normalize moved content before completing its blocked preflight: {rel}")
    if (target / "lab" / "code" / "imported" / "unplanned-root").exists():
        raise SystemExit("normalize created an import tree despite the unplanned-root blocker")
    if sorted(p.relative_to(external).as_posix() for p in external.rglob("*")) != ["sentinel.txt"]:
        raise SystemExit("normalize wrote outside the target repo in the unplanned-root case")
    if (external / "sentinel.txt").read_text(encoding="utf-8") != "must stay unchanged\n":
        raise SystemExit("normalize changed external bytes in the unplanned-root case")

    log_path = target / "lab" / "docs" / "audits" / "template-adoption" / "state" / "phase-log.jsonl"
    rows = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line]
    normalize_rows = [row for row in rows if row.get("phase") == "normalize"]
    if not normalize_rows or normalize_rows[-1].get("status") != "blocked":
        raise SystemExit("unplanned-root blocker was not recorded as a blocked normalize phase")
    if not any("checkpoints" in blocker for blocker in normalize_rows[-1]["details"]["blockers"]):
        raise SystemExit("unplanned-root blocker was not readable in phase-log.jsonl")
    print("[adoption-smoke] test_unplanned_root_entry_rejected OK")


def test_forged_template_control_item_rejected(root: Path) -> None:
    """Fresh-review MAJOR: a forged template-control category must not skip
    current-state protection scanning or authorize a non-CONTROL_ITEM."""
    target = make_conservative_fixture(root)
    external = root / "forged-control-external"
    write(external / "sentinel.txt", "must stay unchanged\n")
    base_cmd = [
        sys.executable,
        str(ADOPTER),
        str(target),
        "--test-command",
        "none",
        "--project-name",
        "forged-control",
    ]
    run(base_cmd + ["--phase", "discover"], REPO)
    write(target / "src" / "checkpoints" / "model.bin", "hidden-after-discover\n")
    plan_path = target / "lab" / "docs" / "audits" / "template-adoption" / "state" / "adoption-plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    for entry in plan["classification"]:
        if entry["path"] == "src":
            entry["category"] = "template_control_item"
            entry["blocker"] = False
            entry["target_path"] = "src"
            entry["reason"] = "forged control-item authorization"
    plan_path.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    proc = run(base_cmd + ["--phase", "normalize"], REPO, check=False)
    if proc.returncode == 0:
        raise SystemExit(
            "forged template_control_item classification must block normalize — "
            f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )
    combined = proc.stdout + proc.stderr
    if (
        "src" not in combined
        or "template_control_item" not in combined
        or "actual CONTROL_ITEMS" not in combined
        or "src/checkpoints" not in combined
    ):
        raise SystemExit(
            "forged-control blocker must name the forged category and current protected hit — "
            f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )
    for rel in (
        "src/sample_existing.py",
        "src/checkpoints/model.bin",
        "pyproject.toml",
        "tests/test_sample.py",
    ):
        if not (target / rel).exists():
            raise SystemExit(f"normalize moved content before completing forged-control preflight: {rel}")
    if (target / "lab" / "code" / "imported" / "forged-control").exists():
        raise SystemExit("normalize created an import tree despite the forged-control blocker")
    if sorted(p.relative_to(external).as_posix() for p in external.rglob("*")) != ["sentinel.txt"]:
        raise SystemExit("normalize wrote outside the target repo in the forged-control case")
    if (external / "sentinel.txt").read_text(encoding="utf-8") != "must stay unchanged\n":
        raise SystemExit("normalize changed external bytes in the forged-control case")

    log_path = target / "lab" / "docs" / "audits" / "template-adoption" / "state" / "phase-log.jsonl"
    rows = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line]
    normalize_rows = [row for row in rows if row.get("phase") == "normalize"]
    if not normalize_rows or normalize_rows[-1].get("status") != "blocked":
        raise SystemExit("forged-control blocker was not recorded as a blocked normalize phase")
    if not any("src/checkpoints" in blocker for blocker in normalize_rows[-1]["details"]["blockers"]):
        raise SystemExit("current protected hit was not readable in the forged-control phase log")
    print("[adoption-smoke] test_forged_template_control_item_rejected OK")


def test_excluded_dir_protected_content(root: Path) -> None:
    """Review round 2 BLOCKER-A negative test: protected content nested
    inside a directory that the *performance* walks exclude (`.venv`,
    `__pycache__`, ...) must still be found by the protection-boundary
    scan — otherwise the whole entry gets moved with the checkpoint in it."""
    target = root / "venv-protected"
    git_init(target)
    write(target / "README.md", (REPO / "README.md").read_text(encoding="utf-8"))
    write(target / "src" / "main.py", "print('hi')\n")
    write(target / "src" / ".venv" / "lib" / "checkpoints" / "model.bin", "fake-model-bytes\n")
    run(["git", "add", "."], target)
    run(["git", "commit", "-m", "initial"], target)
    cmd = [
        sys.executable,
        str(ADOPTER),
        str(target),
        "--phase",
        "all",
        "--test-command",
        "none",
        "--project-name",
        "venv-protected",
    ]
    proc = run(cmd, REPO, check=False)
    if proc.returncode == 0:
        raise SystemExit(
            "protected content inside an excluded dir name (.venv) must block — "
            f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )
    plan = read_plan(target)
    entry = classification_by_path(plan).get("src", {})
    if entry.get("category") != "protected" or not entry.get("blocker"):
        raise SystemExit(f"'src' should classify as a protected blocker, got: {entry}")
    if "src/.venv/lib/checkpoints" not in entry.get("reason", ""):
        raise SystemExit(f"protected reason should name the nested hit path, got: {entry.get('reason')}")
    for rel in ("src/main.py", "src/.venv/lib/checkpoints/model.bin"):
        if not (target / rel).exists():
            raise SystemExit(f"content of a protected entry moved or lost: {rel}")
    if (target / "lab" / "code" / "imported" / "venv-protected" / "src").exists():
        raise SystemExit("'src' must not be imported while .venv-nested protected content exists")
    print("[adoption-smoke] test_excluded_dir_protected_content OK")


def test_target_path_escape_rejected(root: Path) -> None:
    """Review round 2 BLOCKER-B negative test: normalize must reject a
    stale/tampered target_path (`../escape`, absolute) — target_path is
    only accepted when it exactly equals the import path derived from the
    entry name, and it must resolve inside the target repo."""
    target = make_conservative_fixture(root)
    base_cmd = [
        sys.executable,
        str(ADOPTER),
        str(target),
        "--test-command",
        "none",
        "--project-name",
        "escape-target",
    ]
    run(base_cmd + ["--phase", "discover"], REPO)
    plan_path = target / "lab" / "docs" / "audits" / "template-adoption" / "state" / "adoption-plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    abs_escape = root / "abs-escaped-tests"
    for entry in plan["classification"]:
        if entry["path"] == "src":
            entry["target_path"] = "../escaped-src"
        if entry["path"] == "tests":
            entry["target_path"] = str(abs_escape)
    plan_path.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    proc = run(base_cmd + ["--phase", "normalize"], REPO, check=False)
    if proc.returncode == 0:
        raise SystemExit(
            "normalize must reject escaping target_path values (non-zero exit) — "
            f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )
    combined = proc.stdout + proc.stderr
    if "../escaped-src" not in combined or str(abs_escape) not in combined:
        raise SystemExit(
            "escape blockers did not mention both tampered target_paths — "
            f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )
    if (root / "escaped-src").exists() or (target.parent / "escaped-src").exists():
        raise SystemExit("entry escaped the target repo via relative target_path")
    if abs_escape.exists():
        raise SystemExit("entry escaped the target repo via absolute target_path")
    for rel in ("src/sample_existing.py", "tests/test_sample.py"):
        if not (target / rel).exists():
            raise SystemExit(f"entry with tampered target_path must stay put: {rel}")
    print("[adoption-smoke] test_target_path_escape_rejected OK")


def test_protected_symlink_blocked(root: Path) -> None:
    """Review round 2 BLOCKER-C negative test: a symlink at a protected
    position (target's `lab/data` -> external dir) or at a control-item
    position (`memory` -> external dir) must be a blocker — never
    dereferenced, never written through by scaffold, external bytes
    untouched."""
    external_data = root / "external-data"
    write(external_data / "raw.csv", "a,b\n1,2\n")
    external_memory = root / "external-memory"
    write(external_memory / "notes.md", "external notes\n")
    target = root / "symlinked-protected"
    git_init(target)
    write(target / "README.md", (REPO / "README.md").read_text(encoding="utf-8"))
    write(target / "lab" / "notes.md", "# lab notes owned by the target repo\n")
    (target / "lab" / "data").symlink_to(external_data, target_is_directory=True)
    (target / "memory").symlink_to(external_memory, target_is_directory=True)
    run(["git", "add", "."], target)
    run(["git", "commit", "-m", "initial"], target)
    cmd = [
        sys.executable,
        str(ADOPTER),
        str(target),
        "--phase",
        "all",
        "--test-command",
        "none",
        "--project-name",
        "symlinked-protected",
    ]
    proc = run(cmd, REPO, check=False)
    if proc.returncode == 0:
        raise SystemExit(
            "symlinks at protected/control-item positions must block (non-zero exit) — "
            f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )
    plan = read_plan(target)
    by_path = classification_by_path(plan)
    lab_entry = by_path.get("lab", {})
    if lab_entry.get("category") != "protected" or not lab_entry.get("blocker"):
        raise SystemExit(f"'lab' should classify as a protected blocker, got: {lab_entry}")
    if "lab/data (symlink)" not in lab_entry.get("reason", ""):
        raise SystemExit(f"'lab' reason should name the symlink hit, got: {lab_entry.get('reason')}")
    memory_entry = by_path.get("memory", {})
    if memory_entry.get("category") != "conflict" or not memory_entry.get("blocker"):
        raise SystemExit(f"'memory' should classify as a conflict blocker, got: {memory_entry}")
    if "symlink" not in memory_entry.get("reason", ""):
        raise SystemExit(f"'memory' reason should mention the symlink, got: {memory_entry.get('reason')}")
    # The links themselves stay in place, never replaced by real dirs.
    if not (target / "lab" / "data").is_symlink() or not (target / "memory").is_symlink():
        raise SystemExit("protected/control-item symlinks must stay in place as symlinks")
    # Nothing may have been written through the links into the external
    # trees, and the external bytes stay untouched.
    if sorted(p.name for p in external_data.rglob("*")) != ["raw.csv"]:
        raise SystemExit(f"external data dir was modified: {sorted(p.name for p in external_data.rglob('*'))}")
    if (external_data / "raw.csv").read_text(encoding="utf-8") != "a,b\n1,2\n":
        raise SystemExit("external data bytes changed")
    if sorted(p.name for p in external_memory.rglob("*")) != ["notes.md"]:
        raise SystemExit(f"external memory dir was modified: {sorted(p.name for p in external_memory.rglob('*'))}")
    # scaffold must have skipped the whole `lab` control item (no template
    # files merged next to the symlink either).
    if (target / "lab" / "AGENTS.md").exists():
        raise SystemExit("scaffold wrote template files into a lab/ holding a protected symlink")
    print("[adoption-smoke] test_protected_symlink_blocked OK")


def test_tampered_category_blocker_rejected(root: Path) -> None:
    """Review round 2 MAJOR-D negative test: the category/blocker
    invariant — `protected` and `conflict` entries are blockers BY
    DEFINITION. A plan tampered to `blocker=false` for those categories
    must be rejected, never fall through into the move branch."""
    target = make_blocker_fixture(root)
    base_cmd = [
        sys.executable,
        str(ADOPTER),
        str(target),
        "--test-command",
        "none",
        "--project-name",
        "blocker-existing",
    ]
    run(base_cmd + ["--phase", "discover"], REPO)
    plan_path = target / "lab" / "docs" / "audits" / "template-adoption" / "state" / "adoption-plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    for entry in plan["classification"]:
        if entry["path"] in ("checkpoints", "extra"):
            entry["blocker"] = False
    plan_path.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    proc = run(base_cmd + ["--phase", "normalize"], REPO, check=False)
    if proc.returncode == 0:
        raise SystemExit(
            "tampered category/blocker combinations must be rejected (non-zero exit) — "
            f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )
    combined = proc.stdout + proc.stderr
    if combined.count("requires blocker=true") < 2:
        raise SystemExit(
            "both tampered entries should be rejected by the category/blocker invariant — "
            f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )
    if not (target / "checkpoints" / "model.bin").exists():
        raise SystemExit("protected 'checkpoints/model.bin' must not be moved despite blocker=false tampering")
    if not (target / "extra" / "seed.txt").exists():
        raise SystemExit("conflicting 'extra/seed.txt' must not be moved despite blocker=false tampering")
    pre_existing = target / "lab" / "code" / "imported" / "blocker-existing" / "extra" / "seed.txt"
    if pre_existing.read_text(encoding="utf-8") != "pre-existing content already at the import destination\n":
        raise SystemExit("pre-existing conflicting import destination content must not be overwritten")
    print("[adoption-smoke] test_tampered_category_blocker_rejected OK")


def test_non_root_entry_path_rejected(root: Path) -> None:
    """Review rounds 2+3 MAJOR-D negative test: a plan path must name a
    single, real root entry — paths with separators (a nested file, which
    would be a partial move), paths naming nonexistent entries, and '..'
    (round 3: `Path("..").name == ".."`, so the single-segment check alone
    lets it through, and `(target / "..").exists()` is trivially true) are
    all rejected."""
    target = make_conservative_fixture(root)
    base_cmd = [
        sys.executable,
        str(ADOPTER),
        str(target),
        "--test-command",
        "none",
        "--project-name",
        "bad-paths",
    ]
    run(base_cmd + ["--phase", "discover"], REPO)
    plan_path = target / "lab" / "docs" / "audits" / "template-adoption" / "state" / "adoption-plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    # Replace the legit whole-entry 'src' move with a tampered *nested*
    # path (a partial move if it were ever executed) plus a ghost entry.
    plan["classification"] = [e for e in plan["classification"] if e["path"] != "src"]
    plan["classification"].append(
        {
            "path": "src/sample_existing.py",
            "kind": "file",
            "category": "conservative_import",
            "target_path": "lab/code/imported/bad-paths/src/sample_existing.py",
            "blocker": False,
            "reason": "tampered nested path",
        }
    )
    plan["classification"].append(
        {
            "path": "ghost-entry",
            "kind": "dir",
            "category": "conservative_import",
            "target_path": "lab/code/imported/bad-paths/ghost-entry",
            "blocker": False,
            "reason": "tampered nonexistent entry",
        }
    )
    plan["classification"].append(
        {
            "path": "..",
            "kind": "dir",
            "category": "conservative_import",
            "target_path": "lab/code/imported/bad-paths/..",
            "blocker": False,
            "reason": "tampered parent-directory path",
        }
    )
    plan_path.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    proc = run(base_cmd + ["--phase", "normalize"], REPO, check=False)
    if proc.returncode == 0:
        raise SystemExit(
            "non-root-entry plan paths must be rejected (non-zero exit) — "
            f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )
    combined = proc.stdout + proc.stderr
    if "src/sample_existing.py" not in combined or "not a single root entry" not in combined:
        raise SystemExit(
            "nested plan path was not rejected by name validation — "
            f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )
    if "ghost-entry" not in combined or "does not exist" not in combined:
        raise SystemExit(
            "nonexistent plan entry was not rejected — "
            f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )
    if "plan-mismatch: '..'" not in combined:
        raise SystemExit(
            "'..' plan path was not rejected by name validation — "
            f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )
    if not (target / "src" / "sample_existing.py").exists():
        raise SystemExit("nested tampered path must not be moved (partial move)")
    if (target / "lab" / "code" / "imported" / "bad-paths" / "src").exists():
        raise SystemExit("nothing under 'src' may appear at the import destination")
    if not target.exists() or not (target / ".git").exists():
        raise SystemExit("the target repo itself must not move despite the '..' plan path")
    print("[adoption-smoke] test_non_root_entry_path_rejected OK")


def external_tree_names(root: Path) -> list[str]:
    return sorted(p.name for p in root.rglob("*"))


def test_state_dir_symlink_redirected(root: Path) -> None:
    """Review round 3 BLOCKER-C negative test (state writes): the target's
    `lab` is a symlink to an external tree. discover runs BEFORE any
    protection verdict is acted on, so its plan/log writes must not go
    through the symlink — state is redirected to the /tmp fallback, the
    redirect is registered as a blocker (not silently swallowed), and the
    pipeline exits non-zero."""
    external_lab = root / "external-lab"
    write(external_lab / "keep.md", "external bytes\n")
    target = root / "symlinked-lab"
    git_init(target)
    write(target / "README.md", (REPO / "README.md").read_text(encoding="utf-8"))
    (target / "lab").symlink_to(external_lab, target_is_directory=True)
    run(["git", "add", "."], target)
    run(["git", "commit", "-m", "initial"], target)
    fallback = state_fallback(target)
    try:
        cmd = [
            sys.executable,
            str(ADOPTER),
            str(target),
            "--phase",
            "all",
            "--test-command",
            "none",
            "--project-name",
            "symlinked-lab",
        ]
        proc = run(cmd, REPO, check=False)
        if proc.returncode == 0:
            raise SystemExit(
                "a symlinked state path must block the pipeline (non-zero exit) — "
                f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
            )
        combined = proc.stdout + proc.stderr
        if "state-redirect" not in combined:
            raise SystemExit(
                "state redirect was not reported as a blocker — "
                f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
            )
        # Nothing may have been written through the symlink.
        if external_tree_names(external_lab) != ["keep.md"]:
            raise SystemExit(f"external lab tree was modified: {external_tree_names(external_lab)}")
        # The plan landed at the /tmp fallback and records both the
        # control-item-symlink conflict and the state redirect.
        plan_path = fallback / "adoption-plan.json"
        if not plan_path.exists():
            raise SystemExit(f"plan was not written to the state fallback: {plan_path}")
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        entry = classification_by_path(plan).get("lab", {})
        if entry.get("category") != "conflict" or not entry.get("blocker"):
            raise SystemExit(f"symlinked 'lab' should classify as a conflict blocker, got: {entry}")
        if not any("state-redirect" in b for b in plan.get("normalize_blockers", [])):
            raise SystemExit(f"plan must record the state redirect blocker, got: {plan.get('normalize_blockers')}")
        if not (target / "lab").is_symlink():
            raise SystemExit("the symlinked 'lab' must stay in place as a symlink")
    finally:
        shutil.rmtree(fallback, ignore_errors=True)
    print("[adoption-smoke] test_state_dir_symlink_redirected OK")


def test_state_docs_symlink_redirected(root: Path) -> None:
    """Review round 3 BLOCKER-C negative test (state writes, intermediate
    segment): `lab` is a real directory but `lab/docs` is a symlink to an
    external tree — the state path check must lstat EVERY segment, not
    just the state dir leaf or the root entry."""
    external_docs = root / "external-docs"
    write(external_docs / "index.md", "external docs\n")
    target = root / "symlinked-docs"
    git_init(target)
    write(target / "README.md", (REPO / "README.md").read_text(encoding="utf-8"))
    write(target / "lab" / "notes.md", "# lab notes owned by the target repo\n")
    (target / "lab" / "docs").symlink_to(external_docs, target_is_directory=True)
    run(["git", "add", "."], target)
    run(["git", "commit", "-m", "initial"], target)
    fallback = state_fallback(target)
    try:
        cmd = [
            sys.executable,
            str(ADOPTER),
            str(target),
            "--phase",
            "all",
            "--test-command",
            "none",
            "--project-name",
            "symlinked-docs",
        ]
        proc = run(cmd, REPO, check=False)
        if proc.returncode == 0:
            raise SystemExit(
                "a symlinked lab/docs on the state path must block (non-zero exit) — "
                f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
            )
        combined = proc.stdout + proc.stderr
        if "state-redirect" not in combined:
            raise SystemExit(
                "state redirect was not reported as a blocker — "
                f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
            )
        # Nothing may have been written through the symlink (no audits/
        # subtree, no template docs merged into the external tree).
        if external_tree_names(external_docs) != ["index.md"]:
            raise SystemExit(f"external docs tree was modified: {external_tree_names(external_docs)}")
        if not (fallback / "adoption-plan.json").exists():
            raise SystemExit("plan was not written to the state fallback")
        if not (target / "lab" / "docs").is_symlink():
            raise SystemExit("the symlinked 'lab/docs' must stay in place as a symlink")
    finally:
        shutil.rmtree(fallback, ignore_errors=True)
    print("[adoption-smoke] test_state_docs_symlink_redirected OK")


def test_state_leaf_symlinks_redirected(root: Path) -> None:
    """Fresh-review BLOCKER: every canonical state-file leaf participates
    in the state-area lstat gate, not just the directories above it."""
    for leaf in ("adoption-plan.json", "baseline.json", "phase-log.jsonl"):
        case = root / leaf.replace(".", "-")
        external = case / "external"
        sentinel = external / "sentinel.txt"
        write(sentinel, f"external bytes for {leaf}\n")
        original = sentinel.read_text(encoding="utf-8")
        target = case / "target"
        git_init(target)
        write(target / "README.md", (REPO / "README.md").read_text(encoding="utf-8"))
        run(["git", "add", "README.md"], target)
        run(["git", "commit", "-m", "initial"], target)
        state_dir = target / "lab" / "docs" / "audits" / "template-adoption" / "state"
        state_dir.mkdir(parents=True)
        (state_dir / leaf).symlink_to(sentinel)
        fallback = state_fallback(target)
        remove_path(fallback)
        try:
            proc = run(
                [
                    sys.executable,
                    str(ADOPTER),
                    str(target),
                    "--phase",
                    "all",
                    "--test-command",
                    "none",
                    "--project-name",
                    f"canonical-leaf-{leaf}",
                ],
                REPO,
                check=False,
            )
            if proc.returncode == 0:
                raise SystemExit(
                    f"canonical state leaf symlink {leaf} must block the pipeline — "
                    f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
                )
            combined = proc.stdout + proc.stderr
            if "state-redirect" not in combined or leaf not in combined:
                raise SystemExit(
                    f"canonical leaf redirect did not name {leaf} — "
                    f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
                )
            if sentinel.read_text(encoding="utf-8") != original:
                raise SystemExit(f"canonical state leaf symlink was written through: {leaf}")
            if not (state_dir / leaf).is_symlink():
                raise SystemExit(f"canonical state leaf symlink was replaced: {leaf}")
            plan_path = fallback / "adoption-plan.json"
            if not plan_path.is_file() or plan_path.is_symlink():
                raise SystemExit(f"safe fallback plan missing for canonical leaf {leaf}: {plan_path}")
        finally:
            remove_path(fallback)
    print("[adoption-smoke] test_state_leaf_symlinks_redirected OK")


def test_fallback_root_symlink_refused(root: Path) -> None:
    """Fresh-review BLOCKER: a pre-created fallback-root symlink is not a
    second redirect opportunity; adoption fails closed before state I/O."""
    external_lab = root / "external-lab"
    write(external_lab / "keep.md", "canonical external bytes\n")
    target = root / "target"
    git_init(target)
    write(target / "README.md", (REPO / "README.md").read_text(encoding="utf-8"))
    run(["git", "add", "README.md"], target)
    run(["git", "commit", "-m", "initial"], target)
    (target / "lab").symlink_to(external_lab, target_is_directory=True)

    external_fallback = root / "external-fallback"
    write(external_fallback / "sentinel.txt", "fallback external bytes\n")
    fallback = state_fallback(target)
    remove_path(fallback)
    fallback.symlink_to(external_fallback, target_is_directory=True)
    try:
        before = external_tree_names(external_fallback)
        proc = run(
            [sys.executable, str(ADOPTER), str(target), "--phase", "discover", "--test-command", "none"],
            REPO,
            check=False,
        )
        combined = proc.stdout + proc.stderr
        if proc.returncode == 0 or "unsafe state fallback" not in combined:
            raise SystemExit(
                "symlinked fallback root did not fail closed — "
                f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
            )
        if external_tree_names(external_fallback) != before:
            raise SystemExit("fallback-root symlink was written through")
        if not fallback.is_symlink():
            raise SystemExit("fallback-root symlink was replaced")
    finally:
        remove_path(fallback)
    print("[adoption-smoke] test_fallback_root_symlink_refused OK")


def test_fallback_intermediate_symlink_refused(root: Path) -> None:
    """Fresh-review BLOCKER: an intermediate component of the fallback's
    absolute path is lstat-checked too (exercised via TMPDIR)."""
    external_lab = root / "external-lab"
    write(external_lab / "keep.md", "canonical external bytes\n")
    target = root / "target"
    git_init(target)
    write(target / "README.md", (REPO / "README.md").read_text(encoding="utf-8"))
    run(["git", "add", "README.md"], target)
    run(["git", "commit", "-m", "initial"], target)
    (target / "lab").symlink_to(external_lab, target_is_directory=True)

    tmp_parent = root / "tmp-parent"
    tmp_parent.mkdir()
    external_tmp = root / "external-tmp"
    write(external_tmp / "sentinel.txt", "temporary external bytes\n")
    tmp_link = tmp_parent / "redirect"
    tmp_link.symlink_to(external_tmp, target_is_directory=True)
    expected_fallback = fallback_at(target, tmp_link)
    env = os.environ.copy()
    env["TMPDIR"] = str(tmp_link)
    before = external_tree_names(external_tmp)
    proc = run(
        [sys.executable, str(ADOPTER), str(target), "--phase", "discover", "--test-command", "none"],
        REPO,
        check=False,
        env=env,
    )
    combined = proc.stdout + proc.stderr
    if proc.returncode == 0 or "unsafe state fallback" not in combined or str(tmp_link) not in combined:
        raise SystemExit(
            "symlinked fallback intermediate did not fail closed — "
            f"expected fallback={expected_fallback}\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )
    if external_tree_names(external_tmp) != before:
        raise SystemExit("fallback-intermediate symlink was written through")
    if expected_fallback.exists() or expected_fallback.is_symlink():
        raise SystemExit(f"fallback root was created through an intermediate symlink: {expected_fallback}")
    print("[adoption-smoke] test_fallback_intermediate_symlink_refused OK")


def test_fallback_leaf_symlinks_refused(root: Path) -> None:
    """Fresh-review BLOCKER: no deterministic fallback state leaf may be a
    pre-positioned symlink, even when another leaf would be written first."""
    for leaf in ("adoption-plan.json", "baseline.json", "phase-log.jsonl"):
        case = root / leaf.replace(".", "-")
        external_lab = case / "external-lab"
        write(external_lab / "keep.md", "canonical external bytes\n")
        target = case / "target"
        git_init(target)
        write(target / "README.md", (REPO / "README.md").read_text(encoding="utf-8"))
        run(["git", "add", "README.md"], target)
        run(["git", "commit", "-m", "initial"], target)
        (target / "lab").symlink_to(external_lab, target_is_directory=True)

        fallback = state_fallback(target)
        remove_path(fallback)
        fallback.mkdir()
        sentinel = case / "external-state" / "sentinel.txt"
        write(sentinel, f"fallback external bytes for {leaf}\n")
        original = sentinel.read_text(encoding="utf-8")
        (fallback / leaf).symlink_to(sentinel)
        try:
            proc = run(
                [
                    sys.executable,
                    str(ADOPTER),
                    str(target),
                    "--phase",
                    "discover",
                    "--test-command",
                    "none",
                ],
                REPO,
                check=False,
            )
            combined = proc.stdout + proc.stderr
            if proc.returncode == 0 or "unsafe state fallback" not in combined or leaf not in combined:
                raise SystemExit(
                    f"fallback state leaf symlink {leaf} did not fail closed — "
                    f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
                )
            if sentinel.read_text(encoding="utf-8") != original:
                raise SystemExit(f"fallback state leaf symlink was written through: {leaf}")
            if not (fallback / leaf).is_symlink():
                raise SystemExit(f"fallback state leaf symlink was replaced: {leaf}")
        finally:
            remove_path(fallback)
    print("[adoption-smoke] test_fallback_leaf_symlinks_refused OK")


def test_archive_path_symlink_refused(root: Path) -> None:
    """Review round 3 BLOCKER-C negative test (conflict archive): the
    target's `human/imported` is a symlink to an external tree. When
    scaffold wants to stash a divergent control-dir file into
    human/imported/adoption-conflicts/, it must refuse (blocker) instead
    of moving the original file OUT of the repo — and must not overwrite
    the file it could not stash."""
    external_stash = root / "external-stash"
    write(external_stash / "keep.md", "external bytes\n")
    target = root / "symlinked-archive"
    git_init(target)
    write(target / "README.md", (REPO / "README.md").read_text(encoding="utf-8"))
    divergent = "# target's own status file, not the template's\n"
    write(target / "memory" / "current-status.md", divergent)
    (target / "human").mkdir()
    (target / "human" / "imported").symlink_to(external_stash, target_is_directory=True)
    run(["git", "add", "."], target)
    run(["git", "commit", "-m", "initial"], target)
    cmd = [
        sys.executable,
        str(ADOPTER),
        str(target),
        "--phase",
        "all",
        "--test-command",
        "none",
        "--project-name",
        "symlinked-archive",
    ]
    proc = run(cmd, REPO, check=False)
    if proc.returncode == 0:
        raise SystemExit(
            "a symlinked conflict-archive path must block the pipeline (non-zero exit) — "
            f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )
    combined = proc.stdout + proc.stderr
    if "archive-symlink" not in combined:
        raise SystemExit(
            "archive-path symlink was not reported as a blocker — "
            f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )
    # The divergent file was neither stashed out of the repo nor
    # overwritten with the template's version.
    current = (target / "memory" / "current-status.md").read_text(encoding="utf-8")
    if current != divergent:
        raise SystemExit("the file that could not be archived must not be overwritten")
    if external_tree_names(external_stash) != ["keep.md"]:
        raise SystemExit(f"external stash tree was modified: {external_tree_names(external_stash)}")
    if not (target / "human" / "imported").is_symlink():
        raise SystemExit("the symlinked 'human/imported' must stay in place as a symlink")
    print("[adoption-smoke] test_archive_path_symlink_refused OK")


def test_long_slug_truncated(root: Path) -> None:
    """Review round 3 MAJOR positive test: a 300-char --project-name must
    not ENAMETOOLONG mid-pipeline — project_slug caps the slug at 100
    chars (hash-suffixed for uniqueness) and `--phase all` completes."""
    target = make_conservative_fixture(root)
    long_name = "x" * 300
    cmd = [
        sys.executable,
        str(ADOPTER),
        str(target),
        "--phase",
        "all",
        "--test-command",
        "none",
        "--project-name",
        long_name,
    ]
    run(cmd, REPO)
    run([sys.executable, str(INTEGRITY), str(target)], REPO)
    plan = read_plan(target)
    slug = plan["project_slug"]
    if len(slug) > 100:
        raise SystemExit(f"slug was not truncated to a safe length: len={len(slug)}")
    if not slug.startswith("xxx") or "-" not in slug:
        raise SystemExit(f"truncated slug should keep a readable prefix plus a hash suffix, got: {slug!r}")
    imported = target / "lab" / "code" / "imported" / slug
    if not (imported / "src" / "sample_existing.py").exists():
        raise SystemExit(f"import root with truncated slug missing: {imported}")
    print("[adoption-smoke] test_long_slug_truncated OK")


def test_tracked_file_in_excluded_dir_integrity(root: Path) -> None:
    """Review round 3 MAJOR positive test: the baseline collects ALL
    tracked files (`git ls-files`), including ones under a `.venv`-named
    dir — the integrity proof's current-hash index must honour the same
    contract and find them at the moved location instead of misreporting
    intact files as missing (which would fail a legitimate adoption)."""
    target = root / "venv-tracked"
    git_init(target)
    write(target / "README.md", (REPO / "README.md").read_text(encoding="utf-8"))
    write(target / "tools" / "main.py", "print('hi')\n")
    write(target / "tools" / ".venv" / "pinned.txt", "pinned==1.0\n")
    run(["git", "add", "."], target)
    run(["git", "commit", "-m", "initial"], target)
    cmd = [
        sys.executable,
        str(ADOPTER),
        str(target),
        "--phase",
        "all",
        "--test-command",
        "none",
        "--project-name",
        "venv-tracked",
    ]
    run(cmd, REPO)
    run([sys.executable, str(INTEGRITY), str(target)], REPO)
    moved = target / "lab" / "code" / "imported" / "venv-tracked" / "tools" / ".venv" / "pinned.txt"
    if not moved.exists():
        raise SystemExit(f"tracked file under .venv should have moved with its entry: {moved}")
    print("[adoption-smoke] test_tracked_file_in_excluded_dir_integrity OK")


def _contract_repo(root: Path, name: str) -> Path:
    target = root / name
    git_init(target)
    write(target / "README.md", (REPO / "README.md").read_text(encoding="utf-8"))
    return target


def _commit_fixture(target: Path) -> None:
    run(["git", "add", "."], target)
    run(["git", "commit", "-m", "initial"], target)


def _state_log(target: Path) -> Path:
    return target / "lab" / "docs" / "audits" / "template-adoption" / "state" / "phase-log.jsonl"


def test_smoke_contract_protected_integrity(root: Path) -> None:
    target = _contract_repo(root, "contract-protected")
    write(target / "checkpoints" / "model.bin", "fixture only\n")
    _commit_fixture(target)
    proc = run(
        [sys.executable, str(ADOPTER), str(target), "--phase", "all", "--project-name", target.name],
        REPO,
        check=False,
    )
    if proc.returncode == 0 or "checkpoints" not in proc.stderr:
        raise SystemExit("protected smoke-contract fixture did not fail with a readable blocker")
    integrity = run([sys.executable, str(INTEGRITY), str(target), "--json"], REPO, check=False)
    data = json.loads(integrity.stdout)
    blockers = data.get("unresolved_blockers", [])
    if integrity.returncode == 0 or data.get("ok") or not any(
        "checkpoints" in item for item in blockers
    ):
        raise SystemExit(f"protected blocker was not preserved by integrity JSON: {data}")
    print("[adoption-smoke] test_smoke_contract_protected_integrity OK")


def test_smoke_contract_destination_conflict(root: Path) -> None:
    target = _contract_repo(root, "contract-conflict")
    source_text = "source bytes\n"
    destination_text = "existing destination bytes\n"
    destination = target / "lab" / "code" / "imported" / target.name / "data.txt"
    write(target / "data.txt", source_text)
    write(destination, destination_text)
    _commit_fixture(target)
    proc = run(
        [sys.executable, str(ADOPTER), str(target), "--phase", "all", "--project-name", target.name],
        REPO,
        check=False,
    )
    if proc.returncode == 0:
        raise SystemExit("destination conflict unexpectedly passed")
    if (target / "data.txt").read_text(encoding="utf-8") != source_text:
        raise SystemExit("destination conflict moved or changed the source")
    if destination.read_text(encoding="utf-8") != destination_text:
        raise SystemExit("destination conflict changed the existing destination")
    integrity = run([sys.executable, str(INTEGRITY), str(target), "--json"], REPO, check=False)
    data = json.loads(integrity.stdout)
    blockers = data.get("unresolved_blockers", [])
    if integrity.returncode == 0 or not any("destination" in item for item in blockers):
        raise SystemExit(f"destination conflict missing from integrity JSON: {data}")
    print("[adoption-smoke] test_smoke_contract_destination_conflict OK")


def test_smoke_contract_failure(root: Path) -> None:
    target = _contract_repo(root, "contract-failure")
    write(
        target / "tests" / "test_broken.py",
        "import unittest\n\n"
        "class BrokenTest(unittest.TestCase):\n"
        "    def test_broken(self):\n"
        "        self.assertEqual(1, 2, 'intentional fixture failure')\n",
    )
    _commit_fixture(target)
    run(
        [
            sys.executable,
            str(ADOPTER),
            str(target),
            "--phase",
            "all",
            "--test-command",
            "python -m unittest discover -s tests",
            "--project-name",
            target.name,
        ],
        REPO,
    )
    integrity = run([sys.executable, str(INTEGRITY), str(target), "--json"], REPO)
    data = json.loads(integrity.stdout)
    warnings = data.get("smoke_warnings", [])
    if not data.get("ok") or not warnings or warnings[0].get("result") != "fail":
        raise SystemExit(f"real failing test did not produce an explicit fail warning: {data}")
    prove_rows = [
        json.loads(line)
        for line in _state_log(target).read_text(encoding="utf-8").splitlines()
        if line.strip() and json.loads(line).get("phase") == "prove"
    ]
    smoke_exec = prove_rows[-1]["details"]["smoke"]["exec"]
    output = (smoke_exec.get("stdout") or "") + (smoke_exec.get("stderr") or "")
    if "Ran 1 test" not in output or "FAILED" not in output:
        raise SystemExit("failure fixture did not run and fail exactly one unittest")
    print("[adoption-smoke] test_smoke_contract_failure OK")


def test_smoke_contract_undetected(root: Path) -> None:
    target = _contract_repo(root, "contract-undetected")
    write(target / "notes.txt", "no test infrastructure\n")
    _commit_fixture(target)
    run(
        [sys.executable, str(ADOPTER), str(target), "--phase", "all", "--project-name", target.name],
        REPO,
    )
    data = json.loads(
        run([sys.executable, str(INTEGRITY), str(target), "--json"], REPO).stdout
    )
    warnings = data.get("smoke_warnings", [])
    if not data.get("ok") or not warnings or warnings[0].get("result") != "skipped":
        raise SystemExit(f"undetected test command was not explicitly reported as skipped: {data}")
    print("[adoption-smoke] test_smoke_contract_undetected OK")


def test_smoke_contract_timeout(root: Path) -> None:
    target = _contract_repo(root, "contract-timeout")
    write(target / "notes.txt", "timeout fixture\n")
    _commit_fixture(target)
    run(
        [
            sys.executable,
            str(ADOPTER),
            str(target),
            "--phase",
            "all",
            "--test-command",
            f'{sys.executable} -c "import time; time.sleep(3)"',
            "--test-timeout",
            "1",
            "--project-name",
            target.name,
        ],
        REPO,
    )
    data = json.loads(
        run([sys.executable, str(INTEGRITY), str(target), "--json"], REPO).stdout
    )
    warnings = data.get("smoke_warnings", [])
    if not data.get("ok") or not warnings or warnings[0].get("result") != "unknown":
        raise SystemExit(f"timed-out test was not explicitly reported as unknown: {data}")
    prove_rows = [
        json.loads(line)
        for line in _state_log(target).read_text(encoding="utf-8").splitlines()
        if line.strip() and json.loads(line).get("phase") == "prove"
    ]
    if not prove_rows[-1]["details"]["smoke"].get("exec", {}).get("timeout"):
        raise SystemExit("timed-out test did not retain timeout=true in the phase log")
    print("[adoption-smoke] test_smoke_contract_timeout OK")


def test_smoke_contract_legacy_state(root: Path) -> None:
    target = _contract_repo(root, "contract-legacy")
    write(target / "notes.txt", "legacy state fixture\n")
    _commit_fixture(target)
    run(
        [
            sys.executable,
            str(ADOPTER),
            str(target),
            "--phase",
            "all",
            "--test-command",
            "true",
            "--project-name",
            target.name,
        ],
        REPO,
    )
    plan_path = (
        target
        / "lab"
        / "docs"
        / "audits"
        / "template-adoption"
        / "state"
        / "adoption-plan.json"
    )
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan["schema"] = "template-adoption-plan-v1"
    plan.pop("test_command_source", None)
    plan_path.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    prove = run(
        [sys.executable, str(ADOPTER), str(target), "--phase", "prove", "--project-name", target.name],
        REPO,
        check=False,
    )
    output = prove.stdout + prove.stderr
    if prove.returncode == 0 or "rerun --phase discover before prove" not in output:
        raise SystemExit("legacy state without command provenance did not fail closed")
    print("[adoption-smoke] test_smoke_contract_legacy_state OK")


def main() -> int:
    # Sandboxes without a writable temp dir (e.g. no /tmp) must get an
    # explicit SKIP, not a crash mid-run.
    try:
        with tempfile.TemporaryDirectory(prefix="adoption-smoke-probe-"):
            pass
    except OSError as e:
        print(
            f"[adoption-smoke] SKIP: no writable temp dir available ({e}); "
            "set TMPDIR to a writable scratch directory and re-run"
        )
        return 0
    with tempfile.TemporaryDirectory(prefix="adoption-smoke-") as tmp:
        test_conservative_migration(Path(tmp))
    with tempfile.TemporaryDirectory(prefix="adoption-smoke-blocker-") as tmp:
        test_blocker_fixture(Path(tmp))
    with tempfile.TemporaryDirectory(prefix="adoption-smoke-nested-") as tmp:
        test_nested_protected_fixture(Path(tmp))
    with tempfile.TemporaryDirectory(prefix="adoption-smoke-divergent-") as tmp:
        test_control_item_divergence(Path(tmp))
    with tempfile.TemporaryDirectory(prefix="adoption-smoke-stale-") as tmp:
        test_stale_plan_rejected(Path(tmp))
    with tempfile.TemporaryDirectory(prefix="adoption-smoke-unplanned-") as tmp:
        test_unplanned_root_entry_rejected(Path(tmp))
    with tempfile.TemporaryDirectory(prefix="adoption-smoke-forged-control-") as tmp:
        test_forged_template_control_item_rejected(Path(tmp))
    with tempfile.TemporaryDirectory(prefix="adoption-smoke-venv-") as tmp:
        test_excluded_dir_protected_content(Path(tmp))
    with tempfile.TemporaryDirectory(prefix="adoption-smoke-escape-") as tmp:
        test_target_path_escape_rejected(Path(tmp))
    with tempfile.TemporaryDirectory(prefix="adoption-smoke-symlink-") as tmp:
        test_protected_symlink_blocked(Path(tmp))
    with tempfile.TemporaryDirectory(prefix="adoption-smoke-tamper-") as tmp:
        test_tampered_category_blocker_rejected(Path(tmp))
    with tempfile.TemporaryDirectory(prefix="adoption-smoke-badpath-") as tmp:
        test_non_root_entry_path_rejected(Path(tmp))
    with tempfile.TemporaryDirectory(prefix="adoption-smoke-statelink-") as tmp:
        test_state_dir_symlink_redirected(Path(tmp))
    with tempfile.TemporaryDirectory(prefix="adoption-smoke-docslink-") as tmp:
        test_state_docs_symlink_redirected(Path(tmp))
    with tempfile.TemporaryDirectory(prefix="adoption-smoke-stateleaf-") as tmp:
        test_state_leaf_symlinks_redirected(Path(tmp))
    with tempfile.TemporaryDirectory(prefix="adoption-smoke-fallback-root-") as tmp:
        test_fallback_root_symlink_refused(Path(tmp))
    with tempfile.TemporaryDirectory(prefix="adoption-smoke-fallback-mid-") as tmp:
        test_fallback_intermediate_symlink_refused(Path(tmp))
    with tempfile.TemporaryDirectory(prefix="adoption-smoke-fallback-leaf-") as tmp:
        test_fallback_leaf_symlinks_refused(Path(tmp))
    with tempfile.TemporaryDirectory(prefix="adoption-smoke-archivelink-") as tmp:
        test_archive_path_symlink_refused(Path(tmp))
    with tempfile.TemporaryDirectory(prefix="adoption-smoke-longslug-") as tmp:
        test_long_slug_truncated(Path(tmp))
    with tempfile.TemporaryDirectory(prefix="adoption-smoke-venvtracked-") as tmp:
        test_tracked_file_in_excluded_dir_integrity(Path(tmp))
    with tempfile.TemporaryDirectory(prefix="adoption-smoke-contract-protected-") as tmp:
        test_smoke_contract_protected_integrity(Path(tmp))
    with tempfile.TemporaryDirectory(prefix="adoption-smoke-contract-conflict-") as tmp:
        test_smoke_contract_destination_conflict(Path(tmp))
    with tempfile.TemporaryDirectory(prefix="adoption-smoke-contract-failure-") as tmp:
        test_smoke_contract_failure(Path(tmp))
    with tempfile.TemporaryDirectory(prefix="adoption-smoke-contract-undetected-") as tmp:
        test_smoke_contract_undetected(Path(tmp))
    with tempfile.TemporaryDirectory(prefix="adoption-smoke-contract-timeout-") as tmp:
        test_smoke_contract_timeout(Path(tmp))
    with tempfile.TemporaryDirectory(prefix="adoption-smoke-contract-legacy-") as tmp:
        test_smoke_contract_legacy_state(Path(tmp))
    print("[adoption-smoke] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
