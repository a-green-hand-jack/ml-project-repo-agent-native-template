#!/usr/bin/env python3
"""Synthetic smoke test for adopt-existing-repo.

Two fixtures (plan B5, plans/20260712-bootstrap-adoption-proof.zh.md):

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
    write(target / "README.md", "# Sample Existing Repo\n")
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
        target / "human" / "imported" / "adoption-conflicts" / "README.md",
        target / "lab" / "docs" / "audits" / "template-adoption-report.md",
    ]
    missing = [p for p in expected_paths if not p.exists()]
    if missing:
        raise SystemExit("missing expected path(s): " + ", ".join(str(p) for p in missing))
    root_names = {p.name for p in target.iterdir()}
    polluted = {"src", "tests", "pyproject.toml"} & root_names
    if polluted:
        raise SystemExit(f"root pollution remained: {sorted(polluted)}")
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


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="adoption-smoke-") as tmp:
        test_conservative_migration(Path(tmp))
    with tempfile.TemporaryDirectory(prefix="adoption-smoke-blocker-") as tmp:
        test_blocker_fixture(Path(tmp))
    print("[adoption-smoke] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
