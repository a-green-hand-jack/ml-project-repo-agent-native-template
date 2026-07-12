#!/usr/bin/env python3
"""Check that template adoption preserved baseline tracked file bytes.

Exit code semantics (decided, plans/20260712-bootstrap-adoption-proof.zh.md
open question 5 / C3): non-zero is reserved for adoption's own integrity
failures -- tracked-byte hash mismatches or unresolved normalize blockers
(conflict/protected-path entries the tool could not safely move). The
target repo's own native-test smoke result (pass/fail/skipped/unknown) is a
*separate* signal about that repo's health, not about whether this tool did
its job; it never flips this script's exit code. To make sure a non-pass
smoke result can never be silently missed, it is always surfaced here as an
explicit `smoke_warnings` field (JSON) / `SMOKE WARNING` lines (text), read
from the most recent `prove` phase-log entry when available.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


def load_adopter():
    script = Path(__file__).resolve().with_name("adopt-existing-repo.py")
    spec = importlib.util.spec_from_file_location("adopt_existing_repo", script)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {script}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def latest_smoke_warnings(adopter: Any, target: Path) -> list[dict[str, Any]]:
    rows = adopter.read_phase_log(target)
    prove_rows = [r for r in rows if r.get("phase") == "prove"]
    if not prove_rows:
        return []
    details = prove_rows[-1].get("details", {})
    return list(details.get("warnings", []))


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    adopter = load_adopter()
    target = args.target.resolve()
    result = adopter.integrity_result(target)
    smoke_warnings = latest_smoke_warnings(adopter, target)
    if args.json:
        result_out = dict(result)
        result_out["smoke_warnings"] = smoke_warnings
        print(json.dumps(result_out, indent=2, sort_keys=True))
    else:
        print(
            "[check-adoption-integrity] "
            + ("OK" if result["ok"] else "FAIL")
            + f" -- present {result['present']}/{result['baseline_files']}"
        )
        for row in result["missing"]:
            print(f"missing {row['path']}")
        for blocker in result.get("unresolved_blockers", []):
            print(f"BLOCKED {blocker}")
        for w in smoke_warnings:
            print(f"SMOKE WARNING {w['item']}: result={w['result']} reason={w['reason']}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
