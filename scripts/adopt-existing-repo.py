#!/usr/bin/env python3
"""Adopt an existing Git repo into this template shape.

The script is intentionally conservative:
- no deletes;
- no overwrites without first preserving the original file;
- no protected data/model/checkpoint byte moves;
- state is written into lab/docs/audits/template-adoption/state.
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
    spec.loader.exec_module(module)
    return module


AGENT_SURFACE = _load_sibling("_agent_surface")

STATE_DIR = Path("lab/docs/audits/template-adoption/state")
REPORT_PATH = Path("lab/docs/audits/template-adoption-report.md")
PLAN_FILE = "adoption-plan.json"
BASELINE_FILE = "baseline.json"
LOG_FILE = "phase-log.jsonl"

CONTROL_ITEMS = [
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


def rel_posix(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def state_root(target: Path) -> Path:
    return target / STATE_DIR


def state_path(target: Path, name: str) -> Path:
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

    Returns repo-root-relative posix paths under `name` that match a
    protected pattern and are NOT byte-identical to the template's own
    file at the same relative path. The template itself ships placeholder
    docs under `lab/data/`, `lab/runs/`, `lab/models/`, `lab/infra/private/`
    — scaffold legitimately copies those in, and an unmodified copy must
    not turn every re-run into a blocker. Anything else that matches a
    protected pattern makes the WHOLE entry a blocker: the conservative
    policy never does partial moves.
    """
    hits: list[str] = []
    if protected_path(name):
        hits.append(name)
    root = target / name
    if not root.is_dir():
        return hits[:limit]
    for walk_root, dirnames, filenames in os.walk(root):
        walk_path = Path(walk_root)
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIR_NAMES]
        for child in dirnames:
            rel = rel_posix(walk_path / child, target)
            if protected_path(rel) and not (TEMPLATE_ROOT / rel).is_dir():
                hits.append(rel)
        for filename in filenames:
            path = walk_path / filename
            rel = rel_posix(path, target)
            if not protected_path(rel):
                continue
            if hash_matches_template(path, TEMPLATE_ROOT / rel) is True:
                continue  # unmodified template placeholder, not target data
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
    """
    protected_hits = protected_hits_within(target, name)
    if protected_hits:
        if protected_hits == [name]:
            detail = (
                f"matches a forbidden/protected path (lab/data, lab/runs, lab/models, "
                f"lab/infra/private, checkpoints, wandb, .env, ...): '{name}'"
            )
        else:
            detail = (
                f"'{name}' contains protected content ({', '.join(protected_hits)})"
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


def project_slug(target: Path, explicit: str | None) -> str:
    base = explicit or target.name
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", base.strip()).strip("-._")
    return slug or "imported-project"


def detect_test_command(target: Path, requested: str | None) -> str | None:
    if requested == "none":
        return None
    if requested and requested != "auto":
        return requested
    if (target / "pytest.ini").exists() or (target / "tests").is_dir():
        return "python -m pytest"
    if (target / "Makefile").exists():
        text = (target / "Makefile").read_text(encoding="utf-8", errors="replace")
        if re.search(r"^test:", text, re.MULTILINE):
            return "make test"
    return None


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
    plan = {
        "schema": "template-adoption-plan-v1",
        "created_at": now_iso(),
        "target": str(target),
        "template_root": str(TEMPLATE_ROOT),
        "policy": args.policy,
        "project_slug": slug,
        "state_dir": STATE_DIR.as_posix(),
        "report_path": REPORT_PATH.as_posix(),
        "test_command": detect_test_command(target, args.test_command),
        "root_entries": root_entries,
        "classification": classification,
        "protected_roots": protected_roots,
        "root_pollution": root_pollution,
        "template_conflicts": conflicts,
        "conservative_import_roots": conservative_import_roots,
        "template_control_item_roots": template_control_item_roots,
        "import_root": f"lab/code/imported/{slug}",
        "normalize_blockers": [
            f"{e['category']}: {e['path']} — {e['reason']}" for e in classification if e["blocker"]
        ],
    }
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
    write_json(state_path(target, BASELINE_FILE), data, args.dry_run)
    append_log(target, "baseline", "ok", {"tracked_files": len(tracked)}, args.dry_run)
    print(f"[baseline] tracked_files={len(tracked)}")
    return data


def unique_preserve_path(target: Path, rel: str) -> Path:
    base = target / "human" / "imported" / "adoption-conflicts" / rel
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
        preserve_existing(target, rel, dry_run)
    if dry_run:
        print(f"DRY-RUN copy {src} -> {dst}")
        return "copy"
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return "copy"


def copy_template_tree(src_root: Path, dst_root: Path, target: Path, dry_run: bool) -> dict[str, int]:
    counts = {"copy": 0, "same": 0, "skip": 0, "protected_skip": 0}
    for root, dirnames, filenames in os.walk(src_root):
        root_path = Path(root)
        rel_root = root_path.relative_to(TEMPLATE_ROOT).as_posix()
        dirnames[:] = [
            d for d in dirnames if not template_excluded(f"{rel_root}/{d}".strip("./"), root_path / d)
        ]
        for filename in filenames:
            src = root_path / filename
            rel = src.relative_to(TEMPLATE_ROOT).as_posix()
            if template_excluded(rel, src):
                counts["skip"] += 1
                continue
            dst = target / rel
            status = copy_file_preserving(src, dst, rel, target, dry_run)
            counts[status] += 1
    return counts


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
    """
    target = args.target.resolve()
    require_git_repo(target)
    if not state_path(target, BASELINE_FILE).exists():
        baseline(args)
    counts = {"copy": 0, "same": 0, "skip": 0, "protected_skip": 0}
    blockers: list[str] = []
    for item in CONTROL_ITEMS:
        src = TEMPLATE_ROOT / item
        if not src.exists():
            continue
        protected_hits = protected_hits_within(target, item)
        if protected_hits:
            blockers.append(
                f"protected: {item} — contains protected content "
                f"({', '.join(protected_hits)}); scaffold skipped this control item entirely"
            )
            continue
        dst = target / item
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
            sub = copy_template_tree(src, dst, target, args.dry_run)
            counts = {k: counts[k] + sub[k] for k in counts}
    status = "blocked" if blockers else "ok"
    append_log(target, "scaffold", status, {**counts, "blockers": blockers}, args.dry_run)
    print(
        f"[scaffold] copied={counts['copy']} same={counts['same']} skipped={counts['skip']} "
        f"protected_skipped={counts['protected_skip']} blockers={len(blockers)}"
    )
    for blocker in blockers:
        print(f"[scaffold] BLOCKER {blocker}")
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

    Review MAJOR-3: the persisted plan is a *proposal*, not a trusted
    authorization. Before moving anything, normalize re-verifies the
    safety invariants against the tree as it exists now: the category must
    be one of the known four, the entry (and its descendants) must not
    have become protected since discover, and the recorded target_path
    must be sane (present, non-protected). A stale/tampered plan entry is
    rejected with a blocker instead of executed."""
    target = args.target.resolve()
    require_git_repo(target)
    plan = read_json(state_path(target, PLAN_FILE))
    classification = plan.get("classification")
    if classification is None:
        # Backward compatibility: a plan.json written before B1 has no
        # per-entry classification — recompute it now with the same
        # conservative rules rather than silently doing nothing.
        classification = classify_root_entries(target, plan["project_slug"])
    known_categories = {"protected", "template_control_item", "conflict", "conservative_import"}
    moved: list[dict[str, str]] = []
    blockers: list[str] = []
    for entry in sorted(classification, key=lambda e: e["path"]):
        name = entry["path"]
        if name == ".git":
            continue
        src = target / name
        if not src.exists():
            # Entry no longer present between discover and normalize
            # (e.g. already moved by a prior partial run) — nothing to do.
            continue
        category = entry.get("category")
        if category not in known_categories:
            blockers.append(
                f"unknown-category: {name} — plan entry carries unrecognized "
                f"category {category!r}; refusing to act on it"
            )
            continue
        if entry["blocker"]:
            blockers.append(f"{category}: {name} — {entry['reason']}")
            continue
        if category == "template_control_item":
            continue  # stays in place by definition, never moved
        # category == "conservative_import" and plan said non-blocker:
        # re-check the current tree before trusting the persisted plan.
        current_hits = protected_hits_within(target, name)
        if current_hits:
            blockers.append(
                f"protected: {name} — protected content present at normalize time "
                f"({', '.join(current_hits)}); stale plan rejected for this entry"
            )
            continue
        if name in CONTROL_ITEMS:
            blockers.append(
                f"plan-mismatch: {name} — plan says {category!r} but the entry is a "
                "template control item; stale/tampered plan rejected for this entry"
            )
            continue
        target_path = entry.get("target_path")
        if not target_path or protected_path(target_path):
            blockers.append(
                f"plan-mismatch: {name} — plan target_path {target_path!r} is missing "
                "or protected; refusing to move"
            )
            continue
        dst = target / target_path
        if dst.exists():
            blockers.append(
                f"conflict: {name} — destination appeared after discover: "
                f"{dst.relative_to(target).as_posix()}"
            )
            continue
        if args.dry_run:
            print(f"DRY-RUN move {src} -> {dst}")
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
        moved.append({"from": name, "to": entry["target_path"]})
    status = "blocked" if blockers else "ok"
    append_log(target, "normalize", status, {"moved": moved, "blockers": blockers}, args.dry_run)
    print(f"[normalize] moved={len(moved)} blockers={len(blockers)}")
    if blockers and not args.allow_blocked_normalize:
        raise SystemExit("normalize blocked by protected/conflicting paths: " + ", ".join(blockers))
    return {"moved": moved, "blockers": blockers}


def current_hash_index(target: Path) -> dict[str, list[str]]:
    index: dict[str, list[str]] = {}
    for root, dirnames, filenames in os.walk(target):
        root_path = Path(root)
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIR_NAMES]
        if ".git" in root_path.parts:
            continue
        for filename in filenames:
            path = root_path / filename
            if path.stat().st_size > LARGE_HASH_LIMIT:
                continue
            digest = sha256_file(path)
            index.setdefault(digest, []).append(rel_posix(path, target))
    return index


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
    return {
        "schema": "template-adoption-integrity-v1",
        "checked_at": now_iso(),
        "baseline_files": len(baseline_data["tracked_files"]),
        "present": present,
        "missing": missing,
        "ok": not missing,
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
    result = run([sys.executable, str(script), "--check"], target, timeout=60)
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
    original_test = None
    if plan.get("test_command"):
        cwd = target / plan["import_root"]
        if not cwd.exists():
            cwd = target
        original_test = run(plan["test_command"], cwd, shell=True, timeout=args.test_timeout)
    agent_surface = agent_surface_report(target)
    report = {
        "schema": "template-adoption-proof-v1",
        "created_at": now_iso(),
        "target": str(target),
        "integrity": integrity,
        "governance": governance,
        "original_test": original_test,
        "agent_surface": agent_surface,
    }
    if not args.dry_run:
        write_report(target, plan, report)
    append_log(target, "prove", "ok" if integrity["ok"] else "failed", report, args.dry_run)
    print(
        "[prove] integrity="
        + ("ok" if integrity["ok"] else "failed")
        + f" governance_rc={None if governance is None else governance['returncode']}"
    )
    return report


def write_report(target: Path, plan: dict[str, Any], proof: dict[str, Any]) -> None:
    governance = proof.get("governance")
    original_test = proof.get("original_test")
    phase_rows = read_phase_log(target)
    normalize_rows = [r for r in phase_rows if r.get("phase") == "normalize"]
    normalize = normalize_rows[-1].get("details", {}) if normalize_rows else {}
    moved = normalize.get("moved", [])
    blockers = normalize.get("blockers", [])
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
        f"- policy: `{plan.get('policy')}`",
        f"- import_root: `{plan.get('import_root')}`",
        f"- integrity: `{'ok' if proof['integrity']['ok'] else 'failed'}`",
        f"- governance_returncode: `{None if governance is None else governance['returncode']}`",
        f"- original_test_returncode: `{None if original_test is None else original_test['returncode']}`",
        f"- baseline_files_present: `{proof['integrity']['present']}/{proof['integrity']['baseline_files']}`",
        f"- moved_root_entries: `{len(moved)}`",
        f"- normalize_blockers: `{len(blockers)}`",
        f"- remaining_root_pollution: `{len(current_pollution)}`",
        "",
        "## Notes",
        "",
        "- This report is generated by `scripts/adopt-existing-repo.py`.",
        "- Original tracked files are checked by content hash, not by path.",
        "- Before staging, Git may show original paths as deleted and imported paths as untracked; "
        "that is expected for a move-based migration. Use `check-adoption-integrity.py` to verify bytes.",
        "- Protected bytes are not moved by the conservative policy.",
        "",
        "## Normalize",
        "",
    ]
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
    path = target / REPORT_PATH
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
        help="record normalize blockers but continue; useful for partial reports",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    phases = ["discover", "baseline", "scaffold", "normalize", "prove"]
    if args.phase != "all":
        phases = [args.phase]
    for phase in phases:
        {
            "discover": discover,
            "baseline": baseline,
            "scaffold": scaffold,
            "normalize": normalize,
            "prove": prove,
        }[phase](args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
