#!/usr/bin/env python3
"""launch 命令门禁判定（registry 单一真源的消费端）。

被 `.claude/hooks/pre_tool_guard.py` 以 importlib 薄接线加载（Claude 与 Codex 共享同一
hook），判定一条 Bash 命令是否命中 `registry.yaml` 的 `gated_prefixes`（launch/kill/
restart 类计算副作用入口）。命中且未带 human 放行环境变量时，hook 地板拒绝。

设计约束：
- 零第三方依赖、必须快（每条 Bash 命令都会过一遍）。registry 的 gated_prefixes 按
  「每行一条 `- "..."`」的约定做行级提取，不做完整 YAML 解析。
- 放行语义与 push-main 地板同构：`CLAUDE_ALLOW_LAUNCH=1` / `CODEX_ALLOW_LAUNCH=1`
  （进程环境或命令前导赋值，单次）代表 human 对该次 launch 的明确放行；permission 层
  （settings.json ask / execpolicy prompt）仍会各自提示，本模块只是不可调的地板。
- 匹配做路径归一化：绝对路径 / `./` 前缀的脚本路径会折算成 repo 相对形态再比对，
  防止「换个写法就绕过前缀」。但本门禁是防误操作护栏，非对抗性沙箱
  （与 pre_tool_guard.py 的定位一致）。

对外 API：
- gate_reason(raw_cmd) -> str | None   # None = 放行；str = 拒绝理由
- load_gated_prefixes() -> list[str]
"""
from __future__ import annotations

import os
import re
import shlex
from pathlib import Path

_HERE = Path(__file__).resolve().parent
REGISTRY = _HERE / "registry.yaml"
# repo 根：lab/infra/launch/ 上溯三层。
REPO_ROOT = _HERE.parent.parent.parent

ALLOW_ENVS = ("CLAUDE_ALLOW_LAUNCH", "CODEX_ALLOW_LAUNCH")
_PREFIX_LINE = re.compile(r'^\s*-\s*"([^"]+)"\s*(?:#.*)?$')


def load_gated_prefixes(registry_path: Path | None = None) -> list[str]:
    """行级提取 gated_prefixes 块下的条目（无 PyYAML 依赖）。文件缺失返回空。"""
    path = registry_path or REGISTRY
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    prefixes: list[str] = []
    in_block = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("gated_prefixes:"):
            in_block = True
            continue
        if in_block:
            m = _PREFIX_LINE.match(line)
            if m:
                prefixes.append(m.group(1))
            elif stripped and not stripped.startswith("#"):
                break  # 块结束（遇到下一个顶层 key）
    return prefixes


def _norm_token(tok: str) -> str:
    """路径归一化：./ 前缀去掉；指向 repo 内的绝对路径折算成 repo 相对路径。"""
    t = tok.strip().strip('"').strip("'")
    if t.startswith("./"):
        t = t[2:]
    if t.startswith("/"):
        try:
            t = str(Path(t).resolve().relative_to(REPO_ROOT))
        except ValueError:
            pass  # repo 外的绝对路径保持原样
    return t


def _split_commands(raw_cmd: str) -> list[list[str]]:
    """按 ; | & 等把一条 bash 串切成若干简单命令 token 列表（与 pre_tool_guard 同思路）。"""
    try:
        lex = shlex.shlex(raw_cmd, posix=True, punctuation_chars=True)
        lex.whitespace_split = True
        toks = list(lex)
    except ValueError:
        toks = raw_cmd.split()
    cmds: list[list[str]] = []
    cur: list[str] = []
    for t in toks:
        if t and set(t) <= set(";|&<>()"):
            if cur:
                cmds.append(cur)
                cur = []
        else:
            cur.append(t)
    if cur:
        cmds.append(cur)
    return cmds


def _split_env(tokens: list[str]) -> tuple[list[str], list[str]]:
    i = 0
    while i < len(tokens) and re.match(r"^[A-Za-z_]\w*=", tokens[i]):
        i += 1
    return tokens[:i], tokens[i:]


def _env_allows(env_assignments: list[str]) -> bool:
    for env in ALLOW_ENVS:
        if os.environ.get(env, "").strip().lower() in ("1", "true", "yes"):
            return True
        for e in env_assignments:
            if re.match(rf"^{env}=(1|true|yes)$", e, re.IGNORECASE):
                return True
    return False


def _matches_prefix(tokens: list[str], prefix: str) -> bool:
    ptoks = prefix.split()
    if len(tokens) < len(ptoks):
        return False
    return all(_norm_token(tokens[i]) == ptoks[i] for i in range(len(ptoks)))


def gate_reason(raw_cmd: str) -> str | None:
    """命中 gated_prefixes 且未获 env 放行 → 返回拒绝理由；否则 None。"""
    if not raw_cmd.strip():
        return None
    prefixes = load_gated_prefixes()
    if not prefixes:
        return None
    for tokens in _split_commands(raw_cmd):
        envs, rest = _split_env(tokens)
        if not rest:
            continue
        for prefix in prefixes:
            if _matches_prefix(rest, prefix):
                if _env_allows(envs):
                    break  # 本段获 env 放行；继续查其余命令段
                return (
                    f"launch/kill/restart 类命令是 human gate（命中 launch registry 前缀 "
                    f"`{prefix}`，见 lab/infra/launch/registry.yaml 与 .agent/human-gates.md）。"
                    "需 human 明确放行：命令前加 `CLAUDE_ALLOW_LAUNCH=1 ` / "
                    "`CODEX_ALLOW_LAUNCH=1 `（单次），或先经 experiment-orchestrator 走"
                    "「提案 → human 批准」流程。"
                )
    return None


def _self_test() -> int:
    cases_block = [
        "python lab/infra/launch/fake_job.py launch --run-id r1 --workdir /tmp/x",
        "python3 lab/infra/launch/fake_job.py kill --run-id r1 --workdir /tmp/x",
        "sbatch train.sh",
        "scancel 12345",
        "runai submit job1 -i image",
        "echo ok && sbatch train.sh",
        f"python {REPO_ROOT}/lab/infra/launch/fake_job.py restart --run-id r1",
        "python ./lab/infra/launch/expctl.py apply-recovery --run-id r1 --alert-id a1",
    ]
    cases_allow = [
        "python lab/infra/launch/fake_job.py status --run-id r1",
        "python lab/infra/launch/expctl.py watch --run-id r1 --workdir /tmp/x",
        "python lab/infra/launch/expctl.py plan --action launch --run-id r1",
        "echo 'sbatch train.sh'",  # 引号内字面量不拦
        "kill 12345",  # 裸 kill 不在地板（permission 层已覆盖）
        "git status",
        "squeue --job 1",
        "CLAUDE_ALLOW_LAUNCH=1 sbatch train.sh",  # 前导赋值放行
    ]
    failed = 0
    for c in cases_block:
        if gate_reason(c) is None:
            print(f"FAIL 应拦未拦：{c}")
            failed += 1
    for c in cases_allow:
        if gate_reason(c) is not None:
            print(f"FAIL 应放未放：{c}")
            failed += 1
    # 进程级 env 放行
    os.environ["CLAUDE_ALLOW_LAUNCH"] = "1"
    if gate_reason("sbatch train.sh") is not None:
        print("FAIL 进程 env 放行失效")
        failed += 1
    del os.environ["CLAUDE_ALLOW_LAUNCH"]
    total = len(cases_block) + len(cases_allow) + 1
    print(f"[launch_gate --self-test] {'OK' if not failed else 'FAIL'} — {total - failed}/{total} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    import sys

    if "--self-test" in sys.argv:
        sys.exit(_self_test())
    cmd = " ".join(sys.argv[1:])
    reason = gate_reason(cmd)
    print(reason or "allow")
    sys.exit(2 if reason else 0)
