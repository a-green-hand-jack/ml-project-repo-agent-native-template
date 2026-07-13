#!/usr/bin/env python3
"""agent-mailbox —— agent 间消息与 ownership handoff 的 repo 落盘层（issue #14）。

schema 见 `.agent/multi-agent-control-plane.md`。落盘粒度（human 拍板 2026-07-12）：
每个 agent 一对 `memory/mailbox/<name>/inbox.md` + `outbox.md`（不是单一 append-only log）。
发送 = 写自己的 outbox + 追加对方的 inbox；inbox 副本是 read/state 的权威副本。

与 Paseo 的分工：`paseo send <id>` 只做低延迟**送达提醒**（复用 spawn skill 原语，缺 Paseo
优雅降级、不 raise）；本脚本负责「可恢复、可查」的结构化真相层——fresh session 只读 repo
文件即可恢复未读消息与任务归属。

回写规则（验收 #5）：`kind` 为 `decision` / `handoff` 的关键消息**必须**带 `--ref` 指向真实
存在的 repo 落盘文件（handoff 文档 / branch status / plan / decision），拒绝只留临时消息。
`--ref` 只认控制面 repo 内的相对路径：绝对路径、realpath 后逃逸控制面根（`..`/符号链接）
一律拒绝——外部文件不算落盘记录。

ownership handoff（验收 #1/#3 的一半）：`handoff` 发起（state: pending）→ 接收方 `ack`
（state: accepted），ack 时把 `--paths` 声明的 owned paths 从发起方转移给接收方、回执入
发起方 inbox——状态转移走 agent-state.py，冲突检测立即感知新 ownership。ack 前验证发起方
状态文件存在且**精确拥有**每条待转移路径（只拥有父目录不算——不做目录所有权分裂，先
register 拆细再 handoff）；任何一条不满足整个 ack 拒绝、消息保持 pending。

用法：
  python scripts/agent-mailbox.py send --from A --to B --kind info|question|decision|handoff|ack \
         --summary "..." [--ref path] [--root R] [--no-notify]
  python scripts/agent-mailbox.py inbox NAME [--unread] [--json] [--root R]
  python scripts/agent-mailbox.py mark-read NAME (--id MSGID | --all) [--root R]
  python scripts/agent-mailbox.py handoff --from A --to B --task "..." --ref path [--paths P ...] [--root R]
  python scripts/agent-mailbox.py ack NAME --id MSGID [--root R]
  python scripts/agent-mailbox.py --self-test
退出码 0 = 成功，1 = 失败（缺 ref / 找不到消息等）。
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
KINDS = ("info", "question", "decision", "handoff", "ack")
REF_REQUIRED_KINDS = ("decision", "handoff")  # 关键消息必须落盘 ref（验收 #5）
MSG_HEAD = re.compile(r"^## msg ", re.MULTILINE)


def _load_agent_state():
    spec = importlib.util.spec_from_file_location("agent_state", SCRIPTS_DIR / "agent-state.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


AS = _load_agent_state()


# ---------------------------------------------------------------- 消息块读写

def _msg_id(sender: str, to: str, summary: str, ts: str) -> str:
    return hashlib.sha1(f"{ts}|{sender}|{to}|{summary}".encode()).hexdigest()[:8]


def format_message(msg: dict) -> str:
    lines = [f"## msg {msg['id']} | {msg['kind']} | {msg['from']} → {msg['to']} | {msg['time']}"]
    for key in ("id", "kind", "from", "to", "time", "read", "state", "task", "paths", "ref", "summary"):
        if key in msg and msg[key] not in (None, ""):
            lines.append(f"- {key}: {msg[key]}")
    return "\n".join(lines) + "\n\n"


def parse_messages(text: str) -> list[dict]:
    msgs: list[dict] = []
    blocks = MSG_HEAD.split(text)
    for block in blocks[1:]:
        msg: dict = {}
        for line in block.splitlines()[1:]:
            m = re.match(r"^- (\w+): (.*)$", line.strip())
            if m:
                msg[m.group(1)] = m.group(2).strip()
            elif not line.startswith("-") and line.strip() == "":
                continue
            elif not line.strip().startswith("- "):
                break
        if msg.get("id"):
            msgs.append(msg)
    return msgs


def _append(path: Path, block: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(block)


def _rewrite_field(path: Path, msg_id: str, field: str, old: str, new: str) -> bool:
    """在 id 对应消息块内把 `- field: old` 改写为 `- field: new`。"""
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8", errors="replace")
    pattern = re.compile(
        rf"(## msg {re.escape(msg_id)} [^\n]*\n(?:- \w+: [^\n]*\n)*?- {field}: ){re.escape(old)}(\n)"
    )
    new_text, n = pattern.subn(rf"\g<1>{new}\g<2>", text, count=1)
    if n == 0:
        return False
    path.write_text(new_text, encoding="utf-8")
    return True


# ---------------------------------------------------------------- 发送 / 通知

def _norm_path(p: str) -> str:
    """路径归一化（与 check-agent-conflicts._norm 同形）：去引号、去 ./ 前缀、去尾随 /。"""
    p = str(p).strip().strip('"').strip("'")
    if p.startswith("./"):
        p = p[2:]
    return p.rstrip("/")


def _validate_ref(root: Path, ref: str) -> None:
    """--ref 只认控制面 repo 内真实存在的相对路径：拒绝绝对路径，拒绝 realpath 归一化后
    逃逸控制面根的路径（`..` / 符号链接）——防止外部文件（如 /etc/hosts）冒充落盘记录。"""
    if Path(ref).is_absolute():
        raise ValueError(f"--ref 拒绝绝对路径：{ref}（用控制面 repo 内的相对路径）")
    root_r = Path(root).resolve()
    try:
        target = (root_r / ref).resolve()
        target.relative_to(root_r)
    except ValueError:
        raise ValueError(f"--ref 逃逸控制面根（{root}）：{ref}") from None
    except OSError as exc:
        raise ValueError(f"--ref 无法解析：{ref}（{exc}）") from None
    if not target.is_file():
        raise ValueError(f"--ref 指向的文件不存在：{ref}（先落盘再发消息）")


def _paseo_notify(root: Path, to: str, summary: str) -> str:
    """低延迟提醒：复用 spawn skill 的 `paseo send <id>`。全程降级、不 raise。"""
    state = AS.load_state(root, to) or {}
    pid = str(state.get("paseo_id") or "").strip()
    if not pid or pid == "-":
        return "skip(no paseo_id)"
    if not shutil.which("paseo"):
        return "skip(no paseo cli)"
    try:
        r = subprocess.run(
            ["paseo", "send", pid, f"[mailbox] 新消息：{summary}（读 memory/mailbox/…/inbox.md）"],
            capture_output=True, text=True, timeout=10,
        )
        return "notified" if r.returncode == 0 else f"notify-failed(rc={r.returncode})"
    except (OSError, subprocess.SubprocessError):
        return "notify-failed(no paseo)"


def send(root: Path, sender: str, to: str, kind: str, summary: str,
         ref: str | None = None, task: str | None = None, paths: list[str] | None = None,
         state: str | None = None, notify: bool = True, now: float | None = None) -> dict:
    if kind not in KINDS:
        raise ValueError(f"非法 kind {kind!r}，可选：{'/'.join(KINDS)}")
    if kind in REF_REQUIRED_KINDS:
        if not ref:
            raise ValueError(f"kind={kind} 是关键消息，必须 --ref 指向 repo 落盘记录（验收 #5）")
        _validate_ref(root, ref)
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now if now is not None else time.time()))
    msg = {
        "id": _msg_id(sender, to, summary, ts), "kind": kind, "from": sender, "to": to,
        "time": ts, "read": "no", "summary": summary,
    }
    if ref:
        msg["ref"] = ref
    if task:
        msg["task"] = task
    if paths:
        msg["paths"] = ", ".join(paths)
    if state:
        msg["state"] = state
    block = format_message(msg)
    sender_inbox, sender_outbox = AS.ensure_mailbox(root, sender)
    to_inbox, _ = AS.ensure_mailbox(root, to)
    _append(sender_outbox, block)
    _append(to_inbox, block)
    msg["_notify"] = _paseo_notify(root, to, summary) if notify else "skip(--no-notify)"
    return msg


def read_inbox(root: Path, name: str, unread_only: bool = False) -> list[dict]:
    inbox = AS.mailbox_dir(root, name) / "inbox.md"
    if not inbox.is_file():
        return []
    msgs = parse_messages(inbox.read_text(encoding="utf-8", errors="replace"))
    if unread_only:
        msgs = [m for m in msgs if m.get("read") == "no"]
    return msgs


def mark_read(root: Path, name: str, msg_id: str | None = None) -> int:
    inbox = AS.mailbox_dir(root, name) / "inbox.md"
    targets = [m["id"] for m in read_inbox(root, name, unread_only=True)
               if msg_id is None or m["id"] == msg_id]
    return sum(1 for mid in targets if _rewrite_field(inbox, mid, "read", "no", "yes"))


# ---------------------------------------------------------------- handoff / ack

def initiate_handoff(root: Path, sender: str, to: str, task: str, ref: str,
                     paths: list[str] | None = None, notify: bool = True) -> dict:
    return send(root, sender, to, "handoff", f"ownership handoff：{task}",
                ref=ref, task=task, paths=paths, state="pending", notify=notify)


def _validate_transfer(initiator: str, ini_state: dict | None,
                       paths: list[str], msg_id: str) -> list[str]:
    """ack 前验证：每条待转移路径都能合法、完整地从发起方 owned_paths 移出。
    发起方必须**精确拥有**该条目（归一化后逐条匹配）；发起方只拥有父目录时拒绝——
    不做目录所有权分裂（否则转移后目录与子文件立即重叠），先让发起方 register 拆细
    owned_paths 再 handoff（doctrine：`.agent/multi-agent-control-plane.md`）。
    返回发起方的原始 owned_paths 列表（供移除用）。"""
    if ini_state is None:
        raise ValueError(
            f"handoff {msg_id} 被拒：发起方「{initiator}」无状态文件（memory/agents/），"
            f"无法验证 ownership。先让发起方 python scripts/agent-state.py register 再重试"
        )
    owned = [str(p) for p in (ini_state.get("owned_paths") or [])]
    owned_norm = {_norm_path(p) for p in owned}
    problems: list[str] = []
    for p in paths:
        np = _norm_path(p)
        if np in owned_norm:
            continue
        parent = next((o for o in owned if np.startswith(_norm_path(o) + "/")), None)
        if parent:
            problems.append(f"{p}（发起方拥有的是目录 {parent}：不做目录所有权分裂，"
                            f"先让发起方 register 拆细 owned_paths 再 handoff）")
        else:
            problems.append(f"{p}（不在发起方 owned_paths 内）")
    if problems:
        raise ValueError(
            f"handoff {msg_id} 被拒：待转移路径无法从发起方「{initiator}」完整移出——"
            + "；".join(problems)
        )
    return owned


def ack_handoff(root: Path, name: str, msg_id: str, notify: bool = True) -> dict:
    """接收方确认：先验证 ownership 可合法转移，再 pending→accepted + 标已读 + 转移 + 回执。
    验证不过整个 ack 拒绝、消息保持 pending（修正发起方声明后可重试），不留重叠 ownership。"""
    msgs = [m for m in read_inbox(root, name) if m["id"] == msg_id and m.get("kind") == "handoff"]
    if not msgs:
        raise ValueError(f"inbox 里找不到 handoff 消息 id={msg_id}（agent={name}）")
    msg = msgs[0]
    if msg.get("state") != "pending":
        raise ValueError(f"handoff {msg_id} 状态是 {msg.get('state')!r}，只有 pending 可 ack")

    initiator = msg["from"]
    task = msg.get("task") or msg.get("summary", "")
    paths = [p.strip() for p in (msg.get("paths") or "").split(",") if p.strip()]
    # 先验证再改状态：任何一条转移不合法就拒绝 ack（消息保持 pending）。
    ini_owned: list[str] = []
    if paths:
        ini_owned = _validate_transfer(initiator, AS.load_state(root, initiator), paths, msg_id)

    inbox = AS.mailbox_dir(root, name) / "inbox.md"
    if not _rewrite_field(inbox, msg_id, "state", "pending", "accepted"):
        raise ValueError(f"改写 handoff {msg_id} 状态失败")
    _rewrite_field(inbox, msg_id, "read", "no", "yes")

    # ownership 转移：发起方 owned_paths 移除、接收方并入；任务归属写进接收方状态文件。
    if paths:
        moved = {_norm_path(p) for p in paths}
        remaining = [p for p in ini_owned if _norm_path(p) not in moved]
        AS.register(root, initiator, owned=remaining)
    recv_state = AS.load_state(root, name) or {}
    merged = list(dict.fromkeys((recv_state.get("owned_paths") or []) + paths))
    AS.register(root, name, task=task or None, owned=merged)

    receipt = send(root, name, initiator, "ack",
                   f"已接手：{task}（handoff {msg_id} accepted）", notify=notify)
    return {"handoff": msg_id, "accepted_by": name, "paths": paths, "receipt": receipt["id"]}


# ---------------------------------------------------------------- self-test

def _self_test() -> int:  # noqa: PLR0915
    failures: list[str] = []

    def check(cond: bool, label: str) -> None:
        print(("  ok    " if cond else "  FAIL  ") + label)
        if not cond:
            failures.append(label)

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        a, b = "干将·改·alpha", "师爷·审·beta"
        AS.register(root, a, task="实现", owned=["src/a/", "docs/a.md"])
        AS.register(root, b, task="审查", owned=["reviews/"])

        msg = send(root, a, b, "info", "进度：schema 落地", notify=False)
        out_a = (AS.mailbox_dir(root, a) / "outbox.md").read_text(encoding="utf-8")
        in_b = (AS.mailbox_dir(root, b) / "inbox.md").read_text(encoding="utf-8")
        check(msg["id"] in out_a, "send → 发送方 outbox 落盘")
        check(msg["id"] in in_b, "send → 接收方 inbox 落盘")
        check(read_inbox(root, b, unread_only=True)[0]["summary"] == "进度：schema 落地",
              "inbox 可解析未读消息")

        # 回写规则（验收 #5）：decision/handoff 必须带真实 ref
        try:
            send(root, a, b, "decision", "关键决定", notify=False)
            check(False, "decision 无 ref 应拒绝")
        except ValueError:
            check(True, "decision 无 ref 应拒绝")
        try:
            send(root, a, b, "decision", "关键决定", ref="memory/branches/nonexistent.md", notify=False)
            check(False, "decision ref 不存在应拒绝")
        except ValueError:
            check(True, "decision ref 不存在应拒绝")
        refdoc = root / "memory" / "handoffs" / "20260712-demo.md"
        refdoc.parent.mkdir(parents=True, exist_ok=True)
        refdoc.write_text("# handoff demo\n", encoding="utf-8")
        ok_msg = send(root, a, b, "decision", "关键决定已落盘",
                      ref="memory/handoffs/20260712-demo.md", notify=False)
        check(bool(ok_msg["id"]), "decision 带真实 ref 可发送")

        # [MAJOR-2 回归] ref 越界：绝对路径 / .. 逃逸控制面根一律拒绝（即使文件真实存在）
        try:
            send(root, a, b, "decision", "绝对路径 ref", ref=str(refdoc), notify=False)
            check(False, "ref 绝对路径应拒绝（即使文件在控制面根内且存在）")
        except ValueError as exc:
            check("绝对路径" in str(exc), "ref 绝对路径应拒绝（即使文件在控制面根内且存在）")
        try:
            send(root, a, b, "decision", "外部文件 ref", ref="/etc/hosts", notify=False)
            check(False, "ref 指向 repo 外绝对路径应拒绝")
        except ValueError:
            check(True, "ref 指向 repo 外绝对路径应拒绝")
        try:
            send(root, a, b, "decision", "逃逸 ref", ref="../outside.md", notify=False)
            check(False, "ref 经 .. 逃逸控制面根应拒绝")
        except ValueError as exc:
            check("逃逸" in str(exc), "ref 经 .. 逃逸控制面根应拒绝")
        try:
            send(root, a, b, "decision", "藏在中间的逃逸",
                 ref="memory/../../outside.md", notify=False)
            check(False, "ref 中段 .. 逃逸同样拒绝")
        except ValueError as exc:
            check("逃逸" in str(exc), "ref 中段 .. 逃逸同样拒绝")

        # mark-read
        n = mark_read(root, b, ok_msg["id"])
        check(n == 1, "mark-read 单条")
        unread = [m["id"] for m in read_inbox(root, b, unread_only=True)]
        check(ok_msg["id"] not in unread and msg["id"] in unread, "read 状态只翻转目标消息")

        # handoff：pending → ack accepted + ownership 转移 + 回执
        hmsg = initiate_handoff(root, a, b, task="接手 docs/a.md 维护",
                                ref="memory/handoffs/20260712-demo.md",
                                paths=["docs/a.md"], notify=False)
        check(read_inbox(root, b)[-1]["state"] == "pending", "handoff 初始 pending")
        result = ack_handoff(root, b, hmsg["id"], notify=False)
        accepted = [m for m in read_inbox(root, b) if m["id"] == hmsg["id"]][0]
        check(accepted["state"] == "accepted" and accepted["read"] == "yes",
              "ack → accepted + 已读")
        ini = AS.load_state(root, a) or {}
        recv = AS.load_state(root, b) or {}
        check("docs/a.md" not in (ini.get("owned_paths") or []), "发起方 owned path 已移除")
        check("docs/a.md" in (recv.get("owned_paths") or []), "接收方 owned path 已并入")
        check(recv.get("task") == "接手 docs/a.md 维护", "接收方 task 更新")
        back = [m for m in read_inbox(root, a) if m["kind"] == "ack"]
        check(len(back) == 1 and result["receipt"] == back[0]["id"], "发起方收到 ack 回执")
        try:
            ack_handoff(root, b, hmsg["id"], notify=False)
            check(False, "重复 ack 应拒绝")
        except ValueError:
            check(True, "重复 ack 应拒绝")

        # [MAJOR-1 回归] 转移发起方未拥有的路径 → 拒绝 ack、消息保持 pending、不并入接收方
        h2 = initiate_handoff(root, a, b, task="转移未拥有的路径",
                              ref="memory/handoffs/20260712-demo.md",
                              paths=["not-owned.md"], notify=False)
        try:
            ack_handoff(root, b, h2["id"], notify=False)
            check(False, "转移发起方未拥有的路径应拒绝")
        except ValueError as exc:
            check("owned_paths" in str(exc), "转移发起方未拥有的路径应拒绝")
        still = [m for m in read_inbox(root, b) if m["id"] == h2["id"]][0]
        check(still["state"] == "pending", "被拒的 handoff 保持 pending（可修正后重试）")
        check("not-owned.md" not in ((AS.load_state(root, b) or {}).get("owned_paths") or []),
              "被拒时接收方不并入任何路径")

        # [MAJOR-1 回归] 发起方拥有目录、转移其子文件 → 拒绝（不做目录所有权分裂）
        h3 = initiate_handoff(root, a, b, task="转移目录子文件",
                              ref="memory/handoffs/20260712-demo.md",
                              paths=["src/a/sub.md"], notify=False)
        try:
            ack_handoff(root, b, h3["id"], notify=False)
            check(False, "拥有目录、转移子文件应拒绝（否则留下目录/子文件重叠）")
        except ValueError as exc:
            check("目录" in str(exc) and "src/a/" in str(exc),
                  "拥有目录、转移子文件应拒绝（否则留下目录/子文件重叠）")
        check("src/a/" in ((AS.load_state(root, a) or {}).get("owned_paths") or []),
              "被拒时发起方目录 ownership 原样保留")

        # [MAJOR-1 回归] 发起方无状态文件 → 拒绝（无法验证 ownership）
        h4 = initiate_handoff(root, "幽灵·改·ghost", b, task="无状态发起方",
                              ref="memory/handoffs/20260712-demo.md",
                              paths=["ghost.md"], notify=False)
        try:
            ack_handoff(root, b, h4["id"], notify=False)
            check(False, "发起方无状态文件应拒绝")
        except ValueError as exc:
            check("状态文件" in str(exc), "发起方无状态文件应拒绝")

        # 重启恢复（验收 #2）：fresh 视角只读文件即可复述归属 + 未读
        fresh_states = AS.load_states(root)
        fresh_unread_a = read_inbox(root, a, unread_only=True)
        check(fresh_states[b].get("task") == "接手 docs/a.md 维护"
              and any(m["kind"] == "ack" for m in fresh_unread_a),
              "fresh session 仅凭 repo 文件恢复「谁拥有任务 + 未读消息」")

        # 通知降级：no paseo / no paseo_id 不 raise
        status = _paseo_notify(root, b, "x")
        check(status.startswith("skip") or status.startswith("notify-failed"),
              f"Paseo 通知优雅降级（{status}）")

    print(f"\nagent-mailbox self-test：{'全部通过' if not failures else f'{len(failures)} 项失败'}")
    return 1 if failures else 0


# ---------------------------------------------------------------- CLI

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--self-test", action="store_true")
    sub = ap.add_subparsers(dest="cmd")

    p_send = sub.add_parser("send")
    p_send.add_argument("--from", dest="sender", required=True)
    p_send.add_argument("--to", required=True)
    p_send.add_argument("--kind", required=True, choices=KINDS)
    p_send.add_argument("--summary", required=True)
    p_send.add_argument("--ref", default=None)
    p_send.add_argument("--root", default=None)
    p_send.add_argument("--no-notify", action="store_true")

    p_inbox = sub.add_parser("inbox")
    p_inbox.add_argument("name")
    p_inbox.add_argument("--unread", action="store_true")
    p_inbox.add_argument("--json", action="store_true")
    p_inbox.add_argument("--root", default=None)

    p_mark = sub.add_parser("mark-read")
    p_mark.add_argument("name")
    p_mark.add_argument("--id", dest="msg_id", default=None)
    p_mark.add_argument("--all", action="store_true")
    p_mark.add_argument("--root", default=None)

    p_ho = sub.add_parser("handoff")
    p_ho.add_argument("--from", dest="sender", required=True)
    p_ho.add_argument("--to", required=True)
    p_ho.add_argument("--task", required=True)
    p_ho.add_argument("--ref", required=True, help="handoff 落盘文档（如 memory/handoffs/<date>-<slug>.md）")
    p_ho.add_argument("--paths", nargs="*", default=None, help="要转移的 owned paths")
    p_ho.add_argument("--root", default=None)
    p_ho.add_argument("--no-notify", action="store_true")

    p_ack = sub.add_parser("ack")
    p_ack.add_argument("name")
    p_ack.add_argument("--id", dest="msg_id", required=True)
    p_ack.add_argument("--root", default=None)
    p_ack.add_argument("--no-notify", action="store_true")

    args = ap.parse_args()
    if args.self_test:
        return _self_test()
    if not args.cmd:
        ap.print_help()
        return 1
    root = Path(args.root) if getattr(args, "root", None) else AS.default_root()

    try:
        if args.cmd == "send":
            msg = send(root, args.sender, args.to, args.kind, args.summary,
                       ref=args.ref, notify=not args.no_notify)
            print(f"[mailbox] 已发送 {msg['id']}（{args.sender} → {args.to}，notify={msg['_notify']}）")
        elif args.cmd == "inbox":
            msgs = read_inbox(root, args.name, unread_only=args.unread)
            if args.json:
                print(json.dumps(msgs, ensure_ascii=False, indent=2))
            else:
                for m in msgs:
                    flag = " " if m.get("read") == "yes" else "*"
                    print(f"{flag} {m['id']} [{m.get('kind')}] {m.get('from')} → {m.get('to')} "
                          f"{m.get('time')}  {m.get('summary')}")
                if not msgs:
                    print("（无消息）")
        elif args.cmd == "mark-read":
            if not args.msg_id and not args.all:
                print("[mailbox] mark-read 需要 --id 或 --all", file=sys.stderr)
                return 1
            n = mark_read(root, args.name, None if args.all else args.msg_id)
            print(f"[mailbox] 已标记 {n} 条为已读")
        elif args.cmd == "handoff":
            msg = initiate_handoff(root, args.sender, args.to, args.task, args.ref,
                                   paths=args.paths, notify=not args.no_notify)
            print(f"[mailbox] handoff 已发起：{msg['id']}（pending，等待 {args.to} ack）")
        elif args.cmd == "ack":
            result = ack_handoff(root, args.name, args.msg_id,
                                 notify=not getattr(args, "no_notify", False))
            print(f"[mailbox] handoff {result['handoff']} accepted；"
                  f"转移 paths：{result['paths'] or '（无）'}；回执 {result['receipt']}")
    except ValueError as exc:
        print(f"[mailbox] 失败：{exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
