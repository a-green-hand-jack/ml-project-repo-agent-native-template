#!/usr/bin/env python3
"""agent-state —— 多 agent 控制面的 agent 状态文件（`memory/agents/<name>.yaml`）写侧。

schema 与协议见 `.agent/multi-agent-control-plane.md`（issue #14，human 已拍板：
每 agent 一份结构化 yaml；`memory/agents-roster.md` 只做总览索引；heartbeat TTL 30 分钟）。

本脚本是状态文件格式的**唯一 owner**：`agent-status.py` / `agent-mailbox.py` /
`check-agent-conflicts.py` 经 importlib 复用这里的解析/路径/staleness 逻辑，避免多份实现漂移
（先例：`check-adoption-integrity.py` 加载 `adopt-existing-repo.py`）。

runtime-neutral：纯 python + repo 文件读写，Claude / Codex 等价调用；PyYAML 可选，
缺依赖回退受限解析器（约定：扁平 mapping + 块列表，字符串值 JSON 引号）。

状态锚定（重要）：控制面状态默认落在**主 checkout**（linked worktree 的 `.git` 文件指回
主仓库），使所有 worktree 里的 agent 共享同一份 `memory/agents/` + `memory/mailbox/`——
否则每个 worktree 各存一份、互相发现/冲突检测都失效。显式覆盖：`--root` 或
`AGENT_CONTROL_PLANE_ROOT` 环境变量（测试/多 repo 场景用）。

用法：
  python scripts/agent-state.py register "<name>" [--task T] [--owned P ...] [--forbidden P ...]
                                [--worktree PATH] [--branch B] [--paseo-id ID] [--root R]
  python scripts/agent-state.py heartbeat "<name>" [--root R]
  python scripts/agent-state.py set-status "<name>" <active|idle|blocked|done> [--root R]
  python scripts/agent-state.py show "<name>" [--root R]
  python scripts/agent-state.py --self-test
退出码 0 = 成功，1 = 失败（找不到 agent / 非法状态等）。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

STORED_STATUSES = ("active", "idle", "blocked", "done")
STALE_TTL_MINUTES = 30  # human 拍板（2026-07-12）：30 分钟无心跳 → stale
ROOT_ENV = "AGENT_CONTROL_PLANE_ROOT"
DOCTRINE = ".agent/multi-agent-control-plane.md"

# 状态文件字段顺序（写出时稳定，便于 diff）。
FIELD_ORDER = (
    "name", "task", "status", "heartbeat", "ttl_minutes", "worktree", "branch",
    "paseo_id", "owned_paths", "forbidden_paths", "inbox_ref", "outbox_ref",
)
LIST_FIELDS = ("owned_paths", "forbidden_paths")


def _now_iso(now: float | None = None) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now if now is not None else time.time()))


def _parse_iso(ts: str) -> float | None:
    try:
        import calendar

        return calendar.timegm(time.strptime(ts.strip(), "%Y-%m-%dT%H:%M:%SZ"))
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------- root 解析

def _git_toplevel(start: Path) -> Path | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=str(start), capture_output=True, text=True, timeout=5,
        )
        if out.returncode == 0 and out.stdout.strip():
            return Path(out.stdout.strip())
    except (OSError, subprocess.SubprocessError):
        pass
    return None


def control_plane_root(start: Path) -> Path:
    """从某个 checkout 根解析共享控制面根：linked worktree → 主 checkout；否则原样。
    纯文件读取（解析 `.git` 文件的 gitdir 行），不 shell out——hook 判定层也要调它。"""
    start = Path(start)
    override = os.environ.get(ROOT_ENV, "").strip()
    if override:
        return Path(override)
    gitfile = start / ".git"
    if gitfile.is_file():
        try:
            text = gitfile.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return start
        m = re.search(r"^gitdir:\s*(.+)$", text, re.MULTILINE)
        if m:
            gitdir = m.group(1).strip()
            marker = f"{os.sep}.git{os.sep}worktrees{os.sep}"
            if marker in gitdir:
                return Path(gitdir.split(marker)[0])
    return start


def default_root() -> Path:
    """CLI 默认根：env 覆盖 > 当前 cwd 所在 checkout 的主 checkout > 脚本所在 repo。"""
    override = os.environ.get(ROOT_ENV, "").strip()
    if override:
        return Path(override)
    top = _git_toplevel(Path.cwd())
    if top is not None:
        return control_plane_root(top)
    return Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------- 路径与命名

def sanitize_name(name: str) -> str:
    """agent 名 → 文件名 stem：换掉文件系统敌对字符，保留 `·` 与中文。"""
    out = name.strip()
    for ch in ("/", "\\", ":", "|", "*", "?", '"', "<", ">", "\n", "\t"):
        out = out.replace(ch, "-")
    return out.replace(" ", "-") or "unnamed"


def agents_dir(root: Path) -> Path:
    return Path(root) / "memory" / "agents"


def state_path(root: Path, name: str) -> Path:
    return agents_dir(root) / f"{sanitize_name(name)}.yaml"


def mailbox_dir(root: Path, name: str) -> Path:
    return Path(root) / "memory" / "mailbox" / sanitize_name(name)


def current_agent_name(repo_root: Path) -> str:
    """当前 agent 身份：AGENT_NAME env > worktree 根 `.agent-identity` 首行 > 空串。"""
    env = os.environ.get("AGENT_NAME", "").strip()
    if env:
        return env
    ident = Path(repo_root) / ".agent-identity"
    if ident.is_file():
        try:
            return ident.read_text(encoding="utf-8", errors="replace").splitlines()[0].strip()
        except (OSError, IndexError):
            return ""
    return ""


# ---------------------------------------------------------------- YAML 读写（PyYAML 可选）

def _quote(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def dump_state(state: dict) -> str:
    lines = [f"# 由 scripts/agent-state.py 维护；schema 见 {DOCTRINE}"]
    for key in FIELD_ORDER:
        if key not in state or state[key] is None:
            continue
        value = state[key]
        if key in LIST_FIELDS:
            items = [str(v) for v in (value or [])]
            if not items:
                lines.append(f"{key}: []")
            else:
                lines.append(f"{key}:")
                lines.extend(f"  - {_quote(v)}" for v in items)
        elif isinstance(value, int):
            lines.append(f"{key}: {value}")
        else:
            lines.append(f"{key}: {_quote(str(value))}")
    return "\n".join(lines) + "\n"


def _scalar(raw: str):
    v = raw.strip()
    if not v or v in ("null", "~"):
        return None
    if v.startswith('"'):
        try:
            return json.loads(v)
        except ValueError:
            return v.strip('"')
    if len(v) >= 2 and v[0] == v[-1] == "'":
        return v[1:-1]
    if re.fullmatch(r"-?\d+", v):
        return int(v)
    return v


def _parse_restricted(text: str) -> dict:
    """无 PyYAML 的受限解析：扁平 mapping + 块列表 + 行内 `[]`（本文件写出的形状）。"""
    data: dict = {}
    cur_list: str | None = None
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        stripped = raw.strip()
        if raw.startswith((" ", "\t")) and stripped.startswith("- "):
            if cur_list is not None:
                data.setdefault(cur_list, []).append(_scalar(stripped[2:]))
            continue
        if ":" in stripped:
            key, _, val = stripped.partition(":")
            key, val = key.strip(), val.strip()
            if val == "":
                data[key] = []
                cur_list = key
            elif val == "[]":
                data[key] = []
                cur_list = None
            else:
                data[key] = _scalar(val)
                cur_list = None
    return data


def parse_state(text: str) -> dict:
    try:
        import yaml  # type: ignore

        loaded = yaml.safe_load(text)
        return loaded if isinstance(loaded, dict) else {}
    except ImportError:
        return _parse_restricted(text)
    except Exception:  # noqa: BLE001  破损 yaml → 尽力回退受限解析
        return _parse_restricted(text)


def load_state(root: Path, name: str) -> dict | None:
    path = state_path(root, name)
    if not path.is_file():
        return None
    try:
        return parse_state(path.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return None


def load_states(root: Path) -> dict[str, dict]:
    """读 `memory/agents/*.yaml` → {name: state}。破损文件跳过（保守）。"""
    out: dict[str, dict] = {}
    directory = agents_dir(root)
    if not directory.is_dir():
        return out
    for path in sorted(directory.glob("*.yaml")):
        try:
            state = parse_state(path.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        name = str(state.get("name") or path.stem)
        state["_path"] = str(path)
        out[name] = state
    return out


# ---------------------------------------------------------------- staleness

def heartbeat_age_minutes(state: dict, now: float | None = None) -> float | None:
    ts = _parse_iso(str(state.get("heartbeat") or ""))
    if ts is None:
        return None
    return ((now if now is not None else time.time()) - ts) / 60.0


def effective_status(state: dict, now: float | None = None) -> str:
    """derive stale：存储态 active/idle/blocked 且心跳超 TTL（默认 30min）→ stale。
    done 是终态不派生；无心跳字段视为 stale（保守：没证据证明它活着）。"""
    stored = str(state.get("status") or "active")
    if stored == "done":
        return "done"
    age = heartbeat_age_minutes(state, now)
    ttl = state.get("ttl_minutes")
    ttl = int(ttl) if isinstance(ttl, int) or (isinstance(ttl, str) and ttl.isdigit()) else STALE_TTL_MINUTES
    if age is None or age > ttl:
        return "stale"
    return stored


def is_enforceable(state: dict, now: float | None = None) -> bool:
    """ownership 是否仍应被冲突检测强制：stale/done 不强制（防陈旧 agent 卡路）。"""
    return effective_status(state, now) in ("active", "idle", "blocked")


# ---------------------------------------------------------------- 写操作

def _write_state(root: Path, name: str, state: dict) -> Path:
    path = state_path(root, name)
    path.parent.mkdir(parents=True, exist_ok=True)
    clean = {k: v for k, v in state.items() if not k.startswith("_")}
    path.write_text(dump_state(clean), encoding="utf-8")
    return path


def ensure_mailbox(root: Path, name: str) -> tuple[Path, Path]:
    box = mailbox_dir(root, name)
    box.mkdir(parents=True, exist_ok=True)
    inbox, outbox = box / "inbox.md", box / "outbox.md"
    for path, label in ((inbox, "inbox"), (outbox, "outbox")):
        if not path.is_file():
            path.write_text(
                f"# {label} — {name}\n\n"
                f"> 由 scripts/agent-mailbox.py 维护；schema 见 {DOCTRINE}。\n",
                encoding="utf-8",
            )
    return inbox, outbox


def register(root: Path, name: str, *, task: str | None = None,
             owned: list[str] | None = None, forbidden: list[str] | None = None,
             worktree: str | None = None, branch: str | None = None,
             paseo_id: str | None = None, status: str | None = None,
             now: float | None = None) -> Path:
    state = load_state(root, name) or {}
    state["name"] = name
    if task is not None:
        state["task"] = task
    if owned is not None:
        state["owned_paths"] = owned
    if forbidden is not None:
        state["forbidden_paths"] = forbidden
    if worktree is not None:
        state["worktree"] = worktree
    if branch is not None:
        state["branch"] = branch
    if paseo_id is not None:
        state["paseo_id"] = paseo_id
    state["status"] = status or state.get("status") or "active"
    state["heartbeat"] = _now_iso(now)
    state.setdefault("ttl_minutes", STALE_TTL_MINUTES)
    state.setdefault("owned_paths", [])
    state.setdefault("forbidden_paths", [])
    rel_box = f"memory/mailbox/{sanitize_name(name)}"
    state.setdefault("inbox_ref", f"{rel_box}/inbox.md")
    state.setdefault("outbox_ref", f"{rel_box}/outbox.md")
    ensure_mailbox(root, name)
    return _write_state(root, name, state)


def touch_heartbeat(root: Path, name: str, now: float | None = None) -> bool:
    state = load_state(root, name)
    if state is None:
        return False
    state["heartbeat"] = _now_iso(now)
    _write_state(root, name, state)
    return True


def set_status(root: Path, name: str, status: str) -> bool:
    if status not in STORED_STATUSES:
        raise ValueError(f"非法状态 {status!r}，可选：{'/'.join(STORED_STATUSES)}")
    state = load_state(root, name)
    if state is None:
        return False
    state["status"] = status
    state["heartbeat"] = _now_iso()
    _write_state(root, name, state)
    return True


# ---------------------------------------------------------------- self-test

def _self_test() -> int:
    failures: list[str] = []

    def check(cond: bool, label: str) -> None:
        print(("  ok    " if cond else "  FAIL  ") + label)
        if not cond:
            failures.append(label)

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        register(root, "干将·改·demo", task="控制面 demo", owned=["scripts/agent-state.py"],
                 forbidden=["lab/data/"], worktree="/tmp/wt", branch="feat/x")
        st = load_state(root, "干将·改·demo")
        check(st is not None and st["task"] == "控制面 demo", "register → 可回读 task")
        check(st is not None and st["owned_paths"] == ["scripts/agent-state.py"], "owned_paths 列表往返")
        check(st is not None and st["forbidden_paths"] == ["lab/data/"], "forbidden_paths 列表往返")
        check(effective_status(st or {}) == "active", "新心跳 → active")
        old = time.time() - 31 * 60
        register(root, "斥候·查·stale", task="过期", now=old)
        stale = load_state(root, "斥候·查·stale") or {}
        check(effective_status(stale) == "stale", "31 分钟无心跳 → stale（TTL=30）")
        register(root, "斥候·查·idle", status="idle")
        check(effective_status(load_state(root, "斥候·查·idle") or {}) == "idle", "TTL 内 idle 保留")
        check(effective_status({"name": "x", "status": "active"}) == "stale", "无心跳字段 → stale")
        check(set_status(root, "干将·改·demo", "done"), "set-status done")
        check(effective_status(load_state(root, "干将·改·demo") or {}) == "done", "done 是终态不派生 stale")
        check(touch_heartbeat(root, "斥候·查·stale"), "heartbeat 可刷新")
        check(effective_status(load_state(root, "斥候·查·stale") or {}) == "active", "刷新后回 active")
        inbox = root / "memory" / "mailbox" / "干将·改·demo" / "inbox.md"
        check(inbox.is_file(), "register 顺带建 mailbox inbox/outbox")
        parsed = _parse_restricted(dump_state({"name": "a·b", "ttl_minutes": 30,
                                               "owned_paths": ["x/y.py"], "forbidden_paths": []}))
        check(parsed.get("name") == "a·b" and parsed.get("owned_paths") == ["x/y.py"]
              and parsed.get("forbidden_paths") == [] and parsed.get("ttl_minutes") == 30,
              "受限解析器（无 PyYAML 路径）与写出形状一致")
        check(sanitize_name("a/b|c d") == "a-b-c-d", "文件名 sanitize")
        # control_plane_root：linked worktree 的 .git 文件 → 主 checkout
        main = root / "main"
        (main / ".git" / "worktrees" / "wt1").mkdir(parents=True)
        wt = root / "wt1"
        wt.mkdir()
        (wt / ".git").write_text(f"gitdir: {main}/.git/worktrees/wt1\n", encoding="utf-8")
        check(control_plane_root(wt) == main, "control_plane_root：worktree → 主 checkout")
        check(control_plane_root(main) == main, "control_plane_root：主 checkout 原样")
        os.environ[ROOT_ENV] = str(root / "override")
        try:
            check(control_plane_root(wt) == root / "override", f"{ROOT_ENV} 显式覆盖")
        finally:
            os.environ.pop(ROOT_ENV, None)

    print(f"\nagent-state self-test：{'全部通过' if not failures else f'{len(failures)} 项失败'}")
    return 1 if failures else 0


# ---------------------------------------------------------------- CLI

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--self-test", action="store_true")
    sub = ap.add_subparsers(dest="cmd")

    p_reg = sub.add_parser("register", help="登记/更新 agent 状态文件（含心跳 + mailbox 初始化）")
    p_reg.add_argument("name")
    p_reg.add_argument("--task", default=None)
    p_reg.add_argument("--owned", nargs="*", default=None, help="owned paths（repo-relative）")
    p_reg.add_argument("--forbidden", nargs="*", default=None)
    p_reg.add_argument("--worktree", default=None, help="该 agent 的 worktree 绝对路径（默认取当前 toplevel）")
    p_reg.add_argument("--branch", default=None)
    p_reg.add_argument("--paseo-id", default=None)
    p_reg.add_argument("--status", default=None, choices=STORED_STATUSES)
    p_reg.add_argument("--root", default=None)

    for cmd, help_ in (("heartbeat", "刷新心跳"), ("show", "打印状态文件")):
        p = sub.add_parser(cmd, help=help_)
        p.add_argument("name")
        p.add_argument("--root", default=None)

    p_set = sub.add_parser("set-status", help="改存储态（active/idle/blocked/done）")
    p_set.add_argument("name")
    p_set.add_argument("status", choices=STORED_STATUSES)
    p_set.add_argument("--root", default=None)

    args = ap.parse_args()
    if args.self_test:
        return _self_test()
    if not args.cmd:
        ap.print_help()
        return 1

    root = Path(args.root) if getattr(args, "root", None) else default_root()

    if args.cmd == "register":
        worktree = args.worktree
        if worktree is None:
            top = _git_toplevel(Path.cwd())
            worktree = str(top) if top else None
        branch = args.branch
        if branch is None:
            try:
                out = subprocess.run(["git", "branch", "--show-current"], cwd=str(Path.cwd()),
                                     capture_output=True, text=True, timeout=5)
                branch = out.stdout.strip() or None
            except (OSError, subprocess.SubprocessError):
                branch = None
        path = register(root, args.name, task=args.task, owned=args.owned,
                        forbidden=args.forbidden, worktree=worktree, branch=branch,
                        paseo_id=args.paseo_id, status=args.status)
        print(f"[agent-state] 已登记 {args.name} → {path}")
        return 0
    if args.cmd == "heartbeat":
        if touch_heartbeat(root, args.name):
            print(f"[agent-state] 心跳已刷新：{args.name}")
            return 0
        print(f"[agent-state] 找不到 agent：{args.name}（先 register）", file=sys.stderr)
        return 1
    if args.cmd == "set-status":
        if set_status(root, args.name, args.status):
            print(f"[agent-state] {args.name} → {args.status}")
            return 0
        print(f"[agent-state] 找不到 agent：{args.name}", file=sys.stderr)
        return 1
    if args.cmd == "show":
        state = load_state(root, args.name)
        if state is None:
            print(f"[agent-state] 找不到 agent：{args.name}", file=sys.stderr)
            return 1
        sys.stdout.write(dump_state(state))
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
