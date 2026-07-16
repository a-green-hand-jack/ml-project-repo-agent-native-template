# Branch Status: 67-downstream-adapter-context

## Purpose

issue #67：`sync-codex-adapters.py --check` 把「git index 成员资格」误当「磁盘存在性」，
导致真实 adopt→首次 template-sync 时，正确、byte-match 但尚未 `git add` 的 38 个 `.codex`/
`.agents` 生成物被误报 missing，receipt 永远 partial。human 已批准 D1–D3 全部推荐方案。

## Parent session

派发方：都督·统·P2收口（Paseo id 98b55ecc-b223-43f0-b2e0-f959cdfcb30f）。
执行 agent：干将·改·双境合同（本 session）。

## Branch / base

`fix/67-downstream-adapter-context`，base `main@934f42c`（= origin/main，clean checkout）。
实现 commit HEAD：`7992478` — `79924780279d3d5d64b7614745af294e21876a9b`。

## Worktree

`/home/user/.paseo/worktrees/1kaz3672/fix-67-downstream-adapter-context`（独立 Paseo worktree）。

## Linked issue / PR

`gh issue view 67`（未编辑其内容）。未开 PR——按停止条件本 session 只交实现，PR/merge 是 human gate。

## Owned paths

`scripts/sync-codex-adapters.py`、`scripts/check-agent-harness.py`、`scripts/bootstrap-project.py`、
`scripts/adopt-existing-repo.py`、`lab/evals/bootstrap/run-bootstrap-smoke.py`、`scripts/ANATOMY.md`、
`scripts/CONTRACT.md`、`scripts/README.md`、`lab/evals/bootstrap/README.md`、`CONTRACT.md`（根，
仅 contract_version 表格行）、`memory/branches/67-downstream-adapter-context.md`。

## Forbidden paths

未触碰：root `CONTRACT.md` 分类内容、`.agent/template-versioning-policy.md`、#60 anchor 合同、
#62 CONTRACT 分类逻辑、`lab/data/`、`lab/runs/`、`lab/models/`、`lab/infra/private/`、其它 agent
的 worktree/branch。`scripts/template-sync.py` 未改动（核实其从未直接调用
`sync-codex-adapters.py --check`，只调用 write 模式，故无 context 相关改动需要）。

## Anatomy impact

`scripts/ANATOMY.md` 的 `sync-codex-adapters.py` 行改写为描述 context-aware 合同（同 commit）。
无新文件/目录，`check-same-commit.py --staged` 确认 0 处结构改动需要额外 anatomy 更新之外的内容。
`scripts/CONTRACT.md`：TS-5 收窄措辞（分类真源仍是 template-manifest.toml，context 语义移到新规则）；
新增 **TS-10** adapter-check-context 规则；`contract_version` 1→2（root `CONTRACT.md` 表格同步）。

## Claim / evidence impact

无 lab/研究 claim 受影响；本 issue 是治理脚本 bugfix，不涉及实验结果。

## Plan doc

无独立 plan doc；本 prompt（issue #67 正文 D1–D3 + 派发方 root-cause 定位）即权威 spec。

## Current state

D1（context-aware 拆分）、D2（真实 Git fixture 回归 + truthful write() 输出）、D3（issue 独立
owner，不重开 #61/不动 #60/#62）全部实现完成并已提交。

**D1** — `scripts/sync-codex-adapters.py`：
- 新增 `--context {source,downstream,auto}`（默认 auto，只影响 `--check`；write 模式磁盘-only，
  与 context 无关）。
- `detect_context()`：无 `.template.toml` → source；regular 可解析文件 → downstream；symlink 或
  无法解析为合法 TOML → `ContextDetectionError` fail-closed（非零退出，不降级到较弱检查）。
- `source_manifest_errors()`（原 `generated_manifest_errors()`）：#61 tracked exact-set 原样保留。
- `downstream_manifest_errors()`：新增，只要求 `template-manifest.toml` 把每个 expected adapter
  path 分类为 generated，不要求已 `git add`；复用 `template-sync.classify()`，未写第二套
  parser/glob。
- missing/stale/unexpected 磁盘检查对两种 context 均无条件执行（本就是磁盘读取，未依赖 git）。
- 输出打印 `context=<resolved>`，避免两种 PASS 混淆。

**D2a** — `write()` 现在打印 `changed N/expected M`（真实改了几个就报几个），不再无论是否有
改动都声称 `wrote {len(expected)}`。

**已知身份调用点显式传 context**：
- `check-agent-harness.py::check_codex_adapters()` → `--context auto`（该脚本自身既可能在模板
  source 跑（自检）也可能被复制进 downstream repo 跑，身份取决于所在 REPO，显式 auto 而非隐式
  默认）。
- `bootstrap-project.py::run_sync_codex_adapters()` 的 check_result 调用 → `--context downstream`
  （target 在此步骤前已写好 `.template.toml`，结构上必是 downstream）。
- `adopt-existing-repo.py::run_sync_codex_check()` → `--context downstream`（adoption target 恒为
  downstream）。
- `template-sync.py` 核实无直接 `--check` 调用（只调用 write 模式做 generated_rebuild），故无需
  改动——这是与 issue 正文字面列举的唯一偏差，已在此说明并非遗漏。

**D2b** — `lab/evals/bootstrap/run-bootstrap-smoke.py` 新增 `check_untracked_generated_adapters`
（单一 owner，复用已有 `git archive HEAD` + 真实 harness 基础设施，未新建第二个 fixture 体系）：
1. `build_untracked_adapters_repo()`：materialize 真实模板树后，在 `git init` 提交前删除
   `.codex/agents` 与 `.agents/skills`（真实生成命名空间），使基线 commit 完全不含它们。
2. `self_bootstrap()` 跑真实 `bootstrap-project.py`：其内部 `sync-codex-adapters.py` write 模式
   重新生成这些文件——磁盘正确、但因基线提交在它们存在前已完成而【真实 untracked】（issue #67 的
   精确前置条件，非合成占位）。
3. 断言 `git ls-files -- .codex/agents .agents/skills` 为空、`git status --porcelain` 显示 untracked。
4. 断言真实 `validate-governance.py --strict` / `check-agent-harness.py --strict` /
   `sync-codex-adapters.py --check` 全绿（这正是修复前会 FAIL 的路径——已用未修复 HEAD 复现验证，
   见下方 Commands run）。
5. 断言直接 `--check`（auto）stdout 含 `context=downstream`。
6. 断言同一 untracked fixture 上显式 `--context source` 仍 FAIL（#61 未被全局放宽）。
7. 断言磁盘层 missing / stale / unexpected 三种负例在 downstream context 下仍 FAIL（分别删除、
   改写、新增 rogue 文件，逐一验证后还原）。
8. 断言 malformed（非法 TOML）与 symlink 的 `.template.toml` 锚点在 `--context auto` 下 fail-closed
   （非零退出，明确报错，不静默降级为 source 或 downstream 的 PASS）；最后还原合法锚点确认恢复 OK。

**D3** — 未重开 #61，未回滚其 exact-set 结论；未动 #60 anchor 合同；未动 #62 CONTRACT 分类逻辑。

## Commands run

全部在 worktree 内执行，路径均为 repo-relative；`uv run --with pyyaml` 用于规避裸 python3 缺
PyYAML 时 `validate-governance --strict` 的假 YAML warning（已知环境坑，非本次回归）。

1. **复现验证（修复前，未提交状态）**：
   `python lab/evals/bootstrap/run-bootstrap-smoke.py`
   → `FAIL: self-bootstrap over a base commit without generated adapters should succeed`
   （`sync-codex-adapters: failed`），证明新回归确实捕获了 #67 描述的真实 bug。
2. 提交实现后（HEAD=7992478）重跑同一命令：
   `python lab/evals/bootstrap/run-bootstrap-smoke.py`
   → `[bootstrap-smoke] OK (tested commit 79924780279d3d5d64b7614745af294e21876a9b)`
3. `python lab/evals/adoption/run-adoption-smoke.py` → `[adoption-smoke] OK`（27 项子测试全过）
4. `python lab/evals/template-sync/run-template-sync-smoke.py` → `[template-sync-smoke] OK`
   （18 个场景，含 `check_adapter_ownership_exact_set` 仍验证 #61 未受影响）
5. `python scripts/sync-codex-adapters.py --check` → `[sync-codex-adapters] context=source OK — 0 issue(s)`
6. `python scripts/check-agent-harness.py --strict` → `[check-agent-harness] OK — 0 error(s), 0 warning(s)`
7. `python scripts/check-anatomy-drift.py` → `OK — 扫描 17 个 ANATOMY.md，0 处结构漂移`
8. `python scripts/check-same-commit.py --staged` → `OK —— 0 处结构改动`
9. `git diff --check HEAD~1 HEAD` → 无输出（0 处空白错误）
10. `python -m py_compile scripts/sync-codex-adapters.py scripts/check-agent-harness.py scripts/bootstrap-project.py scripts/adopt-existing-repo.py lab/evals/bootstrap/run-bootstrap-smoke.py` → 通过
11. `uv run --with pyyaml python scripts/validate-governance.py --strict` → `[validate-governance] OK — 0 error(s), 0 warning(s)`
    （子检查 check-agent-harness / check-anatomy-drift(strict) / check-doc-lifecycle /
    check-outcome-ledger-schema / validate-experiment-state / check-provenance-chain(13 pass) /
    check-capability-catalog(46 项) 全绿）
12. `python scripts/check-capability-catalog.py` → `OK — 登记 46 项，0 error(s), 0 warning(s)`

补充手工验证（`/tmp/scratch-context-test.py`，跑后已删除，不留痕）：轻量 fixture 逐一验证
auto/source/downstream 三种 context、missing/stale/unexpected 三种负例、malformed/symlink 锚点
fail-closed，共 8 个场景全部符合预期，先于写入正式回归前用于设计验证。

## Latest result

全部验证命令 PASS，无 FAIL/WARN。工作区干净（`git status` 无未提交改动，实现已原子提交在
`7992478`）。

## Open risks

- `check-agent-harness.py::check_codex_adapters()` 传 `--context auto` 而非固定
  `downstream`——这是有意设计（该脚本自身身份随所在 REPO 变化，无法静态确定），依赖
  `.template.toml` 角色锚点的存在时机；若某调用路径在 anchor 写入前就跑 check-agent-harness，
  auto 会错判为 source。当前 4 个已知调用点（bootstrap/adopt/check-agent-harness 自身）均在
  anchor 写入之后才跑 check，未发现反例，但这是隐含时序假设，值得 fresh review 关注。
- issue 正文把 `template-sync.py` 列入「已知身份的调用点」，但核实其从未直接调用
  `sync-codex-adapters.py --check`（只有 write 模式），故未对其做改动——这是对 spec 字面表述的
  偏离，原因已在上文「Current state」说明，认为不影响验收标准（`template-sync.py` 的验收路径
  是通过 `validate-governance.py`→`check-agent-harness.py`→`sync-codex-adapters.py --check` 间接
  覆盖，已被新回归验证）。
- `contract_version` 1→2 的判级依据是 CONTRACT.md 自身变更矩阵的「MINOR：新增可选参数」条款，
  但矩阵表未穷尽「新增 CLI 可选参数 + 新增 contract rule」这一组合的判级；采用保守的显式 bump
  而非留在 1，供 fresh review 复核判级是否合适。

## Exit condition

实现完成、自验全绿、已原子提交、branch status 已落盘。等待 fresh reviewer 独立复核；PR/merge/
关闭 issue 均为 human gate，本 agent 不代做。
