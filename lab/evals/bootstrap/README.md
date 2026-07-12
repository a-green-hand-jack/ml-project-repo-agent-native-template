# bootstrap evals

Synthetic smoke test for `scripts/bootstrap-project.py`.

`run-bootstrap-smoke.py` materializes this template's own tracked tree into a fresh
throwaway Git repo (simulating a repo just derived via "Use this template" /
`gh repo create --template` / clone+reinit), then runs `bootstrap-project.py` against it
to assert:

- first run creates `.template.toml` with the passed `--origin` + this template's `VERSION`;
- second run with the same `--origin` is idempotent (`confirmed`, not `created`, exit 0);
- a run with a different `--origin` and no `--force` stops with a non-zero exit and does not
  touch `.template.toml`;
- the same run with `--force` overwrites and records `previous_origin`;
- inside the bootstrapped repo, `validate-governance.py --strict`,
  `check-agent-harness.py --strict`, and `sync-codex-adapters.py --check` are all green
  (Claude-side config + Codex adapters are statically self-consistent).

This smoke test does **not** cover the fresh-Codex-session runtime check from A5 (guidance/skill
discovery, project hook load provenance) — that requires an actual Codex CLI session against the
bootstrapped repo and cannot be scripted from inside a Claude Code subagent sandbox. See
`plans/20260712-bootstrap-adoption-proof.zh.md` A5 for the acknowledged gap.
