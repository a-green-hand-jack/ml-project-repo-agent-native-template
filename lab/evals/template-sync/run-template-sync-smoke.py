#!/usr/bin/env python3
"""Synthetic fault-injection smoke for scripts/template-sync.py (issue #35).

Builds a throwaway upstream template + downstream repo pair in a temp dir and
drives the *real* `scripts/template-sync.py` (copied into the synthetic
downstream, so its module-level `DOWNSTREAM = __file__.parent.parent` resolves
to the temp repo). The synthetic downstream ships stub
`sync-codex-adapters.py` / `validate-governance.py` whose exit codes the
fixture controls, so generator/validator success and failure are injectable
end-to-end.

Scenarios (each asserts the P0 transactional contract of issue #35):

- happy: five path classes handled correctly (framework overwrite / identical
  framework left alone / generated NOT raw-copied but generator rebuild runs /
  project bytes preserved / scaffold created when missing and kept when
  present / merge sentinel block replaced with the surrounding tail
  preserved), version advances atomically to the upstream version, receipt
  result=pass with a consistent source/from-to/manifest/stages, then an
  immediate rerun is idempotent (still pass, version stays put);
- generator_fail: generator stub exits 1 -> process non-zero, receipt
  result=partial, `.template.toml` STILL the old version (the exact bug this
  issue fixes: version must not advance before generated rebuild succeeds);
- validator_fail: validator stub exits 1 -> process non-zero, receipt
  result=partial, version unchanged, stages.validate=fail;
- no_verify: --no-verify keeps CLI compatibility but must NOT advance the
  version -> result=partial, validate=skipped, commit_version=skipped, exit
  non-zero, old version kept;
- dirty_upstream: a git upstream records git SHA + working-tree content_digest
  + dirty=true, and the dirty (uncommitted) bytes are the ones actually synced;
- interrupt: an in-process KeyboardInterrupt at the stage boundary is caught as
  status 'interrupt' (mapped to receipt result=unknown, never pass);
- warnings: an unclassified upstream file and a merge file with no sentinel
  block -> receipt result=partial (never pass) with explicit warnings; version
  still advances because the validator passed, but the honest signal is
  partial, not pass;
- governance_data_gap: real check-doc-lifecycle.py / validate-experiment-state.py /
  check-provenance-chain.py / init-governance-data.py newly landing (action=create)
  makes the receipt report new_validators + an init-governance-data.py --dry-run gap
  preview + a suggested command, without ever touching downstream data files; a
  second sync where those files already exist (action=unchanged) reports no gap
  (issue #63 D1);
- root_contract_framework: root CONTRACT.md is bound to the real production
  template-manifest.toml; dry-run does not create it, apply creates a missing
  copy and overwrites a stale copy, receipts keep it out of unclassified, and
  the immediate rerun is an apply no-op;
- generated_stale_rogue: a rogue generated-namespace file that already existed
  BEFORE the run, untouched by this run's generator, still surfaces as
  generated.unexpected -- generated.actual is the full post-generator governed
  set (classify() applied to the complete downstream snapshot), not just this
  run's generator delta;
- timeout_unknown: a validator that never returns within --timeout yields
  receipt result=unknown (never pass), keeps the old version, and exits
  non-zero;
- major_gate: a MAJOR jump without --allow-major is a strict pre-write no-op
  (exit 2, version untouched, no receipt written); with --allow-major it
  proceeds and advances;
- atomic_write (in-process): monkeypatch os.replace to fail during the version
  write and assert `.template.toml` keeps the old, still-parseable value with
  no orphan temp file — a version-write interruption never leaves a half row.
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "scripts" / "template-sync.py"
ADAPTER_SYNC_SCRIPT = REPO / "scripts" / "sync-codex-adapters.py"
PRODUCTION_MANIFEST = REPO / "template-manifest.toml"

# The upstream ships gen/adapter.txt as its committed generated output
# (kind=generated -> skipped by raw sync, rebuilt by the generator). GEN_CONTENT
# is the canonical expected content; GEN_OK reproduces it exactly.
GEN_CONTENT = "GEN-OUT v1\n"
GEN_OK = (
    "import os, sys\n"
    "os.makedirs('gen', exist_ok=True)\n"
    "open('gen/adapter.txt', 'w').write('GEN-OUT v1\\n')\n"
    "print('[stub-gen] ok'); sys.exit(0)\n"
)
# GEN_EXTRA reproduces the expected file BUT also emits an arbitrary file that is
# not in the expected generated set -> must become generated.unexpected -> fail.
GEN_EXTRA = (
    "import os, sys\n"
    "os.makedirs('gen', exist_ok=True)\n"
    "open('gen/adapter.txt', 'w').write('GEN-OUT v1\\n')\n"
    "open('gen/rogue.txt', 'w').write('surprise\\n')\n"
    "print('[stub-gen] extra'); sys.exit(0)\n"
)
# GEN_MISSING exits 0 but does not produce the expected generated file -> missing.
GEN_MISSING = "import sys\nprint('[stub-gen] noop'); sys.exit(0)\n"
# GEN_WRONG_BYTES writes the expected path (present in actual) but with the
# wrong content -> generated.content_mismatches, NOT generated.missing.
GEN_WRONG_BYTES = (
    "import os, sys\n"
    "os.makedirs('gen', exist_ok=True)\n"
    "open('gen/adapter.txt', 'w').write('WRONG BYTES\\n')\n"
    "print('[stub-gen] wrong-bytes'); sys.exit(0)\n"
)
GEN_FAIL = "import sys\nprint('[stub-gen] boom')\nsys.exit(1)\n"
VAL_OK = "import sys\nprint('[stub-val] ok')\nsys.exit(0)\n"
VAL_FAIL = "import sys\nprint('[stub-val] boom')\nsys.exit(1)\n"
VAL_SLOW = "import time\ntime.sleep(30)\n"  # exceeds the injected --timeout -> unknown

MANIFEST = """\
[[rule]]
glob = ".template.toml"
kind = "project"
[[rule]]
glob = "VERSION"
kind = "framework"
[[rule]]
glob = "template-manifest.toml"
kind = "framework"
[[rule]]
glob = "fw/**"
kind = "framework"
[[rule]]
glob = "gen/**"
kind = "generated"
[[rule]]
glob = "proj/**"
kind = "project"
[[rule]]
glob = "scaf/**"
kind = "scaffold"
[[rule]]
glob = "merge.md"
kind = "merge"
[[rule]]
glob = "merge-nosentinel.md"
kind = "merge"
"""

# #61: generated ownership is deliberately narrower than either adapter
# directory. The final framework rules are fallbacks and must therefore follow
# the concrete generated rules.
ADAPTER_OWNERSHIP_MANIFEST = """\
[[rule]]
glob = ".template.toml"
kind = "project"
[[rule]]
glob = "VERSION"
kind = "framework"
[[rule]]
glob = "template-manifest.toml"
kind = "framework"
[[rule]]
glob = ".claude/**"
kind = "framework"
[[rule]]
glob = ".codex/agents/**"
kind = "generated"
[[rule]]
glob = ".agents/skills/**"
kind = "generated"
[[rule]]
glob = ".codex/**"
kind = "framework"
[[rule]]
glob = ".agents/**"
kind = "framework"
[[rule]]
glob = "scripts/**"
kind = "framework"
"""

SENT_BEGIN = "<!-- template:begin -->"
SENT_END = "<!-- template:end -->"

# issue #63 D1: template-sync 收尾阶段的 governance_data_gap receipt 字段。用真实的
# check-doc-lifecycle.py / validate-experiment-state.py / check-provenance-chain.py /
# init-governance-data.py（而非 stub），因为这个场景直接测的是它们之间的接线，不是
# generator/validator 本身的通过与否（那两者继续用 stub 保持确定性）。
GOVERNANCE_GAP_MANIFEST = """\
[[rule]]
glob = ".template.toml"
kind = "project"
[[rule]]
glob = "VERSION"
kind = "framework"
[[rule]]
glob = "template-manifest.toml"
kind = "framework"
[[rule]]
glob = "scripts/**"
kind = "framework"
[[rule]]
glob = "gen/**"
kind = "generated"
"""

GOVERNANCE_VALIDATOR_NAMES = (
    "check-doc-lifecycle.py",
    "validate-experiment-state.py",
    "check-provenance-chain.py",
    "init-governance-data.py",
)


def fail(label: str, proc: subprocess.CompletedProcess[str] | None = None) -> int:
    print(f"[template-sync-smoke] FAIL: {label}")
    if proc is not None:
        print("$ " + (" ".join(map(str, proc.args)) if isinstance(proc.args, list) else str(proc.args)))
        print(proc.stdout)
        print(proc.stderr)
    return 1


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_upstream(root: Path, version: str, *, with_warnings: bool = False) -> None:
    write(root / "VERSION", version + "\n")
    write(root / "template-manifest.toml", MANIFEST)
    write(root / "fw" / "tool.txt", "new-fw\n")
    write(root / "fw" / "same.txt", "identical\n")
    write(root / "gen" / "adapter.txt", GEN_CONTENT)  # canonical expected generated content
    write(root / "proj" / "keep.txt", "upstream project content (must be ignored)\n")
    write(root / "scaf" / "new.txt", "scaffold seed\n")
    write(root / "scaf" / "existing.txt", "upstream scaffold seed (must NOT overwrite)\n")
    write(root / "merge.md", f"UP-HEAD\n{SENT_BEGIN}\nUPSTREAM BLOCK v2\n{SENT_END}\nUP-TAIL\n")
    if with_warnings:
        write(root / "unknown" / "orphan.txt", "no rule classifies me\n")
        write(root / "merge-nosentinel.md", "no sentinel here at all\n")


def build_downstream(root: Path, version: str, *, gen: str, val: str) -> None:
    (root / "scripts").mkdir(parents=True, exist_ok=True)
    shutil.copy2(SCRIPT, root / "scripts" / "template-sync.py")
    write(root / "scripts" / "sync-codex-adapters.py", gen)
    write(root / "scripts" / "validate-governance.py", val)
    write(root / ".template.toml", f'[template]\norigin = "acme/downstream"\nversion = "{version}"\n')
    # framework: one stale (to overwrite), one identical (must be left alone).
    write(root / "fw" / "tool.txt", "old-fw\n")
    write(root / "fw" / "same.txt", "identical\n")
    # project: downstream-owned bytes that must survive untouched.
    write(root / "proj" / "keep.txt", "DOWNSTREAM OWNED — do not touch\n")
    # scaffold: one already present (keep), scaf/new.txt intentionally absent (create).
    write(root / "scaf" / "existing.txt", "downstream custom scaffold\n")
    # merge: old block + downstream tail that must be preserved.
    write(root / "merge.md", f"DOWN-HEAD\n{SENT_BEGIN}\nDOWNSTREAM BLOCK v1\n{SENT_END}\nDOWN-TAIL\n")


def build_adapter_ownership_upstream(root: Path) -> None:
    """Build a real Codex adapter surface without duplicating generator logic."""
    (root / "scripts").mkdir(parents=True, exist_ok=True)
    write(root / "VERSION", "v1.1.0\n")
    write(root / "template-manifest.toml", ADAPTER_OWNERSHIP_MANIFEST)
    shutil.copy2(SCRIPT, root / "scripts" / "template-sync.py")
    shutil.copy2(ADAPTER_SYNC_SCRIPT, root / "scripts" / "sync-codex-adapters.py")
    write(root / ".claude" / "agents" / "demo.md", "---\nname: demo\ndescription: demo agent\ntools: Read\n---\n\nDemo.\n")
    write(root / ".claude" / "skills" / "demo-skill" / "SKILL.md", "---\nname: demo-skill\ndescription: demo skill\n---\n\nDemo.\n")
    for rel in ("config.toml", "rules/default.rules", "README.md", "AGENTS.md", "CLAUDE.md", "ANATOMY.md"):
        write(root / ".codex" / rel, f"upstream codex {rel}\n")
    for rel in ("README.md", "AGENTS.md", "CLAUDE.md", "ANATOMY.md"):
        write(root / ".agents" / rel, f"upstream agents {rel}\n")
    proc = subprocess.run([sys.executable, str(root / "scripts" / "sync-codex-adapters.py")],
                          cwd=root, text=True, capture_output=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"adapter fixture generation failed:\n{proc.stdout}\n{proc.stderr}")


def build_adapter_ownership_downstream(root: Path) -> None:
    (root / "scripts").mkdir(parents=True, exist_ok=True)
    shutil.copy2(SCRIPT, root / "scripts" / "template-sync.py")
    write(root / ".template.toml", '[template]\norigin = "acme/downstream"\nversion = "v1.0.0"\n')
    for rel in ("config.toml", "rules/default.rules", "README.md", "AGENTS.md", "CLAUDE.md", "ANATOMY.md"):
        write(root / ".codex" / rel, f"stale codex {rel}\n")
    for rel in ("README.md", "AGENTS.md", "CLAUDE.md", "ANATOMY.md"):
        write(root / ".agents" / rel, f"stale agents {rel}\n")
    write(root / ".codex" / "agents" / "demo.toml", "stale generated agent\n")
    write(root / ".agents" / "skills" / "demo-skill" / "SKILL.md", "stale generated skill\n")
    write(root / "scripts" / "validate-governance.py", VAL_OK)


def build_governance_gap_upstream(root: Path) -> None:
    (root / "scripts").mkdir(parents=True, exist_ok=True)
    write(root / "VERSION", "v1.1.0\n")
    write(root / "template-manifest.toml", GOVERNANCE_GAP_MANIFEST)
    shutil.copy2(SCRIPT, root / "scripts" / "template-sync.py")
    for name in GOVERNANCE_VALIDATOR_NAMES:
        shutil.copy2(REPO / "scripts" / name, root / "scripts" / name)
    write(root / "scripts" / "sync-codex-adapters.py", GEN_OK)
    write(root / "scripts" / "validate-governance.py", VAL_OK)
    write(root / "gen" / "adapter.txt", GEN_CONTENT)


def build_governance_gap_downstream(root: Path) -> None:
    (root / "scripts").mkdir(parents=True, exist_ok=True)
    shutil.copy2(SCRIPT, root / "scripts" / "template-sync.py")
    write(root / "scripts" / "sync-codex-adapters.py", GEN_OK)
    write(root / "scripts" / "validate-governance.py", VAL_OK)
    write(root / ".template.toml", '[template]\norigin = "acme/downstream"\nversion = "v1.0.0"\n')
    # 预置一条真实的 pre-governance 存量数据缺口：run status=done 但缺 status_history/
    # approval 字段——这些新 validator 落地前它们从未被要求过。
    write(
        root / "lab" / "research" / "experiment-ledger.yaml",
        "experiments:\n  - id: run-legacy\n    status: done\n    commit: \"abc1234\"\n",
    )


def check_governance_data_gap_report(tmp: Path) -> int:
    """issue #63 D1: template-sync 新落地门禁 validator 时，receipt 必须报告新增门禁
    清单 + 数据层 gap 预览计数 + 建议命令，且绝不自动执行 init（数据文件不得被动过）。
    validator 已存在（非首次落地）时不应再报 governance_data_gap。
    """
    up = tmp / "up-gov-gap"
    down = tmp / "down-gov-gap"
    receipt_f = tmp / "receipt-gov-gap.json"
    build_governance_gap_upstream(up)
    build_governance_gap_downstream(down)

    proc = subprocess.run(
        [sys.executable, "scripts/template-sync.py", "--from", str(up), "--receipt", str(receipt_f)],
        cwd=down, text=True, capture_output=True,
    )
    if not receipt_f.exists():
        return fail("首次落地 governance validator：receipt 未落盘", proc)
    data = json.loads(receipt_f.read_text(encoding="utf-8"))
    gap = data.get("governance_data_gap")
    if not gap:
        return fail(f"首次落地 3 个 G1 validator 应产出 governance_data_gap，得到 {gap}", proc)
    # newly_landed_validators 只认 scripts/check-*.py / scripts/validate-*.py —— 命中三个
    # G1 门禁本身；init-governance-data.py 是补救脚本不是 gate，故意不在这个集合里。
    expected_new = {
        f"scripts/{n}" for n in GOVERNANCE_VALIDATOR_NAMES if n != "init-governance-data.py"
    }
    if set(gap.get("new_validators", [])) != expected_new:
        return fail(f"new_validators 应恰为 {expected_new}，得到 {gap.get('new_validators')}", proc)
    inner = gap.get("gap")
    if not inner or inner.get("error"):
        return fail(f"gap 预览应成功产出诚实计数，得到：{inner}", proc)
    if inner.get("changed", 0) < 1:
        return fail(f"应检测到 ≥1 处缺口（run-legacy 缺 status_history/approval），得到 {inner}", proc)
    if not any("run-legacy" in k for k in inner.get("changed_keys", [])):
        return fail(f"缺口应命中 run-legacy，changed_keys={inner.get('changed_keys')}", proc)
    if gap.get("suggested_command") != "python scripts/init-governance-data.py":
        return fail(f"suggested_command 不对：{gap.get('suggested_command')}", proc)
    ledger_after = (down / "lab" / "research" / "experiment-ledger.yaml").read_text(encoding="utf-8")
    if "governance_status" in ledger_after:
        return fail("template-sync 不该自动执行 init——数据文件被静默改动了", proc)

    # 负例：validator 已存在（非首次落地，本次 action=unchanged）——不应再报 gap。
    for name in GOVERNANCE_VALIDATOR_NAMES:
        shutil.copy2(up / "scripts" / name, down / "scripts" / name)
    receipt_f2 = tmp / "receipt-gov-gap-2.json"
    proc2 = subprocess.run(
        [sys.executable, "scripts/template-sync.py", "--from", str(up), "--receipt", str(receipt_f2)],
        cwd=down, text=True, capture_output=True,
    )
    data2 = json.loads(receipt_f2.read_text(encoding="utf-8"))
    if data2.get("governance_data_gap") is not None:
        return fail(f"validator 已存在时不该再报 governance_data_gap，得到 {data2.get('governance_data_gap')}", proc2)

    print("[template-sync-smoke] governance_data_gap OK")
    return 0


def check_adapter_ownership_exact_set(tmp: Path) -> int:
    """#61 regression: only actual adapter outputs are generated.

    A broad `.codex/**` or `.agents/**` generated rule wrongly makes native
    config/rules/navigation files part of the exact generated manifest and
    blocks version advancement forever. This production-path fixture copies the
    real adapter generator and derives the expected paths from it.
    """
    up, down, receipt = tmp / "up-adapter-owner", tmp / "down-adapter-owner", tmp / "receipt-adapter-owner.json"
    build_adapter_ownership_upstream(up)
    build_adapter_ownership_downstream(down)

    proc = run_sync(down, up, receipt)
    if proc.returncode != 0:
        return fail("adapter ownership sync should pass", proc)
    r = read_json(receipt)
    sync_spec = importlib.util.spec_from_file_location("adapter_sync_expected", up / "scripts" / "sync-codex-adapters.py")
    sync_mod = importlib.util.module_from_spec(sync_spec)
    sys.modules[sync_spec.name] = sync_mod
    sync_spec.loader.exec_module(sync_mod)
    expected_generated = {path.relative_to(up).as_posix() for path in sync_mod.expected_files()}
    got_generated = set(r["manifest"]["generated"]["expected"])
    if got_generated != expected_generated:
        return fail(f"generated manifest must exactly equal real adapter outputs, got {got_generated}", proc)
    if r["manifest"]["generated"]["missing"] or r["manifest"]["generated"]["unexpected"]:
        return fail(f"adapter generated manifest should be clean, got {r['manifest']['generated']}", proc)
    framework_paths = {".codex/config.toml", ".codex/rules/default.rules", ".codex/README.md",
                       ".codex/AGENTS.md", ".codex/CLAUDE.md", ".codex/ANATOMY.md",
                       ".agents/README.md", ".agents/AGENTS.md", ".agents/CLAUDE.md", ".agents/ANATOMY.md"}
    if not framework_paths <= set(r["manifest"]["apply_changed"]):
        return fail(f"native adapter framework files must be applied, got {r['manifest']['apply_changed']}", proc)
    if expected_generated & set(r["manifest"]["apply_changed"]):
        return fail("generated adapters must not be raw-copied during apply", proc)
    if version_of(down) != "v1.1.0" or r["result"] != "pass":
        return fail(f"clean adapter ownership sync must advance version, got {r['result']}/{version_of(down)}", proc)

    rerun = run_sync(down, up, receipt)
    if rerun.returncode != 0 or read_json(receipt)["manifest"]["apply_changed"]:
        return fail("adapter ownership immediate rerun must be an apply no-op", rerun)
    return 0


def run_sync(downstream: Path, upstream: Path, receipt: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(downstream / "scripts" / "template-sync.py"),
         "--from", str(upstream), "--receipt", str(receipt), *extra],
        cwd=downstream, text=True, capture_output=True, check=False,
    )


def version_of(downstream: Path) -> str:
    return tomllib.loads((downstream / ".template.toml").read_text(encoding="utf-8"))["template"]["version"]


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def root_contract_manifest_error(manifest: Path) -> str | None:
    """Check the production rule with template-sync's own parser/matcher."""
    rules = tomllib.loads(manifest.read_text(encoding="utf-8")).get("rule", [])
    spec = importlib.util.spec_from_file_location("template_sync_manifest_check", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    matches = [rule for rule in rules if module.match_glob("CONTRACT.md", rule.get("glob", ""))]
    if len(matches) != 1:
        return f"CONTRACT.md must match exactly one production rule, got {matches}"
    if matches[0].get("kind") != "framework":
        return f"CONTRACT.md's only production rule must be framework, got {matches[0]}"
    if module.classify("CONTRACT.md", rules) != "framework":
        return "template-sync classify() must classify CONTRACT.md as framework"
    return None


def write_conflicting_contract_manifest(source: Path, destination: Path) -> None:
    """Create an isolated contradictory rule solely for mutation sanity."""
    lines = source.read_text(encoding="utf-8").splitlines(keepends=True)
    for index, line in enumerate(lines):
        if line.strip() != 'glob = "CONTRACT.md"':
            continue
        for kind_index in range(index + 1, len(lines)):
            if lines[kind_index].startswith("[[rule]]"):
                break
            if lines[kind_index].lstrip().startswith("kind ="):
                lines[kind_index] = 'kind = "project"  # isolated mutation sanity\\n'
                write(destination, "".join(lines))
                return
        break
    raise RuntimeError("production CONTRACT.md rule has no mutable kind field")


def check_happy_and_idempotent(tmp: Path) -> int:
    up = tmp / "up"
    down = tmp / "down"
    receipt = tmp / "receipt.json"
    build_upstream(up, "v1.1.0")
    build_downstream(down, "v1.0.0", gen=GEN_OK, val=VAL_OK)

    proc = run_sync(down, up, receipt)
    if proc.returncode != 0:
        return fail("happy path should exit 0", proc)
    r = read_json(receipt)
    if r["result"] != "pass":
        return fail(f"happy path receipt result should be pass, got {r['result']}", proc)
    if version_of(down) != "v1.1.0":
        return fail(f"version should advance to v1.1.0, got {version_of(down)}", proc)
    if r["committed_version"] != "v1.1.0" or r["from_version"] != "v1.0.0" or not r["version_advanced"]:
        return fail(f"receipt version fields inconsistent: {r}", proc)
    if not r["source"].get("content_digest", "").startswith("sha256:"):
        return fail(f"upstream must always carry a sha256 content_digest, got {r['source']}", proc)
    stages = r["stages"]
    if not all(stages[k] == "ok" for k in ("apply", "generated_rebuild", "validate", "commit_version")):
        return fail(f"all stages should be ok on happy path, got {stages}", proc)
    if r["manifest"]["missing"] or r["manifest"]["unexpected"]:
        return fail(f"happy manifest should have no missing/unexpected, got {r['manifest']}", proc)
    # generated exact manifest: expected generated set = kind=generated upstream paths.
    gm = r["manifest"]["generated"]
    if "gen/adapter.txt" not in gm["expected"]:
        return fail(f"expected generated set should come from kind=generated paths, got {gm}", proc)
    if "gen/adapter.txt" not in gm["actual_changed"]:
        return fail(f"generator should (re)produce the expected generated file, got {gm}", proc)
    if "gen/adapter.txt" not in gm["actual"]:
        return fail(f"generated.actual must be the full post-generator governed set, got {gm}", proc)
    if gm["missing"] or gm["unexpected"]:
        return fail(f"happy generated manifest should have no missing/unexpected, got {gm}", proc)

    # five-class assertions
    if (down / "fw" / "tool.txt").read_text() != "new-fw\n":
        return fail("framework positive: fw/tool.txt should be overwritten")
    if "fw/same.txt" in r["manifest"]["apply_changed"]:
        return fail("framework negative: identical fw/same.txt should not be rewritten")
    if "gen/adapter.txt" in r["manifest"]["apply_changed"]:
        return fail("generated negative: gen/adapter.txt must NOT be raw-copied during apply")
    if (down / "gen" / "adapter.txt").read_text() != GEN_CONTENT:
        return fail("generated positive: generator should reproduce gen/adapter.txt content")
    if (down / "proj" / "keep.txt").read_text() != "DOWNSTREAM OWNED — do not touch\n":
        return fail("project negative: downstream proj/keep.txt bytes must be preserved")
    if not (down / "scaf" / "new.txt").exists():
        return fail("scaffold positive: scaf/new.txt should be created when missing")
    if (down / "scaf" / "existing.txt").read_text() != "downstream custom scaffold\n":
        return fail("scaffold negative: existing scaffold must be kept, not overwritten")
    merged = (down / "merge.md").read_text()
    if "UPSTREAM BLOCK v2" not in merged:
        return fail("merge positive: sentinel block should be replaced with upstream block")
    if "DOWN-HEAD" not in merged or "DOWN-TAIL" not in merged:
        return fail("merge negative: downstream content outside the sentinel must be preserved")

    # idempotent rerun
    proc2 = run_sync(down, up, receipt)
    if proc2.returncode != 0:
        return fail("idempotent rerun should exit 0", proc2)
    r2 = read_json(receipt)
    if r2["result"] != "pass" or version_of(down) != "v1.1.0":
        return fail(f"idempotent rerun should stay pass at v1.1.0, got {r2['result']}/{version_of(down)}", proc2)
    if r2["manifest"]["apply_changed"]:
        return fail(f"idempotent rerun should apply nothing, changed {r2['manifest']['apply_changed']}", proc2)
    return 0


def check_generator_fail(tmp: Path) -> int:
    up = tmp / "up-gf"
    down = tmp / "down-gf"
    receipt = tmp / "receipt-gf.json"
    build_upstream(up, "v1.1.0")
    build_downstream(down, "v1.0.0", gen=GEN_FAIL, val=VAL_OK)

    proc = run_sync(down, up, receipt)
    if proc.returncode == 0:
        return fail("generator failure must make the process exit non-zero", proc)
    if version_of(down) != "v1.0.0":
        return fail(f"generator failure must NOT advance version, got {version_of(down)}", proc)
    r = read_json(receipt)
    if r["result"] != "partial":
        return fail(f"generator failure receipt should be partial, got {r['result']}", proc)
    if r["committed_version"] != "v1.0.0" or r["version_advanced"]:
        return fail(f"receipt must report version kept at v1.0.0, got {r}", proc)
    if r["stages"]["generated_rebuild"] != "fail" or r["stages"]["commit_version"] != "skipped":
        return fail(f"stages should show generated_rebuild=fail, commit skipped, got {r['stages']}", proc)
    if not r["failure"] or r["failure"]["stage"] != "generated_rebuild" or not r["failure"]["rerun_command"]:
        return fail(f"failure block should name generated_rebuild + a rerun command, got {r.get('failure')}", proc)
    # framework file WAS written (partial physical state) but version stayed old — the core fix.
    if (down / "fw" / "tool.txt").read_text() != "new-fw\n":
        return fail("generator-fail partial state should still show the applied framework write")
    return 0


def check_validator_fail(tmp: Path) -> int:
    up = tmp / "up-vf"
    down = tmp / "down-vf"
    receipt = tmp / "receipt-vf.json"
    build_upstream(up, "v1.1.0")
    build_downstream(down, "v1.0.0", gen=GEN_OK, val=VAL_FAIL)

    proc = run_sync(down, up, receipt)
    if proc.returncode == 0:
        return fail("validator failure must make the process exit non-zero", proc)
    if version_of(down) != "v1.0.0":
        return fail(f"validator failure must NOT advance version, got {version_of(down)}", proc)
    r = read_json(receipt)
    if r["result"] != "partial":
        return fail(f"validator failure receipt should be partial, got {r['result']}", proc)
    if r["stages"]["validate"] != "fail" or r["stages"]["commit_version"] != "skipped":
        return fail(f"stages should show validate=fail, commit skipped, got {r['stages']}", proc)
    if not r["failure"] or r["failure"]["stage"] != "validate":
        return fail(f"failure block should name validate, got {r.get('failure')}", proc)
    return 0


def check_warnings_partial(tmp: Path) -> int:
    up = tmp / "up-w"
    down = tmp / "down-w"
    receipt = tmp / "receipt-w.json"
    build_upstream(up, "v1.1.0", with_warnings=True)
    build_downstream(down, "v1.0.0", gen=GEN_OK, val=VAL_OK)

    proc = run_sync(down, up, receipt)
    if proc.returncode != 0:
        return fail("warnings scenario should still exit 0 (validator passed)", proc)
    r = read_json(receipt)
    if r["result"] != "partial":
        return fail(f"unclassified/no-sentinel should yield partial, not pass, got {r['result']}", proc)
    if version_of(down) != "v1.1.0":
        return fail("with a passing validator the version still advances (flagged partial)", proc)
    if "unknown/orphan.txt" not in r["classification"]["unclassified"]:
        return fail(f"unclassified upstream file should be recorded, got {r['classification']}", proc)
    if not any("unclassified" in w for w in r["warnings"]):
        return fail(f"warnings should include the unclassified entry, got {r['warnings']}", proc)
    if not any("merge" in w for w in r["warnings"]):
        return fail(f"warnings should include the no-sentinel merge entry, got {r['warnings']}", proc)
    # the no-sentinel merge file must be left untouched (not clobbered).
    if (down / "merge-nosentinel.md").exists():
        return fail("no-sentinel merge file must be skipped, not created downstream")
    return 0


def git_commit_repo(root: Path) -> None:
    for cmd in (
        ["git", "init", "-q"],
        ["git", "config", "user.email", "smoke@example.test"],
        ["git", "config", "user.name", "Smoke"],
        ["git", "add", "."],
        ["git", "commit", "-q", "-m", "seed"],
    ):
        proc = subprocess.run(cmd, cwd=root, text=True, capture_output=True, check=False)
        if proc.returncode != 0:
            raise SystemExit(fail(f"git seed step {cmd}", proc))


def check_no_verify_no_advance(tmp: Path) -> int:
    """--no-verify keeps CLI compatibility but must NOT advance the version:
    result=partial, commit_version=skipped, exit non-zero, old version kept."""
    up = tmp / "up-nv"
    down = tmp / "down-nv"
    receipt = tmp / "receipt-nv.json"
    build_upstream(up, "v1.1.0")
    build_downstream(down, "v1.0.0", gen=GEN_OK, val=VAL_FAIL)  # val stub present but must be skipped

    proc = run_sync(down, up, receipt, "--no-verify")
    if proc.returncode == 0:
        return fail("--no-verify must NOT advance version -> exit non-zero", proc)
    if version_of(down) != "v1.0.0":
        return fail(f"--no-verify must keep the old version, got {version_of(down)}", proc)
    r = read_json(receipt)
    if r["result"] != "partial":
        return fail(f"--no-verify receipt should be partial, got {r['result']}", proc)
    if r["stages"]["validate"] != "skipped" or r["stages"]["commit_version"] != "skipped":
        return fail(f"--no-verify stages should be validate=skipped, commit=skipped, got {r['stages']}", proc)
    if r["committed_version"] != "v1.0.0" or r["version_advanced"]:
        return fail(f"--no-verify must report version kept, got {r}", proc)
    if not r["failure"] or r["failure"]["stage"] != "validate":
        return fail(f"--no-verify failure block should name validate, got {r.get('failure')}", proc)
    return 0


# The exact path set that build_upstream()/build_downstream() cause plan_sync()
# to mark writes=True for (framework create/overwrite + scaffold create +
# merge-update) -- the same fixture pair check_happy_and_idempotent drives to a
# real apply of these same five paths. Used here to prove --dry-run's planned
# set matches the real apply plan, without re-implementing classify()/plan_sync.
EXPECTED_WRITE_PATHS = {"VERSION", "template-manifest.toml", "fw/tool.txt", "merge.md", "scaf/new.txt"}


def check_dry_run_no_side_effect(tmp: Path) -> int:
    """--dry-run drives the real copied-script CLI end-to-end: it must share the
    exact same plan/classify surface as apply (planned paths == the real apply's
    write set), exit 0, report result=dry-run, and cause zero downstream side
    effects -- except that an explicitly-passed --receipt PATH is written (the
    one documented exception), never the default receipt path, never the synced
    files/generator/validator/.template.toml version."""
    up = tmp / "up-dr"
    down = tmp / "down-dr"
    receipt = tmp / "receipt-dr.json"
    build_upstream(up, "v1.1.0")
    build_downstream(down, "v1.0.0", gen=GEN_OK, val=VAL_OK)

    proc = run_sync(down, up, receipt, "--dry-run")
    if proc.returncode != 0:
        return fail("--dry-run should exit 0", proc)
    if not receipt.exists():
        return fail("--dry-run with an explicit --receipt PATH must still write that one file", proc)
    r = read_json(receipt)
    if r["result"] != "dry-run":
        return fail(f"--dry-run receipt result should be 'dry-run', got {r['result']}", proc)
    if r["stages"]["apply"] != "planned":
        return fail(f"--dry-run stages.apply should be 'planned', got {r['stages']}", proc)
    if (r["stages"]["generated_rebuild"] != "skipped" or r["stages"]["validate"] != "skipped"
            or r["stages"]["commit_version"] != "skipped"):
        return fail(
            "--dry-run must leave generated_rebuild/validate/commit_version all 'skipped', "
            f"got {r['stages']}", proc,
        )
    planned = set(r["manifest"]["expected"])
    if planned != EXPECTED_WRITE_PATHS:
        return fail(
            f"--dry-run planned write set must equal the real apply's write set "
            f"{EXPECTED_WRITE_PATHS}, got {planned} (dry-run and apply must share one plan)",
            proc,
        )
    # zero side effects: no default receipt path, no synced bytes, no generator/
    # validator run, no version advance.
    if (down / ".template-sync-receipt.json").exists():
        return fail("--dry-run must never write the default receipt path when --receipt is given", proc)
    if version_of(down) != "v1.0.0":
        return fail(f"--dry-run must not advance the version, got {version_of(down)}", proc)
    if (down / "fw" / "tool.txt").read_text() != "old-fw\n":
        return fail("--dry-run must not touch framework files", proc)
    if (down / "VERSION").exists():
        return fail("--dry-run must not create the planned downstream/VERSION target", proc)
    if (down / "template-manifest.toml").exists():
        return fail("--dry-run must not create the planned downstream/template-manifest.toml target", proc)
    if (down / "scaf" / "new.txt").exists():
        return fail("--dry-run must not create scaffold files", proc)
    if (down / "gen").exists():
        return fail("--dry-run must never run the generator (gen/ must not exist)", proc)
    if "DOWN-HEAD" not in (down / "merge.md").read_text() or "UPSTREAM BLOCK v2" in (down / "merge.md").read_text():
        return fail("--dry-run must not touch merge files", proc)
    return 0


def check_root_contract_framework(tmp: Path) -> int:
    """#62: bind root CONTRACT.md coverage to the production manifest."""
    up = tmp / "up-root-contract"
    down = tmp / "down-root-contract"
    dry_receipt = tmp / "receipt-root-contract-dry.json"
    receipt = tmp / "receipt-root-contract.json"
    build_upstream(up, "v1.1.0")
    build_downstream(down, "v1.0.0", gen=GEN_OK, val=VAL_OK)
    shutil.copy2(PRODUCTION_MANIFEST, up / "template-manifest.toml")

    manifest_error = root_contract_manifest_error(up / "template-manifest.toml")
    if manifest_error is not None:
        return fail(f"production root CONTRACT manifest rule invalid: {manifest_error}")
    conflicting_manifest = tmp / "conflicting-template-manifest.toml"
    write_conflicting_contract_manifest(up / "template-manifest.toml", conflicting_manifest)
    conflicting_error = root_contract_manifest_error(conflicting_manifest)
    if conflicting_error is None:
        return fail("root CONTRACT manifest assertion must fail for an isolated conflicting rule")
    print(f"[template-sync-smoke] #62 mutation rejected: {conflicting_error}")

    write(up / "CONTRACT.md", "upstream governed-component index\n")

    dry = run_sync(down, up, dry_receipt, "--dry-run")
    if dry.returncode != 0:
        return fail("root CONTRACT dry-run should exit 0", dry)
    dry_result = read_json(dry_receipt)
    if "CONTRACT.md" not in dry_result["classification"]["framework"]:
        return fail(f"root CONTRACT must classify as framework, got {dry_result['classification']}", dry)
    if "CONTRACT.md" not in dry_result["manifest"]["expected"]:
        return fail(f"root CONTRACT missing from dry-run plan, got {dry_result['manifest']}", dry)
    if (down / "CONTRACT.md").exists():
        return fail("root CONTRACT dry-run must not create the downstream file", dry)

    missing = run_sync(down, up, receipt)
    if missing.returncode != 0:
        return fail("missing root CONTRACT apply should exit 0", missing)
    missing_result = read_json(receipt)
    contract = down / "CONTRACT.md"
    if contract.read_text(encoding="utf-8") != "upstream governed-component index\n":
        return fail("missing root CONTRACT must be created from upstream", missing)
    if "CONTRACT.md" not in missing_result["manifest"]["apply_changed"]:
        return fail(f"missing root CONTRACT must be applied, got {missing_result['manifest']}", missing)
    if "CONTRACT.md" in missing_result["classification"]["unclassified"]:
        return fail(f"receipt must not list root CONTRACT as unclassified, got {missing_result['classification']}", missing)

    write(contract, "downstream stale index\n")
    stale = run_sync(down, up, receipt)
    if stale.returncode != 0:
        return fail("stale root CONTRACT apply should exit 0", stale)
    stale_result = read_json(receipt)
    if contract.read_text(encoding="utf-8") != "upstream governed-component index\n":
        return fail("stale root CONTRACT must be overwritten from upstream", stale)
    if "CONTRACT.md" not in stale_result["manifest"]["apply_changed"]:
        return fail(f"stale root CONTRACT must be overwritten, got {stale_result['manifest']}", stale)
    if "CONTRACT.md" in stale_result["classification"]["unclassified"]:
        return fail(f"stale receipt must not list root CONTRACT as unclassified, got {stale_result['classification']}", stale)

    rerun = run_sync(down, up, receipt)
    if rerun.returncode != 0:
        return fail("root CONTRACT idempotent rerun should exit 0", rerun)
    if read_json(receipt)["manifest"]["apply_changed"]:
        return fail("root CONTRACT idempotent rerun must be an apply no-op", rerun)
    return 0


def check_dirty_upstream_source(tmp: Path) -> int:
    """A git upstream must record git SHA + working-tree content digest + dirty
    status; a dirty source must not be reported as a clean SHA only."""
    up = tmp / "up-dirty"
    down = tmp / "down-dirty"
    receipt = tmp / "receipt-dirty.json"
    build_upstream(up, "v1.1.0")
    build_downstream(down, "v1.0.0", gen=GEN_OK, val=VAL_OK)
    git_commit_repo(up)
    # make the tracked framework file dirty (uncommitted edit) -> working tree != HEAD
    (up / "fw" / "tool.txt").write_text("new-fw DIRTY EDIT\n", encoding="utf-8")

    proc = run_sync(down, up, receipt)
    if proc.returncode != 0:
        return fail("dirty-upstream sync should still complete (dirty is recorded, not fatal)", proc)
    src = read_json(receipt)["source"]
    if not (isinstance(src.get("git_sha"), str) and len(src["git_sha"]) == 40):
        return fail(f"git upstream must record a 40-char HEAD SHA, got {src.get('git_sha')}", proc)
    if src.get("dirty") is not True:
        return fail(f"dirty working tree must be flagged dirty=true, got {src.get('dirty')}", proc)
    if not src.get("content_digest", "").startswith("sha256:"):
        return fail(f"source must always carry a content_digest, got {src}", proc)
    # the actually-copied dirty bytes must have landed downstream (binds real bytes).
    if (down / "fw" / "tool.txt").read_text() != "new-fw DIRTY EDIT\n":
        return fail("dirty working-tree bytes should be the ones synced downstream", proc)
    return 0


def check_interrupt_unknown(tmp: Path) -> int:
    """In-process, reproducible interruption injection: a KeyboardInterrupt at
    the stage boundary (subprocess.run) is caught as an 'interrupt' status that
    the receipt maps to unknown (never pass)."""
    spec = importlib.util.spec_from_file_location("template_sync_intr", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)

    def interrupt(*_a: object, **_k: object) -> None:
        raise KeyboardInterrupt

    real = mod.subprocess.run
    mod.subprocess.run = interrupt
    try:
        status, _detail = mod.run_stage(["true"], tmp, 5)
    finally:
        mod.subprocess.run = real
    if status != "interrupt":
        return fail(f"a KeyboardInterrupt at the stage boundary must be caught as interrupt, got {status}")
    # and interrupt must be in the indeterminate set that maps to unknown (never ok/pass).
    if status in ("ok", "fail"):
        return fail("interrupt must never be confused with ok/fail")
    return 0


def check_generated_arbitrary_unexpected(tmp: Path) -> int:
    """A generator that emits a file outside the expected generated set -> that
    path is generated.unexpected, overall not success, version not advanced."""
    up = tmp / "up-gx"
    down = tmp / "down-gx"
    receipt = tmp / "receipt-gx.json"
    build_upstream(up, "v1.1.0")
    build_downstream(down, "v1.0.0", gen=GEN_EXTRA, val=VAL_OK)

    proc = run_sync(down, up, receipt)
    if proc.returncode == 0:
        return fail("arbitrary generator output must fail the sync", proc)
    if version_of(down) != "v1.0.0":
        return fail(f"arbitrary generator output must NOT advance version, got {version_of(down)}", proc)
    r = read_json(receipt)
    if "gen/rogue.txt" not in r["manifest"]["generated"]["unexpected"]:
        return fail(f"rogue generator file must be listed in generated.unexpected, got {r['manifest']['generated']}", proc)
    if r["failure"]["stage"] != "generated_rebuild":
        return fail(f"failure stage should be generated_rebuild, got {r.get('failure')}", proc)
    return 0


def check_generated_missing(tmp: Path) -> int:
    """A generator that fails to (re)produce an expected generated file -> that
    path is generated.missing, sync fails, version not advanced."""
    up = tmp / "up-gm"
    down = tmp / "down-gm"
    receipt = tmp / "receipt-gm.json"
    build_upstream(up, "v1.1.0")
    build_downstream(down, "v1.0.0", gen=GEN_MISSING, val=VAL_OK)

    proc = run_sync(down, up, receipt)
    if proc.returncode == 0:
        return fail("a missing expected generated file must fail the sync", proc)
    if version_of(down) != "v1.0.0":
        return fail(f"missing generated file must NOT advance version, got {version_of(down)}", proc)
    r = read_json(receipt)
    if "gen/adapter.txt" not in r["manifest"]["generated"]["missing"]:
        return fail(f"expected generated file must be listed in generated.missing, got {r['manifest']['generated']}", proc)
    return 0


def check_generated_wrong_bytes_content_mismatch(tmp: Path) -> int:
    """An expected generated path that IS present (in actual) but whose bytes
    don't match the canonical upstream generated output -> content_mismatches,
    NEVER missing (missing is pure path-set semantics: expected - actual)."""
    up = tmp / "up-gwb"
    down = tmp / "down-gwb"
    receipt = tmp / "receipt-gwb.json"
    build_upstream(up, "v1.1.0")
    build_downstream(down, "v1.0.0", gen=GEN_WRONG_BYTES, val=VAL_OK)

    proc = run_sync(down, up, receipt)
    if proc.returncode == 0:
        return fail("wrong-bytes expected generated output must fail the sync", proc)
    if version_of(down) != "v1.0.0":
        return fail(f"wrong-bytes generated output must NOT advance version, got {version_of(down)}", proc)
    r = read_json(receipt)
    gm = r["manifest"]["generated"]
    if "gen/adapter.txt" not in gm["actual"]:
        return fail(f"the wrong-bytes path exists on disk, so it must be in generated.actual, got {gm}", proc)
    if "gen/adapter.txt" not in gm["content_mismatches"]:
        return fail(f"wrong bytes must be listed in generated.content_mismatches, got {gm}", proc)
    if "gen/adapter.txt" in gm["missing"]:
        return fail(f"a present-but-wrong-bytes path must NEVER be counted as missing, got {gm}", proc)
    if r["failure"]["stage"] != "generated_rebuild":
        return fail(f"failure stage should be generated_rebuild, got {r.get('failure')}", proc)
    return 0


def check_generated_stale_rogue_unexpected(tmp: Path) -> int:
    """A rogue generated-namespace file that already existed on disk BEFORE
    this run -- and that this run's generator never touches -- must still be
    reported as generated.unexpected. generated.actual is the full
    post-generator governed set (same classify()/generated glob rules applied
    to the complete downstream snapshot), not just this run's generator delta
    -- otherwise a pre-existing stale file is invisible and the version could
    wrongly advance (the exact P0 gap issue #35's second round closes)."""
    up = tmp / "up-gsr"
    down = tmp / "down-gsr"
    receipt = tmp / "receipt-gsr.json"
    build_upstream(up, "v1.1.0")
    build_downstream(down, "v1.0.0", gen=GEN_OK, val=VAL_OK)
    # Pre-seed a stale rogue file under the generated root BEFORE the run;
    # GEN_OK only (re)writes gen/adapter.txt and never touches/removes this one.
    write(down / "gen" / "rogue-stale.txt", "pre-existing stale generated file\n")

    proc = run_sync(down, up, receipt)
    if proc.returncode == 0:
        return fail("a pre-existing untouched rogue generated file must fail the sync", proc)
    if version_of(down) != "v1.0.0":
        return fail(f"stale rogue generated file must NOT advance version, got {version_of(down)}", proc)
    r = read_json(receipt)
    gm = r["manifest"]["generated"]
    if "gen/rogue-stale.txt" in gm.get("actual_changed", []):
        return fail(f"the rogue file was never touched by the generator this run, so it must NOT "
                    f"appear in actual_changed (the delta), got {gm}", proc)
    if "gen/rogue-stale.txt" not in gm.get("actual", []):
        return fail(f"generated.actual must be the full post-generator set, including an untouched "
                    f"pre-existing rogue file, got {gm}", proc)
    if "gen/rogue-stale.txt" not in gm["unexpected"]:
        return fail(f"pre-existing untouched rogue file must be listed in generated.unexpected, got {gm}", proc)
    if r["failure"]["stage"] != "generated_rebuild":
        return fail(f"failure stage should be generated_rebuild, got {r.get('failure')}", proc)
    # detect-and-report only: the sync must not silently delete/touch the rogue file.
    if (down / "gen" / "rogue-stale.txt").read_text() != "pre-existing stale generated file\n":
        return fail("pre-existing rogue file bytes must be left untouched by the sync")
    return 0


def _load_downstream_module(down: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, down / "scripts" / "template-sync.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _drive_main(mod, up: Path, receipt: Path) -> int:
    argv = sys.argv
    sys.argv = ["template-sync.py", "--from", str(up), "--receipt", str(receipt)]
    try:
        return mod.main()
    finally:
        sys.argv = argv


def check_commit_interrupt(tmp: Path) -> int:
    """End-to-end (in-process) commit interruption at two points: BEFORE the
    atomic replace (old version stays) and AFTER the replace (new version is
    already on disk). Both must produce an unknown, non-zero receipt whose
    committed_version / version_advanced match the ACTUAL on-disk state — no
    hard-coded version_kept=old, no fake rollback."""
    # Case A: interrupt before replace -> disk keeps old version.
    upA, downA, recA = tmp / "up-ciA", tmp / "down-ciA", tmp / "rec-ciA.json"
    build_upstream(upA, "v1.1.0")
    build_downstream(downA, "v1.0.0", gen=GEN_OK, val=VAL_OK)
    modA = _load_downstream_module(downA, "ts_ciA")
    real_a = modA.os.replace
    fired_a = {"v": False}

    def before_replace(src: object, dst: object) -> None:
        if not fired_a["v"]:
            fired_a["v"] = True
            raise KeyboardInterrupt
        return real_a(src, dst)  # later writes (receipt) proceed normally

    modA.os.replace = before_replace
    try:
        rcA = _drive_main(modA, upA, recA)
    except KeyboardInterrupt:
        return fail("before-replace interrupt must be caught inside main, not propagate")
    finally:
        modA.os.replace = real_a
    if rcA == 0:
        return fail("commit interrupt must exit non-zero")
    if version_of(downA) != "v1.0.0":
        return fail(f"before-replace interrupt must leave old version on disk, got {version_of(downA)}")
    rA = read_json(recA)
    if rA["result"] != "unknown" or rA["stages"]["commit_version"] != "interrupt":
        return fail(f"before-replace receipt must be unknown/interrupt, got {rA['result']}/{rA['stages']}")
    if rA["committed_version"] != "v1.0.0" or rA["version_advanced"]:
        return fail(f"before-replace receipt must reflect version NOT advanced, got {rA}")
    if rA["failure"]["actual_version"] != "v1.0.0":
        return fail(f"before-replace actual_version must match disk, got {rA['failure']}")

    # Case B: interrupt after replace -> disk already shows the new version.
    upB, downB, recB = tmp / "up-ciB", tmp / "down-ciB", tmp / "rec-ciB.json"
    build_upstream(upB, "v1.1.0")
    build_downstream(downB, "v1.0.0", gen=GEN_OK, val=VAL_OK)
    modB = _load_downstream_module(downB, "ts_ciB")
    real_b = modB.os.replace
    fired_b = {"v": False}

    def after_replace(src: object, dst: object) -> None:
        real_b(src, dst)
        if not fired_b["v"]:
            fired_b["v"] = True
            raise KeyboardInterrupt

    modB.os.replace = after_replace
    try:
        rcB = _drive_main(modB, upB, recB)
    except KeyboardInterrupt:
        return fail("after-replace interrupt must be caught inside main, not propagate")
    finally:
        modB.os.replace = real_b
    if rcB == 0:
        return fail("after-replace interrupt must still exit non-zero (unknown)")
    if version_of(downB) != "v1.1.0":
        return fail(f"after-replace interrupt: disk must show advanced version, got {version_of(downB)}")
    rB = read_json(recB)
    if rB["result"] != "unknown":
        return fail(f"after-replace receipt must be unknown, got {rB['result']}")
    if rB["committed_version"] != "v1.1.0" or not rB["version_advanced"]:
        return fail(f"after-replace receipt must honestly report advanced under interrupt, got {rB}")
    if rB["failure"]["version_kept"] is not None:
        return fail("after-replace must NOT claim version_kept=old (no fake rollback)")
    return 0


def check_timeout_unknown(tmp: Path) -> int:
    """A validator that never returns within --timeout must yield result=unknown
    (never pass), keep the old version, and exit non-zero (issue #35: timeout /
    interrupt / unknown must not be shown as pass)."""
    up = tmp / "up-to"
    down = tmp / "down-to"
    receipt = tmp / "receipt-to.json"
    build_upstream(up, "v1.1.0")
    build_downstream(down, "v1.0.0", gen=GEN_OK, val=VAL_SLOW)

    proc = run_sync(down, up, receipt, "--timeout", "1")
    if proc.returncode == 0:
        return fail("a validator timeout must make the process exit non-zero", proc)
    if version_of(down) != "v1.0.0":
        return fail(f"a validator timeout must NOT advance version, got {version_of(down)}", proc)
    r = read_json(receipt)
    if r["result"] != "unknown":
        return fail(f"timeout must be recorded as unknown, never pass, got {r['result']}", proc)
    if r["stages"]["validate"] != "timeout" or r["stages"]["commit_version"] != "skipped":
        return fail(f"stages should show validate=timeout, commit skipped, got {r['stages']}", proc)
    if not r["failure"] or r["failure"]["stage"] != "validate":
        return fail(f"failure block should name validate, got {r.get('failure')}", proc)
    return 0


def check_major_gate(tmp: Path) -> int:
    up = tmp / "up-mj"
    down = tmp / "down-mj"
    receipt = tmp / "receipt-mj.json"
    build_upstream(up, "v2.0.0")
    build_downstream(down, "v1.0.0", gen=GEN_OK, val=VAL_OK)

    blocked = run_sync(down, up, receipt)
    if blocked.returncode != 2:
        return fail("MAJOR without --allow-major should exit 2", blocked)
    if version_of(down) != "v1.0.0":
        return fail("MAJOR gate must not advance version", blocked)
    if receipt.exists():
        return fail("MAJOR gate is a strict pre-write no-op: no receipt should be written", blocked)
    if (down / "fw" / "tool.txt").read_text() != "old-fw\n":
        return fail("MAJOR gate must not touch any files before the STOP")

    allowed = run_sync(down, up, receipt, "--allow-major")
    if allowed.returncode != 0:
        return fail("MAJOR with --allow-major should proceed and exit 0", allowed)
    if version_of(down) != "v2.0.0":
        return fail(f"MAJOR with --allow-major should advance to v2.0.0, got {version_of(down)}", allowed)
    return 0


def check_atomic_write_fail(tmp: Path) -> int:
    """In-process: os.replace failure during the version write leaves the old,
    parseable `.template.toml` and no orphan temp file (issue #35 acceptance:
    a version-write interruption never leaves a half row / unparseable TOML)."""
    spec = importlib.util.spec_from_file_location("template_sync_mod", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    # Register before exec so @dataclass annotation resolution can find the module.
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)

    target = tmp / "atomic" / ".template.toml"
    write(target, '[template]\norigin = "acme/downstream"\nversion = "v1.0.0"\n')
    extra = {"origin": "acme/downstream", "version": "v1.0.0"}

    orig_replace = mod.os.replace

    def boom(_a: object, _b: object) -> None:
        raise OSError("injected os.replace failure")

    mod.os.replace = boom
    try:
        raised = False
        try:
            mod.write_template_version("acme/downstream", "v1.1.0", extra, target=target)
        except OSError:
            raised = True
        if not raised:
            return fail("atomic write should surface the os.replace failure")
    finally:
        mod.os.replace = orig_replace

    parsed = tomllib.loads(target.read_text(encoding="utf-8"))
    if parsed["template"]["version"] != "v1.0.0":
        return fail(f"failed version write must keep old value, got {parsed['template']['version']}")
    leftovers = list(target.parent.glob(".template.toml.*"))
    if leftovers:
        return fail(f"failed version write must not leave an orphan temp file: {leftovers}")

    # cleanup must not delete an UNRELATED concurrent temp file in the same dir.
    other = target.parent / ".template.toml.someone-else.tmp"
    other.write_text("not mine", encoding="utf-8")
    mod.os.replace = boom
    try:
        try:
            mod.write_template_version("acme/downstream", "v1.1.0", extra, target=target)
        except OSError:
            pass
    finally:
        mod.os.replace = orig_replace
    if not other.exists():
        return fail("cleanup must only remove this call's own temp, not another writer's temp")
    other.unlink()

    # positive: a normal write replaces atomically and leaves no temp file.
    mod.write_template_version("acme/downstream", "v1.1.0", extra, target=target)
    if tomllib.loads(target.read_text(encoding="utf-8"))["template"]["version"] != "v1.1.0":
        return fail("normal atomic write should advance the version")
    if list(target.parent.glob(".template.toml.*")):
        return fail("successful atomic write should leave no temp file")
    return 0


def main() -> int:
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPO, text=True, capture_output=True, check=False
    ).stdout.strip()
    print(f"[template-sync-smoke] tested script: {SCRIPT} @ {head or 'unknown'}")
    with tempfile.TemporaryDirectory(prefix="template-sync-smoke-") as tmp_str:
        tmp = Path(tmp_str)
        for check in (
            check_happy_and_idempotent,
            check_generator_fail,
            check_validator_fail,
            check_no_verify_no_advance,
            check_dry_run_no_side_effect,
            check_root_contract_framework,
            check_dirty_upstream_source,
            check_warnings_partial,
            check_generated_arbitrary_unexpected,
            check_generated_missing,
            check_generated_wrong_bytes_content_mismatch,
            check_generated_stale_rogue_unexpected,
            check_adapter_ownership_exact_set,
            check_governance_data_gap_report,
            check_interrupt_unknown,
            check_commit_interrupt,
            check_timeout_unknown,
            check_major_gate,
            check_atomic_write_fail,
        ):
            rc = check(tmp)
            if rc != 0:
                return rc
    print("[template-sync-smoke] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
