#!/usr/bin/env python3
"""Synthetic fault-injection smoke for scripts/template-sync.py (issue #35).

Builds a throwaway upstream template + downstream repo pair in a temp dir and
drives the *real* `scripts/template-sync.py` (copied into the synthetic
downstream, so its module-level `DOWNSTREAM = __file__.parent.parent` resolves
to the temp repo). The synthetic downstream ships stub
`sync-codex-adapters.py` / `validate-governance.py` whose exit codes the
fixture controls, so generator/validator success and failure are injectable
end-to-end.

Scenarios (each asserts the P0 transactional contract of issue #35):

- happy: five path classes handled correctly (framework overwrite / identical
  framework left alone / generated NOT raw-copied but generator rebuild runs /
  project bytes preserved / scaffold created when missing and kept when
  present / merge sentinel block replaced with the surrounding tail
  preserved), version advances atomically to the upstream version, receipt
  result=pass with a consistent source/from-to/manifest/stages, then an
  immediate rerun is idempotent (still pass, version stays put);
- generator_fail: generator stub exits 1 -> process non-zero, receipt
  result=partial, `.template.toml` STILL the old version (the exact bug this
  issue fixes: version must not advance before generated rebuild succeeds);
- validator_fail: validator stub exits 1 -> process non-zero, receipt
  result=partial, version unchanged, stages.validate=fail;
- warnings: an unclassified upstream file and a merge file with no sentinel
  block -> receipt result=partial (never pass) with explicit warnings; version
  still advances because the validator passed, but the honest signal is
  partial, not pass;
- timeout_unknown: a validator that never returns within --timeout yields
  receipt result=unknown (never pass), keeps the old version, and exits
  non-zero;
- major_gate: a MAJOR jump without --allow-major is a strict pre-write no-op
  (exit 2, version untouched, no receipt written); with --allow-major it
  proceeds and advances;
- atomic_write (in-process): monkeypatch os.replace to fail during the version
  write and assert `.template.toml` keeps the old, still-parseable value with
  no orphan temp file — a version-write interruption never leaves a half row.
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "scripts" / "template-sync.py"

GEN_OK = "import sys\nprint('[stub-gen] ok')\nsys.exit(0)\n"
GEN_FAIL = "import sys\nprint('[stub-gen] boom')\nsys.exit(1)\n"
VAL_OK = "import sys\nprint('[stub-val] ok')\nsys.exit(0)\n"
VAL_FAIL = "import sys\nprint('[stub-val] boom')\nsys.exit(1)\n"
VAL_SLOW = "import time\ntime.sleep(30)\n"  # exceeds the injected --timeout -> unknown

MANIFEST = """\
[[rule]]
glob = ".template.toml"
kind = "project"
[[rule]]
glob = "VERSION"
kind = "framework"
[[rule]]
glob = "template-manifest.toml"
kind = "framework"
[[rule]]
glob = "fw/**"
kind = "framework"
[[rule]]
glob = "gen/**"
kind = "generated"
[[rule]]
glob = "proj/**"
kind = "project"
[[rule]]
glob = "scaf/**"
kind = "scaffold"
[[rule]]
glob = "merge.md"
kind = "merge"
[[rule]]
glob = "merge-nosentinel.md"
kind = "merge"
"""

SENT_BEGIN = "<!-- template:begin -->"
SENT_END = "<!-- template:end -->"


def fail(label: str, proc: subprocess.CompletedProcess[str] | None = None) -> int:
    print(f"[template-sync-smoke] FAIL: {label}")
    if proc is not None:
        print("$ " + (" ".join(map(str, proc.args)) if isinstance(proc.args, list) else str(proc.args)))
        print(proc.stdout)
        print(proc.stderr)
    return 1


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_upstream(root: Path, version: str, *, with_warnings: bool = False) -> None:
    write(root / "VERSION", version + "\n")
    write(root / "template-manifest.toml", MANIFEST)
    write(root / "fw" / "tool.txt", "new-fw\n")
    write(root / "fw" / "same.txt", "identical\n")
    write(root / "gen" / "adapter.txt", "GENERATED upstream, must not be raw-copied\n")
    write(root / "proj" / "keep.txt", "upstream project content (must be ignored)\n")
    write(root / "scaf" / "new.txt", "scaffold seed\n")
    write(root / "scaf" / "existing.txt", "upstream scaffold seed (must NOT overwrite)\n")
    write(root / "merge.md", f"UP-HEAD\n{SENT_BEGIN}\nUPSTREAM BLOCK v2\n{SENT_END}\nUP-TAIL\n")
    if with_warnings:
        write(root / "unknown" / "orphan.txt", "no rule classifies me\n")
        write(root / "merge-nosentinel.md", "no sentinel here at all\n")


def build_downstream(root: Path, version: str, *, gen: str, val: str) -> None:
    (root / "scripts").mkdir(parents=True, exist_ok=True)
    shutil.copy2(SCRIPT, root / "scripts" / "template-sync.py")
    write(root / "scripts" / "sync-codex-adapters.py", gen)
    write(root / "scripts" / "validate-governance.py", val)
    write(root / ".template.toml", f'[template]\norigin = "acme/downstream"\nversion = "{version}"\n')
    # framework: one stale (to overwrite), one identical (must be left alone).
    write(root / "fw" / "tool.txt", "old-fw\n")
    write(root / "fw" / "same.txt", "identical\n")
    # project: downstream-owned bytes that must survive untouched.
    write(root / "proj" / "keep.txt", "DOWNSTREAM OWNED — do not touch\n")
    # scaffold: one already present (keep), scaf/new.txt intentionally absent (create).
    write(root / "scaf" / "existing.txt", "downstream custom scaffold\n")
    # merge: old block + downstream tail that must be preserved.
    write(root / "merge.md", f"DOWN-HEAD\n{SENT_BEGIN}\nDOWNSTREAM BLOCK v1\n{SENT_END}\nDOWN-TAIL\n")


def run_sync(downstream: Path, upstream: Path, receipt: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(downstream / "scripts" / "template-sync.py"),
         "--from", str(upstream), "--receipt", str(receipt), *extra],
        cwd=downstream, text=True, capture_output=True, check=False,
    )


def version_of(downstream: Path) -> str:
    return tomllib.loads((downstream / ".template.toml").read_text(encoding="utf-8"))["template"]["version"]


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def check_happy_and_idempotent(tmp: Path) -> int:
    up = tmp / "up"
    down = tmp / "down"
    receipt = tmp / "receipt.json"
    build_upstream(up, "v1.1.0")
    build_downstream(down, "v1.0.0", gen=GEN_OK, val=VAL_OK)

    proc = run_sync(down, up, receipt)
    if proc.returncode != 0:
        return fail("happy path should exit 0", proc)
    r = read_json(receipt)
    if r["result"] != "pass":
        return fail(f"happy path receipt result should be pass, got {r['result']}", proc)
    if version_of(down) != "v1.1.0":
        return fail(f"version should advance to v1.1.0, got {version_of(down)}", proc)
    if r["committed_version"] != "v1.1.0" or r["from_version"] != "v1.0.0" or not r["version_advanced"]:
        return fail(f"receipt version fields inconsistent: {r}", proc)
    if not r["source"].get("digest", "").startswith("sha256:"):
        return fail(f"non-git upstream should carry a sha256 source digest, got {r['source']}", proc)
    stages = r["stages"]
    if not all(stages[k] == "ok" for k in ("apply", "generated_rebuild", "validate", "commit_version")):
        return fail(f"all stages should be ok on happy path, got {stages}", proc)
    if r["manifest"]["missing"] or r["manifest"]["unexpected"]:
        return fail(f"happy manifest should have no missing/unexpected, got {r['manifest']}", proc)

    # five-class assertions
    if (down / "fw" / "tool.txt").read_text() != "new-fw\n":
        return fail("framework positive: fw/tool.txt should be overwritten")
    if "fw/same.txt" in r["manifest"]["actual"]:
        return fail("framework negative: identical fw/same.txt should not be rewritten")
    if (down / "gen" / "adapter.txt").exists():
        return fail("generated negative: gen/adapter.txt must NOT be raw-copied downstream")
    if (down / "proj" / "keep.txt").read_text() != "DOWNSTREAM OWNED — do not touch\n":
        return fail("project negative: downstream proj/keep.txt bytes must be preserved")
    if not (down / "scaf" / "new.txt").exists():
        return fail("scaffold positive: scaf/new.txt should be created when missing")
    if (down / "scaf" / "existing.txt").read_text() != "downstream custom scaffold\n":
        return fail("scaffold negative: existing scaffold must be kept, not overwritten")
    merged = (down / "merge.md").read_text()
    if "UPSTREAM BLOCK v2" not in merged:
        return fail("merge positive: sentinel block should be replaced with upstream block")
    if "DOWN-HEAD" not in merged or "DOWN-TAIL" not in merged:
        return fail("merge negative: downstream content outside the sentinel must be preserved")

    # idempotent rerun
    proc2 = run_sync(down, up, receipt)
    if proc2.returncode != 0:
        return fail("idempotent rerun should exit 0", proc2)
    r2 = read_json(receipt)
    if r2["result"] != "pass" or version_of(down) != "v1.1.0":
        return fail(f"idempotent rerun should stay pass at v1.1.0, got {r2['result']}/{version_of(down)}", proc2)
    if r2["manifest"]["actual"]:
        return fail(f"idempotent rerun should write nothing, wrote {r2['manifest']['actual']}", proc2)
    return 0


def check_generator_fail(tmp: Path) -> int:
    up = tmp / "up-gf"
    down = tmp / "down-gf"
    receipt = tmp / "receipt-gf.json"
    build_upstream(up, "v1.1.0")
    build_downstream(down, "v1.0.0", gen=GEN_FAIL, val=VAL_OK)

    proc = run_sync(down, up, receipt)
    if proc.returncode == 0:
        return fail("generator failure must make the process exit non-zero", proc)
    if version_of(down) != "v1.0.0":
        return fail(f"generator failure must NOT advance version, got {version_of(down)}", proc)
    r = read_json(receipt)
    if r["result"] != "partial":
        return fail(f"generator failure receipt should be partial, got {r['result']}", proc)
    if r["committed_version"] != "v1.0.0" or r["version_advanced"]:
        return fail(f"receipt must report version kept at v1.0.0, got {r}", proc)
    if r["stages"]["generated_rebuild"] != "fail" or r["stages"]["commit_version"] != "skipped":
        return fail(f"stages should show generated_rebuild=fail, commit skipped, got {r['stages']}", proc)
    if not r["failure"] or r["failure"]["stage"] != "generated_rebuild" or not r["failure"]["rerun_command"]:
        return fail(f"failure block should name generated_rebuild + a rerun command, got {r.get('failure')}", proc)
    # framework file WAS written (partial physical state) but version stayed old — the core fix.
    if (down / "fw" / "tool.txt").read_text() != "new-fw\n":
        return fail("generator-fail partial state should still show the applied framework write")
    return 0


def check_validator_fail(tmp: Path) -> int:
    up = tmp / "up-vf"
    down = tmp / "down-vf"
    receipt = tmp / "receipt-vf.json"
    build_upstream(up, "v1.1.0")
    build_downstream(down, "v1.0.0", gen=GEN_OK, val=VAL_FAIL)

    proc = run_sync(down, up, receipt)
    if proc.returncode == 0:
        return fail("validator failure must make the process exit non-zero", proc)
    if version_of(down) != "v1.0.0":
        return fail(f"validator failure must NOT advance version, got {version_of(down)}", proc)
    r = read_json(receipt)
    if r["result"] != "partial":
        return fail(f"validator failure receipt should be partial, got {r['result']}", proc)
    if r["stages"]["validate"] != "fail" or r["stages"]["commit_version"] != "skipped":
        return fail(f"stages should show validate=fail, commit skipped, got {r['stages']}", proc)
    if not r["failure"] or r["failure"]["stage"] != "validate":
        return fail(f"failure block should name validate, got {r.get('failure')}", proc)
    return 0


def check_warnings_partial(tmp: Path) -> int:
    up = tmp / "up-w"
    down = tmp / "down-w"
    receipt = tmp / "receipt-w.json"
    build_upstream(up, "v1.1.0", with_warnings=True)
    build_downstream(down, "v1.0.0", gen=GEN_OK, val=VAL_OK)

    proc = run_sync(down, up, receipt)
    if proc.returncode != 0:
        return fail("warnings scenario should still exit 0 (validator passed)", proc)
    r = read_json(receipt)
    if r["result"] != "partial":
        return fail(f"unclassified/no-sentinel should yield partial, not pass, got {r['result']}", proc)
    if version_of(down) != "v1.1.0":
        return fail("with a passing validator the version still advances (flagged partial)", proc)
    if "unknown/orphan.txt" not in r["classification"]["unclassified"]:
        return fail(f"unclassified upstream file should be recorded, got {r['classification']}", proc)
    if not any("unclassified" in w for w in r["warnings"]):
        return fail(f"warnings should include the unclassified entry, got {r['warnings']}", proc)
    if not any("merge" in w for w in r["warnings"]):
        return fail(f"warnings should include the no-sentinel merge entry, got {r['warnings']}", proc)
    # the no-sentinel merge file must be left untouched (not clobbered).
    if (down / "merge-nosentinel.md").exists():
        return fail("no-sentinel merge file must be skipped, not created downstream")
    return 0


def check_timeout_unknown(tmp: Path) -> int:
    """A validator that never returns within --timeout must yield result=unknown
    (never pass), keep the old version, and exit non-zero (issue #35: timeout /
    interrupt / unknown must not be shown as pass)."""
    up = tmp / "up-to"
    down = tmp / "down-to"
    receipt = tmp / "receipt-to.json"
    build_upstream(up, "v1.1.0")
    build_downstream(down, "v1.0.0", gen=GEN_OK, val=VAL_SLOW)

    proc = run_sync(down, up, receipt, "--timeout", "1")
    if proc.returncode == 0:
        return fail("a validator timeout must make the process exit non-zero", proc)
    if version_of(down) != "v1.0.0":
        return fail(f"a validator timeout must NOT advance version, got {version_of(down)}", proc)
    r = read_json(receipt)
    if r["result"] != "unknown":
        return fail(f"timeout must be recorded as unknown, never pass, got {r['result']}", proc)
    if r["stages"]["validate"] != "timeout" or r["stages"]["commit_version"] != "skipped":
        return fail(f"stages should show validate=timeout, commit skipped, got {r['stages']}", proc)
    if not r["failure"] or r["failure"]["stage"] != "validate":
        return fail(f"failure block should name validate, got {r.get('failure')}", proc)
    return 0


def check_major_gate(tmp: Path) -> int:
    up = tmp / "up-mj"
    down = tmp / "down-mj"
    receipt = tmp / "receipt-mj.json"
    build_upstream(up, "v2.0.0")
    build_downstream(down, "v1.0.0", gen=GEN_OK, val=VAL_OK)

    blocked = run_sync(down, up, receipt)
    if blocked.returncode != 2:
        return fail("MAJOR without --allow-major should exit 2", blocked)
    if version_of(down) != "v1.0.0":
        return fail("MAJOR gate must not advance version", blocked)
    if receipt.exists():
        return fail("MAJOR gate is a strict pre-write no-op: no receipt should be written", blocked)
    if (down / "fw" / "tool.txt").read_text() != "old-fw\n":
        return fail("MAJOR gate must not touch any files before the STOP")

    allowed = run_sync(down, up, receipt, "--allow-major")
    if allowed.returncode != 0:
        return fail("MAJOR with --allow-major should proceed and exit 0", allowed)
    if version_of(down) != "v2.0.0":
        return fail(f"MAJOR with --allow-major should advance to v2.0.0, got {version_of(down)}", allowed)
    return 0


def check_atomic_write_fail(tmp: Path) -> int:
    """In-process: os.replace failure during the version write leaves the old,
    parseable `.template.toml` and no orphan temp file (issue #35 acceptance:
    a version-write interruption never leaves a half row / unparseable TOML)."""
    spec = importlib.util.spec_from_file_location("template_sync_mod", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    # Register before exec so @dataclass annotation resolution can find the module.
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)

    target = tmp / "atomic" / ".template.toml"
    write(target, '[template]\norigin = "acme/downstream"\nversion = "v1.0.0"\n')
    extra = {"origin": "acme/downstream", "version": "v1.0.0"}

    orig_replace = mod.os.replace

    def boom(_a: object, _b: object) -> None:
        raise OSError("injected os.replace failure")

    mod.os.replace = boom
    try:
        raised = False
        try:
            mod.write_template_version("acme/downstream", "v1.1.0", extra, target=target)
        except OSError:
            raised = True
        if not raised:
            return fail("atomic write should surface the os.replace failure")
    finally:
        mod.os.replace = orig_replace

    parsed = tomllib.loads(target.read_text(encoding="utf-8"))
    if parsed["template"]["version"] != "v1.0.0":
        return fail(f"failed version write must keep old value, got {parsed['template']['version']}")
    leftovers = list(target.parent.glob(".template.toml.tmp-*"))
    if leftovers:
        return fail(f"failed version write must not leave an orphan temp file: {leftovers}")

    # positive: a normal write replaces atomically and leaves no temp file.
    mod.write_template_version("acme/downstream", "v1.1.0", extra, target=target)
    if tomllib.loads(target.read_text(encoding="utf-8"))["template"]["version"] != "v1.1.0":
        return fail("normal atomic write should advance the version")
    if list(target.parent.glob(".template.toml.tmp-*")):
        return fail("successful atomic write should leave no temp file")
    return 0


def main() -> int:
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPO, text=True, capture_output=True, check=False
    ).stdout.strip()
    print(f"[template-sync-smoke] tested script: {SCRIPT} @ {head or 'unknown'}")
    with tempfile.TemporaryDirectory(prefix="template-sync-smoke-") as tmp_str:
        tmp = Path(tmp_str)
        for check in (
            check_happy_and_idempotent,
            check_generator_fail,
            check_validator_fail,
            check_warnings_partial,
            check_timeout_unknown,
            check_major_gate,
            check_atomic_write_fail,
        ):
            rc = check(tmp)
            if rc != 0:
                return rc
    print("[template-sync-smoke] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
