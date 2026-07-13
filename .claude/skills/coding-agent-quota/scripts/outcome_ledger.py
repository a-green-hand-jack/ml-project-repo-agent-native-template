#!/usr/bin/env python3
"""Outcome ledger for quota+outcome aware routing (coding-agent-quota skill).

Append-only JSONL ledger with two record types linked by ``decision_id``:

- ``decision``: written at dispatch time. ``outcome_status`` is always
  ``pending`` and the record must NOT carry any result fields (a decision
  that "already has results" is invalid by construction).
- ``outcome``: written after the task finishes. ``observed`` records must
  carry an observation time, an evidence source, and the *actual*
  provider/model/effort that ran (not just the recommendation).

Vocabulary (provider / model / native effort) is validated against a frozen,
versioned model catalog (see ``fixtures/outcome/model-catalog.v1.json``), not
against ``read_agent_quota.model_for()`` which evolves with routing policy.

Runtime-neutral by design: plain ``python`` from the repo root works for both
Claude Code and Codex. Stdlib only. Never reads credential files — the only
inputs are this repo's fixtures and the local gitignored ledger directory.

Usage:
  python .claude/skills/coding-agent-quota/scripts/outcome_ledger.py record-decision \
      --role impl --routing-tier 2 --provider codex --model gpt-5.6-terra \
      --effort medium --launch-surface codex_exec --task-class bounded-implementation \
      --quota-generated-at 2026-07-12T08:00:00Z --quota-source usage.db
  python .../outcome_ledger.py record-outcome --decision-id d-xxxx --status observed \
      --quality pass --evidence-source "pytest exit 0" --rework 0 \
      --actual-provider codex --actual-model gpt-5.6-terra --actual-effort medium
  python .../outcome_ledger.py show --decision-id d-xxxx
  python .../outcome_ledger.py summary
  python .../outcome_ledger.py validate --ledger <file.jsonl> [--catalog <file>]
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

SKILL_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = SKILL_DIR.parents[2]
DEFAULT_LEDGER_FILE = SKILL_DIR / ".outcome-ledger" / "ledger.jsonl"
DEFAULT_CATALOG = SKILL_DIR / "fixtures" / "outcome" / "model-catalog.v1.json"

# Write boundary (BLOCKER fix): ledger writes are only allowed inside the
# default gitignored ledger directory or the system temp dir (tests). Protected
# paths (aligned with .claude/hooks/pre_tool_guard.py) and any other location
# are rejected — `--ledger`/`--record-ledger` must not become an arbitrary
# file-write primitive that bypasses the protected-path floor.
PROTECTED_REPO_PREFIXES = (
    "lab/data/", "lab/runs/", "lab/models/", "lab/infra/private/",
)
PROTECTED_REPO_FILES = (".env",)

SCHEMA_VERSION = 1
RECORD_TYPES = ("decision", "outcome")
DECISION_ID_RE = re.compile(r"^d-[A-Za-z0-9][A-Za-z0-9_-]*$")
# Required-key floors: every key must be PRESENT (some values may be null).
# Deleting any of these from a record must be rejected by the validator.
DECISION_REQUIRED_KEYS = (
    "record_type", "schema_version", "decision_id", "decided_at", "task_class",
    "role", "routing_tier", "provider", "model", "effort", "policy_version",
    "launch_surface", "quota_snapshot_ref", "paseo_preference", "degraded",
    "degraded_reason", "baseline_provider", "signals", "outcome_status",
)
OUTCOME_REQUIRED_KEYS = (
    "record_type", "schema_version", "decision_id", "outcome_observed_at",
    "outcome_status", "evidence_source", "outcome_quality", "rework_count",
    "failure_reason", "tokens_in", "tokens_out", "latency_wall_clock_s",
    "actual_provider", "actual_model", "actual_effort", "policy_version",
)
# quota_cost is optional on an outcome, but when present it must be complete.
QUOTA_COST_REQUIRED_KEYS = (
    "window", "before_used_percent", "after_used_percent", "delta_percent",
    "sampled_before_at", "sampled_after_at", "attribution_confidence", "is_estimate",
)
ROLES = ("impl", "ui", "research", "planning", "audit")
OUTCOME_STATUSES = ("pending", "observed", "unavailable")
QUALITIES = ("pass", "partial", "fail")
FAILURE_REASONS = (
    "test_failure", "tooling_error", "scope_misread", "quota_exhausted",
    "timeout", "escalated", "rework_abandoned", "other",
)
ATTRIBUTION_CONFIDENCE = ("isolated", "shared_window", "unknown")
PASEO_STATUSES = ("ok", "missing", "unreadable")
# Fields that describe results; forbidden on decision records (lifecycle rule).
RESULT_FIELDS = (
    "outcome_quality", "rework_count", "failure_reason", "outcome_observed_at",
    "tokens_in", "tokens_out", "latency_wall_clock_s", "quota_cost",
    "actual_provider", "actual_model", "actual_effort", "evidence_source",
)


def parse_iso(value: Any) -> dt.datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = dt.datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def iso_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def make_decision_id(payload: dict[str, Any]) -> str:
    return "d-" + hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()[:12]


def load_catalog(path: Path = DEFAULT_CATALOG) -> dict[str, Any]:
    catalog = json.loads(Path(path).read_text(encoding="utf-8"))
    for key in ("policy_version", "providers", "launch_surfaces"):
        if key not in catalog:
            raise ValueError(f"model catalog missing key: {key} ({path})")
    return catalog


def read_ledger(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    """Parse a JSONL ledger. Returns (records, parse_errors). Missing file -> empty."""
    path = Path(path)
    if not path.exists():
        return [], []
    records: list[dict[str, Any]] = []
    errors: list[str] = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"{path.name}:{lineno}: invalid JSON ({exc})")
            continue
        if not isinstance(record, dict):
            errors.append(f"{path.name}:{lineno}: record is not an object")
            continue
        records.append(record)
    return records, errors


def _check_vocab(rec: dict, catalog: dict, prov_key: str, model_key: str,
                 effort_key: str, errs: list[str], prefix: str) -> None:
    providers = catalog.get("providers", {})
    prov = rec.get(prov_key)
    if prov not in providers:
        errs.append(f"{prefix}: {prov_key} not in catalog providers: {prov!r}")
        return
    entry = providers[prov]
    if rec.get(model_key) not in entry.get("models", []):
        errs.append(
            f"{prefix}: {model_key} {rec.get(model_key)!r} not in catalog models for {prov}"
        )
    if rec.get(effort_key) not in entry.get("effort_vocab", []):
        errs.append(
            f"{prefix}: {effort_key} {rec.get(effort_key)!r} not in native effort vocab "
            f"for {prov} ({entry.get('effort_vocab')})"
        )


def validate_decision(rec: dict[str, Any], catalog: dict[str, Any]) -> list[str]:
    errs: list[str] = []
    did = rec.get("decision_id")
    prefix = f"decision {did or '<no id>'}"
    missing = [k for k in DECISION_REQUIRED_KEYS if k not in rec]
    if missing:
        errs.append(f"{prefix}: missing required key(s): {missing}")
    if rec.get("schema_version") != SCHEMA_VERSION:
        errs.append(
            f"{prefix}: schema_version must be {SCHEMA_VERSION}: {rec.get('schema_version')!r}"
        )
    if not isinstance(did, str) or not did:
        errs.append(f"{prefix}: missing/empty decision_id")
    elif not DECISION_ID_RE.match(did):
        errs.append(f"{prefix}: decision_id does not match 'd-<id>' format: {did!r}")
    baseline = rec.get("baseline_provider")
    if not isinstance(baseline, str) or baseline not in catalog.get("providers", {}):
        errs.append(f"{prefix}: baseline_provider not in catalog providers: {baseline!r}")
    signals = rec.get("signals")
    if not isinstance(signals, list) or not all(isinstance(s, str) for s in signals):
        errs.append(f"{prefix}: signals must be a list of strings")
    if parse_iso(rec.get("decided_at")) is None:
        errs.append(f"{prefix}: decided_at is not a valid ISO-8601 time")
    if not isinstance(rec.get("task_class"), str) or not rec.get("task_class"):
        errs.append(f"{prefix}: missing/empty task_class")
    if rec.get("role") not in ROLES:
        errs.append(f"{prefix}: role not in {ROLES}: {rec.get('role')!r}")
    tier = rec.get("routing_tier")
    if not isinstance(tier, int) or isinstance(tier, bool) or not 0 <= tier <= 4:
        errs.append(f"{prefix}: routing_tier must be int 0-4: {tier!r}")
    if rec.get("policy_version") != catalog.get("policy_version"):
        errs.append(
            f"{prefix}: policy_version {rec.get('policy_version')!r} != catalog "
            f"{catalog.get('policy_version')!r}"
        )
    _check_vocab(rec, catalog, "provider", "model", "effort", errs, prefix)
    surface = rec.get("launch_surface")
    provider_entry = catalog.get("providers", {}).get(rec.get("provider"), {})
    allowed_surfaces = provider_entry.get("launch_surfaces") or catalog.get("launch_surfaces", [])
    if surface not in allowed_surfaces:
        errs.append(f"{prefix}: launch_surface {surface!r} not in {allowed_surfaces}")
    ref = rec.get("quota_snapshot_ref")
    if not isinstance(ref, dict) or parse_iso(ref.get("generated_at")) is None or not ref.get("source"):
        errs.append(f"{prefix}: quota_snapshot_ref needs generated_at (ISO) and source")
    paseo = rec.get("paseo_preference")
    if paseo is not None:
        if not isinstance(paseo, dict) or paseo.get("status") not in PASEO_STATUSES:
            errs.append(f"{prefix}: paseo_preference.status must be one of {PASEO_STATUSES}")
    if not isinstance(rec.get("degraded"), bool):
        errs.append(f"{prefix}: degraded must be a bool")
    elif rec["degraded"] and not rec.get("degraded_reason"):
        errs.append(f"{prefix}: degraded=true requires degraded_reason")
    if rec.get("outcome_status") != "pending":
        errs.append(
            f"{prefix}: decision outcome_status must be 'pending' "
            f"(got {rec.get('outcome_status')!r}); outcomes live in outcome records"
        )
    present_results = [f for f in RESULT_FIELDS if rec.get(f) not in (None, [], {})]
    if present_results:
        errs.append(
            f"{prefix}: decision record must not carry result fields "
            f"(a decision cannot 'already have results'): {present_results}"
        )
    return errs


def validate_outcome(
    rec: dict[str, Any], catalog: dict[str, Any], decision_ids: set[str] | None = None
) -> list[str]:
    errs: list[str] = []
    did = rec.get("decision_id")
    prefix = f"outcome for {did or '<no id>'}"
    missing = [k for k in OUTCOME_REQUIRED_KEYS if k not in rec]
    if missing:
        errs.append(f"{prefix}: missing required key(s): {missing}")
    if rec.get("schema_version") != SCHEMA_VERSION:
        errs.append(
            f"{prefix}: schema_version must be {SCHEMA_VERSION}: {rec.get('schema_version')!r}"
        )
    if not isinstance(did, str) or not did:
        errs.append(f"{prefix}: missing/empty decision_id")
    elif not DECISION_ID_RE.match(did):
        errs.append(f"{prefix}: decision_id does not match 'd-<id>' format: {did!r}")
    elif decision_ids is not None and did not in decision_ids:
        errs.append(f"{prefix}: references unknown decision_id {did!r}")
    status = rec.get("outcome_status")
    if status not in ("observed", "unavailable"):
        errs.append(
            f"{prefix}: outcome_status must be observed|unavailable (got {status!r}); "
            "'pending' is expressed by the absence of an outcome record"
        )
        return errs
    if parse_iso(rec.get("outcome_observed_at")) is None:
        errs.append(f"{prefix}: outcome_observed_at is required and must be ISO-8601")
    if status == "observed":
        if not isinstance(rec.get("evidence_source"), str) or not rec.get("evidence_source"):
            errs.append(f"{prefix}: observed outcome requires a non-empty evidence_source")
        if rec.get("outcome_quality") not in QUALITIES:
            errs.append(f"{prefix}: outcome_quality must be one of {QUALITIES}")
        rework = rec.get("rework_count")
        if not isinstance(rework, int) or isinstance(rework, bool) or rework < 0:
            errs.append(f"{prefix}: rework_count must be int >= 0")
        if rec.get("outcome_quality") == "fail" and rec.get("failure_reason") not in FAILURE_REASONS:
            errs.append(f"{prefix}: failed outcome requires failure_reason in {FAILURE_REASONS}")
        if rec.get("policy_version") != catalog.get("policy_version"):
            errs.append(
                f"{prefix}: policy_version {rec.get('policy_version')!r} != catalog "
                f"{catalog.get('policy_version')!r}"
            )
        _check_vocab(rec, catalog, "actual_provider", "actual_model", "actual_effort",
                     errs, prefix)
    else:  # unavailable
        if rec.get("outcome_quality") is not None:
            errs.append(f"{prefix}: unavailable outcome must not claim an outcome_quality")
    if rec.get("failure_reason") is not None and rec.get("failure_reason") not in FAILURE_REASONS:
        errs.append(f"{prefix}: failure_reason not in {FAILURE_REASONS}: {rec.get('failure_reason')!r}")
    for key in ("tokens_in", "tokens_out", "latency_wall_clock_s"):
        value = rec.get(key)
        if value is not None and (not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0):
            errs.append(f"{prefix}: {key} must be a number >= 0")
    cost = rec.get("quota_cost")
    if cost is not None:
        if not isinstance(cost, dict):
            errs.append(f"{prefix}: quota_cost must be an object")
        else:
            missing_cost = [k for k in QUOTA_COST_REQUIRED_KEYS if k not in cost]
            if missing_cost:
                errs.append(f"{prefix}: quota_cost missing required key(s): {missing_cost}")
            if not isinstance(cost.get("window"), str) or not cost.get("window"):
                errs.append(f"{prefix}: quota_cost.window must be a non-empty string")
            for key in ("before_used_percent", "after_used_percent"):
                value = cost.get(key)
                if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
                    errs.append(f"{prefix}: quota_cost.{key} must be a number >= 0")
            if cost.get("attribution_confidence") not in ATTRIBUTION_CONFIDENCE:
                errs.append(
                    f"{prefix}: quota_cost.attribution_confidence must be one of "
                    f"{ATTRIBUTION_CONFIDENCE}"
                )
            if not isinstance(cost.get("is_estimate"), bool):
                errs.append(f"{prefix}: quota_cost.is_estimate must be a bool")
            if not isinstance(cost.get("delta_percent"), (int, float)) or isinstance(
                cost.get("delta_percent"), bool
            ):
                errs.append(f"{prefix}: quota_cost.delta_percent must be a number")
            if parse_iso(cost.get("sampled_after_at")) is None:
                errs.append(f"{prefix}: quota_cost.sampled_after_at must be ISO-8601")
            before = cost.get("sampled_before_at")
            if before is not None and parse_iso(before) is None:
                errs.append(f"{prefix}: quota_cost.sampled_before_at must be null or ISO-8601")
    if rec.get("metered_price_estimate") is not None:
        errs.append(
            f"{prefix}: metered_price_estimate is reserved and NOT implemented in this "
            "schema version (see plan doc, resolved question 6)"
        )
    return errs


def validate_records(records: list[dict[str, Any]], catalog: dict[str, Any]) -> list[str]:
    errs: list[str] = []
    seen: set[str] = set()
    decision_ids: set[str] = set()
    for rec in records:
        if rec.get("record_type") == "decision":
            did = rec.get("decision_id")
            if isinstance(did, str) and did:
                if did in seen:
                    errs.append(f"duplicate decision_id: {did}")
                seen.add(did)
                decision_ids.add(did)
    for rec in records:
        rtype = rec.get("record_type")
        if rtype == "decision":
            errs.extend(validate_decision(rec, catalog))
        elif rtype == "outcome":
            errs.extend(validate_outcome(rec, catalog, decision_ids))
        else:
            errs.append(f"record_type must be one of {RECORD_TYPES}: {rtype!r}")
    return errs


def latest_outcomes(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """decision_id -> latest outcome record (append-only corrections: latest wins)."""
    latest: dict[str, dict[str, Any]] = {}
    for rec in records:
        if rec.get("record_type") != "outcome":
            continue
        did = rec.get("decision_id")
        if not isinstance(did, str):
            continue
        prev = latest.get(did)
        t_new = parse_iso(rec.get("outcome_observed_at")) or dt.datetime.min.replace(tzinfo=dt.timezone.utc)
        t_old = (
            parse_iso(prev.get("outcome_observed_at")) if prev else None
        ) or dt.datetime.min.replace(tzinfo=dt.timezone.utc)
        if prev is None or t_new >= t_old:
            latest[did] = rec
    return latest


def _avg(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 4) if values else None


def summarize(records: list[dict[str, Any]], catalog: dict[str, Any]) -> dict[str, Any]:
    """Per-route report with dimensions kept separate (no single merged score)."""
    expensive = catalog.get("expensive_routes", {})
    expensive_models = set(expensive.get("models", []))
    min_expensive_tier = expensive.get("min_expensive_tier", 3)
    decisions = {r["decision_id"]: r for r in records
                 if r.get("record_type") == "decision" and isinstance(r.get("decision_id"), str)}
    outcomes = latest_outcomes(records)

    routes: dict[str, dict[str, Any]] = {}
    for did, dec in sorted(decisions.items()):
        provider = dec.get("provider", "unknown")
        model = dec.get("model", "unknown")
        key = f"{provider}/{model}"
        route = routes.setdefault(key, {
            "provider": provider, "model": model,
            "decisions": 0, "pending": 0, "observed": 0, "unavailable": 0,
            "outcomes": {"pass": 0, "partial": 0, "fail": 0},
            "failure_reasons": {},
            "_rework": [], "_tokens_in": [], "_tokens_out": [], "_latency": [], "_quota": [],
            "expensive_route": model in expensive_models
            or (isinstance(dec.get("routing_tier"), int) and dec["routing_tier"] >= min_expensive_tier),
        })
        route["decisions"] += 1
        out = outcomes.get(did)
        if out is None:
            route["pending"] += 1
            continue
        status = out.get("outcome_status")
        if status == "observed":
            route["observed"] += 1
            quality = out.get("outcome_quality")
            if quality in route["outcomes"]:
                route["outcomes"][quality] += 1
            reason = out.get("failure_reason")
            if reason:
                route["failure_reasons"][reason] = route["failure_reasons"].get(reason, 0) + 1
            if isinstance(out.get("rework_count"), int):
                route["_rework"].append(out["rework_count"])
            for src, dst in (("tokens_in", "_tokens_in"), ("tokens_out", "_tokens_out"),
                             ("latency_wall_clock_s", "_latency")):
                if isinstance(out.get(src), (int, float)):
                    route[dst].append(float(out[src]))
            cost = out.get("quota_cost") or {}
            if isinstance(cost.get("delta_percent"), (int, float)):
                route["_quota"].append(float(cost["delta_percent"]))
        else:
            route["unavailable"] += 1

    report: dict[str, Any] = {}
    for key in sorted(routes):
        r = routes[key]
        judged = r["outcomes"]["pass"] + r["outcomes"]["fail"]
        report[key] = {
            "provider": r["provider"],
            "model": r["model"],
            "expensive_route": r["expensive_route"],
            "decisions": r["decisions"],
            "pending": r["pending"],
            "unavailable": r["unavailable"],
            # dimensions reported separately by design (Child G):
            "outcome": {
                "observed": r["observed"],
                "pass": r["outcomes"]["pass"],
                "partial": r["outcomes"]["partial"],
                "fail": r["outcomes"]["fail"],
                "success_rate": round(r["outcomes"]["pass"] / judged, 4) if judged else None,
                "avg_rework": _avg([float(x) for x in r["_rework"]]),
                "failure_reasons": r["failure_reasons"],
            },
            "tokens": {
                "avg_tokens_in": _avg(r["_tokens_in"]),
                "avg_tokens_out": _avg(r["_tokens_out"]),
            },
            "quota_cost": {
                "avg_delta_percent": _avg(r["_quota"]),
                "note": "subscription window burn (estimate; not metered billing, no $ dimension in this version)",
            },
            "wall_clock": {"avg_latency_s": _avg(r["_latency"])},
        }
    return {"policy_version": catalog.get("policy_version"), "routes": report}


def provider_stats(
    records: list[dict[str, Any]],
    role: str | None = None,
    task_class: str | None = None,
    routing_tier: int | None = None,
) -> dict[str, dict[str, Any]]:
    """Per-provider observed-outcome stats, filtered by role/task_class/routing_tier.

    Task-identity isolation: callers routing a specific segment must filter on
    the full ``role + task_class + routing_tier`` combination so that e.g.
    tier-3 samples never pollute a tier-2 routing decision.
    """
    decisions = {r["decision_id"]: r for r in records
                 if r.get("record_type") == "decision" and isinstance(r.get("decision_id"), str)}
    outcomes = latest_outcomes(records)
    stats: dict[str, dict[str, Any]] = {}
    for did, dec in sorted(decisions.items()):
        if role is not None and dec.get("role") != role:
            continue
        if task_class is not None and dec.get("task_class") != task_class:
            continue
        if routing_tier is not None and dec.get("routing_tier") != routing_tier:
            continue
        out = outcomes.get(did)
        if out is None or out.get("outcome_status") != "observed":
            continue
        provider = out.get("actual_provider") or dec.get("provider", "unknown")
        s = stats.setdefault(provider, {"observed": 0, "pass": 0, "fail": 0, "partial": 0,
                                        "_rework": [], "_quota": [], "_latency": [], "_tokens_out": []})
        s["observed"] += 1
        quality = out.get("outcome_quality")
        if quality in ("pass", "fail", "partial"):
            s[quality] += 1
        if isinstance(out.get("rework_count"), int):
            s["_rework"].append(float(out["rework_count"]))
        cost = out.get("quota_cost") or {}
        if isinstance(cost.get("delta_percent"), (int, float)):
            s["_quota"].append(float(cost["delta_percent"]))
        if isinstance(out.get("latency_wall_clock_s"), (int, float)):
            s["_latency"].append(float(out["latency_wall_clock_s"]))
        if isinstance(out.get("tokens_out"), (int, float)):
            s["_tokens_out"].append(float(out["tokens_out"]))
    result: dict[str, dict[str, Any]] = {}
    for provider in sorted(stats):
        s = stats[provider]
        judged = s["pass"] + s["fail"]
        result[provider] = {
            "observed": s["observed"],
            "pass": s["pass"], "fail": s["fail"], "partial": s["partial"],
            "success_rate": round(s["pass"] / judged, 4) if judged else None,
            "avg_rework": _avg(s["_rework"]),
            "expected_quota_cost_percent": _avg(s["_quota"]),
            "avg_latency_s": _avg(s["_latency"]),
            "avg_tokens_out": _avg(s["_tokens_out"]),
        }
    return result


class LedgerWriteError(ValueError):
    """Raised when a ledger write target violates the write boundary."""


def resolve_write_path(path: Path | str) -> Path:
    """Resolve (realpath) a ledger WRITE target and enforce the write boundary.

    Allowed: the default `.outcome-ledger/` directory inside this skill, and
    the system temp dir (`/tmp` / ``tempfile.gettempdir()``, for tests only).
    Rejected with ``LedgerWriteError``: protected repo paths (lab/data|runs|
    models, lab/infra/private, .env — aligned with pre_tool_guard) and any
    other repo or non-temp location. Read paths are NOT restricted.
    """
    resolved = Path(path).expanduser().resolve()
    repo_root = REPO_ROOT.resolve()
    try:
        rel = resolved.relative_to(repo_root).as_posix()
    except ValueError:
        rel = None
    if rel is not None and (
        rel in PROTECTED_REPO_FILES
        or resolved.name in PROTECTED_REPO_FILES
        or any(rel == p.rstrip("/") or rel.startswith(p) for p in PROTECTED_REPO_PREFIXES)
    ):
        raise LedgerWriteError(
            f"refusing to write ledger to protected path: {path} "
            "(protected-path floor, see .agent/action-boundary.md)"
        )
    allowed_dirs = {
        DEFAULT_LEDGER_FILE.parent.resolve(),
        Path("/tmp").resolve(),
        Path(tempfile.gettempdir()).resolve(),
    }
    for root in allowed_dirs:
        if root in resolved.parents:
            return resolved
    raise LedgerWriteError(
        f"refusing to write ledger outside the allowed directories: {path} "
        f"(allowed: {DEFAULT_LEDGER_FILE.parent} or the system temp dir)"
    )


def append_record(record: dict[str, Any], ledger_file: Path) -> None:
    ledger_file = resolve_write_path(ledger_file)
    ledger_file.parent.mkdir(parents=True, exist_ok=True)
    with ledger_file.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def _fail_on_errors(errs: list[str]) -> int:
    for err in errs:
        print(f"ERROR {err}")
    return 1 if errs else 0


def cmd_record_decision(args: argparse.Namespace) -> int:
    try:
        ledger_path = resolve_write_path(args.ledger)
    except LedgerWriteError as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 2
    catalog = load_catalog(Path(args.catalog))
    decided_at = args.decided_at or iso_now()
    record: dict[str, Any] = {
        "record_type": "decision",
        "schema_version": SCHEMA_VERSION,
        "decided_at": decided_at,
        "task_class": args.task_class,
        "role": args.role,
        "routing_tier": args.routing_tier,
        "provider": args.provider,
        "model": args.model,
        "effort": args.effort,
        "policy_version": catalog["policy_version"],
        "launch_surface": args.launch_surface,
        "quota_snapshot_ref": {
            "generated_at": args.quota_generated_at or decided_at,
            "source": args.quota_source,
        },
        "paseo_preference": {"status": args.paseo_status, "role_default": args.paseo_role_default}
        if args.paseo_status else None,
        "degraded": args.degraded,
        "degraded_reason": args.degraded_reason,
        "baseline_provider": args.baseline_provider or args.provider,
        "signals": args.signal or [],
        "outcome_status": "pending",
    }
    record["decision_id"] = args.decision_id or make_decision_id(
        {k: record[k] for k in ("decided_at", "role", "routing_tier", "task_class",
                                "provider", "model", "effort", "policy_version")}
    )
    errs = validate_decision(record, catalog)
    if errs:
        return _fail_on_errors(errs)
    append_record(record, ledger_path)
    print(json.dumps({"decision_id": record["decision_id"], "ledger": str(args.ledger)},
                     ensure_ascii=False))
    return 0


def cmd_record_outcome(args: argparse.Namespace) -> int:
    try:
        ledger_path = resolve_write_path(args.ledger)
    except LedgerWriteError as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 2
    catalog = load_catalog(Path(args.catalog))
    record: dict[str, Any] = {
        "record_type": "outcome",
        "schema_version": SCHEMA_VERSION,
        "decision_id": args.decision_id,
        "outcome_observed_at": args.observed_at or iso_now(),
        "outcome_status": args.status,
        "evidence_source": args.evidence_source,
        "outcome_quality": args.quality,
        "rework_count": args.rework,
        "failure_reason": args.failure_reason,
        "tokens_in": args.tokens_in,
        "tokens_out": args.tokens_out,
        "latency_wall_clock_s": args.latency_s,
        "actual_provider": args.actual_provider,
        "actual_model": args.actual_model,
        "actual_effort": args.actual_effort,
        "policy_version": catalog["policy_version"] if args.status == "observed" else None,
    }
    if args.quota_before is not None and args.quota_after is not None:
        record["quota_cost"] = {
            "window": "current",
            "before_used_percent": args.quota_before,
            "after_used_percent": args.quota_after,
            "delta_percent": round(args.quota_after - args.quota_before, 2),
            "sampled_before_at": None,
            "sampled_after_at": record["outcome_observed_at"],
            "attribution_confidence": args.attribution,
            "is_estimate": True,
        }
    records, parse_errs = read_ledger(Path(args.ledger))
    decision_ids = {r.get("decision_id") for r in records if r.get("record_type") == "decision"}
    errs = parse_errs + validate_outcome(record, catalog, decision_ids)
    if errs:
        return _fail_on_errors(errs)
    append_record(record, ledger_path)
    print(json.dumps({"decision_id": record["decision_id"], "status": record["outcome_status"]},
                     ensure_ascii=False))
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    records, parse_errs = read_ledger(Path(args.ledger))
    hits = [r for r in records if r.get("decision_id") == args.decision_id]
    for err in parse_errs:
        print(f"WARN {err}", file=sys.stderr)
    if not hits:
        print(f"ERROR decision_id not found in {args.ledger}: {args.decision_id}")
        return 1
    print(json.dumps(hits, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def cmd_summary(args: argparse.Namespace) -> int:
    catalog = load_catalog(Path(args.catalog))
    records, parse_errs = read_ledger(Path(args.ledger))
    for err in parse_errs:
        print(f"WARN {err}", file=sys.stderr)
    print(json.dumps(summarize(records, catalog), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    catalog = load_catalog(Path(args.catalog))
    records, parse_errs = read_ledger(Path(args.ledger))
    errs = parse_errs + validate_records(records, catalog)
    status = "FAIL" if errs else "OK"
    rc = _fail_on_errors(errs)
    print(f"[outcome-ledger validate] {status} — {len(records)} record(s), {len(errs)} error(s)")
    return rc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ledger", default=str(DEFAULT_LEDGER_FILE),
                        help="JSONL ledger file (default: repo-local gitignored ledger)")
    parser.add_argument("--catalog", default=str(DEFAULT_CATALOG),
                        help="frozen model catalog JSON")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("record-decision", help="append a route decision (outcome pending)")
    p.add_argument("--decision-id", help="explicit id; default: deterministic hash")
    p.add_argument("--decided-at", help="ISO time; default now (UTC)")
    p.add_argument("--task-class", required=True)
    p.add_argument("--role", required=True, choices=ROLES)
    p.add_argument("--routing-tier", required=True, type=int, choices=range(0, 5))
    p.add_argument("--provider", required=True)
    p.add_argument("--model", required=True)
    p.add_argument("--effort", required=True, help="provider-native effort value")
    p.add_argument("--launch-surface", required=True)
    p.add_argument("--quota-generated-at", help="generated_at of the quota snapshot used")
    p.add_argument("--quota-source", default="unspecified")
    p.add_argument("--paseo-status", choices=PASEO_STATUSES)
    p.add_argument("--paseo-role-default")
    p.add_argument("--degraded", action="store_true")
    p.add_argument("--degraded-reason")
    p.add_argument("--baseline-provider", help="quota-only baseline provider")
    p.add_argument("--signal", action="append", help="repeatable explanation note")
    p.set_defaults(func=cmd_record_decision)

    p = sub.add_parser("record-outcome", help="append an observed/unavailable outcome")
    p.add_argument("--decision-id", required=True)
    p.add_argument("--observed-at", help="ISO time; default now (UTC)")
    p.add_argument("--status", required=True, choices=("observed", "unavailable"))
    p.add_argument("--quality", choices=QUALITIES)
    p.add_argument("--evidence-source")
    p.add_argument("--rework", type=int, default=0)
    p.add_argument("--failure-reason", choices=FAILURE_REASONS)
    p.add_argument("--tokens-in", type=float)
    p.add_argument("--tokens-out", type=float)
    p.add_argument("--latency-s", type=float)
    p.add_argument("--actual-provider")
    p.add_argument("--actual-model")
    p.add_argument("--actual-effort")
    p.add_argument("--quota-before", type=float, help="window used%% before the task")
    p.add_argument("--quota-after", type=float, help="window used%% after the task")
    p.add_argument("--attribution", default="shared_window", choices=ATTRIBUTION_CONFIDENCE)
    p.set_defaults(func=cmd_record_outcome)

    p = sub.add_parser("show", help="print all records for one decision_id")
    p.add_argument("--decision-id", required=True)
    p.set_defaults(func=cmd_show)

    p = sub.add_parser("summary", help="per-route report; dimensions kept separate")
    p.set_defaults(func=cmd_summary)

    p = sub.add_parser("validate", help="validate a ledger file against the catalog")
    p.set_defaults(func=cmd_validate)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
