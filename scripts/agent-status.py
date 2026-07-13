#!/usr/bin/env python3
"""agent-status —— 只读 list/status：现在有哪些 agent、在做什么、状态如何、心跳新鲜度。

数据源（见 `.agent/multi-agent-control-plane.md`，issue #14）：
- `memory/agents/<name>.yaml` —— 状态明细真相源（task/owned/forbidden/heartbeat/...）；
- `memory/agents-roster.md` —— spawn skill 维护的花名册总览（name↔paseo-id↔worktree）；
- 可选 `paseo ls --json` —— roster 里登记的 paseo-id 当前是否还活着（缺 Paseo 优雅降级，
  不 raise——沿用 spawn skill「非 Paseo 表面退回」的兜底策略）。

staleness：TTL 30 分钟无心跳 → stale（human 拍板 2026-07-12），判定复用 agent-state.py。
runtime-neutral：纯 python，Claude / Codex 等价调用；无写副作用（本脚本绝不落盘）。

用法：
  python scripts/agent-status.py [--json] [--root R] [--no-paseo]
  python scripts/agent-status.py --self-test
退出码恒 0（查询工具；--self-test 失败时非 0）。
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent


def _load_agent_state():
    spec = importlib.util.spec_from_file_location("agent_state", SCRIPTS_DIR / "agent-state.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


AS = _load_agent_state()


# ---------------------------------------------------------------- roster 解析

def parse_roster(root: Path) -> list[dict]:
    """解析 `memory/agents-roster.md` 数据行（容忍新旧列数：state 列可缺）。"""
    roster = Path(root) / "memory" / "agents-roster.md"
    rows: list[dict] = []
    if not roster.is_file():
        return rows
    try:
        text = roster.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return rows
    for line in text.splitlines():
        s = line.strip()
        if not s.startswith("|") or s.startswith("| ---") or s.startswith("| name "):
            continue
        cols = [c.replace("\x00", "|").strip() for c in s.strip("|").replace("\\|", "\x00").split("|")]
        if len(cols) < 5:
            continue
        rows.append({
            "name": cols[0],
            "doing": cols[1] if len(cols) > 1 else "-",
            "worktree_label": cols[3] if len(cols) > 3 else "-",
            "paseo_id": cols[4] if len(cols) > 4 else "-",
            "roster_status": cols[5] if len(cols) > 5 else "-",
            "state_ref": cols[7] if len(cols) > 7 else "-",
        })
    return rows


# ---------------------------------------------------------------- paseo presence（可选）

def paseo_live_ids() -> set[str] | None:
    """`paseo ls --json` 里活着的 agent id 集合；不可用返回 None（降级为纯 repo 视图）。"""
    if not shutil.which("paseo"):
        return None
    try:
        out = subprocess.run(["paseo", "ls", "--json"], capture_output=True, text=True, timeout=10)
        if out.returncode != 0:
            return None
        data = json.loads(out.stdout)
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError, ValueError):
        return None
    ids: set[str] = set()

    def collect(obj) -> None:
        if isinstance(obj, dict):
            val = obj.get("id")
            if isinstance(val, str):
                ids.add(val)
            for v in obj.values():
                collect(v)
        elif isinstance(obj, list):
            for v in obj:
                collect(v)

    collect(data)
    return ids


# ---------------------------------------------------------------- 汇总

def _unread_count(root: Path, state: dict) -> int:
    ref = state.get("inbox_ref")
    if not ref:
        return 0
    inbox = Path(root) / str(ref)
    if not inbox.is_file():
        return 0
    try:
        return inbox.read_text(encoding="utf-8", errors="replace").count("- read: no")
    except OSError:
        return 0


def _age_label(minutes: float | None) -> str:
    if minutes is None:
        return "无心跳"
    if minutes < 1:
        return "<1m"
    if minutes < 60:
        return f"{int(minutes)}m"
    return f"{minutes / 60:.1f}h"


def collect_status(root: Path, use_paseo: bool = True, now: float | None = None) -> list[dict]:
    states = AS.load_states(root)
    roster_rows = {r["name"]: r for r in parse_roster(root)}
    live_ids = paseo_live_ids() if use_paseo else None

    entries: list[dict] = []
    for name in sorted(set(states) | set(roster_rows)):
        state = states.get(name, {})
        row = roster_rows.get(name, {})
        age = AS.heartbeat_age_minutes(state, now) if state else None
        pid = str(state.get("paseo_id") or row.get("paseo_id") or "-")
        if live_ids is None:
            presence = "unknown(no-paseo)"
        elif pid in ("", "-"):
            presence = "-"
        else:
            presence = "live" if pid in live_ids else "gone"
        entries.append({
            "name": name,
            "status": AS.effective_status(state, now) if state else "unregistered(roster-only)",
            "stored_status": state.get("status") if state else None,
            "heartbeat_age_minutes": round(age, 1) if age is not None else None,
            "heartbeat": state.get("heartbeat"),
            "task": state.get("task") or row.get("doing") or "-",
            "worktree": state.get("worktree") or row.get("worktree_label") or "-",
            "branch": state.get("branch"),
            "paseo_id": pid,
            "paseo_presence": presence,
            "unread_inbox": _unread_count(root, state) if state else 0,
            "owned_paths": state.get("owned_paths") or [],
            "state_file": state.get("_path"),
        })
    return entries


def render_table(entries: list[dict]) -> str:
    if not entries:
        return "（无已登记 agent：memory/agents/ 与 memory/agents-roster.md 均为空）"
    headers = ("name", "status", "heartbeat", "unread", "paseo", "task", "worktree")
    rows = [headers]
    for e in entries:
        rows.append((
            e["name"], e["status"], _age_label(e["heartbeat_age_minutes"]),
            str(e["unread_inbox"]), e["paseo_presence"],
            str(e["task"])[:40], Path(str(e["worktree"])).name if e["worktree"] else "-",
        ))
    widths = [max(len(str(r[i])) for r in rows) for i in range(len(headers))]
    lines = ["  ".join(str(c).ljust(widths[i]) for i, c in enumerate(r)) for r in rows]
    lines.insert(1, "  ".join("-" * w for w in widths))
    return "\n".join(lines)


# ---------------------------------------------------------------- self-test

def _self_test() -> int:
    failures: list[str] = []

    def check(cond: bool, label: str) -> None:
        print(("  ok    " if cond else "  FAIL  ") + label)
        if not cond:
            failures.append(label)

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        now = time.time()
        AS.register(root, "干将·改·alpha", task="实现 A", owned=["src/a/"], now=now)
        AS.register(root, "师爷·审·beta", task="审查 B", now=now - 45 * 60)  # 45min 无心跳
        AS.register(root, "都督·统·gamma", task="收尾", now=now)
        AS.set_status(root, "都督·统·gamma", "done")
        # roster-only agent（有花名册行、无状态文件）
        (root / "memory").mkdir(exist_ok=True)
        (root / "memory" / "agents-roster.md").write_text(
            "| name | 做什么 | focus | branch/worktree | paseo-id | status | updated |\n"
            "| --- | --- | --- | --- | --- | --- | --- |\n"
            "| 斥候·查·roster-only | 斥候·查 | roster-only | b (wt) | pid-123 | active | 2026-07-12 |\n",
            encoding="utf-8",
        )
        entries = {e["name"]: e for e in collect_status(root, use_paseo=False, now=now)}
        check(len(entries) == 4, "roster ∪ yaml 全量列出（4 个）")
        check(entries["干将·改·alpha"]["status"] == "active", "TTL 内 → active")
        check(entries["师爷·审·beta"]["status"] == "stale", "45m 无心跳 → stale")
        check(entries["都督·统·gamma"]["status"] == "done", "done 终态")
        check(entries["斥候·查·roster-only"]["status"] == "unregistered(roster-only)",
              "roster-only 行可见且标注未登记状态文件")
        check(entries["斥候·查·roster-only"]["paseo_id"] == "pid-123", "roster paseo-id 透传")
        check(entries["干将·改·alpha"]["paseo_presence"] == "unknown(no-paseo)",
              "无 Paseo → 降级 unknown，不 raise")
        table = render_table(list(entries.values()))
        check("stale" in table and "干将·改·alpha" in table, "表格渲染含状态")
        # 无心跳字段的手写状态文件 → stale（保守）
        (root / "memory" / "agents" / "手写·无·心跳.yaml").write_text(
            'name: "手写·无·心跳"\nstatus: "active"\n', encoding="utf-8")
        entries2 = {e["name"]: e for e in collect_status(root, use_paseo=False, now=now)}
        check(entries2["手写·无·心跳"]["status"] == "stale", "无心跳字段 → stale")
        check(collect_status(Path(td) / "empty", use_paseo=False) == [], "空 repo → 空列表不 raise")

    print(f"\nagent-status self-test：{'全部通过' if not failures else f'{len(failures)} 项失败'}")
    return 1 if failures else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--root", default=None)
    ap.add_argument("--no-paseo", action="store_true", help="跳过 paseo ls 实时校验（纯 repo 视图）")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return _self_test()
    root = Path(args.root) if args.root else AS.default_root()
    entries = collect_status(root, use_paseo=not args.no_paseo)
    if args.json:
        print(json.dumps(entries, ensure_ascii=False, indent=2))
    else:
        print(f"control-plane root: {root}")
        print(render_table(entries))
    return 0


if __name__ == "__main__":
    sys.exit(main())
