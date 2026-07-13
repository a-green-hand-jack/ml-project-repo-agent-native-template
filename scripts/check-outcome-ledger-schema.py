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
   quota-only 推荐；对 frozen fixture 跑两次，输出必须逐字节一致（确定性）；
   从未见过的 task_class（零条具体路线 outcome）必须 degraded=true 并回退；
   `--min-samples 0` 必须被 CLI 拒绝。
6. credential 防线：skill scripts 静态扫描，不得出现 credential 类路径字面量；
   `.gitignore` 必须覆盖 `.outcome-ledger` 明细。
7. 负向 schema 校验：以 sample fixture 的合法 decision/outcome 为底，逐个删除
   required key（含 quota_cost 子字段）、破坏 schema_version / decision_id 格式，
   validator 必须逐条拒绝；完整路线统计键必须含 provider/model/effort/role/task/tier/policy。

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
            route_stats = ol.route_stats(
                records,
                role="impl",
                task_class="bounded-implementation",
                routing_tier=2,
                policy_version=catalog["policy_version"],
            )
            expected_codex_route = (
                "codex", "gpt-5.6-terra", "medium", "impl",
                "bounded-implementation", 2, catalog["policy_version"],
            )
            if route_stats.get(expected_codex_route, {}).get("observed", 0) < 3:
                errors.append(
                    "fixture 完整路线统计异常：codex/gpt-5.6-terra@medium 的 "
                    "impl/bounded-implementation/tier2 样本不足"
                )
            if any(len(identity) != 7 for identity in route_stats):
                errors.append(
                    "outcome 统计键未按 provider+model+effort+role+task+tier+policy 隔离"
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


def _run_replay(quota_fixture: Path, ledger: Path,
                task_class: str = "bounded-implementation") -> tuple[int, str]:
    # 默认 task_class 必须在 fixture 里有足量样本：outcome 证据按
    # role+task_class+routing_tier segment 隔离，未见过的 segment 会保守 degraded。
    result = subprocess.run(
        [sys.executable, str(ROUTE_SCRIPT),
         "--quota-fixture", str(quota_fixture), "--ledger", str(ledger),
         "--role", "impl", "--tier", "2", "--task-class", task_class,
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
    # 从未见过的 task_class：该 segment 无样本，必须 degraded 并回退 quota-only。
    rc4, out4 = _run_replay(FROZEN_QUOTA, SAMPLE_LEDGER, task_class="validator-unseen-task-class")
    if rc4 != 0:
        errors.append(f"replay 在 unseen task_class 上退出码非 0（{rc4}）")
        return
    try:
        rec = json.loads(out4)["outcome_route_recommendation"]
    except (json.JSONDecodeError, KeyError) as exc:
        errors.append(f"unseen task_class replay 输出不可解析：{exc}")
        return
    if rec.get("degraded") is not True:
        errors.append("task 身份隔离失效：未见过的 task_class 应 degraded=true（不得借用他类样本）")
    elif rec.get("provider") != rec.get("baseline_provider"):
        errors.append("unseen task_class degraded 时未回退 quota-only 推荐")
    # 样本阈值不得通过 0 绕过；argparse 必须在进入推荐逻辑前拒绝。
    min_zero = subprocess.run(
        [sys.executable, str(ROUTE_SCRIPT),
         "--quota-fixture", str(FROZEN_QUOTA), "--ledger", str(SAMPLE_LEDGER),
         "--role", "impl", "--tier", "2", "--task-class", "bounded-implementation",
         "--now", REPLAY_NOW, "--min-samples", "0"],
        capture_output=True, text=True, cwd=REPO,
    )
    if min_zero.returncode != 2 or "must be >= 1" not in min_zero.stderr:
        errors.append("--min-samples 0 未被 CLI 正整数地板拒绝")


def check_negative_schema_rejection(ol, catalog) -> None:
    """负向 fixtures：逐个删除 required key / 破坏格式，校验必须 FAIL。"""
    records, _ = ol.read_ledger(SAMPLE_LEDGER)
    decision = next((r for r in records if r.get("record_type") == "decision"), None)
    outcome = next((r for r in records
                    if r.get("record_type") == "outcome" and r.get("quota_cost")), None)
    if decision is None or outcome is None:
        errors.append("sample fixture 缺少可用于负向校验的 decision/outcome 记录")
        return
    for key in ol.DECISION_REQUIRED_KEYS:
        mutated = {k: v for k, v in decision.items() if k != key}
        if not ol.validate_decision(mutated, catalog):
            errors.append(f"负向校验失效：decision 删除 {key} 未被拒绝")
    for key in ol.OUTCOME_REQUIRED_KEYS:
        mutated = {k: v for k, v in outcome.items() if k != key}
        if not ol.validate_outcome(mutated, catalog):
            errors.append(f"负向校验失效：outcome 删除 {key} 未被拒绝")
    for key in ol.QUOTA_COST_REQUIRED_KEYS:
        mutated = dict(outcome)
        mutated["quota_cost"] = {k: v for k, v in outcome["quota_cost"].items() if k != key}
        if not ol.validate_outcome(mutated, catalog):
            errors.append(f"负向校验失效：quota_cost 删除 {key} 未被拒绝（残缺 quota_cost 应 FAIL）")
    if not ol.validate_decision({**decision, "schema_version": 999}, catalog):
        errors.append("负向校验失效：decision schema_version 漂移未被拒绝")
    if not ol.validate_outcome({**outcome, "schema_version": 999}, catalog):
        errors.append("负向校验失效：outcome schema_version 漂移未被拒绝")
    # 类型混淆：Python 里 True == 1 == 1.0，schema_version 只认精确 int。
    for bad in (True, 1.0, "1"):
        if not ol.validate_decision({**decision, "schema_version": bad}, catalog):
            errors.append(f"负向校验失效：decision schema_version={bad!r}（类型混淆）未被拒绝")
        if not ol.validate_outcome({**outcome, "schema_version": bad}, catalog):
            errors.append(f"负向校验失效：outcome schema_version={bad!r}（类型混淆）未被拒绝")
    if not ol.validate_decision({**decision, "decision_id": "not-a-valid-id"}, catalog):
        errors.append("负向校验失效：decision_id 非 d-<id> 格式未被拒绝")
    if not ol.validate_records([decision, dict(decision)], catalog):
        errors.append("负向校验失效：重复 decision_id 未被拒绝")


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
    for script in (SKILL / "scripts" / "outcome_ledger.py",
                   SKILL / "scripts" / "outcome_route.py"):
        if "--allow-test-dir" in script.read_text(encoding="utf-8"):
            errors.append(f"生产 CLI 仍暴露任意测试写目录逃生口：{script.name}")


def main() -> int:
    strict = "--strict" in sys.argv
    ol = load_outcome_ledger_module()
    catalog = check_catalog(ol)
    if catalog is not None:
        check_fixture_ledgers(ol, catalog)
        check_real_ledger(ol, catalog)
        check_negative_schema_rejection(ol, catalog)
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
