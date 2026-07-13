#!/usr/bin/env python3
"""local-fake 后端：用本地小进程模拟一个训练 job（零算力、零真实副作用）。

角色（plans/20260712-experiment-control-plane.zh.md 任务 C2）：给控制面 smoke 提供
「可启动 / 可查询 / 可 kill / 可 restart / 可人为制造异常」的被控对象。绝不触达真实
GPU / Slurm / RunAI。launch/kill/restart 子命令是 launch registry 登记的 human-gate
入口（见 registry.yaml gated_prefixes）；status 只读不设门禁。

workdir 布局（全部在 workdir 内，默认 /tmp/ml-template-fake-jobs/<run-id>）：
- status.json     进程状态（run_id / pid / state / heartbeat_at / config_sha256 / launch_args）
- job.log         模拟训练日志（worker 逐步追加）
- metrics.jsonl   模拟 metric 流（每步一行 JSON）
- checkpoints/    模拟 checkpoint（空文件 touch，不产生真实 bytes 体积）

异常注入（供 watcher smoke）：
- --fail-after N   第 N 步后写 NaN 错误日志并以 failed 退出
- --stall-after N  第 N 步后停止心跳/metrics/checkpoint 更新，但进程继续存活（模拟 stall）

安全约束：workdir 必须是无 symlink 的字面 `/tmp/.../<run-id>`，末级与 run-id 精确一致；
status 与 worker argv 也必须绑定同一 run/workdir。无法证明 worker 身份时 kill/restart
fail-closed；control lock 串行化 launch/kill/restart，signal 通过 pidfd 固定目标身份。
无第三方依赖。
"""
from __future__ import annotations

import argparse
import contextlib
import fcntl
import json
import os
import re
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
LITERAL_TMP = Path("/tmp")
DEFAULT_WORKROOT = LITERAL_TMP / "ml-template-fake-jobs"
RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
SAFE_WORKDIR_RE = re.compile(r"^/tmp/[A-Za-z0-9._/-]+$")

STATES = ("running", "done", "failed", "killed")


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def _sha256(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def _first_symlink(path: Path) -> Path | None:
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        if current.is_symlink():
            return current
    return None


def _check_workdir(workdir: Path, run_id: str) -> Path:
    """Fake jobs only use a literal-/tmp leaf named exactly after run_id."""
    if not RUN_ID_RE.fullmatch(run_id):
        raise SystemExit(f"[fake_job] 拒绝：非法 run-id {run_id!r}")
    candidate = Path(os.path.abspath(workdir.expanduser()))
    if candidate.name != run_id:
        raise SystemExit(
            f"[fake_job] 拒绝：workdir 末级 {candidate.name!r} 必须与 run-id {run_id!r} 一致"
        )
    symlink = _first_symlink(candidate)
    if symlink is not None:
        raise SystemExit(f"[fake_job] 拒绝：workdir 含 symlink component：{symlink}")
    resolved = candidate.resolve()
    if LITERAL_TMP not in candidate.parents or LITERAL_TMP not in resolved.parents:
        raise SystemExit(
            "[fake_job] 拒绝：workdir 必须在字面 /tmp 内且不得越界/落入 repo "
            f"受保护路径：{workdir}"
        )
    if not SAFE_WORKDIR_RE.fullmatch(str(candidate)):
        raise SystemExit(
            f"[fake_job] 拒绝：workdir 含不允许的字符（仅限 /tmp 下 ASCII path chars）：{workdir}"
        )
    return resolved


def _status_path(workdir: Path) -> Path:
    return workdir / "status.json"


def _read_status(workdir: Path, run_id: str) -> dict:
    workdir = _check_workdir(workdir, run_id)
    p = _status_path(workdir)
    if not p.exists():
        raise SystemExit(f"[fake_job] 找不到 status.json：{p}（run 未启动或 workdir 不对）")
    status = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(status, dict):
        raise SystemExit(f"[fake_job] 拒绝：status.json 不是 object：{p}")
    if status.get("run_id") != run_id:
        raise SystemExit(
            f"[fake_job] 拒绝：status.run_id={status.get('run_id')!r} 与请求 {run_id!r} 不一致"
        )
    recorded = status.get("workdir")
    if not isinstance(recorded, str) or Path(recorded) != workdir:
        raise SystemExit(
            f"[fake_job] 拒绝：status.workdir={recorded!r} 与安全 workdir {workdir} 不一致"
        )
    return status


def _write_status(workdir: Path, status: dict) -> None:
    p = _status_path(workdir)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(status, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(p)


@contextlib.contextmanager
def _control_lock(workdir: Path):
    """Serialize launch/kill/restart so two controllers cannot create or signal twice."""
    flags = os.O_CREAT | os.O_RDWR
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(workdir / ".control.lock", flags, 0o600)
    except OSError as exc:
        raise SystemExit(f"[fake_job] 拒绝：无法安全打开 control lock：{exc}") from exc
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        os.close(fd)


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except (ProcessLookupError, PermissionError):
        return False
    return True


def _worker_argv_matches(argv: list[str], run_id: str, workdir: Path) -> bool:
    """Require the exact trusted interpreter/script/action and a non-duplicated worker argv."""
    if len(argv) < 11:
        return False
    try:
        interpreter = Path(argv[0]).resolve(strict=True)
        script = Path(argv[1]).resolve()
    except (IndexError, OSError):
        return False
    if interpreter != Path(sys.executable).resolve() or script != Path(__file__).resolve():
        return False
    if argv[2] != "_worker" or (len(argv) - 3) % 2:
        return False
    allowed = {
        "--run-id", "--workdir", "--duration", "--interval",
        "--fail-after", "--stall-after", "--config",
    }
    values: dict[str, str] = {}
    for i in range(3, len(argv), 2):
        option = argv[i]
        if option not in allowed or option in values:
            return False
        values[option] = argv[i + 1]
    return (
        all(option in values for option in ("--run-id", "--workdir", "--duration", "--interval"))
        and values["--run-id"] == run_id
        and Path(values["--workdir"]) == workdir
    )


def _is_our_worker(pid: int, run_id: str, workdir: Path) -> bool:
    """防 pid 复用误杀：受信解释器/script/action/args 必须精确匹配。"""
    try:
        argv = [
            part.decode("utf-8", "replace")
            for part in Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0")
            if part
        ]
    except OSError:
        return False  # 无法证明身份时 fail-closed，绝不只凭 pid 存活就 kill。
    return _worker_argv_matches(argv, run_id, workdir)


# ---------------------------------------------------------------- worker ----


def cmd_worker(args: argparse.Namespace) -> int:
    workdir = _check_workdir(Path(args.workdir), args.run_id)
    log = workdir / "job.log"
    metrics = workdir / "metrics.jsonl"
    ckpt_dir = workdir / "checkpoints"
    ckpt_dir.mkdir(exist_ok=True)

    def append(path: Path, line: str) -> None:
        with path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")

    steps = max(1, int(args.duration / args.interval))
    append(log, f"[{_now()}] fake job {args.run_id} started (steps={steps})")
    stalled = False
    for step in range(1, steps + 1):
        time.sleep(args.interval)
        if args.fail_after and step > args.fail_after:
            append(log, f"[{_now()}] step {step}: RuntimeError: loss is NaN")
            status = _read_status(workdir, args.run_id)
            status.update(state="failed", ended_at=_now(), exit_reason="NaN loss (injected)")
            _write_status(workdir, status)
            return 1
        if args.stall_after and step > args.stall_after:
            stalled = True  # 停更心跳/metrics/checkpoint，但进程存活
            continue
        loss = round(1.0 / step, 4)
        append(log, f"[{_now()}] step {step}: loss={loss}")
        append(metrics, json.dumps({"step": step, "loss": loss, "at": _now()}))
        (ckpt_dir / "ckpt-latest.fake").touch()
        status = _read_status(workdir, args.run_id)
        status["heartbeat_at"] = _now()
        status["last_step"] = step
        _write_status(workdir, status)
    status = _read_status(workdir, args.run_id)
    if stalled:
        # stall 注入的 run 最终也标 failed（模拟被人发现 stall 后处理前的状态仍是 running，
        # 到 duration 自然结束时如实落 failed，避免假 done）。
        status.update(state="failed", ended_at=_now(), exit_reason="stalled (injected)")
    else:
        append(log, f"[{_now()}] fake job {args.run_id} finished")
        status.update(state="done", ended_at=_now())
    _write_status(workdir, status)
    return 0


# ------------------------------------------------------------- commands ----


def _spawn(args: argparse.Namespace, workdir: Path) -> dict:
    worker_cmd = [
        sys.executable, str(Path(__file__).resolve()), "_worker",
        "--run-id", args.run_id, "--workdir", str(workdir),
        "--duration", str(args.duration), "--interval", str(args.interval),
    ]
    if args.fail_after:
        worker_cmd += ["--fail-after", str(args.fail_after)]
    if args.stall_after:
        worker_cmd += ["--stall-after", str(args.stall_after)]
    if args.config:
        worker_cmd += ["--config", args.config]

    launch_args = {
        "run_id": args.run_id, "workdir": str(workdir), "duration": args.duration,
        "interval": args.interval, "fail_after": args.fail_after,
        "stall_after": args.stall_after, "config": args.config,
    }
    config_sha = None
    if args.config:
        cfg = Path(args.config)
        if not cfg.exists():
            raise SystemExit(f"[fake_job] config 不存在：{cfg}")
        config_sha = _sha256(cfg)

    with (workdir / "worker.out").open("ab") as out:
        proc = subprocess.Popen(  # noqa: S603
            worker_cmd, stdout=out, stderr=subprocess.STDOUT,
            start_new_session=True, cwd=str(workdir),
        )
    status = {
        "run_id": args.run_id, "pid": proc.pid, "state": "running",
        "started_at": _now(), "heartbeat_at": _now(), "last_step": 0,
        "config_path": args.config, "config_sha256": config_sha,
        "launch_args": launch_args, "workdir": str(workdir),
    }
    _write_status(workdir, status)
    return status


def cmd_launch(args: argparse.Namespace) -> int:
    workdir = Path(args.workdir) if args.workdir else DEFAULT_WORKROOT / args.run_id
    workdir = _check_workdir(workdir, args.run_id)
    workdir.mkdir(parents=True, exist_ok=True)
    workdir = _check_workdir(workdir, args.run_id)
    with _control_lock(workdir):
        existing = _status_path(workdir)
        if existing.exists():
            old = _read_status(workdir, args.run_id)
            old_pid = int(old.get("pid", -1))
            worker_alive = _is_our_worker(old_pid, args.run_id, workdir)
            if old.get("state") == "running" and worker_alive:
                raise SystemExit(
                    f"[fake_job] run {args.run_id} 已在运行（pid {old['pid']}）；先 kill 或换 run-id"
                )
            if old.get("state") == "running":
                raise SystemExit(
                    "[fake_job] 拒绝：existing running status 未绑定同 run/workdir worker；"
                    "不得覆盖后再启动"
                )
            if worker_alive:
                raise SystemExit("[fake_job] 拒绝：terminal status 仍绑定存活 worker，不得并发 launch")
            if old.get("state") not in ("done", "failed", "killed"):
                raise SystemExit(f"[fake_job] 拒绝：不可覆盖 state={old.get('state')!r} 的 status")
        status = _spawn(args, workdir)
    print(json.dumps({"launched": True, **status}, indent=2, ensure_ascii=False))
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    workdir = Path(args.workdir) if args.workdir else DEFAULT_WORKROOT / args.run_id
    workdir = _check_workdir(workdir, args.run_id)
    status = _read_status(workdir, args.run_id)
    pid = int(status.get("pid", -1))
    status["process_alive"] = _is_our_worker(pid, args.run_id, workdir)
    if status.get("state") == "running" and not status["process_alive"]:
        status["note"] = "state=running 但进程不存活（可能 crash / 被外部终止）"
    print(json.dumps(status, indent=2, ensure_ascii=False))
    return 0


def cmd_kill(args: argparse.Namespace) -> int:
    workdir = Path(args.workdir) if args.workdir else DEFAULT_WORKROOT / args.run_id
    workdir = _check_workdir(workdir, args.run_id)
    with _control_lock(workdir):
        status = _read_status(workdir, args.run_id)
        pid = int(status.get("pid", -1))
        if status.get("state") != "running" or not _is_our_worker(pid, args.run_id, workdir):
            raise SystemExit(
                "[fake_job] 拒绝：kill 要求同 run/workdir 的 running worker"
                f"（state={status.get('state')} pid={pid}）"
            )
        _terminate_worker(pid, args.run_id, workdir)
        status.update(state="killed", ended_at=_now(), exit_reason=args.reason or "killed via fake_job kill")
        _write_status(workdir, status)
    print(json.dumps({"killed": True, "run_id": args.run_id, "pid": pid}, ensure_ascii=False))
    return 0


def _terminate_worker(pid: int, run_id: str, workdir: Path) -> None:
    """Terminate only the exact verified worker through a Linux pidfd.

    pidfd pins process identity across the final verification/send boundary, avoiding a reused PID
    receiving the signal. Platforms without pidfd support fail closed.
    """
    if not hasattr(os, "pidfd_open") or not hasattr(signal, "pidfd_send_signal"):
        raise SystemExit("[fake_job] 拒绝：当前平台无 pidfd，无法安全证明 signal 目标身份")
    try:
        pidfd = os.pidfd_open(pid)
    except OSError as exc:
        raise SystemExit(f"[fake_job] 拒绝：无法为 worker pid {pid} 建立 pidfd：{exc}") from exc
    try:
        if not _is_our_worker(pid, run_id, workdir):
            raise SystemExit("[fake_job] 拒绝：signal 前 worker 身份复核失败")
        signal.pidfd_send_signal(pidfd, signal.SIGTERM)
        for _ in range(50):
            if not _pid_alive(pid):
                return
            time.sleep(0.1)
        raise SystemExit(f"[fake_job] 拒绝继续：worker pid {pid} 未在超时内终止")
    finally:
        os.close(pidfd)


def cmd_restart(args: argparse.Namespace) -> int:
    workdir = Path(args.workdir) if args.workdir else DEFAULT_WORKROOT / args.run_id
    workdir = _check_workdir(workdir, args.run_id)
    with _control_lock(workdir):
        status = _read_status(workdir, args.run_id)
        pid = int(status.get("pid", -1))
        if status.get("state") == "running":
            if not _is_our_worker(pid, args.run_id, workdir):
                raise SystemExit("[fake_job] 拒绝：running status 未绑定同 run/workdir worker")
            _terminate_worker(pid, args.run_id, workdir)
        elif status.get("state") not in ("done", "failed", "killed"):
            raise SystemExit(f"[fake_job] 拒绝：不可从 state={status.get('state')!r} restart")
        elif _is_our_worker(pid, args.run_id, workdir):
            raise SystemExit("[fake_job] 拒绝：terminal status 仍绑定存活 worker，不得并发 restart")
        la = status.get("launch_args") or {}
        ns = argparse.Namespace(
            run_id=args.run_id, workdir=str(workdir),
            duration=la.get("duration", 20.0), interval=la.get("interval", 1.0),
            fail_after=None, stall_after=None,  # restart 后不再注入异常（恢复语义）
            config=la.get("config"),
        )
        new_status = _spawn(ns, workdir)
    print(json.dumps({"restarted": True, **new_status}, indent=2, ensure_ascii=False))
    return 0


# ------------------------------------------------------------- self-test ----


def _wait_state(workdir: Path, run_id: str, want: str, timeout: float = 15.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        status = _read_status(workdir, run_id)
        if status.get("state") == want:
            return status
        time.sleep(0.1)
    raise AssertionError(f"等待 state={want} 超时（当前 {status.get('state')}）")


def _self_test() -> int:
    import shutil

    root = Path(tempfile.mkdtemp(prefix="fake-job-selftest-", dir="/tmp"))
    me = [sys.executable, str(Path(__file__).resolve())]
    failed = 0

    def run(argv: list[str]) -> subprocess.CompletedProcess:
        return subprocess.run(me + argv, capture_output=True, text=True)  # noqa: S603

    try:
        # 1. 正常跑完 → done，log/metrics/checkpoint 齐备
        w1 = root / "t1"
        r = run(["launch", "--run-id", "t1", "--workdir", str(w1), "--duration", "1", "--interval", "0.1"])
        assert r.returncode == 0, r.stderr
        s = _wait_state(w1, "t1", "done")
        assert (w1 / "job.log").exists() and (w1 / "metrics.jsonl").exists()
        assert (w1 / "checkpoints" / "ckpt-latest.fake").exists()
        assert s.get("last_step", 0) > 0

        # 2. fail-after 注入 → failed，日志含 NaN
        w2 = root / "t2"
        run(["launch", "--run-id", "t2", "--workdir", str(w2), "--duration", "2",
             "--interval", "0.1", "--fail-after", "2"])
        _wait_state(w2, "t2", "failed")
        assert "NaN" in (w2 / "job.log").read_text(encoding="utf-8")

        # 3. kill 路径：长 job → kill → killed 且进程死
        w3 = root / "t3"
        run(["launch", "--run-id", "t3", "--workdir", str(w3), "--duration", "30", "--interval", "0.2"])
        s3 = _read_status(w3, "t3")
        r = run(["kill", "--run-id", "t3", "--workdir", str(w3)])
        assert r.returncode == 0, r.stderr
        assert _read_status(w3, "t3")["state"] == "killed"
        assert not _pid_alive(int(s3["pid"]))

        # 4. restart：killed → running（新 pid）→ 再 kill 清场
        r = run(["restart", "--run-id", "t3", "--workdir", str(w3)])
        assert r.returncode == 0, r.stderr
        s3b = _read_status(w3, "t3")
        assert s3b["state"] == "running" and s3b["pid"] != s3["pid"]
        run(["kill", "--run-id", "t3", "--workdir", str(w3)])

        # 5. workdir 保护：受保护/非 /tmp 路径拒绝
        r = run(["launch", "--run-id", "bad", "--workdir", str(REPO_ROOT / "lab/runs/bad")])
        assert r.returncode != 0 and "workdir" in (r.stderr + r.stdout)

        # 6. status 只读可用
        r = run(["status", "--run-id", "t1", "--workdir", str(w1)])
        assert r.returncode == 0 and '"state": "done"' in r.stdout

        # 7. status/kill/restart 都核对 status.run_id。
        wc = root / "t-corrupt"
        wc.mkdir()
        bad_status = {**s, "run_id": "another-run", "workdir": str(wc)}
        _write_status(wc, bad_status)
        for action in ("status", "kill", "restart"):
            r = run([action, "--run-id", "t-corrupt", "--workdir", str(wc)])
            assert r.returncode != 0 and "status.run_id" in (r.stderr + r.stdout)

        # 8. status.workdir 必须逐字等于安全 canonical path，不能靠 resolve 等价蒙混。
        _write_status(wc, {**s, "run_id": "t-corrupt", "workdir": str(root / "not-t-corrupt")})
        for action in ("status", "kill", "restart"):
            r = run([action, "--run-id", "t-corrupt", "--workdir", str(wc)])
            assert r.returncode != 0 and "status.workdir" in (r.stderr + r.stdout)

        # 9. protected / cross-run leaf / symlink escape 全部在写 bytes 前拒绝。
        r = run(["launch", "--run-id", "leaf", "--workdir", str(root / "other")])
        assert r.returncode != 0 and "必须与 run-id" in (r.stderr + r.stdout)
        r = run(["launch", "--run-id", "inject", "--workdir", str(root / "bad;parent" / "inject")])
        assert r.returncode != 0 and "不允许的字符" in (r.stderr + r.stdout)
        link = root / "escape-link"
        link.symlink_to(REPO_ROOT, target_is_directory=True)
        r = run(["launch", "--run-id", "escape", "--workdir", str(link / "escape")])
        assert r.returncode != 0 and "symlink" in (r.stderr + r.stdout)

        # 10. existing running 状态若不绑定 exact worker，launch 不得覆盖后再起第二个进程。
        wr = root / "t-running-corrupt"
        wr.mkdir()
        _write_status(wr, {
            "run_id": "t-running-corrupt", "workdir": str(wr), "state": "running",
            "pid": os.getpid(), "launch_args": {},
        })
        r = run(["launch", "--run-id", "t-running-corrupt", "--workdir", str(wr)])
        assert r.returncode != 0 and "不得覆盖" in (r.stderr + r.stdout)
        assert not (wr / "worker.out").exists()

        # 11. worker 身份要求受信解释器 + exact argv；重复 run/workdir 参数不得蒙混。
        good_argv = [
            sys.executable, str(Path(__file__).resolve()), "_worker",
            "--run-id", "argv-run", "--workdir", str(root / "argv-run"),
            "--duration", "1", "--interval", "0.1",
        ]
        assert _worker_argv_matches(good_argv, "argv-run", root / "argv-run")
        assert not _worker_argv_matches(
            good_argv + ["--run-id", "other"], "argv-run", root / "argv-run"
        )
        assert not _worker_argv_matches(
            ["/bin/false", *good_argv[1:]], "argv-run", root / "argv-run"
        )

        # 12. 并发 launch 由 control lock 串行化：同一 run 只允许一个 worker 生效。
        wq = root / "t-concurrent"
        concurrent_cmd = me + [
            "launch", "--run-id", "t-concurrent", "--workdir", str(wq),
            "--duration", "30", "--interval", "0.2",
        ]
        p1 = subprocess.Popen(  # noqa: S603
            concurrent_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        p2 = subprocess.Popen(  # noqa: S603
            concurrent_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        p1.communicate(timeout=10)
        p2.communicate(timeout=10)
        assert sorted((p1.returncode, p2.returncode)) == [0, 1]
        sq = _read_status(wq, "t-concurrent")
        assert _is_our_worker(int(sq["pid"]), "t-concurrent", wq)
        r = run(["kill", "--run-id", "t-concurrent", "--workdir", str(wq)])
        assert r.returncode == 0, r.stderr
    except AssertionError as e:
        print(f"FAIL {e}")
        failed = 1
    finally:
        shutil.rmtree(root, ignore_errors=True)
    print(f"[fake_job --self-test] {'OK — 12/12 场景通过' if not failed else 'FAIL'}")
    return failed


# ------------------------------------------------------------------ main ----


def main(argv: list[str]) -> int:
    if "--self-test" in argv:
        return _self_test()
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    def common(p: argparse.ArgumentParser, launch_opts: bool = False) -> None:
        p.add_argument("--run-id", required=True)
        p.add_argument("--workdir", default=None, help=f"默认 {DEFAULT_WORKROOT}/<run-id>")
        if launch_opts:
            p.add_argument("--duration", type=float, default=20.0, help="模拟运行秒数")
            p.add_argument("--interval", type=float, default=1.0, help="心跳/step 间隔秒")
            p.add_argument("--fail-after", type=int, default=None, help="第 N 步后注入 NaN 失败")
            p.add_argument("--stall-after", type=int, default=None, help="第 N 步后注入 stall")
            p.add_argument("--config", default=None, help="记录 config 路径+sha256（供 drift 检查）")

    common(sub.add_parser("launch", help="启动 fake job（human gate 入口）"), launch_opts=True)
    common(sub.add_parser("status", help="只读查询状态"))
    kp = sub.add_parser("kill", help="终止 fake job（human gate 入口）")
    common(kp)
    kp.add_argument("--reason", default=None)
    common(sub.add_parser("restart", help="按原参数重启（human gate 入口；不复注异常）"))
    wp = sub.add_parser("_worker", help=argparse.SUPPRESS)
    common(wp, launch_opts=True)

    args = parser.parse_args(argv)
    handlers = {
        "launch": cmd_launch, "status": cmd_status, "kill": cmd_kill,
        "restart": cmd_restart, "_worker": cmd_worker,
    }
    return handlers[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
