"""Shared Claude/Codex agent-surface postflight checklist (plan D2c).

Both `bootstrap-project.py` (new/empty repo landing, plan A4) and
`adopt-existing-repo.py` (existing repo migration, plan B6) render the same
Claude/Codex file-presence + ground-truth-validator + human-out-of-band
checklist so the two entry points do not drift in wording or judgement.
See `plans/20260712-bootstrap-adoption-proof.zh.md` D2c.

Not a standalone CLI script (no `__main__` guard) — imported the same way
`check-adoption-integrity.py` already loads `adopt-existing-repo.py`, via
`importlib.util.spec_from_file_location` (scripts/ has no `__init__.py`
and most filenames are hyphenated, so a plain `import` across scripts
does not work). This file uses an underscore-safe name specifically so
it *could* also be imported directly if ever needed.

No third-party dependency.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any


def count_glob(target: Path, pattern: str) -> int:
    return len(list(target.glob(pattern)))


def codex_trust_item() -> dict[str, Any]:
    """Fixed, caller-independent text: Codex trust is always an out-of-band
    human prerequisite, whether the repo was just bootstrapped or adopted."""
    return {
        "id": "codex-trust",
        "status": "needs-human",
        "note": (
            "Codex 的 `.codex/config.toml` hooks 需 human 先 trust 本 repo 才加载；"
            "bootstrap/adoption 都无法代做，也没有稳定可脚本读取的 trust/provenance API "
            "可用于自动判定，因此保守标注 needs-human，不猜测已生效。"
        ),
    }


def codex_agent_boundary_item() -> dict[str, Any]:
    """Fixed, caller-independent text: Codex custom-agent adapters are a
    looser sandbox/tooling boundary than Claude's, regardless of entry point."""
    return {
        "id": "codex-agent-boundary",
        "status": "informational",
        "note": (
            "Codex custom-agent TOML 不强制 Claude 的 tools allowlist、不 pin model、"
            "sandbox_mode 只有 read-only/workspace-write 粗粒度（见 "
            "scripts/sync-codex-adapters.py 的 _sandbox_for_tools/_agent_adapter）；"
            "这是「行为边界靠自觉」而非硬隔离。"
        ),
    }


def agent_surface_checklist(
    target: Path,
    hooks_item: dict[str, Any],
    sync_codex_result: dict[str, Any],
    harness_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Machine-derived Claude/Codex loading checklist (plan A4 / B6).

    `hooks_item` is a fully-formed `human_out_of_band` entry
    (`{"id": "core-hooks-path", "status": ..., "note": ...}`) built by the
    *caller*, because how `core.hooksPath` status is obtained legitimately
    differs: bootstrap actively sets it (`git config core.hooksPath
    .githooks`), adoption only inspects the target repo's current git
    config and reports it (never sets it on adoption's behalf, plan B6).
    Only the rendered structure/wording is shared here, not the underlying
    action.

    File presence/counts here are informational display only; the
    authoritative pass/fail ground truth is `check-agent-harness.py --strict`
    (harness_result, run separately by the caller/verification step) and
    `sync-codex-adapters.py --check` (sync_codex_result), so the checklist
    text stays derived from the same validators instead of hand-duplicated
    judgment that can drift.
    """
    claude = {
        "settings_json": (target / ".claude" / "settings.json").exists(),
        "agents_md_count": count_glob(target, ".claude/agents/*.md"),
        "skills_count": count_glob(target, ".claude/skills/*/SKILL.md"),
        "commands_md_count": count_glob(target, ".claude/commands/*.md"),
        "statusline_sh": (target / ".claude" / "statusline.sh").exists(),
    }
    codex = {
        "config_toml": (target / ".codex" / "config.toml").exists(),
        "agents_toml_count": count_glob(target, ".codex/agents/*.toml"),
        "skills_count": count_glob(target, ".agents/skills/*/SKILL.md"),
    }
    ground_truth = {
        "check_agent_harness_strict": (harness_result or {}).get("status", "not-run-by-caller"),
        "sync_codex_adapters_check": sync_codex_result.get("status"),
        "note": (
            "文件就位/静态一致性的机器事实源是 check-agent-harness.py --strict 与 "
            "sync-codex-adapters.py --check；上面 claude/codex 两段计数只是辅助展示，"
            "不是独立判据（见 plan A4/B6）。这两个 validator 只能证明静态自洽，"
            "不能证明当前 Codex session 已加载 project config/hooks。"
        ),
    }
    human_out_of_band = [
        codex_trust_item(),
        hooks_item,
        codex_agent_boundary_item(),
    ]
    return {
        "claude": claude,
        "codex": codex,
        "ground_truth": ground_truth,
        "human_out_of_band": human_out_of_band,
    }
