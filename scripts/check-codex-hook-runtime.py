#!/usr/bin/env python3
"""Audit Codex project-hook trust readiness without editing user-global state.

The supported trust action is interactive (`/hooks` inside Codex). This tool
keeps the repo side honest:

- `--manifest` shows the exact project hooks and referenced-script hashes;
- `--refresh-bundle` updates the shared bundle hash embedded in every Codex
  hook definition after a referenced script changes;
- `--check` fails when hook definitions carry a stale/missing bundle hash;
- `--status` only reports runtime-loaded after a fresh Codex SessionStart hook
  wrote a receipt matching the current bundle.

It deliberately does not parse or mutate `~/.codex/config.toml` trust internals.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
import tomllib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
CONFIG_REL = Path(".codex/config.toml")
RECEIPT_REL = Path(".codex/runtime/hook-receipt.json")
BUNDLE_ENV = "CODEX_HOOK_BUNDLE_SHA"
BUNDLE_RE = re.compile(rf"{BUNDLE_ENV}=(?:[0-9a-f]{{64}}|__CODEX_HOOK_BUNDLE_SHA__)")
PATH_RE = re.compile(r"(?:\.claude/hooks|scripts)/[A-Za-z0-9_./-]+\.py")
AUDIT_HELPERS = ("scripts/check-codex-hook-runtime.py",)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _config(repo: Path) -> dict[str, Any]:
    path = repo / CONFIG_REL
    return tomllib.loads(path.read_text(encoding="utf-8"))


def hook_entries(repo: Path) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    for event, groups in (_config(repo).get("hooks") or {}).items():
        if not isinstance(groups, list):
            continue
        for group_index, group in enumerate(groups):
            matcher = str(group.get("matcher", ""))
            for hook_index, hook in enumerate(group.get("hooks") or []):
                command = str(hook.get("command", ""))
                entries.append(
                    {
                        "event": str(event),
                        "matcher": matcher,
                        "group": str(group_index),
                        "hook": str(hook_index),
                        "command": command,
                    }
                )
    return entries


def referenced_scripts(repo: Path) -> list[dict[str, str]]:
    rels = sorted(
        {match for entry in hook_entries(repo) for match in PATH_RE.findall(entry["command"])}
        | set(AUDIT_HELPERS)
    )
    rows: list[dict[str, str]] = []
    for rel in rels:
        path = repo / rel
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"hook 引用不是 repo 内 regular file：{rel}")
        rows.append({"path": rel, "sha256": _sha256_bytes(path.read_bytes())})
    if not rows:
        raise ValueError(".codex/config.toml 没有可审计的 repo-local Python hook")
    return rows


def bundle_sha(repo: Path) -> str:
    payload = json.dumps(referenced_scripts(repo), sort_keys=True, separators=(",", ":"))
    return _sha256_bytes(payload.encode("utf-8"))


def refresh_bundle(repo: Path) -> int:
    config_path = repo / CONFIG_REL
    text = config_path.read_text(encoding="utf-8")
    digest = bundle_sha(repo)
    commands = [entry["command"] for entry in hook_entries(repo)]
    if not commands or any(BUNDLE_RE.search(command) is None for command in commands):
        print("[codex-hook-trust] ERROR: 每个 hook command 都必须声明 CODEX_HOOK_BUNDLE_SHA", file=sys.stderr)
        return 1
    updated = BUNDLE_RE.sub(f"{BUNDLE_ENV}={digest}", text)
    if updated != text:
        config_path.write_text(updated, encoding="utf-8")
    print(digest)
    return 0


def check_bundle(repo: Path) -> tuple[bool, str, list[dict[str, str]]]:
    try:
        digest = bundle_sha(repo)
        entries = hook_entries(repo)
    except (OSError, ValueError, tomllib.TOMLDecodeError) as exc:
        return False, str(exc), []
    stale: list[str] = []
    for entry in entries:
        match = BUNDLE_RE.search(entry["command"])
        if match is None or match.group(0) != f"{BUNDLE_ENV}={digest}":
            stale.append(f"{entry['event']}[{entry['group']}].hooks[{entry['hook']}]")
    if stale:
        return False, "bundle hash 缺失或过期：" + ", ".join(stale), entries
    return True, digest, entries


def write_receipt(repo: Path) -> int:
    ok, detail, _ = check_bundle(repo)
    if not ok:
        print(f"[codex-hook-trust] receipt refused: {detail}", file=sys.stderr)
        return 1
    if os.environ.get(BUNDLE_ENV) != detail:
        print("[codex-hook-trust] receipt refused: runtime bundle env 与当前 bundle 不一致", file=sys.stderr)
        return 1
    try:
        payload = json.load(sys.stdin)
    except (ValueError, TypeError):
        payload = {}
    receipt = {
        "schema": "codex-project-hook-receipt-v1",
        "repo_root": str(repo.resolve()),
        "bundle_sha256": detail,
        "event": str(payload.get("hook_event_name", "SessionStart")),
        "session_id": str(payload.get("session_id", "")),
        "observed_at": datetime.now(timezone.utc).isoformat(),
    }
    path = repo / RECEIPT_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix="hook-receipt-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(receipt, stream, ensure_ascii=False, sort_keys=True, indent=2)
            stream.write("\n")
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
    return 0


def runtime_status(repo: Path, as_json: bool) -> int:
    ok, detail, _ = check_bundle(repo)
    state: dict[str, Any] = {
        "status": "UNTRUSTED_OR_NOT_LOADED",
        "repo_root": str(repo.resolve()),
        "bundle_sha256": detail if ok else None,
        "reason": None if ok else detail,
        "receipt": str(RECEIPT_REL),
        "identity_observable": (repo / ".agent-identity").is_file(),
    }
    path = repo / RECEIPT_REL
    if ok and path.is_file() and not path.is_symlink():
        try:
            receipt = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            state["status"] = "STALE_OR_INVALID"
            state["reason"] = f"receipt 无法解析：{exc}"
        else:
            if receipt.get("repo_root") != str(repo.resolve()):
                state["status"] = "STALE_OR_INVALID"
                state["reason"] = "receipt 属于其它 repo/worktree"
            elif receipt.get("bundle_sha256") != detail:
                state["status"] = "STALE_OR_INVALID"
                state["reason"] = "hook bundle 已变化，必须重新打开 /hooks 审阅"
            else:
                state["status"] = "TRUSTED_AND_LOADED"
                state["reason"] = None
                state["session_id"] = receipt.get("session_id", "")
                state["observed_at"] = receipt.get("observed_at")
    if as_json:
        print(json.dumps(state, ensure_ascii=False, sort_keys=True, indent=2))
    else:
        print(f"[codex-hook-trust] {state['status']}")
        if state.get("reason"):
            print(f"reason: {state['reason']}")
        print(f"bundle_sha256: {state.get('bundle_sha256') or 'unavailable'}")
        print(f"identity_observable: {str(state['identity_observable']).lower()}")
    return 0 if state["status"] == "TRUSTED_AND_LOADED" else 2


def print_manifest(repo: Path, as_json: bool) -> int:
    ok, detail, entries = check_bundle(repo)
    result = {
        "status": "READY_FOR_REVIEW" if ok else "STALE",
        "bundle_sha256": detail if ok else None,
        "reason": None if ok else detail,
        "hooks": entries,
        "scripts": referenced_scripts(repo) if entries else [],
        "trust_action": "在该 repo 启动 Codex，运行 /hooks，逐项审阅并信任；退出后启动 fresh session",
        "revoke_action": "在该 repo 的 Codex /hooks 中禁用对应 non-managed hooks",
    }
    if as_json:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    else:
        print(f"[codex-hook-trust] {result['status']}")
        print(f"bundle_sha256: {result.get('bundle_sha256') or 'unavailable'}")
        for row in result["scripts"]:
            print(f"- {row['path']} sha256={row['sha256']}")
        print(f"trust: {result['trust_action']}")
        print(f"revoke: {result['revoke_action']}")
    return 0 if ok else 1


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--check", action="store_true")
    group.add_argument("--manifest", action="store_true")
    group.add_argument("--status", action="store_true")
    group.add_argument("--refresh-bundle", action="store_true")
    group.add_argument("--write-receipt", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if args.refresh_bundle:
        return refresh_bundle(REPO)
    if args.write_receipt:
        return write_receipt(REPO)
    if args.status:
        return runtime_status(REPO, args.json)
    if args.manifest:
        return print_manifest(REPO, args.json)
    ok, detail, _ = check_bundle(REPO)
    print(f"[codex-hook-trust] {'OK' if ok else 'FAIL'}: {detail}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
