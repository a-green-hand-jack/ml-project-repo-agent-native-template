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
10. `test_non_root_entry_path_rejected` (review round 2 MAJOR-D): plan
    paths with separators (nested files) or naming nonexistent root
    entries are rejected; no partial moves.

If no writable temp directory is available (sandboxes without /tmp), the
whole smoke prints an explicit SKIP and exits 0 instead of crashing.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
ADOPTER = REPO / "scripts" / "adopt-existing-repo.py"
INTEGRITY = REPO / "scripts" / "check-adoption-integrity.py"


def run(cmd: list[str], cwd: Path, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, check=False)
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
    """Review round 2 MAJOR-D negative test: a plan path must name a
    single, real root entry — paths with separators (a nested file, which
    would be a partial move) and paths naming nonexistent entries are
    rejected."""
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
    if not (target / "src" / "sample_existing.py").exists():
        raise SystemExit("nested tampered path must not be moved (partial move)")
    if (target / "lab" / "code" / "imported" / "bad-paths" / "src").exists():
        raise SystemExit("nothing under 'src' may appear at the import destination")
    print("[adoption-smoke] test_non_root_entry_path_rejected OK")


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
    print("[adoption-smoke] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
