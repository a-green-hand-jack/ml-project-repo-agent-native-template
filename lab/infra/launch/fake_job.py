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

安全约束：workdir 不得落在 repo 受保护路径（lab/data|runs|models、checkpoints/、wandb/）
内；建议一律用 /tmp。无第三方依赖。
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
PROTECTED_PARTS = ("lab/data", "lab/runs", "lab/models", "checkpoints", "wandb", "lab/infra/private")
DEFAULT_WORKROOT = Path(tempfile.gettempdir()) / "ml-template-fake-jobs"

STATES = ("running", "done", "failed", "killed")


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def _sha256(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def _check_workdir(workdir: Path) -> None:
    resolved = workdir.resolve()
    try:
        rel = resolved.relative_to(REPO_ROOT)
    except ValueError:
        return  # repo 外（如 /tmp）：安全
    rel_posix = rel.as_posix()
    for p in PROTECTED_PARTS:
        if rel_posix == p or rel_posix.startswith(p + "/"):
            raise SystemExit(f"[fake_job] 拒绝：workdir 落在受保护路径 {p}（用 /tmp 下的目录）")


def _status_path(workdir: Path) -> Path:
    return workdir / "status.json"


def _read_status(workdir: Path) -> dict:
    p = _status_path(workdir)
    if not p.exists():
        raise SystemExit(f"[fake_job] 找不到 status.json：{p}（run 未启动或 workdir 不对）")
    return json.loads(p.read_text(encoding="utf-8"))


def _write_status(workdir: Path, status: dict) -> None:
    p = _status_path(workdir)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(status, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(p)


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except (ProcessLookupError, PermissionError):
        return False
    return True


def _is_our_worker(pid: int, run_id: str) -> bool:
    """防 pid 复用误杀：检查 /proc/<pid>/cmdline 是否是本脚本的 worker 且 run-id 匹配。"""
    try:
        cmdline = Path(f"/proc/{pid}/cmdline").read_bytes().decode("utf-8", "replace")
    except OSError:
        return _pid_alive(pid)  # 无 /proc（非 Linux）：退化为存活检查
    return "fake_job.py" in cmdline and run_id in cmdline


# ---------------------------------------------------------------- worker ----


def cmd_worker(args: argparse.Namespace) -> int:
    workdir = Path(args.workdir)
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
            status = _read_status(workdir)
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
        status = _read_status(workdir)
        status["heartbeat_at"] = _now()
        status["last_step"] = step
        _write_status(workdir, status)
    status = _read_status(workdir)
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
    _check_workdir(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    existing = _status_path(workdir)
    if existing.exists():
        old = json.loads(existing.read_text(encoding="utf-8"))
        if old.get("state") == "running" and _is_our_worker(int(old.get("pid", -1)), args.run_id):
            raise SystemExit(f"[fake_job] run {args.run_id} 已在运行（pid {old['pid']}）；先 kill 或换 run-id")
    status = _spawn(args, workdir)
    print(json.dumps({"launched": True, **status}, indent=2, ensure_ascii=False))
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    workdir = Path(args.workdir) if args.workdir else DEFAULT_WORKROOT / args.run_id
    status = _read_status(workdir)
    pid = int(status.get("pid", -1))
    status["process_alive"] = _is_our_worker(pid, args.run_id)
    if status.get("state") == "running" and not status["process_alive"]:
        status["note"] = "state=running 但进程不存活（可能 crash / 被外部终止）"
    print(json.dumps(status, indent=2, ensure_ascii=False))
    return 0


def cmd_kill(args: argparse.Namespace) -> int:
    workdir = Path(args.workdir) if args.workdir else DEFAULT_WORKROOT / args.run_id
    status = _read_status(workdir)
    pid = int(status.get("pid", -1))
    if _is_our_worker(pid, args.run_id):
        if _pgid_ok(pid):
            os.killpg(os.getpgid(pid), signal.SIGTERM)
        else:
            os.kill(pid, signal.SIGTERM)
        for _ in range(50):
            if not _pid_alive(pid):
                break
            time.sleep(0.1)
    status.update(state="killed", ended_at=_now(), exit_reason=args.reason or "killed via fake_job kill")
    _write_status(workdir, status)
    print(json.dumps({"killed": True, "run_id": args.run_id, "pid": pid}, ensure_ascii=False))
    return 0


def _pgid_ok(pid: int) -> bool:
    try:
        os.getpgid(pid)
        return True
    except ProcessLookupError:
        return False


def cmd_restart(args: argparse.Namespace) -> int:
    workdir = Path(args.workdir) if args.workdir else DEFAULT_WORKROOT / args.run_id
    status = _read_status(workdir)
    pid = int(status.get("pid", -1))
    if _is_our_worker(pid, args.run_id):
        os.kill(pid, signal.SIGTERM)
        for _ in range(50):
            if not _pid_alive(pid):
                break
            time.sleep(0.1)
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


def _wait_state(workdir: Path, want: str, timeout: float = 15.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        status = _read_status(workdir)
        if status.get("state") == want:
            return status
        time.sleep(0.1)
    raise AssertionError(f"等待 state={want} 超时（当前 {status.get('state')}）")


def _self_test() -> int:
    import shutil

    root = Path(tempfile.mkdtemp(prefix="fake-job-selftest-"))
    me = [sys.executable, str(Path(__file__).resolve())]
    failed = 0

    def run(argv: list[str]) -> subprocess.CompletedProcess:
        return subprocess.run(me + argv, capture_output=True, text=True)  # noqa: S603

    try:
        # 1. 正常跑完 → done，log/metrics/checkpoint 齐备
        w1 = root / "t1"
        r = run(["launch", "--run-id", "t1", "--workdir", str(w1), "--duration", "1", "--interval", "0.1"])
        assert r.returncode == 0, r.stderr
        s = _wait_state(w1, "done")
        assert (w1 / "job.log").exists() and (w1 / "metrics.jsonl").exists()
        assert (w1 / "checkpoints" / "ckpt-latest.fake").exists()
        assert s.get("last_step", 0) > 0

        # 2. fail-after 注入 → failed，日志含 NaN
        w2 = root / "t2"
        run(["launch", "--run-id", "t2", "--workdir", str(w2), "--duration", "2",
             "--interval", "0.1", "--fail-after", "2"])
        _wait_state(w2, "failed")
        assert "NaN" in (w2 / "job.log").read_text(encoding="utf-8")

        # 3. kill 路径：长 job → kill → killed 且进程死
        w3 = root / "t3"
        run(["launch", "--run-id", "t3", "--workdir", str(w3), "--duration", "30", "--interval", "0.2"])
        s3 = _read_status(w3)
        r = run(["kill", "--run-id", "t3", "--workdir", str(w3)])
        assert r.returncode == 0, r.stderr
        assert _read_status(w3)["state"] == "killed"
        assert not _pid_alive(int(s3["pid"]))

        # 4. restart：killed → running（新 pid）→ 再 kill 清场
        r = run(["restart", "--run-id", "t3", "--workdir", str(w3)])
        assert r.returncode == 0, r.stderr
        s3b = _read_status(w3)
        assert s3b["state"] == "running" and s3b["pid"] != s3["pid"]
        run(["kill", "--run-id", "t3", "--workdir", str(w3)])

        # 5. workdir 保护：受保护路径拒绝
        r = run(["launch", "--run-id", "bad", "--workdir", str(REPO_ROOT / "lab/runs/bad")])
        assert r.returncode != 0 and "受保护" in (r.stderr + r.stdout)

        # 6. status 只读可用
        r = run(["status", "--run-id", "t1", "--workdir", str(w1)])
        assert r.returncode == 0 and '"state": "done"' in r.stdout
    except AssertionError as e:
        print(f"FAIL {e}")
        failed = 1
    finally:
        shutil.rmtree(root, ignore_errors=True)
    print(f"[fake_job --self-test] {'OK — 6/6 场景通过' if not failed else 'FAIL'}")
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
