#!/usr/bin/env python3
"""Agent self-naming setter —— agent 据 doctrine 选定名字后调用，做「机械」那部分：
① 写 worktree 根的 `.agent-identity`；② `paseo agent update <id> --name`（**默认开启**，清理
垃圾 tab 名）；③ upsert `memory/agents-roster.md` 花名册一行；④ 尽力初始化控制面状态文件
`memory/agents/<name>.yaml`（经 `scripts/agent-state.py`，见 `.agent/multi-agent-control-plane.md`；
roster 尾列 `state` 指向该文件——roster 管总览索引，yaml 管状态明细，不重复同一批字段）。

命名 doctrine（`<persona>·<动作字>·<focus>`）见 `.agent/agent-identity.md`——**选名由 agent 做**
（据真实任务），本脚本只负责落地。

用法：
    python3 agent_name_set.py "<persona·动作·focus>"                       # 自命名（本 agent）
    python3 agent_name_set.py "<name>" --register --paseo-id <child-id> \
        [--worktree "<branch (wt)>"]                                       # 登记子 agent（launcher 用）

行为开关：
- `AGENT_NO_AUTORENAME=1` → 跳过 `paseo rename`（仍写文件 + roster）。
- 无 `PASEO_AGENT_ID`（非 Paseo 表面）→ 自动跳过 rename（runtime-agnostic）。

`--register` 模式（供 spawn skill 的 Paseo-tab launcher）：只 upsert roster 一行（给定 name+id），
**不**写自己的 `.agent-identity`、**不** rename——子 agent 已在 `paseo run --title/--env` 时出生即命名。

尽力而为、失败不 raise、不 block。无第三方依赖。
"""
import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import agent_identity  # noqa: E402  复用 _clean / 路径锚定

REPO_ROOT = agent_identity.REPO_ROOT
IDENTITY_FILE = agent_identity.IDENTITY_FILE
ROSTER = REPO_ROOT / "memory" / "agents-roster.md"

ROSTER_HEADER = (
    "# agents-roster —— 活 agent 花名册（运行时 · 项目层 · 不随 template sync）\n\n"
    "> 由 `.claude/hooks/agent_name_set.py` 维护；命名 doctrine 见 `.agent/agent-identity.md`。\n"
    "> 每个 project 各自的活 agent，不继承、不同步。\n"
    "> `state` 列指向 `memory/agents/<name>.yaml` 状态明细（`.agent/multi-agent-control-plane.md`）。\n\n"
    "| name | 做什么 | focus | branch/worktree | paseo-id | status | updated | state |\n"
    "| --- | --- | --- | --- | --- | --- | --- | --- |\n"
)


def _git(args: list[str]) -> str:
    try:
        out = subprocess.run(
            ["git", *args], cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=5
        )
        return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def _branch_worktree() -> str:
    branch = _git(["branch", "--show-current"]) or _git(["rev-parse", "--short", "HEAD"])
    top = _git(["rev-parse", "--show-toplevel"])
    wt = Path(top).name if top else ""
    if branch and wt:
        return f"{branch} ({wt})"
    return branch or wt or "-"


def _paseo_rename(name: str) -> str:
    """默认自动改名清垃圾 tab 名；返回状态串（供日志）。"""
    if os.environ.get("AGENT_NO_AUTORENAME"):
        return "skip(AGENT_NO_AUTORENAME)"
    pid = os.environ.get("PASEO_AGENT_ID", "").strip()
    if not pid:
        return "skip(no PASEO_AGENT_ID)"
    try:
        # 正确命令：`paseo agent update <id> --name "<name>"`（`paseo rename` 不存在）。
        r = subprocess.run(
            ["paseo", "agent", "update", pid, "--name", name],
            capture_output=True, text=True, timeout=10,
        )
        # 注意：paseo agent update 对「agent 不存在」也 exit 0 并打印 Error → 查输出才准。
        # 用 paseo 的确切失败短语（非裸 "error"），否则名字含 "error"（如 focus=error-handling）
        # 会把成功误判成失败。
        out = (r.stdout + r.stderr).lower()
        ok = r.returncode == 0 and "failed to update agent" not in out and "agent not found" not in out
        return "renamed" if ok else f"rename-failed(rc={r.returncode})"
    except (OSError, subprocess.SubprocessError):
        return "rename-failed(no paseo)"


def _split_name(name: str) -> tuple[str, str]:
    """`persona·动作·focus` → (做什么=persona·动作, focus)。

    分隔符归一化：把常见中点变体（片假名中点 U+30FB `・`、连字点 U+2027 `‧`）归到
    标准 `·`(U+00B7)，再按 `·` 切；不动 `-`（focus 可能含连字号如 auth-重构）。
    """
    for ch in "・‧":
        name = name.replace(ch, "·")
    parts = name.split("·")
    if len(parts) >= 3:
        return "·".join(parts[:2]), "·".join(parts[2:])
    if len(parts) == 2:
        return parts[0], parts[1]
    return name, "-"


def _cell(s: str) -> str:
    """markdown 表格单元格：转义 | 与换行，防止破表。"""
    return s.replace("|", "\\|").replace("\n", " ").strip() or "-"


def _state_helpers():
    """尽力加载 scripts/agent-state.py（issue #14 控制面）；缺失/失败返回 None（不 block）。"""
    script = REPO_ROOT / "scripts" / "agent-state.py"
    if not script.is_file():
        return None
    try:
        import importlib.util

        spec = importlib.util.spec_from_file_location("agent_state", script)
        if spec is None or spec.loader is None:
            return None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception:  # noqa: BLE001  控制面是增量层，任何失败不影响命名主流程
        return None


def _register_state(name: str, pid: str, worktree: str | None, branch: str | None) -> str:
    """初始化/刷新 `memory/agents/<name>.yaml`（心跳+mailbox）。返回状态串（供日志）。"""
    mod = _state_helpers()
    if mod is None:
        return "state-skip(no agent-state.py)"
    try:
        root = mod.control_plane_root(REPO_ROOT)
        mod.register(root, name, paseo_id=pid or None, worktree=worktree, branch=branch)
        return "state-registered"
    except Exception:  # noqa: BLE001
        return "state-failed"


def _state_ref(name: str) -> str:
    mod = _state_helpers()
    if mod is None:
        return "-"
    try:
        return f"memory/agents/{mod.sanitize_name(name)}.yaml"
    except Exception:  # noqa: BLE001
        return "-"


def _split_cols(row: str) -> list[str]:
    """按「未转义」的 | 切表格行：先把 \\| 占位，切完再还原（防 name/focus 里的真实 |）。"""
    return [c.replace("\x00", "|").strip()
            for c in row.strip("|").replace("\\|", "\x00").split("|")]


def _migrate_roster(lines: list[str]) -> list[str]:
    """旧 7 列表头（无尾列 `state`）原位升级为 8 列：表头/分隔行补列、7 列旧数据行补默认值
    `-`。否则合并后会出现七列表头配八列数据（新行由本脚本按 8 列写出）。幂等：已是 8 列表头
    原样返回；已有 8 列的数据行不再补。"""
    header_i = next((i for i, ln in enumerate(lines) if ln.strip().startswith("| name ")), None)
    if header_i is None or "| state |" in lines[header_i]:
        return lines
    out: list[str] = []
    for ln in lines:
        s = ln.strip()
        if not s.startswith("|"):
            out.append(ln)
        elif s.startswith("| name "):
            out.append(s + " state |\n")
        elif s.startswith("| ---"):
            out.append(s + " --- |\n")
        elif len(_split_cols(s)) == 7:
            out.append(s + " - |\n")
        else:
            out.append(ln)
    return out


def _upsert_roster(name: str, doing: str, focus: str, bw: str, pid: str) -> None:
    ts = time.strftime("%Y-%m-%d %H:%M")
    row = (f"| {_cell(name)} | {_cell(doing)} | {_cell(focus)} | {_cell(bw)} | {_cell(pid or '-')} "
           f"| active | {ts} | {_cell(_state_ref(name))} |\n")
    try:
        ROSTER.parent.mkdir(parents=True, exist_ok=True)
        text = ROSTER.read_text(encoding="utf-8") if ROSTER.is_file() else ROSTER_HEADER
    except (OSError, ValueError):
        text = ROSTER_HEADER
    lines = _migrate_roster(text.splitlines(keepends=True))
    # 找同一 agent 的数据行替换；否则追加。数据行 = 以 | 开头且不是表头/分隔行。
    replaced = False
    for i, ln in enumerate(lines):
        s = ln.strip()
        if not s.startswith("|") or s.startswith("| ---") or s.startswith("| name "):
            continue
        # 按「未转义」的 | 切列（_split_cols）——否则 name/focus 里的真实 |
        # 会多切出一列、错位 paseo-id、导致去重失败而重复行（无限增长）。
        cols = _split_cols(s)
        row_name = cols[0] if cols else ""
        row_pid = cols[4] if len(cols) >= 5 else ""
        if pid:
            match = row_pid == pid                                  # 有 pid：按 paseo-id 去重
        else:
            match = row_name == name and row_pid in ("", "-")       # 无 pid：只认同样无 pid 的同名行
        if match:
            lines[i] = row
            replaced = True
            break
    if not replaced:
        if not text.endswith("\n"):
            lines.append("\n")
        lines.append(row)
    try:
        ROSTER.write_text("".join(lines), encoding="utf-8")
    except OSError:
        pass


def _register_child(name: str, pid: str, worktree: str) -> int:
    """launcher 用：把「已出生即命名」的子 agent 登记进 roster + 初始化控制面状态文件。
    不写自身 `.agent-identity`、不 rename。worktree 参数是展示标签（`branch (wt)`），
    子 agent 的实际 worktree 路径由它自己首次 register/heartbeat 时补。"""
    doing, focus = _split_name(name)
    _upsert_roster(name, doing, focus, worktree or "-", pid)
    state_status = _register_state(name, pid, None, None)
    print(f"[agent-name] 已登记子 agent {name}（paseo-id={pid or '-'}；roster + {state_status}）",
          file=sys.stderr)
    return 0


def _self_test() -> int:
    """roster 读写自检（只写 /tmp 临时目录，可在只读 repo 下跑）。"""
    global ROSTER
    import tempfile

    failures: list[str] = []

    def check(cond: bool, label: str) -> None:
        print(("  ok    " if cond else "  FAIL  ") + label)
        if not cond:
            failures.append(label)

    saved_roster = ROSTER
    try:
        with tempfile.TemporaryDirectory() as td:
            ROSTER = Path(td) / "agents-roster.md"
            # [MINOR 回归] 旧 7 列表头 roster（无 state 列）→ upsert 时原位升级为 8 列
            ROSTER.write_text(
                "# agents-roster —— 活 agent 花名册\n\n"
                "| name | 做什么 | focus | branch/worktree | paseo-id | status | updated |\n"
                "| --- | --- | --- | --- | --- | --- | --- |\n"
                "| 旧·将·one | 旧·将 | one | main (repo) | p-1 | active | 2026-07-01 10:00 |\n",
                encoding="utf-8",
            )
            _upsert_roster("干将·修·two", "干将·修", "two", "feat/x (wt)", "p-2")
            lines = ROSTER.read_text(encoding="utf-8").splitlines()
            header = next(ln for ln in lines if ln.startswith("| name "))
            sep = next(ln for ln in lines if ln.startswith("| ---"))
            rows = {_split_cols(ln)[0]: _split_cols(ln) for ln in lines
                    if ln.startswith("|") and not ln.startswith(("| name ", "| ---"))}
            check(header.rstrip().endswith("| state |") and len(_split_cols(header)) == 8,
                  "旧 7 列表头升级为含 state 的 8 列")
            check(len(_split_cols(sep)) == 8, "分隔行同步补到 8 列")
            check(len(rows["旧·将·one"]) == 8 and rows["旧·将·one"][7] == "-",
                  "旧数据行补默认值 `-`（7 列 → 8 列）")
            check(len(rows["干将·修·two"]) == 8 and rows["干将·修·two"][4] == "p-2",
                  "新行按 8 列写出、paseo-id 不错位")

            # 幂等：8 列 roster 再 upsert 不再迁移、按 paseo-id 去重不重复行
            _upsert_roster("干将·修·two", "干将·修", "two", "feat/x (wt)", "p-2")
            lines2 = ROSTER.read_text(encoding="utf-8").splitlines()
            check(sum(1 for ln in lines2 if ln.startswith("| name ")) == 1
                  and sum("p-2" in ln for ln in lines2) == 1,
                  "8 列 roster 幂等：不重复迁移、同 paseo-id 不重复行")

            # 全新 roster（无文件）→ 直接 8 列表头
            ROSTER = Path(td) / "fresh-roster.md"
            _upsert_roster("师爷·审·three", "师爷·审", "three", "main (repo)", "p-3")
            fresh = ROSTER.read_text(encoding="utf-8")
            check("| state |" in fresh and "| 师爷·审·three |" in fresh,
                  "全新 roster 直接 8 列表头")
    finally:
        ROSTER = saved_roster

    print(("agent-name-set self-test：全部通过" if not failures
           else f"agent-name-set self-test：{len(failures)} 项失败"), file=sys.stderr)
    return 1 if failures else 0


def main() -> int:
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("name", nargs="?", default="")
    ap.add_argument("--register", action="store_true",
                    help="只登记给定 name+id 到 roster（launcher 用），不改自身")
    ap.add_argument("--paseo-id", default="", help="--register 时要登记的子 agent id")
    ap.add_argument("--worktree", default="", help="--register 时该 agent 的 branch/worktree 标签")
    ap.add_argument("--self-test", action="store_true")
    args, _ = ap.parse_known_args()

    if args.self_test:
        return _self_test()

    name = agent_identity._clean(args.name)
    if not name:
        print("[agent-name] 用法：agent_name_set.py \"<persona·动作·focus>\"（名字为空，未改动）", file=sys.stderr)
        return 0  # 不 raise

    if args.register:
        pid = args.paseo_id.strip()
        if not pid:
            # 空 pid 说明 launcher 没取到子 agent id（run --json 形状异常/未起成功）。
            # 不登记：否则无 pid 的行可能覆盖掉一条合法的、同名的自命名行（非 Paseo 表面）。
            print("[agent-name] --register 缺 --paseo-id：疑似子 agent 未起成功，未登记（先排查 paseo run）",
                  file=sys.stderr)
            return 0
        return _register_child(name, pid, args.worktree.strip())

    # 自命名（本 agent）：① identity 文件 ② paseo rename（默认开启）③ roster ④ 控制面状态文件
    try:
        IDENTITY_FILE.write_text(name + "\n", encoding="utf-8")
    except OSError:
        pass
    rename_status = _paseo_rename(name)
    doing, focus = _split_name(name)
    pid = os.environ.get("PASEO_AGENT_ID", "").strip()
    _upsert_roster(name, doing, focus, _branch_worktree(), pid)
    top = _git(["rev-parse", "--show-toplevel"])
    branch = _git(["branch", "--show-current"])
    state_status = _register_state(name, pid, top or None, branch or None)
    print(f"[agent-name] 已命名 {name}（{rename_status}；已写 .agent-identity + roster + {state_status}）",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
