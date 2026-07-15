#!/usr/bin/env python3
"""check-agent-conflicts —— ownership 冲突检测 + 写错 worktree 检测（issue #14）。

依据 `.agent/multi-agent-control-plane.md`：agent 在 `memory/agents/<name>.yaml` 声明
owned_paths / forbidden_paths / worktree；本脚本做两件可判定的事：

1. **overlap 扫描**（`scan`，默认）：活跃（active/idle/blocked 且心跳未超 TTL=30min）agent
   之间 owned_paths 重叠 → 明确冲突信号（exit 1）。stale/done 的声明不强制（human 拍板
   4.4：heartbeat+TTL 防陈旧 agent 卡路）。
2. **写错 worktree 检测**（`worktree`）：当前 agent（AGENT_NAME / `.agent-identity`）状态
   文件里 declared worktree 与实际 `git rev-parse --show-toplevel` 不符 → exit 1。
   机器检查，不依赖 prompt 自检（验收 #4）。

同时暴露 `pretooluse_reason(tool_name, tool_input, repo_root)` 给
`.claude/hooks/pre_tool_guard.py` 做写入前机械拦截（Claude/Codex 共用同一物理 hook；
human 拍板：折进已共享 hook、第一版只做写入前这一层）。覆盖 Claude 的
Edit/Write/NotebookEdit 与 Codex 的 apply_patch（`*** Add/Update/Delete/Move` patch 头）。
判定层任何异常由 hook 侧保守放行；当前 agent 身份未知时不拦（避免误伤未纳管 session）。
human 显式绕过：`AGENT_CONFLICT_SKIP=1`。

runtime-neutral：纯 python、无第三方依赖（状态解析复用 agent-state.py，PyYAML 可选）。

用法：
  python scripts/check-agent-conflicts.py [scan] [--root R] [--json]
  python scripts/check-agent-conflicts.py worktree [--name N] [--actual-toplevel P] [--root R]
  python scripts/check-agent-conflicts.py --self-test
退出码：0 = 无冲突，1 = 检出冲突/不符。
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import tempfile
import time
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
SKIP_ENV = "AGENT_CONFLICT_SKIP"
_ESCAPE_HINT = f"确属误报/human 授权可 {SKIP_ENV}=1 显式放行（先与对方 agent/监控员协调）。"


def _load_agent_state():
    spec = importlib.util.spec_from_file_location("agent_state", SCRIPTS_DIR / "agent-state.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


AS = _load_agent_state()


# ---------------------------------------------------------------- 路径匹配

def _norm(path: str) -> str:
    p = str(path).strip().strip('"').strip("'")
    if p.startswith("./"):
        p = p[2:]
    return p.rstrip("/")


def path_under(target: str, owned_entry: str) -> bool:
    """target 是否落在 owned_entry（文件精确匹配；目录含尾随内容前缀匹配）之下。"""
    t, e = _norm(target), _norm(owned_entry)
    if not t or not e:
        return False
    return t == e or t.startswith(e + "/") or e.startswith(t + "/")


def _rel_to_repo(path: str, repo_root: Path, cp_root: Path) -> str | None:
    """写入路径 → repo-relative posix；不在 repo 内返回 None（不属本控制面管）。"""
    p = Path(path)
    if p.is_absolute():
        for base in (repo_root, cp_root):
            try:
                return p.resolve().relative_to(Path(base).resolve()).as_posix()
            except (ValueError, OSError):
                continue
        return None
    return _norm(Path(path).as_posix())


def _patch_paths(patch_text: str) -> list[str]:
    """Codex apply_patch 的 patch 头 → 路径列表（与 pre_tool_guard._patch_paths 同形）。"""
    paths: list[str] = []
    for line in patch_text.splitlines():
        for prefix in ("*** Add File: ", "*** Update File: ", "*** Delete File: ", "*** Move to: "):
            if line.startswith(prefix):
                paths.append(line[len(prefix):].strip())
                break
    return paths


def write_paths(tool_name: str, tool_input: dict) -> list[str]:
    if tool_name in ("Edit", "Write", "NotebookEdit"):
        p = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
        return [p] if p else []
    if tool_name == "apply_patch":
        return _patch_paths(tool_input.get("command", "") or "")
    return []


# ---------------------------------------------------------------- 判定

def find_overlaps(states: dict[str, dict], now: float | None = None) -> list[dict]:
    """活跃 agent 两两 owned_paths 重叠。返回冲突记录列表。"""
    enforceable = {n: s for n, s in states.items() if AS.is_enforceable(s, now)}
    names = sorted(enforceable)
    out: list[dict] = []
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            for pa in enforceable[a].get("owned_paths") or []:
                for pb in enforceable[b].get("owned_paths") or []:
                    if path_under(str(pa), str(pb)):
                        out.append({"agent_a": a, "path_a": str(pa),
                                    "agent_b": b, "path_b": str(pb)})
    return out


def worktree_mismatch(root: Path, name: str, actual_toplevel: Path,
                      now: float | None = None) -> str | None:
    """declared worktree vs 实际 toplevel 不符 → 返回原因串；一致/无声明 → None。"""
    state = AS.load_state(root, name)
    if state is None:
        return None
    declared = str(state.get("worktree") or "").strip()
    if not declared:
        return None
    try:
        if Path(declared).resolve() == Path(actual_toplevel).resolve():
            return None
    except OSError:
        return None
    return (
        f"agent「{name}」登记的 worktree 是 {declared}，但当前写入发生在 {actual_toplevel}。"
        f"疑似写错 worktree——先 pwd + git rev-parse --show-toplevel 核对，或更新状态文件"
        f"（python scripts/agent-state.py register）。{_ESCAPE_HINT}"
    )


def pretooluse_reason(tool_name: str, tool_input: dict, repo_root) -> str | None:
    """给 pre_tool_guard.py 的写入前判定：返回 deny 原因串，None = 放行。
    保守原则：身份未知 / 无状态文件 / 路径不在 repo 内 → 放行；stale/done 声明不强制。"""
    if os.environ.get(SKIP_ENV, "").strip().lower() in ("1", "true", "yes"):
        return None
    paths = write_paths(tool_name, tool_input or {})
    if not paths:
        return None
    repo_root = Path(repo_root)
    cp_root = AS.control_plane_root(repo_root)
    states = AS.load_states(cp_root)
    if not states:
        return None
    me = AS.current_agent_name(repo_root)
    if not me or me not in states:
        return None  # 未纳管 session：只有声明过身份+状态的 agent 才被强制
    now = time.time()

    mismatch = worktree_mismatch(cp_root, me, repo_root, now)
    if mismatch:
        return mismatch

    my_state = states[me]
    for raw in paths:
        rel = _rel_to_repo(raw, repo_root, cp_root)
        if rel is None:
            continue
        for fp in my_state.get("forbidden_paths") or []:
            if path_under(rel, str(fp)):
                return (
                    f"路径 {rel} 在你（{me}）自己声明的 forbidden_paths（{fp}）内。"
                    f"任务边界外的改动先升级给上层。{_ESCAPE_HINT}"
                )
        for other, st in states.items():
            if other == me or not AS.is_enforceable(st, now):
                continue
            for op in st.get("owned_paths") or []:
                if path_under(rel, str(op)):
                    age = AS.heartbeat_age_minutes(st, now)
                    age_s = f"{age:.0f}min 前" if age is not None else "未知"
                    return (
                        f"ownership 冲突：{rel} 由活跃 agent「{other}」持有"
                        f"（owned: {op}；task: {st.get('task') or '-'}；心跳 {age_s}）。"
                        f"先经 mailbox 协调或走 ownership handoff"
                        f"（python scripts/agent-mailbox.py handoff … + ack）。{_ESCAPE_HINT}"
                    )
    return None


# ---------------------------------------------------------------- self-test

def _self_test() -> int:  # noqa: PLR0915
    failures: list[str] = []

    def check(cond: bool, label: str) -> None:
        print(("  ok    " if cond else "  FAIL  ") + label)
        if not cond:
            failures.append(label)

    saved_env = {k: os.environ.pop(k, None) for k in ("AGENT_NAME", SKIP_ENV, AS.ROOT_ENV)}
    try:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            now = time.time()
            AS.register(root, "干将·改·alpha", task="实现 A", owned=["src/core/", "scripts/x.py"],
                        worktree=str(root), now=now)
            AS.register(root, "师爷·审·beta", task="审查 B", owned=["reviews/"],
                        forbidden=["lab/data/"], worktree=str(root), now=now)

            # 1) overlap 扫描
            check(find_overlaps(AS.load_states(root), now) == [], "无重叠 → 扫描干净")
            AS.register(root, "干将·改·gamma", task="也要改 core", owned=["src/core/db.py"],
                        worktree=str(root), now=now)
            overlaps = find_overlaps(AS.load_states(root), now)
            check(len(overlaps) == 1 and {overlaps[0]["agent_a"], overlaps[0]["agent_b"]}
                  == {"干将·改·alpha", "干将·改·gamma"}, "目录 vs 文件重叠可检出（明确信号）")
            AS.register(root, "干将·改·gamma", now=now - 45 * 60)  # gamma 心跳过期
            check(find_overlaps(AS.load_states(root), now) == [], "stale agent 的声明不强制")

            # 2) pretooluse：他人 owned path
            os.environ["AGENT_NAME"] = "师爷·审·beta"
            deny = pretooluse_reason("Edit", {"file_path": str(root / "src/core/engine.py")}, root)
            check(deny is not None and "干将·改·alpha" in deny and "src/core/engine.py" in deny,
                  "写他人 owned path → deny（点名 owner）")
            deny2 = pretooluse_reason(
                "apply_patch",
                {"command": "*** Begin Patch\n*** Update File: src/core/engine.py\n*** End Patch"},
                root)
            check(deny2 is not None and "干将·改·alpha" in deny2,
                  "Codex apply_patch 形状同样触发")
            check(pretooluse_reason("Write", {"file_path": str(root / "reviews/r1.md")}, root) is None,
                  "写自己 owned path → 放行")
            deny3 = pretooluse_reason("Edit", {"file_path": str(root / "lab/data/x.csv")}, root)
            check(deny3 is not None and "forbidden_paths" in deny3,
                  "写自己声明的 forbidden path → deny")
            check(pretooluse_reason("Edit", {"file_path": "/etc/hosts"}, root) is None,
                  "repo 外路径不管")
            check(pretooluse_reason("Bash", {"command": "ls"}, root) is None,
                  "非写工具不触发")
            gamma_deny = pretooluse_reason("Edit", {"file_path": str(root / "src/core/db.py")}, root)
            check(gamma_deny is not None and "干将·改·alpha" in gamma_deny,
                  "stale 的 gamma 不拦、活跃的 alpha 仍拦")

            # 3) skip env / 身份未知
            os.environ[SKIP_ENV] = "1"
            check(pretooluse_reason("Edit", {"file_path": str(root / "src/core/engine.py")}, root)
                  is None, f"{SKIP_ENV}=1 显式放行")
            os.environ.pop(SKIP_ENV)
            os.environ.pop("AGENT_NAME")
            check(pretooluse_reason("Edit", {"file_path": str(root / "src/core/engine.py")}, root)
                  is None, "身份未知（无 AGENT_NAME/.agent-identity）→ 保守放行")

            # 4) 写错 worktree（负向 fixture：declared ≠ 实际 toplevel）
            os.environ["AGENT_NAME"] = "干将·改·alpha"
            AS.register(root, "干将·改·alpha", worktree=str(root / "elsewhere"), now=now)
            wt_deny = pretooluse_reason("Edit", {"file_path": str(root / "src/core/engine.py")}, root)
            check(wt_deny is not None and "写错 worktree" in wt_deny,
                  "declared worktree ≠ 实际 → hook 层 deny")
            reason = worktree_mismatch(root, "干将·改·alpha", root, now)
            check(reason is not None and "elsewhere" in reason,
                  "worktree 子命令负向 fixture 可重复触发")
            AS.register(root, "干将·改·alpha", worktree=str(root), now=now)
            check(worktree_mismatch(root, "干将·改·alpha", root, now) is None,
                  "declared = 实际 → 通过")
            os.environ.pop("AGENT_NAME")

            # 5) 空控制面 / 无状态目录 → 放行
            with tempfile.TemporaryDirectory() as td2:
                os.environ["AGENT_NAME"] = "谁·都·不是"
                check(pretooluse_reason("Edit", {"file_path": "a.md"}, Path(td2)) is None,
                      "无任何状态文件 → 放行")
                os.environ.pop("AGENT_NAME")
    finally:
        for k, v in saved_env.items():
            if v is not None:
                os.environ[k] = v

    print(f"\ncheck-agent-conflicts self-test：{'全部通过' if not failures else f'{len(failures)} 项失败'}")
    return 1 if failures else 0


# ---------------------------------------------------------------- CLI

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--self-test", action="store_true")
    sub = ap.add_subparsers(dest="cmd")

    p_scan = sub.add_parser("scan", help="活跃 agent owned_paths 两两重叠扫描（默认）")
    p_scan.add_argument("--root", default=None)
    p_scan.add_argument("--json", action="store_true")

    p_wt = sub.add_parser("worktree", help="当前 agent declared worktree vs 实际 toplevel")
    p_wt.add_argument("--name", default=None)
    p_wt.add_argument("--actual-toplevel", default=None, help="覆盖实际 toplevel（负向 fixture 用）")
    p_wt.add_argument("--root", default=None)

    args = ap.parse_args()
    if args.self_test:
        return _self_test()
    cmd = args.cmd or "scan"
    root = Path(getattr(args, "root", None)) if getattr(args, "root", None) else AS.default_root()

    if cmd == "scan":
        overlaps = find_overlaps(AS.load_states(root))
        if getattr(args, "json", False):
            print(json.dumps(overlaps, ensure_ascii=False, indent=2))
        elif overlaps:
            print(f"检出 {len(overlaps)} 处 ownership 重叠（活跃 agent 间）：")
            for o in overlaps:
                print(f"  ✗ {o['agent_a']}（{o['path_a']}） ↔ {o['agent_b']}（{o['path_b']}）")
            print("先经 mailbox 协调或走 ownership handoff，再开工。")
        else:
            print("无 ownership 重叠（stale/done 声明不计）。")
        return 1 if overlaps else 0

    if cmd == "worktree":
        name = args.name or AS.current_agent_name(Path.cwd())
        if not name:
            print("[conflicts] 无法确定当前 agent（设 AGENT_NAME 或写 .agent-identity）", file=sys.stderr)
            return 1
        actual = Path(args.actual_toplevel) if args.actual_toplevel else (
            AS._git_toplevel(Path.cwd()) or Path.cwd())
        reason = worktree_mismatch(root, name, actual)
        if reason:
            print(f"[conflicts] {reason}", file=sys.stderr)
            return 1
        print(f"[conflicts] worktree 一致：{name} @ {actual}")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
