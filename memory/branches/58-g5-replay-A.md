# 分支状态：test/g5-elf-replay-r2（G5，issue #58，父 #52 P5）—— Agent A（更新者）

> 执行官：干将·迁·ELF追平。角色：**更新者 A**，只做「把下游从 v1.1.0 追平到 v1.3.8」这一侧。
> **不做 B 的验收**（下游 G1 门禁全绿、G3 抽测、幂等复跑由独立的 Agent B 完成）。B 不读本文件的
> 过程也能凭「更新后的 worktree」自行验收；本文件是给 B/human 的自解释交接记录。

## Entry condition

- worktree：`/home/user/.paseo/worktrees/1kaz3672/test-g5-elf-replay-r2`，分支 `test/g5-elf-replay-r2`。
- 入场时 `git status` 干净，HEAD = `4f1a9ec`（`Merge branch 'main' into worktree-case+elf-template-replay`），
  与 `origin/test/g5-elf-replay-r2` 0 ahead / 0 behind。
- `VERSION` = `v1.1.0`；**`.template.toml` 不存在**（干净 ELF case 从未建立过版本锚点——这本身
  复现了 round1 发现的 #60「adopt-existing-repo 从不写 .template.toml」，本次不重开票，直接按
  T-G5-1 指示建立基线）。
- 上游 = 主 checkout `/home/user/Projects/ml-project-repo-agent-native-template`，当前 `v1.3.8`
  （git HEAD `cdba8bb506492e416f4e1d2c30e62cae43491dfd`，工作树 clean/not dirty）。
- 本轮**未读** round1（`elf-replay-sync-v14rc`）的过程记录（`memory/branches/elf-replay-sync-A*`），
  按指示独立干净重跑。唯一交叉引用：`git log --oneline --all -- scripts/template-sync.py` 时
  自然看到 round1 的证据 commit 标题（`94a9a35`），据此确认 #60/#61/#62 已修复合入 `main`；
  未打开该 commit 引用的 branch report 正文。

## 下游基线（建立 .template.toml 锚点，T-G5-1 前置）

干净 case 没有 `.template.toml`，按「真实 adopt 语义」建立 v1.1.0 基线（origin 用本 repo 自己的
git remote，因为这个测试 fixture 本身就是模板仓库的一个 worktree/clone，没有独立的下游 GitHub repo）：

```toml
[template]
origin = "git@github.com:a-green-hand-jack/ml-project-repo-agent-native-template.git"
version = "v1.1.0"
```

## 一个必须记录的桥接决策：先引导 `scripts/template-sync.py` 本身

读代码发现：这个 v1.1.0 下游自带的 `scripts/template-sync.py`（fb70fb1/b6358cc 引入，早于
v1.1.0 tag）是 **issue #35 事务化重写之前**的旧版本——没有 preflight/plan/apply/verify/commit
分阶段、没有 receipt、且有一个真实缺陷：`write_template_version()` 在 validator 跑之前就无条件
执行（写版本号 → 才跑 validate-governance），也就是说**验证失败版本也已经被写了**。这个缺陷早
已被上游 `3bb5a6b`（`fix(#35): template-sync 事务化——验证成功前不推进下游版本`）等一串 commit
修复，是 v1.1.0 之后、v1.3.8 之前的历史修复，不属于本轮 #60-63 范围，不重开票。

但这意味着：如果直接用这个下游自带的旧脚本去做本轮要求的「dry-run 报 preflight/receipt」「注入
verify 失败确认版本不推进」测试，工具本身就不具备 receipt/分阶段这些能力——**旧工具没法验证「新
合同」**。处理方式：把这一个文件（`scripts/template-sync.py`，manifest 里就是 `framework` kind，
本来就会被本次 sync 覆盖）提前从上游原样落地到下游（字节级 diff 确认一致），再用这个（即将成为
下游正式内容的）工具跑后续全部测试。这不是抄近道——这份文件反正会在真实 apply 里被覆盖成同一份
字节；提前落地只是让 dry-run/inject-failure 这些「用工具测工具」的步骤不必先撞上一个已知早已修复
的旧缺陷。已在下游 T-G5-1 之前完成，diff 确认字节相同后才开始跑 dry-run。

## T-G5-1：preflight + 版本 diff + 逐文件分类计划（dry-run）

```
python scripts/template-sync.py --from /home/user/Projects/ml-project-repo-agent-native-template --dry-run
```

结果（完整 log：本次 session 内 `/tmp/g5-dryrun-1.log`，未随分支提交）：

- `[template-sync] 下游 v1.1.0 → 上游 v1.3.8（跨 MINOR）`
- 计划：覆盖(framework) 53 · 新建 41 · merge 换块 4 · 保护(project) 257 · scaffold 保留 3
- **0 处 unclassified、0 处 merge-warn**——确认 #62（根 `CONTRACT.md` 未分类）已修复：dry-run
  计划里 `CONTRACT.md`/`scripts/CONTRACT.md` 都正确落在 `framework`（`+` 新建）。
- 提醒：本次会新落地 6 个门禁 validator（`check-agent-conflicts.py` /
  `check-capability-catalog.py` / `check-doc-lifecycle.py` / `check-outcome-ledger-schema.py` /
  `check-provenance-chain.py` / `validate-experiment-state.py`），dry-run 阶段 gap 字段按合同为
  `null`（未落地不预览）。
- receipt：`result="dry-run"`，未落盘文件（`--dry-run` 默认只打印，未指定 `--receipt`）。

**结论：T-G5-1 通过。** 版本 diff 与逐文件分类计划均干净、可解释；无需 `--allow-major`
（v1.1.0→v1.3.8 同 major，判级 MINOR）。

## T-G5-2：失败不推进版本（真实/天然触发，非人工语义损坏）

```
python scripts/template-sync.py --from /home/user/Projects/ml-project-repo-agent-native-template
```

第一次真实（非 dry-run）执行的结果**天然**触发了 verify 失败——不需要额外去人为破坏文件才能
造出一个失败场景：dry-run 已提示的 6 个新落地门禁 validator，一旦真的落地到磁盘，会立刻要求
下游既有的旧数据（`lab/research/*.yaml`、`lab/artifacts/*.yaml`、`memory/doc-lifecycle.yaml`
注册表）满足它们从未被要求过的字段（`schema_version`、`run_id`、`approved_by`、doc 状态锚点
等）——这正是 issue #63 D1 要解决的「新门禁 vs 旧数据」缺口，dry-run 阶段已诚实预告，真实 apply
时兑现。

真实执行结果（`/tmp/g5-apply-1.log` + 当时的 `.template-sync-receipt.json`）：

```
stages: {preflight: ok, plan: ok, apply: ok, generated_rebuild: ok, validate: fail, commit_version: skipped}
result: partial
from_version: v1.1.0 -> committed_version: v1.1.0（version_advanced: False）
failure.stage: validate / detail: exit 1
failure.touched_paths: 98 个精确路径（.agent/**、.claude/**、scripts/**、AGENTS.md 等 framework/merge 文件）
failure.rerun_command: python scripts/template-sync.py --from /home/user/Projects/ml-project-repo-agent-native-template
manifest.missing / manifest.unexpected: [] / []（apply 本身干净，问题只在 validate 阶段）
governance_data_gap: {new_validators: [...6个...], gap: {changed: 31, skipped: 9, flagged: 3}, suggested_command: "python scripts/init-governance-data.py"}
```

`validate-governance.py` 的具体 FAIL 来自 `validate-experiment-state.py`（23 error，旧 experiment
ledger 条目缺 `status_history`/`approved_by`/`approved_at` 等新字段）与 `check-provenance-chain.py`
（28 fail，evidence/claims/artifact-index 缺 `schema_version`/`run_id`/`location` 等）——**全部是
「新门禁遇旧数据」的已知缺口类别，不是新缺陷**。

**TS 规则核对**：`commit_version=skipped`、`version_kept=v1.1.0`、`result=partial`（非 fail，因为
`applied.written` 非空——文件确实半同步落地了，可安全重跑）、`touched_paths` 精确、`rerun_command`
可直接复制重跑。全部符合 CONTRACT.md 的 TS-6（validate-before-commit）与 TS-7
（receipt-result-states：非 pass 情况下正确落在 `partial`）。

### 补充：TS-2 MAJOR-gate 人工注入验证（合成注入，零副作用、无需 revert）

为了也覆盖「人工注入」这条路径（而不是只依赖天然失败），额外用一次性 scratch 目录
（`/tmp/g5-fake-major-upstream/VERSION` 内容 `v2.0.0`，与本仓库/上游均无关联，跑完即删）单独测了
MAJOR-gate（TS-2）：

```
python scripts/template-sync.py --from /tmp/g5-fake-major-upstream
```

输出 `STOP：这是 MAJOR 追平...`，exit code **2**；验证前后 `.template.toml`、
`.template-sync-receipt.json` 字节级 `diff` 完全一致（连 receipt 文件都没被摸一下）、
`git status --short | wc -l` 计数不变（129，无新增改动）。这是一条**先于任何写动作**的
pre-write no-op STOP，天然「零副作用」，跑完直接删掉 scratch 目录即完成"还原"，无需 `git checkout`。

**结论：T-G5-2 通过。** 两条独立证据都证明「verify/preflight 失败 → 版本不推进」：一条是本次
sync 自身天然触发的 validate 阶段 partial-fail（真实缺口，非人工破坏），一条是人工合成的
MAJOR-gate pre-write STOP。

## 追加：governance_data_gap 初始化（真跑，非 dry-run）

```
python scripts/init-governance-data.py --dry-run --verbose   # 先预览
python scripts/init-governance-data.py --verbose             # 真跑
```

预览：`changed=31 skipped=9 flagged=3`（3 个 flag 是 `init-governance-data.py` 自己文档里写明的
已知 dry-run 局限——`init_claims` 在 dry-run 下看不到 `init_evidence` 还没落盘的 legacy 标记，是
保守低估，不是真实缺口）。

真跑：`changed=34 skipped=9 flagged=0`——真实运行下评估顺序正确（evidence 先落盘，claims 再重新
计算），3 个 dry-run 期间的 flag 全部正确降级为 `legacy_unverified`，无遗留 flag。

初始化清单（真跑 `CHANGED` 条目，节选，完整见 `/tmp/g5-init-real.log`）：

- `memory/doc-lifecycle.yaml`：新建注册表 + 登记 8 篇既有文档（plans/human 下）状态锚点
  （全部 `status=draft`，未编造 issue/branch/approval）。
- `lab/research/experiment-ledger.yaml`：4 条 run 标记 `governance_status: legacy_unverified`
  （缺 `status_history`/`approved_by`/`approved_at` 等）+ 补 `schema_version: 1`。
- `lab/research/evidence.yaml`：4 条 evidence 标记 legacy（缺 `config`/`run_id`）+ `schema_version`。
- `lab/research/claims.yaml`：4 条 claim 标记 legacy（引用的 evidence 已全部降级）+ `schema_version`。
- `lab/artifacts/{result,trace}-index.yaml`：各 2 条 legacy（缺 `location`）+ 6 个 artifact-index
  文件全部补 `schema_version: 1`（含 model/table/figure/checkpoint-index，即使无 legacy 条目）。
- `lab/research/{regression-matrix,release-gates}.yaml`：补 `schema_version: 1`。

跑完立即 `python scripts/validate-governance.py` 复核：**`[validate-governance] OK — 0 error(s),
0 warning(s)`**，`check-provenance-chain` 从「28 fail, 1 unknown, 2 pass」转为
「0 fail, 1 unknown, 17 pass」（唯一的 `UNKNOWN` 是 `lab/data/dataset-index.yaml` 不存在，
本就不该在这个案例里存在，不是缺陷）。

## T-G5-3：干净 apply，verify 全绿，版本真推进到 v1.3.8

```
python scripts/template-sync.py --from /home/user/Projects/ml-project-repo-agent-native-template
```

```
stages: {preflight: ok, plan: ok, apply: ok, generated_rebuild: ok, validate: ok, commit_version: ok}
result: pass
from_version: v1.1.0 -> committed_version: v1.3.8（version_advanced: True）
warnings: []
manifest.missing / unexpected: [] / []
generated.missing / unexpected / content_mismatches: [] / [] / []
governance_data_gap: null（validator 这次 action≠create，本就该是 null）
source: {kind: git, git_sha: cdba8bb506492e416f4e1d2c30e62cae43491dfd, dirty: False}
```

**`.template.toml` before/after（版本推进的直接证据）：**

```diff
- version = "v1.1.0"
+ version = "v1.3.8"
```

（origin 字段不变）。写入方式：`.template.toml.<random>.tmp` mkstemp + `os.replace` 原子替换 +
父目录 fsync（TS-8）。

唯一的非阻断 WARN 来自 `check-agent-harness.py`：`.template-sync-receipt.json` 落在 repo
根目录，不在其「根目录白名单」里，告警"长文/报告/实验记录不应堆在 root"。这是**已知、非阻断**
的观察，不计入 governance error（`[check-agent-harness] OK — 0 error(s), 1 warning(s)`，整体
`validate-governance` 仍 `OK — 0 error(s), 0 warning(s)`）。receipt 落盘路径是
`template-sync.py` 自己的默认约定（`DEFAULT_RECEIPT = DOWNSTREAM / ".template-sync-receipt.json"`），
本次未覆盖为其它路径；这是模板自身「receipt 默认路径」与「根目录白名单」两处约定之间的一处小
不一致，记录在此供 human 参考，未展开修复（超出 A 的更新者授权范围，且不阻断本次 sync 结果）。

**结论：T-G5-3 通过。** round1 卡在「版本诚实停留 v1.1.0（未推进）」的那个缺口，本轮在
#60-63 修复 + 显式 init-governance-data.py 之后，干净转为 `result=pass` + 版本真实推进到
v1.3.8。

## T-G5-4(A)：分类未覆盖下游内容

用上游 `template-manifest.toml` 的 classify 规则对整个 `git status --porcelain` 变更集重新分类，
核对是否有 `project` kind 的路径被本次 sync 的 apply/generated 环节改动：

- 从最终 receipt 的 `manifest.apply_changed` / `manifest.generated_outputs` 与
  `classification.project`（257 条）取交集 → **空集**（sync 自己的 apply 阶段零命中 project 层）。
- 对整个 `git status --porcelain` 变更集（129 条，累计两次 sync + init-governance-data 的合计）
  重新分类，确实出现的 `project` kind 路径全部可归因到**两类明确、非 sync-apply 的动作**：
  1. `init-governance-data.py`（显式独立动作，本就设计为写 project 层的 legacy 标记/schema_version，
     不编造字段真实值）：`lab/research/*.yaml`、`lab/artifacts/*.yaml`、`lab/models/checkpoint-index.yaml`、
     `memory/doc-lifecycle.yaml`、`plans/*.zh.md` 状态锚点、`human/**`。
  2. `.template.toml` 本身（sync 的 `commit_version` 专门原子写入，`snapshot_tree` 显式排除它，
     不算在 apply/generated 的分类覆盖判定范围内——这是版本锚点自己的合同，不是「框架层覆盖了
     项目层」）。
- 硬边界路径（`lab/data|runs|models` 的 bytes/checkpoint、`wandb/`）**零命中**——`init-governance-data.py`
  只碰了 `lab/models/checkpoint-index.yaml`（索引 yaml，纯 `schema_version` 补丁），未碰
  `lab/models/` 下任何 checkpoint 字节。
- 抽查一个 merge kind 文件（`AGENTS.md`）：哨兵块外的"项目自定义区"在 sync 前后原样保留
  （本 case 该区域本就是空的占位注释，未见破坏）。

**结论：T-G5-4(A) 通过。** project/scaffold/merge/generated 分类没有覆盖下游自有内容；仅有的
project 层改动全部来自显式、独立、非「sync 覆盖」的合法动作。

## Stop condition

未触发任何 blocking 情况；未发现需要阻断并回 issue 的新缺陷。全部 T-ID（A 侧）通过。

发现的两处非阻断观察（均不新开票，理由见上文对应小节）：

1. `.template-sync-receipt.json` 默认落盘路径与 `check-agent-harness.py` 根目录白名单不一致
   （产生 1 条 WARN，不影响 governance 判定）。
2. 本 v1.1.0 下游自带的旧版 `scripts/template-sync.py`（事务化重写前）本身有「验证前写版本」的
   真实缺陷——但这是 v1.1.0 之后、本次 #60-63 之前就已经在上游修复的历史问题（`3bb5a6b` 等），
   不属于本轮范围，仅作为「为什么要先引导 template-sync.py 自身」的背景记录。

## 给 B（测试者）的交接说明

- **更新后的 worktree** 就是这个分支 `test/g5-elf-replay-r2`，已 push 到
  `origin/test/g5-elf-replay-r2`（同名远端分支，非 `main`）。
- 当前状态：`.template.toml` version = `v1.3.8`，`.template-sync-receipt.json`（root）是最后一次
  真实 apply 的 receipt，`result=pass`。
- 期望 B 独立验的三件事（A 不代为下结论）：
  1. **G1 门禁全绿**：直接跑 `python scripts/validate-governance.py`（A 已在 apply 后跑过一次
     `OK`，但 receipt/init 之后 B 应自己重跑一次新鲜验证，不要信任 A 的旧输出）。
  2. **G3 抽测**：`scripts/ANATOMY.md` 提到的 production-path smoke（如
     `lab/evals/template-sync/run-template-sync-smoke.py`）B 自行决定要不要跑；A 未跑这个
     （不在 A 的 T-ID 范围内）。
  3. **幂等复跑**：对已追平到 v1.3.8 的下游立即重跑
     `python scripts/template-sync.py --from <上游路径>` 应该是真正 no-op（TS-9：
     `result=pass`、版本不动、`apply_changed` 为空）——A 没有为了保持 worktree "干净待验" 而
     提前替 B 跑这个复验，留给 B 独立确认。
- 本次同步涉及的**上游 exact commit**：`cdba8bb506492e416f4e1d2c30e62cae43491dfd`（工作树 clean，
  非 dirty）；`content_digest` 见 receipt 的 `source.content_digest`。
- 若 B 需要复现 A 的每一步，本文件已含全部命令与关键输出；原始完整 log
  （dry-run/两次 apply/两次 init）留在本 session 的 `/tmp/g5-*.log`，**未随分支提交**（会话级
  临时产物，不是仓库内容）。
