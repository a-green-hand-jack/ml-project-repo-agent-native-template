#!/usr/bin/env python3
"""检查 agent harness 结构是否自洽（防漂移 / 防膨胀门禁）。

检查项：
1. 必需的顶层入口文件与目录存在。
2. 根污染：根目录只出现白名单条目（未知条目告警）。
3. 导航四件套：重要目录有 README/AGENTS/CLAUDE/ANATOMY。
4. 能力索引：.claude/agents/*.md 与 .claude/skills/*/SKILL.md 有 frontmatter（name/description）。
5. settings.json 可解析、含 permissions，且 hooks 引用的脚本存在。

无第三方依赖。退出码 0 = 通过（可含 warning），1 = 有 error。
用法：python scripts/check-agent-harness.py [--strict]
--strict 把 warning 也当作失败。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# 必需的顶层条目。
REQUIRED_TOP = [
    "README.md", "PROJECT.md", "AGENTS.md", "CLAUDE.md", "ANATOMY.md",
    ".agent", ".claude", "lab", "memory", "scripts",
]

# 根目录白名单（其余视为潜在污染 -> warning）。
ROOT_WHITELIST = {
    "README.md", "PROJECT.md", "DECISIONS.md", "DESIGN.md", "AGENTS.md", "CLAUDE.md",
    "ANATOMY.md", ".gitignore", ".github", ".agent", ".claude", "human",
    "lab", "memory", "deliverables", "scripts", "plans", ".reference-docs",
    # 常见工程文件（允许存在，不算污染）
    "LICENSE", "pyproject.toml", "uv.lock", ".python-version",
    ".pre-commit-config.yaml", "Makefile",
}
# 工具 / VCS 产物：忽略，不告警。
ROOT_IGNORE = {
    ".git", ".venv", "__pycache__", ".DS_Store", ".ruff_cache",
    ".mypy_cache", ".pytest_cache", ".idea", ".vscode", ".env",
}

# 需要完整四件套的目录。
QUARTET_DIRS = [
    "human", ".claude", "lab", "lab/code", "lab/code/src",
    "lab/infra", "lab/research", "lab/artifacts", "memory",
    "deliverables", "scripts",
]
QUARTET_FILES = ["README.md", "AGENTS.md", "CLAUDE.md", "ANATOMY.md"]

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)

errors: list[str] = []
warnings: list[str] = []


def err(msg: str) -> None:
    errors.append(msg)


def warn(msg: str) -> None:
    warnings.append(msg)


def check_required_top() -> None:
    for name in REQUIRED_TOP:
        if not (REPO / name).exists():
            err(f"缺少必需顶层条目：{name}")


def check_root_pollution() -> None:
    for entry in sorted(REPO.iterdir()):
        name = entry.name
        if name in ROOT_IGNORE or name in ROOT_WHITELIST:
            continue
        warn(f"根目录疑似污染（不在白名单）：{name} —— 长文/报告/实验记录不应堆在 root")


def check_quartets() -> None:
    for d in QUARTET_DIRS:
        base = REPO / d
        if not base.is_dir():
            err(f"四件套目录不存在：{d}/")
            continue
        for f in QUARTET_FILES:
            if not (base / f).exists():
                err(f"缺少导航文件：{d}/{f}")
    # .agent 用 AGENTS.md 作 doctrine 索引（不要求 ANATOMY）。
    if not (REPO / ".agent" / "AGENTS.md").exists():
        err("缺少 .agent/AGENTS.md（doctrine 索引）")


def _frontmatter(path: Path) -> dict[str, str] | None:
    m = FRONTMATTER_RE.search(path.read_text(encoding="utf-8", errors="replace"))
    if not m:
        return None
    fields: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line.startswith((" ", "\t", "-")):
            k, _, v = line.partition(":")
            fields[k.strip()] = v.strip()
    return fields


def check_capabilities() -> None:
    agents_dir = REPO / ".claude" / "agents"
    if agents_dir.is_dir():
        agent_files = list(agents_dir.glob("*.md"))
        if not agent_files:
            warn(".claude/agents/ 为空：没有 repo-local subagent")
        for f in agent_files:
            fm = _frontmatter(f)
            if fm is None:
                err(f"subagent 缺少 frontmatter：{f.relative_to(REPO)}")
            elif "name" not in fm or "description" not in fm:
                err(f"subagent frontmatter 缺 name/description：{f.relative_to(REPO)}")
    skills_dir = REPO / ".claude" / "skills"
    if skills_dir.is_dir():
        for skill in sorted(p for p in skills_dir.iterdir() if p.is_dir()):
            sk = skill / "SKILL.md"
            if not sk.exists():
                err(f"skill 缺少 SKILL.md：{skill.relative_to(REPO)}/")
                continue
            fm = _frontmatter(sk)
            if fm is None or "name" not in fm or "description" not in fm:
                err(f"SKILL.md frontmatter 缺 name/description：{sk.relative_to(REPO)}")


def check_settings() -> None:
    settings = REPO / ".claude" / "settings.json"
    if not settings.exists():
        err("缺少 .claude/settings.json")
        return
    try:
        data = json.loads(settings.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        err(f".claude/settings.json 解析失败：{e}")
        return
    if "permissions" not in data:
        warn(".claude/settings.json 无 permissions 段")
    for event, groups in (data.get("hooks") or {}).items():
        for group in groups:
            for hook in group.get("hooks", []):
                cmd = hook.get("command", "")
                m = re.search(r"\.claude/hooks/[\w./-]+\.py", cmd)
                if m and not (REPO / m.group(0)).exists():
                    err(f"hook 脚本不存在：{m.group(0)}（{event}）")


def main() -> int:
    strict = "--strict" in sys.argv
    check_required_top()
    check_root_pollution()
    check_quartets()
    check_capabilities()
    check_settings()

    for w in warnings:
        print(f"WARN  {w}")
    for e in errors:
        print(f"ERROR {e}")
    n_e, n_w = len(errors), len(warnings)
    status = "FAIL" if (n_e or (strict and n_w)) else "OK"
    print(f"[check-agent-harness] {status} — {n_e} error(s), {n_w} warning(s)")
    return 1 if status == "FAIL" else 0


if __name__ == "__main__":
    sys.exit(main())
