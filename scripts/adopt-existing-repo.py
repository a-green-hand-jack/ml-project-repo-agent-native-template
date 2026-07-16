#!/usr/bin/env python3
"""Adopt an existing Git repo into this template shape.

The script is intentionally conservative:
- no deletes;
- no overwrites without first preserving the original file;
- no protected data/model/checkpoint byte moves;
- state is written into lab/docs/audits/template-adoption/state (or a
  /tmp fallback plus a blocker when that path, including a state-file
  leaf, crosses a symlink — see `state_root`). The fallback's absolute
  path and state-file leaves are also checked before use; an unsafe
  fallback fails closed instead of redirecting again.

Residual risk (accepted, review round 3): the symlink/containment checks
(lstat / resolve) and the writes that follow them (mkdir / copy2 / move)
are not atomic. Every "never writes through / never moves" statement in
this file therefore assumes the target repo is NOT being concurrently and
adversarially modified while a phase runs; adoption is a single-operator
migration tool, not a defense against a live attacker racing its checks.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType
from typing import Any

TEMPLATE_ROOT = Path(__file__).resolve().parent.parent


def _load_sibling(name: str) -> ModuleType:
    """Load a sibling script/module by file path (scripts/ has no
    __init__.py and most filenames are hyphenated, so a plain `import`
    across scripts doesn't work — same pattern as
    `check-adoption-integrity.py`'s `load_adopter()`)."""
    script = Path(__file__).resolve().with_name(f"{name}.py")
    spec = importlib.util.spec_from_file_location(name, script)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {script}")
    module = importlib.util.module_from_spec(spec)
    previous = sys.dont_write_bytecode
    try:
        sys.dont_write_bytecode = True
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


AGENT_SURFACE = _load_sibling("_agent_surface")
TEMPLATE_ANCHOR = _load_sibling("_template_anchor")

STATE_DIR = Path("lab/docs/audits/template-adoption/state")
REPORT_PATH = Path("lab/docs/audits/template-adoption-report.md")
PLAN_FILE = "adoption-plan.json"
BASELINE_FILE = "baseline.json"
LOG_FILE = "phase-log.jsonl"
PLAN_SCHEMA = "template-adoption-plan-v2"
LEGACY_PLAN_SCHEMA = "template-adoption-plan-v1"
STATE_FILES = (PLAN_FILE, BASELINE_FILE, LOG_FILE)

CONTROL_ITEMS = [
    ".template.toml",
    "AGENTS.md",
    "CLAUDE.md",
    "ANATOMY.md",
    "PROJECT.md",
    "DESIGN.md",
    "DECISIONS.md",
    "README.md",
    ".gitignore",
    ".githooks",
    ".github",
    ".reference-docs",
    ".agent",
    ".claude",
    # Codex adapters (generated from .claude/** by sync-codex-adapters.py):
    # required top-level entries per check-agent-harness.py's REQUIRED_TOP —
    # must be scaffolded alongside .claude for the double-agent-surface
    # postflight (B6/D2c) to have anything to report other than "missing".
    ".codex",
    ".agents",
    "human",
    "lab",
    "memory",
    "deliverables",
    "scripts",
    "plans",
]

ROOT_WHITELIST = {
    ".template.toml",
    "README.md",
    "PROJECT.md",
    "DECISIONS.md",
    "DESIGN.md",
    "AGENTS.md",
    "CLAUDE.md",
    "ANATOMY.md",
    ".gitignore",
    ".github",
    ".githooks",
    ".agent",
    ".claude",
    ".codex",
    ".agents",
    "human",
    "lab",
    "memory",
    "deliverables",
    "scripts",
    "plans",
    ".reference-docs",
    "LICENSE",
    "pyproject.toml",
    "uv.lock",
    ".python-version",
    ".pre-commit-config.yaml",
    "Makefile",
}

PROTECTED_PARTS = {
    ".env",
    "checkpoints",
    "wandb",
}
PROTECTED_PREFIXES = (
    ("lab", "data"),
    ("lab", "runs"),
    ("lab", "models"),
    ("lab", "infra", "private"),
)
LARGE_HASH_LIMIT = 25 * 1024 * 1024

EXCLUDE_DIR_NAMES = {
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
}
EXCLUDE_REL_PREFIXES = (
    ".claude/worktrees",
    "lab/docs/audits/template-adoption/state",
)


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_own_version() -> str:
    version_file = TEMPLATE_ROOT / "VERSION"
    if not version_file.is_file():
        raise SystemExit(f"template root missing VERSION: {version_file}")
    return version_file.read_text(encoding="utf-8").strip()


def rel_posix(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


class SymlinkOnPath(RuntimeError):
    """A segment on an intended write path (from the target root down to
    the leaf, lstat semantics) is a symlink. `rel` names the first
    offending segment, repo-root-relative."""

    def __init__(self, rel: str) -> None:
        super().__init__(rel)
        self.rel = rel


def safe_target_path(root: Path, *parts: str) -> Path:
    """Join `parts` onto `root`, lstat-checking EVERY intermediate segment
    and the leaf: the first symlink on the way raises `SymlinkOnPath`.

    Review round 3 BLOCKER-C: this is the single shared gate for all write
    paths into the target repo — state files (`state_root`), the report
    (`write_report`), the conflict archive (`unique_preserve_path`) and
    normalize's move destination. Checking only the leaf is not enough: a
    symlinked `lab`, `lab/docs` or `human/imported` on the way would make
    mkdir/copy/move write outside the repo. The check-then-write sequence
    is not atomic — see the module docstring's residual-risk note.
    """
    probe = root
    for part in parts:
        for piece in Path(part).parts:
            probe = probe / piece
            if probe.is_symlink():
                raise SymlinkOnPath(rel_posix(probe, root))
    return probe


def absolute_symlink_hit(path: Path) -> Path | None:
    """Return the first symlink on an absolute path, including its leaf.

    The target-repo helper above can trust an already-resolved repo root
    and report repo-relative hits. The deterministic state fallback has no
    equivalent trusted anchor, so it must lstat every component from the
    filesystem root through the requested leaf. This remains a
    check-then-use guard; see the module-level TOCTOU note.
    """
    if not path.is_absolute():
        raise ValueError(f"expected absolute path, got: {path}")
    probe = Path(path.anchor)
    for piece in path.parts[1:]:
        probe = probe / piece
        if probe.is_symlink():
            return probe
    return None


def state_fallback_root(target: Path) -> Path:
    """Deterministic per-target /tmp location used when the canonical
    state area crosses a symlink: re-runs and later phases of the same
    adoption find the same state. Deliberately outside the target repo and
    never auto-deleted — it is the audit trail for a blocked adoption.
    Callers must use ``checked_state_fallback_root`` or
    ``checked_fallback_path`` before I/O; this function only derives the
    stable name."""
    digest = hashlib.sha256(str(target.resolve()).encode("utf-8")).hexdigest()[:12]
    return Path(tempfile.gettempdir()) / f"template-adoption-state-{digest}"


def state_symlink_hit(target: Path) -> str | None:
    """First symlink on the canonical state area, repo-root-relative.

    The three state-file leaves are part of the safety decision. Checking
    only ``.../state`` would still let ``Path.write_text``/``open('a')``
    follow a pre-positioned ``adoption-plan.json``, ``baseline.json`` or
    ``phase-log.jsonl`` symlink.
    """
    candidates = [STATE_DIR, *(STATE_DIR / name for name in STATE_FILES)]
    for candidate in candidates:
        try:
            safe_target_path(target, *candidate.parts)
        except SymlinkOnPath as e:
            return e.rel
    return None


def fallback_state_symlink_hit(target: Path) -> Path | None:
    """First symlink on the fallback root or any state-file leaf.

    Each absolute candidate check includes all intermediate path segments,
    so a symlink supplied through e.g. ``TMPDIR=/safe/link`` is rejected as
    firmly as a symlink at the deterministic fallback root or leaf.
    """
    root = state_fallback_root(target)
    candidates = [root, *(root / name for name in STATE_FILES)]
    for candidate in candidates:
        hit = absolute_symlink_hit(candidate)
        if hit is not None:
            return hit
    return None


def checked_state_fallback_root(target: Path) -> Path:
    """Return the fallback root only when its full state area is safe."""
    root = state_fallback_root(target)
    hit = fallback_state_symlink_hit(target)
    if hit is not None:
        raise SystemExit(
            f"unsafe state fallback: '{hit}' is a symlink on deterministic fallback "
            f"path {root}; refusing to read or write adoption state"
        )
    return root


def checked_fallback_path(target: Path, name: str) -> Path:
    """Return one non-state fallback leaf after an absolute lstat walk."""
    path = state_fallback_root(target) / name
    hit = absolute_symlink_hit(path)
    if hit is not None:
        raise SystemExit(
            f"unsafe state fallback: '{hit}' is a symlink on fallback path {path}; "
            "refusing to write"
        )
    return path


def state_redirect_blocker(target: Path) -> str | None:
    """Blocker line describing a state redirect, or None when state is
    safe. Review round 3 BLOCKER-C: being unable to write state safely is
    itself a blocker — it must fail the pipeline loudly, never be silently
    swallowed just because the state file landed somewhere else."""
    hit = state_symlink_hit(target)
    if hit is None:
        return None
    return (
        f"state-redirect: '{hit}' on the canonical state path ({STATE_DIR.as_posix()}) "
        f"is a symlink; canonical state is disabled and {state_fallback_root(target)} "
        "will be used only if its full fallback safety check passes — reconcile the "
        "canonical symlink and re-run"
    )


def state_root(target: Path) -> Path:
    """Canonical state dir unless its path or a known leaf is a symlink.

    For example, the target's ``lab``/``lab/docs`` may point at an external
    tree, or ``adoption-plan.json`` itself may be pre-positioned as a
    symlink. In either case state reads/writes are redirected to the checked
    fallback and every phase registers/prints ``state_redirect_blocker``.
    """
    if state_symlink_hit(target) is None:
        return target / STATE_DIR
    return checked_state_fallback_root(target)


def state_path(target: Path, name: str) -> Path:
    if name not in STATE_FILES:
        raise ValueError(f"unrecognized adoption state file: {name}")
    return state_root(target) / name


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any], dry_run: bool = False) -> None:
    if dry_run:
        print(f"DRY-RUN write {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def append_log(target: Path, phase: str, status: str, details: dict[str, Any], dry_run: bool) -> None:
    row = {"time": now_iso(), "phase": phase, "status": status, "details": details}
    if dry_run:
        print(f"DRY-RUN log {row}")
        return
    path = state_path(target, LOG_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, sort_keys=True) + "\n")


def run(
    cmd: list[str] | str,
    cwd: Path,
    *,
    shell: bool = False,
    timeout: int = 120,
) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            shell=shell,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        return {
            "command": cmd if isinstance(cmd, str) else " ".join(cmd),
            "returncode": proc.returncode,
            "stdout": proc.stdout[-8000:],
            "stderr": proc.stderr[-8000:],
            "timeout": False,
        }
    except subprocess.TimeoutExpired as e:
        return {
            "command": cmd if isinstance(cmd, str) else " ".join(cmd),
            "returncode": 124,
            "stdout": (e.stdout or "")[-8000:] if isinstance(e.stdout, str) else "",
            "stderr": (e.stderr or "")[-8000:] if isinstance(e.stderr, str) else "",
            "timeout": True,
        }


def require_git_repo(target: Path) -> None:
    if not target.exists() or not target.is_dir():
        raise SystemExit(f"target is not a directory: {target}")
    if not (target / ".git").exists():
        raise SystemExit(f"target is not a Git repo: {target}")
    if target.resolve() == TEMPLATE_ROOT.resolve():
        raise SystemExit("refusing to adopt the template repo into itself")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def protected_path(rel: str) -> bool:
    parts = tuple(Path(rel).parts)
    if any(part in PROTECTED_PARTS for part in parts):
        return True
    return any(parts[: len(prefix)] == prefix for prefix in PROTECTED_PREFIXES)


def under_protected_prefix(rel: str) -> bool:
    """True only for paths anchored under a full PROTECTED_PREFIXES path
    from the repo root (`lab/data/**`, ...) — NOT for paths that merely
    contain a protected directory *name* at some level. The template's
    own placeholder files all live under these prefixes, so this is the
    only region where the "byte-identical to the template" exemption in
    `protected_hits_within` may apply (review round 2 BLOCKER-A: the
    exemption must be anchored by full relative path, never by
    any-level name matching)."""
    parts = tuple(Path(rel).parts)
    return any(parts[: len(prefix)] == prefix for prefix in PROTECTED_PREFIXES)


def template_excluded(rel: str, path: Path) -> bool:
    if any(rel == prefix or rel.startswith(prefix + "/") for prefix in EXCLUDE_REL_PREFIXES):
        return True
    return path.name in EXCLUDE_DIR_NAMES


def list_root_entries(target: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for entry in sorted(target.iterdir(), key=lambda p: p.name):
        if entry.name == ".git":
            continue
        rel = entry.name
        kind = "dir" if entry.is_dir() else "file" if entry.is_file() else "other"
        entries.append(
            {
                "path": rel,
                "kind": kind,
                "allowed_root": rel in ROOT_WHITELIST,
                "template_control_item": rel in CONTROL_ITEMS,
                "protected": protected_path(rel),
            }
        )
    return entries


def hash_matches_template(src: Path, template_item: Path) -> bool | None:
    """Compare a root file's content against the template's own copy of the
    same-named file. Returns None when either side isn't a plain,
    hashable file (directory, missing, or oversized — see
    LARGE_HASH_LIMIT); callers must treat None as "not comparable", not as
    a mismatch."""
    if not src.is_file() or not template_item.is_file():
        return None
    src_hash = path_hash(src)
    template_hash = path_hash(template_item)
    if src_hash is None or template_hash is None:
        return None
    return src_hash == template_hash


def protected_hits_within(target: Path, name: str, limit: int = 5) -> list[str]:
    """Recursively scan a root entry for protected content (review
    BLOCKER-1: name-only checks miss nested protected paths such as
    `src/checkpoints/model.bin` or a target repo's own `lab/data/**`).

    This is a protection-boundary scan, not a performance walk (review
    round 2 BLOCKER-A): it must cover EVERY descendant of the entry it is
    clearing for a wholesale move, so the `EXCLUDE_DIR_NAMES` pruning used
    by other walks is deliberately NOT applied here — a
    `src/.venv/checkpoints/model.bin` must still block `src`. The scan
    stays cheap because it only matches protected patterns per path and
    hashes nothing except anchored template-placeholder candidates (see
    below). A protected-pattern hit inside a virtualenv/cache (e.g. a
    pip-installed `wandb/` package) is still reported as a hit: the
    per-hit paths in the reason let the human judge and remove the
    artifact, instead of the scan silently skipping whole subtrees.

    Symlinks (review round 2 BLOCKER-C): a symlink sitting at a protected
    position is ALWAYS a hit — it is never dereferenced, never followed,
    and never exempted by the template comparison (the target's `lab/data`
    being a symlink to an external directory must block, even though the
    template has a real directory at that path). A root entry that is
    itself a symlink is never walked through.

    Returns repo-root-relative posix paths under `name` that match a
    protected pattern (symlink hits are suffixed with " (symlink)") and
    are NOT an anchored, byte-identical copy of the template's own file at
    the same relative path. The template ships placeholder docs under the
    `PROTECTED_PREFIXES` roots (`lab/data/`, `lab/runs/`, `lab/models/`,
    `lab/infra/private/`) — scaffold legitimately copies those in, and an
    unmodified copy must not turn every re-run into a blocker. This
    exemption is anchored to full `PROTECTED_PREFIXES` relative paths only
    (review round 2 BLOCKER-A), never applied to name-based matches
    elsewhere, and never applied to symlinks. Anything else that matches a
    protected pattern makes the WHOLE entry a blocker: the conservative
    policy never does partial moves.
    """
    hits: list[str] = []
    root = target / name
    if protected_path(name):
        hits.append(name + (" (symlink)" if root.is_symlink() else ""))
    if root.is_symlink():
        # Never walk through a symlink root entry: scanning would traverse
        # a tree outside the entry itself. Nothing behind the link is ever
        # written or moved either — scaffold lstat-checks before writes,
        # and normalize moves the link inode, not its referent.
        return hits[:limit]
    if not root.is_dir():
        return hits[:limit]
    # followlinks=False (default): the walk itself never descends through
    # symlinked directories; they are inspected as entries below instead.
    for walk_root, dirnames, filenames in os.walk(root):
        walk_path = Path(walk_root)
        for child in dirnames:
            child_path = walk_path / child
            rel = rel_posix(child_path, target)
            if not protected_path(rel):
                continue
            if child_path.is_symlink():
                hits.append(rel + " (symlink)")
            elif not (under_protected_prefix(rel) and (TEMPLATE_ROOT / rel).is_dir()):
                hits.append(rel)
        for filename in filenames:
            path = walk_path / filename
            rel = rel_posix(path, target)
            if not protected_path(rel):
                continue
            if path.is_symlink():
                hits.append(rel + " (symlink)")
                continue
            if under_protected_prefix(rel) and hash_matches_template(path, TEMPLATE_ROOT / rel) is True:
                continue  # anchored, unmodified template placeholder — not target data
            hits.append(rel)
        if len(hits) >= limit:
            break
    return hits[:limit]


def classify_entry(target: Path, name: str, kind: str, import_root_rel: str) -> dict[str, Any]:
    """Classify a single root entry into one of the four built-in
    conservative buckets (plan B1, human-decided 2026-07-12 — no external
    rule file/CLI override, see 开放问题 4):

    - protected: hits a forbidden/protected path — either the entry name
      itself or (for directories) any nested path inside it (review
      BLOCKER-1) — never moved, registered as a blocker for the whole
      entry (conservative: no partial moves).
    - template_control_item: hits `CONTROL_ITEMS` **and** the content hash
      is unchanged vs the template (plan B1, human-decided 2026-07-12) —
      left in place, nothing to reconcile. Structural control directories
      are merged file-by-file by `scaffold`; normalize never moves a
      control item wholesale.
    - conflict: either a same-named control-item file whose hash differs
      from / is not comparable to the template's canonical content (plan
      B1 conflict branch: the target position already holds inconsistent
      content — review MAJOR-2), or a non-control entry whose intended
      import destination (`lab/code/imported/<slug>/<name>`) already holds
      different content — registered as a blocker, never overwritten.
    - conservative_import: everything else — moved wholesale into
      `lab/code/imported/<slug>/<name>`.

    Review round 2 BLOCKER-C: a symlink at a control-item position is a
    `conflict` blocker — scaffold merges file-by-file into control
    directories, and writing through a symlink would leave the target repo
    and touch whatever the link points at. Symlinks at protected positions
    (the entry itself or nested) are reported by `protected_hits_within`.
    """
    if name == TEMPLATE_ANCHOR.ANCHOR_NAME:
        try:
            anchor = TEMPLATE_ANCHOR.read(target)
        except TEMPLATE_ANCHOR.TemplateAnchorError as exc:
            return {
                "path": name,
                "kind": kind,
                "category": "conflict",
                "target_path": name,
                "blocker": True,
                "reason": f"template anchor is unsafe or malformed: {exc}",
            }
        if anchor is not None:
            return {
                "path": name,
                "kind": kind,
                "category": "template_control_item",
                "target_path": name,
                "blocker": False,
                "reason": "governed template anchor; retained at the root and never imported",
                "anchor_origin": anchor["origin"],
                "anchor_version": anchor["version"],
            }
    protected_hits = protected_hits_within(target, name)
    if protected_hits:
        if protected_hits == [name]:
            detail = (
                f"matches a forbidden/protected path (lab/data, lab/runs, lab/models, "
                f"lab/infra/private, checkpoints, wandb, .env, ...): '{name}'"
            )
        else:
            detail = (
                f"'{name}' contains protected content ({', '.join(protected_hits)}; "
                "first hits shown — if any are non-data artifacts such as a virtualenv "
                "or cache, remove them and re-run discover)"
            )
        return {
            "path": name,
            "kind": kind,
            "category": "protected",
            "target_path": None,
            "blocker": True,
            "reason": (
                detail + " — never moved, scaffolded over, or edited by adoption "
                "(conservative: the whole entry is a blocker, no partial moves)"
            ),
        }
    if name in CONTROL_ITEMS:
        if (target / name).is_symlink():
            return {
                "path": name,
                "kind": kind,
                "category": "conflict",
                "target_path": name,
                "blocker": True,
                "reason": (
                    f"control-item position '{name}' is a symlink (review round 2 "
                    "BLOCKER-C): adoption never dereferences, writes through, moves, "
                    "or replaces it; registered as a blocker for the human to reconcile"
                ),
            }
        template_item = TEMPLATE_ROOT / name
        if kind == "dir":
            return {
                "path": name,
                "kind": kind,
                "category": "template_control_item",
                "target_path": name,
                "blocker": False,
                "reason": (
                    "template-managed directory: scaffold merges/copies its contents in place "
                    "file-by-file; the directory itself is never moved as a whole"
                ),
                "hash_note": "not-applicable (directory)",
            }
        same = hash_matches_template(target / name, template_item)
        if same is True:
            return {
                "path": name,
                "kind": kind,
                "category": "template_control_item",
                "target_path": name,
                "blocker": False,
                "reason": "matches the template's canonical content for this control item; nothing to reconcile",
                "hash_note": "matches template",
            }
        # Plan B1 (review MAJOR-2): only "hits CONTROL_ITEMS *and* hash
        # unchanged" is a template_control_item. A same-named file with
        # different (or non-comparable) content is the target's own file
        # at a position the template also claims — that is B1's conflict
        # branch: register a blocker and stop; never silently stash the
        # original and install the template's version.
        hash_note = "differs from template" if same is False else "not comparable"
        return {
            "path": name,
            "kind": kind,
            "category": "conflict",
            "target_path": name,
            "blocker": True,
            "reason": (
                f"same-named as template control item but content {hash_note} "
                "(plan B1 conflict: the target position already holds inconsistent "
                "content); registered as a blocker, left untouched for the human to reconcile"
            ),
            "hash_note": hash_note,
        }
    dst_rel = f"{import_root_rel}/{name}"
    dst = target / dst_rel
    if dst.exists():
        return {
            "path": name,
            "kind": kind,
            "category": "conflict",
            "target_path": dst_rel,
            "blocker": True,
            "reason": (
                f"intended import destination already holds content: '{dst_rel}'; "
                "registered as a blocker, not overwritten"
            ),
        }
    return {
        "path": name,
        "kind": kind,
        "category": "conservative_import",
        "target_path": dst_rel,
        "blocker": False,
        "reason": "not a template control item and not protected; conservatively imported wholesale",
    }


def classify_root_entries(target: Path, slug: str) -> list[dict[str, Any]]:
    import_root_rel = f"lab/code/imported/{slug}"
    classified: list[dict[str, Any]] = []
    for entry in sorted(target.iterdir(), key=lambda p: p.name):
        if entry.name == ".git":
            continue
        kind = "dir" if entry.is_dir() else "file" if entry.is_file() else "other"
        classified.append(classify_entry(target, entry.name, kind, import_root_rel))
    return classified


SLUG_MAX_LEN = 100


def project_slug(target: Path, explicit: str | None) -> str:
    """Sanitize the project name into a filesystem-safe slug.

    Review round 3 MAJOR: the slug becomes a directory name under
    `lab/code/imported/`, so it is capped at `SLUG_MAX_LEN` (100 chars,
    comfortably under the common NAME_MAX=255) — an over-long slug would
    only fail at normalize's mkdir (ENAMETOOLONG) AFTER scaffold already
    modified the target, leaving a half-finished adoption. A truncated
    slug gets an 8-hex sha256 suffix of the full sanitized name so two
    long names that share a 91-char prefix still map to distinct import
    roots. Truncation is idempotent (a ≤100-char slug passes through
    unchanged), so normalize's re-derivation from the persisted slug
    agrees with discover's.
    """
    base = explicit or target.name
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", base.strip()).strip("-._")
    if len(slug) > SLUG_MAX_LEN:
        digest = hashlib.sha256(slug.encode("utf-8")).hexdigest()[:8]
        slug = slug[: SLUG_MAX_LEN - 1 - len(digest)].rstrip("-._") + "-" + digest
    return slug or "imported-project"


def detect_test_command(target: Path, requested: str | None) -> tuple[str | None, str]:
    """Return (command, command_source).

    command_source is one of the smoke-contract values (C1): "explicit",
    "auto-detected", "none". A command of None with source "explicit" means
    the caller explicitly opted out (`--test-command none`); a command of
    None with source "none" means auto-detection found nothing to run.
    """
    if requested == "none":
        return None, "explicit"
    if requested and requested != "auto":
        return requested, "explicit"
    if (target / "pytest.ini").exists() or (target / "tests").is_dir():
        return "python -m pytest", "auto-detected"
    if (target / "Makefile").exists():
        text = (target / "Makefile").read_text(encoding="utf-8", errors="replace")
        if re.search(r"^test:", text, re.MULTILINE):
            return "make test", "auto-detected"
    return None, "none"


def git_ls_files(target: Path) -> list[str]:
    proc = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=target,
        text=False,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise SystemExit(proc.stderr.decode("utf-8", errors="replace"))
    return [p.decode("utf-8", errors="replace") for p in proc.stdout.split(b"\0") if p]


def format_classification_line(entry: dict[str, Any]) -> str:
    target_disp = entry["target_path"] or "-"
    blocker_disp = "BLOCKER" if entry["blocker"] else "-"
    return (
        f"  - {entry['path']} ({entry['kind']}) -> category={entry['category']} "
        f"target={target_disp} blocker={blocker_disp} reason={entry['reason']}"
    )


def discover(args: argparse.Namespace) -> dict[str, Any]:
    target = args.target.resolve()
    require_git_repo(target)
    slug = project_slug(target, args.project_name)
    root_entries = list_root_entries(target)
    # B1: per-entry semantic classification (built-in conservative four
    # buckets — template_control_item / conservative_import / protected /
    # conflict; no external rule file/CLI override, see 开放问题 4).
    classification = classify_root_entries(target, slug)
    protected_roots = [e["path"] for e in classification if e["category"] == "protected"]
    conservative_import_roots = [e["path"] for e in classification if e["category"] == "conservative_import"]
    template_control_item_roots = [e["path"] for e in classification if e["category"] == "template_control_item"]
    conflicts = [e["path"] for e in classification if e["category"] == "conflict"]
    # Legacy/backwards-compatible summary field: everything that is a
    # candidate to leave the root (conservative_import + conflict), kept
    # under its historical name for any external reader of this field.
    root_pollution = conservative_import_roots + conflicts
    test_command, test_command_source = detect_test_command(target, args.test_command)
    plan = {
        "schema": PLAN_SCHEMA,
        "created_at": now_iso(),
        "target": str(target),
        "template_root": str(TEMPLATE_ROOT),
        "policy": args.policy,
        "origin": args.origin,
        "template_version": read_own_version(),
        "project_slug": slug,
        "state_dir": STATE_DIR.as_posix(),
        "report_path": REPORT_PATH.as_posix(),
        "test_command": test_command,
        "test_command_source": test_command_source,
        "root_entries": root_entries,
        "classification": classification,
        "protected_roots": protected_roots,
        "root_pollution": root_pollution,
        "template_conflicts": conflicts,
        "conservative_import_roots": conservative_import_roots,
        "template_control_item_roots": template_control_item_roots,
        # Control-item roots scaffold may create after discover are declared
        # up front so normalize can distinguish those expected additions from
        # an arbitrary post-discover root that the classification omitted.
        "scaffold_control_items": sorted(CONTROL_ITEMS),
        "import_root": f"lab/code/imported/{slug}",
        "normalize_blockers": [
            f"{e['category']}: {e['path']} — {e['reason']}" for e in classification if e["blocker"]
        ],
    }
    # Review round 3 BLOCKER-C: writing the plan/log must never go through
    # a symlinked state path — state_path() already redirects to the /tmp
    # fallback in that case, and the redirect itself is registered as a
    # blocker in the plan (not silently swallowed).
    state_blocker = state_redirect_blocker(target)
    if state_blocker:
        plan["normalize_blockers"].append(state_blocker)
        print(f"[discover] BLOCKER {state_blocker}")
    write_json(state_path(target, PLAN_FILE), plan, args.dry_run)
    append_log(target, "discover", "ok", {"root_entries": len(root_entries)}, args.dry_run)
    print("[discover] classification plan (target position + reason + blocker per root entry):")
    for entry in classification:
        print(format_classification_line(entry))
    print(
        f"[discover] root_entries={len(root_entries)} "
        f"template_control_item={len(template_control_item_roots)} "
        f"conservative_import={len(conservative_import_roots)} "
        f"protected={len(protected_roots)} conflict={len(conflicts)}"
    )
    return plan


def baseline(args: argparse.Namespace) -> dict[str, Any]:
    target = args.target.resolve()
    require_git_repo(target)
    plan_path = state_path(target, PLAN_FILE)
    plan = read_json(plan_path) if plan_path.exists() else discover(args)
    tracked: list[dict[str, Any]] = []
    for rel in git_ls_files(target):
        path = target / rel
        if not path.is_file():
            continue
        size = path.stat().st_size
        row: dict[str, Any] = {"path": rel, "size": size, "protected": protected_path(rel)}
        if size <= LARGE_HASH_LIMIT:
            row["sha256"] = sha256_file(path)
        else:
            row["sha256"] = None
            row["hash_skipped_reason"] = f"size>{LARGE_HASH_LIMIT}"
        tracked.append(row)
    test_result = None
    if plan.get("test_command"):
        test_result = run(plan["test_command"], target, shell=True, timeout=args.test_timeout)
    data = {
        "schema": "template-adoption-baseline-v1",
        "created_at": now_iso(),
        "target": str(target),
        "git_status": run(["git", "status", "--short"], target),
        "git_head": run(["git", "rev-parse", "--verify", "HEAD"], target),
        "root_entries": list_root_entries(target),
        "tracked_files": tracked,
        "test_command": plan.get("test_command"),
        "test_result": test_result,
    }
    state_blocker = state_redirect_blocker(target)
    if state_blocker:
        print(f"[baseline] BLOCKER {state_blocker}")
    write_json(state_path(target, BASELINE_FILE), data, args.dry_run)
    append_log(target, "baseline", "ok", {"tracked_files": len(tracked)}, args.dry_run)
    print(f"[baseline] tracked_files={len(tracked)}")
    return data


def unique_preserve_path(target: Path, rel: str) -> Path:
    # Review round 3 BLOCKER-C: lstat-check EVERY segment of the archive
    # path (human, human/imported, adoption-conflicts, and each component
    # of `rel`) — a symlinked `human/imported` would otherwise make the
    # conflict archive move the original file OUT of the repo. Raises
    # SymlinkOnPath; callers refuse the archive (and the overwrite that
    # depends on it) and register a blocker.
    base = safe_target_path(target, "human", "imported", "adoption-conflicts", rel)
    if not base.exists():
        return base
    stem = base.name
    parent = base.parent
    for i in range(1, 1000):
        candidate = parent / f"{stem}.conflict-{i}"
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"could not allocate conflict path for {rel}")


def preserve_existing(target: Path, rel: str, dry_run: bool) -> Path:
    src = target / rel
    dst = unique_preserve_path(target, rel)
    if dry_run:
        print(f"DRY-RUN preserve {src} -> {dst}")
        return dst
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dst))
    return dst


def copy_file_preserving(src: Path, dst: Path, rel: str, target: Path, dry_run: bool) -> str:
    if dst.is_symlink():
        # Review round 2 BLOCKER-C: never write through, replace, or stash
        # a symlink at the destination position (lstat semantics — checked
        # before any exists()/hash logic, which would dereference). The
        # caller registers this as a blocker.
        return "symlink_skip"
    if dst.exists():
        if dst.is_file() and sha256_file(src) == sha256_file(dst):
            return "same"
        if protected_path(rel):
            # Review BLOCKER-1 (belt and suspenders): never stash/move or
            # overwrite existing target content at a protected path, even
            # when the template ships a same-named file. Scaffold's
            # detect-before-scaffold check should prevent reaching here;
            # if it is reached anyway, skip rather than touch the bytes.
            return "protected_skip"
        try:
            preserve_existing(target, rel, dry_run)
        except SymlinkOnPath:
            # Review round 3 BLOCKER-C: the conflict-archive path itself
            # crosses a symlink (e.g. human/imported -> external dir).
            # Refuse the archive — and therefore also the overwrite that
            # would have followed it. The caller registers a blocker.
            return "archive_symlink_skip"
    if dry_run:
        print(f"DRY-RUN copy {src} -> {dst}")
        return "copy"
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return "copy"


def copy_template_tree(
    src_root: Path, dst_root: Path, target: Path, dry_run: bool
) -> tuple[dict[str, int], list[str], list[str]]:
    """Merge one template control directory into the target, file by file.

    Returns (counts, symlink_hits, archive_hits): `symlink_hits` are
    target-relative paths where the destination position is a symlink
    (review round 2 BLOCKER-C) — those subtrees/files are never written
    through (lstat check before any write, symlinked destination
    directories are pruned from the walk); `archive_hits` (review round 3
    BLOCKER-C) are destination files whose pre-existing content could not
    be stashed because the conflict-archive path itself crosses a symlink
    — those files are left untouched (no archive, no overwrite). The
    caller registers each hit of either kind as a blocker.
    """
    counts = {"copy": 0, "same": 0, "skip": 0, "protected_skip": 0, "symlink_skip": 0, "archive_symlink_skip": 0}
    symlink_hits: list[str] = []
    archive_hits: list[str] = []
    for root, dirnames, filenames in os.walk(src_root):
        root_path = Path(root)
        rel_root = root_path.relative_to(TEMPLATE_ROOT).as_posix()
        kept: list[str] = []
        for d in dirnames:
            if template_excluded(f"{rel_root}/{d}".strip("./"), root_path / d):
                continue
            dst_rel = (root_path / d).relative_to(TEMPLATE_ROOT).as_posix()
            if (target / dst_rel).is_symlink():
                # BLOCKER-C: the target has a symlink where the template
                # has a directory — never descend/write through it.
                symlink_hits.append(dst_rel)
                counts["symlink_skip"] += 1
                continue
            kept.append(d)
        dirnames[:] = kept
        for filename in filenames:
            src = root_path / filename
            rel = src.relative_to(TEMPLATE_ROOT).as_posix()
            if template_excluded(rel, src):
                counts["skip"] += 1
                continue
            dst = target / rel
            status = copy_file_preserving(src, dst, rel, target, dry_run)
            if status == "symlink_skip":
                symlink_hits.append(rel)
            elif status == "archive_symlink_skip":
                archive_hits.append(rel)
            counts[status] += 1
    return counts, symlink_hits, archive_hits


def scaffold(args: argparse.Namespace) -> dict[str, Any]:
    """Copy/merge template control items into the target.

    Detect-before-scaffold (review BLOCKER-1): a control item that already
    exists in the target and contains protected content (e.g. the target's
    own `lab/data/**`) is skipped entirely and registered as a blocker —
    scaffold must not write into it or stash same-named protected files
    away before normalize's blocker gate is reached.

    Plan B1 (review MAJOR-2): a same-named control-item *file* whose hash
    differs from the template is a conflict blocker — left untouched, not
    stashed under human/imported/adoption-conflicts/ with the template's
    version installed over it.

    Review round 2 BLOCKER-C: any symlink at a destination position — the
    control item itself or anything nested inside it — is a blocker;
    scaffold does not dereference or write through it (lstat checks before
    every write).

    Review round 3: scaffold now fails closed on its own blockers (same
    `--allow-blocked-normalize` escape hatch as normalize). Some scaffold
    blockers — a symlinked conflict-archive path, a state-dir redirect —
    have NO classification counterpart, so relying on normalize's gate
    alone would let `--phase all` finish with exit 0 despite them.
    """
    target = args.target.resolve()
    require_git_repo(target)
    if not state_path(target, BASELINE_FILE).exists():
        baseline(args)
    counts = {"copy": 0, "same": 0, "skip": 0, "protected_skip": 0, "symlink_skip": 0, "archive_symlink_skip": 0}
    blockers: list[str] = []
    for item in CONTROL_ITEMS:
        src = TEMPLATE_ROOT / item
        if not src.exists():
            continue
        dst = target / item
        if dst.is_symlink():
            # Review round 2 BLOCKER-C: a symlink at a control-item
            # position is never dereferenced, written through, or replaced
            # (lstat check before protected_hits_within, which would
            # otherwise treat a dir symlink like a plain entry).
            blockers.append(
                f"symlink: {item} — control-item position is a symlink; "
                "scaffold refuses to write through or replace it"
            )
            counts["symlink_skip"] += 1
            continue
        protected_hits = protected_hits_within(target, item)
        if protected_hits:
            blockers.append(
                f"protected: {item} — contains protected content "
                f"({', '.join(protected_hits)}); scaffold skipped this control item entirely"
            )
            continue
        if src.is_file():
            if dst.exists():
                if hash_matches_template(dst, src) is True:
                    counts["same"] += 1
                else:
                    blockers.append(
                        f"conflict: {item} — existing root file differs from the template's "
                        "control item content (plan B1 conflict); left untouched"
                    )
                continue
            status = copy_file_preserving(src, dst, item, target, args.dry_run)
            counts[status] += 1
        elif src.is_dir():
            sub, symlink_hits, archive_hits = copy_template_tree(src, dst, target, args.dry_run)
            counts = {k: counts[k] + sub[k] for k in counts}
            blockers.extend(
                f"symlink: {hit} — destination position inside control item '{item}' "
                "is a symlink; scaffold refuses to write through it"
                for hit in symlink_hits
            )
            blockers.extend(
                f"archive-symlink: {hit} — the conflict-archive path "
                "(human/imported/adoption-conflicts) crosses a symlink; scaffold refuses "
                "to stash the existing file out of the repo and left it untouched "
                "(no overwrite either)"
                for hit in archive_hits
            )
    state_blocker = state_redirect_blocker(target)
    if state_blocker:
        blockers.append(state_blocker)
    status = "blocked" if blockers else "ok"
    append_log(target, "scaffold", status, {**counts, "blockers": blockers}, args.dry_run)
    print(
        f"[scaffold] copied={counts['copy']} same={counts['same']} skipped={counts['skip']} "
        f"protected_skipped={counts['protected_skip']} symlink_skipped={counts['symlink_skip']} "
        f"archive_symlink_skipped={counts['archive_symlink_skip']} "
        f"blockers={len(blockers)}"
    )
    for blocker in blockers:
        print(f"[scaffold] BLOCKER {blocker}")
    if blockers and not args.allow_blocked_normalize:
        raise SystemExit("scaffold blocked: " + ", ".join(blockers))
    return {**counts, "blockers": blockers}


def path_hash(path: Path) -> str | None:
    return sha256_file(path) if path.is_file() and path.stat().st_size <= LARGE_HASH_LIMIT else None


def normalize(args: argparse.Namespace) -> dict[str, Any]:
    """B4: normalize consumes the discover-time classification plan
    (`plan["classification"]`, plan B1) instead of a hardcoded binary
    judgment. `template_control_item` entries are never moved (scaffold
    already reconciles them in place); `conservative_import` entries are
    moved wholesale into `plan["import_root"]`; `protected`/`conflict`
    entries stay put and are registered as blockers — the pipeline still
    stops here unless `--allow-blocked-normalize` is passed (unchanged
    conservative behavior).

    Review MAJOR-3/fresh-review MAJOR: the persisted plan is a *proposal*,
    not a trusted authorization. Normalize uses a two-pass preflight: it
    first reclassifies the complete current root and validates every planned
    entry, then performs moves only if the preflight has no blockers (unless
    the explicit `--allow-blocked-normalize` reporting escape hatch is used).
    A stale/tampered plan entry is rejected with a blocker instead of
    executed:

    - the plan path must name a single, real root entry — no separators,
      no '.'/'..' (rejected explicitly: `Path("..").name == ".."`, so the
      single-segment check alone would let '..' through — review round 3
      MAJOR-D), no absolute paths, and it must be a member of the actual
      `target.iterdir()` entry-name set right now (review round 2 MAJOR-D);
    - category must be one of the known four, `blocker` must be a real
      boolean, and the category/blocker combination must satisfy the
      invariant that `protected`/`conflict` are ALWAYS blockers (review
      round 2 MAJOR-D: `category="conflict", blocker=false` must not fall
      through into the move branch);
    - every current root entry must still be represented by the discover
      classification or its explicit `scaffold_control_items` declaration;
      declared scaffold additions are accepted only after they reclassify as
      safe template control items;
    - the entry's kind/category/blocker/target_path are recomputed from the
      current tree and must match the persisted row; protection scanning is
      therefore performed before *any* category-specific continue, including
      `template_control_item`, which is valid only for actual CONTROL_ITEMS;
    - target_path must EXACTLY equal the import path re-derived from the
      entry name under the current rules, resolve to a location inside
      the target repo, and have no symlink anywhere on its path (review
      round 2 BLOCKER-B: a stale/tampered `../escape` or absolute
      target_path must never move an entry out of the repo)."""
    target = args.target.resolve()
    require_git_repo(target)
    plan = read_json(state_path(target, PLAN_FILE))
    # Re-derive the import root from the recorded slug through the same
    # sanitizer discover uses (review round 2 BLOCKER-B): a tampered slug
    # cannot smuggle separators or '..' into the expected target path.
    raw_slug = plan.get("project_slug")
    slug = project_slug(target, raw_slug if isinstance(raw_slug, str) else None)
    expected_import_root = f"lab/code/imported/{slug}"
    classification_value = plan.get("classification")
    plan_shape_blockers: list[str] = []
    if classification_value is None:
        # Backward compatibility: a plan.json written before B1 has no
        # per-entry classification — recompute it now with the same
        # conservative rules rather than silently doing nothing.
        classification = classify_root_entries(target, slug)
    elif isinstance(classification_value, list):
        classification = classification_value
    else:
        classification = []
        plan_shape_blockers.append(
            "plan-malformed: classification must be a list; refusing to normalize"
        )
    scaffold_control_value = plan.get("scaffold_control_items", CONTROL_ITEMS)
    if isinstance(scaffold_control_value, list) and all(
        isinstance(item, str) for item in scaffold_control_value
    ):
        scaffold_control_items = set(scaffold_control_value)
        unknown_scaffold_items = scaffold_control_items - set(CONTROL_ITEMS)
        if unknown_scaffold_items:
            plan_shape_blockers.append(
                "plan-malformed: scaffold_control_items contains non-control names "
                f"{sorted(unknown_scaffold_items)!r}; refusing to trust them"
            )
    else:
        scaffold_control_items = set()
        plan_shape_blockers.append(
            "plan-malformed: scaffold_control_items must be a list of strings; "
            "refusing to normalize"
        )
    known_categories = {"protected", "template_control_item", "conflict", "conservative_import"}
    always_blocker_categories = {"protected", "conflict"}
    # Review round 2/3 MAJOR-D: precise membership check against the REAL
    # current root-entry names, not a reconstructed existence probe
    # (`(target / "..").exists()` is true — it is the parent directory).
    current_entries = {p.name: p for p in target.iterdir() if p.name != ".git"}
    root_entry_names = set(current_entries)
    moved: list[dict[str, str]] = []
    move_candidates: list[tuple[str, str, Path, Path]] = []
    blockers: list[str] = list(plan_shape_blockers)
    if plan.get("origin") != args.origin:
        blockers.append(
            "origin-mismatch: discover recorded "
            f"{plan.get('origin')!r}, but normalize received --origin={args.origin!r}; "
            "re-run discover with the requested explicit origin"
        )
    anchor_decision: dict[str, Any] | None = None
    anchor_preflight_error: str | None = None
    try:
        anchor_decision = TEMPLATE_ANCHOR.preflight(target, args.origin, read_own_version())
    except TEMPLATE_ANCHOR.TemplateAnchorError as exc:
        anchor_preflight_error = f"template-anchor: {exc}"
        blockers.append(anchor_preflight_error)
    state_blocker = state_redirect_blocker(target)
    if state_blocker:
        blockers.append(state_blocker)

    # An unsafe or incompatible existing anchor is not an ordinary normalize
    # blocker. `--allow-blocked-normalize` may retain its reporting behavior
    # for legacy non-anchor blockers, but it must never authorize any queued
    # move when the anchor itself fails closed.
    if anchor_preflight_error:
        template_anchor = {"status": "not-written-anchor-conflict"}
        append_log(
            target,
            "normalize",
            "blocked",
            {"moved": moved, "blockers": blockers, "template_anchor": template_anchor},
            args.dry_run,
        )
        print(f"[normalize] moved=0 blockers={len(blockers)} template_anchor={template_anchor['status']}")
        raise SystemExit("normalize blocked by template anchor: " + anchor_preflight_error)

    planned_names: set[str] = set()
    for entry in classification:
        if not isinstance(entry, dict):
            continue
        name = entry.get("path")
        if (
            isinstance(name, str)
            and name
            and name not in {".", "..", ".git"}
            and Path(name).name == name
        ):
            planned_names.add(name)

    # Fresh-review MAJOR: compare the proposal to the complete current root,
    # not just the rows the proposal chose to mention. Discover itself creates
    # `lab/` for state and scaffold can add other plan-declared CONTROL_ITEMS,
    # so such an entry is accepted only when reclassification proves it is
    # currently a safe, non-blocking template control item. Every other
    # unplanned root entry is a blocker before any move is attempted.
    for name in sorted(root_entry_names - planned_names):
        path = current_entries[name]
        kind = "dir" if path.is_dir() else "file" if path.is_file() else "other"
        current = classify_entry(target, name, kind, expected_import_root)
        if (
            name in scaffold_control_items
            and name in CONTROL_ITEMS
            and current["category"] == "template_control_item"
            and current["blocker"] is False
        ):
            continue
        blockers.append(
            f"plan-mismatch: {name} — current root entry was not recorded by discover; "
            f"current classification={current['category']!r} blocker={current['blocker']}: "
            f"{current['reason']} (re-run discover)"
        )

    seen_names: set[str] = set()
    for entry in sorted(classification, key=lambda e: str(e.get("path")) if isinstance(e, dict) else ""):
        if not isinstance(entry, dict):
            blockers.append(f"plan-malformed: non-object classification entry {entry!r}; rejected")
            continue
        name = entry.get("path")
        if name == ".git":
            blockers.append("plan-mismatch: '.git' is reserved and must not appear in classification")
            continue
        # Review round 2/3 MAJOR-D: the plan path must be a single root
        # entry name. `Path(name).name != name` catches separators,
        # absolute paths, '.' and trailing slashes — but NOT '..'
        # (Path("..").name == ".."), so '.'/'..' are rejected explicitly.
        if not isinstance(name, str) or not name or name in {".", ".."} or Path(name).name != name:
            blockers.append(
                f"plan-mismatch: {name!r} — plan path is not a single root entry "
                "name (separators/'.'/'..'/absolute paths are rejected); refusing to act on it"
            )
            continue
        if name in seen_names:
            blockers.append(
                f"plan-mismatch: {name} — duplicate classification rows are not allowed; "
                "refusing to act on this entry"
            )
            continue
        seen_names.add(name)
        if name not in root_entry_names:
            # Review round 2 MAJOR-D: a plan entry that is not one of the
            # target's actual current root entries is stale/tampered —
            # reject it instead of silently skipping (re-run discover).
            blockers.append(
                f"plan-mismatch: {name} — plan references a root entry that does not "
                "exist; stale/tampered plan rejected for this entry (re-run discover)"
            )
            continue
        src = current_entries[name]
        category = entry.get("category")
        if category not in known_categories:
            blockers.append(
                f"unknown-category: {name} — plan entry carries unrecognized "
                f"category {category!r}; refusing to act on it"
            )
            continue
        blocker_flag = entry.get("blocker")
        if not isinstance(blocker_flag, bool):
            blockers.append(
                f"plan-malformed: {name} — blocker flag is missing or not a boolean "
                f"({blocker_flag!r}); refusing to act on it"
            )
            continue
        # Review round 2 MAJOR-D invariant: protected/conflict entries are
        # blockers BY DEFINITION — a plan claiming otherwise is tampered.
        if category in always_blocker_categories and not blocker_flag:
            blockers.append(
                f"plan-mismatch: {name} — category {category!r} requires blocker=true "
                "but the plan says false; tampered/stale plan rejected for this entry"
            )
            continue

        # Reclassify before any category-specific branch. In particular, a
        # forged `template_control_item` row must not skip the protection scan
        # and hide e.g. `src/checkpoints/model.bin`.
        current_kind = "dir" if src.is_dir() else "file" if src.is_file() else "other"
        current = classify_entry(target, name, current_kind, expected_import_root)
        if category == "template_control_item" and name not in CONTROL_ITEMS:
            blockers.append(
                f"plan-mismatch: {name} — category 'template_control_item' is valid only "
                f"for actual CONTROL_ITEMS; current classification={current['category']!r}: "
                f"{current['reason']}"
            )
            continue
        if entry.get("kind") != current_kind:
            blockers.append(
                f"plan-mismatch: {name} — persisted kind {entry.get('kind')!r} does not "
                f"match current kind {current_kind!r}; current classification="
                f"{current['category']!r}: {current['reason']}"
            )
            continue
        if current["category"] != category or current["blocker"] is not blocker_flag:
            blockers.append(
                f"plan-mismatch: {name} — persisted classification category={category!r} "
                f"blocker={blocker_flag} does not match current classification "
                f"category={current['category']!r} blocker={current['blocker']}: "
                f"{current['reason']}"
            )
            continue
        target_path = entry.get("target_path")
        current_target = current.get("target_path")
        if target_path != current_target:
            blockers.append(
                f"plan-mismatch: {name} — plan target_path {target_path!r} does not "
                f"equal the current derived target {current_target!r}; refusing to act"
            )
            continue
        if blocker_flag:
            blockers.append(f"{category}: {name} — {current['reason']}")
            continue
        if category == "template_control_item":
            continue  # revalidated actual control item; stays in place

        # category == "conservative_import" and the complete current-state
        # classification matches the proposal. Containment/symlink checks are
        # still applied to the derived destination before queuing the move.
        expected_target = f"{expected_import_root}/{name}"
        if target_path != expected_target:
            blockers.append(
                f"plan-mismatch: {name} — derived target {target_path!r} does not "
                f"equal the required import path {expected_target!r}; refusing to move"
            )
            continue
        if protected_path(target_path):
            blockers.append(
                f"plan-mismatch: {name} — plan target_path {target_path!r} is "
                "protected; refusing to move"
            )
            continue
        dst = target / target_path
        # Belt and suspenders containment (review round 2 BLOCKER-B): the
        # resolved destination must stay inside the resolved target root.
        resolved_root = target.resolve()
        try:
            dst.resolve().relative_to(resolved_root)
        except (OSError, ValueError):
            blockers.append(
                f"plan-mismatch: {name} — target_path {target_path!r} resolves "
                "outside the target repo; refusing to move"
            )
            continue
        # Review round 2/3 BLOCKER-C: refuse to move through a symlink at
        # any position on the destination path (lstat semantics, shared
        # `safe_target_path` gate).
        try:
            safe_target_path(target, target_path)
        except SymlinkOnPath as e:
            blockers.append(
                f"symlink: {name} — destination path component "
                f"'{e.rel}' is a symlink; refusing to move through it"
            )
            continue
        if dst.exists():
            blockers.append(
                f"conflict: {name} — destination appeared after discover: "
                f"{dst.relative_to(target).as_posix()}"
            )
            continue
        move_candidates.append((name, target_path, src, dst))

    # The default path is atomic with respect to validation findings: no safe
    # entry is moved before a later stale/tampered row or unplanned root is
    # discovered. The explicit reporting escape hatch retains its historical
    # ability to move independently validated candidates alongside blockers.
    if blockers and not args.allow_blocked_normalize:
        append_log(target, "normalize", "blocked", {"moved": moved, "blockers": blockers}, args.dry_run)
        print(f"[normalize] moved=0 blockers={len(blockers)}")
        raise SystemExit("normalize blocked by protected/conflicting paths: " + ", ".join(blockers))

    for name, target_path, src, dst in move_candidates:
        if args.dry_run:
            print(f"DRY-RUN move {src} -> {dst}")
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
        moved.append({"from": name, "to": target_path})
    if blockers:
        template_anchor = {"status": "not-written-blocked"}
    elif args.dry_run:
        assert anchor_decision is not None
        template_anchor = {
            "status": "would-" + anchor_decision["action"],
            "origin": anchor_decision["origin"],
            "version": anchor_decision["version"],
        }
        print(f"DRY-RUN template anchor {anchor_decision['action']}: {target / TEMPLATE_ANCHOR.ANCHOR_NAME}")
    else:
        assert anchor_decision is not None
        try:
            template_anchor = TEMPLATE_ANCHOR.apply_atomic(target, anchor_decision)
        except TEMPLATE_ANCHOR.TemplateAnchorError as exc:
            append_log(
                target,
                "normalize",
                "failed",
                {"moved": moved, "blockers": blockers, "template_anchor_error": str(exc)},
                args.dry_run,
            )
            raise SystemExit(f"normalize completed moves but could not write template anchor: {exc}") from exc
    status = "blocked" if blockers else "ok"
    append_log(
        target,
        "normalize",
        status,
        {"moved": moved, "blockers": blockers, "template_anchor": template_anchor},
        args.dry_run,
    )
    print(
        f"[normalize] moved={len(moved)} blockers={len(blockers)} "
        f"template_anchor={template_anchor['status']}"
    )
    return {"moved": moved, "blockers": blockers, "template_anchor": template_anchor}


def current_hash_index(target: Path) -> dict[str, list[str]]:
    """Hash every file currently in the target; only `.git` internals are
    skipped.

    Review round 3 MAJOR: this walk must honour the same contract as the
    baseline — `git ls-files` collects ALL tracked files, including ones
    under `.venv`/cache dirs, so pruning `EXCLUDE_DIR_NAMES` here would
    misreport intact tracked files as missing and fail a legitimate
    adoption. "tracked ⇒ covered by the integrity proof" is the contract
    (option a); the extra hashing cost on virtualenvs is accepted as the
    honest price. Non-regular entries (broken symlinks, fifos) are skipped
    — they carry no hashable bytes.
    """
    index: dict[str, list[str]] = {}
    for root, dirnames, filenames in os.walk(target):
        root_path = Path(root)
        dirnames[:] = [d for d in dirnames if d != ".git"]
        for filename in filenames:
            path = root_path / filename
            if not path.is_file():
                continue
            if path.stat().st_size > LARGE_HASH_LIMIT:
                continue
            digest = sha256_file(path)
            index.setdefault(digest, []).append(rel_posix(path, target))
    return index


def latest_normalize_blockers(target: Path) -> list[str]:
    """Return the blocker list from the most recent `normalize` phase-log entry.

    Unresolved conflict/protected-path blockers are an adoption-tool-self
    integrity failure (the tool could not safely complete the move), distinct
    from the target repo's own runtime/smoke health (see C1/C3 in
    plans/20260712-bootstrap-adoption-proof.zh.md).
    """
    rows = read_phase_log(target)
    normalize_rows = [r for r in rows if r.get("phase") == "normalize"]
    if not normalize_rows:
        return []
    return list(normalize_rows[-1].get("details", {}).get("blockers", []))


def integrity_result(target: Path) -> dict[str, Any]:
    baseline_path = state_path(target, BASELINE_FILE)
    if not baseline_path.exists():
        raise SystemExit(f"missing baseline: {baseline_path}")
    baseline_data = read_json(baseline_path)
    index = current_hash_index(target)
    missing: list[dict[str, Any]] = []
    present = 0
    for row in baseline_data["tracked_files"]:
        digest = row.get("sha256")
        if not digest:
            original = target / row["path"]
            if original.exists() and original.stat().st_size == row["size"]:
                present += 1
            else:
                missing.append(row)
            continue
        if digest in index:
            present += 1
        else:
            missing.append(row)
    unresolved_blockers = latest_normalize_blockers(target)
    return {
        "schema": "template-adoption-integrity-v1",
        "checked_at": now_iso(),
        "baseline_files": len(baseline_data["tracked_files"]),
        "present": present,
        "missing": missing,
        "unresolved_blockers": unresolved_blockers,
        "ok": not missing and not unresolved_blockers,
    }


def smoke_command_metadata(plan: dict[str, Any]) -> tuple[str | None, str]:
    """Validate the persisted smoke-command metadata before execution.

    Plans written before the smoke contract used the same v1 schema label but
    did not record command provenance. Guessing `none` for those plans can
    produce contradictory records such as command=`true`, source=`none`.
    Keep compatible v1 plans that already contain the field, but require
    genuinely legacy plans to rerun discover and persist unambiguous metadata.
    """
    schema = plan.get("schema")
    if schema not in {LEGACY_PLAN_SCHEMA, PLAN_SCHEMA}:
        raise SystemExit(
            f"unsupported adoption plan schema {schema!r}; rerun --phase discover before prove"
        )
    if "test_command_source" not in plan:
        raise SystemExit(
            "adoption plan predates smoke command provenance; rerun --phase discover "
            "before prove"
        )
    command = plan.get("test_command")
    source = plan["test_command_source"]
    if source not in {"auto-detected", "explicit", "none"}:
        raise SystemExit(
            f"invalid test_command_source {source!r}; rerun --phase discover before prove"
        )
    if command is not None and source == "none":
        raise SystemExit(
            "adoption plan has a test command with command_source=none; "
            "rerun --phase discover before prove"
        )
    if command is None and source == "auto-detected":
        raise SystemExit(
            "adoption plan has no test command but command_source=auto-detected; "
            "rerun --phase discover before prove"
        )
    return command, source


def evaluate_smoke(plan: dict[str, Any], target: Path, test_timeout: int) -> dict[str, Any]:
    """Run the target repo's own native test command and classify the result.

    Implements the smoke contract from plans/20260712-bootstrap-adoption-proof.zh.md
    (C1): command_source (auto-detected/explicit/none), command, result
    (pass/fail/skipped/unknown), unverified_reason (required whenever result
    is not "pass"). This function never raises for a non-pass result -- the
    smoke contract is decoupled from `prove`'s process exit code (C1/C2); a
    non-pass smoke result is surfaced as an explicit, structured warning in
    the report instead of a silent success or a hard failure.
    """
    command, source = smoke_command_metadata(plan)
    if command is None:
        reason = (
            "test command explicitly disabled via --test-command none"
            if source == "explicit"
            else "no native test command detected "
            "(no pytest.ini, no tests/ dir, no Makefile `test:` target, "
            "and none supplied via --test-command)"
        )
        return {
            "schema": "template-adoption-smoke-v1",
            "command_source": source,
            "command": None,
            "result": "skipped",
            "unverified_reason": reason,
            "exec": None,
        }
    cwd = target / plan["import_root"]
    if not cwd.exists():
        cwd = target
    exec_result = run(command, cwd, shell=True, timeout=test_timeout)
    if exec_result.get("timeout"):
        return {
            "schema": "template-adoption-smoke-v1",
            "command_source": source,
            "command": command,
            "result": "unknown",
            "unverified_reason": f"command timed out after {test_timeout}s",
            "exec": exec_result,
        }
    if exec_result["returncode"] == 0:
        return {
            "schema": "template-adoption-smoke-v1",
            "command_source": source,
            "command": command,
            "result": "pass",
            "unverified_reason": None,
            "exec": exec_result,
        }
    return {
        "schema": "template-adoption-smoke-v1",
        "command_source": source,
        "command": command,
        "result": "fail",
        "unverified_reason": f"command exited with returncode {exec_result['returncode']}",
        "exec": exec_result,
    }


def inspect_hooks_path(target: Path) -> dict[str, Any]:
    """B6: adoption only *inspects* the target repo's current
    `core.hooksPath` — it never sets it on the human's behalf (setting it
    is bootstrap's job for freshly-derived repos; an adopted repo may
    already have its own pre-existing hooksPath convention that adoption
    must not silently override)."""
    result = run(["git", "config", "--get", "core.hooksPath"], target)
    value = result["stdout"].strip()
    if result["returncode"] != 0 or not value:
        status = "unset"
    elif value == ".githooks":
        status = "set"
    else:
        status = "different"
    return {"status": status, "value": value or None}


def run_sync_codex_check(target: Path) -> dict[str, Any]:
    """Read-only diagnostic: `sync-codex-adapters.py --check` inside the
    target repo (adoption never writes/regenerates adapters on the
    target's behalf; it only reports whether they're currently in sync)."""
    script = target / "scripts" / "sync-codex-adapters.py"
    if not script.exists():
        return {"status": "missing", "path": "scripts/sync-codex-adapters.py"}
    # An adoption target is always downstream: correct, byte-matching
    # generated adapters that were never `git add`ed must pass, not be
    # reported as missing (issue #67 D1) — explicit, not auto-detected.
    result = run(
        [sys.executable, str(script), "--check", "--context", "downstream"], target, timeout=60
    )
    return {
        "status": "ok" if result["returncode"] == 0 else "failed",
        "returncode": result["returncode"],
        "stdout_tail": result["stdout"][-2000:],
    }


def run_check_agent_harness(target: Path) -> dict[str, Any]:
    """Read-only diagnostic: `check-agent-harness.py --strict` inside the
    target repo. Review MINOR-4: the shared checklist contract
    (`_agent_surface.agent_surface_checklist`) documents the
    `check_agent_harness_strict` ground-truth field as exactly this
    validator's result, so adoption runs the real script instead of
    masquerading `validate-governance.py --strict`'s aggregate return code
    under the harness field name (bootstrap keeps passing `None` →
    `not-run-by-caller`, which the contract also allows)."""
    script = target / "scripts" / "check-agent-harness.py"
    if not script.exists():
        return {"status": "missing", "path": "scripts/check-agent-harness.py"}
    result = run([sys.executable, str(script), "--strict"], target, timeout=120)
    return {
        "status": "ok" if result["returncode"] == 0 else "failed",
        "returncode": result["returncode"],
        "stdout_tail": result["stdout"][-2000:],
    }


def agent_surface_report(target: Path) -> dict[str, Any]:
    """B6/D2c: adoption's Claude/Codex postflight checklist, built on the
    same shared `_agent_surface.agent_surface_checklist()` bootstrap uses
    (plan A4) so the two entry points do not drift. The harness ground
    truth is a dedicated `check-agent-harness.py --strict` run (see
    `run_check_agent_harness`, review MINOR-4) — `prove()`'s
    `validate-governance.py --strict` result stays its own separate field
    in the proof report."""
    hooks_state = inspect_hooks_path(target)
    hooks_item = {
        "id": "core-hooks-path",
        "status": hooks_state["status"],
        "note": (
            "git config core.hooksPath .githooks 是 Claude/Codex 两侧共用的 pre-commit 前提；"
            "adoption 只读取目标 repo 当前状态、不代为设置（是否覆盖已有 hooksPath 配置由 human 决定）；"
            f"当前检测值: {hooks_state['value']!r}。"
        ),
    }
    sync_codex_result = run_sync_codex_check(target)
    harness_result = run_check_agent_harness(target)
    return AGENT_SURFACE.agent_surface_checklist(target, hooks_item, sync_codex_result, harness_result)


def prove(args: argparse.Namespace) -> dict[str, Any]:
    target = args.target.resolve()
    require_git_repo(target)
    plan = read_json(state_path(target, PLAN_FILE))
    integrity = integrity_result(target)
    governance = None
    if (target / "scripts" / "validate-governance.py").exists():
        governance = run([sys.executable, "scripts/validate-governance.py", "--strict"], target, timeout=180)
    smoke = evaluate_smoke(plan, target, args.test_timeout)
    warnings: list[dict[str, Any]] = []
    if smoke["result"] != "pass":
        warnings.append(
            {
                "item": "original_test",
                "result": smoke["result"],
                "reason": smoke["unverified_reason"],
            }
        )
    agent_surface = agent_surface_report(target)
    state_blocker = state_redirect_blocker(target)
    if state_blocker:
        print(f"[prove] BLOCKER {state_blocker}")
    report = {
        "schema": "template-adoption-proof-v1",
        "created_at": now_iso(),
        "target": str(target),
        "origin": plan.get("origin"),
        "integrity": integrity,
        "governance": governance,
        "smoke": smoke,
        # Back-compat field: the raw exec result of the smoke command (or
        # None when skipped). Prefer `smoke` for the structured contract.
        "original_test": smoke.get("exec"),
        "warnings": warnings,
        "agent_surface": agent_surface,
    }
    if not args.dry_run:
        write_report(target, plan, report)
    # C1/C2 (decided, see plan doc open question 5): the prove process exit
    # code is decoupled from the smoke result. It is non-zero only for
    # adoption's own integrity failure (tracked-byte mismatch or unresolved
    # normalize blockers); a fail/skipped/unknown smoke result stays exit 0
    # but must be visible via the `warnings` field above, never silently
    # dropped.
    append_log(target, "prove", "ok" if integrity["ok"] else "failed", report, args.dry_run)
    print(
        "[prove] integrity="
        + ("ok" if integrity["ok"] else "failed")
        + f" governance_rc={None if governance is None else governance['returncode']}"
        + f" smoke={smoke['result']}"
    )
    if warnings:
        for w in warnings:
            print(f"[prove] WARNING {w['item']}: result={w['result']} reason={w['reason']}")
    return report


def write_report(target: Path, plan: dict[str, Any], proof: dict[str, Any]) -> None:
    governance = proof.get("governance")
    original_test = proof.get("original_test")
    smoke = proof.get("smoke") or {}
    warnings = proof.get("warnings") or []
    phase_rows = read_phase_log(target)
    normalize_rows = [r for r in phase_rows if r.get("phase") == "normalize"]
    normalize = normalize_rows[-1].get("details", {}) if normalize_rows else {}
    moved = normalize.get("moved", [])
    blockers = normalize.get("blockers", [])
    template_anchor = normalize.get("template_anchor")
    current_pollution = [
        e["path"]
        for e in list_root_entries(target)
        if not e["allowed_root"] and not e["protected"] and not e["template_control_item"]
    ]
    lines = [
        "# Template Adoption Report",
        "",
        f"- created_at: `{proof['created_at']}`",
        f"- target: `{proof['target']}`",
        f"- origin: `{proof.get('origin')}`",
        f"- policy: `{plan.get('policy')}`",
        f"- import_root: `{plan.get('import_root')}`",
        f"- integrity: `{'ok' if proof['integrity']['ok'] else 'failed'}`",
        f"- governance_returncode: `{None if governance is None else governance['returncode']}`",
        f"- original_test_returncode: `{None if original_test is None else original_test['returncode']}`",
        f"- smoke_result: `{smoke.get('result')}`",
        f"- baseline_files_present: `{proof['integrity']['present']}/{proof['integrity']['baseline_files']}`",
        f"- moved_root_entries: `{len(moved)}`",
        f"- normalize_blockers: `{len(blockers)}`",
        f"- template_anchor: `{json.dumps(template_anchor, sort_keys=True)}`",
        f"- remaining_root_pollution: `{len(current_pollution)}`",
        "",
        "## Notes",
        "",
        "- This report is generated by `scripts/adopt-existing-repo.py`.",
        "- Original tracked files are checked by content hash, not by path.",
        "- Before staging, Git may show original paths as deleted and imported paths as untracked; "
        "that is expected for a move-based migration. Use `check-adoption-integrity.py` to verify bytes.",
        "- Protected bytes are not moved by the conservative policy.",
        "- The smoke result below is about the *target repo's own* native test command, not about "
        "whether this adoption tool itself succeeded (that is `integrity`); see the smoke contract "
        "in plans/20260712-bootstrap-adoption-proof.zh.md (C1).",
        "",
        "## Smoke (target repo native test command)",
        "",
        f"- command_source: `{smoke.get('command_source')}`",
        f"- command: `{smoke.get('command')}`",
        f"- result: `{smoke.get('result')}`",
        f"- unverified_reason: `{smoke.get('unverified_reason')}`",
        "",
        "## Warnings",
        "",
    ]
    if warnings:
        lines.append(
            "The smoke/original-test result below did **not** reach `pass`. This does NOT make "
            "`prove`/`check-adoption-integrity.py` exit non-zero (decided, open question 5) -- it is "
            "surfaced here as an explicit, machine-readable warning instead:"
        )
        lines.append("")
        for w in warnings:
            lines.append(f"- `{w['item']}`: result=`{w['result']}` reason=`{w['reason']}`")
        lines.append("")
    else:
        lines.extend(["No warnings. Smoke result is `pass` (or explicitly not applicable).", ""])
    lines.extend(["## Normalize", ""])
    if moved:
        lines.extend(["Moved root entries:", ""])
        lines.extend(f"- `{row['from']}` -> `{row['to']}`" for row in moved)
        lines.append("")
    else:
        lines.extend(["No root entries were moved.", ""])
    if blockers:
        lines.extend(["Blockers:", ""])
        lines.extend(f"- `{b}`" for b in blockers)
        lines.append("")
    if current_pollution:
        lines.extend(["Remaining root pollution:", ""])
        lines.extend(f"- `{p}`" for p in current_pollution)
        lines.append("")
    else:
        lines.extend(["Remaining root pollution: `0`", ""])
    surface = proof.get("agent_surface")
    if surface:
        lines.extend(["## Claude/Codex loading checklist", ""])
        lines.append(f"- Claude: `{json.dumps(surface['claude'], sort_keys=True)}`")
        lines.append(f"- Codex: `{json.dumps(surface['codex'], sort_keys=True)}`")
        lines.append(f"- ground_truth: `{json.dumps(surface['ground_truth'], sort_keys=True, ensure_ascii=False)}`")
        lines.append("")
        lines.append("Human out-of-band prerequisites (not auto-verifiable/auto-completable):")
        lines.append("")
        for item in surface["human_out_of_band"]:
            lines.append(f"- `{item['id']}` status=`{item['status']}` — {item['note']}")
        lines.append("")
    # Review round 3 BLOCKER-C: the report path shares `lab/docs/...` with
    # the state dir — never write it through a symlinked segment either;
    # redirect to the /tmp state fallback and say so loudly.
    try:
        path = safe_target_path(target, *REPORT_PATH.parts)
    except SymlinkOnPath as e:
        path = checked_fallback_path(target, REPORT_PATH.name)
        print(
            f"[prove] BLOCKER report-redirect: '{e.rel}' on the report path is a "
            f"symlink; report written to {path} instead"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def read_phase_log(target: Path) -> list[dict[str, Any]]:
    path = state_path(target, LOG_FILE)
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rows.append(json.loads(line))
    return rows


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", type=Path)
    parser.add_argument(
        "--origin",
        required=True,
        help="upstream template <owner/repo>; required for every phase and never inferred",
    )
    parser.add_argument(
        "--phase",
        choices=["discover", "baseline", "scaffold", "normalize", "prove", "all"],
        default="discover",
    )
    parser.add_argument("--policy", choices=["conservative"], default="conservative")
    parser.add_argument("--project-name")
    parser.add_argument("--test-command", default="auto")
    parser.add_argument("--test-timeout", type=int, default=120)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--allow-blocked-normalize",
        action="store_true",
        help="record scaffold/normalize blockers but continue; useful for partial reports",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    try:
        TEMPLATE_ANCHOR.validate_origin(args.origin)
    except TEMPLATE_ANCHOR.TemplateAnchorError as exc:
        raise SystemExit(str(exc)) from exc
    phases = ["discover", "baseline", "scaffold", "normalize", "prove"]
    if args.phase != "all":
        phases = [args.phase]
    exit_code = 0
    for phase in phases:
        result = {
            "discover": discover,
            "baseline": baseline,
            "scaffold": scaffold,
            "normalize": normalize,
            "prove": prove,
        }[phase](args)
        if phase == "prove" and isinstance(result, dict):
            # C1/C2 (decided): exit code reflects adoption's own integrity
            # only (tracked-byte mismatch or unresolved normalize blockers),
            # never the target repo's own smoke/original-test result.
            integrity = result.get("integrity", {})
            if not integrity.get("ok", True):
                exit_code = 1
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
