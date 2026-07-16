#!/usr/bin/env python3
"""实验状态机 / 必填字段 / 闭环 校验（experiment control plane 的机器门禁）。

对应 plans/20260712-experiment-control-plane.zh.md 任务 A/B/G：
1. 状态机：`planned → approved → running → done|failed`，`done|failed → superseded`；
   其他转换非法。每个 ledger 条目用 `status_history`（逐步追加，validator 逐步校验）
   证明自己的转换路径合法——快照式校验因此也能拦「done 又转回 running」这类非法转换。
2. 必填字段：进入 `approved`（及之后任何状态）前，commit / config / data_split /
   expected_runtime（budget）/ success_metric 必须非空且非 `<...>` 占位；
   同时 approved_by / approved_at 必须落记录。
3. alert 审计：提案必须绑定 command + workdir；若带任何批准字段，approved_by /
   approved_at / approved_action 三者必须齐备且逐字匹配 proposal.command。恢复消费状态
   必须满足 pending/executing/succeeded/failed 的字段不变量；当前 repo-local provenance
   不受信，因此 approval_provenance 只能为 null，actual recovery fail-closed。
4. 闭环（status=done）：run_summary 是 `lab/code/experiments/` 内 repo-relative、非 symlink
   regular file，且 lab/artifacts/*-index.yaml 有引用该 run id 的条目；绝对路径、traversal、
   repo/允许目录逃逸与缺任一环节均报告错误。
5. pre-governance 存量豁免（issue #63 D1）：条目可显式登记 `governance_status: legacy_unverified`
   + 非占位 `governance_note`，跳过 2/3/4（history/approval/closure）三项严格检查——用于本门禁
   落地前就已存在、无法回填真实证据的历史条目；不豁免 status/id 合法性与 alerts 审计；
   新条目（无此标记）判定严格度不放松。由 `scripts/init-governance-data.py` 登记，不手填猜测值。

独立脚本（仿 check-same-commit.py 先例），由 validate-governance.py 经 run_subcheck 拉起。
YAML 解析：优先 PyYAML；无 PyYAML 时用内置受限解析器（block-style 子集：嵌套 mapping /
sequence / 内联 list / 引号标量；ledger 与 registry 按约定保持 block style）。
退出码 0 = 通过；1 = 有 error（--strict 时 warning 也算失败）。--self-test 跑内嵌 fixture。
"""
from __future__ import annotations

import re
import stat
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LEDGER_REL = "lab/research/experiment-ledger.yaml"
RUN_SUMMARY_DIR_REL = Path("lab/code/experiments")

STATUSES = ("planned", "approved", "running", "done", "failed", "superseded")
# pre-governance 存量豁免（issue #63 D1）：entry 可选 governance_status=legacy_unverified +
# 非占位 governance_note，跳过 history/approval/closure 三项严格检查（结构校验仍适用）。
# 新条目（无此标记）判定严格度不放松；豁免范围只到这三项，不覆盖 status/id 合法性、alerts。
LEGACY_MARKER = "legacy_unverified"
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
RECOVERY_EXECUTION_STATUSES = ("pending", "executing", "succeeded", "failed")


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


def _check_legacy_marker(exp: dict, errors: list[str]) -> bool:
    """校验并返回该条目是否合法登记为 legacy_unverified。标记本身非法/不完整时返回
    False——不完整的豁免声明不能顺带换来豁免，仍须过正常严格检查。"""
    eid = exp.get("id")
    gs = exp.get("governance_status")
    if gs is None:
        return False
    if gs != LEGACY_MARKER:
        errors.append(f"{eid}: governance_status 非法：{gs!r}（合法值仅 {LEGACY_MARKER}）")
        return False
    if _is_placeholder(exp.get("governance_note")):
        errors.append(
            f"{eid}: governance_status={LEGACY_MARKER} 但缺非占位 governance_note"
            "（说明该条目为 pre-governance 存量、未验证，不是新数据不合规）"
        )
        return False
    return True


def _check_history(exp: dict, is_legacy: bool, errors: list[str]) -> None:
    if is_legacy:
        return
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


def _check_approval_fields(exp: dict, is_legacy: bool, errors: list[str]) -> None:
    if is_legacy:
        return
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
    seen_alert_ids: set[str] = set()
    for idx, a in enumerate(alerts):
        if not isinstance(a, dict):
            errors.append(f"{eid}: alerts[{idx}] 应为 mapping")
            continue
        aid = a.get("id")
        if not isinstance(aid, str) or _is_placeholder(aid):
            errors.append(f"{eid}: alerts[{idx}] 缺合法 id 字段")
            aid = f"alerts[{idx}]"
        elif aid in seen_alert_ids:
            errors.append(f"{eid}: alert id 重复：{aid}")
        else:
            seen_alert_ids.add(aid)
        for f in ("type", "at"):
            if not isinstance(a.get(f), str) or _is_placeholder(a.get(f)):
                errors.append(f"{eid}: {aid} 缺 {f} 字段")
        proposal = a.get("proposal")
        if not isinstance(proposal, dict):
            errors.append(f"{eid}: {aid} proposal 应为 mapping")
        else:
            for f in ("action", "command", "workdir", "radius"):
                if not isinstance(proposal.get(f), str) or _is_placeholder(proposal.get(f)):
                    errors.append(f"{eid}: {aid} proposal 缺 {f} 字段")
        approval = {f: a.get(f) for f in ("approved_by", "approved_at", "approved_action")}
        present = [f for f, v in approval.items() if not _is_placeholder(v)]
        for field in present:
            if not isinstance(approval[field], str):
                errors.append(f"{eid}: {aid} {field} 必须是非空字符串")
        if present and len(present) < 3:
            missing = [f for f in approval if f not in present]
            errors.append(
                f"{eid}: {aid} 批准记录不完整（有 {', '.join(present)} 但缺 {', '.join(missing)}）"
                "——批准必须同时落 approved_by/approved_at/approved_action"
            )
        if len(present) == 3 and isinstance(proposal, dict):
            cmd = proposal.get("command")
            if not _is_placeholder(cmd) and approval["approved_action"] != cmd:
                errors.append(
                    f"{eid}: {aid} approved_action 与 proposal.command 不一致"
                    "（批准的动作必须与提案确切命令逐字匹配）"
                )

        # repo-local YAML 字段可被任意进程伪造；在接入外部可信证明前，非空 provenance
        # 必须被拒绝，不能让审计元数据伪装成可执行 capability。
        if "approval_provenance" not in a:
            errors.append(f"{eid}: {aid} 缺 approval_provenance 字段（当前应为 null）")
        elif a.get("approval_provenance") is not None:
            errors.append(
                f"{eid}: {aid} approval_provenance 非 null，但当前无受信 provenance verifier；"
                "不得把 repo-local 声明当 human capability"
            )

        for f in ("consumed_at", "consumed_by", "execution_status", "execution_exit_code", "resolved"):
            if f not in a:
                errors.append(f"{eid}: {aid} 缺恢复状态字段 {f}")
        execution_status = a.get("execution_status")
        if execution_status not in RECOVERY_EXECUTION_STATUSES:
            errors.append(
                f"{eid}: {aid} execution_status 非法：{execution_status!r}"
                f"（应为 {'/'.join(RECOVERY_EXECUTION_STATUSES)}）"
            )
            continue
        consumed_at = a.get("consumed_at")
        consumed_by = a.get("consumed_by")
        for field, value in (("consumed_at", consumed_at), ("consumed_by", consumed_by)):
            if value is not None and (not isinstance(value, str) or _is_placeholder(value)):
                errors.append(f"{eid}: {aid} {field} 必须为 null 或非空字符串")
        consumed = not _is_placeholder(consumed_at) and not _is_placeholder(consumed_by)
        if _is_placeholder(consumed_at) != _is_placeholder(consumed_by):
            errors.append(f"{eid}: {aid} consumed_at / consumed_by 必须同时为空或同时落值")
        if not isinstance(a.get("resolved"), bool):
            errors.append(f"{eid}: {aid} resolved 必须是 boolean")
        exit_code = a.get("execution_exit_code")
        if execution_status == "pending":
            if consumed:
                errors.append(f"{eid}: {aid} pending 状态不得已有 consume 记录")
            if exit_code is not None or a.get("resolved") is not False:
                errors.append(f"{eid}: {aid} pending 必须 exit_code=null 且 resolved=false")
        elif execution_status == "executing":
            if not consumed:
                errors.append(f"{eid}: {aid} executing 必须已有原子 consume 记录")
            if exit_code is not None or a.get("resolved") is not False:
                errors.append(f"{eid}: {aid} executing 必须 exit_code=null 且 resolved=false")
        elif execution_status == "succeeded":
            if not consumed:
                errors.append(f"{eid}: {aid} succeeded 必须保留 consume 记录")
            if type(exit_code) is not int or exit_code != 0 or a.get("resolved") is not True:
                errors.append(f"{eid}: {aid} succeeded 必须 exit_code=0 且 resolved=true")
        elif execution_status == "failed":
            if not consumed:
                errors.append(f"{eid}: {aid} failed 必须保留 consume 记录")
            if type(exit_code) is not int or exit_code == 0 or a.get("resolved") is not False:
                errors.append(f"{eid}: {aid} failed 必须 exit_code=非零整数 且 resolved=false")


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


def _run_summary_reason(root: Path, value: object) -> str | None:
    """Validate a tracked summary without following links outside its documented directory."""
    if not isinstance(value, str) or not value.strip():
        return "必须是非空 repo-relative path"
    rel = Path(value)
    if rel.is_absolute():
        return "必须是 repo-relative path，不能是绝对路径"
    if ".." in rel.parts:
        return "不得含 .. traversal"
    allowed = root / RUN_SUMMARY_DIR_REL
    candidate = root / rel
    try:
        candidate.relative_to(allowed)
    except ValueError:
        return f"必须位于 {RUN_SUMMARY_DIR_REL}/"

    current = root
    for part in rel.parts:
        current /= part
        if current.is_symlink():
            return f"含 symlink component：{current.relative_to(root)}"
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(root.resolve())
        resolved.relative_to(allowed.resolve())
    except FileNotFoundError:
        return "文件不存在"
    except (OSError, ValueError) as exc:
        return f"解析后逃逸 repo/允许目录或无法解析：{exc}"
    try:
        mode = candidate.lstat().st_mode
    except OSError as exc:
        return f"无法读取文件状态：{exc}"
    if not stat.S_ISREG(mode):
        return "必须是 non-symlink regular file"
    return None


def _check_closure(
    exp: dict, root: Path, artifact_run_ids: set[str], is_legacy: bool, errors: list[str]
) -> None:
    eid = exp.get("id")
    if exp.get("status") != "done":
        return
    if is_legacy:
        return
    summary = exp.get("run_summary")
    if _is_placeholder(summary):
        errors.append(f"{eid}: status=done 但 run_summary 仍是占位——闭环缺 run summary 环节")
    else:
        reason = _run_summary_reason(root, summary)
        if reason:
            errors.append(f"{eid}: status=done 但 run_summary 非法：{summary}（{reason}）")
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
        is_legacy = _check_legacy_marker(exp, errors)
        _check_history(exp, is_legacy, errors)
        _check_approval_fields(exp, is_legacy, errors)
        _check_alerts(exp, errors)
        _check_closure(exp, root, artifact_run_ids, is_legacy, errors)
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
          command: "python lab/infra/launch/fake_job.py restart --run-id run-ok --workdir /tmp/run-ok"
          workdir: "/tmp/run-ok"
          radius: "fake/local only"
        approved_by: "human-a"
        approved_at: "2026-07-03"
        approved_action: "python lab/infra/launch/fake_job.py restart --run-id run-ok --workdir /tmp/run-ok"
        approval_provenance: null
        consumed_at: null
        consumed_by: null
        execution_status: pending
        execution_exit_code: null
        resolved: false
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
      - id: alert-z
        type: stall
        at: "2026-07-05"
        proposal:
          action: restart
          command: "python lab/infra/launch/fake_job.py restart --run-id run-bad-approval --workdir /tmp/run-bad-approval"
          workdir: "/tmp/run-bad-approval"
          radius: "fake/local only"
        approval_provenance: "self-asserted-human"
        consumed_at: "2026-07-05"
        consumed_by: null
        execution_status: executing
        execution_exit_code: null
        resolved: false
      - id: alert-z
        type: stall
        at: "2026-07-06"
        proposal:
          action: restart
          command: "python lab/infra/launch/fake_job.py restart --run-id run-bad-approval --workdir /tmp/run-bad-approval"
          workdir: "/tmp/run-bad-approval"
          radius: "fake/local only"
        approval_provenance: null
        consumed_at: null
        consumed_by: null
        execution_status: pending
        execution_exit_code: null
        resolved: false
"""


_FIXTURE_LEGACY_OK = """\
experiments:
  - id: run-legacy
    status: done
    governance_status: legacy_unverified
    governance_note: "pre-governance backfill by scripts/init-governance-data.py on 2026-07-16; original data predates G1 validators, not fabricated, pending human re-verification"
    commit: "b29d8833609e9ab7f67cd9da39435ac5cea04837"
    config: null
    data_split: null
    promote: no
"""

_FIXTURE_LEGACY_BAD = """\
experiments:
  - id: run-legacy-no-note
    status: done
    governance_status: legacy_unverified
    commit: "abc"
  - id: run-legacy-bad-value
    status: done
    governance_status: retroactive
    governance_note: "some note"
    commit: "abc"
  - id: run-new-strict
    status: done
    commit: "abc"
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

        def summary_errors(path: str) -> str:
            text = _FIXTURE_OK.replace(
                'run_summary: "lab/code/experiments/run-ok.md"',
                f'run_summary: "{path}"',
            )
            (root / LEDGER_REL).write_text(text, encoding="utf-8")
            found, _ = check_ledger(root)
            return "\n".join(found)

        # done summary 必须是允许目录内的 repo-relative、非 symlink regular file。
        absolute = root / "absolute-summary.md"
        absolute.write_text("# absolute\n", encoding="utf-8")
        expect("绝对路径" in summary_errors(str(absolute)), "拒绝 absolute run_summary")
        (root / "outside-summary.md").write_text("# traversal\n", encoding="utf-8")
        expect("traversal" in summary_errors("lab/code/experiments/../../../outside-summary.md"),
               "拒绝 traversal run_summary")
        (root / "lab/code/elsewhere").mkdir(parents=True)
        (root / "lab/code/elsewhere/run-ok.md").write_text("# wrong dir\n", encoding="utf-8")
        expect("必须位于" in summary_errors("lab/code/elsewhere/run-ok.md"),
               "拒绝允许目录外 run_summary")
        link = root / "lab/code/experiments/run-link.md"
        link.symlink_to(root / "lab/code/experiments/run-ok.md")
        expect("symlink" in summary_errors("lab/code/experiments/run-link.md"),
               "拒绝 symlink run_summary")
        directory = root / "lab/code/experiments/run-dir.md"
        directory.mkdir()
        expect("regular file" in summary_errors("lab/code/experiments/run-dir.md"),
               "拒绝 directory run_summary")

        # 非法 ledger：逐条命中
        (root / LEDGER_REL).write_text(_FIXTURE_BAD, encoding="utf-8")
        errors, _ = check_ledger(root)
        text = "\n".join(errors)
        expect("run-skip-approval" in text and "planned → running" in text, "拦截跳过 approved")
        expect("run-zombie" in text and "done → running" in text, "拦截 done 回转 running")
        expect("run-skip-approval" in text and "approved_by" in text, "缺批准记录报错")
        expect("run-missing-fields" in text and "commit" in text, "缺必填字段清单报错")
        expect("run-open-closure" in text and "run_summary 非法" in text, "闭环缺 summary 报错")
        expect("run-open-closure" in text and "artifact" in text, "闭环缺 artifact index 报错")
        expect("run-bad-approval" in text and "不一致" in text, "批 A 执 B 报错")
        expect("run-bad-approval" in text and "approved_at" in text, "批准记录不完整报错")
        expect("run-bad-approval" in text and "provenance verifier" in text, "伪造 provenance 报错")
        expect("run-bad-approval" in text and "consumed_at / consumed_by" in text, "半消费状态报错")
        expect("run-bad-approval" in text and "alert id 重复" in text, "重复 alert id 报错")

        # legacy 豁免（issue #63 D1）：显式标记 + 非占位 note 时跳过 history/approval/closure，
        # 但仍受基础结构与非 legacy 条目的严格判定约束。
        (root / LEDGER_REL).write_text(_FIXTURE_LEGACY_OK, encoding="utf-8")
        errors, _ = check_ledger(root)
        expect(errors == [], f"合法 legacy 条目应零 error（缺 config/data_split/status_history/闭环也放行），得到：{errors}")

        (root / LEDGER_REL).write_text(_FIXTURE_LEGACY_BAD, encoding="utf-8")
        errors, _ = check_ledger(root)
        text = "\n".join(errors)
        expect("run-legacy-no-note" in text and "governance_note" in text,
               "legacy 标记缺 governance_note 报错")
        expect("run-legacy-bad-value" in text and "governance_status 非法" in text,
               "governance_status 非法取值报错")
        expect("run-new-strict" in text and "status_history" in text,
               "无 legacy 标记的新条目仍严格判定（不因隔壁条目放松）")
        expect("run-legacy-no-note" in text and "status_history" in text,
               "缺 governance_note 的不完整豁免声明不换来豁免——仍须过正常严格检查")
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
