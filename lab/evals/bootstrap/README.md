# bootstrap evals

Synthetic smoke test for `scripts/bootstrap-project.py`.

`run-bootstrap-smoke.py` materializes the **candidate commit**（`git archive HEAD`，被测 commit
hash 会打印进输出作为证据；未提交的工作区改动不在覆盖范围内，先 commit 再跑）into a fresh
throwaway Git repo (simulating a repo just derived via "Use this template" /
`gh repo create --template` / clone+reinit), then exercises the **real README path — the derived
repo runs its own copy of the script against itself (self-bootstrap, target `.`)** to assert:

- first run creates `.template.toml` with the passed `--origin` + the copy's own `VERSION`;
- second run with the same `--origin` is a confirming run: exit 0, `confirmed`, and a strict
  before/after snapshot shows `state.json` + `template-bootstrap-report.md` stay bit-for-bit
  identical while `run-log.jsonl` grows by exactly one append-only audit row with
  `content_changed: false`（两层幂等语义：state/report 内容稳定，run-log 追加式审计）;
- a run with a different `--origin` and no `--force` stops with a non-zero exit and does not
  touch `.template.toml`; the same run with `--force` overwrites and records `previous_origin`;
- inside the bootstrapped repo, `validate-governance.py --strict`,
  `check-agent-harness.py --strict`, and `sync-codex-adapters.py --check` are all green
  (Claude-side config + Codex adapters are statically self-consistent);
- (negative) a copy without `.githooks/` fails bootstrap with a non-zero exit（plan A2 要求
  必须配置 `core.hooksPath`，缺失不允许被当成 skipped 成功）;
- (negative) a target whose git remote points at the `--origin` slug（即上游模板 repo 自身的
  checkout）is refused before any mutation.
- (issue #67) `.codex/agents/**` + `.agents/skills/**` stripped from the base commit before
  `git init`，so bootstrap's own generator regenerates them correct-but-genuinely-untracked（真实
  adoption-time 场景，not a synthetic stand-in）；`validate-governance.py --strict` /
  `check-agent-harness.py --strict` / `sync-codex-adapters.py --check` 仍全绿（自动判定
  `context=downstream`）；同一 untracked fixture 显式 `--context source` 仍 fail（#61 未被全局放宽）；
  磁盘 missing/stale/unexpected 两种 context 都仍 fail；`.template.toml` 角色锚点是 symlink 或无法
  解析时，`--context auto` fail-closed 而非静默降级。

This smoke test does **not** cover the fresh-Codex-session runtime check from A5 (guidance/skill
discovery, project hook load provenance) — that requires an actual Codex CLI session against the
bootstrapped repo and cannot be scripted from inside a Claude Code subagent sandbox. See
`plans/20260712-bootstrap-adoption-proof.zh.md` A5 for the acknowledged gap and its 2026-07-13
correction (the earlier A5 runtime evidence was built from `git archive main`, not the candidate
commit; the re-run must archive from HEAD and record the tested hash).
