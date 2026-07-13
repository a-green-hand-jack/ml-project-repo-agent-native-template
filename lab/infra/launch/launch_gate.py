#!/usr/bin/env python3
"""launch 命令门禁判定（registry 单一真源的消费端）。

被 `.claude/hooks/pre_tool_guard.py` 以 importlib 薄接线加载（Claude 与 Codex 共享同一
hook），判定一条 Bash 命令是否命中 `registry.yaml` 的 `gated_prefixes`（launch/kill/
restart 类计算副作用入口）。命中且未获 env 放行时，hook 地板拒绝。

设计约束：
- 零第三方依赖、必须快（每条 Bash 命令都会过一遍）。registry 的 gated_prefixes 按
  「每行一条 `- "..."`」的约定做行级提取，不做完整 YAML 解析。
- 匹配是 wrapper-robust 的（宁可误拦不漏拦，误拦有 env 放行路径）：
  * 脚本类前缀（`python <script> <action>`）：在命令段任意位置找归一化后的脚本路径，
    其后紧邻 token 为 action 即命中——`env python -u <script> launch`、`./<script> launch`
    都拦得住，与是否/如何调用解释器无关。
  * 可执行类前缀（sbatch/scancel/srun/runai …）：先剥离常见 wrapper
    （env/nohup/nice/stdbuf/timeout/setsid/time/command/exec/ionice 及其选项/时长/赋值参数）
    再做命令位匹配——`nohup sbatch`、`timeout 60 sbatch` 拦，`grep sbatch` 不拦。
- 放行语义（与 push-main 地板同构，且**诚实界定**）：`CLAUDE_ALLOW_LAUNCH=1` /
  `CODEX_ALLOW_LAUNCH=1`（命令内赋值或进程环境）只是 **advisory 级**放行——它作用于
  所加的命令；若 export 到进程环境则对整个 session 持续生效，**不是**单次消费的 human
  签名。不可绕过的确认在 permission 层：`.claude/settings.json` 的 ask 与
  `.codex/rules/default.rules` 的 prompt 仍会对每条 gated 命令各自提示。
- 路径归一化：绝对路径 / `./` 前缀的脚本路径折算成 repo 相对形态再比对。但本门禁是
  防误操作护栏，非对抗性沙箱（与 pre_tool_guard.py 的定位一致）：不为把命令藏进
  `bash -c "..."` / `python -c` 负责。

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
_ENV_ASSIGN = re.compile(r"^[A-Za-z_]\w*=")
_INTERPRETER = re.compile(r"^python(\d+(\.\d+)*)?$")
# 时长/数值参数（timeout 60 / nice 优先级数字等）。
_WRAPPER_NUM_ARG = re.compile(r"^\d+(\.\d+)?[smhd]?$")
# 常见 wrapper：剥掉后再匹配可执行类前缀。非穷举（非对抗性），漏网 wrapper 由
# permission 层 ask/prompt 兜底。
WRAPPERS = frozenset(
    {"env", "nohup", "nice", "stdbuf", "timeout", "setsid", "time", "command", "exec", "ionice"}
)


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
    while i < len(tokens) and _ENV_ASSIGN.match(tokens[i]):
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


def _strip_wrappers(tokens: list[str]) -> list[str]:
    """剥离前导 wrapper（env/nohup/timeout …）及其选项/时长/赋值参数，露出真实命令。"""
    toks = list(tokens)
    while toks:
        base = os.path.basename(toks[0])
        if base not in WRAPPERS:
            break
        # `command -v/-V x` 是查询不是执行：保留原样（不会匹配任何 gated 可执行名）。
        if base == "command" and len(toks) > 1 and toks[1] in ("-v", "-V"):
            break
        toks = toks[1:]
        while toks and (
            toks[0].startswith("-")
            or _WRAPPER_NUM_ARG.match(toks[0])
            or _ENV_ASSIGN.match(toks[0])
        ):
            toks = toks[1:]
    return toks


def _matches_prefix(tokens: list[str], prefix: str) -> bool:
    """wrapper-robust 匹配一条 gated prefix（语义见模块 docstring）。"""
    ptoks = prefix.split()
    if not ptoks:
        return False
    if _INTERPRETER.match(os.path.basename(ptoks[0])) and len(ptoks) >= 2:
        # 脚本类前缀：签名 = 归一化脚本路径 (+ 紧邻的 action)。任意位置扫描，
        # 解释器选项（python -u/-X …）与 wrapper 都影响不了脚本 token 本身。
        script = ptoks[1]
        action = ptoks[2] if len(ptoks) > 2 else None
        norm = [_norm_token(t) for t in tokens]
        for i, t in enumerate(norm):
            if t == script and (action is None or (i + 1 < len(norm) and norm[i + 1] == action)):
                return True
        return False
    # 可执行类前缀：剥 wrapper 后按命令位逐 token 匹配。
    stripped = [_norm_token(t) for t in _strip_wrappers(tokens)]
    if len(stripped) < len(ptoks):
        return False
    if os.path.basename(stripped[0]) != ptoks[0]:
        return False
    return all(stripped[i] == ptoks[i] for i in range(1, len(ptoks)))


def gate_reason(raw_cmd: str) -> str | None:
    """命中 gated_prefixes 且未获 env 放行 → 返回拒绝理由；否则 None。"""
    if not raw_cmd.strip():
        return None
    prefixes = load_gated_prefixes()
    if not prefixes:
        return None
    for tokens in _split_commands(raw_cmd):
        lead_envs, rest = _split_env(tokens)
        if not rest:
            continue
        # env 赋值可能在前导（FOO=1 cmd）也可能在 wrapper 后（env FOO=1 cmd）：都收集。
        envs = lead_envs + [t for t in rest if _ENV_ASSIGN.match(t)]
        for prefix in prefixes:
            if _matches_prefix(rest, prefix):
                if _env_allows(envs):
                    break  # 本段获 env 放行；继续查其余命令段
                return (
                    f"launch/kill/restart 类命令是 human gate（命中 launch registry 前缀 "
                    f"`{prefix}`，见 lab/infra/launch/registry.yaml 与 .agent/human-gates.md）。"
                    "需 human 明确放行：命令前加 `CLAUDE_ALLOW_LAUNCH=1 ` / "
                    "`CODEX_ALLOW_LAUNCH=1 `（advisory 放行，作用于所加命令/当前进程环境；"
                    "permission 层 ask/prompt 仍会确认），或先经 experiment-orchestrator 走"
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
        # wrapper / 解释器选项绕过（Codex 初审 BLOCKER-1 PoC 及变体）
        "env python lab/infra/launch/fake_job.py launch --run-id r1 --workdir /tmp/x",
        "python -u lab/infra/launch/fake_job.py launch --run-id r1",
        "env -i python3 -X utf8 lab/infra/launch/fake_job.py kill --run-id r1",
        "env python -u lab/infra/launch/expctl.py apply-recovery --run-id r1 --alert-id a1",
        "./lab/infra/launch/fake_job.py launch --run-id r1",
        "nohup sbatch train.sh",
        "timeout 60 sbatch train.sh",
        "timeout -k 5 60s sbatch train.sh",
        "nice -n 10 scancel 12345",
        "stdbuf -oL srun --pty bash",
        "setsid runai submit job1 -i image",
        "nohup nice -n 5 sbatch train.sh",  # 嵌套 wrapper
        "command sbatch train.sh",
        "FOO=1 sbatch train.sh",  # 无关赋值不构成放行
    ]
    cases_allow = [
        "python lab/infra/launch/fake_job.py status --run-id r1",
        "env python lab/infra/launch/fake_job.py status --run-id r1",  # 只读入口带 wrapper 也放
        "python lab/infra/launch/expctl.py watch --run-id r1 --workdir /tmp/x",
        "python lab/infra/launch/expctl.py plan --action launch --run-id r1",
        "echo 'sbatch train.sh'",  # 引号内字面量不拦
        "grep -rn sbatch lab/",  # 非命令位出现 gated 词不拦
        "command -v sbatch",  # 可用性查询不拦
        "kill 12345",  # 裸 kill 不在地板（permission 层已覆盖）
        "git status",
        "squeue --job 1",
        "timeout 60 pytest -q",  # wrapper + 非 gated 命令不拦
        "CLAUDE_ALLOW_LAUNCH=1 sbatch train.sh",  # 前导赋值放行
        "env CODEX_ALLOW_LAUNCH=1 sbatch train.sh",  # env wrapper 内赋值放行
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
    # 进程级 env 放行（advisory：对整个进程环境生效）
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
