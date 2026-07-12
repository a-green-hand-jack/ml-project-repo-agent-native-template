#!/usr/bin/env python3
"""outcome ledger / routing fixture / fallback 行为检查（只读）。

对应 doctrine：`.agent/model-routing-policy.md`（outcome-aware 整合）与
`plans/20260712-outcome-aware-routing.zh.md`。校验内容：

1. 冻结 model catalog 存在、可解析、含 policy_version / providers 词表。
2. fixture ledger（sample + 变体）逐条通过 schema 校验：字段完整、枚举合法、
   decision/outcome 生命周期不混淆（pending 不携带结果、observed 必须有观测
   时间与证据来源、outcome 必须指向已知 decision）。
3. provider/model/effort 词表不漂移为 Claude-only：取值不越出带 policy_version
   的 catalog；且 sample fixture 中至少一条 Codex 生态 decision 记录。
4. 真实 ledger（`.outcome-ledger/ledger.jsonl`，若存在）同样通过 schema 校验。
5. fallback 行为：对 stale quota fixture 跑 replay，必须 degraded=true 并回退
   quota-only 推荐；对 frozen fixture 跑两次，输出必须逐字节一致（确定性）。
6. credential 防线：skill scripts 静态扫描，不得出现 credential 类路径字面量；
   `.gitignore` 必须覆盖 `.outcome-ledger` 明细。

校验逻辑经 importlib 复用 skill 内 `outcome_ledger.py`（同
`check-adoption-integrity.py` 复用 adopt 脚本的先例），避免两份 schema 漂移。

无第三方依赖。退出码 0 = 通过，1 = 失败；`--strict` 让 warning 也算失败。
用法：python scripts/check-outcome-ledger-schema.py [--strict]
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKILL = REPO / ".claude" / "skills" / "coding-agent-quota"
FIXTURES = SKILL / "fixtures" / "outcome"
CATALOG = FIXTURES / "model-catalog.v1.json"
SAMPLE_LEDGER = FIXTURES / "outcome-ledger.sample.jsonl"
VARIANT_LEDGERS = [FIXTURES / "outcome-ledger.codex-degraded.jsonl"]
FROZEN_QUOTA = FIXTURES / "quota-snapshot.frozen.json"
STALE_QUOTA = FIXTURES / "quota-snapshot.stale.json"
REAL_LEDGER = SKILL / ".outcome-ledger" / "ledger.jsonl"
ROUTE_SCRIPT = SKILL / "scripts" / "outcome_route.py"
# 与 fixture 冻结时间对齐的 replay 时刻（frozen 新鲜、stale 过期）。
REPLAY_NOW = "2026-07-12T08:30:00Z"
# credential 类路径字面量：skill 脚本里出现即报错（只读扫描，不打开这些路径）。
CREDENTIAL_TOKENS = (
    "auth.json", ".aws/credentials", ".netrc", "id_rsa",
    "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "access_token",
)

errors: list[str] = []
warnings: list[str] = []


def load_outcome_ledger_module():
    spec = importlib.util.spec_from_file_location(
        "outcome_ledger", SKILL / "scripts" / "outcome_ledger.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def check_catalog(ol) -> dict | None:
    if not CATALOG.exists():
        errors.append(f"缺少冻结 model catalog：{CATALOG.relative_to(REPO)}")
        return None
    try:
        catalog = ol.load_catalog(CATALOG)
    except (ValueError, json.JSONDecodeError) as exc:
        errors.append(f"model catalog 不合法：{exc}")
        return None
    for provider, entry in catalog["providers"].items():
        for key in ("models", "effort_vocab", "tier_model", "tier_effort"):
            if not entry.get(key):
                errors.append(f"catalog providers.{provider} 缺 {key}")
    if "xhigh" in (catalog["providers"].get("codex", {}).get("effort_vocab") or []):
        errors.append(
            "catalog codex effort_vocab 含未对账合成值 'xhigh'（应记 routing_tier，"
            "effort 只收 provider 原生值，见 plan doc Child A）"
        )
    return catalog


def check_fixture_ledgers(ol, catalog) -> None:
    for ledger in [SAMPLE_LEDGER, *VARIANT_LEDGERS]:
        if not ledger.exists():
            errors.append(f"缺少 fixture ledger：{ledger.relative_to(REPO)}")
            continue
        records, parse_errs = ol.read_ledger(ledger)
        errs = parse_errs + ol.validate_records(records, catalog)
        for err in errs:
            errors.append(f"{ledger.name}: {err}")
        if ledger == SAMPLE_LEDGER:
            codex_decisions = [
                r for r in records
                if r.get("record_type") == "decision" and r.get("provider") == "codex"
            ]
            if not codex_decisions:
                errors.append(
                    "fixture 无任何 Codex 生态 decision 记录——跨 provider schema "
                    "退化成 Claude-only（plan doc Child H 要求至少一条）"
                )
            pending = [
                r for r in records if r.get("record_type") == "decision"
                and r.get("decision_id") not in {
                    o.get("decision_id") for o in records if o.get("record_type") == "outcome"
                }
            ]
            if not pending:
                warnings.append("sample fixture 建议保留至少一条 pending decision（生命周期示例）")


def check_real_ledger(ol, catalog) -> None:
    if not REAL_LEDGER.exists():
        return
    records, parse_errs = ol.read_ledger(REAL_LEDGER)
    for err in parse_errs + ol.validate_records(records, catalog):
        errors.append(f".outcome-ledger/ledger.jsonl: {err}")


def _run_replay(quota_fixture: Path, ledger: Path) -> tuple[int, str]:
    result = subprocess.run(
        [sys.executable, str(ROUTE_SCRIPT),
         "--quota-fixture", str(quota_fixture), "--ledger", str(ledger),
         "--role", "impl", "--tier", "2", "--task-class", "validator-replay",
         "--now", REPLAY_NOW],
        capture_output=True, text=True, cwd=REPO,
    )
    return result.returncode, result.stdout


def check_fallback_and_determinism() -> None:
    if not (ROUTE_SCRIPT.exists() and FROZEN_QUOTA.exists() and STALE_QUOTA.exists()
            and SAMPLE_LEDGER.exists()):
        errors.append("replay 行为检查所需脚本/fixture 不齐，无法验证 fallback 与确定性")
        return
    rc1, out1 = _run_replay(FROZEN_QUOTA, SAMPLE_LEDGER)
    rc2, out2 = _run_replay(FROZEN_QUOTA, SAMPLE_LEDGER)
    if rc1 != 0 or rc2 != 0:
        errors.append(f"replay 在 frozen fixture 上退出码非 0（{rc1}/{rc2}）")
        return
    if out1 != out2:
        errors.append("replay 不确定：同一冻结 fixture 两次输出不一致")
    else:
        try:
            rec = json.loads(out1)["outcome_route_recommendation"]
            if rec.get("degraded") is not False:
                errors.append("frozen fixture 不应触发 degraded（fixture 或阈值漂移）")
        except (json.JSONDecodeError, KeyError) as exc:
            errors.append(f"replay 输出不可解析：{exc}")
    rc3, out3 = _run_replay(STALE_QUOTA, SAMPLE_LEDGER)
    if rc3 != 0:
        errors.append(f"replay 在 stale fixture 上退出码非 0（{rc3}）")
        return
    try:
        rec = json.loads(out3)["outcome_route_recommendation"]
    except (json.JSONDecodeError, KeyError) as exc:
        errors.append(f"stale replay 输出不可解析：{exc}")
        return
    if rec.get("degraded") is not True:
        errors.append("fallback 未在过期数据场景下触发：stale fixture 应 degraded=true")
    elif rec.get("provider") != rec.get("baseline_provider"):
        errors.append("degraded 时未回退 quota-only 推荐（provider != baseline_provider）")


def check_credentials_and_gitignore() -> None:
    for script in sorted((SKILL / "scripts").glob("*.py")):
        text = script.read_text(encoding="utf-8", errors="replace")
        for token in CREDENTIAL_TOKENS:
            if token in text:
                errors.append(
                    f"skill 脚本出现 credential 类路径字面量：{script.name} 含 {token!r}"
                )
    gitignore = REPO / ".gitignore"
    if not gitignore.exists() or ".outcome-ledger" not in gitignore.read_text(encoding="utf-8"):
        errors.append(".gitignore 未覆盖 .outcome-ledger 明细（决策：repo 内 gitignored 目录）")


def main() -> int:
    strict = "--strict" in sys.argv
    ol = load_outcome_ledger_module()
    catalog = check_catalog(ol)
    if catalog is not None:
        check_fixture_ledgers(ol, catalog)
        check_real_ledger(ol, catalog)
    check_fallback_and_determinism()
    check_credentials_and_gitignore()

    for warning in warnings:
        print(f"WARN  {warning}")
    for error in errors:
        print(f"ERROR {error}")
    n_e, n_w = len(errors), len(warnings)
    ok = not n_e and not (strict and n_w)
    print(f"[check-outcome-ledger-schema] {'OK' if ok else 'FAIL'} — {n_e} error(s), {n_w} warning(s)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
