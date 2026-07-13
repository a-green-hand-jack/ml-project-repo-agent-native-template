#!/usr/bin/env python3
"""Synthetic smoke test for adopt-existing-repo.

Covers the happy path plus the negative fixtures required by the C part of
plans/20260712-bootstrap-adoption-proof.zh.md (smoke/integrity contract):

1. happy path -- clean adoption, native test passes, no warnings.
2. blocked normalize (protected path) -- adoption-tool-self integrity
   failure: both `adopt-existing-repo.py` and `check-adoption-integrity.py`
   must exit non-zero, and the blocker must be readable in their output.
3. blocked conflict (destination exists) -- the normalize destination for a
   root entry already holds different content: same non-zero-exit integrity
   contract as (2), plus the blocker must appear in `--json`
   `unresolved_blockers` and neither side of the conflict may be touched.
4. smoke command detected but failing -- NOT an integrity failure: both
   scripts must exit 0, but the generated report / `check-adoption-integrity
   --json` output must carry an explicit, non-empty warning for the failed
   native test (which must have actually run -- not "Ran 0 tests").
5. smoke command undetected -- same exit-0-with-explicit-warning contract,
   for the "skipped" (no test command found) case.
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


def run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    """Run a command and raise (loudly) on unexpected non-zero exit."""
    proc = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, check=False)
    if proc.returncode != 0:
        print("$ " + " ".join(cmd))
        print(proc.stdout)
        print(proc.stderr)
        raise SystemExit(proc.returncode)
    return proc


def run_allow_fail(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    """Run a command without raising; caller inspects returncode."""
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, check=False)


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def init_repo(target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    run(["git", "init"], target)
    run(["git", "config", "user.email", "adoption@example.test"], target)
    run(["git", "config", "user.name", "Adoption Test"], target)


def make_happy_fixture(root: Path) -> Path:
    target = root / "sample-existing"
    init_repo(target)
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


def scenario_happy_path(root: Path) -> None:
    target = make_happy_fixture(root)
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
    imported = target / "lab" / "code" / "imported" / "sample-existing"
    expected = [
        imported / "src" / "sample_existing.py",
        imported / "tests" / "test_sample.py",
        imported / "pyproject.toml",
        target / "human" / "imported" / "adoption-conflicts" / "README.md",
        target / "lab" / "docs" / "audits" / "template-adoption-report.md",
    ]
    missing = [p for p in expected if not p.exists()]
    if missing:
        for path in missing:
            print(f"missing expected path: {path}")
        raise SystemExit(1)
    root_names = {p.name for p in target.iterdir()}
    polluted = {"src", "tests", "pyproject.toml"} & root_names
    if polluted:
        print(f"root pollution remained: {sorted(polluted)}")
        raise SystemExit(1)
    report = (target / "lab" / "docs" / "audits" / "template-adoption-report.md").read_text(
        encoding="utf-8"
    )
    if "smoke_result: `pass`" not in report:
        print("happy path: expected smoke_result: `pass` in report")
        print(report)
        raise SystemExit(1)
    if "No warnings." not in report:
        print("happy path: expected no-warnings note in report")
        print(report)
        raise SystemExit(1)
    integrity_json = run([sys.executable, str(INTEGRITY), str(target), "--json"], REPO)
    data = json.loads(integrity_json.stdout)
    if data.get("smoke_warnings"):
        print(f"happy path: expected no smoke_warnings, got {data['smoke_warnings']}")
        raise SystemExit(1)
    print("[adoption-smoke] happy-path OK")


def scenario_blocked_normalize(root: Path) -> None:
    """Protected root path -> adoption-tool-self integrity failure.

    Both `adopt-existing-repo.py` and `check-adoption-integrity.py` must
    exit non-zero, and the blocker must be readable in their output (C3).
    """
    target = root / "blocked-existing"
    init_repo(target)
    write(target / "README.md", "# Blocked Repo\n")
    write(target / "checkpoints" / "model.bin", "not-a-real-checkpoint")
    run(["git", "add", "."], target)
    run(["git", "commit", "-m", "initial"], target)

    adopt_cmd = [
        sys.executable,
        str(ADOPTER),
        str(target),
        "--phase",
        "all",
        "--project-name",
        "blocked-existing",
    ]
    adopt_proc = run_allow_fail(adopt_cmd, REPO)
    if adopt_proc.returncode == 0:
        print("blocked-normalize: expected non-zero exit from adopt-existing-repo.py")
        print(adopt_proc.stdout)
        print(adopt_proc.stderr)
        raise SystemExit(1)
    if "checkpoints" not in adopt_proc.stderr:
        print("blocked-normalize: expected 'checkpoints' blocker to be readable in stderr")
        print(adopt_proc.stderr)
        raise SystemExit(1)

    integrity_cmd = [sys.executable, str(INTEGRITY), str(target)]
    integrity_proc = run_allow_fail(integrity_cmd, REPO)
    if integrity_proc.returncode == 0:
        print("blocked-normalize: expected non-zero exit from check-adoption-integrity.py")
        print(integrity_proc.stdout)
        raise SystemExit(1)
    if "BLOCKED checkpoints" not in integrity_proc.stdout:
        print("blocked-normalize: expected 'BLOCKED checkpoints' in check-adoption-integrity output")
        print(integrity_proc.stdout)
        raise SystemExit(1)

    integrity_json_proc = run_allow_fail(
        [sys.executable, str(INTEGRITY), str(target), "--json"], REPO
    )
    if integrity_json_proc.returncode == 0:
        print("blocked-normalize: expected non-zero exit from check-adoption-integrity.py --json")
        raise SystemExit(1)
    data = json.loads(integrity_json_proc.stdout)
    if data.get("ok"):
        print("blocked-normalize: expected ok=false in --json output")
        raise SystemExit(1)
    if "checkpoints" not in data.get("unresolved_blockers", []):
        print(f"blocked-normalize: expected 'checkpoints' in unresolved_blockers, got {data}")
        raise SystemExit(1)
    print("[adoption-smoke] blocked-normalize OK")


def scenario_blocked_conflict(root: Path) -> None:
    """Destination-exists conflict -> adoption-tool-self integrity failure.

    The normalize destination for a root entry already holds *different*
    content. The adopter must stop with a non-zero exit (no move, both sides
    of the conflict byte-untouched), and the blocker must be readable both in
    `check-adoption-integrity.py` text output and in `--json`
    `unresolved_blockers` (C3; the "conflict file" sub-case of the plan's
    negative-fixture acceptance criteria, distinct from the protected-path
    sub-case covered by scenario_blocked_normalize).
    """
    target = root / "conflict-existing"
    init_repo(target)
    write(target / "README.md", "# Conflict Repo\n")
    root_content = "root copy: should be moved by normalize\n"
    dest_content = "pre-existing, inconsistent content at the destination\n"
    dest_rel = "lab/code/imported/conflict-existing/data.txt"
    write(target / "data.txt", root_content)
    write(target / dest_rel, dest_content)
    run(["git", "add", "."], target)
    run(["git", "commit", "-m", "initial"], target)

    adopt_cmd = [
        sys.executable,
        str(ADOPTER),
        str(target),
        "--phase",
        "all",
        "--project-name",
        "conflict-existing",
    ]
    adopt_proc = run_allow_fail(adopt_cmd, REPO)
    if adopt_proc.returncode == 0:
        print("blocked-conflict: expected non-zero exit from adopt-existing-repo.py")
        print(adopt_proc.stdout)
        print(adopt_proc.stderr)
        raise SystemExit(1)
    blocker = f"destination exists: {dest_rel}"
    if blocker not in adopt_proc.stderr:
        print(f"blocked-conflict: expected {blocker!r} to be readable in stderr")
        print(adopt_proc.stderr)
        raise SystemExit(1)
    # The adopter must have stopped without destroying either side of the
    # conflict: the root copy stays in place, the destination keeps its bytes.
    if (target / "data.txt").read_text(encoding="utf-8") != root_content:
        print("blocked-conflict: root data.txt was moved/modified despite the blocker")
        raise SystemExit(1)
    if (target / dest_rel).read_text(encoding="utf-8") != dest_content:
        print("blocked-conflict: destination file content changed despite the blocker")
        raise SystemExit(1)

    integrity_proc = run_allow_fail([sys.executable, str(INTEGRITY), str(target)], REPO)
    if integrity_proc.returncode == 0:
        print("blocked-conflict: expected non-zero exit from check-adoption-integrity.py")
        print(integrity_proc.stdout)
        raise SystemExit(1)
    if f"BLOCKED {blocker}" not in integrity_proc.stdout:
        print(f"blocked-conflict: expected 'BLOCKED {blocker}' in check-adoption-integrity output")
        print(integrity_proc.stdout)
        raise SystemExit(1)

    integrity_json_proc = run_allow_fail(
        [sys.executable, str(INTEGRITY), str(target), "--json"], REPO
    )
    if integrity_json_proc.returncode == 0:
        print("blocked-conflict: expected non-zero exit from check-adoption-integrity.py --json")
        raise SystemExit(1)
    data = json.loads(integrity_json_proc.stdout)
    if data.get("ok"):
        print("blocked-conflict: expected ok=false in --json output")
        raise SystemExit(1)
    if blocker not in data.get("unresolved_blockers", []):
        print(f"blocked-conflict: expected {blocker!r} in unresolved_blockers, got {data}")
        raise SystemExit(1)
    print("[adoption-smoke] blocked-conflict OK")


def scenario_smoke_failing_command(root: Path) -> None:
    """Native test command detected but fails -- NOT an integrity failure.

    Exit codes for both scripts must stay 0; the report and
    `check-adoption-integrity --json` output must carry an explicit,
    non-empty warning (C1/C2/C3, open question 5).
    """
    target = root / "smoke-fail-existing"
    init_repo(target)
    write(target / "README.md", "# Smoke Fail Repo\n")
    # The fixture must be a unittest.TestCase: the explicit --test-command
    # below is `python -m unittest discover`, which does NOT collect
    # pytest-style module-level functions. (A previous version of this
    # fixture used a bare `def test_broken()` and unittest ran 0 tests --
    # exit 0 on Python <= 3.11, exit 5 via NO_TESTS_RAN on >= 3.12 -- so the
    # scenario never exercised a real detected-but-failing native test.)
    write(
        target / "tests" / "test_broken.py",
        "import unittest\n\n"
        "class BrokenTest(unittest.TestCase):\n"
        "    def test_broken(self):\n"
        "        self.assertEqual(1, 2, 'intentionally broken for the smoke fixture')\n",
    )
    run(["git", "add", "."], target)
    run(["git", "commit", "-m", "initial"], target)

    adopt_cmd = [
        sys.executable,
        str(ADOPTER),
        str(target),
        "--phase",
        "all",
        "--test-command",
        "python -m unittest discover -s tests",
        "--project-name",
        "smoke-fail-existing",
    ]
    run(adopt_cmd, REPO)  # must exit 0 despite the failing native test
    run([sys.executable, str(INTEGRITY), str(target)], REPO)  # must exit 0 too

    report_path = target / "lab" / "docs" / "audits" / "template-adoption-report.md"
    report = report_path.read_text(encoding="utf-8")
    if "smoke_result: `fail`" not in report:
        print("smoke-fail: expected smoke_result: `fail` in report")
        print(report)
        raise SystemExit(1)
    if "`original_test`: result=`fail`" not in report:
        print("smoke-fail: expected an explicit original_test warning line in report")
        print(report)
        raise SystemExit(1)

    integrity_json_proc = run(
        [sys.executable, str(INTEGRITY), str(target), "--json"], REPO
    )
    data = json.loads(integrity_json_proc.stdout)
    if not data.get("ok"):
        print(f"smoke-fail: expected ok=true (integrity unaffected by smoke), got {data}")
        raise SystemExit(1)
    warnings = data.get("smoke_warnings", [])
    if not warnings or warnings[0].get("result") != "fail":
        print(f"smoke-fail: expected a non-empty fail warning, got {warnings}")
        raise SystemExit(1)

    # Guard against the fixture silently degrading into "Ran 0 tests": the
    # `fail` must come from a native test that actually ran. Read the
    # structured smoke exec record from the prove phase-log (single
    # structured source of truth, same as latest_smoke_warnings()).
    log_path = (
        target / "lab" / "docs" / "audits" / "template-adoption" / "state" / "phase-log.jsonl"
    )
    prove_rows = [
        row
        for row in (
            json.loads(line)
            for line in log_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
        if row.get("phase") == "prove"
    ]
    smoke_exec = prove_rows[-1]["details"]["smoke"]["exec"]
    combined_output = (smoke_exec.get("stdout") or "") + (smoke_exec.get("stderr") or "")
    if "Ran 1 test" not in combined_output or "FAILED" not in combined_output:
        print(
            "smoke-fail: expected the native test to actually run and fail "
            "(unittest 'Ran 1 test' + 'FAILED'), not e.g. 'Ran 0 tests'"
        )
        print(combined_output)
        raise SystemExit(1)
    print("[adoption-smoke] smoke-failing-command OK")


def scenario_smoke_undetected(root: Path) -> None:
    """No native test command detectable -- "skipped", not silently pass.

    Exit codes for both scripts must stay 0; the report and
    `check-adoption-integrity --json` output must carry an explicit,
    non-empty warning explaining why nothing was verified (C1/C2/C3).
    """
    target = root / "smoke-undetected-existing"
    init_repo(target)
    write(target / "README.md", "# Smoke Undetected Repo\n")
    write(target / "notes.txt", "no test infra here on purpose\n")
    run(["git", "add", "."], target)
    run(["git", "commit", "-m", "initial"], target)

    adopt_cmd = [
        sys.executable,
        str(ADOPTER),
        str(target),
        "--phase",
        "all",
        "--project-name",
        "smoke-undetected-existing",
    ]
    run(adopt_cmd, REPO)
    run([sys.executable, str(INTEGRITY), str(target)], REPO)

    report_path = target / "lab" / "docs" / "audits" / "template-adoption-report.md"
    report = report_path.read_text(encoding="utf-8")
    if "smoke_result: `skipped`" not in report:
        print("smoke-undetected: expected smoke_result: `skipped` in report")
        print(report)
        raise SystemExit(1)
    if "no native test command detected" not in report:
        print("smoke-undetected: expected the undetected-command reason in report")
        print(report)
        raise SystemExit(1)

    integrity_json_proc = run(
        [sys.executable, str(INTEGRITY), str(target), "--json"], REPO
    )
    data = json.loads(integrity_json_proc.stdout)
    if not data.get("ok"):
        print(f"smoke-undetected: expected ok=true, got {data}")
        raise SystemExit(1)
    warnings = data.get("smoke_warnings", [])
    if not warnings or warnings[0].get("result") != "skipped":
        print(f"smoke-undetected: expected a non-empty skipped warning, got {warnings}")
        raise SystemExit(1)
    print("[adoption-smoke] smoke-undetected OK")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="adoption-smoke-") as tmp:
        root = Path(tmp)
        scenario_happy_path(root)
        scenario_blocked_normalize(root)
        scenario_blocked_conflict(root)
        scenario_smoke_failing_command(root)
        scenario_smoke_undetected(root)
    print("[adoption-smoke] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
