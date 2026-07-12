#!/usr/bin/env python3
"""Synthetic smoke test for adopt-existing-repo.

Covers the happy path plus the negative fixtures required by the C part of
plans/20260712-bootstrap-adoption-proof.zh.md (smoke/integrity contract):

1. happy path -- clean adoption, native test passes, no warnings.
2. blocked normalize (protected path) -- adoption-tool-self integrity
   failure: both `adopt-existing-repo.py` and `check-adoption-integrity.py`
   must exit non-zero, and the blocker must be readable in their output.
3. smoke command detected but failing -- NOT an integrity failure: both
   scripts must exit 0, but the generated report / `check-adoption-integrity
   --json` output must carry an explicit, non-empty warning for the failed
   native test.
4. smoke command undetected -- same exit-0-with-explicit-warning contract,
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


def scenario_smoke_failing_command(root: Path) -> None:
    """Native test command detected but fails -- NOT an integrity failure.

    Exit codes for both scripts must stay 0; the report and
    `check-adoption-integrity --json` output must carry an explicit,
    non-empty warning (C1/C2/C3, open question 5).
    """
    target = root / "smoke-fail-existing"
    init_repo(target)
    write(target / "README.md", "# Smoke Fail Repo\n")
    write(
        target / "tests" / "test_broken.py",
        "def test_broken():\n    assert 1 == 2, 'intentionally broken for the smoke fixture'\n",
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
        scenario_smoke_failing_command(root)
        scenario_smoke_undetected(root)
    print("[adoption-smoke] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
