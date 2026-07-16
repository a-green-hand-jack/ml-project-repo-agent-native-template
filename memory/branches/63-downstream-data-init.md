# Branch Status: 63-downstream-data-init

## Purpose

issue #63（#52 系统测试 P3 阶段）：template-sync 会给旧下游落地全新 G1 validator 脚本
（`check-doc-lifecycle.py` / `validate-experiment-state.py` / `check-provenance-chain.py`），
但不迁移它们要求的数据层，导致真实 ELF case 追平后从全绿掉到 4-FAIL（约 55 处：注册表缺失、
`status_history`/`approval` 字段缺失、`schema_version` 缺失、evidence `run_id`/`config` 缺失、
artifact-index `location` 缺失），且 sync receipt 完全不体现这个语义缺口。human 已批准 D1–D3
方案（issue 正文）。

## Parent session

派发方：都督·统·P2收口（Paseo id 98b55ecc-b223-43f0-b2e0-f959cdfcb30f）。
执行 agent：干将·迁·下游数据层（本 session；中途因 Claude session 额度上限中断一次，派发方
指示额度重置后原地继续，worktree 现场完整保留，未丢失进度）。

## Branch / base

`fix/63-downstream-data-init`，base `origin/main@deeda67`（确认 HEAD 与 origin/main 一致，
clean checkout）。实现完成但**未提交**——本 doc 写于 commit 之前，commit sha 见下方
「Commands run」末尾补记或下一次更新。

## Worktree

`/home/user/.paseo/worktrees/1kaz3672/fix-63-downstream-data-init`（独立 Paseo worktree）。

## Linked issue / PR

`gh issue view 63`（未编辑其内容）。未开 PR——按停止条件本 session 只交实现，PR/merge 是
human gate。

## Owned paths

`scripts/init-governance-data.py`（新建）、`scripts/validate-experiment-state.py`、
`scripts/check-provenance-chain.py`、`scripts/validate-governance.py`、`scripts/template-sync.py`、
`scripts/ANATOMY.md`、`scripts/CONTRACT.md`、`scripts/README.md`、`scripts/CLAUDE.md`、
`.agent/artifact-policy.md`、`lab/evals/template-sync/run-template-sync-smoke.py`、
`memory/branches/63-downstream-data-init.md`。

## Forbidden paths

未触碰：ELF worktree 本体（`~/.paseo/worktrees/1kaz3672/worktree-case-elf-template-replay`，
见下方「事故与修复」——文件字节确认零损伤）、`p2a-*`/其它 agent 分支、P4–P8、`lab/data/`、
`lab/runs/`、`lab/models/`、`lab/infra/private/`。无新第三方依赖；未写第二套 YAML/schema
parser（`init-governance-data.py` 全程通过 `importlib` 复用三个 validator 自身的 parser/
判定函数）。

## Anatomy impact

`scripts/ANATOMY.md`：新增 `init-governance-data.py` 一行 + related_files 条目；
`check-doc-lifecycle.py` / `validate-experiment-state.py` / `check-provenance-chain.py` /
`validate-governance.py` / `template-sync.py` 五行描述扩写（同行追加文字，未破坏 120 行硬上限，
现 116 行）。`check-anatomy-drift.py` 确认 0 处漂移。`scripts/CONTRACT.md`：新增 **TS-11**
governance-data-gap-report 规则；变更矩阵「弱化/删除 TS-1..TS-9」行扩为 TS-1..TS-11。
`scripts/README.md` / `scripts/CLAUDE.md` / `.agent/artifact-policy.md` 同 commit 补充说明。
`contract_version` 未 bump（判定为 MINOR 加字段，沿用现有「receipt schema 增字段」条款，不
认为触发 contract_version 递增——与 #67 的保守 bump 判断不同，因为 #67 是新增 CLI 参数，
本次是纯 receipt 字段新增，供 fresh review 复核这一判级差异是否合适）。

## Claim / evidence impact

无 lab/research claim 受影响（本 issue 是治理脚本能力扩展 + 数据层初始化工具，不涉及本仓库
自身的实验结果）。ELF fixture 内 4 条 claim（`claim-elf-source-identity` 等）在验证过程中被
`init-governance-data.py` 标记 `governance_status: legacy_unverified`——这是**验证用的临时
fixture 副本**上发生的，不是本仓库/ELF worktree 本体的真实数据变更。

## Plan doc

无独立 plan doc；issue #63 正文「批准的方案（D1–D3）/ Non-goals / Stop condition」即权威 spec
（human 2026-07-16 批准）。

## Current state：D1–D3 逐条对照

**D1 · 机制** — 已实现，全部通过 `importlib` 复用三个 validator 自身的 parser/判定函数，
未写第二套 schema parser：

- **`memory/doc-lifecycle.yaml` 注册表 + 状态锚点回填**：不改 `check-doc-lifecycle.py` 代码，
  复用其既有 `status: draft` 档位（该 validator 模块 docstring 本就写明「占位符容忍范式：
  draft/in-review 天然通过」，`plans/ANATOMY.md` 确认这是官方状态模型的一部分，不是我发明的
  旁路）。给每个未登记的四类文档补状态锚点行（`Status: draft · <今日日期> · legacy backfill by
  scripts/init-governance-data.py, structure only, unverified`）+ 注册表条目
  （`issue`/`branch`/`worktree`/`approval` 均为 `null`，draft 档位不要求这些字段）。
- **`schema_version`**：对 `experiment-ledger.yaml` / `claims.yaml` / `evidence.yaml` /
  7 类 artifact-index / `regression-matrix.yaml` / `release-gates.yaml` 统一补
  `schema_version: 1`（纯结构，新旧数据同等安全，不需要 legacy 标记，文件不存在时跳过不越权
  创建）。
- **`governance_status: legacy_unverified` + `governance_note`** 统一标记（**改了 3 个
  validator 代码**，见下）：
  - `validate-experiment-state.py`：新增 `_check_legacy_marker()`（返回 bool，标记非法/缺
    note 时不换来豁免，仍走严格路径），`_check_history` / `_check_approval_fields` /
    `_check_closure` 三处豁免；不豁免 `id`/`status` 合法性与 `alerts` 审计。
  - `check-provenance-chain.py`：`_check_governance_marker()`（同构）；`check_evidence` 里
    `command`/`config`/`run_id` 缺失可豁免，但**不进 `valid_ids`**（新增 `legacy_ids` 三态）；
    `check_claim_evidence_edges` 里 legacy evidence 归属边仍要求成立、不算 FAIL 也不算
    eligible；claim 全部 evidence 降级为 legacy 时 claim 自身也可标记，豁免
    「`status∈{partial,supported}` 需 eligible evidence」检查；`check_artifact_indexes` 里
    `status≠unknown` 但 `location` 缺失，原代码硬编码「任何真实状态都不得跳过」（无例外设计），
    现加 legacy 例外——这是本次唯一改动一条「原设计明确无豁免出口」的硬规则的地方，判断依据与
    风险见下方「Open risks」。
  - `validate-governance.py`：**发现范围外的第 4 个重叠检查**——`check_evidence_chain()`
    是一个早于本次三个新 G1 validator 就存在的独立函数，语义几乎完全重复
    `check-provenance-chain.py` 的 evidence/claim 校验（`evidence_complete()` 同样要求
    `run_id`/`config` 等 6 字段）。在 ELF fixture 上，即使三个新 validator 全绿，
    `validate-governance.py` 聚合仍会因这个旧检查报 7 个 ERROR，导致「G1 全绿」这个 D3
    验收目标实际达不成。判定为该检查是同一根因的第 4 个受灾点，不是 #63 范围外的新问题
    （字段/语义完全一致），补了对称的 legacy 豁免（新增 `_check_legacy_marker()` 局部复制，
    因为这个文件是独立进程、不方便 importlib 复用另一文件的私有函数）。这一决定未见诸原
    issue 文字，属于我在实现中发现并按同一设计原则处理的范围扩展，请 fresh review 重点复核。

- **`scripts/init-governance-data.py`**（新建，单一 owner，幂等）：
  - 扫描四类 gap，只补结构骨架 + legacy 标记，不编造任何字段真实值。
  - **幂等 + 「对新数据不放松」的机制保证**：每个文件用「是否已有 `schema_version`」
    （doc-lifecycle 用「注册表文件是否已存在」）作为「是否已 init 过」的信号——首次运行才会
    把当前 FAIL 条目回填为 legacy；一旦该信号已存在，之后新出现的不合规条目一律只 `FLAG`
    （打印待人工处理），不会被静默标成 legacy。已登记 `governance_status` 的条目永远跳过。
    条目缺 `commit`/`supports_claim`/`grade` 等「非治理新增」基础字段时也只 `FLAG`，不算
    legacy 缺口（那类空缺不是新门禁字段，标 legacy 会掩盖真实缺陷）。
  - 诚实计数：`changed`/`skipped`/`flagged`，`--verbose` 打印 skip 明细（吸取 #67 「不许虚报」
    的教训）。
  - `--dry-run` 供 `template-sync.py` 收尾阶段预览（不落盘）。
  - `--self-test` 内嵌 fixture：4 类正例（ledger/evidence/claim/artifact-index 全部标记）+
    doc-lifecycle 首次登记 + 幂等（二次运行 zero changed）+ 3 类负例（已 init 后新增不合规
    条目不自动标记、governance_note 缺失不换来豁免、governance_status 非法值报错）+
    dry-run 零副作用断言。

**D2 · receipt 诚实性** — 已实现，`template-sync.py` 新增 `governance_data_gap` 字段（向后
兼容，不改既有字段语义）：

- 新检测函数 `newly_landed_validators(plan)`：匹配 `scripts/check-*.py` / `scripts/validate-*.py`
  且 `action == "create"` 的 framework 文件（`init-governance-data.py` 本身不匹配这个 glob——
  它是补救脚本不是 gate，故意不计入「新落地门禁」清单）。
- `governance_data_gap_report()`：apply 完成后（文件已落地）通过 `importlib` 加载刚落地的
  `init-governance-data.py`，调用 `run(downstream, dry_run=True)` 拿诚实计数，异常时返回
  `{"error": ...}` 不影响 sync 本身结果。
- **不自动执行 init**：全程只读预览，写进 receipt 供人工/agent 决定是否执行；已用 smoke 负例
  验证数据文件字节在 sync 过程中未被动过。
- `--dry-run` sync 模式下文件还未落地，`gap` 字段为 `null` + 提示改用真实 sync 后的
  `--dry-run` 预览（诚实说明局限，不假装能预览）。

**D3 · 验收** — 见下方「Commands run」与「事故与修复」，全部通过。

## 事故与修复（务必完整阅读）

D2 验收过程中，为了在 `/tmp` 造 ELF fixture 副本，我用 `shutil.copytree` 复制了受保护的
`~/.paseo/worktrees/1kaz3672/worktree-case-elf-template-replay`。**根因**：git worktree 的
`.git` 是指向共享元数据的**指针文件**（`gitdir: .../worktrees/<name>`），不是独立 `.git`
目录；`copytree` 把这个指针文件也复制了过去，导致 `/tmp` 副本与原 worktree 共享同一份
HEAD/index/refs。我在 `/tmp` 副本里跑的 `git checkout -b elf-replay-sync-v14rc ...` 与
`git stash -u`/`git stash pop` 因此**改写了原 worktree 共享的 HEAD 指针**（一度指向
`elf-replay-sync-v14rc` 而非正确的 `worktree-case+elf-template-replay`）与 index 缓存。

**影响面**：仅 git 元数据（HEAD 指针 + index 缓存），文件字节零损伤——`git diff HEAD`（工作区
直接对比 HEAD commit，绕开 index）在修复前后全程为空，证明工作区文件从未被写入/删除。

**发现与处置**（派发方独立复核后给出的带条件批准，按其指定顺序执行）：
1. 发现后立即停止，不再对该 worktree做任何新操作，先用 `git symbolic-ref HEAD
   refs/heads/worktree-case+elf-template-replay` 把 HEAD 指针改回正确分支（只改指针，不动
   文件/index）。
2. 用 `AskUserQuestion` 把完整诊断（根因、已验证的零文件损伤证据、剩余 index 缓存问题）报给
   派发方，请求确认修复步骤。
3. 派发方独立复核我的三项主张（`git diff HEAD` 为空、`stash list` 为空、HEAD 已复位）后给出
   带条件批准 + 精确的五步顺序：① 先 `rm -rf /tmp/elf-fixture-63`（销毁污染源，防止修复过程
   中被再次改写）；② 原 worktree 内 `git reset`（mixed、无路径参数，只重置 index 到 HEAD，
   不碰文件）；③ 验证 `git status --short` 为空、`git worktree list` 指向 `4f1a9ec`、
   `git diff HEAD` 仍为空；④ 用 `git clone --branch worktree-case+elf-template-replay
   <本地 origin repo> /tmp/elf-fixture-63-v2` 重建独立 fixture（真正独立 `.git` 目录，与
   worktree 元数据完全隔离）；⑤ 完整记录进本文档。
4. 按顺序执行，全部验证通过（见下方 Commands run 第 12–15 条的确切输出）。

**教训**：以后任何需要复制 git worktree 的场景，一律用 `git clone --branch <name> <origin>`
或 `git archive`（`lab/evals/bootstrap/run-bootstrap-smoke.py` 已有先例），绝不用
`cp -r`/`shutil.copytree` 直接复制 worktree 目录——`.git` 指针文件会把两个物理目录悄悄焊接
成同一个共享 git 状态。

## D2 验收路径（Commands run）

全部在 worktree 内执行，路径均为 repo-relative；`uv run --with pyyaml` 规避裸 python3 缺
PyYAML 时的假失败（已知环境坑）。

1. **ELF fixture baseline（修复前，安全 clone `/tmp/elf-fixture-63-v2`，`elf-replay-sync-v14rc`
   分支 @ `94a9a35`）**：
   - `check-doc-lifecycle.py` → `FAIL — 1 error(s)`（注册表缺失）
   - `validate-experiment-state.py` → `FAIL — 23 error(s)`
   - `check-provenance-chain.py` → `FAIL — 28 fail, 1 unknown, 2 pass`
   三者与 issue 正文复现记录的数字完全一致。
2. 同步本次改动的 5 个脚本（`check-doc-lifecycle.py`/`validate-experiment-state.py`/
   `check-provenance-chain.py`/`validate-governance.py`/`init-governance-data.py`）进 fixture，
   跑 `uv run --with pyyaml python scripts/init-governance-data.py --verbose` →
   `changed=34 skipped=9 flagged=0`（8 文档登记、4 run 标记 legacy、4 evidence 标记、
   3 claim 标记、4 artifact-index 条目标记 + 全部所需文件补 schema_version）。
3. init 后：三个 G1 validator 单独跑全部 `OK`；`uv run --with pyyaml python
   scripts/validate-governance.py`（非 strict，对应 D3「G1 门禁全绿」验收口径）→
   `[validate-governance] OK — 0 error(s), 0 warning(s)`。
4. **`--strict` 在 fixture 上的已知偏差（非回归，超出范围）**：`--strict` 会额外报
   `check-anatomy-drift.py` 与 `check-provenance-chain.py`（`dataset-index.yaml` UNKNOWN
   升级为 FAIL）两处——前者是因为我只同步了 5 个脚本、未同步 fixture 自己那份陈旧的
   `scripts/ANATOMY.md`（fixture 是 #63 之前的模板快照，文档天然对不上我新改的脚本内容，
   这是测试方法的产物，不是本仓库/新脚本的缺陷）；后者是 ELF fixture 从未有过
   `lab/data/dataset-index.yaml`，与 #63 范围（三个新 G1 validator vs 旧数据）无关，是更早
   就存在的独立数据缺口。非 strict 口径完全对应 D3 写明的验收标准。
5. **幂等**：同一 fixture 上二次运行 `init-governance-data.py` → `changed=0 skipped=35
   flagged=0`。
6. **`init-governance-data.py --self-test`** → `OK`（4 类正例 + 2 类负例 + dry-run 零副作用 +
   幂等断言，均通过）。
7. **`validate-experiment-state.py --self-test`** → `OK`（含新增 legacy 正例 + 3 类负例）。
8. **`check-provenance-chain.py --self-test`** → `OK — 正负 fixture 全部符合预期`（既有对抗
   fixture 未受影响）。
9. **template source 自身全套门禁**（本 worktree，改动后）：
   - `uv run --with pyyaml python scripts/validate-governance.py --strict` →
     `OK — 0 error(s), 0 warning(s)`
   - `uv run --with pyyaml python scripts/check-agent-harness.py --strict` →
     `OK — 0 error(s), 0 warning(s)`
   - `uv run --with pyyaml python scripts/check-anatomy-drift.py` →
     `OK — 扫描 17 个 ANATOMY.md，0 处结构漂移`
   - `uv run --with pyyaml python scripts/sync-codex-adapters.py --check` →
     `context=source OK — 0 issue(s)`
   - `python3 scripts/check-same-commit.py --staged`（改动已 `git add -A`）→
     `OK —— 1 处结构改动，对应 anatomy 已同变更集更新`
   - `git diff --cached --check` → 无输出（0 处空白错误）
   - `python3 -m py_compile scripts/*.py lab/evals/template-sync/*.py` → 通过
10. **bootstrap 派生路径回归**：`uv run --with pyyaml python
    lab/evals/bootstrap/run-bootstrap-smoke.py` → `OK`（未受影响，WARN 仅提示测的是 HEAD
    非 dirty worktree，与本次改动无关）。
11. **adoption smoke 回归**：`uv run --with pyyaml python
    lab/evals/adoption/run-adoption-smoke.py` → `OK`（27 场景全过）。
12. **template-sync smoke 回归（含新场景）**：`uv run --with pyyaml python
    lab/evals/template-sync/run-template-sync-smoke.py` → `OK`（19 个场景，新增
    `check_governance_data_gap_report`：首次落地 3 个 G1 validator 时 receipt 含
    `governance_data_gap`（`new_validators` 精确匹配、`gap.changed≥1` 命中已知缺口、
    `suggested_command` 正确、数据文件字节未被动过）；validator 已存在时该字段为 `null`）。
13. **worktree 事故修复验证**：`git -C ~/.paseo/worktrees/1kaz3672/worktree-case-elf-template-replay
    status --short` → 空；`git worktree list` → `.../worktree-case-elf-template-replay
    4f1a9ec [worktree-case+elf-template-replay]`；`git diff HEAD` → 空（0 行）。

## Latest result

D1–D3 全部实现完成，D2 验收路径全部通过（非 strict 口径，对应 D3 明文验收标准），ELF worktree
事故已按派发方指定顺序完整修复并三重验证。工作区改动已 `git add -A`（11 个文件：10 改动 +
1 新建），尚待 commit + push。

## Open risks

- `validate-governance.py::check_evidence_chain()` 的 legacy 豁免是本次实现中发现并按同一
  设计原则处理的**范围扩展**（issue 原文只点名三个新 G1 validator），不是原 spec 字面要求；
  虽然判断依据充分（同一根因、同一字段、达不成 D3「G1 全绿」验收目标否则），但请 fresh review
  重点复核这个决定是否应该单独走一次 human 确认，而不是由 writer agent 自行拍板。
- artifact-index 的 `location` 空值原本是「任何真实状态都不允许跳过」的硬编码无例外规则（代码
  注释明确写了这个设计意图）；本次新增了 legacy 例外，等于打开了这条规则唯一的口子。已严格
  限定：只对显式登记 `governance_status: legacy_unverified` + 非占位 `governance_note` 的
  条目生效，新条目/无标记条目判定丝毫未变松；但这条规则的原始「无例外」设计本身可能是刻意的
  更强主张，请 fresh review/human 确认这个例外是否符合原作者意图。
- `contract_version` 保持 2 未 bump（本次新增 TS-11 属 receipt schema 增字段，判定为
  MINOR、复用「receipt schema 增字段」条款），与 #67 分支「保守 bump」的先例不同——供
  fresh review 复核两次判级是否应该一致。
- `init_claims()` 的 dry-run 预览有已知局限（在函数 docstring 与本 doc 均已说明）：dry-run
  模式下 evidence.yaml 未落盘，claims 侧 valid/legacy 集合基于磁盘现状重算，可能保守低估
  「evidence 全部降级后 claim 也该标记」的场景；只影响 `template-sync.py` receipt 的 gap
  **预览**准确度，不影响 `init-governance-data.py` 真实运行（非 dry-run）的正确性。
- 本次事故发现时机较晚（D2 验收阶段，而非事故发生的当下）——`git checkout -b` 早期执行时未
  立刻意识到 worktree `.git` 指针共享的风险；已在本 doc「教训」一节记录规避方式，供其他 agent
  与未来 session 参考，避免重复踩坑。

## Exit condition

实现完成、D1–D3 自验全绿、ELF worktree 事故已修复验证、branch status 已落盘。下一步：
原子 commit + push topic 分支（已获授权）；等待 fresh reviewer 独立复核；PR/merge/关闭 issue
均为 human gate，本 agent 不代做。
