"""Narrow `.template.toml` create/confirm/conflict helper.

Bootstrap and adoption have distinct workflows, but share this one anchor
contract: callers supply an explicit origin, matching anchors retain their
recorded version, and malformed, conflicting, or symlinked anchors fail
closed. Bootstrap may opt into its established explicit force override;
adoption intentionally does not.
"""
from __future__ import annotations

import json
import os
import re
import stat
import tempfile
import tomllib
from pathlib import Path
from typing import Any

ORIGIN_RE = re.compile(r"^[\w.-]+/[\w.-]+$")
ANCHOR_NAME = ".template.toml"


class TemplateAnchorError(RuntimeError):
    """The target anchor is unsafe or incompatible with the requested origin."""


def validate_origin(origin: str) -> None:
    if not ORIGIN_RE.match(origin):
        raise TemplateAnchorError(
            f"--origin must look like <owner/repo>, got {origin!r} "
            "(not inferred; pass it explicitly)"
        )


def _path(target: Path) -> Path:
    return target / ANCHOR_NAME


def _existing_anchor(path: Path) -> dict[str, Any] | None:
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError:
        return None
    if stat.S_ISLNK(mode):
        raise TemplateAnchorError(f"template anchor is a symlink: {path}; refusing to follow or write through it")
    if not stat.S_ISREG(mode):
        raise TemplateAnchorError(f"template anchor is not a regular file: {path}")
    try:
        parsed = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise TemplateAnchorError(f"malformed template anchor: {path}: {exc}") from exc
    template = parsed.get("template")
    if not isinstance(template, dict):
        raise TemplateAnchorError(f"malformed template anchor: {path} lacks a [template] table")
    origin = template.get("origin")
    version = template.get("version")
    if not isinstance(origin, str) or not origin or not isinstance(version, str) or not version:
        raise TemplateAnchorError(
            f"malformed template anchor: {path} requires non-empty string template.origin and template.version"
        )
    return {"origin": origin, "version": version}


def read(target: Path) -> dict[str, Any] | None:
    """Read and validate the target's anchor without following symlinks."""
    return _existing_anchor(_path(target))


def preflight(target: Path, origin: str, version: str, *, allow_force: bool = False) -> dict[str, Any]:
    """Return a non-mutating create/confirm/overwrite decision or fail closed."""
    validate_origin(origin)
    path = _path(target)
    existing = _existing_anchor(path)
    if existing is None:
        return {"action": "create", "origin": origin, "version": version}
    if existing["origin"] == origin:
        return {"action": "confirm", "origin": origin, "version": existing["version"]}
    if not allow_force:
        raise TemplateAnchorError(
            f"origin mismatch: {path} already has origin={existing['origin']!r}, "
            f"requested --origin={origin!r}. Refusing to overwrite silently."
        )
    return {
        "action": "overwrite",
        "origin": origin,
        "version": version,
        "previous_origin": existing["origin"],
    }


def _content(origin: str, version: str) -> str:
    return "\n".join(
        [
            "[template]",
            f"origin = {json.dumps(origin, ensure_ascii=False)}",
            f"version = {json.dumps(version, ensure_ascii=False)}",
            "",
        ]
    )


def apply_atomic(target: Path, decision: dict[str, Any]) -> dict[str, Any]:
    """Apply a preflighted decision without following the anchor path.

    The caller must run this only after its own non-anchor mutations have
    succeeded. `os.replace` keeps anchor writes atomic within the target
    directory; a fresh preflight closes the ordinary non-concurrent gap.
    """
    action = decision["action"]
    if action == "confirm":
        return {"status": "confirmed", "origin": decision["origin"], "version": decision["version"]}
    if action not in {"create", "overwrite"}:
        raise TemplateAnchorError(f"invalid template-anchor action: {action!r}")

    # Recheck immediately before replacement so a normal concurrent edit is
    # rejected rather than silently overwritten. The callers document the
    # remaining adversarial TOCTOU limitation of their broader workflows.
    current = preflight(target, decision["origin"], decision["version"], allow_force=action == "overwrite")
    if current["action"] != action:
        raise TemplateAnchorError(
            "template anchor changed after preflight; refusing to apply a stale decision"
        )

    fd, temporary = tempfile.mkstemp(prefix=".template.toml.", suffix=".tmp", dir=target)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(_content(decision["origin"], decision["version"]))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, _path(target))
    except OSError as exc:
        raise TemplateAnchorError(f"could not atomically write template anchor: {exc}") from exc
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    status = "created" if action == "create" else "overwritten"
    result = {"status": status, "origin": decision["origin"], "version": decision["version"]}
    if "previous_origin" in decision:
        result["previous_origin"] = decision["previous_origin"]
    return result


def ensure(
    target: Path, origin: str, version: str, *, allow_force: bool = False, dry_run: bool = False
) -> dict[str, Any]:
    """Bootstrap-facing convenience wrapper around preflight/apply."""
    decision = preflight(target, origin, version, allow_force=allow_force)
    if dry_run:
        status = {"create": "would-create", "confirm": "confirmed", "overwrite": "would-overwrite"}[decision["action"]]
        result = {"status": status, "origin": decision["origin"], "version": decision["version"]}
        if "previous_origin" in decision:
            result["previous_origin"] = decision["previous_origin"]
        return result
    return apply_atomic(target, decision)
