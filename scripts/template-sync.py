#!/usr/bin/env python3
"""下游追平：把上游 template 的框架层同步进本（下游）repo。

四站闭环的第④站，见 .agent/template-versioning-policy.md。本脚本**在下游 repo 内**运行。

分阶段事务流（issue #35 的 P0 correctness 合同）：

  preflight  读下游 .template.toml（origin + 当前 version）、上游 VERSION（目标 version）、
             上游 Git SHA（无 Git 时对全部上游文件算 source digest）；跨 MAJOR 且未 --allow-major
             时在任何写动作之前 STOP。
  plan       读上游 template-manifest.toml，逐个上游文件按 kind 生成动作计划
             （framework 覆盖 / generated 跳过稍后重建 / project 不碰 / scaffold 缺才建 /
             merge 只换哨兵块）。dry-run 与 apply 共用同一份 classify/plan parser。
  apply      按计划落地文件，并回读校验每处写入确实生效（manifest missing/unexpected）。
  verify     跑下游 scripts/sync-codex-adapters.py 重建 .codex/.agents 适配，再跑
             validate-governance.py 验收。任一步失败/超时 → **绝不推进版本**。
  commit     只有 apply + 生成器 + validator 全部成功后，才用「同目录临时文件 + 原子替换」
             把下游 .template.toml 的 version 推进到上游版本。

无论成败都写一份结构化 sync receipt：result 区分 pass / partial / fail / unknown，
绑定 exact upstream commit/digest、from/to version、expected/actual path manifest、
分类结果、逐阶段状态、失败阶段与可重跑命令。失败时版本保持旧值、精确列出已改路径，
不静默伪装成功；超时/中断记为 unknown，绝不显示为 pass。版本不前进 + 精确 partial
receipt + 可重跑，取代危险的自动 rollback。

`governance_data_gap`（issue #63 D1，新增字段，不改既有字段语义）：本次 sync 新创建
（下游此前不存在）的 `scripts/check-*.py` / `scripts/validate-*.py` 门禁 validator 清单 +
`scripts/init-governance-data.py --dry-run` 的诚实缺口计数（无新落地 validator 时为
`null`）。template-sync **只报告，不自动执行 init**——数据层初始化是显式、独立、可审计
的人工/agent 动作。

无第三方硬依赖（tomllib 读；.template.toml 手写）。退出码 0 = 成功（pass/partial），
非 0 = 失败或需人工介入（fail/unknown/MAJOR-STOP）。
用法：
  python scripts/template-sync.py --from /path/to/upstream/template-checkout
  python scripts/template-sync.py --from ... --allow-major     # 明确接受破坏性追平
  python scripts/template-sync.py --from ... --dry-run          # 只报告不落地、不推进版本
  python scripts/template-sync.py --from ... --receipt PATH      # 自定义 receipt 落盘路径
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

GOVERNANCE_VALIDATOR_GLOBS = ("scripts/check-*.py", "scripts/validate-*.py")

DOWNSTREAM = Path(__file__).resolve().parent.parent
SEMVER_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")
SENTINEL_BEGIN = "<!-- template:begin -->"
SENTINEL_END = "<!-- template:end -->"
RECEIPT_SCHEMA = "template-sync-receipt/v1"
DEFAULT_RECEIPT = DOWNSTREAM / ".template-sync-receipt.json"
STAGE_TIMEOUT_DEFAULT = 600


def parse_semver(raw: str) -> tuple[int, int, int]:
    m = SEMVER_RE.match(raw.strip())
    if not m:
        raise SystemExit(f"ERROR 非法 semver：{raw!r}")
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def cross_level(old: tuple[int, int, int], new: tuple[int, int, int]) -> str | None:
    if new < old:
        raise SystemExit(f"ERROR 上游版本 {new} 低于下游 {old}，拒绝降级")
    if new == old:
        return None
    if new[0] != old[0]:
        return "major"
    if new[1] != old[1]:
        return "minor"
    return "patch"


def match_glob(path: str, glob: str) -> bool:
    if glob.endswith("/**"):
        prefix = glob[:-3]
        return path == prefix or path.startswith(prefix + "/")
    return fnmatch.fnmatch(path, glob)


def classify(path: str, rules: list[dict]) -> str | None:
    for rule in rules:
        if match_glob(path, rule.get("glob", "")):
            return rule.get("kind")
    return None


def upstream_files(upstream: Path) -> list[str]:
    if (upstream / ".git").exists():
        out = subprocess.run(
            ["git", "ls-files"], cwd=upstream, capture_output=True, text=True, check=True
        ).stdout
        return [ln for ln in out.splitlines() if ln]
    # 无 git：rglob，排除常见产物目录。
    skip = {".git", ".venv", "__pycache__", ".ruff_cache", ".mypy_cache", ".pytest_cache"}
    files = []
    for p in upstream.rglob("*"):
        if p.is_file() and not any(part in skip for part in p.relative_to(upstream).parts):
            files.append(p.relative_to(upstream).as_posix())
    return files


def sentinel_block(text: str) -> str | None:
    i = text.find(SENTINEL_BEGIN)
    j = text.find(SENTINEL_END)
    if i == -1 or j == -1 or j < i:
        return None
    return text[i : j + len(SENTINEL_END)]


def source_identity(upstream: Path) -> dict:
    """上游 exact identity。**始终**记录对实际复制字节（working-tree bytes of the synced
    files）算出的 content_digest；有 Git 时**额外**记录 HEAD SHA 与 dirty 状态。

    这样 dirty source 的 receipt 不会只声称一个 clean SHA —— content_digest 反映真正被拷的
    字节，dirty=true 显式暴露 working tree 与 HEAD 的偏离。
    """
    h = hashlib.sha256()
    for rel in sorted(upstream_files(upstream)):
        h.update(rel.encode("utf-8"))
        h.update(b"\0")
        h.update((upstream / rel).read_bytes())
        h.update(b"\0")
    info = {"kind": "digest", "git_sha": None, "dirty": None,
            "content_digest": "sha256:" + h.hexdigest()}
    if (upstream / ".git").exists():
        try:
            sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=upstream,
                                 capture_output=True, text=True, timeout=20)
            status = subprocess.run(["git", "status", "--porcelain"], cwd=upstream,
                                    capture_output=True, text=True, timeout=20)
            if sha.returncode == 0 and sha.stdout.strip():
                info["kind"] = "git"
                info["git_sha"] = sha.stdout.strip()
                info["dirty"] = bool(status.stdout.strip()) if status.returncode == 0 else None
        except Exception:  # noqa: BLE001  best-effort：Git 信息缺失不影响 content_digest
            pass
    return info


def snapshot_tree(root: Path, exclude: set[str]) -> dict[str, str]:
    """下游整棵树的 path→content 快照（regular file 记 sha256，symlink 记 target）。

    排除 `.git/**`、version 控制的原子临时文件、以及 receipt 文件（exclude 里给出），
    使 apply/generator 前后的真实 changed-path 计算不被这些带外文件污染。
    """
    snap: dict[str, str] = {}
    for p in root.rglob("*"):
        parts = p.relative_to(root).parts
        if parts and parts[0] == ".git":
            continue
        rel = "/".join(parts)
        if rel in exclude:
            continue
        if p.name.startswith(".template.toml.") and p.name.endswith(".tmp"):
            continue
        if p.is_symlink():
            snap[rel] = "L:" + os.readlink(p)
        elif p.is_file():
            snap[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
    return snap


def diff_snap(before: dict[str, str], after: dict[str, str]) -> list[str]:
    keys = set(before) | set(after)
    return sorted(k for k in keys if before.get(k) != after.get(k))


# ── plan ────────────────────────────────────────────────────────────────────
@dataclass
class PlanItem:
    path: str
    kind: str | None
    action: str
    writes: bool


def plan_sync(upstream: Path, rules: list[dict]) -> list[PlanItem]:
    """纯计划：只读上下游，决定每条上游文件的动作，不写任何文件。dry-run/apply 共用。"""
    plan: list[PlanItem] = []
    for rel in upstream_files(upstream):
        kind = classify(rel, rules)
        src = upstream / rel
        dst = DOWNSTREAM / rel
        if kind is None:
            plan.append(PlanItem(rel, None, "unclassified", False))
            continue
        if kind == "project":
            plan.append(PlanItem(rel, kind, "skip-project", False))
            continue
        if kind == "generated":
            plan.append(PlanItem(rel, kind, "skip-generated", False))
            continue
        exists = dst.exists()
        if kind == "framework":
            if not exists:
                action = "create"
            elif dst.read_bytes() != src.read_bytes():
                action = "overwrite"
            else:
                action = "unchanged"
            plan.append(PlanItem(rel, kind, action, action in ("create", "overwrite")))
        elif kind == "scaffold":
            plan.append(
                PlanItem(rel, kind, "create" if not exists else "keep-scaffold", not exists)
            )
        elif kind == "merge":
            up_block = sentinel_block(src.read_text(encoding="utf-8", errors="replace"))
            if up_block is None:
                plan.append(PlanItem(rel, kind, "merge-warn-upstream", False))
            elif not exists:
                plan.append(PlanItem(rel, kind, "merge-create", True))
            else:
                down_block = sentinel_block(dst.read_text(encoding="utf-8", errors="replace"))
                if down_block is None:
                    plan.append(PlanItem(rel, kind, "merge-warn-downstream", False))
                elif down_block != up_block:
                    plan.append(PlanItem(rel, kind, "merge-update", True))
                else:
                    plan.append(PlanItem(rel, kind, "merge-unchanged", False))
        else:
            plan.append(PlanItem(rel, kind, "unclassified", False))
    return plan


# ── apply ───────────────────────────────────────────────────────────────────
@dataclass
class ApplyResult:
    written: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def apply_plan(plan: list[PlanItem], upstream: Path) -> ApplyResult:
    """按计划落地文件（非 dry-run 才调用）。逐条捕获 OSError，不让半途异常吞掉证据。"""
    res = ApplyResult()
    for item in plan:
        if not item.writes:
            continue
        src = upstream / item.path
        dst = DOWNSTREAM / item.path
        try:
            if item.action == "merge-update":
                down_text = dst.read_text(encoding="utf-8", errors="replace")
                up_block = sentinel_block(src.read_text(encoding="utf-8", errors="replace"))
                down_block = sentinel_block(down_text)
                # 只替换定位到的那一块（count=1），避免子串在文件他处重复时误伤。
                dst.write_text(down_text.replace(down_block, up_block, 1), encoding="utf-8")
            else:
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_bytes(src.read_bytes())
            res.written.append(item.path)
        except OSError as e:
            res.errors.append(f"{item.path}: {e}")
    return res


def build_manifest(plan: list[PlanItem], applied: ApplyResult, upstream: Path,
                   apply_changed: list[str], generated_outputs: list[str],
                   excluded: list[str], after_gen: dict[str, str],
                   rules: list[dict]) -> dict:
    """基于**真实**磁盘快照的 manifest。

    - expected：plan 里 writes=True 的路径（我们打算改的）。
    - apply_changed / generated_outputs：apply 前后、generator 前后由 snapshot 算出的真实
      changed path（后者单列，代表生成器产物 delta，不被吞掉、也不直接等同 actual）。
    - missing：expected 里内容没真正落地的（回读内容校验 + 磁盘未变化的双重判据）。
    - unexpected：apply 阶段真实变化但不在 expected 里的带外改动。
    - excluded：快照显式排除的带外类别（.git、临时文件、receipt/version 控制文件）。
    - after_gen / rules：generator 完成后的完整下游快照 + 上游 classify 规则，用于按同一
      generated classification 对**全量**磁盘状态重新分类（而非只看本次 generator delta），
      见下方 generated.actual。
    """
    planned = [p.path for p in plan if p.writes]
    planned_set = set(planned)
    changed_set = set(apply_changed)
    missing: list[str] = []
    for item in plan:
        if not item.writes:
            continue
        dst = DOWNSTREAM / item.path
        src = upstream / item.path
        landed = True
        if item.path not in applied.written or not dst.exists():
            landed = False
        elif item.action == "merge-update":
            up_block = sentinel_block(src.read_text(encoding="utf-8", errors="replace"))
            if up_block is None or up_block not in dst.read_text(encoding="utf-8", errors="replace"):
                landed = False
        elif dst.read_bytes() != src.read_bytes():
            landed = False
        # 磁盘快照必须也见证到这条计划写入真的改变了下游。
        if not landed or item.path not in changed_set:
            missing.append(item.path)
    unexpected = sorted(p for p in apply_changed if p not in planned_set)

    # generated exact manifest：canonical expected set = 同一 plan 中 kind=generated 的上游路径
    # （单一真源，不新增清单）。actual 是对 post-generator **完整**下游快照应用同一
    # classify()/generated glob rules 得到的全量集合——不是本次 generator 改动的 delta，
    # 因此运行前已存在、本次未变化的 rogue/stale generated 文件也会出现在 actual 里。
    gen_expected = [p.path for p in plan if p.kind == "generated"]
    gen_expected_set = set(gen_expected)
    gen_actual = sorted(p for p in after_gen if classify(p, rules) == "generated")
    gen_actual_set = set(gen_actual)
    # missing 是纯路径集合语义：expected - actual（路径根本不在 post-generator 全量集合里）。
    # 内容正确性单独归入 content_mismatches，不混进 missing。
    gen_missing = sorted(gp for gp in gen_expected if gp not in gen_actual_set)
    gen_content_mismatches: list[str] = []
    for gp in gen_expected:
        if gp not in gen_actual_set:
            continue  # 路径本身缺失已计入 missing，内容判定只看 expected ∩ actual。
        dstg = DOWNSTREAM / gp
        srcg = upstream / gp
        if srcg.exists() and dstg.read_bytes() != srcg.read_bytes():
            gen_content_mismatches.append(gp)
    gen_unexpected = sorted(p for p in gen_actual if p not in gen_expected_set)
    return {
        "expected": planned,
        "apply_changed": apply_changed,
        "generated_outputs": generated_outputs,
        "missing": sorted(set(missing)),
        "unexpected": unexpected,
        "excluded": excluded,
        "generated": {
            "expected": gen_expected,
            "actual": gen_actual,
            "actual_changed": generated_outputs,
            "missing": gen_missing,
            "unexpected": gen_unexpected,
            "content_mismatches": sorted(set(gen_content_mismatches)),
        },
    }


def newly_landed_validators(plan: list[PlanItem]) -> list[str]:
    """本次 sync 新创建（下游此前不存在）的门禁 validator 脚本（issue #63 D1）。

    template-sync 只落地 validator 本身，不迁移它要求的数据层——追平后下游可能从全绿
    掉到大面积 FAIL。receipt 必须报告这个语义缺口，不能静默（见 issue #63 复现记录）。
    """
    out = []
    for pi in plan:
        if pi.kind != "framework" or pi.action != "create":
            continue
        if any(match_glob(pi.path, g) for g in GOVERNANCE_VALIDATOR_GLOBS):
            out.append(pi.path)
    return sorted(out)


def governance_data_gap_report(downstream: Path) -> dict | None:
    """跑 scripts/init-governance-data.py --dry-run 得到的诚实缺口计数（不落盘，纯预览）。

    只在 apply 已把 init-governance-data.py 落到下游磁盘后调用才有意义（dry-run sync
    模式下文件还没落地，调用方需跳过）。init-governance-data.py 不存在（上游尚未发布
    这个版本）时返回 None，不是 error。
    """
    init_script = downstream / "scripts" / "init-governance-data.py"
    if not init_script.is_file():
        return None
    try:
        spec = importlib.util.spec_from_file_location("_ts_init_governance_data", init_script)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        counts = mod.run(downstream, dry_run=True)
    except Exception as e:  # noqa: BLE001  best-effort：gap 预览失败不影响 sync 本身结果
        return {"error": str(e)}
    return {
        "changed": len(counts.changed),
        "skipped": len(counts.skipped),
        "flagged": len(counts.flagged),
        "changed_keys": [k for k, _m in counts.changed],
        "flagged_keys": [k for k, _m in counts.flagged],
    }


def classification_summary(plan: list[PlanItem]) -> dict:
    out: dict[str, list[str]] = {
        "framework": [], "generated": [], "project": [], "scaffold": [], "merge": [],
        "unclassified": [],
    }
    for p in plan:
        key = p.kind if p.kind in out else "unclassified"
        out[key].append(p.path)
    return {k: sorted(v) for k, v in out.items()}


# ── atomic version write ─────────────────────────────────────────────────────
def render_template_toml(origin: str, version: str, extra: dict) -> str:
    # 用 json.dumps 生成带正确转义的 TOML basic string（引号/反斜杠安全）。
    lines = ["[template]", f"origin = {json.dumps(origin, ensure_ascii=False)}",
             f"version = {json.dumps(version, ensure_ascii=False)}"]
    for k, v in extra.items():
        if k in ("origin", "version"):
            continue
        lines.append(f"{k} = {json.dumps(str(v), ensure_ascii=False)}")
    return "\n".join(lines) + "\n"


def atomic_write_text(path: Path, text: str) -> None:
    """同目录唯一临时文件（mkstemp）+ fsync + os.replace 原子替换 + parent dir fsync。

    - 用 tempfile.mkstemp 生成唯一名，绝不与并发写者的临时文件撞名。
    - replace 之前中断/抛错 → 只影响本次自己的 tmp，finally 只删本次的 tmp，
      不会误删他人临时文件；目标文件字节始终未动（不会半行/不可解析）。
    - replace 成功后 fsync 父目录，确保重命名本身落盘。
    """
    path = Path(path)
    directory = path.parent
    fd, tmpname = tempfile.mkstemp(dir=directory, prefix=path.name + ".", suffix=".tmp")
    tmp: Path | None = Path(tmpname)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
        tmp = None  # 已重命名到目标，不再是「我们的临时文件」
        try:
            dfd = os.open(directory, os.O_RDONLY)
            try:
                os.fsync(dfd)
            finally:
                os.close(dfd)
        except OSError:
            pass  # 目录 fsync 失败不致命（replace 已完成）
    finally:
        if tmp is not None and tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


def write_template_version(origin: str, version: str, extra: dict, target: Path | None = None) -> None:
    atomic_write_text(target or (DOWNSTREAM / ".template.toml"),
                      render_template_toml(origin, version, extra))


def read_template_toml() -> dict:
    f = DOWNSTREAM / ".template.toml"
    if not f.exists():
        raise SystemExit(
            "ERROR 缺少 .template.toml —— 这看起来不是本模板的下游 repo。"
            "首次采用请走 adopt-existing-repo。"
        )
    return tomllib.loads(f.read_text(encoding="utf-8")).get("template", {})


# ── external stages ──────────────────────────────────────────────────────────
def run_stage(argv: list[str], cwd: Path, timeout: int) -> tuple[str, str]:
    """跑外部阶段脚本。返回 (status, detail)：ok / fail / timeout / interrupt / error。

    timeout/interrupt/error 表示无法判定结果（不能判成功也不能判失败）→ 上层记 unknown。
    KeyboardInterrupt 在此 stage boundary 捕获，绝不让中断被误当成成功继续到 commit。
    """
    try:
        proc = subprocess.run(argv, cwd=cwd, timeout=timeout)
    except subprocess.TimeoutExpired:
        return "timeout", f"超过 {timeout}s 未返回"
    except KeyboardInterrupt:
        return "interrupt", "被中断 (KeyboardInterrupt)"
    except Exception as e:  # noqa: BLE001
        return "error", str(e)
    return ("ok" if proc.returncode == 0 else "fail"), f"exit {proc.returncode}"


def closed_downstream_issues(origin: str) -> None:
    try:
        out = subprocess.run(
            ["gh", "issue", "list", "--repo", origin, "--label", "from-downstream",
             "--state", "closed", "--limit", "20", "--json", "number,title"],
            capture_output=True, text=True, timeout=20,
        )
        if out.returncode != 0 or not out.stdout.strip():
            return
        issues = json.loads(out.stdout)
        if issues:
            print("\n闭环回执 —— 上游已关闭的 from-downstream issue（核对你上报的是否已随本次追平进来）：")
            for it in issues[:20]:
                print(f"  #{it['number']} {it['title']}")
    except Exception:  # noqa: BLE001  best-effort，无 gh/网络就静默
        return


# ── receipt ──────────────────────────────────────────────────────────────────
def receipt_path(args: argparse.Namespace) -> Path | None:
    if args.receipt:
        return Path(args.receipt)
    if args.dry_run:
        return None  # dry-run 默认不落地 receipt 文件（无副作用），只打印
    return DEFAULT_RECEIPT


def snapshot_exclusions(args: argparse.Namespace) -> set[str]:
    """快照要显式排除的下游相对路径（receipt 文件 + version 控制文件），避免带外文件
    污染真实 changed-path。`.git` 与原子临时文件由 snapshot_tree 本身排除。"""
    ex: set[str] = {".template.toml"}  # 版本控制文件由 commit 阶段单独原子写
    rp = receipt_path(args)
    if rp is not None:
        try:
            ex.add(rp.resolve().relative_to(DOWNSTREAM).as_posix())
        except ValueError:
            pass  # receipt 落在下游之外，无需排除
    return ex


def emit_receipt(receipt: dict, args: argparse.Namespace) -> None:
    path = receipt_path(args)
    text = json.dumps(receipt, ensure_ascii=False, indent=2) + "\n"
    if path is not None:
        atomic_write_text(path, text)
        print(f"\n[receipt] result={receipt['result']} → {path}")
    else:
        print("\n[receipt] (dry-run，未落盘)\n" + text)


def rerun_command(args: argparse.Namespace) -> str:
    parts = ["python scripts/template-sync.py", f"--from {args.upstream}"]
    if args.allow_major:
        parts.append("--allow-major")
    if args.no_verify:
        parts.append("--no-verify")
    if args.receipt:
        parts.append(f"--receipt {args.receipt}")
    return " ".join(parts)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--from", dest="upstream", required=True,
                   help="上游 template 的本地 checkout 路径")
    p.add_argument("--allow-major", action="store_true", help="接受 MAJOR 破坏性追平")
    p.add_argument("--dry-run", action="store_true", help="只报告不落地、不推进版本")
    p.add_argument("--no-verify", action="store_true",
                   help="跳过 validate-governance（保留 CLI 兼容；但按合同**绝不推进版本**："
                        "receipt=partial、commit_version=skipped、进程非零、旧版本保持）")
    p.add_argument("--receipt", default=None,
                   help="sync receipt 落盘路径（默认 .template-sync-receipt.json；dry-run 默认只打印）")
    p.add_argument("--timeout", type=int, default=STAGE_TIMEOUT_DEFAULT,
                   help="生成器 / validator 每步超时秒数（默认 600）")
    args = p.parse_args()

    upstream = Path(args.upstream).resolve()
    if not upstream.is_dir():
        raise SystemExit(f"ERROR 上游路径不存在：{upstream}")
    if upstream == DOWNSTREAM:
        raise SystemExit("ERROR --from 指向了当前 repo 自身")

    # ── preflight ────────────────────────────────────────────────────────────
    meta = read_template_toml()
    origin = meta.get("origin", "")
    cur_raw = meta.get("version", "v0.0.0")
    up_version_f = upstream / "VERSION"
    if not up_version_f.exists():
        raise SystemExit("ERROR 上游缺少 VERSION 文件")
    up_raw = up_version_f.read_text(encoding="utf-8").strip()

    old, new = parse_semver(cur_raw), parse_semver(up_raw)
    level = cross_level(old, new)
    print(f"[template-sync] 下游 {cur_raw} → 上游 {up_raw}"
          + (f"（跨 {level.upper()}）" if level else "（版本相同，仍会对齐文件）"))
    if level == "major" and not args.allow_major:
        # MAJOR STOP 发生在任何写动作之前（含 receipt 落盘），保证严格 no-op。
        print(
            "\nSTOP：这是 MAJOR 追平，定义上需人工 reconcile（见 template-versioning-policy）。\n"
            "先读上游 CHANGELOG.md，确认破坏性变更点，再加 --allow-major 重跑。"
        )
        return 2

    manifest_f = upstream / "template-manifest.toml"
    if not manifest_f.exists():
        raise SystemExit("ERROR 上游缺少 template-manifest.toml")
    rules = tomllib.loads(manifest_f.read_text(encoding="utf-8")).get("rule", [])

    src_id = source_identity(upstream)

    # ── plan ───────────────────────────────────────────────────────────────
    plan = plan_sync(upstream, rules)
    warn_merge = [pi.path for pi in plan if pi.action in ("merge-warn-upstream", "merge-warn-downstream")]
    warn_unclassified = [pi.path for pi in plan if pi.action == "unclassified"]
    n_overwrite = sum(1 for pi in plan if pi.action == "overwrite")
    n_create = sum(1 for pi in plan if pi.action in ("create", "merge-create"))
    n_merge = sum(1 for pi in plan if pi.action == "merge-update")
    n_project = sum(1 for pi in plan if pi.action == "skip-project")
    n_scaffold_kept = sum(1 for pi in plan if pi.action == "keep-scaffold")

    print(f"\n计划：覆盖(framework) {n_overwrite} · 新建 {n_create} · merge 换块 {n_merge}"
          f" · 保护(project) {n_project} · scaffold 保留 {n_scaffold_kept}")
    for pi in plan:
        if pi.action in ("overwrite", "merge-update"):
            print(f"  ~ {pi.path}")
        elif pi.action in ("create", "merge-create"):
            print(f"  + {pi.path}")
    for w in warn_merge:
        print(f"  WARN merge: {w}（哨兵块缺失，跳过；需人工 reconcile）")
    for u in warn_unclassified:
        print(f"  WARN 未分类(补 template-manifest.toml): {u}")

    receipt: dict = {
        "schema": RECEIPT_SCHEMA,
        "result": "unknown",
        "dry_run": bool(args.dry_run),
        "from_version": cur_raw,
        "target_version": up_raw,
        "committed_version": cur_raw,
        "version_advanced": False,
        "level": level,
        "origin": origin,
        "source": {"path": str(upstream), **src_id},
        "classification": classification_summary(plan),
        "stages": {
            "preflight": "ok", "plan": "ok", "apply": "pending",
            "generated_rebuild": "skipped", "validate": "skipped", "commit_version": "skipped",
        },
        "manifest": {"expected": [pi.path for pi in plan if pi.writes],
                     "apply_changed": [], "generated_outputs": [],
                     "missing": [], "unexpected": [], "excluded": [],
                     "generated": {"expected": [pi.path for pi in plan if pi.kind == "generated"],
                                   "actual": [], "actual_changed": [], "missing": [],
                                   "unexpected": [], "content_mismatches": []}},
        "warnings": ([f"merge:{w}" for w in warn_merge]
                     + [f"unclassified:{w}" for w in warn_unclassified]),
        "failure": None,
        "governance_data_gap": None,
    }

    # ── dry-run 早退：不写任何文件、不推进版本、不验证 ──────────────────────
    if args.dry_run:
        receipt["stages"]["apply"] = "planned"
        receipt["result"] = "dry-run"
        new_validators = newly_landed_validators(plan)
        if new_validators:
            receipt["governance_data_gap"] = {
                "new_validators": new_validators,
                "gap": None,  # dry-run 未 apply，文件还没落地，无法预览缺口
                "suggested_command": "python scripts/init-governance-data.py",
                "note": "dry-run 未落地文件，数据层 gap 需在真实 sync 后用"
                        "`python scripts/init-governance-data.py --dry-run` 预览",
            }
            print(f"\n提醒：本次 sync 会新落地门禁 validator：{new_validators}；"
                  "真实 sync 后建议跑 python scripts/init-governance-data.py --dry-run 预览数据层缺口。")
        print("\n[dry-run] 未落地任何文件、未推进版本、未验证。")
        emit_receipt(receipt, args)
        return 0

    # ── apply（先给下游拍前快照，用于基于真实磁盘的 changed-path 证据）──────
    excluded = snapshot_exclusions(args)
    before_apply = snapshot_tree(DOWNSTREAM, excluded)
    applied = apply_plan(plan, upstream)
    after_apply = snapshot_tree(DOWNSTREAM, excluded)

    # ── verify：生成器（其产物计入真实 changed-path，单列 generated_outputs）──
    print("\n=== 重建 Codex 适配 ===", flush=True)
    try:
        gen_status, gen_detail = run_stage(
            [sys.executable, str(DOWNSTREAM / "scripts" / "sync-codex-adapters.py")], DOWNSTREAM, args.timeout)
    except KeyboardInterrupt:
        gen_status, gen_detail = "interrupt", "被中断 (KeyboardInterrupt)"
    receipt["stages"]["generated_rebuild"] = gen_status
    if gen_status != "ok":
        print(f"ERROR Codex 适配重建 {gen_status}（{gen_detail}）：.codex/.agents 可能 stale，"
              "本次不推进版本。")
    after_gen = snapshot_tree(DOWNSTREAM, excluded)

    # ── 新落地门禁 validator + 数据层 gap 报告（issue #63 D1：不再静默，不自动执行 init）──
    new_validators = newly_landed_validators(plan)
    if new_validators:
        gap = governance_data_gap_report(DOWNSTREAM)
        receipt["governance_data_gap"] = {
            "new_validators": new_validators,
            "gap": gap,
            "suggested_command": "python scripts/init-governance-data.py",
        }
        if gap and not gap.get("error") and gap.get("changed"):
            print(
                f"\n提醒：本次 sync 新落地门禁 validator {new_validators}；"
                f"数据层检测到 {gap['changed']} 处缺口（结构骨架未初始化，不自动修复）。"
                "建议执行：python scripts/init-governance-data.py"
            )
        elif gap and gap.get("error"):
            print(f"\nWARN 数据层 gap 检测本身失败（不影响本次 sync 结果）：{gap['error']}")

    apply_changed = diff_snap(before_apply, after_apply)
    generated_outputs = diff_snap(after_apply, after_gen)
    manifest = build_manifest(plan, applied, upstream, apply_changed, generated_outputs,
                              sorted(excluded), after_gen, rules)
    receipt["manifest"] = manifest
    apply_ok = not applied.errors and not manifest["missing"] and not manifest["unexpected"]
    receipt["stages"]["apply"] = "ok" if apply_ok else "fail"
    print(f"\n真实变更：apply={apply_changed} · generator={generated_outputs}"
          + (f"；未生效 {manifest['missing']}" if manifest["missing"] else "")
          + (f"；计划外 {manifest['unexpected']}" if manifest["unexpected"] else ""))

    # ── validator（--no-verify 保留 CLI 兼容，但按合同不推进版本）──────────
    if args.no_verify:
        val_status, val_detail = "skipped", "--no-verify"
        print("\n[--no-verify] 跳过 validate-governance —— 按合同版本不会推进")
    else:
        print("\n=== validate-governance（追平后验收）===", flush=True)
        try:
            val_status, val_detail = run_stage(
                [sys.executable, str(DOWNSTREAM / "scripts" / "validate-governance.py")], DOWNSTREAM, args.timeout)
        except KeyboardInterrupt:
            val_status, val_detail = "interrupt", "被中断 (KeyboardInterrupt)"
    receipt["stages"]["validate"] = val_status

    gen_manifest = manifest["generated"]
    generated_ok = (not gen_manifest["missing"] and not gen_manifest["unexpected"]
                    and not gen_manifest["content_mismatches"])
    indeterminate = (gen_status in ("timeout", "error", "interrupt")
                     or val_status in ("timeout", "error", "interrupt"))
    # 版本推进的唯一条件：apply 干净 + 生成器成功 + generated exact manifest 干净 +
    # validator **真的通过**（skipped 不算）。
    version_ok = apply_ok and gen_status == "ok" and generated_ok and val_status == "ok"

    # ── failure paths：绝不推进版本 ────────────────────────────────────────
    if not version_ok:
        if indeterminate:
            receipt["result"] = "unknown"
            if gen_status in ("timeout", "error", "interrupt"):
                stage, detail = "generated_rebuild", gen_detail
            else:
                stage, detail = "validate", val_detail
        else:
            # 干净失败/跳过验收：已改过文件 → partial（半同步态，可重跑恢复）；否则 fail。
            receipt["result"] = "partial" if applied.written else "fail"
            if not apply_ok:
                stage = "apply"
                detail = "; ".join(applied.errors
                                   + [f"missing:{m}" for m in manifest["missing"]]
                                   + [f"unexpected:{u}" for u in manifest["unexpected"]])
            elif gen_status == "fail":
                stage, detail = "generated_rebuild", gen_detail
            elif not generated_ok:
                stage = "generated_rebuild"
                detail = "; ".join([f"gen-missing:{m}" for m in gen_manifest["missing"]]
                                   + [f"gen-unexpected:{u}" for u in gen_manifest["unexpected"]]
                                   + [f"gen-content-mismatch:{c}"
                                      for c in gen_manifest["content_mismatches"]])
            elif val_status == "skipped":
                stage, detail = "validate", "--no-verify：跳过验收，按合同不推进版本"
            else:
                stage, detail = "validate", val_detail
        receipt["failure"] = {
            "stage": stage, "detail": detail,
            "version_kept": cur_raw,
            "touched_paths": list(applied.written),
            "rerun_command": rerun_command(args),
        }
        emit_receipt(receipt, args)
        print(f"\n[template-sync] {receipt['result'].upper()} — 版本保持 {cur_raw}，"
              f"失败阶段 {stage}（{detail}）。修复后重跑：{receipt['failure']['rerun_command']}")
        return 1

    # ── commit-version：原子推进（仅在全部成功后）────────────────────────
    try:
        write_template_version(origin, up_raw, meta)
    except KeyboardInterrupt:
        # 原子替换要么发生要么没发生：重新读盘取**事实**版本，绝不硬写 version_kept=old，
        # 也不做危险 rollback。若 replace 已发生就诚实报告「中断下已推进」。
        actual = read_template_toml().get("version", cur_raw)
        advanced = actual != cur_raw
        receipt["stages"]["commit_version"] = "interrupt"
        receipt["result"] = "unknown"
        receipt["committed_version"] = actual
        receipt["version_advanced"] = advanced
        receipt["failure"] = {
            "stage": "commit_version",
            "detail": (f"replace 已发生：版本在中断下已推进到 {actual}（非 rollback）"
                       if advanced else "replace 前中断：版本未变"),
            "actual_version": actual,
            "version_kept": None if advanced else cur_raw,
            "touched_paths": list(applied.written),
            "rerun_command": rerun_command(args),
        }
        emit_receipt(receipt, args)
        print(f"\n[template-sync] UNKNOWN — 版本写入被中断；.template.toml 现为 {actual}"
              + ("（中断下已推进，非 rollback）" if advanced else "（保持旧值）") + "。")
        return 1
    except OSError as e:
        receipt["stages"]["commit_version"] = "fail"
        receipt["result"] = "partial" if applied.written else "fail"
        receipt["failure"] = {
            "stage": "commit_version", "detail": str(e),
            "version_kept": cur_raw,
            "touched_paths": list(applied.written),
            "rerun_command": rerun_command(args),
        }
        emit_receipt(receipt, args)
        print(f"\n[template-sync] 版本原子写入失败（{e}）：.template.toml 仍是 {cur_raw}。")
        return 1

    receipt["stages"]["commit_version"] = "ok"
    receipt["committed_version"] = up_raw
    receipt["version_advanced"] = up_raw != cur_raw
    print(f"\n[template-sync] .template.toml version → {up_raw}（mkstemp + 原子替换 + parent fsync）")

    receipt["result"] = "pass" if not receipt["warnings"] else "partial"
    emit_receipt(receipt, args)
    if origin:
        closed_downstream_issues(origin)

    if warn_unclassified:
        print("\n提醒：有未分类文件，请在上游 template-manifest.toml 补规则后再发下一版。")
    print(f"\n[template-sync] {receipt['result'].upper()}"
          + ("" if receipt["result"] == "pass" else "（有 warning，见 receipt）"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
