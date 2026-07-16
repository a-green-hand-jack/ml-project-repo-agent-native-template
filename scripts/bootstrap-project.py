#!/usr/bin/env python3
"""Bootstrap a repo freshly derived from this template ("Use this template" /
`gh repo create --template` / clone+reinit) into a landed, self-consistent state.

The target already contains the full template tree (GitHub's "Use this
template" copies the tree; it does not scaffold a bare directory — see
`adopt-existing-repo.py` for the "existing repo with unrelated content"
case, which is a different problem with a different safety envelope).
The README main path is *self-bootstrap*: the derived repo runs its own
copy of this script against itself (`python scripts/bootstrap-project.py .
--origin <owner/repo>` inside the derived repo). Running the upstream
checkout's copy against a separate target path also works. What is refused
(best-effort, not a security boundary) is bootstrapping the *upstream
template repo itself* — see `refuse_upstream_template()` for the criterion
and its known residual gaps.

Automated substeps (see plans/20260712-bootstrap-adoption-proof.zh.md, A2):
  1. `.template.toml` generation/confirmation (origin + version anchor).
     `--origin <owner/repo>` must be passed explicitly; this script never
     infers it from `git remote -v` or GitHub template metadata, and never
     asks interactively. If the target already has a `.template.toml` whose
     origin disagrees with `--origin`, this stops with a non-zero exit
     *before* touching anything else; pass `--force` to overwrite.
  2. `git config core.hooksPath .githooks` inside the target.
  3. `python scripts/sync-codex-adapters.py` inside the target (write, then
     `--check` to get a ground-truth pass/fail signal).
  4. `python scripts/validate-governance.py` inside the target.

Substeps that need human information are never guessed — they are reported
as todo/blocker items (CODEOWNERS owner, PROJECT.md, whether to delete
unused directories, Codex trust). See `human_todo_items()`.

Idempotent, with two-layer state semantics (plan A1):
  * `state/state.json` + `template-bootstrap-report.md` are *content-stable*:
    a confirming re-run whose outcome is substantively identical (same
    origin/version anchor, same substep results) leaves both files
    bit-for-bit untouched. `created_at` therefore means "when the recorded
    content last changed", not "when the script last ran".
  * `state/run-log.jsonl` is an *append-only audit log*: every non-dry run
    appends exactly one row (run timestamp, per-run transition such as
    created/confirmed, and a `content_changed` flag). Append-only growth is
    the intended audit semantic, not an idempotency violation.
Re-running with the same `--origin` does not rewrite `.template.toml` and
reports "confirmed" rather than "created"; the other substeps are naturally
idempotent (git config re-set is a no-op, adapters write only on diff,
governance just re-validates).

No third-party dependency (tomllib is stdlib on Python 3.11+, matching
`scripts/template-sync.py`). Exit code: 0 = landed cleanly (or `--dry-run`),
non-zero = origin conflict without `--force`, or a substep failed/missing.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import subprocess
import sys
import tomllib
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

STATE_DIR = Path("lab/docs/audits/template-bootstrap/state")
REPORT_PATH = Path("lab/docs/audits/template-bootstrap-report.md")
STATE_FILE = "state.json"
LOG_FILE = "run-log.jsonl"

ORIGIN_RE = re.compile(r"^[\w.-]+/[\w.-]+$")
PLACEHOLDER_RE = re.compile(r"<[^<>\n]{2,120}>")
TEMPLATE_DEFAULT_OWNER = "@a-green-hand-jack"


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def run(cmd: list[str], cwd: Path, timeout: int = 120) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            cmd, cwd=cwd, text=True, capture_output=True, timeout=timeout, check=False
        )
        return {
            "command": " ".join(cmd),
            "returncode": proc.returncode,
            "stdout": proc.stdout[-4000:],
            "stderr": proc.stderr[-4000:],
            "timeout": False,
        }
    except subprocess.TimeoutExpired as e:
        return {
            "command": " ".join(cmd),
            "returncode": 124,
            "stdout": (e.stdout or "")[-4000:] if isinstance(e.stdout, str) else "",
            "stderr": (e.stderr or "")[-4000:] if isinstance(e.stderr, str) else "",
            "timeout": True,
        }


def require_git_repo(target: Path) -> None:
    if not target.exists() or not target.is_dir():
        raise SystemExit(f"target is not a directory: {target}")
    if not (target / ".git").exists():
        raise SystemExit(
            f"target is not a Git repo: {target} "
            "(bootstrap expects `git init`/`git clone` to already have happened)"
        )


def _normalize_slug(slug: str) -> str:
    """Comparison form of a <owner/repo> slug, per hosting-platform semantics.

    GitHub-style slugs are case-insensitive and a trailing `.git` (or `/`)
    is URL decoration, not identity — strip both and lowercase so that e.g.
    `Acme/Repo.git` and `acme/repo` compare equal.
    """
    slug = slug.strip().rstrip("/")
    if slug.lower().endswith(".git"):
        slug = slug[: -len(".git")]
    return slug.lower()


def _origin_remote_slugs(target: Path) -> set[str]:
    """Normalized <owner/repo> slugs of the target's *origin* remote only.

    Only the identity remote (`origin`) participates in the upstream-template
    refusal criterion. A legitimately derived repo commonly carries extra
    remotes — e.g. `upstream` pointing back at the template for
    template-sync — and those must NOT trip the guard (Codex review round 2,
    MAJOR-1). Both fetch and push URLs of `origin` are considered.
    """
    proc = run(["git", "remote", "-v"], target)
    slugs: set[str] = set()
    if proc["returncode"] != 0:
        return slugs
    for line in proc["stdout"].splitlines():
        parts = line.split()
        if len(parts) < 2 or parts[0] != "origin":
            continue
        m = re.search(r"[:/]([\w.-]+/[\w.-]+?)(?:\.[gG][iI][tT])?/?$", parts[1])
        if m:
            slugs.add(_normalize_slug(m.group(1)))
    return slugs


def refuse_upstream_template(target: Path, origin: str) -> None:
    """Best-effort refusal to bootstrap the *upstream template repo itself*.

    An earlier guard rejected `target == TEMPLATE_ROOT` (the repo containing
    this running script). That criterion was wrong: derived repos ship their
    own copy of this script, and the README main path is self-bootstrap
    (`python scripts/bootstrap-project.py .` inside the derived repo), where
    target == TEMPLATE_ROOT is the normal, intended case.

    What the guard tries to protect: don't dirty the upstream template repo
    by bootstrapping it into "a project derived from itself". Criterion: the
    caller already names the upstream explicitly via `--origin`; if the
    target's *identity remote* (`origin`) resolves to that same <owner/repo>
    slug (compared case-insensitively, `.git` suffix stripped), the target
    looks like a checkout of the upstream template — refuse before any
    mutation. Other remotes (`upstream` etc.) deliberately do NOT participate:
    a derived repo often keeps an `upstream` remote pointing back at the
    template (e.g. for template-sync), and that is a legitimate setup.

    This is a best-effort footgun guard, not a security boundary: a template
    checkout with no remotes (or with `origin` renamed/re-pointed) will not
    be caught, and that residual risk is accepted. (`--origin` is still never
    *inferred* from remotes — see 未解决问题 2; remotes are only read for
    this self-pollution check, never to fill in origin.)
    """
    if _normalize_slug(origin) in _origin_remote_slugs(target):
        raise SystemExit(
            "refusing to bootstrap the upstream template repo into itself: "
            f"target {target} has its `origin` remote pointing at --origin "
            f"{origin!r}. A derived project's origin remote should be its own "
            "slug (or absent for clone+reinit), not the template's."
        )


def validate_origin(origin: str) -> None:
    if not ORIGIN_RE.match(origin):
        raise SystemExit(
            f"--origin must look like <owner/repo>, got {origin!r} "
            "(not inferred; pass it explicitly — see 未解决问题 2)"
        )


def read_own_version() -> str:
    version_file = TEMPLATE_ROOT / "VERSION"
    if not version_file.exists():
        raise SystemExit(f"template root missing VERSION: {version_file}")
    return version_file.read_text(encoding="utf-8").strip()


def read_template_toml(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return tomllib.loads(path.read_text(encoding="utf-8")).get("template", {})


def write_template_toml(path: Path, origin: str, version: str) -> None:
    lines = [
        "[template]",
        f"origin = {json.dumps(origin, ensure_ascii=False)}",
        f"version = {json.dumps(version, ensure_ascii=False)}",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def ensure_template_toml(
    target: Path, origin: str, version: str, force: bool, dry_run: bool
) -> dict[str, Any]:
    path = target / ".template.toml"
    existing = read_template_toml(path)
    if existing is None:
        if dry_run:
            return {"status": "would-create", "origin": origin, "version": version}
        write_template_toml(path, origin, version)
        return {"status": "created", "origin": origin, "version": version}

    existing_origin = existing.get("origin")
    if existing_origin == origin:
        # Idempotent: same origin -> confirm, do not rewrite (not even version).
        return {
            "status": "confirmed",
            "origin": existing_origin,
            "version": existing.get("version"),
        }

    if not force:
        raise SystemExit(
            f"origin mismatch: {path} already has origin={existing_origin!r}, "
            f"requested --origin={origin!r}. Refusing to overwrite silently; "
            "pass --force to override (见开放问题 3 已决策)."
        )
    if dry_run:
        return {
            "status": "would-overwrite",
            "origin": origin,
            "version": version,
            "previous_origin": existing_origin,
        }
    write_template_toml(path, origin, version)
    return {
        "status": "overwritten",
        "origin": origin,
        "version": version,
        "previous_origin": existing_origin,
    }


def ensure_hooks_path(target: Path, dry_run: bool) -> dict[str, Any]:
    hooks_dir = target / ".githooks"
    if not hooks_dir.is_dir():
        # Plan A2 mandates `core.hooksPath .githooks`; a template-derived
        # repo without `.githooks/` is an incomplete tree, and silently
        # skipping would let a broken derivation look bootstrapped. Hard
        # failure (non-zero exit via main()'s ok-condition), never "skipped".
        return {
            "status": "failed",
            "reason": ".githooks/ missing — template tree incomplete; "
            "plan A2 requires core.hooksPath to be configured",
        }
    if dry_run:
        return {"status": "would-set", "value": "core.hooksPath=.githooks"}
    result = run(["git", "config", "core.hooksPath", ".githooks"], target)
    if result["returncode"] != 0:
        return {"status": "failed", "stderr": result["stderr"]}
    return {"status": "ok"}


def run_target_script(
    target: Path, rel: str, args: list[str], timeout: int = 180
) -> dict[str, Any]:
    script = target / "scripts" / rel
    if not script.exists():
        return {"status": "missing", "path": f"scripts/{rel}"}
    result = run([sys.executable, str(script), *args], target, timeout=timeout)
    return {
        "status": "ok" if result["returncode"] == 0 else "failed",
        "returncode": result["returncode"],
        "stdout_tail": result["stdout"][-2000:],
        "stderr_tail": result["stderr"][-2000:],
    }


def run_sync_codex_adapters(target: Path, dry_run: bool) -> dict[str, Any]:
    script = target / "scripts" / "sync-codex-adapters.py"
    if not script.exists():
        return {"status": "missing", "path": "scripts/sync-codex-adapters.py"}
    if dry_run:
        return {"status": "would-sync"}
    write_result = run([sys.executable, str(script)], target, timeout=60)
    # target 已在此之前写好 .template.toml（步骤 1 先于本步骤），结构上必是
    # downstream；显式传 context 而非依赖 auto 检测，见 issue #67 D1。
    check_result = run(
        [sys.executable, str(script), "--check", "--context", "downstream"], target, timeout=60
    )
    return {
        "status": "ok" if check_result["returncode"] == 0 else "failed",
        "write_returncode": write_result["returncode"],
        "check_returncode": check_result["returncode"],
        "check_stdout_tail": check_result["stdout"][-2000:],
    }


def run_governance(target: Path, dry_run: bool) -> dict[str, Any]:
    if dry_run:
        return {"status": "would-run"}
    return run_target_script(target, "validate-governance.py", [], timeout=180)


def _text_state(path: Path, still_default: Any) -> str:
    if not path.exists():
        return "missing"
    text = path.read_text(encoding="utf-8", errors="replace")
    return "still-default" if still_default(text) else "likely-customized"


def human_todo_items(target: Path) -> list[dict[str, Any]]:
    """Steps that need human information. Never guessed/auto-filled — only
    reported, with a best-effort *detected_state* for the ones we can read
    without modifying (see plan A3)."""
    codeowners = target / ".github" / "CODEOWNERS"
    project_md = target / "PROJECT.md"
    return [
        {
            "id": "codeowners-owner",
            "path": ".github/CODEOWNERS",
            "detected_state": _text_state(codeowners, lambda t: TEMPLATE_DEFAULT_OWNER in t),
            "action": "把默认 owner 换成该项目真实 GitHub 用户/团队",
        },
        {
            "id": "project-md",
            "path": "PROJECT.md",
            "detected_state": _text_state(project_md, lambda t: bool(PLACEHOLDER_RE.search(t))),
            "action": "填写研究对象、active family、trunk、remote/worktree 策略",
        },
        {
            "id": "prune-unused-dirs",
            "path": "(repo root)",
            "detected_state": "not-auto-detectable",
            "action": "模板是「一次建好，按需删减」，不是「一定全用」；决定并删除本项目用不到的目录",
        },
        {
            "id": "codex-trust",
            "path": ".codex/config.toml",
            "detected_state": "unknown",
            "action": (
                "在 Codex 里 trust 本 repo，否则 project hooks/config 不会加载"
                "（out-of-band 前提，脚本无法代做、也无法可靠探测）"
            ),
        },
        {
            "id": "reference-docs-version",
            "path": ".reference-docs/",
            "detected_state": "not-auto-detectable",
            "action": "保留或更新你信奉的 doctrine 版本（来源文档 + 实现覆盖说明）",
        },
    ]


def agent_surface_checklist(
    target: Path, hooks_result: dict[str, Any], harness_result: dict[str, Any] | None,
    sync_codex_result: dict[str, Any],
) -> dict[str, Any]:
    """Bootstrap-specific wrapper around the shared postflight checklist
    (`scripts/_agent_surface.py`, plan A4/D2c): builds the `core-hooks-path`
    entry from bootstrap's own `ensure_hooks_path()` result (bootstrap
    actively sets `core.hooksPath`), then delegates the shared
    claude/codex/ground_truth rendering to `_agent_surface`. See
    `adopt-existing-repo.py`'s `agent_surface_report()` for the adoption-side
    counterpart, which inspects rather than sets `core.hooksPath` (plan B6).
    """
    hooks_item = {
        "id": "core-hooks-path",
        "status": "auto-configured" if hooks_result.get("status") == "ok" else hooks_result.get("status"),
        "note": "git config core.hooksPath .githooks 已由 bootstrap 自动设置（per-clone，不随 git clone 复制，换机器需重跑）。",
    }
    return AGENT_SURFACE.agent_surface_checklist(target, hooks_item, sync_codex_result, harness_result)


def state_root(target: Path) -> Path:
    return target / STATE_DIR


def write_state(target: Path, report: dict[str, Any]) -> None:
    path = state_root(target) / STATE_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_existing_state(target: Path) -> dict[str, Any] | None:
    path = state_root(target) / STATE_FILE
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _stable_form(report: dict[str, Any]) -> dict[str, Any]:
    """Report content with per-run volatility removed, for change detection.

    - `created_at` is dropped: it records when content last changed (see
      `persist()`), so it must not itself count as a change.
    - `.template.toml` transition verbs (created/confirmed/overwritten) all
      collapse to "present": the *anchor facts* (origin, version) are the
      content; which transition a particular run took is per-run audit info
      and lives in `run-log.jsonl`, not in the stable state.
    """
    stable: dict[str, Any] = json.loads(json.dumps(report, sort_keys=True))
    stable.pop("created_at", None)
    tt = stable.get("template_toml") or {}
    if tt.get("status") in ("created", "confirmed", "overwritten"):
        tt["status"] = "present"
        tt.pop("previous_origin", None)
    return stable


def append_log(
    target: Path, run_time: str, report: dict[str, Any], content_changed: bool
) -> None:
    path = state_root(target) / LOG_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "time": run_time,
        "template_toml_status": report["template_toml"]["status"],
        "content_changed": content_changed,
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, sort_keys=True) + "\n")


def persist(target: Path, report: dict[str, Any], run_time: str) -> bool:
    """Two-layer persistence (see module docstring / plan A1).

    state.json + report.md are content-stable: rewritten only when the
    stable form of the outcome actually changed; a purely confirming run
    leaves them bit-for-bit untouched (created_at keeps meaning "when the
    recorded content last changed"). run-log.jsonl is append-only audit:
    every non-dry run appends one row. Returns whether content changed.
    """
    existing = read_existing_state(target)
    content_changed = existing is None or _stable_form(existing) != _stable_form(report)
    if content_changed:
        write_state(target, report)
        write_report(target, report)
    else:
        report["created_at"] = existing["created_at"]
    append_log(target, run_time, report, content_changed)
    return content_changed


def write_report(target: Path, report: dict[str, Any]) -> None:
    tt = report["template_toml"]
    hooks = report["hooks_path"]
    sync = report["sync_codex_adapters"]
    gov = report["governance"]
    surface = report["agent_surface"]
    lines = [
        "# Template Bootstrap Report",
        "",
        f"- created_at: `{report['created_at']}`",
        f"- target: `{report['target']}`",
        f"- template_toml: `{tt['status']}` (origin=`{tt.get('origin')}`, version=`{tt.get('version')}`)",
        f"- hooks_path: `{hooks['status']}`",
        f"- sync_codex_adapters: `{sync['status']}`",
        f"- governance: `{gov['status']}`",
        "",
        "## Notes",
        "",
        "- This report is generated by `scripts/bootstrap-project.py`.",
        "- Re-running with the same `--origin` is idempotent: `.template.toml` is confirmed, "
        "not rewritten; the other substeps are naturally idempotent.",
        "- Two-layer state semantics: this report and `state/state.json` are content-stable "
        "(a confirming run with no substantive change leaves them untouched; `created_at` is "
        "when content last changed), while `state/run-log.jsonl` is an append-only audit log "
        "(one row per run, by design).",
        "- Origin mismatch stops with a non-zero exit before any mutation unless `--force` is passed.",
        "",
        "## Human todo / blockers (never guessed)",
        "",
    ]
    for item in report["human_todo"]:
        lines.append(f"- `{item['id']}` ({item['path']}) — {item['action']} [detected: {item['detected_state']}]")
    lines.extend(["", "## Claude/Codex loading checklist", ""])
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


def bootstrap(args: argparse.Namespace) -> dict[str, Any]:
    target = args.target.resolve()
    require_git_repo(target)
    validate_origin(args.origin)
    refuse_upstream_template(target, args.origin)
    version = read_own_version()

    # Conflict check happens first and stops everything (no side effects yet)
    # unless --force — see 未解决问题 3.
    template_toml = ensure_template_toml(target, args.origin, version, args.force, args.dry_run)
    hooks_path = ensure_hooks_path(target, args.dry_run)
    sync_codex_adapters = run_sync_codex_adapters(target, args.dry_run)
    governance = run_governance(target, args.dry_run)
    human_todo = human_todo_items(target)
    agent_surface = agent_surface_checklist(target, hooks_path, None, sync_codex_adapters)

    run_time = now_iso()
    report = {
        "schema": "template-bootstrap-report-v1",
        "created_at": run_time,
        "target": str(target),
        "origin": args.origin,
        "version": version,
        "template_toml": template_toml,
        "hooks_path": hooks_path,
        "sync_codex_adapters": sync_codex_adapters,
        "governance": governance,
        "human_todo": human_todo,
        "agent_surface": agent_surface,
    }
    if not args.dry_run:
        content_changed = persist(target, report, run_time)
        print(
            "[bootstrap] state/report: "
            + ("written" if content_changed else "unchanged (confirming run; run-log appended)")
        )

    print(f"[bootstrap] .template.toml: {template_toml['status']}")
    print(
        f"[bootstrap] core.hooksPath: {hooks_path['status']}"
        + (f" ({hooks_path['reason']})" if "reason" in hooks_path else "")
    )
    print(f"[bootstrap] sync-codex-adapters: {sync_codex_adapters['status']}")
    print(f"[bootstrap] validate-governance: {governance['status']}")
    print(f"[bootstrap] human todo items: {len(human_todo)}")
    return report


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("target", type=Path)
    parser.add_argument(
        "--origin",
        required=True,
        help="upstream template <owner/repo>, e.g. a-green-hand-jack/ml-project-repo-agent-native-template "
        "(must be passed explicitly; never inferred)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="overwrite an existing .template.toml whose origin disagrees with --origin",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="report what would happen without writing/running anything mutating",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    report = bootstrap(args)
    if args.dry_run:
        return 0
    ok = (
        report["template_toml"]["status"] in ("created", "confirmed", "overwritten")
        # Plan A2: core.hooksPath is mandatory — "skipped" is not acceptable
        # (a missing .githooks now reports "failed", see ensure_hooks_path()).
        and report["hooks_path"]["status"] == "ok"
        and report["sync_codex_adapters"]["status"] == "ok"
        and report["governance"]["status"] == "ok"
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
