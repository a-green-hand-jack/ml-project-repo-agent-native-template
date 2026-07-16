# Branch Status: integrate-60-refresh

## Purpose

刷新 #60 approved candidate（`origin/fix/60-adoption-template-anchor@5e40ad3`，两轮 fresh
APPROVE）到 #67/PR #68 合入后的新 `origin/main`（`604a02a`），做集成 merge + 完整验收，
特别是当初因 #67 缺陷而 receipt=partial 的真实 adopt→首次 sync 链路。

## Parent session

派发方：都督·统·P2收口。执行 agent：干将·改·双境合同（同一 session，接续 #67 实现工作）。

## Branch / base

`integrate/60-adoption-anchor-refresh`，从 `origin/main@604a02a` 新建（已核实 = 604a02a）。
`git merge --no-ff origin/fix/60-adoption-template-anchor`（`5e40ad3`，未改写其内容）。

**Merge commit sha：`a73143c4c7baf6cbe5fbd8fedbf2e0ae669ba908`**（`a73143c`）。

## Worktree

`/home/user/.paseo/worktrees/1kaz3672/fix-67-downstream-adapter-context`（复用 #67 的 worktree，
按派发方指示直接换分支，未新建 worktree）。

## Linked issue / PR

#60、#67、PR #68（已合入）。未开新 PR/未 merge/未关 issue——均为 human gate。

## Owned paths

本次 merge 涉及的冲突文件：`lab/evals/bootstrap/run-bootstrap-smoke.py`、`scripts/README.md`；
以及 `memory/branches/integrate-60-refresh.md`（本文件）。其余文件均为 git 自动合并（无冲突），
未手工触碰其内容。

## Forbidden paths

未触碰 `5e40ad3` 历史（`git merge --no-ff` 保留双亲，未 rebase/未 cherry-pick 改写）；未动
`p2a-60-adoption-template-anchor`（#60 旧集成证据分支）；未污染本模板 repo（步骤 5 的端到端
fixture 全部建在 `/tmp`，已在验证后清理）；未触碰 `lab/data/`、`lab/runs/`、`lab/models/`、
`lab/infra/private/`。

## Anatomy impact

无新增/删除文件产生的结构改动（两处冲突都是既有文件内的行级合并）。`check-same-commit.py --staged`
在 merge 前后均确认无遗漏的 ANATOMY 同步（merge commit 自身报告"2 处结构改动，对应 anatomy 已同
变更集更新"——这两处是 git 自动合并识别到的、两侧各自 commit 已经各自同 commit 更新过的历史结构
改动，非本次 merge 新引入）。

## Claim / evidence impact

无 lab/研究 claim 受影响。本次是治理/adoption 工具链的集成 merge + 验收。

## Current state

### 步骤 2：冲突解决（恰好两处，均为纯 additive 合并，未见语义调和需求）

1. **`lab/evals/bootstrap/run-bootstrap-smoke.py`**：唯一冲突 hunk 是 import 行——#67（HEAD）加
   `import os`（symlink 测试用），#60 加 `import stat`（`.template.toml` 创建/覆盖权限 mode 保持
   断言用）。两者互不冲突的功能需求，解法是都保留（`import os` + `import stat`）。git 对该文件
   其余部分（#67 新增的 `check_untracked_generated_adapters` 函数及其 `main()` 注册；#60 对既有
   `check_idempotency`/`check_origin_conflict` 函数内嵌的 mode 断言增强）全部 auto-merge 成功，
   无需手工干预——已逐一核实两侧函数在合并结果中都完整存在且都在 `main()` 的 check 列表/直接调用
   路径中被执行到（见下方验证证据）。
2. **`scripts/README.md`**：唯一冲突 hunk 是相邻两行各自的行内注释——#67 给
   `sync-codex-adapters.py --check` 行加了 `--context` 说明；#60 给
   `adopt-existing-repo.py --phase all` 行加了 `--origin <owner/repo>` 现在是必填参数的说明。两条
   互不相关，解法是都保留。

未出现第三处冲突，未触发"停下汇报"条件。

### 步骤 5：真实端到端 P2 验收（核心交付，见"Commands run"逐条证据）

在 `/tmp` 建了一个真正独立的、非本模板 checkout 的小型"既有项目"（README 缺失以避免命中模板
control-item 冲突判定、`src/main.py`、`requirements.txt`、`LICENSE`，独立 `git init` + 初始
commit），驱动真实 `adopt-existing-repo.py` → **不提交 scaffold 结果**直接驱动真实
`template-sync.py` 做首次同版本 sync——这是刻意还原 issue #67 repro 表格里"scaffold 产生的 38 个
`.codex`/`.agents` 输出存在、byte-correct，但 `git ls-files` 为空"的精确前置条件（不是靠人为删除
`.git` 索引，而是让 adoption 的真实 scaffold 阶段产生的输出保持真正未提交状态）。

a-d 逐条结果：
- **a. adopt**：`adopt-existing-repo.py --phase all --origin <owner/repo>` exit 0；discover 判定
  3 个 root entry 全部 `conservative_import`（无冲突）；scaffold 复制 445 项、0 blocker；normalize
  `template_anchor=created`；`.template.toml` 内容 `origin='a-green-hand-jack/ml-project-repo-agent-native-template'
  version='v1.3.8'`（= 当前 `VERSION` 文件内容）。`git ls-files -- .codex/agents .agents/skills`
  为空；磁盘上已有 16 个 `.codex/agents/*.toml`（scaffold 复制自本 worktree 自身已生成的产物）；
  `git status --porcelain` 显示 22 行 untracked（含整个 scaffold 产物，尚未提交任何东西）。
- **b. 首次同版本 sync**：`template-sync.py --from <本 worktree> --receipt receipt1.json`
  exit 0。receipt1：`result=pass`（**不是 partial**）、`from_version=to_version=v1.3.8`
  （`version_advanced=false`，同版本对齐）、`stages` 全 `ok`
  （preflight/plan/apply/generated_rebuild/validate/commit_version）、
  `classification.framework` 含 `CONTRACT.md` 且落地字节与本 worktree 的 `CONTRACT.md` 完全一致、
  `manifest.generated.expected` 计数 38、`missing`/`unexpected` 均为空列表。同步过程内嵌的
  `validate-governance.py --strict` 段（含 `check-agent-harness.py` → `sync-codex-adapters.py
  --check`）全部 OK。sync 后 `git status --porcelain -- .codex/agents .agents/skills` 显示
  `?? .agents/skills/` `?? .codex/agents/`——确认此时这 38 个文件依然genuinely untracked，而
  验收依然全绿，直接证明 #67 修复生效。
- **c. 第二次 sync（幂等）**：同一 `--from` 再跑一次，`result=pass`、
  `manifest.apply_changed=[]`（真正的 apply no-op）、版本仍 `v1.3.8`。
- **d. 直接 `sync-codex-adapters.py --check`**：exit 0，stdout 含
  `context=downstream OK — 0 issue(s)`——确认 auto 检测正确判定 downstream 并 PASS。

fixture 与两份 receipt 均建在 `/tmp`，验证完成后已用字面路径 `rm -rf` 清理，未留痕、未污染本
模板 repo。

## Commands run

全部确切命令、输出摘录见上文"Current state"。补充列出可复验的命令序列（原始 shell 命令，供
fresh review 复现；`/tmp` 路径为一次性随机目录，复现时会得到不同路径）：

1. `git fetch origin` → `git checkout -b integrate/60-adoption-anchor-refresh origin/main`
   （确认 `git rev-parse origin/main` = `604a02afc68a13b6f68d7e6f09eadac7d21cd265`）
2. `git rev-parse origin/fix/60-adoption-template-anchor` → `5e40ad39e52d52405266dab39d22c5cfa9b92f26`
   （= 派发方给出的 approved candidate sha，核实一致）
3. `git merge --no-ff origin/fix/60-adoption-template-anchor` → 2 处冲突（如上），手工解决后
   `git add -A && git commit` → `a73143c4c7baf6cbe5fbd8fedbf2e0ae669ba908`
4. `python lab/evals/bootstrap/run-bootstrap-smoke.py`
   → `[bootstrap-smoke] anchor-create mode=0664` / `[bootstrap-smoke] anchor-forced-overwrite
   mode=0640`（#60 场景执行证据）/ `[bootstrap-smoke] OK (tested commit
   a73143c4c7baf6cbe5fbd8fedbf2e0ae669ba908)`（#67 的 `check_untracked_generated_adapters` 场景
   同批执行，见其内部无 FAIL 输出）
5. `python lab/evals/adoption/run-adoption-smoke.py`
   → `anchor-allow-blocked foreign-origin/malformed/symlink exit=1 anchor=unchanged
   queued_paths=unchanged`（#60 场景）+ `test_template_anchor_contract OK` + `[adoption-smoke] OK`
6. `python lab/evals/template-sync/run-template-sync-smoke.py` → `[template-sync-smoke] OK`
7. `python scripts/sync-codex-adapters.py --check` →
   `[sync-codex-adapters] context=source OK — 0 issue(s)`
8. `python scripts/check-agent-harness.py --strict` →
   `[check-agent-harness] OK — 0 error(s), 0 warning(s)`
9. `python scripts/check-anatomy-drift.py` → `OK — 扫描 17 个 ANATOMY.md，0 处结构漂移`
10. `uv run --with pyyaml python scripts/validate-governance.py --strict` →
    `[validate-governance] OK — 0 error(s), 0 warning(s)`（七个子检查全绿：
    check-agent-harness / check-anatomy-drift(strict) / check-doc-lifecycle /
    check-outcome-ledger-schema / validate-experiment-state / check-provenance-chain(13 pass) /
    check-capability-catalog(46 项)）
11. `git diff --check HEAD~1 HEAD` → 无输出（0 处空白错误）
12. 真实端到端 fixture（步骤 5，详见上文"Current state"逐条 a-d）：
    - `python scripts/adopt-existing-repo.py <tmp-target> --origin
      a-green-hand-jack/ml-project-repo-agent-native-template --phase all --project-name
      existing-project`
    - `python scripts/template-sync.py --from <本 worktree> --receipt receipt1.json`（首次）
    - `python scripts/template-sync.py --from <本 worktree> --receipt receipt2.json`（第二次）
    - `python scripts/sync-codex-adapters.py --check`（fixture 内直接跑）

## Latest result

全部命令 PASS，0 FAIL。集成分支工作区干净（merge commit 后无未提交改动）。

## Open risks

- 端到端 fixture 里的"既有项目"故意不含 `README.md`（含 README 会被判定为 template control-item
  内容冲突 blocker，那是既有的、正确的保守行为，不是本次要验证的路径）；若 fresh review 想验证
  "含冲突文件的 adoption + 修复后 sync"路径，需要另建 fixture，本次未覆盖（超出派发方给的验收范围）。
- `scripts/README.md`、`lab/evals/bootstrap/run-bootstrap-smoke.py` 两处冲突解法是纯字面拼接
  （两侧行都保留），未做额外 wordsmithing；若 fresh review 认为衔接措辞可以更顺，可另提 nit。

## Exit condition

merge 完成、全部验证命令 PASS（含真实端到端 P2 验收 a-d 全绿，receipt1/receipt2 均
`result=pass`）、branch status 已落盘、已 push `integrate/60-adoption-anchor-refresh` 到
origin。未开 PR、未 merge、未关 issue——等待 human gate 与派发方接手。
