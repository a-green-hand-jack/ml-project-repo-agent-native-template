# 分支状态：elf-replay-sync-v14rc（Agent A / 更新者）

> #52 系统测试 G5（issue #58）Agent A 侧交付记录。B 不应读本文件的过程细节——只需要本分支
> 更新后的 worktree 本身；本文件是写给人类 review 与 mailbox 摘要的证据索引。

## 角色边界

本分支只做「更新」（T-G5-1..T-G5-4 的 A 侧部分）。T-G5-4 的 B 侧、T-G5-5/6/7（G1 门禁复核、
G3 抽测、幂等重跑）由独立 Agent B 在 fresh session 里完成，不在本分支范围内。

## 起点

- 分支：`elf-replay-sync-v14rc`，base = `worktree-case+elf-template-replay` @ `4f1a9ec`。
- 上游同步目标：本机 `/home/user/Projects/ml-project-repo-agent-native-template` checkout（与
  `origin/main`/本 repo 的 local `main` 完全一致，tip `2eaf024`）。

## T-G5-1：sync 前置检查 + 版本 diff 报告

**发现 1（阻塞性，已开 bug [#60](../../issues/60)）**：case 从未有过 `.template.toml`。检索
`scripts/adopt-existing-repo.py`（discover/baseline/scaffold/normalize/prove 五阶段全文）确认它
从不写 `.template.toml`，但 `template-sync.py` 报错文案又指向"首次采用请走 adopt-existing-repo"
——这条补救路径实际走不通。为了能继续测试，我在本分支（非 case 分支本体）手工创建了
`.template.toml`：

```toml
[template]
origin = "a-green-hand-jack/ml-project-repo-agent-native-template"
version = "v1.1.0"
```

`version` 取自 case 分支当时 `VERSION` 文件的值（`v1.1.0`，来自其祖先 commit `1c1f23b`
"chore(release): v1.1.0 (MINOR)" 通过 `Merge branch main` 带入）——`VERSION` 本身在
`template-manifest.toml` 里是 `framework` kind，忠实反映"这个下游最后一次真正对齐到的上游版本"。

**版本 diff**（`python scripts/template-sync.py --from <upstream> --dry-run`，完整 log 见下方
"证据文件"）：

```
[template-sync] 下游 v1.1.0 → 上游 v1.3.8（跨 MINOR）
计划：覆盖(framework/merge) 53 · 新建 38 · 保护(project) 233 · scaffold 保留 3
WARN 未分类(补 template-manifest.toml): CONTRACT.md
```

跨 MINOR，不需要 `--allow-major`。

**发现 2（低优先级，已开 bug [#62](../../issues/62)）**：根级 `CONTRACT.md` 在
`template-manifest.toml` 里没有任何规则匹配，每次 sync 都会 WARN 但从未被同步给任何下游。

## T-G5-2：注入可控失败，验证 partial-failure receipt

用了两组独立证据（一组"自然发生"、一组"人为注入"，互补覆盖 TS-2/TS-6/TS-7/TS-8）：

### 证据 A —— 真实首次 sync 尝试（非人为构造，天然复现）

在完成 `.template.toml` 补写后，第一次真实（非 `--dry-run`）跑
`python scripts/template-sync.py --from <upstream> --receipt <path>` 时，**天然**（未故意构造）
触发了失败：`apply` 干净落地（`missing=[]`、`unexpected=[]`），`generated_rebuild` 阶段
`gen_status="ok"` 但 `generated.content_mismatches=[".codex/config.toml",
".codex/rules/default.rules"]`（详见 T-G5-3 与 bug [#61](../../issues/61)），导致
`generated_ok=False` → `version_ok=False`：

```json
{
  "result": "partial",
  "version_advanced": false,
  "committed_version": "v1.1.0",
  "stages": {"apply": "ok", "generated_rebuild": "ok", "validate": "fail", "commit_version": "skipped"},
  "failure": {"stage": "generated_rebuild", "detail": "gen-content-mismatch:.codex/config.toml; gen-content-mismatch:.codex/rules/default.rules", "version_kept": "v1.1.0", "rerun_command": "..."}
}
```

`.template.toml` 版本确认保持 `v1.1.0`（未推进）；receipt 含完整 `touched_paths`（87 个文件，
证明这是"半同步态"而非"零动作"，故 `result=partial` 而非 `fail`，符合 TS-7 定义）；
`rerun_command` 字段可直接复制重跑。**没有做还原**——这组文件改动本身就是合法的框架层追平，
后续被 T-G5-3 复用，不是需要撤销的"注入破坏"。

### 证据 B —— 人为注入 MAJOR 无 --allow-major（TS-2 严格 pre-write no-op）

临时把 `.template.toml` 的 `version` 改成 `v0.5.0`（跨 upstream `v1.3.8` 的 MAJOR 边界），不带
`--allow-major` 跑：

```
[template-sync] 下游 v0.5.0 → 上游 v1.3.8（跨 MAJOR）
STOP：这是 MAJOR 追平，定义上需人工 reconcile（见 template-versioning-policy）。
exit code = 2
```

验证：
- `git status --short` 的 md5 在跑前/跑后完全一致（零文件写入，包括零 receipt 文件——
  `/tmp/tg5-evidence/receipt-major-gate.json` 确认不存在）。
- `.template.toml` 内容跑后仍是我注入的 `v0.5.0`（脚本本身没有触碰它——STOP 发生在任何写动作
  之前）。

**已还原**：跑完立即把 `.template.toml` 改回 `v1.1.0`（`cp` 自备份文件恢复，非重新计算）。

## T-G5-3：真实执行 sync 追平主仓 main

在证据 A 的基础上（`.template.toml` 已是 `v1.1.0`、大部分框架文件已落地）重跑一次真实 sync
（`--receipt /tmp/tg5-evidence/receipt-real-sync.json`），得到最终 receipt：

```
result: "fail"（因为这次没有新增写入——applied.written 为空，按 TS-7 定义
         "干净失败/跳过验收：已改过文件→partial；否则→fail"，本轮属于后者）
version_advanced: false, committed_version: "v1.1.0"
stages: {preflight: ok, plan: ok, apply: ok, generated_rebuild: ok, validate: fail, commit_version: skipped}
manifest.missing: [], manifest.unexpected: []
classification: framework=150, project=233, scaffold=3, merge=8, unclassified=[CONTRACT.md]
generated.content_mismatches: [".codex/config.toml", ".codex/rules/default.rules"]
```

**结论（如实报告，不粉饰）**：`.template.toml` 的版本锚点**没有**推进到 `v1.3.8`——这是
`template-sync.py` 严格遵守 TS-6（validate-before-commit）的正确行为，不是 bug。阻塞版本推进的
是两类独立、都已证据化开票的根因：

1. **模板侧缺陷**（[#61](../../issues/61)，高优先级）：`.codex/config.toml` /
   `.codex/rules/default.rules` 被分类成 `generated` 但从未被 `sync-codex-adapters.py`
   实际重建（`generated.actual_changed=[]` 实测证实），导致任何字节差异都无法通过生成器消除，
   永久卡住 `generated_ok`。
2. **下游自身数据债**（不属于模板缺陷，case 自己的证据链登记不完整，预期内——case 内容早于
   `validate-experiment-state.py`/`check-provenance-chain.py`/`check-doc-lifecycle.py`
   这几个较新校验器）：`memory/doc-lifecycle.yaml` 缺失、`lab/research/*.yaml` 缺
   `schema_version`、多条 run 记录缺 `approved_by`/`approved_at`/`run_summary` 位置等。这些是
   `project` kind、`template-sync` 从未也不该触碰的内容，**修复责任在 case 自己的数据维护，
   不在模板**，不开 bug，不由本分支代为回填（超出 Agent A 的"更新"授权，属于研究数据治理）。

**框架层追平本身是完整、干净的**：`missing=[]`、`unexpected=[]`，150 个 framework 文件 + 8 个
merge 文件 + 3 个 scaffold 全部按合同落地，无一处遗漏或越界写入。工作树里的 66 处修改 + 34
个新增文件（`git status --short`）已保留在本分支上，供 Agent B 直接在"已应用最新框架层字节、
但 `.template.toml` 版本诚实停留在 v1.1.0"的真实半同步态上开展 T-G5-5/6/7。

## T-G5-4（A 侧）：五类分类未覆盖下游内容

抽了 6 个（超过要求的 ≥5）不同目录下的下游自有文件，sync 前后 `git diff --stat HEAD -- <path>`
全部零输出（零改动）：

| 路径 | kind | 结果 |
| --- | --- | --- |
| `lab/research/claims.yaml` | project | 零改动 |
| `memory/current-status.md` | project | 零改动 |
| `PROJECT.md` | project | 零改动 |
| `human/reviews/results/elf-case-smoke-result.md` | project | 零改动 |
| `lab/docs/research-narrative/PAPER.md` | project | 零改动 |
| `deliverables/paper/main.tex` | project | 零改动 |

另确认三条硬边界路径（`lab/data/**`、`lab/runs/**`、`lab/models/**`、`lab/infra/private/**`）
在 `git status --short` 里零命中——sync 全程未产生任何越界写入。`README.md`（scaffold，已存在）
同样零改动，符合"已存在则保留"语义。B 侧（跨 project/scaffold/merge/generated 的独立复核，
不读本文件）留给 Agent B。

## 发现的缺陷（已开独立 bug issue，未在本分支顺手修模板）

- [#60](../../issues/60) `adopt-existing-repo` 从不写 `.template.toml`，新下游首次采用永远走
  不通 template-sync（阻塞 T-G5-1，已手工绕过）。
- [#61](../../issues/61) `.codex/config.toml`/`default.rules` 分类为 `generated` 但从未被生成器
  重建，永久阻断 TS-6 版本推进（高优先级，直接导致 T-G5-3 无法 `result=pass`）。
- [#62](../../issues/62) 根 `CONTRACT.md` 在 `template-manifest.toml` 里未分类，永不同步给下游
  （低优先级）。

## 证据文件（已归档进本分支 `memory/branches/elf-replay-sync-A-evidence/`）

- `t-g5-1-dryrun.log` —— T-G5-1 dry-run 版本 diff 报告。
- `t-g5-2-attempt1-stdout.log` + `t-g5-2-receipt-attempt1.json` —— T-G5-2 证据 A（真实首次 sync
  天然触发的 partial-failure receipt）。
- `t-g5-2-major-gate-stdout.log` —— T-G5-2 证据 B（人为注入 MAJOR 无 `--allow-major`，
  `receipt-major-gate.json` 按合同确实未落盘，故无此文件本身就是证据）。
- `t-g5-3-real-sync-stdout.log` + `t-g5-3-receipt-real-sync.json` —— T-G5-3 最终 receipt +
  exact manifest。

case 原本的旧版 `template-sync.py`（无 receipt/TS-1..9 能力，佐证"这个 case 起点确实是
pre-CONTRACT 工具"）未归档字节，仅在本文件与 bug [#60](../../issues/60) 里文字记录其行为差异；
如需原始字节可从 `worktree-case+elf-template-replay` 分支 `4f1a9ec` 的 `scripts/template-sync.py`
直接取得（未改动，仍是 case 分支本体的原始版本）。

## 给 Agent B 的交接状态

- 本分支工作树已应用真实 sync 的框架层结果（详见上文），`.template.toml` 诚实停留在
  `v1.1.0`（版本未推进，原因见上）。
- G1 门禁复核（T-G5-5）预期会看到 validate-governance FAIL——不是回归，是上面两类已知根因
  （#61 模板缺陷 + case 自身数据债）共同作用的结果，B 应独立验证并各自归因，不应假设"A 没测过"。
- G3 抽测（T-G5-6）：`agent_name_set.py`、`agent_identity_hook.py`、`bootstrap-project`/`spawn`
  skill 等这批新能力，在本分支上是**首次**出现（case 原本没有），是很好的抽测对象。
- T-G5-7 幂等重跑：由于版本未推进，"幂等"的语义需要 B 自己判断口径（是"再跑一次 sync 结果不变"
  还是"等 #61 修完、真正 pass 后再测幂等"）——本分支不代为下结论。
