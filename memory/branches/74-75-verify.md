# 74-75-verify — 独立复核报告（师爷·审·门禁缺口）

- 复核对象：PR #76（`fix/74-75-qualification-strict-gaps`），writer = 干将·修·门禁缺口
- 复核范围：**只块 A（#74）、块 B（#75 缺口②）**。块 C（#75 缺口①）已由 writer 标
  NEEDS-HUMAN-DECISION、未改代码，本次只做「writer 是否偷改了锁定合同」的负面核查，不评审块 C 本身。
- 方法：先独立读 issue #74/#75 原文与被改文件全文形成判断，再动手复核；未采信 writer 的
  `memory/branches/74-75-strict-gaps.md` 过程叙述作为判据。

## 总裁决：**APPROVE**

块 A、块 B 均 CONFIRMED-PASS。白名单未被过度放宽（已造负例证明）。writer 未擅自改动块 C 相关的
锁定合同代码（`template-sync.py` / `CONTRACT.md` TS-3 diff 为空）。`validate-governance.py --strict`
独立复跑全绿。

---

## 块 A（#74）—— G4 runner UNAVAILABLE 死代码

**改动**：`lab/evals/control-plane/run-g4-scenario.py` T-G4-6 负例分支 a，先 `shutil.which("paseo")`
探测；装了 paseo 走原断言（期望 `paseo_presence == "-"`），没装则标 `unavailable=True` 走既有
`outcome(..., unavailable=...)` → `make_result()` 里 `positive.get("unavailable") or
negative.get("unavailable")` 的 UNAVAILABLE 判定路径（该路径本身是既有代码，此前从未被真实赋值触发
——本次是"接线"而非新造判定逻辑，符合 issue 要求）。

**独立验证**：

1. 装 paseo 情形（本机真装，`which paseo` = `/home/user/.local/bin/paseo`）：
   ```
   uv run python3 lab/evals/control-plane/run-g4-scenario.py
   ```
   → `T-G4-6 PASS`，整体 `7/7 PASS`。CONFIRMED-PASS。

2. 模拟无 paseo（剥 PATH）：
   ```
   env -i PATH="/usr/bin:/bin" HOME="$HOME" python3 lab/evals/control-plane/run-g4-scenario.py
   ```
   → `T-G4-6 UNAVAILABLE`（**不再是 FAIL**），整体 `6/7 PASS`（第 7 项 UNAVAILABLE，非 FAIL）。
   CONFIRMED-PASS——命中 issue #74 描述的确切缺陷场景（无 paseo CLI 机器上原本误判 FAIL）。

**未接线成 PASS 蒙混的核查**：`unavailable=` 走的是文件里既有、此前零赋值的判定分支
（`make_result()` L117-120，本次未新增该逻辑，只是让它第一次被真实触发），不是伪造 PASS。

**一个次要观察（非阻断项）**：`main()` 的整体 exit code 逻辑（`return 0 if n_pass ==
len(results) ...`，未被本次改动触碰）把 UNAVAILABLE 计入非-PASS，故无 paseo 机器上整体进程 exit
code 仍为 1（`REAL_EXIT=1`，独立验证过）。这与 issue #74 的诉求（"不误判 FAIL 标签"）已经吻合——
issue 只要求 T-G4-6 自身状态标签正确、不要求整体 runner exit 0——且该 runner 未被
`validate-governance.py` 或任何 strict 治理门禁引用（`grep -rn "run-g4-scenario"
scripts/ .agent/ AGENTS.md` 无命中），只是独立资格测试工具，不影响 CI 门禁结果。判定：不阻断
APPROVE，仅记录供 human 参考（若未来想让 UNAVAILABLE 不拖累整体 exit code，可另开 issue）。

## 块 B（#75 缺口②）—— receipt 文件根白名单

**改动**：
- `scripts/check-agent-harness.py`：`ROOT_WHITELIST` 精确新增一个字符串
  `".template-sync-receipt.json"`（无通配符/前缀匹配，membership 语义为 `name in
  ROOT_WHITELIST` 精确匹配，见 L93）。
- `lab/evals/qualification/run-qualification.py` T-G1-5：正例 fixture 新增落一份
  `.template-sync-receipt.json` 到根、断言 `--strict` 不再告警该文件；负例 fixture 在原有
  「删 hook 脚本」基础上**追加**一个真正未知文件 `_qual_unknown_root_probe.md`，断言该文件仍触发
  「根目录疑似污染」告警——这正是防「顺手放宽」的负例覆盖。

**独立验证**（未依赖 writer 的 fixture，自建根级临时文件核查）：

1. baseline strict（无额外文件）：`OK — 0 error(s), 0 warning(s)`，exit 0。
2. 根放 `.template-sync-receipt.json`：仍 `OK — 0 error(s), 0 warning(s)`，exit 0。CONFIRMED-PASS
   ——缺口②本身修复属实。
3. **负例**：再放一个真正未知文件 `.totally-unknown-root-file.txt`：
   ```
   WARN  根目录疑似污染（不在白名单）：.totally-unknown-root-file.txt
   [check-agent-harness] FAIL — 0 error(s), 1 warning(s)
   REAL_EXIT=1
   ```
   CONFIRMED-PASS——白名单**没有**被改宽成能吞掉任意文件，仍能拦真实未知根文件。这是本次复核
   刻意要求的负例，独立验证通过。
4. `run-qualification.py --group g1` 独立复跑：
   ```
   [qualification] T-G1-1..9 全 PASS
   [qualification] 9/9 PASS
   ```
   CONFIRMED-PASS。

## 块 C（#75 缺口①）—— 仅核查「未被偷改」

`git diff main...HEAD -- scripts/template-sync.py scripts/CONTRACT.md
.agent/template-versioning-policy.md ANATOMY.md scripts/check-anatomy-drift.py` 输出为空——
diff 为零。`git diff main...HEAD --stat` 全量改动文件列表与 PR #76 声明的 8 个文件完全一致
（`report-g1.{json,md}`、`report-g4.{json,md}`、`run-g4-scenario.py`、`run-qualification.py`、
`memory/branches/74-75-strict-gaps.md`、`check-agent-harness.py`），无块 C 相关文件出现。
CONFIRMED：writer 未擅自改动锁定的 merge/TS-3 合同代码，块 C 确实原封不动留给 human 决策。

## 门禁复跑

```
uv run --with pyyaml python3 scripts/validate-governance.py --strict
```
→ `[validate-governance] OK — 0 error(s), 0 warning(s)`，REAL_EXIT=0。独立复跑全绿。

## 复核过程中的自我清理

复核时为造负例在 worktree 根临时写过 `.template-sync-receipt.json` / 未知探测文件，验证后已
`rm` 干净；复核过程中重跑 `run-g4-scenario.py --group g1` 等评测脚本会自动重写
`report-g1.{json,md}` / `report-g4.{json,md}` 的时间戳/commit-sha/dirty 字段（内容非本次评审
意图改动），已用 `git checkout --` 还原到 PR 提交时的状态，复核结束时 worktree 干净
（`git status --short` 无输出）。
