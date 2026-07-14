#!/usr/bin/env python3
"""doc-lifecycle 双 runtime hook 协议与 continuity 的 synthetic 探针。

以 stdin JSON 喂 `.claude/hooks/context_continuity.py`（Claude 与 Codex 共用同一物理 hook），
覆盖三个边界事件，断言与 plan 定案（决策 11b：本轮不扩展 startup 注入）一致的行为：

1. `SessionStart(source=startup)`  → 期望 **0 输出**（fresh startup 靠入口纪律读当前 plan 指针，
   不靠 hook 注入；见 plans/20260712-plan-lifecycle-state.zh.md revision log）。
2. `SessionStart(source=clear)`    → 期望回注 `memory/current-status.md`，且含「当前 plan 指针」节。
3. `SessionStart(source=compact)` → 期望同 2。

并对真实失败暴露的两个相邻注入 hook 做协议回归：所有非空 stdout 必须是唯一 JSON
对象，事件名必须匹配，文本只能放在 hookSpecificOutput.additionalContext；这防止 plain-text
stdout 再被 Codex 运行时以 invalid hook JSON 拒绝。

用法：
  python3 lab/evals/doc-lifecycle/run-continuity-probes.py            # 断言模式，exit 0/1
  python3 lab/evals/doc-lifecycle/run-continuity-probes.py --record   # 附带打印可粘贴的证据块

注意：这是 synthetic 探针（直接喂 hook 进程），**不能替代**真实 fresh Claude/Codex session 的
runtime 冒烟（hook trust、matcher 接线、注入是否真正进上下文）——那部分见同目录
`runtime-smoke-checklist.md`，由监控员/human 执行。无第三方依赖。
"""
from __future__ import annotations

import datetime
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
HOOK = REPO / ".claude" / "hooks" / "context_continuity.py"
IDENTITY_HOOK = REPO / ".claude" / "hooks" / "agent_identity_hook.py"
THRESHOLD_HOOK = REPO / ".claude" / "hooks" / "context_threshold_notice.py"
POINTER_MARK = "当前 plan 指针"


def _additional_context(stdout: str, event: str) -> str | None:
    try:
        data = json.loads(stdout)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(data, dict) or set(data) != {"hookSpecificOutput"}:
        return None
    specific = data["hookSpecificOutput"]
    if not isinstance(specific, dict) or set(specific) != {"hookEventName", "additionalContext"}:
        return None
    if specific.get("hookEventName") != event:
        return None
    context = specific.get("additionalContext")
    return context if isinstance(context, str) and context else None


CONTINUITY_PROBES = [
    (
        "SessionStart(source=startup) 不注入",
        {"hook_event_name": "SessionStart", "source": "startup"},
        lambda out: out.strip() == "",
    ),
    (
        "SessionStart(source=clear) 回注 current-status + plan 指针",
        {"hook_event_name": "SessionStart", "source": "clear"},
        lambda out: (
            (context := _additional_context(out, "SessionStart")) is not None
            and "[continuity]" in context
            and POINTER_MARK in context
        ),
    ),
    (
        "SessionStart(source=compact) 回注 current-status + plan 指针",
        {"hook_event_name": "SessionStart", "source": "compact"},
        lambda out: (
            (context := _additional_context(out, "SessionStart")) is not None
            and "[continuity]" in context
            and POINTER_MARK in context
        ),
    ),
]


def _run(
    hook: Path,
    payload: dict,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(hook)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )


def main(argv: list[str]) -> int:
    record = "--record" in argv
    hooks = (HOOK, IDENTITY_HOOK, THRESHOLD_HOOK)
    missing = [str(path) for path in hooks if not path.is_file()]
    if missing:
        print(f"FAIL 找不到 hook：{', '.join(missing)}")
        return 1
    failures = 0
    evidence: list[str] = []
    print("[doc-lifecycle continuity probes] synthetic stdin 探针")
    for name, payload, ok in CONTINUITY_PROBES:
        proc = _run(HOOK, payload)
        passed = proc.returncode == 0 and ok(proc.stdout)
        failures += 0 if passed else 1
        print(f"  {'PASS' if passed else 'FAIL'}  {name} "
              f"(exit {proc.returncode}, stdout {len(proc.stdout)} chars)")
        if record:
            head = proc.stdout if len(proc.stdout) <= 400 else proc.stdout[:400] + "…（截断）"
            evidence.append(
                f"### {name}\n\n- payload: `{json.dumps(payload, ensure_ascii=False)}`\n"
                f"- exit: {proc.returncode} · stdout: {len(proc.stdout)} chars\n"
                f"- stdout 头部：\n\n```\n{head or '（空）'}\n```\n"
            )

    with tempfile.TemporaryDirectory(prefix="doc-lifecycle-hook-probes-") as tmp:
        env = os.environ.copy()
        env["TMPDIR"] = tmp

        identity_session = "identity-json-probe"
        identity_payload = {
            "hook_event_name": "UserPromptSubmit",
            "session_id": identity_session,
        }
        env["AGENT_NAME"] = ""
        proc = _run(IDENTITY_HOOK, identity_payload, env)
        context = _additional_context(proc.stdout, "UserPromptSubmit")
        passed = proc.returncode == 0 and context is not None and "[identity]" in context
        failures += 0 if passed else 1
        print(f"  {'PASS' if passed else 'FAIL'}  UserPromptSubmit identity JSON 协议")

        env["AGENT_NAME"] = "test-persona"
        proc = _run(
            IDENTITY_HOOK,
            {"hook_event_name": "SessionStart", "source": "clear", "session_id": identity_session},
            env,
        )
        context = _additional_context(proc.stdout, "SessionStart")
        passed = proc.returncode == 0 and context is not None and "test-persona" in context
        failures += 0 if passed else 1
        print(f"  {'PASS' if passed else 'FAIL'}  SessionStart identity JSON 协议")

        transcript = Path(tmp) / "transcript.jsonl"
        transcript.write_text(
            json.dumps(
                {
                    "message": {
                        "model": "probe-model",
                        "usage": {
                            "input_tokens": 80,
                            "cache_read_input_tokens": 0,
                            "cache_creation_input_tokens": 0,
                        },
                    }
                }
            )
            + "\n",
            encoding="utf-8",
        )
        env["CLAUDE_CTX_WINDOW"] = "100"
        proc = _run(
            THRESHOLD_HOOK,
            {
                "hook_event_name": "UserPromptSubmit",
                "session_id": "threshold-json-probe",
                "transcript_path": str(transcript),
            },
            env,
        )
        context = _additional_context(proc.stdout, "UserPromptSubmit")
        passed = proc.returncode == 0 and context is not None and "[context]" in context
        failures += 0 if passed else 1
        print(f"  {'PASS' if passed else 'FAIL'}  UserPromptSubmit threshold JSON 协议")

        env["AGENT_NAME"] = ""
        proc = _run(IDENTITY_HOOK, {"hook_event_name": "SessionStart", "source": "startup"}, env)
        passed = proc.returncode == 0 and proc.stdout.strip() == ""
        failures += 0 if passed else 1
        print(f"  {'PASS' if passed else 'FAIL'}  无身份 SessionStart 静默")

        proc = _run(HOOK, {"hook_event_name": "PostCompact", "trigger": "manual"}, env)
        passed = proc.returncode == 0 and proc.stdout.strip() == ""
        failures += 0 if passed else 1
        print(f"  {'PASS' if passed else 'FAIL'}  PostCompact 不输出非法注入字段")
    ok_all = failures == 0
    print(f"[doc-lifecycle continuity probes] {'OK' if ok_all else 'FAIL'} — {failures} failure(s)")
    if record:
        commit = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, cwd=str(REPO),
        ).stdout.strip()
        print("\n----- 证据块（粘贴到 evidence 记录） -----\n")
        print(f"- 日期：{datetime.date.today().isoformat()} · commit：{commit or '<unknown>'}")
        print("- 命令：`python3 lab/evals/doc-lifecycle/run-continuity-probes.py --record`\n")
        print("\n".join(evidence))
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
