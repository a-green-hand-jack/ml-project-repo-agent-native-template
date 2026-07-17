# Branch Status: 75-typed-relation-impl

## Purpose

实现 #75 缺口①（merge 分类锚文件 frontmatter 结构键不随 template-sync 传播，导致
`check-anatomy-drift.py --strict` 的 `parent-child-bidirectional` 判定 FAIL）——新增
**TS-12**（typed-relation-propagation）：对 `kind=merge`/`kind=scaffold` 且已存在于下游的
文件，若声明了 `parent`/`children`/`contracts`/`contract_for`，sync 额外做一次窄字段
union/补齐追平（只增不删），与 TS-3 的哨兵机制正交并存，不改写 TS-3 措辞本身。

## Parent session

都督·统·治理路线交办；plan doc `plans/20260717-75-merge-frontmatter-propagation.zh.md`
（方案 ①b）human 于 2026-07-17 经该路线批准。

## Branch / base

`fix/75-typed-relation-propagation`，base `main`（commit `2edce98`：plan doc 初稿）。

## Worktree

`/home/user/.paseo/worktrees/1kaz3672/fix-75-typed-relation-propagation`

## Linked issue / PR

issue #75 缺口①（父 #52 P5，源 #58）；块 A/B 已由 PR #76 合入 main（commit `c681a18`）；
本分支承接块 C。PR 号：见「Exit condition」。

## Owned paths

- `scripts/template-sync.py`（新增 TS-12 核心逻辑）
- `scripts/CONTRACT.md`（新增 TS-12 规则行 + `related_files` 补 `check-anatomy-drift.py`/
  `../.agent/anatomy-protocol.md`）
- `.agent/anatomy-protocol.md`（typed relation 一节补充 TS-12 追平通道说明）
- `.agent/template-versioning-policy.md`（「已知边界」段落改写为「TS-12 自动追平」）
- `lab/evals/template-sync/run-template-sync-smoke.py`（新增 `check_typed_relation_propagation`
  fixture + 4 组断言）
- `plans/20260717-75-merge-frontmatter-propagation.zh.md` + `memory/doc-lifecycle.yaml`
  （draft → approved，前一个 commit `6f820c8`，先于本分支实现提交完成）

## Forbidden paths

- `scripts/CONTRACT.md` 里 TS-1..TS-11 既有措辞（未改，只新增 TS-12 行）。
- `lab/data|runs|models` bytes、`checkpoints/`、`wandb/`、`lab/infra/private/`。
- 不 push main、不 merge、不建 release tag。

## Anatomy impact

无结构改动（不新增/移动/删除文件），只新增函数与文档条目；`same-commit` 门禁不适用。

## Claim / evidence impact

无 lab/ 实验声明改动。

## Plan doc

`plans/20260717-75-merge-frontmatter-propagation.zh.md`——status: approved（human 于
2026-07-17 经都督·统·治理路线批注，四个 `[?]` 决策点已全部收敛，见该文档「Human 批注区」
「当前决策」）。`memory/doc-lifecycle.yaml` 条目 `plan-20260717-75-merge-frontmatter-propagation`
同步 draft → approved，approval 字段记录批准 provenance。

## Current state

TS-12 已实现、self-test 通过、ELF replay 复验通过、全量门禁绿。待开 PR（不 merge，等独立
verifier + human）。

## Commands run

- `python scripts/check-doc-lifecycle.py` → OK（plan doc 转 approved 后）
- `uv run --with pyyaml python3 scripts/validate-governance.py --strict` → 0 error/0 warning
  （plan 转 approved 后 + TS-12 实现后，各跑一次，均绿）
- `python3 lab/evals/template-sync/run-template-sync-smoke.py` → OK（19 组场景全绿，含新增
  `check_typed_relation_propagation`）
- `python3 scripts/check-anatomy-drift.py --self-test` → OK（16 条 fixture governance 发现，
  与实现前基线一致，未受 TS-12 影响）
- `python3 scripts/sync-codex-adapters.py --check` → `context=source OK — 0 issue(s)`
  （未改 `.claude/` 表面，确认适配未漂移）
- ELF replay（隔离临时 fixture，非 standing case，用后即删）：见下节。

## ELF replay 复验证据（#75 缺口①验收标准）

**方法**：不复用 `origin/worktree-case+elf-template-replay`（该分支内容是早期泛化功能测试，
不是本缺口的最小复现素材）——改为在 `/tmp` 下临时构造一个隔离 fixture，直接反映缺口①的
真实成因（root `ANATOMY.md` 是 `merge` kind，frontmatter 永不随 sync 更新；`scripts/ANATOMY.md`
是 `framework` kind，每次 sync 都整体覆盖）：

1. `rsync -a --exclude='.git'` 复制本 worktree全部内容到临时 downstream 目录；`git init` +
   单 commit 起一个自包含的临时 git（满足 `check-doc-lifecycle.py` 对 approved plan 条目的
   branch-exists 校验，不污染真实仓库历史）。
2. 用脚本把该 downstream 副本根 `ANATOMY.md` frontmatter 的 `children:` 块摘除（模拟一个在
   commit `8d1def4`——即当初把 `parent`/`children` 双向声明首次接上的那次改动——之前接入本
   模板、此后只做常规 merge sync（从未手工同步 frontmatter）的下游：`scripts/ANATOMY.md`
   （framework，逐次整体覆盖）始终带着最新的 `parent: ANATOMY.md`，但根 `ANATOMY.md`
   （merge，frontmatter 永不触碰）永远停留在采纳时的旧 frontmatter）；写一份最小
   `.template.toml`（`version = "v1.3.8"`，与上游同版本，验证「版本不变仍会对齐 typed
   relation」这条路径）。
3. **追平前**：`python3 scripts/check-anatomy-drift.py --strict` → **FAIL**
   （`GOVERNANCE anatomy=scripts/ANATOMY.md rule=parent-child-bidirectional violation=
   声明 parent=ANATOMY.md，但 ANATOMY.md 未在 children 中回链本节点`）——精确复现 issue #75
   缺口①描述的失败模式。
4. 用本分支修改后的 `scripts/template-sync.py --from <本 worktree>` 对该 downstream 副本跑
   一次真实 sync：计划输出 `typed relation 追平 1`，`^ ANATOMY.md（typed relation 追平，
   TS-12）`；apply 后根 `ANATOMY.md` frontmatter 追平出 `children:\n  - scripts/ANATOMY.md`
   （union 补齐，其余 frontmatter/body 逐字节未动）；receipt `typed_relation_sync.applied=true`，
   `changes=[{"path":"ANATOMY.md","fields":[{"key":"children","action":"new-field",
   "added":["scripts/ANATOMY.md"]}]}]`。
5. **追平后**（`uv run --with pyyaml`，确保 strict 深度解析可用）：
   - `python3 scripts/check-anatomy-drift.py --strict` → **OK — 0 处 governance 发现**。
   - `python3 scripts/validate-governance.py --strict` → **OK — 0 error(s), 0 warning(s)**
     （八个子 validator 全绿，含 `check-doc-lifecycle`/`check-provenance-chain`/
     `check-capability-catalog`）。
6. 临时 fixture 用后即删（`shutil.rmtree`），未污染任何 standing case 或真实仓库状态。

**结论**：追平前 FAIL → 追平后 `--strict` 双门禁全绿，且未产生任何非预期 diff（frontmatter
只多了 `children:` 一个字段，body/哨兵块/其余 frontmatter 字节级不变）——#75 缺口①验收标准
达成。

## Open risks

- TS-12 只对 `kind=merge`/`kind=scaffold` 生效（`kind=framework` 排除，因其整体字节覆盖已
  保证 frontmatter 天然同步，重复计算是空 diff）——这是实现阶段在 plan「独立于
  framework/merge/scaffold 哪一类」措辞基础上做的工程收窄，收窄理由已写进
  `scripts/CONTRACT.md` TS-12 行与 `scripts/template-sync.py` 内联注释，供 review 复核。
- 未处理「上游删除/改名某个 typed relation 目标路径」场景——plan 明确列为非目标，留给
  TS-2 既有 MAJOR gate 人工 reconcile。

## Exit condition

TS-12 实现 + self-test + ELF replay strict 转绿 + 全量门禁绿后，开 PR（base main，不 merge），
等独立 verifier + human 批准后合并、归档 worktree。
