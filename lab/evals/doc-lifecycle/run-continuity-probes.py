#!/usr/bin/env python3
"""doc-lifecycle 双 runtime 冒烟的 synthetic 探针（issue #13 验证标准「双 runtime 冒烟」的可复跑部分）。

以 stdin JSON 喂 `.claude/hooks/context_continuity.py`（Claude 与 Codex 共用同一物理 hook），
覆盖三个边界事件，断言与 plan 定案（决策 11b：本轮不扩展 startup 注入）一致的行为：

1. `SessionStart(source=startup)`  → 期望 **0 输出**（fresh startup 靠入口纪律读当前 plan 指针，
   不靠 hook 注入；见 plans/20260712-plan-lifecycle-state.zh.md revision log）。
2. `SessionStart(source=clear)`    → 期望回注 `memory/current-status.md`，且含「当前 plan 指针」节。
3. `PostCompact`（Codex 独立事件） → 期望同 2。

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
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
HOOK = REPO / ".claude" / "hooks" / "context_continuity.py"
POINTER_MARK = "当前 plan 指针"

PROBES = [
    (
        "SessionStart(source=startup) 不注入",
        {"hook_event_name": "SessionStart", "source": "startup"},
        lambda out: out.strip() == "",
    ),
    (
        "SessionStart(source=clear) 回注 current-status + plan 指针",
        {"hook_event_name": "SessionStart", "source": "clear"},
        lambda out: "[continuity]" in out and POINTER_MARK in out,
    ),
    (
        "PostCompact 回注 current-status + plan 指针",
        {"hook_event_name": "PostCompact"},
        lambda out: "[continuity]" in out and POINTER_MARK in out,
    ),
]


def main(argv: list[str]) -> int:
    record = "--record" in argv
    if not HOOK.is_file():
        print(f"FAIL 找不到 hook：{HOOK}")
        return 1
    failures = 0
    evidence: list[str] = []
    print("[doc-lifecycle continuity probes] synthetic stdin 探针")
    for name, payload, ok in PROBES:
        proc = subprocess.run(
            [sys.executable, str(HOOK)],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            timeout=30,
        )
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
