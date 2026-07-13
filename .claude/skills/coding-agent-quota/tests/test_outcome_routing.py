#!/usr/bin/env python3
"""Targeted tests for outcome-aware routing (coding-agent-quota skill).

Stdlib only (unittest). Run from repo root:
  python .claude/skills/coding-agent-quota/tests/test_outcome_routing.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SKILL = Path(__file__).resolve().parent.parent
REPO = SKILL.parent.parent.parent
SCRIPTS = SKILL / "scripts"
FIXTURES = SKILL / "fixtures" / "outcome"
NOW = "2026-07-12T08:30:00Z"

sys.path.insert(0, str(SCRIPTS))
import outcome_ledger as ol  # noqa: E402


def _tmp_writable() -> bool:
    """True when literal /tmp is writable (the only test write root).

    Must catch everything NamedTemporaryFile can raise when no usable temp dir
    exists (FileNotFoundError from gettempdir(), PermissionError, generic
    OSError) so environments without a writable temp SKIP cleanly, never fail.
    """
    try:
        with tempfile.NamedTemporaryFile(dir="/tmp"):
            return True
    except OSError:
        return False


TMP_WRITABLE = _tmp_writable()
NEEDS_TMP = unittest.skipUnless(
    TMP_WRITABLE,
    "no writable temp dir in this environment (read-only sandbox); "
    "skipping tests that must create temp files",
)


def run(args: list[str], env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, *args], capture_output=True, text=True,
                          cwd=REPO, env=env)


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


class RouteIdentityIsolation(unittest.TestCase):
    """Evidence is isolated across every concrete route identity dimension."""

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

    def test_route_stats_filters_on_tier(self):
        records, _ = ol.read_ledger(FIXTURES / "outcome-ledger.sample.jsonl")
        tier2 = ol.route_stats(records, role="impl",
                               task_class="bounded-implementation", routing_tier=2)
        tier3 = ol.route_stats(records, role="impl",
                               task_class="bounded-implementation", routing_tier=3)
        codex_terra = (
            "codex", "gpt-5.6-terra", "medium", "impl",
            "bounded-implementation", 2, "routing-policy-v1",
        )
        self.assertGreaterEqual(tier2.get(codex_terra, {}).get("observed", 0), 3)
        self.assertEqual(tier3, {})

    @NEEDS_TMP
    def test_other_codex_model_effort_cannot_steer_current_route(self):
        """Same provider/role/task/tier is still foreign evidence when the
        concrete model or effort differs from the catalog candidate route."""
        records, _ = ol.read_ledger(FIXTURES / "outcome-ledger.sample.jsonl")
        mutated = []
        for record in records:
            record = dict(record)
            if (
                record.get("record_type") == "outcome"
                and record.get("actual_provider") == "codex"
                and record.get("actual_model") == "gpt-5.6-terra"
            ):
                record["actual_model"] = "gpt-5.5"
                record["actual_effort"] = "high"
            mutated.append(record)
        with tempfile.TemporaryDirectory(dir="/tmp") as tmp:
            ledger = Path(tmp) / "foreign-codex-route.jsonl"
            ledger.write_text(
                "\n".join(json.dumps(r, sort_keys=True) for r in mutated) + "\n",
                encoding="utf-8",
            )
            result = run([
                str(SCRIPTS / "outcome_route.py"),
                "--quota-fixture", str(FIXTURES / "quota-snapshot.frozen.json"),
                "--ledger", str(ledger),
                "--role", "impl", "--tier", "2",
                "--task-class", "bounded-implementation", "--now", NOW,
            ])
        self.assertEqual(result.returncode, 0, result.stderr)
        rec = json.loads(result.stdout)["outcome_route_recommendation"]
        self.assertTrue(rec["degraded"])
        self.assertEqual(rec["provider"], rec["baseline_provider"])
        self.assertIn("codex/gpt-5.6-terra@medium observed=0", rec["degraded_reason"])
        codex_candidate = next(
            c for c in rec["candidates_by_quota_cost"] if c["provider"] == "codex"
        )
        self.assertEqual(codex_candidate["observed"], 0)

    def test_policy_version_is_part_of_stats_key(self):
        records, _ = ol.read_ledger(FIXTURES / "outcome-ledger.sample.jsonl")
        decision_id = "d-fx0001"
        mutated = []
        for record in records:
            record = dict(record)
            if record.get("decision_id") == decision_id:
                record["policy_version"] = "routing-policy-old"
            mutated.append(record)
        current = ol.route_stats(
            mutated,
            role="impl",
            task_class="bounded-implementation",
            routing_tier=2,
            policy_version="routing-policy-v1",
        )
        old = ol.route_stats(
            mutated,
            role="impl",
            task_class="bounded-implementation",
            routing_tier=2,
            policy_version="routing-policy-old",
        )
        self.assertNotEqual(current, old)
        self.assertTrue(all(identity[6] == "routing-policy-v1" for identity in current))
        self.assertTrue(all(identity[6] == "routing-policy-old" for identity in old))


class ConservativeSampleFloor(unittest.TestCase):
    def test_min_samples_must_be_positive(self):
        for value in ("0", "-1"):
            with self.subTest(value=value):
                result = replay(
                    "quota-snapshot.frozen.json",
                    "outcome-ledger.sample.jsonl",
                    extra=["--min-samples", value],
                )
                self.assertEqual(result.returncode, 2)
                self.assertIn("must be >= 1", result.stderr)

    @NEEDS_TMP
    def test_zero_observed_outcomes_force_degraded_fallback(self):
        records, _ = ol.read_ledger(FIXTURES / "outcome-ledger.sample.jsonl")
        pending_only = [r for r in records if r.get("record_type") == "decision"]
        with tempfile.TemporaryDirectory(dir="/tmp") as tmp:
            ledger = Path(tmp) / "pending-only.jsonl"
            ledger.write_text(
                "\n".join(json.dumps(r, sort_keys=True) for r in pending_only) + "\n",
                encoding="utf-8",
            )
            result = run([
                str(SCRIPTS / "outcome_route.py"),
                "--quota-fixture", str(FIXTURES / "quota-snapshot.frozen.json"),
                "--ledger", str(ledger),
                "--role", "impl", "--tier", "2",
                "--task-class", "bounded-implementation", "--now", NOW,
            ])
        self.assertEqual(result.returncode, 0, result.stderr)
        rec = json.loads(result.stdout)["outcome_route_recommendation"]
        self.assertTrue(rec["degraded"])
        self.assertEqual(rec["provider"], rec["baseline_provider"])
        self.assertTrue(all(c["observed"] == 0 for c in rec["candidates_by_quota_cost"]))


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
        with tempfile.TemporaryDirectory(dir="/tmp") as tmp:
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
        with tempfile.TemporaryDirectory(dir="/tmp") as tmp:
            bad = Path(tmp) / "ledger.jsonl"
            bad.write_text("{this is not json\n", encoding="utf-8")
            result = self._replay_with_ledger(str(bad))
        self.assertEqual(result.returncode, 0, result.stderr)
        rec = json.loads(result.stdout)["outcome_route_recommendation"]
        self.assertTrue(rec["degraded"])
        self.assertIn("ledger failed validation", rec["degraded_reason"])
        self.assertEqual(rec["provider"], rec["baseline_provider"])

    def test_non_utf8_ledger_degrades_instead_of_crashing(self):
        """Corrupt bytes must take the same degraded path as JSON/schema errors,
        never an uncaught UnicodeDecodeError traceback."""
        with tempfile.TemporaryDirectory(dir="/tmp") as tmp:
            bad = Path(tmp) / "ledger.jsonl"
            bad.write_bytes(b"\xff\xfe\x00broken bytes\x80\n")
            result = self._replay_with_ledger(str(bad))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        rec = json.loads(result.stdout)["outcome_route_recommendation"]
        self.assertTrue(rec["degraded"])
        self.assertIn("ledger failed validation", rec["degraded_reason"])
        self.assertEqual(rec["provider"], rec["baseline_provider"])
        self.assertFalse(rec["switched_from_baseline"])


class UnreadableLedger(unittest.TestCase):
    """read_ledger degrades (records=[], error reported) instead of raising.

    PermissionError cannot be simulated reliably on CI (root ignores modes),
    so the OSError branch is exercised via mock, per review guidance.
    """

    def test_permission_denied_reported_as_parse_error(self):
        with mock.patch.object(Path, "read_text",
                               side_effect=PermissionError(13, "Permission denied")):
            records, errs = ol.read_ledger(FIXTURES / "outcome-ledger.sample.jsonl")
        self.assertEqual(records, [])
        self.assertEqual(len(errs), 1)
        self.assertIn("unreadable ledger", errs[0])
        self.assertIn("PermissionError", errs[0])

    def test_undecodable_bytes_reported_as_parse_error(self):
        with mock.patch.object(
            Path, "read_text",
            side_effect=UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte"),
        ):
            records, errs = ol.read_ledger(FIXTURES / "outcome-ledger.sample.jsonl")
        self.assertEqual(records, [])
        self.assertEqual(len(errs), 1)
        self.assertIn("unreadable ledger", errs[0])
        self.assertIn("UnicodeDecodeError", errs[0])


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
                       "checkpoints/forbidden.jsonl", "wandb/forbidden.jsonl",
                       "mlruns/forbidden.jsonl", ".env", ".env.local", ".environment"):
            with self.subTest(ledger=ledger):
                self._assert_rejected(ledger)

    def test_arbitrary_repo_path_rejected(self):
        self._assert_rejected("scripts/evil-ledger.jsonl")

    def test_repo_root_rejected(self):
        self._assert_rejected(str(REPO))

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

    def test_resolve_write_path_allows_default_dir_and_literal_tmp(self):
        allowed = ol.resolve_write_path(ol.DEFAULT_LEDGER_FILE)
        self.assertEqual(allowed, Path(ol.DEFAULT_LEDGER_FILE).resolve())
        # Literal POSIX /tmp — pure path check, no file is created here.
        tmp_target = Path("/tmp") / "outcome-ledger-boundary-test.jsonl"
        self.assertEqual(ol.resolve_write_path(tmp_target), tmp_target.resolve())
        with self.assertRaises(ol.LedgerWriteError):
            ol.resolve_write_path(REPO / "lab" / "data" / "x.jsonl")
        with self.assertRaises(ol.LedgerWriteError):
            ol.resolve_write_path(REPO / "anywhere-else.jsonl")

    def test_tmpdir_env_cannot_widen_boundary(self):
        """TMPDIR must never influence the write allowlist (BLOCKER regression:
        TMPDIR=.agent used to let record-decision write inside .agent/)."""
        evil = REPO / ".agent" / "evil-ledger.jsonl"
        for tmpdir in (str(REPO / ".agent"), ".agent"):
            with self.subTest(TMPDIR=tmpdir):
                env = {**os.environ, "TMPDIR": tmpdir}
                result = run([str(SCRIPTS / "outcome_ledger.py"),
                              "--ledger", str(evil),
                              "record-decision", "--role", "impl", "--routing-tier", "2",
                              "--provider", "codex", "--model", "gpt-5.6-terra",
                              "--effort", "medium", "--launch-surface", "codex_exec",
                              "--task-class", "boundary-test", "--decided-at", NOW,
                              "--quota-source", "test"], env=env)
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertIn("refusing to write ledger", result.stderr)
                self.assertFalse(evil.exists(), ".agent/evil-ledger.jsonl must not be created")

    def test_allow_test_dir_escape_hatch_removed_from_both_clis(self):
        ledger_result = run([
            str(SCRIPTS / "outcome_ledger.py"),
            "validate", "--allow-test-dir", str(REPO),
        ])
        route_result = replay(
            "quota-snapshot.frozen.json",
            "outcome-ledger.sample.jsonl",
            extra=["--allow-test-dir", str(REPO)],
        )
        for result in (ledger_result, route_result):
            self.assertEqual(result.returncode, 2)
            self.assertIn("unrecognized arguments: --allow-test-dir", result.stderr)

    def test_env_prefix_rejected_even_under_allowed_roots(self):
        for target in (
            ol.DEFAULT_LEDGER_FILE.parent / ".env.routing",
            Path("/tmp") / ".env-routing-ledger.jsonl",
            Path("/tmp") / ".environment" / "ledger.jsonl",
        ):
            with self.subTest(target=target):
                with self.assertRaises(ol.LedgerWriteError):
                    ol.resolve_write_path(target)

    @NEEDS_TMP
    def test_symlink_components_rejected_even_without_escape(self):
        with tempfile.TemporaryDirectory(dir="/tmp") as tmp:
            root = Path(tmp)
            real = root / "real"
            real.mkdir()
            link = root / "link"
            link.symlink_to(real, target_is_directory=True)
            with self.assertRaises(ol.LedgerWriteError):
                ol.resolve_write_path(link / "ledger.jsonl")

    @NEEDS_TMP
    def test_symlink_escape_from_tmp_rejected(self):
        with tempfile.TemporaryDirectory(dir="/tmp") as tmp:
            link = Path(tmp) / "repo-link"
            link.symlink_to(REPO, target_is_directory=True)
            with self.assertRaises(ol.LedgerWriteError):
                ol.resolve_write_path(link / "scripts" / "ledger.jsonl")


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

    def test_schema_version_type_confusion_rejected(self):
        """True == 1 and 1.0 == 1 in Python; bool/float/str lookalikes of the
        schema version must be rejected (only the exact int passes)."""
        for bad in (True, False, 1.0, "1"):
            with self.subTest(value=bad):
                self.assertTrue(
                    ol.validate_decision({**self.decision, "schema_version": bad},
                                         self.catalog),
                    f"decision schema_version={bad!r} must be rejected")
                self.assertTrue(
                    ol.validate_outcome({**self.outcome, "schema_version": bad},
                                        self.catalog),
                    f"outcome schema_version={bad!r} must be rejected")

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
        with tempfile.TemporaryDirectory(dir="/tmp") as tmp:
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
            key = next(iter(routes))
            self.assertIn("codex/gpt-5.6-terra@medium", key)
            self.assertEqual(routes[key]["outcome"]["pass"], 1)

    def test_record_outcome_for_unknown_decision_fails(self):
        with tempfile.TemporaryDirectory(dir="/tmp") as tmp:
            ledger = str(Path(tmp) / "ledger.jsonl")
            result = run([str(SCRIPTS / "outcome_ledger.py"), "--ledger", ledger,
                          "record-outcome", "--decision-id", "d-nope",
                          "--status", "observed", "--quality", "pass",
                          "--evidence-source", "x",
                          "--actual-provider", "codex", "--actual-model", "gpt-5.6-terra",
                          "--actual-effort", "medium"])
            self.assertEqual(result.returncode, 1)

    def test_record_decision_rejects_duplicate_before_append(self):
        with tempfile.TemporaryDirectory(dir="/tmp") as tmp:
            ledger = str(Path(tmp) / "ledger.jsonl")
            command = [
                str(SCRIPTS / "outcome_ledger.py"), "--ledger", ledger,
                "record-decision", "--decision-id", "d-duplicate-test",
                "--role", "impl", "--routing-tier", "2",
                "--provider", "codex", "--model", "gpt-5.6-terra",
                "--effort", "medium", "--launch-surface", "codex_exec",
                "--task-class", "duplicate-test", "--decided-at", NOW,
                "--quota-source", "test",
            ]
            first, second = run(command), run(command)
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            self.assertEqual(second.returncode, 1)
            self.assertIn("duplicate decision_id", second.stdout)
            self.assertEqual(len(Path(ledger).read_text(encoding="utf-8").splitlines()), 1)

    def test_outcome_route_record_rejects_duplicate_before_append(self):
        with tempfile.TemporaryDirectory(dir="/tmp") as tmp:
            ledger = Path(tmp) / "route-decisions.jsonl"
            command = [
                str(SCRIPTS / "outcome_route.py"),
                "--quota-fixture", str(FIXTURES / "quota-snapshot.frozen.json"),
                "--ledger", str(FIXTURES / "outcome-ledger.sample.jsonl"),
                "--role", "impl", "--tier", "2",
                "--task-class", "bounded-implementation", "--now", NOW,
                "--record", "--record-ledger", str(ledger),
            ]
            first, second = run(command), run(command)
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            self.assertEqual(second.returncode, 1)
            self.assertIn("duplicate decision_id", second.stderr)
            self.assertEqual(len(ledger.read_text(encoding="utf-8").splitlines()), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
