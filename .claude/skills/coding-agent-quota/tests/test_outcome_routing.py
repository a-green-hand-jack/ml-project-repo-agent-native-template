#!/usr/bin/env python3
"""Targeted tests for outcome-aware routing (coding-agent-quota skill).

Stdlib only (unittest). Run from repo root:
  python .claude/skills/coding-agent-quota/tests/test_outcome_routing.py
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
REPO = SKILL.parent.parent.parent
SCRIPTS = SKILL / "scripts"
FIXTURES = SKILL / "fixtures" / "outcome"
NOW = "2026-07-12T08:30:00Z"

sys.path.insert(0, str(SCRIPTS))
import outcome_ledger as ol  # noqa: E402


def run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, *args], capture_output=True, text=True, cwd=REPO)


def replay(quota: str, ledger: str, extra: list[str] | None = None) -> subprocess.CompletedProcess:
    return run([
        str(SCRIPTS / "outcome_route.py"),
        "--quota-fixture", str(FIXTURES / quota),
        "--ledger", str(FIXTURES / ledger),
        "--role", "impl", "--tier", "2",
        "--task-class", "bounded-implementation", "--now", NOW,
        *(extra or []),
    ])


class BackwardCompat(unittest.TestCase):
    def test_read_agent_quota_unchanged(self):
        """Existing quota-only CLI keeps working with identical output surface."""
        result = run([str(SCRIPTS / "read_agent_quota.py"),
                      "--role", "impl", "--tier", "2", "--format", "json"])
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        for key in ("generated_at", "providers", "routing_hint", "paseo_preferences"):
            self.assertIn(key, data)
        rec = data.get("route_recommendation")
        self.assertIsNotNone(rec)
        for key in ("recommended_provider", "recommended_model", "recommended_effort", "scores"):
            self.assertIn(key, rec)
        # The outcome layer must never leak into the legacy output.
        self.assertNotIn("outcome_route_recommendation", data)


class Replay(unittest.TestCase):
    def test_deterministic(self):
        first, second = replay("quota-snapshot.frozen.json", "outcome-ledger.sample.jsonl"), \
            replay("quota-snapshot.frozen.json", "outcome-ledger.sample.jsonl")
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(first.stdout, second.stdout)
        rec = json.loads(first.stdout)["outcome_route_recommendation"]
        self.assertFalse(rec["degraded"])
        self.assertTrue(rec["decision_id"].startswith("d-"))
        self.assertEqual(rec["provider"], "codex")
        self.assertIsNone(rec["metered_price_estimate"])  # reserved, not implemented

    def test_quota_change_flips_route(self):
        healthy = json.loads(replay("quota-snapshot.frozen.json",
                                    "outcome-ledger.sample.jsonl").stdout)
        low = json.loads(replay("quota-snapshot.codex-low.json",
                                "outcome-ledger.sample.jsonl").stdout)
        h, l = healthy["outcome_route_recommendation"], low["outcome_route_recommendation"]
        self.assertEqual(h["provider"], "codex")
        self.assertEqual(l["provider"], "claude_code")
        # the changed signal is quota-driven: baseline itself flipped, no outcome switch
        self.assertNotEqual(h["baseline_provider"], l["baseline_provider"])
        self.assertIsNone(l["switch_signal"])

    def test_outcome_change_flips_route(self):
        degraded_codex = json.loads(replay("quota-snapshot.frozen.json",
                                           "outcome-ledger.codex-degraded.jsonl").stdout)
        rec = degraded_codex["outcome_route_recommendation"]
        self.assertEqual(rec["baseline_provider"], "codex")
        self.assertEqual(rec["provider"], "claude_code")
        self.assertTrue(rec["switched_from_baseline"])
        self.assertEqual(rec["switch_signal"], "outcome_success_rate")

    def test_stale_quota_degrades_to_baseline(self):
        stale = json.loads(replay("quota-snapshot.stale.json",
                                  "outcome-ledger.sample.jsonl").stdout)
        rec = stale["outcome_route_recommendation"]
        self.assertTrue(rec["degraded"])
        self.assertIn("stale", rec["degraded_reason"])
        self.assertEqual(rec["provider"], rec["baseline_provider"])

    def test_missing_ledger_degrades(self):
        result = run([
            str(SCRIPTS / "outcome_route.py"),
            "--quota-fixture", str(FIXTURES / "quota-snapshot.frozen.json"),
            "--ledger", str(FIXTURES / "does-not-exist.jsonl"),
            "--role", "impl", "--tier", "2", "--now", NOW,
        ])
        self.assertEqual(result.returncode, 0, result.stderr)
        rec = json.loads(result.stdout)["outcome_route_recommendation"]
        self.assertTrue(rec["degraded"])
        self.assertIn("insufficient outcome evidence", rec["degraded_reason"])

    def test_candidates_sorted_by_quota_cost(self):
        data = json.loads(replay("quota-snapshot.frozen.json",
                                 "outcome-ledger.sample.jsonl").stdout)
        candidates = data["outcome_route_recommendation"]["candidates_by_quota_cost"]
        costs = [c["expected_quota_cost_percent"] for c in candidates if
                 c["expected_quota_cost_percent"] is not None]
        self.assertEqual(costs, sorted(costs))


class LedgerLifecycle(unittest.TestCase):
    def setUp(self):
        self.catalog = ol.load_catalog()

    def test_decision_with_results_rejected(self):
        records, _ = ol.read_ledger(FIXTURES / "outcome-ledger.sample.jsonl")
        decision = dict(next(r for r in records if r["record_type"] == "decision"))
        decision["outcome_quality"] = "pass"
        errs = ol.validate_decision(decision, self.catalog)
        self.assertTrue(any("must not carry result fields" in e for e in errs))

    def test_observed_requires_evidence_and_time(self):
        records, _ = ol.read_ledger(FIXTURES / "outcome-ledger.sample.jsonl")
        outcome = dict(next(r for r in records if r["record_type"] == "outcome"))
        outcome.pop("evidence_source")
        outcome.pop("outcome_observed_at")
        errs = ol.validate_outcome(outcome, self.catalog)
        self.assertTrue(any("evidence_source" in e for e in errs))
        self.assertTrue(any("outcome_observed_at" in e for e in errs))

    def test_outcome_for_unknown_decision_rejected(self):
        records, _ = ol.read_ledger(FIXTURES / "outcome-ledger.sample.jsonl")
        outcome = dict(next(r for r in records if r["record_type"] == "outcome"))
        outcome["decision_id"] = "d-does-not-exist"
        errs = ol.validate_outcome(outcome, self.catalog, decision_ids={"d-fx0001"})
        self.assertTrue(any("unknown decision_id" in e for e in errs))

    def test_xhigh_not_valid_codex_effort(self):
        records, _ = ol.read_ledger(FIXTURES / "outcome-ledger.sample.jsonl")
        decision = dict(next(r for r in records
                             if r["record_type"] == "decision" and r["provider"] == "codex"))
        decision["effort"] = "xhigh"
        errs = ol.validate_decision(decision, self.catalog)
        self.assertTrue(any("native effort vocab" in e for e in errs))

    def test_metered_price_estimate_rejected(self):
        records, _ = ol.read_ledger(FIXTURES / "outcome-ledger.sample.jsonl")
        outcome = dict(next(r for r in records if r["record_type"] == "outcome"))
        outcome["metered_price_estimate"] = {"usd": 1.23}
        errs = ol.validate_outcome(outcome, self.catalog, decision_ids={outcome["decision_id"]})
        self.assertTrue(any("NOT implemented" in e for e in errs))


class LedgerCli(unittest.TestCase):
    def test_record_show_summary_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = str(Path(tmp) / "ledger.jsonl")
            base = [str(SCRIPTS / "outcome_ledger.py"), "--ledger", ledger]
            rec = run([*base, "record-decision", "--role", "impl", "--routing-tier", "2",
                       "--provider", "codex", "--model", "gpt-5.6-terra", "--effort", "medium",
                       "--launch-surface", "codex_exec", "--task-class", "roundtrip-test",
                       "--decided-at", NOW, "--quota-source", "test"])
            self.assertEqual(rec.returncode, 0, rec.stdout + rec.stderr)
            decision_id = json.loads(rec.stdout)["decision_id"]
            out = run([*base, "record-outcome", "--decision-id", decision_id,
                       "--status", "observed", "--quality", "pass",
                       "--evidence-source", "unittest roundtrip", "--rework", "0",
                       "--actual-provider", "codex", "--actual-model", "gpt-5.6-terra",
                       "--actual-effort", "medium", "--observed-at", NOW,
                       "--quota-before", "10", "--quota-after", "12"])
            self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
            show = run([*base, "show", "--decision-id", decision_id])
            self.assertEqual(show.returncode, 0)
            self.assertEqual(len(json.loads(show.stdout)), 2)
            validate = run([*base, "validate"])
            self.assertEqual(validate.returncode, 0, validate.stdout)
            summary = run([*base, "summary"])
            routes = json.loads(summary.stdout)["routes"]
            self.assertEqual(routes["codex/gpt-5.6-terra"]["outcome"]["pass"], 1)

    def test_record_outcome_for_unknown_decision_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = str(Path(tmp) / "ledger.jsonl")
            result = run([str(SCRIPTS / "outcome_ledger.py"), "--ledger", ledger,
                          "record-outcome", "--decision-id", "d-nope",
                          "--status", "observed", "--quality", "pass",
                          "--evidence-source", "x",
                          "--actual-provider", "codex", "--actual-model", "gpt-5.6-terra",
                          "--actual-effort", "medium"])
            self.assertEqual(result.returncode, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
