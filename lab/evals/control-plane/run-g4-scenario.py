#!/usr/bin/env python3
"""G4 双 agent 场景驱动 —— issue #57（父 issue #52 P7，D 层）。

对多 agent 控制面（`.agent/multi-agent-control-plane.md`，issue #14）跑一个完整的双 agent
故事：两个虚构 demo agent（A/B）在**隔离控制面根**（每个 T-ID 各自一份 `tempfile.mkdtemp`，
用后即弃）里 register/heartbeat/mailbox/handoff/conflict-scan/worktree-check/roster，逐条覆盖
7 个 T-ID（表格见 issue #57）的正例（按契约工作）与负例（越界被拒/优雅降级）。

**不是新 runner 框架**——复用四个控制面脚本（`scripts/agent-state.py` /
`scripts/agent-mailbox.py` / `scripts/agent-status.py` / `scripts/check-agent-conflicts.py`）
已有的 CLI 契约（多数走真实 subprocess + `--root` 隔离）与 `agent-state.py` 的 `register(...,
now=...)` 库函数（唯一无法从 CLI 表达的时间穿梭：TTL→stale 派生需要一个 31 分钟前的心跳，
CLI 没有 `--now` 开关，直接 importlib 复用同一份 register() 而非等真实 30 分钟或重新实现
过期逻辑）。

隔离纪律（务必遵守，详见本目录 README）：
- 每个 T-ID 独立 `tempfile.mkdtemp` 控制面根，同时设 `AGENT_CONTROL_PLANE_ROOT` env **与**
  显式 `--root` 参数（双保险；`agent_name_set.py` 的状态注册只认 env，四个核心脚本的 CLI
  只认 `--root`，两者都设不遗漏任一路径）。
- **绝不**在真实 `memory/agents/` / `memory/mailbox/` / `memory/agents-roster.md` /
  `.agent-identity` 上做任何写测试。T-G4-7 涉及 `.claude/hooks/agent_name_set.py` 的 roster
  逻辑——该脚本的 roster 路径是硬编码到真实 worktree 根的全局变量，没有 env override；本
  driver 用它自己 `_self_test()` 同款手法（importlib 载入新鲜模块实例 + 猴补 `mod.ROSTER`
  指向隔离临时文件）隔离测试，绝不调用会写 `.agent-identity` 的自命名主路径。
- 全程不碰 `lab/data/`、`lab/runs/`、`lab/models/` 等受保护路径，不启停任何训练/远端作业。

用法：
  python3 lab/evals/control-plane/run-g4-scenario.py

输出落 `lab/docs/audits/qualification/report-g4.{json,md}`（与 issue #54 的 A 层 qualification
runner 复用同一输出目录、同构证据形态：机器可读 JSON + Markdown 摘要，含被测 commit sha）。

UNAVAILABLE 语义：若某 T-ID 依赖的外部二进制在本机不可用（如 `paseo` CLI 缺失，且该 T-ID 的
负例场景恰好*需要*可用的 `paseo` 来证明"有 paseo 时也不 raise"这一分支），该子断言标记
`UNAVAILABLE`（而非伪造 PASS 或静默跳过）；若仅仅是"缺 paseo → 优雅降级"本身就是待证的负例，
则缺失环境反而是天然负例 fixture，不算 UNAVAILABLE。
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SCRIPTS = REPO / "scripts"
HOOKS = REPO / ".claude" / "hooks"
OUT_DIR = REPO / "lab" / "docs" / "audits" / "qualification"

A = "干将·改·g4demo-A"
B = "师爷·审·g4demo-B"
C = "干将·改·g4demo-C"


# --------------------------------------------------------------------- module reuse


def _load(rel: str, modname: str):
    spec = importlib.util.spec_from_file_location(modname, REPO / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


AS = _load("scripts/agent-state.py", "_g4_agent_state")


# --------------------------------------------------------------------- isolated root


@contextmanager
def isolated_root(label: str):
    root = Path(tempfile.mkdtemp(prefix=f"g4-{label}-"))
    try:
        yield root
    finally:
        shutil.rmtree(root, ignore_errors=True)


def run(rel_script: str, args: list, root: Path, extra_env: dict | None = None,
        timeout: int = 30) -> subprocess.CompletedProcess:
    """跑真实 CLI subprocess，隔离根双保险：env AGENT_CONTROL_PLANE_ROOT + 显式 --root。"""
    env = os.environ.copy()
    env["AGENT_CONTROL_PLANE_ROOT"] = str(root)
    env.pop("AGENT_NAME", None)
    if extra_env:
        env.update(extra_env)
    cmd = [sys.executable, str(SCRIPTS / rel_script), *args]
    if "--root" not in args:
        cmd += ["--root", str(root)]
    return subprocess.run(cmd, cwd=str(REPO), capture_output=True, text=True,
                           timeout=timeout, env=env)


def tail(text: str, n: int = 15) -> str:
    lines = text.strip("\n").splitlines()
    return "\n".join(lines[-n:])


# --------------------------------------------------------------------- result shape


def outcome(ok: bool, evidence: str, **extra) -> dict:
    out = {"ok": ok, "evidence": evidence}
    out.update(extra)
    return out


def make_result(tid: str, promise: str, positive: dict, negative: dict, notes: str) -> dict:
    status = "PASS" if positive["ok"] and negative["ok"] else "FAIL"
    if positive.get("unavailable") or negative.get("unavailable"):
        status = "UNAVAILABLE"
    return {
        "id": tid, "promise": promise, "status": status,
        "positive": positive, "negative": negative, "notes": notes,
    }


# --------------------------------------------------------------------- T-G4-1


def t_g4_1() -> dict:
    tid = "T-G4-1"
    with isolated_root("1") as root:
        p1 = run("agent-state.py", ["register", A, "--task", "G4 demo A", "--root", str(root)], root)
        p2 = run("agent-state.py", ["register", B, "--task", "G4 demo B", "--root", str(root)], root)
        p3 = run("agent-state.py", ["heartbeat", A, "--root", str(root)], root)
        p4 = run("agent-status.py", ["--no-paseo", "--json", "--root", str(root)], root)
        entries = {e["name"]: e for e in json.loads(p4.stdout or "[]")}
        pos_ok = (
            p1.returncode == 0 and p2.returncode == 0 and p3.returncode == 0 and p4.returncode == 0
            and entries.get(A, {}).get("status") == "active"
            and entries.get(B, {}).get("status") == "active"
        )
        positive = outcome(pos_ok, tail(p4.stdout),
                            register_A=p1.returncode, register_B=p2.returncode,
                            heartbeat=p3.returncode, statuses={k: v["status"] for k, v in entries.items()})

        # 负例：TTL→stale 派生。CLI 无 --now 开关，直接复用 register() 的库函数把心跳
        # 时间戳设成 31 分钟前（TTL 默认 30 分钟）——同一份产线代码，不是重新实现过期逻辑。
        before = AS.load_state(root, A) or {}
        stored_status_before = before.get("status")
        AS.register(root, A, now=time.time() - 31 * 60)
        p5 = run("agent-status.py", ["--no-paseo", "--json", "--root", str(root)], root)
        entries2 = {e["name"]: e for e in json.loads(p5.stdout or "[]")}
        after = AS.load_state(root, A) or {}
        derived_stale = entries2.get(A, {}).get("status") == "stale"
        stored_unchanged = after.get("status") == stored_status_before
        neg_ok = p5.returncode == 0 and derived_stale and stored_unchanged
        negative = outcome(neg_ok, tail(p5.stdout),
                            derived_status=entries2.get(A, {}).get("status"),
                            stored_status_before=stored_status_before,
                            stored_status_after=after.get("status"))
    return make_result(
        tid, "register/heartbeat/TTL→stale 派生",
        positive, negative,
        "正例：A/B register 后心跳内 → active。负例：直接复用 agent-state.py 的 register(now=...) "
        "库函数把 A 心跳时间戳设成 31 分钟前（TTL=30），agent-status.py 派生显示 stale，同时校验"
        "磁盘上 status 存储字段本身未被改写（派生不落盘）。",
    )


# --------------------------------------------------------------------- T-G4-2


def t_g4_2() -> dict:
    tid = "T-G4-2"
    with isolated_root("2") as root:
        run("agent-state.py", ["register", A, "--task", "demo A"], root)
        run("agent-state.py", ["register", B, "--task", "demo B"], root)

        p_send = run("agent-mailbox.py", ["send", "--from", A, "--to", B, "--kind", "info",
                                           "--summary", "进度更新", "--no-notify"], root)
        p_inbox = run("agent-mailbox.py", ["inbox", B, "--unread", "--json"], root)
        msgs = json.loads(p_inbox.stdout or "[]")
        msg_id = msgs[0]["id"] if msgs else None
        p_mark = run("agent-mailbox.py", ["mark-read", B, "--id", msg_id or ""], root) if msg_id else None
        p_inbox2 = run("agent-mailbox.py", ["inbox", B, "--unread", "--json"], root)
        msgs2 = json.loads(p_inbox2.stdout or "[]")
        pos_ok = (
            p_send.returncode == 0 and p_inbox.returncode == 0 and len(msgs) == 1
            and msg_id is not None and p_mark is not None and p_mark.returncode == 0
            and len(msgs2) == 0
        )
        positive = outcome(pos_ok, tail(p_mark.stdout if p_mark else p_inbox.stdout),
                            sent_id=msg_id, unread_before=len(msgs), unread_after=len(msgs2))

        # 负例 a：decision 不带 --ref → 拒绝
        p_no_ref = run("agent-mailbox.py", ["send", "--from", A, "--to", B, "--kind", "decision",
                                             "--summary", "关键决定", "--no-notify"], root)
        no_ref_rejected = p_no_ref.returncode != 0 and "ref" in (p_no_ref.stderr or "")

        # 负例 b：ref 经 .. 逃逸控制面根 → 拒绝
        p_escape = run("agent-mailbox.py", ["send", "--from", A, "--to", B, "--kind", "decision",
                                             "--summary", "逃逸决定", "--ref", "../outside.md",
                                             "--no-notify"], root)
        escape_rejected = p_escape.returncode != 0 and "逃逸" in (p_escape.stderr or "")

        # 负例 c：ref 绝对路径（即使目标真实存在于控制面根内）→ 拒绝
        real_doc = root / "memory" / "handoffs" / "demo.md"
        real_doc.parent.mkdir(parents=True, exist_ok=True)
        real_doc.write_text("# demo\n", encoding="utf-8")
        p_abs = run("agent-mailbox.py", ["send", "--from", A, "--to", B, "--kind", "decision",
                                          "--summary", "绝对路径决定", "--ref", str(real_doc),
                                          "--no-notify"], root)
        abs_rejected = p_abs.returncode != 0 and "绝对路径" in (p_abs.stderr or "")

        neg_ok = no_ref_rejected and escape_rejected and abs_rejected
        negative = outcome(neg_ok,
                            f"no_ref: {tail(p_no_ref.stderr)}\nescape: {tail(p_escape.stderr)}\n"
                            f"abs: {tail(p_abs.stderr)}",
                            no_ref_rejected=no_ref_rejected, escape_rejected=escape_rejected,
                            abs_rejected=abs_rejected)
    return make_result(
        tid, "mailbox send/read + decision/handoff 强制 ref 落盘",
        positive, negative,
        "正例：A→B info send，B inbox 读到未读消息、mark-read 后未读清零。负例三路：decision 不带 "
        "--ref 拒绝；ref 经 `..` 逃逸控制面根拒绝；ref 绝对路径拒绝（即使目标文件真实存在于控制面"
        "根内——只认控制面 repo 内相对路径）。",
    )


# --------------------------------------------------------------------- T-G4-3


def t_g4_3() -> dict:
    tid = "T-G4-3"
    with isolated_root("3") as root:
        doc = root / "memory" / "handoffs" / "20260717-g4-demo.md"
        doc.parent.mkdir(parents=True, exist_ok=True)
        doc.write_text("# G4 demo handoff\n", encoding="utf-8")
        ref = "memory/handoffs/20260717-g4-demo.md"

        # 正例：A 精确 owned 一个文件（非目录）→ handoff → ack 前 ownership 不转移 → ack →
        # 转移 + A 收到 ack 回执
        run("agent-state.py", ["register", A, "--task", "维护 detail",
                                "--owned", "shared/detail.txt"], root)
        run("agent-state.py", ["register", B, "--task", "待接手"], root)
        p_ho = run("agent-mailbox.py", ["handoff", "--from", A, "--to", B,
                                         "--task", "接手 shared/detail.txt", "--ref", ref,
                                         "--paths", "shared/detail.txt", "--no-notify"], root)
        # 解析 handoff msg id（从 B 的 inbox 里取最后一条 handoff）
        inbox_before = json.loads(run("agent-mailbox.py", ["inbox", B, "--json"], root).stdout or "[]")
        ho_msg = next((m for m in inbox_before if m.get("kind") == "handoff"), None)
        ho_id = ho_msg["id"] if ho_msg else None

        a_before = AS.load_state(root, A) or {}
        b_before = AS.load_state(root, B) or {}
        ownership_unmoved_before_ack = (
            "shared/detail.txt" in (a_before.get("owned_paths") or [])
            and "shared/detail.txt" not in (b_before.get("owned_paths") or [])
        )

        p_ack = run("agent-mailbox.py", ["ack", B, "--id", ho_id or "", "--no-notify"], root) \
            if ho_id else None
        a_after = AS.load_state(root, A) or {}
        b_after = AS.load_state(root, B) or {}
        ownership_moved_after_ack = (
            "shared/detail.txt" not in (a_after.get("owned_paths") or [])
            and "shared/detail.txt" in (b_after.get("owned_paths") or [])
        )
        a_inbox = json.loads(run("agent-mailbox.py", ["inbox", A, "--json"], root).stdout or "[]")
        a_got_receipt = any(m.get("kind") == "ack" and m.get("from") == B for m in a_inbox)

        pos_ok = (
            p_ho.returncode == 0 and ho_id is not None and ownership_unmoved_before_ack
            and p_ack is not None and p_ack.returncode == 0
            and ownership_moved_after_ack and a_got_receipt
        )
        positive = outcome(pos_ok, tail((p_ack.stdout if p_ack else "") + p_ho.stdout),
                            ownership_unmoved_before_ack=ownership_unmoved_before_ack,
                            ownership_moved_after_ack=ownership_moved_after_ack,
                            a_got_receipt=a_got_receipt)

        # 负例：C 只拥有父目录 shared/，想转移子文件 shared/detail.txt → ack 拒绝、消息保持 pending
        run("agent-state.py", ["register", C, "--task", "只有父目录",
                                "--owned", "shared/"], root)
        p_ho2 = run("agent-mailbox.py", ["handoff", "--from", C, "--to", B,
                                          "--task", "尝试转移子文件", "--ref", ref,
                                          "--paths", "shared/detail.txt", "--no-notify"], root)
        inbox2 = json.loads(run("agent-mailbox.py", ["inbox", B, "--json"], root).stdout or "[]")
        ho2 = next((m for m in inbox2 if m.get("kind") == "handoff" and m.get("from") == C), None)
        ho2_id = ho2["id"] if ho2 else None
        p_ack2 = run("agent-mailbox.py", ["ack", B, "--id", ho2_id or "", "--no-notify"], root) \
            if ho2_id else None
        ack2_rejected = p_ack2 is not None and p_ack2.returncode != 0 and "目录" in (p_ack2.stderr or "")
        inbox2_after = json.loads(run("agent-mailbox.py", ["inbox", B, "--json"], root).stdout or "[]")
        ho2_after = next((m for m in inbox2_after if m["id"] == ho2_id), None)
        stayed_pending = ho2_after is not None and ho2_after.get("state") == "pending"
        c_after = AS.load_state(root, C) or {}
        c_unchanged = "shared/" in (c_after.get("owned_paths") or [])

        neg_ok = p_ho2.returncode == 0 and ack2_rejected and stayed_pending and c_unchanged
        negative = outcome(neg_ok, tail(p_ack2.stderr if p_ack2 else ""),
                            ack2_rejected=ack2_rejected, stayed_pending=stayed_pending,
                            c_unchanged=c_unchanged)
    return make_result(
        tid, "handoff ack 前 ownership 不转移 + 精确路径匹配拒绝",
        positive, negative,
        "正例：A 先 register 明细 owned_path（文件级，非目录）→ handoff → ack 前查 A/B 状态确认未"
        "转移 → B ack → 转移进 B + A 收到 ack 回执。负例：C 只拥有父目录 shared/、想转移其子文件"
        "shared/detail.txt → ack 拒绝（不做目录所有权分裂）、消息保持 pending、C 的 owned_paths "
        "不变。",
    )


# --------------------------------------------------------------------- T-G4-4


def t_g4_4() -> dict:
    tid = "T-G4-4"
    with isolated_root("4-pos") as root:
        run("agent-state.py", ["register", A, "--task", "改 core", "--owned", "src/core/"], root)
        run("agent-state.py", ["register", B, "--task", "也改 core",
                                "--owned", "src/core/db.py"], root)
        p_scan = run("check-agent-conflicts.py", ["scan", "--json"], root)
        overlaps = json.loads(p_scan.stdout or "[]")
        pos_ok = p_scan.returncode == 1 and len(overlaps) == 1
        positive = outcome(pos_ok, tail(p_scan.stdout), overlaps=overlaps, exit_code=p_scan.returncode)

    with isolated_root("4-neg") as root:
        run("agent-state.py", ["register", A, "--task", "改 core", "--owned", "src/core/"], root)
        run("agent-state.py", ["register", B, "--task", "改别处", "--owned", "src/other/"], root)
        p_scan2 = run("check-agent-conflicts.py", ["scan", "--json"], root)
        overlaps2 = json.loads(p_scan2.stdout or "[]")
        neg_ok = p_scan2.returncode == 0 and overlaps2 == []
        negative = outcome(neg_ok, tail(p_scan2.stdout), overlaps=overlaps2, exit_code=p_scan2.returncode)
    return make_result(
        tid, "check-agent-conflicts scan（重叠→报警，无重叠→clean）",
        positive, negative,
        "正例：A owned src/core/、B owned src/core/db.py（目录 vs 子文件）→ scan 检出 1 处重叠、"
        "exit=1。负例：A/B 各自 owned 互不相交路径 → scan 干净、exit=0。",
    )


# --------------------------------------------------------------------- T-G4-5


def t_g4_5() -> dict:
    tid = "T-G4-5"
    with isolated_root("5") as root:
        actual = root / "actual-toplevel"
        actual.mkdir()
        run("agent-state.py", ["register", A, "--worktree", str(actual)], root)
        p_pos = run("check-agent-conflicts.py",
                    ["worktree", "--name", A, "--actual-toplevel", str(actual)], root)
        pos_ok = p_pos.returncode == 0 and "一致" in p_pos.stdout
        positive = outcome(pos_ok, tail(p_pos.stdout))

        elsewhere = root / "elsewhere"
        elsewhere.mkdir()
        run("agent-state.py", ["register", A, "--worktree", str(elsewhere)], root)
        p_neg = run("check-agent-conflicts.py",
                    ["worktree", "--name", A, "--actual-toplevel", str(actual)], root)
        neg_ok = (p_neg.returncode != 0 and "写错 worktree" in p_neg.stderr
                  and str(elsewhere) in p_neg.stderr)
        negative = outcome(neg_ok, tail(p_neg.stderr))
    return make_result(
        tid, "worktree 声明 vs 实际 toplevel 检测",
        positive, negative,
        "正例：declared worktree == 实际 toplevel → clean。负例：把 A 的 declared worktree 改成"
        "另一目录（elsewhere），传入不同的 --actual-toplevel → 报错并点名两个具体路径。",
    )


# --------------------------------------------------------------------- T-G4-6


def t_g4_6() -> dict:
    tid = "T-G4-6"
    with isolated_root("6") as root:
        run("agent-state.py", ["register", A, "--task", "demo A"], root)
        run("agent-state.py", ["register", B, "--task", "demo B"], root)
        run("agent-mailbox.py", ["send", "--from", A, "--to", B, "--kind", "info",
                                  "--summary", "hi", "--no-notify"], root)

        p_pos = run("agent-status.py", ["--no-paseo", "--json", "--root", str(root)], root)
        entries = {e["name"]: e for e in json.loads(p_pos.stdout or "[]")}
        pos_ok = (
            p_pos.returncode == 0
            and entries.get(A, {}).get("status") == "active"
            and entries.get(B, {}).get("unread_inbox", 0) == 1
            and entries.get(A, {}).get("heartbeat") is not None
            and entries.get(A, {}).get("paseo_presence") == "unknown(no-paseo)"
        )
        positive = outcome(pos_ok, tail(p_pos.stdout),
                            unread_B=entries.get(B, {}).get("unread_inbox"))

        # 负例分支 a：agent 未登记 paseo_id，但环境里 paseo CLI 真实可用（默认带 paseo 交叉校验）
        # → presence 优雅降级为 "-"，不 raise。
        p_no_pid = run("agent-status.py", ["--json", "--root", str(root)], root)
        entries_no_pid = {e["name"]: e for e in json.loads(p_no_pid.stdout or "[]")}
        no_pid_ok = (p_no_pid.returncode == 0
                     and entries_no_pid.get(A, {}).get("paseo_presence") == "-")

        # 负例分支 b：PATH 里去掉 paseo 二进制，模拟"缺 Paseo"→ 全部 presence 降级为
        # unknown(no-paseo)，不 raise。
        stripped_path = "/usr/bin:/bin"
        p_no_cli = run("agent-status.py", ["--json", "--root", str(root)], root,
                       extra_env={"PATH": stripped_path})
        entries_no_cli = {e["name"]: e for e in json.loads(p_no_cli.stdout or "[]")}
        no_cli_ok = (p_no_cli.returncode == 0
                     and all(e.get("paseo_presence") == "unknown(no-paseo)"
                             for e in entries_no_cli.values()))

        neg_ok = no_pid_ok and no_cli_ok
        negative = outcome(neg_ok,
                            f"no_pid presence={entries_no_pid.get(A, {}).get('paseo_presence')}\n"
                            f"no_cli presences="
                            f"{[e.get('paseo_presence') for e in entries_no_cli.values()]}",
                            no_pid_ok=no_pid_ok, no_cli_ok=no_cli_ok)
    return make_result(
        tid, "agent-status 聚合视图（±Paseo 降级）",
        positive, negative,
        "正例：--no-paseo 纯 repo 视图列出 A/B 的 status/heartbeat/unread。负例两分支：(a) 本机"
        "真实 paseo CLI 可用但 agent 未登记 paseo_id → presence='-'，不 raise；(b) PATH 剥掉 "
        "paseo 二进制模拟缺 Paseo → 全体 presence 降级为 unknown(no-paseo)，exit 仍为 0。",
    )


# --------------------------------------------------------------------- T-G4-7


def _load_agent_name_set():
    return _load(".claude/hooks/agent_name_set.py", "_g4_agent_name_set")


def t_g4_7() -> dict:
    tid = "T-G4-7"
    mod = _load_agent_name_set()
    with isolated_root("7") as root:
        roster_path = root / "memory" / "agents-roster.md"
        mod.ROSTER = roster_path  # 猴补：与 agent_name_set.py 自身 _self_test() 同款隔离手法
        os.environ["AGENT_CONTROL_PLANE_ROOT"] = str(root)
        try:
            # 正例 a：--register 子 agent 模式重复调用 → roster 幂等（不重复行）
            mod._register_child(C, "pid-g4-7", "demo-branch (wt)")
            mod._register_child(C, "pid-g4-7", "demo-branch (wt)")
            rows1 = [ln for ln in roster_path.read_text(encoding="utf-8").splitlines()
                     if ln.startswith("|") and not ln.startswith(("| name ", "| ---"))]
            idempotent_ok = len(rows1) == 1

            # 正例 b："改名"：同 paseo-id、新名字字符串 → roster 按 paseo-id 去重，行被替换
            # （而非追加），体现"改名后 roster 一致"。
            renamed = "干将·改·g4demo-C改名"
            mod._register_child(renamed, "pid-g4-7", "demo-branch (wt)")
            rows2 = [ln for ln in roster_path.read_text(encoding="utf-8").splitlines()
                     if ln.startswith("|") and not ln.startswith(("| name ", "| ---"))]
            row2_cols = [c.strip() for c in rows2[0].strip("|").split("|")] if rows2 else []
            rename_ok = (len(rows2) == 1 and row2_cols and row2_cols[0] == renamed
                         and row2_cols[0] != C)
            renamed_state = AS.load_state(root, renamed)
            renamed_state_ok = renamed_state is not None and renamed_state.get("paseo_id") == "pid-g4-7"

            pos_ok = idempotent_ok and rename_ok and renamed_state_ok
            positive = outcome(pos_ok, "\n".join(rows2),
                                idempotent_ok=idempotent_ok, rename_ok=rename_ok,
                                renamed_state_ok=renamed_state_ok)
        finally:
            os.environ.pop("AGENT_CONTROL_PLANE_ROOT", None)

    # 负例：非法（空）名字 → 脚本优雅 no-op（exit 0、不崩、不写任何文件），验证真实
    # .agent-identity / 真实 roster 字节不受影响（额外安全断言，不只是 exit code）。
    real_identity = REPO / ".agent-identity"
    real_roster = REPO / "memory" / "agents-roster.md"

    def _digest(p: Path) -> str:
        return hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else "missing"

    before_identity, before_roster = _digest(real_identity), _digest(real_roster)
    p_empty = subprocess.run([sys.executable, str(HOOKS / "agent_name_set.py"), ""],
                              cwd=str(REPO), capture_output=True, text=True, timeout=15)
    after_identity, after_roster = _digest(real_identity), _digest(real_roster)
    graceful = (p_empty.returncode == 0 and "未改动" in (p_empty.stderr or "")
                and before_identity == after_identity and before_roster == after_roster)
    negative = outcome(graceful, tail(p_empty.stderr),
                        exit_code=p_empty.returncode,
                        real_files_untouched=(before_identity == after_identity
                                               and before_roster == after_roster))
    return make_result(
        tid, "roster/identity（agent_name_set 幂等/改名）",
        positive, negative,
        "正例：`_register_child`（--register 子 agent 模式的库函数，猴补 ROSTER 到隔离路径，"
        "与脚本自身 --self-test 同款手法）重复调用幂等；同 paseo-id 换名字模拟改名 → roster 行"
        "原位替换（非追加），状态 yaml 随新名字一致存在。负例：空名字调用真实 CLI（该路径本就"
        "在写任何文件前提前返回）→ exit 0 优雅提示，且验证真实 .agent-identity/roster 字节"
        "前后不变（未被误触碰）。已知边界（如实记录、非缺陷）：控制面没有统一 rename 原语，"
        "改名后旧名字对应的状态 yaml 不会被自动清理/合并，只是不再被 roster 引用。",
    )


# --------------------------------------------------------------------- rendering


def render_markdown(payload: dict) -> str:
    meta = payload["meta"]
    lines = [
        "# G4 control-plane scenario report",
        "",
        f"- 被测 commit：`{meta['commit']}`",
        f"- 生成时间：{meta['generated_at']}",
        f"- 生成时工作树是否 dirty：{meta['worktree_dirty']}",
        f"- 结果：{meta['counts']['pass']}/{meta['counts']['total']} PASS"
        f"（self-test backstop：{meta['self_test']['total_assertions']} 项全部通过，"
        f"覆盖 {meta['self_test']['scripts']} 个脚本）",
        "",
        "| T-ID | promise | status |",
        "| --- | --- | --- |",
    ]
    for r in payload["results"]:
        lines.append(f"| {r['id']} | {r['promise']} | {r['status']} |")
    lines.append("")
    lines.append("## self-test backstop")
    lines.append("")
    lines.append("| script | ok assertions | exit |")
    lines.append("| --- | --- | --- |")
    for s in meta["self_test"]["detail"]:
        lines.append(f"| `{s['script']}` | {s['ok_count']} | {s['exit_code']} |")
    lines.append("")
    lines.append("## 逐项证据")
    for r in payload["results"]:
        lines.append(f"\n### {r['id']} — {r['status']}\n")
        lines.append(f"- promise: {r['promise']}")
        lines.append(f"- notes: {r['notes']}")
        lines.append(f"- positive: ok={r['positive']['ok']}")
        lines.append("```\n" + r["positive"]["evidence"] + "\n```")
        lines.append(f"- negative: ok={r['negative']['ok']}")
        lines.append("```\n" + r["negative"]["evidence"] + "\n```")
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------- self-test backstop


SELF_TEST_SCRIPTS = [
    ("scripts/agent-state.py", None),
    ("scripts/agent-mailbox.py", None),
    ("scripts/agent-status.py", None),
    ("scripts/check-agent-conflicts.py", None),
    (".claude/hooks/agent_name_set.py", None),
]


def run_self_tests() -> dict:
    detail = []
    for rel, _ in SELF_TEST_SCRIPTS:
        proc = subprocess.run([sys.executable, str(REPO / rel), "--self-test"],
                               cwd=str(REPO), capture_output=True, text=True, timeout=60)
        out = proc.stdout + proc.stderr
        ok_count = out.count("\n  ok ") + (1 if out.startswith("  ok ") else 0)
        detail.append({"script": rel, "exit_code": proc.returncode, "ok_count": ok_count,
                        "all_pass": proc.returncode == 0 and "FAIL" not in out})
    return {
        "scripts": len(detail),
        "total_assertions": sum(d["ok_count"] for d in detail),
        "all_pass": all(d["all_pass"] for d in detail),
        "detail": detail,
    }


# --------------------------------------------------------------------- main


def commit_sha() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO,
                           capture_output=True, text=True, check=True).stdout.strip()


def worktree_dirty() -> bool:
    out = subprocess.run(["git", "status", "--porcelain"], cwd=REPO,
                          capture_output=True, text=True, check=True).stdout
    return bool(out.strip())


def main() -> int:
    self_test = run_self_tests()
    for d in self_test["detail"]:
        print(f"[g4] self-test {d['script']}: {d['ok_count']} ok, exit={d['exit_code']}", flush=True)

    checks = [t_g4_1, t_g4_2, t_g4_3, t_g4_4, t_g4_5, t_g4_6, t_g4_7]
    results = []
    for fn in checks:
        result = fn()
        print(f"[g4] {result['id']} {result['status']}", flush=True)
        results.append(result)

    n_pass = sum(1 for r in results if r["status"] == "PASS")
    payload = {
        "meta": {
            "commit": commit_sha(),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "worktree_dirty": worktree_dirty(),
            "runner": "lab/evals/control-plane/run-g4-scenario.py",
            "self_test": self_test,
            "counts": {"total": len(results), "pass": n_pass, "fail": len(results) - n_pass},
        },
        "results": results,
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = OUT_DIR / "report-g4.json"
    md_path = OUT_DIR / "report-g4.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                          encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")

    print(f"[g4] {n_pass}/{len(results)} PASS —— {json_path.relative_to(REPO)}")
    return 0 if n_pass == len(results) and self_test["all_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
