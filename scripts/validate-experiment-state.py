#!/usr/bin/env python3
"""实验状态机 / 必填字段 / 闭环 校验（experiment control plane 的机器门禁）。

对应 plans/20260712-experiment-control-plane.zh.md 任务 A/B/G：
1. 状态机：`planned → approved → running → done|failed`，`done|failed → superseded`；
   其他转换非法。每个 ledger 条目用 `status_history`（逐步追加，validator 逐步校验）
   证明自己的转换路径合法——快照式校验因此也能拦「done 又转回 running」这类非法转换。
2. 必填字段：进入 `approved`（及之后任何状态）前，commit / config / data_split /
   expected_runtime（budget）/ success_metric 必须非空且非 `<...>` 占位；
   同时 approved_by / approved_at 必须落记录。
3. alert 审计：`alerts[]` 条目若带任何批准字段，approved_by / approved_at /
   approved_action 三者必须齐备，且 approved_action 与 proposal.command 完全一致
   （防「批 A 执 B」）。
4. 闭环（status=done）：run_summary 字段非占位且文件存在，且 lab/artifacts/*-index.yaml
   有引用该 run id 的条目；缺任一环节报告缺口而非静默。

独立脚本（仿 check-same-commit.py 先例），由 validate-governance.py 经 run_subcheck 拉起。
YAML 解析：优先 PyYAML；无 PyYAML 时用内置受限解析器（block-style 子集：嵌套 mapping /
sequence / 内联 list / 引号标量；ledger 与 registry 按约定保持 block style）。
退出码 0 = 通过；1 = 有 error（--strict 时 warning 也算失败）。--self-test 跑内嵌 fixture。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LEDGER_REL = "lab/research/experiment-ledger.yaml"

STATUSES = ("planned", "approved", "running", "done", "failed", "superseded")
ALLOWED_TRANSITIONS = {
    ("planned", "approved"),
    ("approved", "running"),
    ("running", "done"),
    ("running", "failed"),
    ("done", "superseded"),
    ("failed", "superseded"),
}
# 进入 approved（含之后状态）必须齐备的字段（任务 B1；expected_runtime 即 budget）。
APPROVAL_REQUIRED_FIELDS = ("commit", "config", "data_split", "expected_runtime", "success_metric")
PROMOTE_VALUES = ("no", "unclear", "yes")


# ------------------------------------------------- 受限 YAML 解析（无 PyYAML 回退） ----


def _scalar(text: str):
    t = text.strip()
    if t == "" or t in ("null", "~"):
        return None
    if t.startswith('"'):
        m = re.match(r'^"((?:[^"\\]|\\.)*)"', t)
        if m:
            return m.group(1).replace('\\"', '"')
    if t.startswith("'"):
        m = re.match(r"^'([^']*)'", t)
        if m:
            return m.group(1)
    t = t.split(" #")[0].strip()  # 行尾注释（未引号值）
    if t.startswith("[") and t.endswith("]"):
        inner = t[1:-1].strip()
        return [] if not inner else [_scalar(x) for x in inner.split(",")]
    if re.fullmatch(r"-?\d+", t):
        return int(t)
    # 对齐 PyYAML（YAML 1.1）的布尔字面量，保证两条解析路径结构等价
    if t.lower() in ("true", "yes", "on"):
        return True
    if t.lower() in ("false", "no", "off"):
        return False
    return t


def _lines(text: str) -> list[tuple[int, str]]:
    out = []
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        out.append((len(raw) - len(raw.lstrip(" ")), raw.strip()))
    return out


def _parse_block(lines: list[tuple[int, str]], i: int, indent: int):
    """解析 indent 层级的一个 block（mapping 或 sequence）。返回 (value, next_i)。"""
    if i >= len(lines) or lines[i][0] < indent:
        return None, i
    if lines[i][1].startswith("- ") or lines[i][1] == "-":
        return _parse_seq(lines, i, indent)
    return _parse_map(lines, i, indent)


def _parse_map(lines: list[tuple[int, str]], i: int, indent: int):
    out: dict = {}
    while i < len(lines):
        ind, text = lines[i]
        if ind < indent or text.startswith("- "):
            break
        if ind > indent:
            raise ValueError(f"意外缩进：{text!r}")
        m = re.match(r"^([\w.\-]+):(.*)$", text)
        if not m:
            raise ValueError(f"无法解析行：{text!r}")
        key, rest = m.group(1), m.group(2).strip()
        i += 1
        if rest:
            out[key] = _scalar(rest)
        elif i < len(lines) and lines[i][0] > indent:
            out[key], i = _parse_block(lines, i, lines[i][0])
        elif i < len(lines) and lines[i][0] == indent and lines[i][1].startswith("- "):
            # 同缩进的 sequence 挂在上一个 key 下（常见 YAML 风格）
            out[key], i = _parse_seq(lines, i, indent)
        else:
            out[key] = None
    return out, i


def _parse_seq(lines: list[tuple[int, str]], i: int, indent: int):
    out: list = []
    while i < len(lines):
        ind, text = lines[i]
        if ind != indent or not (text.startswith("- ") or text == "-"):
            break
        content = text[2:].strip() if text.startswith("- ") else ""
        item_indent = ind + 2
        if not content:
            i += 1
            val, i = _parse_block(lines, i, lines[i][0] if i < len(lines) else item_indent)
            out.append(val)
            continue
        m = re.match(r"^([\w.\-]+):(.*)$", content)
        if m:
            # dict 项：把首行折算成 item_indent 的一行，与后续更深行一起解析
            sub = [(item_indent, content)]
            i += 1
            while i < len(lines) and lines[i][0] >= item_indent and not (
                lines[i][0] == indent
            ):
                sub.append(lines[i])
                i += 1
            val, _ = _parse_map(sub, 0, item_indent)
            out.append(val)
        else:
            out.append(_scalar(content))
            i += 1
    return out, i


def load_yaml_compat(text: str):
    """受限 YAML 解析（block-style 子集）。解析失败抛 ValueError。"""
    lines = _lines(text)
    if not lines:
        return None
    val, i = _parse_block(lines, 0, lines[0][0])
    if i < len(lines):
        raise ValueError(f"存在未消费的行（从 {lines[i][1]!r} 起）——超出受限解析器子集")
    return val


def load_yaml(text: str):
    """优先 PyYAML，缺失时回退受限解析器。返回 (data, parser_name)。"""
    try:
        import yaml  # type: ignore

        return yaml.safe_load(text), "pyyaml"
    except ImportError:
        return load_yaml_compat(text), "compat"


# ----------------------------------------------------------------- 校验规则 ----


def _is_placeholder(v) -> bool:
    return v is None or (isinstance(v, str) and (not v.strip() or v.strip().startswith("<")))


def _check_history(exp: dict, errors: list[str]) -> None:
    eid, status = exp.get("id"), exp.get("status")
    history = exp.get("status_history")
    if not history:
        if status != "planned":
            errors.append(f"{eid}: status={status} 但缺 status_history（只有 planned 可省略）")
        return
    if not isinstance(history, list):
        errors.append(f"{eid}: status_history 应为列表")
        return
    seq = []
    for idx, h in enumerate(history):
        if not isinstance(h, dict) or "status" not in h:
            errors.append(f"{eid}: status_history[{idx}] 缺 status 字段")
            return
        if _is_placeholder(h.get("at")):
            errors.append(f"{eid}: status_history[{idx}]（{h['status']}）缺 at 时间戳")
        seq.append(h["status"])
    if seq[0] != "planned":
        errors.append(f"{eid}: status_history 必须从 planned 开始（当前从 {seq[0]} 开始）")
    for a, b in zip(seq, seq[1:]):
        if (a, b) not in ALLOWED_TRANSITIONS:
            errors.append(
                f"{eid}: 非法状态转换 {a} → {b}"
                f"（合法：planned→approved→running→done|failed；done|failed→superseded）"
            )
    if seq[-1] != status:
        errors.append(f"{eid}: status={status} 与 status_history 末项 {seq[-1]} 不一致")


def _check_approval_fields(exp: dict, errors: list[str]) -> None:
    eid, status = exp.get("id"), exp.get("status")
    history = exp.get("status_history") or []
    reached_approved = status in ("approved", "running", "done", "failed", "superseded") or any(
        isinstance(h, dict) and h.get("status") == "approved" for h in history
    )
    if not reached_approved:
        return
    missing = [f for f in APPROVAL_REQUIRED_FIELDS if _is_placeholder(exp.get(f))]
    if missing:
        errors.append(
            f"{eid}: status={status} 已过 approved 门，但必填字段缺失/仍是占位：{', '.join(missing)}"
            "（进入 approved 前必须齐备 commit/config/data_split/expected_runtime/success_metric）"
        )
    for f in ("approved_by", "approved_at"):
        if _is_placeholder(exp.get(f)):
            errors.append(f"{eid}: status={status} 已过 approved 门，但缺 human 批准记录字段 {f}")


def _check_alerts(exp: dict, errors: list[str]) -> None:
    eid = exp.get("id")
    alerts = exp.get("alerts")
    if alerts in (None, []):
        return
    if not isinstance(alerts, list):
        errors.append(f"{eid}: alerts 应为列表")
        return
    for idx, a in enumerate(alerts):
        if not isinstance(a, dict):
            errors.append(f"{eid}: alerts[{idx}] 应为 mapping")
            continue
        aid = a.get("id") or f"alerts[{idx}]"
        for f in ("type", "at"):
            if _is_placeholder(a.get(f)):
                errors.append(f"{eid}: {aid} 缺 {f} 字段")
        approval = {f: a.get(f) for f in ("approved_by", "approved_at", "approved_action")}
        present = [f for f, v in approval.items() if not _is_placeholder(v)]
        if present and len(present) < 3:
            missing = [f for f in approval if f not in present]
            errors.append(
                f"{eid}: {aid} 批准记录不完整（有 {', '.join(present)} 但缺 {', '.join(missing)}）"
                "——批准必须同时落 approved_by/approved_at/approved_action"
            )
        proposal = a.get("proposal")
        if len(present) == 3 and isinstance(proposal, dict):
            cmd = proposal.get("command")
            if not _is_placeholder(cmd) and approval["approved_action"] != cmd:
                errors.append(
                    f"{eid}: {aid} approved_action 与 proposal.command 不一致"
                    "（批准的动作必须与提案确切命令逐字匹配）"
                )


def _artifact_index_run_ids(root: Path, warnings: list[str]) -> set[str]:
    ids: set[str] = set()
    for f in sorted((root / "lab" / "artifacts").glob("*-index.yaml")):
        try:
            data, _ = load_yaml(f.read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            warnings.append(f"artifact index 解析失败（跳过）：{f.name}: {e}")
            continue
        if not isinstance(data, dict):
            continue
        for entries in data.values():
            if not isinstance(entries, list):
                continue
            for entry in entries:
                if isinstance(entry, dict):
                    rid = entry.get("run_id") or entry.get("run")
                    if isinstance(rid, str):
                        ids.add(rid)
    return ids


def _check_closure(exp: dict, root: Path, artifact_run_ids: set[str], errors: list[str]) -> None:
    eid = exp.get("id")
    if exp.get("status") != "done":
        return
    summary = exp.get("run_summary")
    if _is_placeholder(summary):
        errors.append(f"{eid}: status=done 但 run_summary 仍是占位——闭环缺 run summary 环节")
    elif not (root / str(summary)).exists():
        errors.append(f"{eid}: status=done 但 run_summary 文件不存在：{summary}")
    if eid not in artifact_run_ids:
        errors.append(
            f"{eid}: status=done 但 lab/artifacts/*-index.yaml 无引用该 run 的条目"
            "（闭环缺 artifact index 环节；见 .agent/artifact-policy.md）"
        )


def check_ledger(root: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    ledger = root / LEDGER_REL
    if not ledger.exists():
        warnings.append(f"未找到 {LEDGER_REL}：跳过实验状态校验")
        return errors, warnings
    try:
        data, parser = load_yaml(ledger.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        # PyYAML 缺失且受限解析器失败：文件可能用了子集外语法——警告而非硬失败
        warnings.append(f"受限解析器无法解析 {LEDGER_REL}（{e}）；装 PyYAML 后重跑深检")
        return errors, warnings
    if parser == "compat":
        warnings.append("未安装 PyYAML：使用受限解析器（block-style 子集）")
    experiments = (data or {}).get("experiments") or []
    if not isinstance(experiments, list):
        errors.append("experiments 应为列表")
        return errors, warnings
    artifact_run_ids = _artifact_index_run_ids(root, warnings)
    seen: set[str] = set()
    for exp in experiments:
        if not isinstance(exp, dict):
            errors.append("发现非 mapping 的实验条目")
            continue
        eid = exp.get("id")
        if _is_placeholder(eid):
            errors.append("存在缺 id 的实验条目")
            continue
        if eid in seen:
            errors.append(f"{eid}: id 重复")
        seen.add(eid)
        status = exp.get("status")
        if status not in STATUSES:
            errors.append(f"{eid}: status 非法：{status}（应为 {'/'.join(STATUSES)}）")
            continue
        promote = exp.get("promote")
        if promote is True:  # YAML 1.1：yes → True
            promote = "yes"
        elif promote is False:  # no → False
            promote = "no"
        if promote not in (None, *PROMOTE_VALUES):
            errors.append(f"{eid}: promote 非法：{exp.get('promote')}")
        _check_history(exp, errors)
        _check_approval_fields(exp, errors)
        _check_alerts(exp, errors)
        _check_closure(exp, root, artifact_run_ids, errors)
    return errors, warnings


# ----------------------------------------------------------------- self-test ----

_FIXTURE_OK = """\
experiments:
  - id: run-ok
    status: done
    status_history:
      - status: planned
        at: "2026-07-01"
      - status: approved
        at: "2026-07-02"
      - status: running
        at: "2026-07-03"
      - status: done
        at: "2026-07-04"
    approved_by: "human-a"
    approved_at: "2026-07-02"
    commit: "abc1234"
    config: "lab/code/configs/x.yaml"
    data_split: "split-v1"
    expected_runtime: "5 min"
    success_metric: "loss < 0.1"
    run_summary: "lab/code/experiments/run-ok.md"
    alerts:
      - id: alert-1
        type: metric-stall
        at: "2026-07-03"
        evidence: "metrics.jsonl 停更 120s"
        proposal:
          action: restart
          command: "python lab/infra/launch/fake_job.py restart --run-id run-ok"
          radius: "fake/local only"
        approved_by: "human-a"
        approved_at: "2026-07-03"
        approved_action: "python lab/infra/launch/fake_job.py restart --run-id run-ok"
    promote: no
"""

_FIXTURE_BAD = """\
experiments:
  - id: run-skip-approval
    status: running
    status_history:
      - status: planned
        at: "2026-07-01"
      - status: running
        at: "2026-07-02"
    commit: "abc"
    config: "c.yaml"
    data_split: "s"
    expected_runtime: "1h"
    success_metric: "m"
  - id: run-zombie
    status: running
    status_history:
      - status: planned
        at: "2026-07-01"
      - status: approved
        at: "2026-07-02"
      - status: running
        at: "2026-07-03"
      - status: done
        at: "2026-07-04"
      - status: running
        at: "2026-07-05"
    approved_by: "h"
    approved_at: "2026-07-02"
    commit: "abc"
    config: "c.yaml"
    data_split: "s"
    expected_runtime: "1h"
    success_metric: "m"
  - id: run-missing-fields
    status: approved
    status_history:
      - status: planned
        at: "2026-07-01"
      - status: approved
        at: "2026-07-02"
    approved_by: "h"
    approved_at: "2026-07-02"
    commit: "<git sha>"
    config: "c.yaml"
    data_split: "s"
    success_metric: "m"
  - id: run-open-closure
    status: done
    status_history:
      - status: planned
        at: "2026-07-01"
      - status: approved
        at: "2026-07-02"
      - status: running
        at: "2026-07-03"
      - status: done
        at: "2026-07-04"
    approved_by: "h"
    approved_at: "2026-07-02"
    commit: "abc"
    config: "c.yaml"
    data_split: "s"
    expected_runtime: "1h"
    success_metric: "m"
    run_summary: "lab/code/experiments/does-not-exist.md"
  - id: run-bad-approval
    status: running
    status_history:
      - status: planned
        at: "2026-07-01"
      - status: approved
        at: "2026-07-02"
      - status: running
        at: "2026-07-03"
    approved_by: "h"
    approved_at: "2026-07-02"
    commit: "abc"
    config: "c.yaml"
    data_split: "s"
    expected_runtime: "1h"
    success_metric: "m"
    alerts:
      - id: alert-x
        type: stall
        at: "2026-07-03"
        proposal:
          action: restart
          command: "python lab/infra/launch/fake_job.py restart --run-id run-bad-approval"
        approved_by: "h"
        approved_at: "2026-07-03"
        approved_action: "some other command"
      - id: alert-y
        type: stall
        at: "2026-07-04"
        proposal:
          action: restart
          command: "python lab/infra/launch/fake_job.py restart --run-id run-bad-approval"
        approved_by: "h"
        approved_action: "python lab/infra/launch/fake_job.py restart --run-id run-bad-approval"
"""


def _self_test() -> int:
    import shutil
    import tempfile

    failed = 0

    def expect(cond: bool, msg: str) -> None:
        nonlocal failed
        if not cond:
            failed += 1
            print(f"FAIL {msg}")

    # 受限解析器与结构断言（不依赖 PyYAML）
    parsed = load_yaml_compat(_FIXTURE_OK)
    expect(parsed["experiments"][0]["id"] == "run-ok", "compat 解析 id")
    expect(parsed["experiments"][0]["status_history"][2]["status"] == "running", "compat 解析嵌套 seq")
    expect(parsed["experiments"][0]["alerts"][0]["proposal"]["action"] == "restart", "compat 解析深嵌套")
    try:
        import yaml  # type: ignore

        expect(yaml.safe_load(_FIXTURE_OK) == parsed, "受限解析器与 PyYAML 结构等价")
    except ImportError:
        pass

    root = Path(tempfile.mkdtemp(prefix="exp-state-selftest-"))
    try:
        # 合法 ledger：done 闭环齐备（造 run summary + artifact index）
        (root / "lab" / "research").mkdir(parents=True)
        (root / "lab" / "artifacts").mkdir(parents=True)
        (root / "lab" / "code" / "experiments").mkdir(parents=True)
        (root / LEDGER_REL).write_text(_FIXTURE_OK, encoding="utf-8")
        (root / "lab/code/experiments/run-ok.md").write_text("# run summary\n", encoding="utf-8")
        (root / "lab/artifacts/result-index.yaml").write_text(
            'results:\n  - id: result-1\n    run_id: "run-ok"\n', encoding="utf-8"
        )
        errors, _ = check_ledger(root)
        expect(errors == [], f"合法 ledger 应零 error，得到：{errors}")

        # 非法 ledger：逐条命中
        (root / LEDGER_REL).write_text(_FIXTURE_BAD, encoding="utf-8")
        errors, _ = check_ledger(root)
        text = "\n".join(errors)
        expect("run-skip-approval" in text and "planned → running" in text, "拦截跳过 approved")
        expect("run-zombie" in text and "done → running" in text, "拦截 done 回转 running")
        expect("run-skip-approval" in text and "approved_by" in text, "缺批准记录报错")
        expect("run-missing-fields" in text and "commit" in text, "缺必填字段清单报错")
        expect("run-open-closure" in text and "run_summary 文件不存在" in text, "闭环缺 summary 报错")
        expect("run-open-closure" in text and "artifact" in text, "闭环缺 artifact index 报错")
        expect("run-bad-approval" in text and "不一致" in text, "批 A 执 B 报错")
        expect("run-bad-approval" in text and "approved_at" in text, "批准记录不完整报错")
    finally:
        shutil.rmtree(root, ignore_errors=True)

    total_msg = "OK" if not failed else f"FAIL（{failed} 处）"
    print(f"[validate-experiment-state --self-test] {total_msg}")
    return 1 if failed else 0


# ---------------------------------------------------------------------- main ----


def main(argv: list[str]) -> int:
    if "--self-test" in argv:
        return _self_test()
    strict = "--strict" in argv
    errors, warnings = check_ledger(REPO)
    for w in warnings:
        print(f"WARN  {w}")
    for e in errors:
        print(f"ERROR {e}")
    ok = not errors and not (strict and warnings)
    print(f"[validate-experiment-state] {'OK' if ok else 'FAIL'} — {len(errors)} error(s), {len(warnings)} warning(s)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
