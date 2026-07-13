---
name: coding-agent-quota
description: Read local Codex and Claude Code quota/rate-limit snapshots and produce routing evidence for agent work allocation, plus outcome-aware routing on top of quota (historical success/rework/latency evidence, deterministic offline replay, degraded fallback, outcome ledger with decision_id traceability). Use when deciding which coding agent/provider/model to use, balancing Codex vs Claude Code load, checking remaining 5-hour/session and weekly quota, estimating routing capacity before launching subagents, comparing candidate routes on quota + outcome evidence, recording route decisions/outcomes, or preparing cross-provider experiments with frozen provider/model policy.
---

> Codex adapter: generated from `.claude/skills/coding-agent-quota/SKILL.md`. Do not edit this copy by hand; run `python scripts/sync-codex-adapters.py`.

# coding-agent-quota

Use this skill before routing meaningful work between Codex and Claude Code when quota, reset time, provider load, cost-control, or historical task outcomes matter. It covers two layers: (1) quota snapshot + quota-only recommendation (`read_agent_quota.py`, unchanged), and (2) an additive outcome-aware layer (`outcome_route.py` + `outcome_ledger.py`) that compares candidate routes on quota + outcome evidence and falls back conservatively when data is missing or stale.

## Quick Start

Run the bundled script from the repo root:

```bash
python .claude/skills/coding-agent-quota/scripts/read_agent_quota.py --format table
python .claude/skills/coding-agent-quota/scripts/read_agent_quota.py --format json
python .claude/skills/coding-agent-quota/scripts/read_agent_quota.py --role impl --tier 2 --format json
```

Prefer JSON when another agent or orchestrator will consume the result. Prefer table output for human handoff.

## Evidence Rules

- Treat the script output as a snapshot, not a guarantee. Route high-risk or long-running work only after checking `captured_at` and reset times.
- Prefer provider-specific latest valid snapshots; do not require Codex and Claude to come from the same database row.
- If a provider is `unavailable` or stale, say so and route conservatively instead of inventing percentages.
- Do not read or print credential files. The script uses local usage DB/cache/session logs only.
- For subagent launch decisions, pass `--role` and `--tier` so the output includes `route_recommendation`.
- For formal transfer experiments, freeze provider, model, and policy before launch; do not switch mid-run just because a later quota snapshot changes.

## Routing Heuristic

Use quota as one signal alongside task shape:

- Infrastructure implementation, debugging, and tests: prefer Codex when current-window capacity is healthy.
- Independent safety review and architecture review: use Claude Opus only when the risk justifies the weekly quota burn.
- Routine review, docs, and low-risk checks: prefer cheaper Claude models or the provider with more remaining weekly capacity.
- Cross-provider transfer experiments: use Claude Code when the experiment requires proving transfer across providers.

When current-window remaining capacity is similar, prefer the provider with materially more weekly remaining capacity. When weekly capacity is similar, prefer the provider whose model/tooling best matches the task.

## Source Priority

The script reads:

1. `~/.claude/.search-index/usage.db`, table `api_usage_snapshots`, when present.
2. Codex JSONL session logs under `~/.codex/sessions/` and `~/.codex/archived_sessions/` as a Codex fallback.
3. `~/.paseo/orchestration-preferences.json`, when present, for role-to-provider defaults.

If both sources exist for Codex, prefer the newest valid snapshot by capture time.

## Launch Packet Fields

When routing a child agent, include these fields from JSON output in the packet:

- `providers`: current-window and weekly quota snapshot.
- `usage_velocity`: recent token/message burn proxy from the local usage DB.
- `paseo_preferences`: role defaults, or `missing` if the local file does not exist.
- `route_recommendation`: recommended provider/model/effort plus scoring notes.
- When the outcome layer was used: `outcome_decision_id` (plus a one-line `degraded` hint if
  the layer fell back). Only the id goes into the packet; the full evidence chain stays in the
  ledger and is queried by id.

## Outcome-Aware Routing (quota + outcome, no $ dimension)

Scripts (plain `python` from the repo root; works identically from Claude Code and Codex):

```bash
# Recommend a route using live quota + the local outcome ledger; record the decision:
python .claude/skills/coding-agent-quota/scripts/outcome_route.py \
    --live --role impl --tier 2 --task-class bounded-implementation --record

# Deterministic offline replay on frozen fixtures (same inputs => identical bytes):
python .claude/skills/coding-agent-quota/scripts/outcome_route.py \
    --quota-fixture .claude/skills/coding-agent-quota/fixtures/outcome/quota-snapshot.frozen.json \
    --ledger .claude/skills/coding-agent-quota/fixtures/outcome/outcome-ledger.sample.jsonl \
    --role impl --tier 2 --now 2026-07-12T08:30:00Z

# Ledger maintenance / traceability:
python .claude/skills/coding-agent-quota/scripts/outcome_ledger.py record-outcome \
    --decision-id d-xxxx --status observed --quality pass --rework 0 \
    --evidence-source "targeted tests exit 0" \
    --actual-provider codex --actual-model gpt-5.6-terra --actual-effort medium
python .claude/skills/coding-agent-quota/scripts/outcome_ledger.py show --decision-id d-xxxx
python .claude/skills/coding-agent-quota/scripts/outcome_ledger.py summary
```

Rules:

- The output adds `outcome_route_recommendation` NEXT TO the unchanged quota-only
  `route_recommendation`; existing consumers keep working as-is.
- Schema: see `schema.md`. Vocabulary (provider/model/native effort) is validated against the
  frozen, versioned catalog `fixtures/outcome/model-catalog.v1.json`, not against `model_for()`.
  `effort` holds provider-native values only (Codex knob: `-c model_reasoning_effort=<v>` per
  launch); the abstract level lives in `routing_tier`.
- Conservative fallback: stale quota snapshot, insufficient outcome evidence, or a
  parse/schema-invalid ledger sets `degraded: true` with a reason and falls back to the
  quota-only recommendation (invalid records are discarded, never fed into routing stats).
  Never dress missing/expired data up as precise numbers.
- Task-identity isolation: outcome evidence is aggregated per `role + task_class +
  routing_tier` segment, and EVERY candidate provider needs >= `--min-samples` observed
  outcomes in that exact segment; otherwise the layer degrades to quota-only (tier-3 or
  other-task samples never steer a tier-2 decision).
- Write boundary: ledger writes (`--ledger` on record commands, `--record-ledger`) are only
  accepted inside the default `.outcome-ledger/` directory or the system temp dir (tests);
  protected paths (`lab/data|runs|models`, `lab/infra/private`, `.env`) and any other
  location are rejected with a non-zero exit. Reads are unrestricted (fixtures replay).
- Cost is quota-only in this version: candidate routes are compared/sorted by `quota_cost`
  (subscription window burn, estimate). `metered_price_estimate` ($/token) is reserved and NOT
  implemented (plan decision Q6). Reports keep dimensions separate (outcome / quota_cost /
  tokens / wall-clock / expensive-route share) — no single merged score.
- Real accumulated records live in the gitignored `.outcome-ledger/` directory (append-only
  JSONL); only its README/.gitkeep are tracked. Frozen fixtures and the catalog are tracked.
- Formal routing benchmarks: freeze model pool / policy_version / budget cap / fixture version
  first via `.agent/templates/routing-benchmark-card.md`, register the card under `benchmarks/`.
- Validation gate: `python scripts/check-outcome-ledger-schema.py` (also run by
  `validate-governance.py`); targeted tests in `tests/test_outcome_routing.py`.
