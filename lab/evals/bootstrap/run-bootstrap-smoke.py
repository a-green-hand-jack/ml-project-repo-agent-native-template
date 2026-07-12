#!/usr/bin/env python3
"""Synthetic smoke test for bootstrap-project.py.

Materializes this template's own tracked tree into a fresh throwaway Git
repo (simulating a repo freshly derived via "Use this template"), then
exercises `scripts/bootstrap-project.py` against it: idempotency, origin
conflict (default reject / --force override), and the three static
validators inside the bootstrapped repo.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
ORIGIN = "example-owner/example-template"
OTHER_ORIGIN = "other-owner/other-template"


def run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, check=False)


def fail(label: str, proc: subprocess.CompletedProcess[str]) -> int:
    print(f"[bootstrap-smoke] FAIL: {label}")
    print("$ " + " ".join(proc.args) if isinstance(proc.args, list) else str(proc.args))
    print(proc.stdout)
    print(proc.stderr)
    return 1


def tracked_files(root: Path) -> list[str]:
    proc = subprocess.run(
        ["git", "ls-files", "-z"], cwd=root, capture_output=True, check=True
    )
    return [p.decode("utf-8") for p in proc.stdout.split(b"\0") if p]


def materialize_template(target: Path) -> None:
    target.mkdir(parents=True)
    for rel in tracked_files(REPO):
        src = REPO / rel
        if not src.is_file():
            continue
        dst = target / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(src.read_bytes())


def git_init(target: Path) -> None:
    for cmd in (
        ["git", "init", "-q"],
        ["git", "config", "user.email", "bootstrap-smoke@example.test"],
        ["git", "config", "user.name", "Bootstrap Smoke"],
        ["git", "add", "."],
        ["git", "commit", "-q", "-m", "materialize template scaffold"],
    ):
        proc = run(cmd, target)
        if proc.returncode != 0:
            raise SystemExit(fail(f"git_init step {cmd}", proc))


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="bootstrap-smoke-") as tmp:
        target = Path(tmp) / "new-project"
        materialize_template(target)
        git_init(target)

        bootstrap = REPO / "scripts" / "bootstrap-project.py"

        first = run([sys.executable, str(bootstrap), str(target), "--origin", ORIGIN], REPO)
        if first.returncode != 0:
            return fail("first run should succeed and create .template.toml", first)
        if "created" not in first.stdout:
            return fail("first run should report .template.toml: created", first)

        template_toml = target / ".template.toml"
        if not template_toml.exists():
            print("[bootstrap-smoke] FAIL: .template.toml missing after first run")
            return 1

        second = run([sys.executable, str(bootstrap), str(target), "--origin", ORIGIN], REPO)
        if second.returncode != 0:
            return fail("second run with same --origin should be idempotent (exit 0)", second)
        if "confirmed" not in second.stdout:
            return fail("second run should report .template.toml: confirmed", second)

        conflict = run(
            [sys.executable, str(bootstrap), str(target), "--origin", OTHER_ORIGIN], REPO
        )
        if conflict.returncode == 0:
            return fail("origin mismatch without --force should exit non-zero", conflict)
        toml_after_conflict = template_toml.read_text(encoding="utf-8")
        if ORIGIN not in toml_after_conflict:
            print("[bootstrap-smoke] FAIL: origin mismatch run mutated .template.toml without --force")
            return 1

        forced = run(
            [sys.executable, str(bootstrap), str(target), "--origin", OTHER_ORIGIN, "--force"],
            REPO,
        )
        if forced.returncode != 0:
            return fail("forced origin override should succeed", forced)
        if "overwritten" not in forced.stdout:
            return fail("forced run should report .template.toml: overwritten", forced)

        restore = run(
            [sys.executable, str(bootstrap), str(target), "--origin", ORIGIN, "--force"], REPO
        )
        if restore.returncode != 0:
            return fail("restoring original origin with --force should succeed", restore)

        for script, args in (
            ("validate-governance.py", ["--strict"]),
            ("check-agent-harness.py", ["--strict"]),
            ("sync-codex-adapters.py", ["--check"]),
        ):
            proc = run([sys.executable, str(target / "scripts" / script), *args], target)
            if proc.returncode != 0:
                return fail(f"{script} should be green inside bootstrapped repo", proc)

        report_path = target / "lab" / "docs" / "audits" / "template-bootstrap-report.md"
        if not report_path.exists():
            print("[bootstrap-smoke] FAIL: missing template-bootstrap-report.md")
            return 1

    print("[bootstrap-smoke] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
