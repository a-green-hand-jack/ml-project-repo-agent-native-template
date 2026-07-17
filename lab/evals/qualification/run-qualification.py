#!/usr/bin/env python3
"""A 层可重复 qualification runner（issue #54 / #59，D1-D3）。

对 G1（9 项静态门禁 validator）与 G6（4 项 Codex adapter parity 承诺）逐 T-ID 跑
「正例 + 负例」：正例 = 在 `git clone` 物化的干净 fixture 上跑 validator，期望全绿；
负例 = 同类隔离 fixture 内注入表格指定的一处违规，期望非零退出且报错文本可定位到
注入点。fixture 用后即弃，绝不在真实 repo/worktree 内注入、绝不 copytree 任何
worktree（P3 事故教训见 `.agent/action-boundary.md`）。

fixture 用 `git clone --no-hardlinks` 而非纯 `git archive`：多个 validator（
`check-agent-harness.py`→`sync-codex-adapters.py --context source`、
`validate-governance.py` 的 tracked-bytes/merge-sentinel 检查）内部依赖
`git ls-files`，纯 tar 物化没有 `.git` 会让这些子检查静默降级或报错，clone 能保留
真实 git 历史与正确的被测 commit sha，两者都是 `.agent/action-boundary.md` 明文允许
的 fixture 手段。

复用优先（#52 A 层明文）：validator 已有 `--self-test` 覆盖该负例语义的（G1 的 5 项：
T-G1-2/3/6/7/8），runner 只调用 self-test 并把其结果登记为该 T-ID 证据，不重复造
fixture；只为 self-test 未覆盖的注入点（G1 的 4 项 T-G1-1/4/5/9 + 全部 G6）新建注入
逻辑。

输出双形态落 `lab/docs/audits/qualification/report-<group>.{json,md}`，含被测 commit
sha；`generated_at` 之外的字段在同一 commit 上重跑应逐字节一致（D2 可重复性合同）。

runner 本身是评测工具，不是新门禁，不挂进 `validate-governance.py`。

用法：python lab/evals/qualification/run-qualification.py --group {g1,g6,all}
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
# 本机裸 python3 缺 PyYAML，validate-governance.py 等门禁在 --strict 下会把「跳过 YAML 深度
# 解析」warning 计成 FAIL（非本 runner 引入的 bug，是既有环境缺口，见 scripts/CLAUDE.md 与
# memory/current-status.md 的既有 workaround）；统一用 `uv run --with pyyaml` 调用子进程校验脚本。
PY_CMD = ["uv", "run", "--with", "pyyaml", "python3"]
OUT_DIR = REPO / "lab" / "docs" / "audits" / "qualification"


# --------------------------------------------------------------------- fixtures


def commit_sha() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True, check=True
    ).stdout.strip()


def worktree_dirty() -> bool:
    out = subprocess.run(
        ["git", "status", "--porcelain"], cwd=REPO, capture_output=True, text=True, check=True
    ).stdout
    return bool(out.strip())


@contextmanager
def fixture(label: str):
    """git clone HEAD 到 /tmp throwaway 目录；退出时无条件删除。"""
    dest = Path(tempfile.mkdtemp(prefix=f"qual-{label}-"))
    dest.rmdir()
    subprocess.run(
        ["git", "clone", "--quiet", "--no-hardlinks", str(REPO), str(dest)],
        cwd=REPO, check=True, capture_output=True, text=True,
    )
    try:
        yield dest
    finally:
        shutil.rmtree(dest, ignore_errors=True)


def run_script(fx: Path, rel_script: str, args: list[str], timeout: int = 180) -> subprocess.CompletedProcess:
    return subprocess.run(
        [*PY_CMD, str(fx / rel_script), *args], cwd=fx, capture_output=True, text=True, timeout=timeout,
    )


def tail(text: str, n: int = 20) -> str:
    lines = text.strip("\n").splitlines()
    return "\n".join(lines[-n:])


def dir_digest(root: Path, rel_dirs: list[str]) -> str:
    """确定性内容摘要：排序遍历给定相对目录下所有文件，累加 path+bytes 的 sha256。"""
    h = hashlib.sha256()
    for rel in sorted(rel_dirs):
        base = root / rel
        if not base.is_dir():
            continue
        for p in sorted(base.rglob("*")):
            if p.is_file():
                h.update(p.relative_to(root).as_posix().encode("utf-8"))
                h.update(p.read_bytes())
    return h.hexdigest()


# --------------------------------------------------------------------- result shape


def mk_outcome(proc: subprocess.CompletedProcess, ok: bool, extra: dict | None = None) -> dict:
    out = {
        "exit_code": proc.returncode,
        "ok": ok,
        "evidence": tail(proc.stdout + proc.stderr),
    }
    if extra:
        out.update(extra)
    return out


def make_result(tid: str, group: str, validator: str, mode: str, positive: dict,
                 negative: dict | None, notes: str, reused_self_test: bool = False) -> dict:
    ok = positive["ok"] and (negative is None or negative["ok"])
    return {
        "id": tid,
        "group": group,
        "validator": validator,
        "mode": mode,
        "reused_self_test": reused_self_test,
        "positive": positive,
        "negative": negative,
        "status": "PASS" if ok else "FAIL",
        "notes": notes,
    }


# --------------------------------------------------------------------- self-test reuse (G1)


def check_self_test(tid: str, group: str, script_rel: str, notes: str) -> dict:
    validator = f"scripts/{script_rel}"
    with fixture(tid.lower()) as fx:
        proc = run_script(fx, validator, ["--self-test"])
        out = proc.stdout + proc.stderr
        # 这几个脚本的 self-test 只在断言失败时才打印该条用例，正常通过时静默——
        # exit 0 且输出里不出现 "FAIL " 前缀即代表内嵌正/负 fixture 全部符合预期。
        no_visible_fail = "FAIL " not in out and "\nFAIL\n" not in out
        ok = proc.returncode == 0 and no_visible_fail
        positive = mk_outcome(proc, ok)
    return make_result(tid, group, validator, "self-test-reuse", positive, None, notes,
                        reused_self_test=True)


# --------------------------------------------------------------------- G1 custom fixtures


def t_g1_1() -> dict:
    tid, group, validator = "T-G1-1", "g1", "scripts/validate-governance.py"
    with fixture("g1-1-pos") as fx:
        proc = run_script(fx, validator, ["--strict"])
        positive = mk_outcome(proc, proc.returncode == 0)
    with fixture("g1-1-neg") as fx:
        gi = fx / ".gitignore"
        before = gi.read_text(encoding="utf-8")
        mutated = "\n".join(ln for ln in before.splitlines() if "lab/data" not in ln) + "\n"
        assert mutated != before, "注入无效：mutated == before"
        gi.write_text(mutated, encoding="utf-8")
        proc = run_script(fx, validator, ["--strict"])
        out = proc.stdout + proc.stderr
        located = ".gitignore 未提及受保护路径：lab/data" in out
        negative = mk_outcome(proc, proc.returncode != 0 and located,
                               {"injection": "删除 .gitignore 中全部含 lab/data 的行"})
    return make_result(
        tid, group, validator, "custom-fixture", positive, negative,
        "负例注入 check_gitignore()：.gitignore 不再提及 lab/data 保护 token，"
        "触发子门（本文件自身治理规则，非 subcheck 子进程）。",
    )


def t_g1_4() -> dict:
    tid, group, validator = "T-G1-4", "g1", "scripts/check-same-commit.py"
    with fixture("g1-4-pos") as fx:
        probe = fx / "scripts" / "_qualification_probe.py"
        probe.write_text("# throwaway qualification probe\n", encoding="utf-8")
        anatomy = fx / "scripts" / "ANATOMY.md"
        anatomy.write_text(anatomy.read_text(encoding="utf-8") + "\n<!-- qualification probe -->\n",
                            encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=fx, check=True, capture_output=True)
        proc = run_script(fx, validator, ["--staged"])
        positive = mk_outcome(proc, proc.returncode == 0,
                               {"injection": "同 staged 集新增 scripts/_qualification_probe.py 并更新 scripts/ANATOMY.md（合规改动）"})
    with fixture("g1-4-neg") as fx:
        probe = fx / "scripts" / "_qualification_probe.py"
        probe.write_text("# throwaway qualification probe\n", encoding="utf-8")
        subprocess.run(["git", "add", "scripts/_qualification_probe.py"], cwd=fx, check=True, capture_output=True)
        proc = run_script(fx, validator, ["--staged"])
        out = proc.stdout + proc.stderr
        located = "scripts/ANATOMY.md" in out and "结构改动未同步更新对应 ANATOMY.md" in out
        negative = mk_outcome(proc, proc.returncode != 0 and located,
                               {"injection": "只 staged scripts/_qualification_probe.py（A），不更新 scripts/ANATOMY.md"})
    return make_result(
        tid, group, validator, "custom-fixture", positive, negative,
        "fixture 用 git clone（需要真实 git 历史支持 --staged diff）；正例证明合规改动放行，"
        "负例证明结构改动未同步更新 anatomy 会被拦。",
    )


def t_g1_5() -> dict:
    tid, group, validator = "T-G1-5", "g1", "scripts/check-agent-harness.py"
    with fixture("g1-5-pos") as fx:
        # 模拟下游用默认路径跑过一次 template-sync.py --commit 后的根目录状态（issue #75
        # 缺口②回归）：receipt 文件必须在 ROOT_WHITELIST 里，不能被误判为根污染。
        (fx / ".template-sync-receipt.json").write_text(
            json.dumps({"schema": "template-sync-receipt/v1", "result": "pass"}) + "\n",
            encoding="utf-8",
        )
        proc = run_script(fx, validator, ["--strict"])
        out = proc.stdout + proc.stderr
        no_receipt_pollution_warning = ".template-sync-receipt.json" not in out
        positive = mk_outcome(proc, proc.returncode == 0 and no_receipt_pollution_warning,
                               {"injection": "根目录放一份 .template-sync-receipt.json（默认 sync 落盘路径），"
                                             "期望 --strict 仍 OK 且不告警该文件"})
    with fixture("g1-5-neg") as fx:
        target = fx / ".claude" / "hooks" / "subagent_report_index.py"
        assert target.exists(), "预期 hook 脚本不存在，fixture 与预期不符"
        target.unlink()
        # 顺带证明 ROOT_WHITELIST 加了 receipt 文件后没有被顺手改宽：一个真正未知的根文件仍应
        # 触发根污染告警（负例本身用 --strict，告警在 strict 下会算进 FAIL 计数）。
        (fx / "_qual_unknown_root_probe.md").write_text("throwaway\n", encoding="utf-8")
        proc = run_script(fx, validator, ["--strict"])
        out = proc.stdout + proc.stderr
        located = "hook 脚本不存在：.claude/hooks/subagent_report_index.py" in out
        pollution_still_detected = "_qual_unknown_root_probe.md" in out and "根目录疑似污染" in out
        negative = mk_outcome(proc, proc.returncode != 0 and located and pollution_still_detected,
                               {"injection": "删除 .claude/hooks/subagent_report_index.py（settings.json 与 "
                                             ".codex/config.toml 均引用）+ 根目录放一个真正未知文件",
                                "pollution_still_detected": pollution_still_detected})
    return make_result(
        tid, group, validator, "custom-fixture", positive, negative,
        "正例额外覆盖 issue #75 缺口②回归：根目录放一份 template-sync.py 默认路径落盘的 "
        ".template-sync-receipt.json，证明 --strict 不再误判根污染。负例删一处被 "
        ".claude/settings.json hooks 声明引用的脚本文件（触发 check_settings() 的 hook 存在性"
        "校验）同时在根目录放一个真正未知文件，证明 ROOT_WHITELIST 加了 receipt 后依旧能拦真"
        "污染，没有被顺手改宽。",
    )


def t_g1_9() -> dict:
    tid, group, validator = "T-G1-9", "g1", "scripts/check-outcome-ledger-schema.py"
    with fixture("g1-9-pos") as fx:
        proc = run_script(fx, validator, ["--strict"])
        positive = mk_outcome(proc, proc.returncode == 0)
    with fixture("g1-9-neg") as fx:
        ledger = fx / ".claude" / "skills" / "coding-agent-quota" / "fixtures" / "outcome" / "outcome-ledger.sample.jsonl"
        lines = ledger.read_text(encoding="utf-8").splitlines()
        assert lines, "sample ledger 为空，无法注入"
        lines[0] = lines[0][:-5]  # 截断末尾字符，破坏 JSON 语法（schema 违规：不可解析记录）
        ledger.write_text("\n".join(lines) + "\n", encoding="utf-8")
        proc = run_script(fx, validator, ["--strict"])
        out = proc.stdout + proc.stderr
        located = "outcome-ledger.sample.jsonl" in out and "invalid JSON" in out
        negative = mk_outcome(proc, proc.returncode != 0 and located,
                               {"injection": "截断 outcome-ledger.sample.jsonl 首行末尾字符，制造非法 JSON 记录"})
    return make_result(
        tid, group, validator, "custom-fixture", positive, negative,
        "check-outcome-ledger-schema.py 无独立 --self-test CLI 开关，但正常 main() 每次都会用"
        "内置合成记录对 schema 拒绝逻辑做内部负向断言（check_negative_schema_rejection）——"
        "clean fixture 正例 OK 本身已经内在验证过该负向逻辑未被破坏；本 T-ID 额外做一次"
        "外部注入（破坏真实 fixture ledger 文件字节），证明对真实文件的 schema 违规同样可定位报错。",
    )


# --------------------------------------------------------------------- G6 custom fixtures

ADAPTER_DIRS = [".codex/agents", ".agents/skills"]
CHANGED_RE = re.compile(r"changed (\d+)/(\d+) adapter file")


def _expected_files_via_import(fx: Path):
    """在 fixture 内以 importlib 方式复用 sync-codex-adapters.py 的 expected_files()，
    不重新实现 adapter 生成规则（复用优先）。"""
    import importlib.util

    mod_path = fx / "scripts" / "sync-codex-adapters.py"
    spec = importlib.util.spec_from_file_location("_qual_sync_codex_adapters", mod_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def t_g6_1() -> dict:
    tid, group, validator = "T-G6-1", "g6", "scripts/sync-codex-adapters.py"
    with fixture("g6-1") as fx:
        mod = _expected_files_via_import(fx)
        expected = mod.expected_files()
        assert expected, "expected_files() 为空，无法验证幂等"
        desynced_path = sorted(expected)[0]
        desynced_path.unlink()
        proc1 = run_script(fx, validator, [])
        m1 = CHANGED_RE.search(proc1.stdout)
        changed_1st = int(m1.group(1)) if m1 else None
        digest1 = dir_digest(fx, ADAPTER_DIRS)
        proc2 = run_script(fx, validator, [])
        m2 = CHANGED_RE.search(proc2.stdout)
        changed_2nd = int(m2.group(1)) if m2 else None
        digest2 = dir_digest(fx, ADAPTER_DIRS)
        ok = (
            proc1.returncode == 0 and proc2.returncode == 0
            and changed_1st is not None and changed_1st >= 1
            and changed_2nd == 0
            and digest1 == digest2
        )
        positive = mk_outcome(
            proc2, ok,
            {
                "injection": f"删除一个已生成 adapter（{desynced_path.relative_to(fx).as_posix()}）制造初始未同步",
                "first_run_changed": changed_1st,
                "second_run_changed": changed_2nd,
                "adapter_tree_digest_stable": digest1 == digest2,
            },
        )
    return make_result(
        tid, group, validator, "custom-fixture", positive, None,
        "幂等性是单一性质（连续两次 write 第二次 changed=0 且产物树摘要不变），无对立负例概念——"
        "本 T-ID 只有 positive 断言，不强行造一个不存在的\"负例\"。先人为删掉一个 adapter 制造"
        "初始未同步（第一次 write 必须 changed>=1），再验证第二次 write 收敛为真正 no-op。",
    )


def t_g6_2() -> dict:
    tid, group, validator = "T-G6-2", "g6", "scripts/sync-codex-adapters.py"
    with fixture("g6-2-pos") as fx:
        proc = run_script(fx, validator, ["--check", "--context", "auto"])
        positive = mk_outcome(proc, proc.returncode == 0)
    with fixture("g6-2-neg") as fx:
        target = fx / ".codex" / "agents"
        toml_files = sorted(target.glob("*.toml"))
        assert toml_files, "fixture 内无 .codex/agents/*.toml，无法注入"
        victim = toml_files[0]
        victim.write_text(victim.read_text(encoding="utf-8") + "\n# manual hand-edit drift\n", encoding="utf-8")
        proc = run_script(fx, validator, ["--check", "--context", "auto"])
        out = proc.stdout + proc.stderr
        rel = victim.relative_to(fx).as_posix()
        located = f"stale generated adapter: {rel}" in out
        negative = mk_outcome(proc, proc.returncode != 0 and located,
                               {"injection": f"手改 {rel} 追加一行非生成内容"})
    return make_result(
        tid, group, validator, "custom-fixture", positive, negative,
        "负例手改一个已生成的 .codex/agents/*.toml，验证 --check 能定位到具体 stale 文件路径。",
    )


def t_g6_3() -> dict:
    tid, group, validator = "T-G6-3", "g6", "scripts/sync-codex-adapters.py"
    with fixture("g6-3-pos") as fx:
        mod = _expected_files_via_import(fx)
        expected = mod.expected_files()
        mismatches, missing = [], []
        for path, content in expected.items():
            rel = path.relative_to(fx).as_posix()
            if not path.exists():
                missing.append(rel)
            elif path.read_text(encoding="utf-8", errors="replace") != content:
                mismatches.append(rel)
        ok = not mismatches and not missing
        positive = {
            "exit_code": 0,
            "ok": ok,
            "evidence": f"{len(expected)} expected adapter path(s) 比对：missing={missing} mismatches={mismatches}",
            "expected_count": len(expected),
        }
    with fixture("g6-3-neg") as fx:
        mod = _expected_files_via_import(fx)
        expected = mod.expected_files()
        victim_path = sorted(expected)[0]
        victim_path.write_text(expected[victim_path] + "\n# byte-level drift\n", encoding="utf-8")
        mismatches = []
        for path, content in expected.items():
            if path.exists() and path.read_text(encoding="utf-8", errors="replace") != content:
                mismatches.append(path.relative_to(fx).as_posix())
        rel = victim_path.relative_to(fx).as_posix()
        ok = mismatches == [rel]
        negative = {
            "exit_code": 0 if ok else 1,
            "ok": ok,
            "evidence": f"注入单点 content drift 后 mismatches={mismatches}（期望仅命中 {rel}）",
            "injection": f"追加字节到 {rel}",
        }
    return make_result(
        tid, group, validator, "custom-fixture", positive, negative,
        f"逐项 byte-for-byte 比对 expected_files()（复用 sync-codex-adapters.py 自身生成规则，不"
        f"重新实现）与磁盘实际内容；正例上实测 expected 文件数为 {positive['expected_count']}"
        "（与 issue #54 表格标注的 38 一致，实测值以本次运行为准，不硬编码）。",
    )


def t_g6_4() -> dict:
    tid, group, validator = "T-G6-4", "g6", "scripts/check-agent-harness.py"
    with fixture("g6-4-pos") as fx:
        proc = run_script(fx, validator, ["--strict"])
        out = proc.stdout + proc.stderr
        clean = "Codex hook 脚本不存在" not in out and "缺少 .codex/rules/default.rules" not in out
        positive = mk_outcome(proc, proc.returncode == 0 and clean)
    with fixture("g6-4-neg") as fx:
        config = fx / ".codex" / "config.toml"
        before = config.read_text(encoding="utf-8")
        after = before.replace(
            ".claude/hooks/context_threshold_notice.py",
            ".claude/hooks/context_threshold_notice_MISSING.py",
        )
        assert after != before, "注入无效：目标字符串未命中"
        config.write_text(after, encoding="utf-8")
        proc = run_script(fx, validator, ["--strict"])
        out = proc.stdout + proc.stderr
        located = "Codex hook 脚本不存在：.claude/hooks/context_threshold_notice_MISSING.py" in out
        negative = mk_outcome(proc, proc.returncode != 0 and located,
                               {"injection": ".codex/config.toml 里一处 hook command 指向不存在的脚本文件名"})
    return make_result(
        tid, group, validator, "custom-fixture", positive, negative,
        "Codex 侧可发现性的权威检查已在 check-agent-harness.py 的 check_codex_config()（复用，"
        "不重复造 fixture）；负例改 .codex/config.toml 一处 hook 引用指向不存在文件。",
    )


# --------------------------------------------------------------------- registry


def g1_checks() -> list:
    return [
        t_g1_1,
        lambda: check_self_test(
            "T-G1-2", "g1", "check-anatomy-drift.py",
            "复用 --self-test：内嵌 governed_components 断链(governed-index-missing) / "
            "orphan(governed-index-orphan) / owner 不一致(governed-index-mismatch) 三类对抗 fixture "
            "（scripts/check-anatomy-drift.py 源码 620-640 行区间），逐条 PASS/FAIL 均无条件打印。",
        ),
        lambda: check_self_test(
            "T-G1-3", "g1", "check-doc-lifecycle.py",
            "复用 --self-test：内嵌\"锚点/注册表状态矛盾被报错\"与\"跃迁 approved 缺段\"两类场景"
            "（对应「非法状态转移」——doc-lifecycle 校验的是锚点/注册表一致性 + 跃迁时字段齐全，"
            "不是像 validate-experiment-state 那样的显式有向状态机图，如实标注该差异，不过度声称）。",
        ),
        t_g1_4,
        t_g1_5,
        lambda: check_self_test(
            "T-G1-6", "g1", "check-capability-catalog.py",
            "复用 --self-test：16 个 catalog 对抗场景含显式 \"missing\"（能力未登记，"
            "scripts/check-capability-catalog.py:459/379）用例；该 self-test 只在失败时打印"
            "case 标签，正常通过时静默——exit 0 + 无 FAIL 行即为全部 16+5 场景符合预期的证据。",
        ),
        lambda: check_self_test(
            "T-G1-7", "g1", "check-provenance-chain.py",
            "复用 --self-test：7+ 个悬空引用负例（evidence/claim/dataset/checkpoint/review/figure，"
            "scripts/check-provenance-chain.py:1712-2001 区间的 negative-dangling-* 用例族）；"
            "_run_case 只在失败时 append，正常通过时静默。",
        ),
        lambda: check_self_test(
            "T-G1-8", "g1", "validate-experiment-state.py",
            "复用 --self-test：显式非法状态转换用例（run-skip-approval「planned → running」跳过 "
            "approved、run-zombie「done → running」回转，命中 scripts/validate-experiment-state.py:233 "
            "的状态机拒绝规则）；expect() 只在失败时打印，正常通过时静默。",
        ),
        t_g1_9,
    ]


def g6_checks() -> list:
    return [t_g6_1, t_g6_2, t_g6_3, t_g6_4]


# --------------------------------------------------------------------- report rendering


def render_markdown(payload: dict) -> str:
    meta = payload["meta"]
    lines = [
        f"# Qualification report — group={meta['group']}",
        "",
        f"- 被测 commit：`{meta['commit']}`",
        f"- 生成时间：{meta['generated_at']}",
        f"- 生成时工作树是否 dirty：{meta['worktree_dirty']}",
        f"- 结果：{meta['counts']['pass']}/{meta['counts']['total']} PASS"
        f"（复用 self-test {meta['counts']['reused_self_test']} 项，自建 fixture "
        f"{meta['counts']['custom_fixture']} 项）",
        "",
        "| T-ID | validator | mode | status | notes |",
        "| --- | --- | --- | --- | --- |",
    ]
    for r in payload["results"]:
        notes = r["notes"].replace("\n", " ").replace("|", "\\|")
        lines.append(f"| {r['id']} | `{r['validator']}` | {r['mode']} | {r['status']} | {notes} |")
    lines.append("")
    lines.append("## 逐项证据")
    for r in payload["results"]:
        lines.append(f"\n### {r['id']} — {r['status']}\n")
        lines.append(f"- validator: `{r['validator']}`（mode={r['mode']}, reused_self_test={r['reused_self_test']}）")
        lines.append(f"- notes: {r['notes']}")
        lines.append(f"- positive: exit={r['positive']['exit_code']} ok={r['positive']['ok']}")
        lines.append("```\n" + r["positive"]["evidence"] + "\n```")
        if r["negative"] is not None:
            lines.append(f"- negative: exit={r['negative']['exit_code']} ok={r['negative']['ok']}"
                          f" injection={r['negative'].get('injection', '')!r}")
            lines.append("```\n" + r["negative"]["evidence"] + "\n```")
        else:
            lines.append("- negative: n/a（见 notes 说明）")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--group", choices=["g1", "g6", "all"], default="all")
    args = parser.parse_args()

    checks = []
    if args.group in ("g1", "all"):
        checks += g1_checks()
    if args.group in ("g6", "all"):
        checks += g6_checks()

    results = []
    for fn in checks:
        result = fn()
        status = result["status"]
        print(f"[qualification] {result['id']} {status}", flush=True)
        results.append(result)

    n_pass = sum(1 for r in results if r["status"] == "PASS")
    n_reused = sum(1 for r in results if r["reused_self_test"])
    n_custom = sum(1 for r in results if not r["reused_self_test"])
    payload = {
        "meta": {
            "commit": commit_sha(),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "worktree_dirty": worktree_dirty(),
            "group": args.group,
            "runner": "lab/evals/qualification/run-qualification.py",
            "counts": {
                "total": len(results),
                "pass": n_pass,
                "fail": len(results) - n_pass,
                "reused_self_test": n_reused,
                "custom_fixture": n_custom,
            },
        },
        "results": results,
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = OUT_DIR / f"report-{args.group}.json"
    md_path = OUT_DIR / f"report-{args.group}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")

    print(f"[qualification] {n_pass}/{len(results)} PASS —— {json_path.relative_to(REPO)}")
    return 0 if n_pass == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
