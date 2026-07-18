#!/usr/bin/env python3
"""Synthetic regression for the repo-controlled half of Codex hook trust."""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
PATH_RE = re.compile(r"(?:\.claude/hooks|scripts)/[A-Za-z0-9_./-]+\.py")


def run(
    repo: Path,
    *args: str,
    payload: str | None = None,
    bundle_env: str | None = None,
) -> subprocess.CompletedProcess[str]:
    env = None
    if bundle_env is not None:
        import os

        env = os.environ.copy()
        env["CODEX_HOOK_BUNDLE_SHA"] = bundle_env
    return subprocess.run(
        [sys.executable, "scripts/check-codex-hook-runtime.py", *args],
        cwd=repo,
        input=payload,
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )


def fail(message: str, proc: subprocess.CompletedProcess[str] | None = None) -> int:
    print(f"[codex-hook-trust-smoke] FAIL: {message}")
    if proc is not None:
        print(proc.stdout)
        print(proc.stderr)
    return 1


def referenced_paths() -> set[str]:
    config = tomllib.loads((REPO / ".codex/config.toml").read_text(encoding="utf-8"))
    paths = {"scripts/check-codex-hook-runtime.py", ".codex/config.toml"}
    for groups in (config.get("hooks") or {}).values():
        if not isinstance(groups, list):
            continue
        for group in groups:
            for hook in group.get("hooks") or []:
                paths.update(PATH_RE.findall(str(hook.get("command", ""))))
    return paths


def materialize(target: Path) -> None:
    for rel in referenced_paths():
        src = REPO / rel
        dst = target / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="codex-hook-trust-") as tmp:
        target = Path(tmp)
        materialize(target)

        check = run(target, "--check")
        if check.returncode != 0:
            return fail("current bundle should pass --check", check)

        before = run(target, "--status")
        if before.returncode != 2 or "UNTRUSTED_OR_NOT_LOADED" not in before.stdout:
            return fail("missing receipt must not report trusted", before)

        receipt = run(
            target,
            "--write-receipt",
            payload='{"hook_event_name":"SessionStart","session_id":"smoke-session"}',
            bundle_env=check.stdout.strip().rsplit(" ", 1)[-1],
        )
        if receipt.returncode != 0:
            return fail("synthetic SessionStart receipt should be writable", receipt)

        active = run(target, "--status")
        if active.returncode != 0 or "TRUSTED_AND_LOADED" not in active.stdout:
            return fail("matching receipt should prove the repo hook executed", active)

        changed = target / ".claude/hooks/pre_tool_guard.py"
        changed.write_text(changed.read_text(encoding="utf-8") + "\n# smoke mutation\n", encoding="utf-8")
        stale_bundle = run(target, "--check")
        if stale_bundle.returncode == 0:
            return fail("hook script change must invalidate bundle", stale_bundle)

        refreshed = run(target, "--refresh-bundle")
        if refreshed.returncode != 0:
            return fail("bundle refresh should succeed", refreshed)
        stale_receipt = run(target, "--status")
        if stale_receipt.returncode != 2 or "STALE_OR_INVALID" not in stale_receipt.stdout:
            return fail("old receipt must not survive hook bundle change", stale_receipt)

    print("[codex-hook-trust-smoke] PASS: untrusted -> loaded -> changed/stale")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
