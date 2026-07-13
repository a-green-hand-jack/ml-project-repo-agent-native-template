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


def _tmp_writable() -> bool:
    """True when a writable temp dir exists (read-only sandboxes lack one)."""
    try:
        with tempfile.NamedTemporaryFile():
            return True
    except OSError:
        return False


TMP_WRITABLE = _tmp_writable()
NEEDS_TMP = unittest.skipUnless(
    TMP_WRITABLE,
    "no writable temp dir in this environment (read-only sandbox); "
    "skipping tests that must create files under tempfile.gettempdir()",
)


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

    def test_route_recommendation_key_preserved_in_outcome_output(self):
        """outcome_route output keeps the exact legacy key `route_recommendation`
        (quota-only baseline) NEXT TO `outcome_route_recommendation` — never a
        renamed `quota_route_recommendation`."""
        result = replay("quota-snapshot.frozen.json", "outcome-ledger.sample.jsonl")
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertIn("route_recommendation", data)
        self.assertIn("outcome_route_recommendation", data)
        self.assertNotIn("quota_route_recommendation", data)
        for key in ("recommended_provider", "recommended_model", "recommended_effort", "scores"):
            self.assertIn(key, data["route_recommendation"])


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


class TaskIdentityIsolation(unittest.TestCase):
    """Outcome samples are isolated per role + task_class + routing_tier segment."""

    def test_task_classes_get_isolated_results(self):
        """Same ledger, different task_class: bounded-implementation has enough
        samples (not degraded); deep-debug at tier 2 has none (degraded)."""
        seen = json.loads(replay("quota-snapshot.frozen.json",
                                 "outcome-ledger.sample.jsonl").stdout)
        other = json.loads(replay("quota-snapshot.frozen.json", "outcome-ledger.sample.jsonl",
                                  extra=["--task-class", "deep-debug"]).stdout)
        self.assertFalse(seen["outcome_route_recommendation"]["degraded"])
        rec = other["outcome_route_recommendation"]
        self.assertTrue(rec["degraded"])
        self.assertIn("insufficient outcome evidence", rec["degraded_reason"])
        self.assertIn("task_class=deep-debug", rec["degraded_reason"])
        self.assertEqual(rec["provider"], rec["baseline_provider"])

    def test_never_seen_task_class_degrades(self):
        result = replay("quota-snapshot.frozen.json", "outcome-ledger.sample.jsonl",
                        extra=["--task-class", "never-seen-task-class"])
        self.assertEqual(result.returncode, 0, result.stderr)
        rec = json.loads(result.stdout)["outcome_route_recommendation"]
        self.assertTrue(rec["degraded"])
        self.assertIn("insufficient outcome evidence", rec["degraded_reason"])
        self.assertEqual(rec["provider"], rec["baseline_provider"])
        self.assertFalse(rec["switched_from_baseline"])

    def test_tier_samples_do_not_leak_across_tiers(self):
        """Tier-2 bounded-implementation evidence must not steer a tier-3 replay."""
        result = replay("quota-snapshot.frozen.json", "outcome-ledger.sample.jsonl",
                        extra=["--tier", "3"])
        self.assertEqual(result.returncode, 0, result.stderr)
        rec = json.loads(result.stdout)["outcome_route_recommendation"]
        self.assertTrue(rec["degraded"])
        self.assertIn("tier=3", rec["degraded_reason"])
        self.assertEqual(rec["provider"], rec["baseline_provider"])

    def test_provider_stats_filters_on_tier(self):
        records, _ = ol.read_ledger(FIXTURES / "outcome-ledger.sample.jsonl")
        tier2 = ol.provider_stats(records, role="impl",
                                  task_class="bounded-implementation", routing_tier=2)
        tier3 = ol.provider_stats(records, role="impl",
                                  task_class="bounded-implementation", routing_tier=3)
        self.assertGreaterEqual(tier2.get("codex", {}).get("observed", 0), 3)
        self.assertEqual(tier3, {})


@NEEDS_TMP
class InvalidLedgerFallback(unittest.TestCase):
    """Schema-invalid/corrupt ledgers never feed routing: degraded quota-only."""

    def _replay_with_ledger(self, ledger_path: str) -> subprocess.CompletedProcess:
        return run([
            str(SCRIPTS / "outcome_route.py"),
            "--quota-fixture", str(FIXTURES / "quota-snapshot.frozen.json"),
            "--ledger", ledger_path,
            "--role", "impl", "--tier", "2",
            "--task-class", "bounded-implementation", "--now", NOW,
        ])

    def test_catalog_invalid_ledger_degrades_and_never_switches(self):
        text = (FIXTURES / "outcome-ledger.codex-degraded.jsonl").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "ledger.jsonl"
            # Model outside the frozen catalog => schema validation errors.
            bad.write_text(text.replace("gpt-5.6-terra", "gpt-9000-nonexistent"),
                           encoding="utf-8")
            result = self._replay_with_ledger(str(bad))
        self.assertEqual(result.returncode, 0, result.stderr)
        rec = json.loads(result.stdout)["outcome_route_recommendation"]
        self.assertTrue(rec["degraded"])
        self.assertIn("ledger failed validation", rec["degraded_reason"])
        # The codex-degraded ledger would normally force a switch; invalid
        # records must be discarded, so we stay on the quota-only baseline.
        self.assertEqual(rec["provider"], rec["baseline_provider"])
        self.assertFalse(rec["switched_from_baseline"])
        self.assertIn("WARN ledger:", result.stderr)

    def test_json_corrupt_ledger_degrades(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "ledger.jsonl"
            bad.write_text("{this is not json\n", encoding="utf-8")
            result = self._replay_with_ledger(str(bad))
        self.assertEqual(result.returncode, 0, result.stderr)
        rec = json.loads(result.stdout)["outcome_route_recommendation"]
        self.assertTrue(rec["degraded"])
        self.assertIn("ledger failed validation", rec["degraded_reason"])
        self.assertEqual(rec["provider"], rec["baseline_provider"])


class WriteBoundary(unittest.TestCase):
    """--ledger/--record-ledger must not write outside the allowed directories."""

    def _record_decision(self, ledger: str) -> subprocess.CompletedProcess:
        return run([str(SCRIPTS / "outcome_ledger.py"), "--ledger", ledger,
                    "record-decision", "--role", "impl", "--routing-tier", "2",
                    "--provider", "codex", "--model", "gpt-5.6-terra", "--effort", "medium",
                    "--launch-surface", "codex_exec", "--task-class", "boundary-test",
                    "--decided-at", NOW, "--quota-source", "test"])

    def _assert_rejected(self, ledger: str) -> None:
        target = (REPO / ledger) if not Path(ledger).is_absolute() else Path(ledger)
        existed_before = target.exists()
        result = self._record_decision(ledger)
        self.assertNotEqual(result.returncode, 0,
                            f"write to {ledger} must be rejected: {result.stdout}")
        self.assertIn("refusing to write ledger", result.stderr)
        if not existed_before:
            self.assertFalse(target.exists(), f"{ledger} must not be created")

    def test_protected_paths_rejected(self):
        for ledger in ("lab/data/forbidden.jsonl", "lab/runs/forbidden.jsonl",
                       "lab/models/forbidden.jsonl", "lab/infra/private/forbidden.jsonl",
                       ".env"):
            with self.subTest(ledger=ledger):
                self._assert_rejected(ledger)

    def test_arbitrary_repo_path_rejected(self):
        self._assert_rejected("scripts/evil-ledger.jsonl")

    def test_path_outside_repo_and_tmp_rejected(self):
        self._assert_rejected(str(REPO.parent / "evil-ledger.jsonl"))

    def test_record_ledger_flag_also_guarded(self):
        result = run([
            str(SCRIPTS / "outcome_route.py"),
            "--quota-fixture", str(FIXTURES / "quota-snapshot.frozen.json"),
            "--ledger", str(FIXTURES / "outcome-ledger.sample.jsonl"),
            "--role", "impl", "--tier", "2",
            "--task-class", "bounded-implementation", "--now", NOW,
            "--record", "--record-ledger", "lab/data/forbidden.jsonl",
        ])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("refusing to write ledger", result.stderr)
        self.assertFalse((REPO / "lab" / "data" / "forbidden.jsonl").exists())

    def test_resolve_write_path_allows_default_dir_and_tmp(self):
        allowed = ol.resolve_write_path(ol.DEFAULT_LEDGER_FILE)
        self.assertEqual(allowed, Path(ol.DEFAULT_LEDGER_FILE).resolve())
        tmp_target = Path(tempfile.gettempdir()) / "outcome-ledger-boundary-test.jsonl"
        self.assertEqual(ol.resolve_write_path(tmp_target), tmp_target.resolve())
        with self.assertRaises(ol.LedgerWriteError):
            ol.resolve_write_path(REPO / "lab" / "data" / "x.jsonl")
        with self.assertRaises(ol.LedgerWriteError):
            ol.resolve_write_path(REPO / "anywhere-else.jsonl")


class RequiredKeyFloor(unittest.TestCase):
    """Deleting any required key (or corrupting version/id/quota_cost) must fail."""

    @classmethod
    def setUpClass(cls):
        cls.catalog = ol.load_catalog()
        records, _ = ol.read_ledger(FIXTURES / "outcome-ledger.sample.jsonl")
        cls.decision = next(r for r in records if r["record_type"] == "decision")
        cls.outcome = next(r for r in records
                           if r["record_type"] == "outcome" and r.get("quota_cost"))

    def test_decision_missing_any_required_key_rejected(self):
        for key in ol.DECISION_REQUIRED_KEYS:
            with self.subTest(key=key):
                mutated = {k: v for k, v in self.decision.items() if k != key}
                self.assertTrue(ol.validate_decision(mutated, self.catalog),
                                f"decision without {key} must be rejected")

    def test_outcome_missing_any_required_key_rejected(self):
        for key in ol.OUTCOME_REQUIRED_KEYS:
            with self.subTest(key=key):
                mutated = {k: v for k, v in self.outcome.items() if k != key}
                self.assertTrue(ol.validate_outcome(mutated, self.catalog),
                                f"outcome without {key} must be rejected")

    def test_partial_quota_cost_rejected(self):
        for key in ol.QUOTA_COST_REQUIRED_KEYS:
            with self.subTest(key=key):
                mutated = dict(self.outcome)
                mutated["quota_cost"] = {k: v for k, v in self.outcome["quota_cost"].items()
                                         if k != key}
                self.assertTrue(ol.validate_outcome(mutated, self.catalog),
                                f"quota_cost without {key} must be rejected")

    def test_wrong_schema_version_rejected(self):
        self.assertTrue(ol.validate_decision({**self.decision, "schema_version": 999},
                                             self.catalog))
        self.assertTrue(ol.validate_outcome({**self.outcome, "schema_version": 999},
                                            self.catalog))

    def test_bad_decision_id_format_rejected(self):
        self.assertTrue(ol.validate_decision({**self.decision, "decision_id": "not-an-id"},
                                             self.catalog))


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


@NEEDS_TMP
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
