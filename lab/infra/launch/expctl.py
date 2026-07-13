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
                  proposal.command 逐字一致；命令脚本 resolve 后必须等于 repo 内 canonical
                  fake_job.py、动作限 launch/kill/restart、--run-id 与 alert 所属 run 精确
                  一致（run-a 的批准不能执行 run-b）——真实后端命令一律拒绝。ledger 只认
                  canonical 路径（临时目录下的测试 ledger 例外，显式标记 TEST MODE）。
                  批准缺失/不匹配时拒绝执行并报错，不静默跳过。本子命令是 launch registry
                  登记的 human-gate 入口。信任模型（诚实界定）：文件级批准记录是可审计、
                  不是防伪造——防线 = ledger 变更走 git commit（可追溯）+ 本命令的调用
                  本身被 permission 层 ask/prompt 门禁（见 .agent/human-gates.md）。

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
import tempfile
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
REPO_ROOT = _HERE.parent.parent.parent
REGISTRY = _HERE / "registry.yaml"
LEDGER = REPO_ROOT / "lab" / "research" / "experiment-ledger.yaml"

DEFAULT_LOG_TAIL = 200
DEFAULT_HEARTBEAT_TIMEOUT = 120.0
# 内置日志 failure patterns（experiment card 的 failure_signals 缺失时的回退）。
FAILURE_PATTERNS = (
    ("OOM", re.compile(r"\b(OOM|out of memory)\b", re.IGNORECASE)),
    ("NaN", re.compile(r"\bnan\b", re.IGNORECASE)),
    ("crash", re.compile(r"Traceback \(most recent call last\)|Segmentation fault")),
)
# 这些 signal 名对应 watch 的结构化检查（心跳/checkpoint/config/终态），不是日志 pattern。
STRUCTURAL_SIGNALS = frozenset(
    {"metric-stall", "metric stall", "missing-checkpoint", "missing checkpoint",
     "stale-checkpoint", "config-mismatch", "failure", "crash"}
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


def _tail(path: Path, n: int, max_bytes: int = 1 << 20) -> list[str]:
    """有界读取最后 n 行：从文件尾部 seek 回读固定字节窗口，I/O 与文件总大小无关。

    逐块（8 KiB）向前回读，凑够 n 行或触到 max_bytes 上限即停——日志再大也只读
    有界字节数（此前实现从头遍历全文件，I/O 随日志无限增长）。
    """
    try:
        size = path.stat().st_size
    except OSError:
        return []
    if size == 0 or n <= 0:
        return []
    block = 8192
    buf = b""
    with path.open("rb") as f:
        pos = size
        while pos > 0 and buf.count(b"\n") <= n and len(buf) < max_bytes:
            step = min(block, pos)
            pos -= step
            f.seek(pos)
            buf = f.read(step) + buf
    # 未读到文件头时窗口最前一行可能被截断；取最后 n 行即天然排除该残行。
    return buf.decode("utf-8", errors="replace").splitlines()[-n:]


def _load_failure_signals(ledger_path: Path, run_id: str) -> tuple[list[tuple[str, re.Pattern]], str]:
    """合并 experiment card/ledger 的 failure_signals 与内置日志 patterns。

    返回 (patterns, source 说明)。card 里的自定义 signal（非内置名、非结构化检查名）
    按 case-insensitive 正则编译（非法正则退化为字面量匹配）。ledger 缺失 / run 未登记 /
    无 failure_signals 字段时回退内置三种（OOM/NaN/crash）并在 source 里注明。
    """
    patterns = list(FAILURE_PATTERNS)
    builtin_names = {name for name, _ in FAILURE_PATTERNS}
    fallback = f"builtin OOM/NaN/crash（{ledger_path} 无 run {run_id} 的 failure_signals，回退内置）"
    try:
        data = _load_yaml_file(ledger_path)
    except Exception:  # noqa: BLE001  ledger 不可读：回退内置，watch 保持只读不报错
        return patterns, f"builtin OOM/NaN/crash（ledger 不可读：{ledger_path}）"
    exps = {e.get("id"): e for e in (data or {}).get("experiments") or [] if isinstance(e, dict)}
    signals = (exps.get(run_id) or {}).get("failure_signals")
    if not isinstance(signals, list) or not signals:
        return patterns, fallback
    custom = []
    for sig in signals:
        s = str(sig).strip()
        if not s or s in builtin_names or s in STRUCTURAL_SIGNALS:
            continue  # 内置已含 / 结构化检查已覆盖
        try:
            pat = re.compile(s, re.IGNORECASE)
        except re.error:
            pat = re.compile(re.escape(s), re.IGNORECASE)
        custom.append((s, pat))
    patterns.extend(custom)
    src = f"builtin + card failure_signals（{ledger_path}"
    src += f"，自定义 {len(custom)} 条）" if custom else "，无额外日志 pattern）"
    return patterns, src


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
    ledger_path = Path(args.ledger) if args.ledger else LEDGER
    failure_patterns, signal_source = _load_failure_signals(ledger_path, args.run_id)

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
                ck_fresh = ck_age is not None and ck_age <= args.heartbeat_timeout
                checks.append(("checkpoint", ck_fresh,
                               f"latest={ckpts[0].name} age={None if ck_age is None else round(ck_age, 1)}s"))
                if not ck_fresh:
                    alert(
                        "stale-checkpoint",
                        f"最新 checkpoint {ckpts[0].name} 停更超过 {args.heartbeat_timeout}s"
                        f"（age={None if ck_age is None else round(ck_age, 1)}s）",
                    )

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

        # failure signals（有界日志尾部扫描；pattern 集 = 内置 + card failure_signals）
        tail_lines = _tail(workdir / "job.log", args.log_tail)
        checks.append(("log-tail", True, f"scanned last {len(tail_lines)} lines (bound={args.log_tail})"))
        for sig, pattern in failure_patterns:
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
    print(f'  failure_signal_source: "{signal_source}"')
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


FAKE_JOB_CANONICAL = (_HERE / "fake_job.py").resolve()


def _resolve_ledger(arg: str | None) -> tuple[Path | None, bool, str | None]:
    """approval 只认 canonical ledger；--ledger 覆盖仅允许临时目录下的测试 ledger。

    返回 (path, test_mode, reject_reason)。信任模型（诚实界定，见 .agent/human-gates.md）：
    ledger 里的三字段批准记录是**可审计**不是**防伪造**——repo 内谁都能写文件；真正的
    防线是 ledger 变更走 git commit（可追溯归因）+ apply-recovery 本身是 permission 层
    gated 入口（ask/prompt）。锁死路径是为了让「批准记录」至少来自那份被 git 跟踪、
    被 validator 校验的 canonical 文件，而不是任意自造输入（如 /dev/stdin）。
    """
    if not arg:
        return LEDGER, False, None
    p = Path(arg)
    try:
        rp = p.resolve()
    except OSError as e:
        return None, False, f"--ledger 无法解析：{e}"
    if rp == LEDGER.resolve():
        return rp, False, None
    tmp_root = Path(tempfile.gettempdir()).resolve()
    if tmp_root == rp or tmp_root in rp.parents:
        return rp, True, None  # 测试 ledger：允许但显式标记 TEST MODE
    return None, False, (
        f"--ledger 只接受 canonical 路径 {LEDGER}（或 {tmp_root} 下的测试 ledger，"
        "带 TEST MODE 标记）。批准记录必须来自 git 跟踪的 canonical ledger，"
        "不接受任意文件/流（如 /dev/stdin）自造批准。"
    )


def _approved_command_reason(command: str, run_id: str) -> str | None:
    """核对已批准命令确实是「同一个 fake job」的 local-fake 动作。

    - 脚本路径 resolve 后必须**等于** repo 内 canonical fake_job.py 的绝对路径
      （不是字符串后缀匹配——/tmp/evil/lab/infra/launch/fake_job.py 会被拒）。
    - 命令的 --run-id 必须与 alert 所属 run 精确一致（run-a 的批准不能执行 run-b）。
    返回 None = 通过；str = 拒绝理由。
    """
    try:
        tokens = shlex.split(command)
    except ValueError:
        return "命令无法解析（引号不闭合？）"
    if len(tokens) < 3:
        return "命令过短，不是合法的 fake_job.py 调用"
    if os.path.basename(tokens[0]) not in ("python", "python3"):
        return f"入口 {tokens[0]} 不是 python/python3 直接调用"
    script = Path(tokens[1])
    if not script.is_absolute():
        script = REPO_ROOT / script  # 执行时 cwd=REPO_ROOT，与执行语义一致
    try:
        script = script.resolve()
    except OSError as e:
        return f"脚本路径无法解析：{e}"
    if script != FAKE_JOB_CANONICAL:
        return (
            f"脚本 {tokens[1]} resolve 后为 {script}，不是 repo 内 canonical "
            f"fake_job.py（{FAKE_JOB_CANONICAL}）"
        )
    if tokens[2] not in ("launch", "kill", "restart"):
        return f"动作 {tokens[2]} 不在允许集 launch/kill/restart"
    cmd_run_id = None
    for i, t in enumerate(tokens):
        if t == "--run-id" and i + 1 < len(tokens):
            cmd_run_id = tokens[i + 1]
        elif t.startswith("--run-id="):
            cmd_run_id = t.split("=", 1)[1]
    if cmd_run_id is None:
        return "命令缺 --run-id，无法核对是否针对同一 run"
    if cmd_run_id != run_id:
        return (
            f"命令的 --run-id {cmd_run_id} 与 alert 所属 run {run_id} 不一致"
            "（run-a 的批准不能执行 run-b）"
        )
    return None


def cmd_apply_recovery(args: argparse.Namespace) -> int:
    ledger_path, test_mode, reject = _resolve_ledger(args.ledger)
    if reject:
        print(f"[expctl] 拒绝：{reject}", file=sys.stderr)
        return 2
    if test_mode:
        print(f"[expctl] TEST MODE：使用临时目录下的非 canonical ledger（{ledger_path}）——"
              "仅供测试，正式批准记录必须落在 lab/research/experiment-ledger.yaml。")
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
    cmd_reason = _approved_command_reason(command, args.run_id)
    if cmd_reason:
        print(
            f"[expctl] 拒绝执行：已批准命令超出 local-fake 范围或指向不同 run：{cmd_reason}"
            "（本 issue 的半自动执行仅限 repo 内 fake_job.py 对同一 run 的动作，"
            "见 plan 非目标与 .agent/action-boundary.md）。",
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

        # 3b. 自定义 failure signal（card/ledger 的 failure_signals 并入日志扫描）
        with (w / "job.log").open("a", encoding="utf-8") as f:
            f.write("CUDA error: device-side assert triggered\n")
        sig_ledger = root / "signals-ledger.yaml"
        sig_ledger.write_text(
            "experiments:\n"
            "  - id: t-w\n"
            "    status: running\n"
            '    failure_signals: [OOM, NaN, "CUDA error"]\n',
            encoding="utf-8",
        )
        r = run(["watch", "--run-id", "t-w", "--workdir", str(w), "--heartbeat-timeout", "5",
                 "--ledger", str(sig_ledger)])
        expect(r.returncode == 3 and "CUDA error" in r.stdout,
               f"自定义 failure signal 应命中并出 alert：\n{r.stdout}")
        expect("card failure_signals" in r.stdout, "watch 应注明 signal 来源为 card")
        # 3c. ledger 无该 run 的 failure_signals → 回退内置并注明
        r = run(["watch", "--run-id", "t-w", "--workdir", str(w), "--heartbeat-timeout", "5"])
        expect("回退内置" in r.stdout or "builtin" in r.stdout, "缺 card signals 应注明回退内置")

        w2 = root / "stalled"
        subprocess.run(  # noqa: S603
            [sys.executable, fake_job, "launch", "--run-id", "t-s", "--workdir", str(w2),
             "--duration", "12", "--interval", "0.2", "--stall-after", "3"],
            capture_output=True, check=True)
        time.sleep(4.0)
        r = run(["watch", "--run-id", "t-s", "--workdir", str(w2), "--heartbeat-timeout", "2"])
        expect(r.returncode == 3, f"stall 应 exit 3：exit={r.returncode}\n{r.stdout}")
        expect("metric-stall" in r.stdout and "proposal:" in r.stdout, "stall 应产出 alert+提案")
        expect("stale-checkpoint" in r.stdout, "checkpoint 停更应产出 stale-checkpoint alert（而非只记 ok:false）")
        expect(f"--run-id t-s" in r.stdout, "提案命令应指向同一 run")

        # 4. watch bounded：日志行数上限生效（scanned 行数 ≤ bound）
        r2 = run(["watch", "--run-id", "t-s", "--workdir", str(w2), "--log-tail", "2",
                  "--heartbeat-timeout", "2"])
        m = re.search(r"scanned last (\d+) lines \(bound=2\)", r2.stdout)
        expect(m is not None and int(m.group(1)) <= 2, f"log tail 应有界：\n{r2.stdout}")

        # 5. apply-recovery：批准缺失 → 拒绝(2)；批 A 执 B → 拒绝(2)；非 local → 拒绝(2)；
        #    伪 ledger 路径 → 拒绝(2)；run-id 不匹配 → 拒绝(2)；假路径 fake_job → 拒绝(2)；
        #    齐备且匹配 → 执行成功(0) 且 job 恢复 running
        cmd_restart = f"python lab/infra/launch/fake_job.py restart --run-id t-s --workdir {w2}"
        ledger = root / "ledger.yaml"

        def write_ledger(alert_extra: str, command: str = cmd_restart) -> None:
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
                f'          command: "{command}"\n'
                '          radius: "fake/local only"\n'
                + alert_extra,
                encoding="utf-8",
            )

        def approved(command: str = cmd_restart) -> str:
            return ('        approved_by: "h"\n        approved_at: "2026-07-13"\n'
                    f'        approved_action: "{command}"\n')

        write_ledger("")  # 无批准
        r = run(["apply-recovery", "--ledger", str(ledger), "--run-id", "t-s", "--alert-id", "alert-1"])
        expect(r.returncode == 2 and "缺批准字段" in r.stderr, "无批准应拒绝")

        write_ledger('        approved_by: "h"\n        approved_at: "2026-07-13"\n'
                     '        approved_action: "some other command"\n')
        r = run(["apply-recovery", "--ledger", str(ledger), "--run-id", "t-s", "--alert-id", "alert-1"])
        expect(r.returncode == 2 and "不一致" in r.stderr, "批 A 执 B 应拒绝")

        cmd_sbatch = "sbatch real.sh"
        write_ledger(approved(cmd_sbatch), command=cmd_sbatch)
        r = run(["apply-recovery", "--ledger", str(ledger), "--run-id", "t-s", "--alert-id", "alert-1"])
        expect(r.returncode == 2 and "local-fake" in r.stderr, "真实后端命令应拒绝")

        # 伪 ledger（BLOCKER-2）：canonical / 临时目录之外的 --ledger 一律拒绝
        r = run(["apply-recovery", "--ledger", str(REPO_ROOT / "README.md"),
                 "--run-id", "t-s", "--alert-id", "alert-1"])
        expect(r.returncode == 2 and "canonical" in r.stderr, "非 canonical 且非临时目录的 ledger 应拒绝")

        # run-id 不匹配（BLOCKER-3）：run-a 的批准不能执行 run-b
        cmd_other = f"python lab/infra/launch/fake_job.py restart --run-id t-other --workdir {w2}"
        write_ledger(approved(cmd_other), command=cmd_other)
        r = run(["apply-recovery", "--ledger", str(ledger), "--run-id", "t-s", "--alert-id", "alert-1"])
        expect(r.returncode == 2 and "不能执行 run-b" in r.stderr, "批准命令指向其他 run 应拒绝")

        # 假路径 fake_job（BLOCKER-3）：路径 resolve 必须等于 repo 内 canonical fake_job.py
        cmd_evil = f"python /tmp/evil/lab/infra/launch/fake_job.py restart --run-id t-s --workdir {w2}"
        write_ledger(approved(cmd_evil), command=cmd_evil)
        r = run(["apply-recovery", "--ledger", str(ledger), "--run-id", "t-s", "--alert-id", "alert-1"])
        expect(r.returncode == 2 and "canonical" in r.stderr, "非 repo 内 fake_job.py 应拒绝")

        write_ledger(approved())
        r = run(["apply-recovery", "--ledger", str(ledger), "--run-id", "t-s", "--alert-id", "alert-1"])
        expect(r.returncode == 0, f"齐备批准应执行成功：{r.stderr}")
        expect("TEST MODE" in r.stdout, "非 canonical 测试 ledger 应显式标记 TEST MODE")
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
    p.add_argument("--ledger", default=None,
                   help="读取该 run 的 failure_signals（默认 canonical ledger；只读）")

    p = sub.add_parser("apply-recovery", help="执行 ledger 里一条已获 human 批准的提案（human gate 入口）")
    p.add_argument("--run-id", required=True)
    p.add_argument("--alert-id", required=True)
    p.add_argument("--ledger", default=None,
                   help="仅接受 canonical ledger 路径；临时目录下的测试 ledger 会标记 TEST MODE")
    p.add_argument("--dry-run", action="store_true")

    args = parser.parse_args(argv)
    handlers = {
        "detect": cmd_detect, "plan": cmd_plan,
        "watch": cmd_watch, "apply-recovery": cmd_apply_recovery,
    }
    return handlers[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
