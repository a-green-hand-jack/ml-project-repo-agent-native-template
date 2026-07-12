#!/usr/bin/env python3
"""experiment control plane CLI（runtime-neutral 主干：Claude 与 Codex 走同一入口）。

子命令（plans/20260712-experiment-control-plane.zh.md 任务 C/E/F）：
- detect          列出 registry adapter 的可用性；后端 CLI 缺失时清晰标注 fallback，
                  不报错不崩溃（本仓库无 Slurm/RunAI 环境即 local-only）。
- plan            按 registry 模板生成 launch/status/kill/restart 的**命令草案**（只打印，
                  绝不执行）；请求的后端不可用时降级 local-fake 并明确提示。
- watch           bounded 一次性快照检查：status/进程存活/日志尾部（有界行数）/metric 与
                  checkpoint 新鲜度/config drift/failure signals。检查完即退出，不常驻
                  不轮询。输出结构化 alert（可直接并入 ledger alerts 字段），附带
                  resume/recovery 提案草案。只读，不写任何文件。
- apply-recovery  半自动执行 ledger 里**已获 human 批准**的一条 resume/recovery 提案：
                  要求 approved_by/approved_at/approved_action 齐备且 approved_action 与
                  proposal.command 逐字一致，且命令仅限 local-fake adapter（fake_job.py）
                  ——真实后端命令一律拒绝。批准缺失/不匹配时拒绝执行并报错，不静默跳过。
                  本子命令是 launch registry 登记的 human-gate 入口。

YAML 解析复用 scripts/validate-experiment-state.py 的 load_yaml（PyYAML 优先 + 受限
解析器回退），经 importlib 加载，避免两份解析逻辑漂移（同 check-adoption-integrity 先例）。
无第三方硬依赖。退出码：0 正常 / 1 错误 / 2 拒绝执行 / 3 watch 检出异常。
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
REPO_ROOT = _HERE.parent.parent.parent
REGISTRY = _HERE / "registry.yaml"
LEDGER = REPO_ROOT / "lab" / "research" / "experiment-ledger.yaml"

DEFAULT_LOG_TAIL = 200
DEFAULT_HEARTBEAT_TIMEOUT = 120.0
FAILURE_PATTERNS = (
    ("OOM", re.compile(r"\b(OOM|out of memory)\b", re.IGNORECASE)),
    ("NaN", re.compile(r"\bnan\b", re.IGNORECASE)),
    ("crash", re.compile(r"Traceback \(most recent call last\)|Segmentation fault")),
)


def _load_state_module():
    path = REPO_ROOT / "scripts" / "validate-experiment-state.py"
    spec = importlib.util.spec_from_file_location("validate_experiment_state", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_yaml_file(path: Path):
    mod = _load_state_module()
    return mod.load_yaml(path.read_text(encoding="utf-8"))[0]


def _load_registry(path: Path | None = None) -> dict:
    return _load_yaml_file(path or REGISTRY) or {}


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


# ------------------------------------------------------------------ detect ----


def _adapter_available(adapter: dict) -> tuple[bool, list[str]]:
    missing = [e for e in (adapter.get("detect_executables") or []) if shutil.which(str(e)) is None]
    return not missing, missing


def cmd_detect(args: argparse.Namespace) -> int:
    registry = _load_registry(Path(args.registry) if args.registry else None)
    print("launch adapter availability（只探测可执行文件，不连接任何后端）：")
    any_remote = False
    for adapter in registry.get("adapters") or []:
        ok, missing = _adapter_available(adapter)
        aid = adapter.get("id")
        if ok:
            print(f"  {aid}: available")
            if adapter.get("kind") == "remote":
                any_remote = True
        else:
            print(f"  {aid}: unavailable（缺 {', '.join(missing)}）→ fallback local-only")
    if not any_remote:
        print("结论：未检测到远端 scheduler CLI，控制面处于 local-only 模式（fake job 可用）。")
    return 0


# -------------------------------------------------------------------- plan ----


def _render(template: str, variables: dict[str, str]) -> str:
    def sub(m: re.Match) -> str:
        key = m.group(1)
        return variables.get(key, "{" + key + "}")

    return re.sub(r"\{(\w+)\}", sub, template)


def cmd_plan(args: argparse.Namespace) -> int:
    registry = _load_registry(Path(args.registry) if args.registry else None)
    adapters = {a.get("id"): a for a in registry.get("adapters") or []}
    backend = args.backend or "local-fake"
    adapter = adapters.get(backend)
    if adapter is None:
        print(f"[expctl] 未知 backend：{backend}（registry 里有：{', '.join(adapters)}）", file=sys.stderr)
        return 1
    ok, missing = _adapter_available(adapter)
    if not ok:
        fallback = adapters.get("local-fake")
        print(
            f"[expctl] 未检测到 {backend} 所需 CLI（缺 {', '.join(missing)}）——"
            "降级到 local-fake（仅提案模式，不影响其余流程）。"
        )
        adapter, backend = fallback, "local-fake"
        if adapter is None:
            print("[expctl] registry 缺 local-fake adapter，无法降级", file=sys.stderr)
            return 1
    template = (adapter.get("commands") or {}).get(args.action)
    if not template:
        print(f"[expctl] adapter {backend} 未定义动作 {args.action}", file=sys.stderr)
        return 1
    variables = {"run_id": args.run_id, "workdir": args.workdir or f"/tmp/ml-template-fake-jobs/{args.run_id}"}
    for kv in args.var or []:
        k, _, v = kv.partition("=")
        variables[k] = v
    command = _render(template, variables)
    unresolved = re.findall(r"\{(\w+)\}", command)
    print("command_draft:")
    print(f"  backend: {backend}")
    print(f"  action: {args.action}")
    print(f'  command: "{command}"')
    if unresolved:
        print(f"  unresolved_vars: [{', '.join(unresolved)}]  # 用 --var key=value 补齐")
    print(
        "  note: 这是命令草案，不会被执行。launch/kill/restart 是 human gate："
        "见 .agent/human-gates.md 与 lab/infra/launch/registry.yaml gated_prefixes。"
    )
    return 0


# -------------------------------------------------------------------- watch ----


def _tail(path: Path, n: int) -> list[str]:
    """有界读取：只保留最后 n 行，不把整个文件读进输出。"""
    if not path.exists():
        return []
    from collections import deque

    dq: deque[str] = deque(maxlen=n)
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            dq.append(line.rstrip("\n"))
    return list(dq)


def _age_seconds(path: Path) -> float | None:
    try:
        return time.time() - path.stat().st_mtime
    except OSError:
        return None


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except (ProcessLookupError, PermissionError):
        return False
    return True


def cmd_watch(args: argparse.Namespace) -> int:
    workdir = Path(args.workdir)
    status_f = workdir / "status.json"
    checks: list[tuple[str, bool, str]] = []
    alerts: list[dict] = []

    def alert(atype: str, evidence: str, action: str = "restart") -> None:
        cmd = (
            f"python lab/infra/launch/fake_job.py {action} "
            f"--run-id {args.run_id} --workdir {workdir}"
        )
        alerts.append({
            "id": f"alert-{time.strftime('%Y%m%d%H%M%S')}-{atype.lower().replace(' ', '-')}",
            "type": atype,
            "at": _now(),
            "evidence": evidence,
            "proposal": {
                "action": action,
                "command": cmd,
                "radius": "fake/local job only; no real compute touched",
            },
        })

    if not status_f.exists():
        alert("missing-status", f"{status_f} 不存在（run 未启动或 workdir 不对）", action="launch")
        state = "unknown"
    else:
        status = json.loads(status_f.read_text(encoding="utf-8"))
        state = status.get("state", "unknown")
        pid = int(status.get("pid", -1))
        alive = _pid_alive(pid)
        checks.append(("process", alive or state != "running", f"pid {pid} alive={alive} state={state}"))
        if state == "running" and not alive:
            alert("crash", f"state=running 但 pid {pid} 不存活（可能 crash/被外部终止）")

        # 心跳 / metric 新鲜度（stale run 判定，任务 F1）
        hb_age = None
        hb = status.get("heartbeat_at")
        metrics_age = _age_seconds(workdir / "metrics.jsonl")
        status_age = _age_seconds(status_f)
        hb_age = status_age  # heartbeat 落在 status.json，用其 mtime 做保守 stale 判定
        if state == "running" and alive:
            stale = (hb_age is None or hb_age > args.heartbeat_timeout) and (
                metrics_age is None or metrics_age > args.heartbeat_timeout
            )
            checks.append((
                "freshness", not stale,
                f"heartbeat_age={None if hb_age is None else round(hb_age, 1)}s "
                f"metrics_age={None if metrics_age is None else round(metrics_age, 1)}s "
                f"timeout={args.heartbeat_timeout}s (heartbeat_at={hb})",
            ))
            if stale:
                alert(
                    "metric-stall",
                    f"进程存活但心跳/metrics 停更超过 {args.heartbeat_timeout}s（stale run）",
                )

        # checkpoint 新鲜度
        ckpts = sorted((workdir / "checkpoints").glob("*"), key=lambda p: p.stat().st_mtime, reverse=True) \
            if (workdir / "checkpoints").is_dir() else []
        if state == "running" and alive:
            if not ckpts:
                alert("missing-checkpoint", "checkpoints/ 目录为空")
            else:
                ck_age = _age_seconds(ckpts[0])
                checks.append(("checkpoint", ck_age is not None and ck_age <= args.heartbeat_timeout,
                               f"latest={ckpts[0].name} age={None if ck_age is None else round(ck_age, 1)}s"))

        # config drift
        cfg_path, cfg_sha = status.get("config_path"), status.get("config_sha256")
        if cfg_path and cfg_sha:
            cfg = Path(cfg_path)
            if not cfg.is_absolute():
                cfg = REPO_ROOT / cfg_path
            if not cfg.exists():
                alert("config-mismatch", f"记录的 config 已不存在：{cfg_path}", action="kill")
            else:
                import hashlib

                now_sha = hashlib.sha256(cfg.read_bytes()).hexdigest()
                checks.append(("config", now_sha == cfg_sha, f"{cfg_path} sha256 match={now_sha == cfg_sha}"))
                if now_sha != cfg_sha:
                    alert("config-mismatch", f"config drift：{cfg_path} 内容与 launch 时 sha256 不一致", action="kill")

        # failure signals（有界日志尾部扫描）
        tail_lines = _tail(workdir / "job.log", args.log_tail)
        checks.append(("log-tail", True, f"scanned last {len(tail_lines)} lines (bound={args.log_tail})"))
        for sig, pattern in FAILURE_PATTERNS:
            hits = [ln for ln in tail_lines if pattern.search(ln)]
            if hits:
                alert(sig if sig != "crash" else "crash", f"日志尾部命中 {sig}：{hits[-1][:160]}",
                      action="restart" if sig != "crash" else "restart")
        if state == "failed":
            reason = status.get("exit_reason", "unknown")
            alert("failure", f"job 以 failed 结束：{reason}")

    health = "ok" if not alerts else "abnormal"
    print("watch_report:")
    print(f"  run_id: {args.run_id}")
    print(f'  checked_at: "{_now()}"')
    print(f"  workdir: {workdir}")
    print(f"  state: {state}")
    print(f"  health: {health}")
    print("  checks:")
    for name, ok, detail in checks:
        print(f"    - name: {name}")
        print(f"      ok: {str(ok).lower()}")
        print(f'      detail: "{detail}"')
    print("  alerts:" + ("" if alerts else " []"))
    for a in alerts:
        print(f"    - id: {a['id']}")
        print(f"      type: {a['type']}")
        print(f'      at: "{a["at"]}"')
        print(f'      evidence: "{a["evidence"]}"')
        print("      proposal:")
        print(f"        action: {a['proposal']['action']}")
        print(f'        command: "{a["proposal"]["command"]}"')
        print(f'        radius: "{a["proposal"]["radius"]}"')
        print("      approved_by: null")
        print("      approved_at: null")
        print("      approved_action: null")
        print("      resolved: false")
    if alerts:
        print(
            "# 下一步：experiment-orchestrator 把上述 alerts 并入 "
            "lab/research/experiment-ledger.yaml 对应条目的 alerts 字段；"
            "human 批准某条提案后（填 approved_by/approved_at/approved_action），"
            "经 `expctl.py apply-recovery` 半自动执行。"
        )
    return 3 if alerts else 0


# ----------------------------------------------------------- apply-recovery ----


def _is_placeholder(v) -> bool:
    return v is None or (isinstance(v, str) and (not v.strip() or v.strip().startswith("<")))


def _local_only(command: str) -> bool:
    """已批准命令必须仅限 local-fake adapter（fake_job.py 的 launch/kill/restart）。"""
    try:
        tokens = shlex.split(command)
    except ValueError:
        return False
    if len(tokens) < 3:
        return False
    if os.path.basename(tokens[0]) not in ("python", "python3"):
        return False
    script = tokens[1]
    if not script.replace("\\", "/").endswith("lab/infra/launch/fake_job.py"):
        return False
    return tokens[2] in ("launch", "kill", "restart")


def cmd_apply_recovery(args: argparse.Namespace) -> int:
    ledger_path = Path(args.ledger) if args.ledger else LEDGER
    try:
        data = _load_yaml_file(ledger_path)
    except Exception as e:  # noqa: BLE001
        print(f"[expctl] ledger 解析失败：{e}", file=sys.stderr)
        return 1
    exps = {e.get("id"): e for e in (data or {}).get("experiments") or [] if isinstance(e, dict)}
    exp = exps.get(args.run_id)
    if exp is None:
        print(f"[expctl] 拒绝：ledger 无实验 {args.run_id}", file=sys.stderr)
        return 2
    alerts = {a.get("id"): a for a in exp.get("alerts") or [] if isinstance(a, dict)}
    a = alerts.get(args.alert_id)
    if a is None:
        print(f"[expctl] 拒绝：实验 {args.run_id} 无 alert {args.alert_id}", file=sys.stderr)
        return 2

    missing = [f for f in ("approved_by", "approved_at", "approved_action") if _is_placeholder(a.get(f))]
    if missing:
        print(
            f"[expctl] 拒绝执行：alert {args.alert_id} 缺批准字段 {', '.join(missing)}。"
            "resume/recovery 是 human gate：先由 human 在 ledger 里落一次性批准记录"
            "（见 .agent/human-gates.md），再执行。",
            file=sys.stderr,
        )
        return 2
    proposal = a.get("proposal") or {}
    command = proposal.get("command")
    if _is_placeholder(command):
        print(f"[expctl] 拒绝执行：alert {args.alert_id} 的 proposal 缺确切命令", file=sys.stderr)
        return 2
    if a.get("approved_action") != command:
        print(
            f"[expctl] 拒绝执行：approved_action 与 proposal.command 不一致（批 A 不能执 B）。\n"
            f"  approved_action: {a.get('approved_action')}\n  proposal.command: {command}",
            file=sys.stderr,
        )
        return 2
    if not _local_only(command):
        print(
            "[expctl] 拒绝执行：已批准命令超出 local-fake 范围（本 issue 的半自动执行仅限 "
            "fake/local job，见 plan 非目标与 .agent/action-boundary.md）。",
            file=sys.stderr,
        )
        return 2

    print(f"[expctl] 批准记录核对通过（approved_by={a['approved_by']} approved_at={a['approved_at']}）")
    print(f"[expctl] 执行已批准动作：{command}")
    if args.dry_run:
        print("[expctl] --dry-run：不实际执行")
        return 0
    result = subprocess.run(shlex.split(command), cwd=str(REPO_ROOT))  # noqa: S603
    print(f"[expctl] 执行完成，exit={result.returncode}。"
          "后续：orchestrator 更新 ledger（alert resolved / status_history）与 memory/current-status.md。")
    return 0 if result.returncode == 0 else 1


# ------------------------------------------------------------------ self-test ----


def _self_test() -> int:  # noqa: PLR0915
    import tempfile

    failed = 0

    def expect(cond: bool, msg: str) -> None:
        nonlocal failed
        if not cond:
            failed += 1
            print(f"FAIL {msg}")

    me = [sys.executable, str(Path(__file__).resolve())]

    def run(argv: list[str]) -> subprocess.CompletedProcess:
        return subprocess.run(me + argv, capture_output=True, text=True, cwd=str(REPO_ROOT))  # noqa: S603

    # 1. detect：本环境无 slurm/runai → local-only 且不报错
    r = run(["detect"])
    expect(r.returncode == 0, f"detect 应 exit 0：{r.stderr}")
    expect("local-fake: available" in r.stdout, "local-fake 应恒可用")
    if shutil.which("sbatch") is None:
        expect("slurm: unavailable" in r.stdout and "fallback local-only" in r.stdout, "slurm 缺失应清晰降级")

    # 2. plan：请求不可用后端 → 降级 local-fake，只出草案
    if shutil.which("runai") is None:
        r = run(["plan", "--action", "launch", "--run-id", "t-plan", "--backend", "runai"])
        expect(r.returncode == 0, f"plan 降级应 exit 0：{r.stderr}")
        expect("降级到 local-fake" in r.stdout and "fake_job.py launch" in r.stdout, "plan 应降级并渲染草案")
    r = run(["plan", "--action", "kill", "--run-id", "t-plan"])
    expect("命令草案，不会被执行" in r.stdout, "plan 应声明不执行")

    root = Path(tempfile.mkdtemp(prefix="expctl-selftest-"))
    fake_job = str(_HERE / "fake_job.py")
    try:
        # 3. watch：健康 running job → ok；stall 注入 → abnormal + 提案
        w = root / "healthy"
        subprocess.run(  # noqa: S603
            [sys.executable, fake_job, "launch", "--run-id", "t-w", "--workdir", str(w),
             "--duration", "8", "--interval", "0.2"], capture_output=True, check=True)
        time.sleep(1.0)
        r = run(["watch", "--run-id", "t-w", "--workdir", str(w), "--heartbeat-timeout", "5"])
        expect(r.returncode == 0 and "health: ok" in r.stdout, f"健康 job 应 ok：\n{r.stdout}")

        w2 = root / "stalled"
        subprocess.run(  # noqa: S603
            [sys.executable, fake_job, "launch", "--run-id", "t-s", "--workdir", str(w2),
             "--duration", "12", "--interval", "0.2", "--stall-after", "3"],
            capture_output=True, check=True)
        time.sleep(4.0)
        r = run(["watch", "--run-id", "t-s", "--workdir", str(w2), "--heartbeat-timeout", "2"])
        expect(r.returncode == 3, f"stall 应 exit 3：exit={r.returncode}\n{r.stdout}")
        expect("metric-stall" in r.stdout and "proposal:" in r.stdout, "stall 应产出 alert+提案")
        expect(f"--run-id t-s" in r.stdout, "提案命令应指向同一 run")

        # 4. watch bounded：日志行数上限生效（scanned 行数 ≤ bound）
        r2 = run(["watch", "--run-id", "t-s", "--workdir", str(w2), "--log-tail", "2",
                  "--heartbeat-timeout", "2"])
        m = re.search(r"scanned last (\d+) lines \(bound=2\)", r2.stdout)
        expect(m is not None and int(m.group(1)) <= 2, f"log tail 应有界：\n{r2.stdout}")

        # 5. apply-recovery：批准缺失 → 拒绝(2)；批 A 执 B → 拒绝(2)；非 local → 拒绝(2)；
        #    齐备且匹配 → 执行成功(0) 且 job 恢复 running
        cmd_restart = f"python lab/infra/launch/fake_job.py restart --run-id t-s --workdir {w2}"
        ledger = root / "ledger.yaml"

        def write_ledger(alert_extra: str) -> None:
            ledger.write_text(
                "experiments:\n"
                "  - id: t-s\n"
                "    status: running\n"
                "    alerts:\n"
                "      - id: alert-1\n"
                "        type: metric-stall\n"
                '        at: "2026-07-13"\n'
                "        proposal:\n"
                "          action: restart\n"
                f'          command: "{cmd_restart}"\n'
                '          radius: "fake/local only"\n'
                + alert_extra,
                encoding="utf-8",
            )

        write_ledger("")  # 无批准
        r = run(["apply-recovery", "--ledger", str(ledger), "--run-id", "t-s", "--alert-id", "alert-1"])
        expect(r.returncode == 2 and "缺批准字段" in r.stderr, "无批准应拒绝")

        write_ledger('        approved_by: "h"\n        approved_at: "2026-07-13"\n'
                     '        approved_action: "some other command"\n')
        r = run(["apply-recovery", "--ledger", str(ledger), "--run-id", "t-s", "--alert-id", "alert-1"])
        expect(r.returncode == 2 and "不一致" in r.stderr, "批 A 执 B 应拒绝")

        ledger.write_text(ledger.read_text(encoding="utf-8").replace(cmd_restart, "sbatch real.sh")
                          .replace('approved_action: "some other command"', 'approved_action: "sbatch real.sh"'),
                          encoding="utf-8")
        r = run(["apply-recovery", "--ledger", str(ledger), "--run-id", "t-s", "--alert-id", "alert-1"])
        expect(r.returncode == 2 and "local-fake" in r.stderr, "真实后端命令应拒绝")

        write_ledger(f'        approved_by: "h"\n        approved_at: "2026-07-13"\n'
                     f'        approved_action: "{cmd_restart}"\n')
        r = run(["apply-recovery", "--ledger", str(ledger), "--run-id", "t-s", "--alert-id", "alert-1"])
        expect(r.returncode == 0, f"齐备批准应执行成功：{r.stderr}")
        status = json.loads((w2 / "status.json").read_text(encoding="utf-8"))
        expect(status.get("state") == "running", "restart 后应回到 running")

        # 清场
        subprocess.run([sys.executable, fake_job, "kill", "--run-id", "t-s", "--workdir", str(w2)],  # noqa: S603
                       capture_output=True)
        subprocess.run([sys.executable, fake_job, "kill", "--run-id", "t-w", "--workdir", str(w)],  # noqa: S603
                       capture_output=True)
    finally:
        import shutil as _sh

        _sh.rmtree(root, ignore_errors=True)

    print(f"[expctl --self-test] {'OK' if not failed else f'FAIL（{failed} 处）'}")
    return 1 if failed else 0


# ---------------------------------------------------------------------- main ----


def main(argv: list[str]) -> int:
    if "--self-test" in argv:
        return _self_test()
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("detect", help="列出 adapter 可用性（只读）")
    p.add_argument("--registry", default=None)

    p = sub.add_parser("plan", help="生成命令草案（只打印，不执行）")
    p.add_argument("--action", required=True, choices=["launch", "status", "kill", "restart"])
    p.add_argument("--run-id", required=True)
    p.add_argument("--backend", default=None)
    p.add_argument("--workdir", default=None)
    p.add_argument("--var", action="append", help="模板变量 key=value，可多次")
    p.add_argument("--registry", default=None)

    p = sub.add_parser("watch", help="一次性快照检查（只读、有界、检查完即退出）")
    p.add_argument("--run-id", required=True)
    p.add_argument("--workdir", required=True)
    p.add_argument("--log-tail", type=int, default=DEFAULT_LOG_TAIL)
    p.add_argument("--heartbeat-timeout", type=float, default=DEFAULT_HEARTBEAT_TIMEOUT)

    p = sub.add_parser("apply-recovery", help="执行 ledger 里一条已获 human 批准的提案（human gate 入口）")
    p.add_argument("--run-id", required=True)
    p.add_argument("--alert-id", required=True)
    p.add_argument("--ledger", default=None)
    p.add_argument("--dry-run", action="store_true")

    args = parser.parse_args(argv)
    handlers = {
        "detect": cmd_detect, "plan": cmd_plan,
        "watch": cmd_watch, "apply-recovery": cmd_apply_recovery,
    }
    return handlers[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
