#!/usr/bin/env python3
"""Outcome-aware route recommendation / deterministic replay (quota + outcome, no $).

Layers historical task outcomes from the outcome ledger on top of the existing
quota-only ``route_recommendation`` from ``read_agent_quota.py``. The quota-only
baseline logic is imported and reused unchanged (backward compatible); this
script only ADDS an ``outcome_route_recommendation`` next to it.

Conservative fallback: when quota data is stale or outcome evidence is missing
or insufficient, the outcome layer marks ``degraded: true`` with a reason and
falls back to the quota-only recommendation instead of faking precision.

Deterministic replay: with ``--quota-fixture``, ``--ledger``, ``--catalog`` and
``--now`` fixed, two runs produce byte-identical output (sorted keys, fixed
tie-breaks, rounded floats). This is what the benchmark freeze and the
validator rely on.

Runtime-neutral: plain ``python`` from the repo root works for both Claude Code
and Codex (``codex exec`` included). Stdlib only; never reads credentials.

Usage (offline replay on frozen fixtures):
  python .claude/skills/coding-agent-quota/scripts/outcome_route.py \
      --quota-fixture .claude/skills/coding-agent-quota/fixtures/outcome/quota-snapshot.frozen.json \
      --ledger .claude/skills/coding-agent-quota/fixtures/outcome/outcome-ledger.sample.jsonl \
      --role impl --tier 2 --now 2026-07-12T10:00:00Z

Usage (live snapshot + real ledger, record the decision):
  python .../outcome_route.py --live --role impl --tier 2 \
      --task-class bounded-implementation --record
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import outcome_ledger as ol  # noqa: E402
import read_agent_quota as raq  # noqa: E402

SKILL_DIR = Path(__file__).resolve().parent.parent
# Fixed candidate order = deterministic tie-break order.
PROVIDER_ORDER = ("codex", "claude_code")
DEFAULT_SURFACE = {"codex": "codex_exec", "claude_code": "claude_subagent"}
# Outcome layer only overrides the quota-only baseline when the evidence is
# strong: both providers have >= min_samples observed outcomes for this role
# and the alternative's success rate beats the baseline's by at least this gap.
SWITCH_SUCCESS_GAP = 0.25
MIN_ALT_CURRENT_REMAINING = 20.0


def _iso(value: dt.datetime) -> str:
    return value.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def _round(value: Any) -> Any:
    return round(value, 4) if isinstance(value, float) else value


def catalog_route(catalog: dict[str, Any], provider: str, role: str, tier: int) -> dict[str, str]:
    """Model + provider-native effort from the frozen catalog (not model_for())."""
    entry = catalog["providers"][provider]
    tier_key = str(tier)
    model = entry["tier_model"][tier_key]
    override = (entry.get("role_model_overrides") or {}).get(role, {})
    model = override.get(tier_key, model)
    return {"model": model, "effort": entry["tier_effort"][tier_key],
            "effort_knob": entry.get("effort_knob", "effort")}


def staleness(providers: dict[str, Any], now: dt.datetime, max_age_minutes: int) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for name in PROVIDER_ORDER:
        provider = providers.get(name, {})
        captured = raq.parse_time(provider.get("captured_at"))
        if provider.get("status") != "ok" or captured is None:
            result[name] = {"stale": True, "age_minutes": None, "reason": "unavailable"}
            continue
        age = (now - captured).total_seconds() / 60
        result[name] = {"stale": age > max_age_minutes, "age_minutes": round(age, 1),
                        "reason": "stale snapshot" if age > max_age_minutes else None}
    return result


def build_recommendation(
    quota: dict[str, Any],
    records: list[dict[str, Any]],
    catalog: dict[str, Any],
    role: str,
    tier: int,
    task_class: str,
    now: dt.datetime,
    max_age_minutes: int,
    min_samples: int,
    ledger_error: str | None = None,
) -> dict[str, Any]:
    providers = quota.get("providers", {})
    preferences = quota.get("paseo_preferences") or {"status": "missing", "providers": {}}
    baseline = raq.route_recommendation(
        role, tier, providers, preferences, quota.get("usage_velocity", {})
    )
    base_provider = baseline["recommended_provider"]

    signals: list[str] = [f"quota-only baseline recommends {base_provider} "
                          f"(scores: " + ", ".join(
                              f"{p}={baseline['scores'][p]['score']}" for p in PROVIDER_ORDER) + ")"]
    degraded = False
    degraded_reason: str | None = None

    # 0) ledger integrity gate: schema-invalid/corrupt ledgers never feed the
    # stats (caller passes records=[] plus the error summary); conservative
    # fallback to quota-only instead of routing on bad data.
    if ledger_error:
        degraded = True
        degraded_reason = (
            f"outcome ledger failed validation ({ledger_error}); outcome evidence "
            "discarded; falling back to quota-only recommendation"
        )

    # 1) freshness gate (reuses the freshness_warning idea from read_agent_quota).
    stale = staleness(providers, now, max_age_minutes)
    if not degraded and stale.get(base_provider, {}).get("stale"):
        degraded = True
        age = stale[base_provider]["age_minutes"]
        degraded_reason = (
            f"quota snapshot for {base_provider} is stale/unavailable "
            f"(age_minutes={age}, max_age_minutes={max_age_minutes}); "
            "falling back to quota-only recommendation"
        )

    # 2) outcome evidence gate, isolated per task identity: samples are
    # aggregated on the full role + task_class + routing_tier segment, and
    # EVERY candidate needs >= min_samples observed outcomes in that segment
    # (tier-3 or other-task data must not steer a tier-2 decision).
    segment = f"role={role} task_class={task_class} tier={tier}"
    stats = ol.provider_stats(records, role=role, task_class=task_class, routing_tier=tier)
    thin = {name: (stats.get(name) or {}).get("observed", 0) for name in PROVIDER_ORDER
            if (stats.get(name) or {}).get("observed", 0) < min_samples}
    if not degraded and thin:
        degraded = True
        degraded_reason = (
            f"insufficient outcome evidence for segment {segment}: "
            + ", ".join(f"{name} observed={n}" for name, n in sorted(thin.items()))
            + f" < min_samples={min_samples}; falling back to quota-only recommendation"
        )

    chosen = base_provider
    switched = False
    switch_signal: str | None = None
    if not degraded:
        for name in PROVIDER_ORDER:
            s = stats.get(name)
            if s:
                signals.append(
                    f"outcome evidence {segment}: {name} observed={s['observed']} "
                    f"success_rate={s['success_rate']} avg_rework={s['avg_rework']}"
                )
            else:
                signals.append(f"outcome evidence {segment}: {name} has no observed outcomes")
        alt = next(p for p in PROVIDER_ORDER if p != base_provider)
        base_stats, alt_stats = stats.get(base_provider), stats.get(alt)
        if (
            base_stats and alt_stats
            and base_stats["observed"] >= min_samples and alt_stats["observed"] >= min_samples
            and base_stats["success_rate"] is not None and alt_stats["success_rate"] is not None
            and alt_stats["success_rate"] - base_stats["success_rate"] >= SWITCH_SUCCESS_GAP
            and providers.get(alt, {}).get("status") == "ok"
            and not stale.get(alt, {}).get("stale")
            and (raq.cap_remaining(providers.get(alt, {}), "current") or 0.0) >= MIN_ALT_CURRENT_REMAINING
        ):
            chosen = alt
            switched = True
            switch_signal = "outcome_success_rate"
            signals.append(
                f"switch signal=outcome_success_rate: {alt} success_rate "
                f"{alt_stats['success_rate']} beats {base_provider} "
                f"{base_stats['success_rate']} by >= {SWITCH_SUCCESS_GAP} "
                f"with n>={min_samples} on both sides and healthy {alt} quota"
            )
        else:
            signals.append(
                "no switch: outcome evidence does not clear the "
                f"success-rate gap ({SWITCH_SUCCESS_GAP}) with n>={min_samples} on both sides"
            )
    else:
        signals.append(f"degraded: {degraded_reason}")

    route = catalog_route(catalog, chosen, role, tier)
    decided_at = _iso(now)
    decision_id = ol.make_decision_id({
        "decided_at": decided_at, "role": role, "routing_tier": tier,
        "task_class": task_class, "provider": chosen, "model": route["model"],
        "effort": route["effort"], "policy_version": catalog["policy_version"],
        "quota_generated_at": quota.get("generated_at"),
    })

    # Candidate comparison: the one and only sort key is quota_cost (no $/token
    # pricing in this version); unknown costs sort last, tie-break = fixed order.
    candidates = []
    for index, name in enumerate(PROVIDER_ORDER):
        s = stats.get(name) or {}
        candidates.append({
            "provider": name,
            "current_remaining_percent": raq.cap_remaining(providers.get(name, {}), "current"),
            "weekly_remaining_percent": raq.cap_remaining(providers.get(name, {}), "weekly"),
            "expected_quota_cost_percent": s.get("expected_quota_cost_percent"),
            "observed": s.get("observed", 0),
            "success_rate": s.get("success_rate"),
            "avg_rework": s.get("avg_rework"),
            "avg_latency_s": s.get("avg_latency_s"),
            "avg_tokens_out": s.get("avg_tokens_out"),
            "stale_quota": stale.get(name, {}).get("stale"),
            "_order": index,
        })
    candidates.sort(key=lambda c: (
        c["expected_quota_cost_percent"] is None,
        c["expected_quota_cost_percent"] if c["expected_quota_cost_percent"] is not None else 0.0,
        c["_order"],
    ))
    for candidate in candidates:
        candidate.pop("_order")

    chosen_stats = stats.get(chosen) or {}
    return {
        "decision_id": decision_id,
        "decided_at": decided_at,
        "task_class": task_class,
        "role": role,
        "routing_tier": tier,
        "provider": chosen,
        "model": route["model"],
        "effort": route["effort"],
        "effort_knob": route["effort_knob"],
        "launch_surface_hint": DEFAULT_SURFACE[chosen],
        "policy_version": catalog["policy_version"],
        "degraded": degraded,
        "degraded_reason": degraded_reason,
        "baseline_provider": base_provider,
        "switched_from_baseline": switched,
        "switch_signal": switch_signal,
        "signals": signals,
        "paseo_preference": {
            "status": preferences.get("status"),
            "role_default": (preferences.get("providers") or {}).get(role),
        },
        "quota_snapshot_ref": {
            "generated_at": quota.get("generated_at"),
            "source": quota.get("_source", "live"),
        },
        "candidates_by_quota_cost": candidates,
        "report": {
            "note": "dimensions reported separately by design; no merged single score, no $ dimension",
            "outcome": {
                "observed": chosen_stats.get("observed", 0),
                "success_rate": chosen_stats.get("success_rate"),
                "avg_rework": chosen_stats.get("avg_rework"),
            },
            "quota_cost": {"expected_delta_percent": chosen_stats.get("expected_quota_cost_percent"),
                           "is_estimate": True},
            "tokens": {"avg_tokens_out": chosen_stats.get("avg_tokens_out")},
            "wall_clock": {"avg_latency_s": chosen_stats.get("avg_latency_s")},
            "expensive_route": route["model"] in set(
                (catalog.get("expensive_routes") or {}).get("models", [])
            ) or tier >= (catalog.get("expensive_routes") or {}).get("min_expensive_tier", 3),
        },
        "metered_price_estimate": None,  # reserved; NOT implemented in this version (plan Q6)
    }


def live_quota(args: argparse.Namespace) -> dict[str, Any]:
    ns = argparse.Namespace(
        max_age_minutes=args.max_age_minutes,
        role=None, tier=None,
        paseo_preferences="~/.paseo/orchestration-preferences.json",
        codex_jsonl_files=200,
    )
    return raq.collect(ns)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--quota-fixture", help="frozen read_agent_quota-shaped JSON snapshot")
    source.add_argument("--live", action="store_true", help="collect a live quota snapshot")
    parser.add_argument("--ledger", default=str(ol.DEFAULT_LEDGER_FILE),
                        help="outcome ledger JSONL (fixture or real; missing => degraded)")
    parser.add_argument("--catalog", default=str(ol.DEFAULT_CATALOG))
    parser.add_argument("--role", required=True, choices=ol.ROLES)
    parser.add_argument("--tier", required=True, type=int, choices=range(0, 5))
    parser.add_argument("--task-class", default="unspecified")
    parser.add_argument("--now", help="ISO time for deterministic replay; default wall clock")
    parser.add_argument("--max-age-minutes", type=int, default=120)
    parser.add_argument("--min-samples", type=int, default=3)
    parser.add_argument("--record", action="store_true",
                        help="append the decision to --record-ledger (default real ledger)")
    parser.add_argument("--record-ledger", default=str(ol.DEFAULT_LEDGER_FILE))
    parser.add_argument("--allow-test-dir", default=None,
                        help="TEST-ONLY: extra directory allowed for ledger writes "
                             "(explicit by design — never derived from TMPDIR/env; "
                             "protected paths stay rejected regardless)")
    args = parser.parse_args(argv)

    now = ol.parse_iso(args.now) if args.now else dt.datetime.now(dt.timezone.utc)
    if now is None:
        print(f"ERROR --now is not valid ISO-8601: {args.now}", file=sys.stderr)
        return 2

    if args.quota_fixture:
        quota = json.loads(Path(args.quota_fixture).read_text(encoding="utf-8"))
        quota["_source"] = args.quota_fixture
    else:
        quota = live_quota(args)
        quota["_source"] = "live"

    catalog = ol.load_catalog(Path(args.catalog))
    records, parse_errs = ol.read_ledger(Path(args.ledger))
    ledger_errs = parse_errs + (ol.validate_records(records, catalog) if records else [])
    ledger_error: str | None = None
    if ledger_errs:
        for err in ledger_errs:
            print(f"WARN ledger: {err}", file=sys.stderr)
        # Invalid records never feed routing stats: drop ALL ledger evidence
        # and force the degraded quota-only fallback (conservative by design).
        ledger_error = f"{len(ledger_errs)} parse/schema error(s) in {args.ledger}"
        records = []

    recommendation = build_recommendation(
        quota, records, catalog, args.role, args.tier, args.task_class,
        now, args.max_age_minutes, args.min_samples, ledger_error=ledger_error,
    )

    if args.record:
        try:
            record_ledger = ol.resolve_write_path(
                args.record_ledger, allow_test_dir=args.allow_test_dir
            )
        except ol.LedgerWriteError as exc:
            print(f"ERROR record: {exc}", file=sys.stderr)
            return 2
        decision = {
            "record_type": "decision",
            "schema_version": ol.SCHEMA_VERSION,
            "decision_id": recommendation["decision_id"],
            "decided_at": recommendation["decided_at"],
            "task_class": args.task_class,
            "role": args.role,
            "routing_tier": args.tier,
            "provider": recommendation["provider"],
            "model": recommendation["model"],
            "effort": recommendation["effort"],
            "policy_version": recommendation["policy_version"],
            "launch_surface": recommendation["launch_surface_hint"],
            "quota_snapshot_ref": recommendation["quota_snapshot_ref"],
            "paseo_preference": {
                "status": recommendation["paseo_preference"]["status"],
                "role_default": recommendation["paseo_preference"]["role_default"],
            } if recommendation["paseo_preference"]["status"] in ol.PASEO_STATUSES else None,
            "degraded": recommendation["degraded"],
            "degraded_reason": recommendation["degraded_reason"],
            "baseline_provider": recommendation["baseline_provider"],
            "signals": recommendation["signals"],
            "outcome_status": "pending",
        }
        errs = ol.validate_decision(decision, catalog)
        if errs:
            for err in errs:
                print(f"ERROR record: {err}", file=sys.stderr)
            return 1
        ol.append_record(decision, record_ledger, allow_test_dir=args.allow_test_dir)

    output = {
        "generated_at": _iso(now),
        "inputs": {
            "quota_source": quota["_source"],
            "ledger": args.ledger,
            "catalog": args.catalog,
            "role": args.role,
            "tier": args.tier,
            "task_class": args.task_class,
            "max_age_minutes": args.max_age_minutes,
            "min_samples": args.min_samples,
        },
        # Exact key preserved for backward compatibility (plan + SKILL.md):
        # the quota-only baseline stays under `route_recommendation`, the
        # outcome layer is ADDED next to it, never renaming the legacy key.
        "route_recommendation": raq.route_recommendation(
            args.role, args.tier, quota.get("providers", {}),
            quota.get("paseo_preferences") or {"status": "missing", "providers": {}},
            quota.get("usage_velocity", {}),
        ),
        "outcome_route_recommendation": recommendation,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
