#!/usr/bin/env python3
"""Synthetic smoke test for bootstrap-project.py.

Materializes the *candidate commit* (`git archive HEAD` — not `main`, so the
tested tree is exactly the implementation under review; the tested commit
hash is printed as evidence) into a fresh throwaway Git repo, simulating a
repo freshly derived via "Use this template". It then exercises the real
README path: the derived repo runs *its own* copy of
`scripts/bootstrap-project.py` against itself (self-bootstrap, target `.`),
asserting:

- first run creates `.template.toml`;
- second run is a confirming run: exit 0, `confirmed`, `state.json` and
  `template-bootstrap-report.md` stay bit-for-bit identical, and
  `run-log.jsonl` grows by exactly one append-only audit row with
  `content_changed: false` (two-layer idempotency semantics, plan A1);
- origin conflict without `--force` exits non-zero without mutation;
  `--force` overwrites;
- inside the bootstrapped repo, `validate-governance.py --strict`,
  `check-agent-harness.py --strict`, `sync-codex-adapters.py --check` are
  all green;
- (negative) a copy without `.githooks/` fails bootstrap with a non-zero
  exit — plan A2 mandates core.hooksPath, missing must not be "skipped";
- (negative) a target whose *origin* remote points at the `--origin` slug
  (i.e. a checkout of the upstream template itself) is refused, and the
  refusal is a strict no-op: a full before/after tree snapshot (including
  `.git/config` and the core.hooksPath value) shows zero changes. The
  fixture URL uses a different case + `.git` suffix to also exercise slug
  normalization;
- (positive) a legitimately derived repo whose *upstream* remote points back
  at the template (origin = its own slug) is NOT refused — only the identity
  remote (`origin`) participates in the refusal criterion.
- (issue #67) `.codex/agents/**` + `.agents/skills/**` stripped from the base
  commit before `git init` — so the bootstrap-generated adapters land on
  disk correct but genuinely untracked, the real adoption-time bug — and
  `validate-governance.py --strict` / `check-agent-harness.py --strict` /
  `sync-codex-adapters.py --check` are still all green (auto-detected
  `context=downstream`); the same untracked fixture under an explicit
  `--context source` still fails (#61's tracked exact-set is not globally
  relaxed); disk-based missing/stale/unexpected adapters still fail
  regardless of context; a malformed or symlinked `.template.toml` role
  anchor fails closed under `--context auto` rather than silently
  downgrading.

Uncommitted worktree changes are NOT covered (the target is built from
HEAD): commit first, then run this smoke.
"""
from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
ORIGIN = "example-owner/example-template"
OTHER_ORIGIN = "other-owner/other-template"
STATE_DIR = Path("lab/docs/audits/template-bootstrap/state")
REPORT_REL = Path("lab/docs/audits/template-bootstrap-report.md")


def run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, check=False)


def fail(label: str, proc: subprocess.CompletedProcess[str] | None = None) -> int:
    print(f"[bootstrap-smoke] FAIL: {label}")
    if proc is not None:
        print("$ " + (" ".join(proc.args) if isinstance(proc.args, list) else str(proc.args)))
        print(proc.stdout)
        print(proc.stderr)
    return 1


def candidate_commit() -> str:
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPO, text=True, capture_output=True, check=True
    ).stdout.strip()
    dirty = subprocess.run(
        ["git", "status", "--porcelain"], cwd=REPO, text=True, capture_output=True, check=True
    ).stdout.strip()
    if dirty:
        print(
            "[bootstrap-smoke] WARN: worktree has uncommitted changes; "
            "the smoke tests HEAD, not the dirty worktree"
        )
    return head


def materialize_template(target: Path) -> None:
    """Materialize the candidate commit (HEAD) — not main, not the worktree."""
    target.mkdir(parents=True)
    archive = subprocess.run(
        ["git", "archive", "--format=tar", "HEAD"], cwd=REPO, capture_output=True, check=True
    )
    with tarfile.open(fileobj=io.BytesIO(archive.stdout)) as tar:
        tar.extractall(target, filter="data")


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


def self_bootstrap(target: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """The real README path: the derived repo runs its OWN script on itself."""
    return run([sys.executable, "scripts/bootstrap-project.py", ".", *args], target)


def check_idempotency(target: Path) -> int:
    """First/second run + strict before/after file-state snapshot (MAJOR-2)."""
    state_json = target / STATE_DIR / "state.json"
    run_log = target / STATE_DIR / "run-log.jsonl"
    report_md = target / REPORT_REL

    first = self_bootstrap(target, "--origin", ORIGIN)
    if first.returncode != 0:
        return fail("first self-bootstrap run should succeed and create .template.toml", first)
    if "created" not in first.stdout:
        return fail("first run should report .template.toml: created", first)
    if not (target / ".template.toml").exists():
        return fail(".template.toml missing after first run")
    for p in (state_json, run_log, report_md):
        if not p.exists():
            return fail(f"missing {p.relative_to(target)} after first run")

    snapshots = {p: p.read_bytes() for p in (state_json, report_md)}
    log_before = run_log.read_text(encoding="utf-8").splitlines()
    if len(log_before) != 1:
        return fail(f"run-log should have exactly 1 row after first run, got {len(log_before)}")

    second = self_bootstrap(target, "--origin", ORIGIN)
    if second.returncode != 0:
        return fail("second run with same --origin should be idempotent (exit 0)", second)
    if "confirmed" not in second.stdout:
        return fail("second run should report .template.toml: confirmed", second)
    for p, before in snapshots.items():
        if p.read_bytes() != before:
            return fail(
                f"{p.relative_to(target)} was rewritten by a confirming run "
                "(content-stable state/report violated)",
                second,
            )
    log_after = run_log.read_text(encoding="utf-8").splitlines()
    if len(log_after) != 2 or log_after[0] != log_before[0]:
        return fail(
            "run-log should grow by exactly one appended row on the second run "
            f"(before={len(log_before)}, after={len(log_after)})",
            second,
        )
    row = json.loads(log_after[1])
    if row.get("content_changed") is not False or row.get("template_toml_status") != "confirmed":
        return fail(f"second run-log row should audit a confirming run, got {row}", second)
    return 0


def check_origin_conflict(target: Path) -> int:
    template_toml = target / ".template.toml"
    conflict = self_bootstrap(target, "--origin", OTHER_ORIGIN)
    if conflict.returncode == 0:
        return fail("origin mismatch without --force should exit non-zero", conflict)
    if ORIGIN not in template_toml.read_text(encoding="utf-8"):
        return fail("origin mismatch run mutated .template.toml without --force")

    forced = self_bootstrap(target, "--origin", OTHER_ORIGIN, "--force")
    if forced.returncode != 0:
        return fail("forced origin override should succeed", forced)
    if "overwritten" not in forced.stdout:
        return fail("forced run should report .template.toml: overwritten", forced)

    restore = self_bootstrap(target, "--origin", ORIGIN, "--force")
    if restore.returncode != 0:
        return fail("restoring original origin with --force should succeed", restore)
    return 0


def check_validators(target: Path) -> int:
    for script, args in (
        ("validate-governance.py", ["--strict"]),
        ("check-agent-harness.py", ["--strict"]),
        ("sync-codex-adapters.py", ["--check"]),
    ):
        proc = run([sys.executable, str(target / "scripts" / script), *args], target)
        if proc.returncode != 0:
            return fail(f"{script} should be green inside bootstrapped repo", proc)
    return 0


def check_missing_githooks_fails(tmp: Path) -> int:
    """Negative (MAJOR-3): missing .githooks must be a hard failure."""
    target = tmp / "no-githooks"
    materialize_template(target)
    shutil.rmtree(target / ".githooks")
    git_init(target)
    proc = self_bootstrap(target, "--origin", ORIGIN)
    if proc.returncode == 0:
        return fail("bootstrap without .githooks should exit non-zero, not skip", proc)
    if "core.hooksPath: failed" not in proc.stdout:
        return fail("missing .githooks should report core.hooksPath: failed", proc)
    return 0


def tree_snapshot(target: Path) -> dict[str, bytes]:
    """Full content snapshot of the target tree, `.git/` included, so the
    refusal path can be asserted to be a strict zero-change no-op (round-2
    MINOR-2: asserting only `.template.toml` absence was too weak)."""
    snap: dict[str, bytes] = {}
    for p in sorted(target.rglob("*")):
        if p.is_symlink():
            snap[str(p.relative_to(target))] = p.readlink().as_posix().encode()
        elif p.is_file():
            snap[str(p.relative_to(target))] = p.read_bytes()
    return snap


def check_upstream_refusal(tmp: Path) -> int:
    """Negative (round-1 MAJOR-1 guard): a checkout of the upstream template
    itself (*origin* remote slug == --origin) must be refused, and the
    refusal must leave the target tree completely untouched. The remote URL
    deliberately differs in case and carries a `.git` suffix to exercise
    hosting-platform slug normalization (round-2 MAJOR-1)."""
    target = tmp / "upstream-checkout"
    materialize_template(target)
    git_init(target)
    proc = run(
        ["git", "remote", "add", "origin", f"https://GitHub.com/{ORIGIN.upper()}.git"], target
    )
    if proc.returncode != 0:
        return fail("git remote add for upstream-refusal fixture", proc)

    before = tree_snapshot(target)
    hooks_before = run(["git", "config", "--get", "core.hooksPath"], target)

    refused = self_bootstrap(target, "--origin", ORIGIN)
    if refused.returncode == 0:
        return fail("bootstrapping the upstream template itself should be refused", refused)
    if "upstream template" not in refused.stderr:
        return fail("refusal message should name the upstream-template guard", refused)

    after = tree_snapshot(target)
    if after != before:
        changed = sorted(
            (set(before) ^ set(after))
            | {k for k in set(before) & set(after) if before[k] != after[k]}
        )
        return fail(
            "upstream refusal must be a strict no-op, but the tree changed: "
            f"{changed}",
            refused,
        )
    hooks_after = run(["git", "config", "--get", "core.hooksPath"], target)
    if (hooks_after.returncode, hooks_after.stdout) != (hooks_before.returncode, hooks_before.stdout):
        return fail(
            "upstream refusal must not touch core.hooksPath "
            f"(before={hooks_before.stdout!r}, after={hooks_after.stdout!r})",
            refused,
        )
    return 0


def check_derived_with_upstream_remote(tmp: Path) -> int:
    """Positive (round-2 MAJOR-1): a legitimately derived repo whose
    *upstream* remote points back at the template — while `origin` is its own
    slug — must NOT be refused; only the identity remote participates."""
    target = tmp / "derived-with-upstream"
    materialize_template(target)
    git_init(target)
    for name, url in (
        ("origin", "https://github.com/acme/derived-project.git"),
        ("upstream", f"https://github.com/{ORIGIN}.git"),
    ):
        proc = run(["git", "remote", "add", name, url], target)
        if proc.returncode != 0:
            return fail(f"git remote add {name} for derived-with-upstream fixture", proc)
    proc = self_bootstrap(target, "--origin", ORIGIN)
    if proc.returncode != 0:
        return fail(
            "derived repo with an upstream remote pointing at the template "
            "must not be refused (origin remote is its own slug)",
            proc,
        )
    if not (target / ".template.toml").exists():
        return fail(".template.toml missing after derived-with-upstream bootstrap")
    return 0


def build_untracked_adapters_repo(target: Path) -> None:
    """Materialize the real template, then strip the generated adapter
    namespaces BEFORE the base commit — so bootstrap's own generator
    regenerates them fresh, correct, and genuinely untracked (issue #67's
    exact adoption-time precondition, not a synthetic stand-in)."""
    materialize_template(target)
    shutil.rmtree(target / ".codex" / "agents")
    shutil.rmtree(target / ".agents" / "skills")
    git_init(target)


def sync_codex_check(target: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return run(
        [sys.executable, str(target / "scripts" / "sync-codex-adapters.py"), "--check", *extra],
        target,
    )


def check_untracked_generated_adapters(tmp: Path) -> int:
    """Issue #67: an adopted/bootstrapped downstream repo whose generated
    Codex adapters are correct, byte-matching, but never `git add`ed must
    pass the real harness — not be misreported as missing."""
    target = tmp / "untracked-adapters"
    build_untracked_adapters_repo(target)

    proc = self_bootstrap(target, "--origin", ORIGIN)
    if proc.returncode != 0:
        return fail("self-bootstrap over a base commit without generated adapters should succeed", proc)

    tracked = run(["git", "ls-files", "--", ".codex/agents", ".agents/skills"], target)
    if tracked.stdout.strip():
        return fail(f"fixture precondition violated — adapters already tracked: {tracked.stdout}", tracked)
    agent_tomls = sorted((target / ".codex" / "agents").glob("*.toml"))
    if not agent_tomls:
        return fail("bootstrap should have regenerated .codex/agents/*.toml on disk")
    status = run(["git", "status", "--porcelain"], target)
    if "?? .codex/agents/" not in status.stdout and ".codex/agents/" not in status.stdout:
        return fail(f"generated adapters should show untracked in git status, got: {status.stdout}", status)

    # the actual fix: real validators must be green despite untracked adapters.
    rc = check_validators(target)
    if rc != 0:
        return rc

    direct = sync_codex_check(target)
    if direct.returncode != 0 or "context=downstream" not in direct.stdout:
        return fail("direct --check (auto) should resolve and print context=downstream and pass", direct)

    # #61 must not be globally relaxed: explicit source context on this same
    # untracked-but-correct fixture must still fail the tracked exact-set gate.
    source_ctx = sync_codex_check(target, "--context", "source")
    if source_ctx.returncode == 0 or "context=source" not in source_ctx.stdout:
        return fail("explicit --context source on untracked adapters must still fail (#61 preserved)", source_ctx)

    # disk-based missing/stale/unexpected must still fail regardless of context.
    victim = agent_tomls[0]
    original = victim.read_bytes()

    victim.unlink()
    missing = sync_codex_check(target, "--context", "downstream")
    if missing.returncode == 0 or "missing generated adapter" not in missing.stdout:
        return fail("a genuinely missing generated adapter must still fail downstream context", missing)
    victim.write_bytes(original)

    victim.write_bytes(b"stale bytes\n")
    stale = sync_codex_check(target, "--context", "downstream")
    if stale.returncode == 0 or "stale generated adapter" not in stale.stdout:
        return fail("stale generated adapter content must still fail downstream context", stale)
    victim.write_bytes(original)

    rogue = target / ".codex" / "agents" / "rogue-unexpected.toml"
    rogue.write_text("rogue\n", encoding="utf-8")
    unexpected = sync_codex_check(target, "--context", "downstream")
    if unexpected.returncode == 0 or "unexpected generated adapter" not in unexpected.stdout:
        return fail("an unexpected rogue adapter must still fail downstream context", unexpected)
    rogue.unlink()

    clean = sync_codex_check(target)
    if clean.returncode != 0:
        return fail("fixture should be clean again after restoring the mutated adapter", clean)

    # malformed / symlink role anchor must fail closed under auto, never
    # silently downgrade to either a source or downstream PASS.
    anchor = target / ".template.toml"
    original_anchor = anchor.read_bytes()

    anchor.write_text("not valid toml {{{", encoding="utf-8")
    malformed = sync_codex_check(target)
    if malformed.returncode == 0 or "拒绝作为角色锚点" not in malformed.stdout:
        return fail("a malformed .template.toml anchor must fail closed under --context auto", malformed)

    anchor.unlink()
    os.symlink("/etc/hostname", anchor)
    symlinked = sync_codex_check(target)
    if symlinked.returncode == 0 or "symlink" not in symlinked.stdout:
        return fail("a symlinked .template.toml anchor must fail closed under --context auto", symlinked)
    anchor.unlink()
    anchor.write_bytes(original_anchor)

    restored = sync_codex_check(target)
    if restored.returncode != 0:
        return fail("fixture should pass again once a valid anchor is restored", restored)
    return 0


def main() -> int:
    head = candidate_commit()
    print(f"[bootstrap-smoke] tested commit (git archive HEAD): {head}")
    with tempfile.TemporaryDirectory(prefix="bootstrap-smoke-") as tmp_str:
        tmp = Path(tmp_str)
        target = tmp / "new-project"
        materialize_template(target)
        git_init(target)

        for check in (
            lambda: check_idempotency(target),
            lambda: check_origin_conflict(target),
            lambda: check_validators(target),
            lambda: check_missing_githooks_fails(tmp),
            lambda: check_upstream_refusal(tmp),
            lambda: check_derived_with_upstream_remote(tmp),
            lambda: check_untracked_generated_adapters(tmp),
        ):
            rc = check()
            if rc != 0:
                return rc

    print(f"[bootstrap-smoke] OK (tested commit {head})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
