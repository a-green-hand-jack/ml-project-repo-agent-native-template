# #75 缺口① TS-12 独立复核（PR #77）

- 复核官：师爷·审·typed传播（独立 verifier，与 writer 干将·修·typed传播分离作业）
- 对象：commit `2b72df0`（fix(#75): TS-12 typed-relation frontmatter 加法式传播）
- 依据：`plans/20260717-75-merge-frontmatter-propagation.zh.md`（方案 ①b，approved）
- 方法：先独立读 plan doc + `scripts/template-sync.py`/`scripts/CONTRACT.md`/
  `.agent/anatomy-protocol.md`/`.agent/template-versioning-policy.md`/smoke 套件形成判断，
  再造两组**独立于 writer smoke test** 的隔离 fixture（`/tmp/elf-verify-75/`，用后即弃，
  未污染 standing ELF case / 真实注册表）验证核心断言。未读、未采信
  `memory/branches/75-typed-relation-impl.md` 的过程叙述。

## 1. ELF replay strict 转绿独立复现 — CONFIRMED

隔离 fixture（`/tmp/elf-verify-75/{up,down}`）：模拟 v1.0.0 下游根 `ANATOMY.md`（merge kind）
frontmatter 无 `children:` 字段，而下游已有的 `scripts/ANATOMY.md` 声明 `parent: ANATOMY.md`
（单侧声明，制造 parent-child-bidirectional 缺口）；上游 v1.1.0 根 `ANATOMY.md` frontmatter
新增 `children: [scripts/ANATOMY.md]`。

- 追平前：`python scripts/check-anatomy-drift.py --strict` → **FAIL**（
  `rule=parent-child-bidirectional violation=声明 parent=ANATOMY.md，但 ANATOMY.md 未在
  children 中回链本节点`，exit 1）。
- 用本分支 `template-sync.py` 跑一次 `--from <up>`：receipt `result=pass`，
  `typed_relation_sync={"applied": true, "changes": [{"path": "ANATOMY.md", "fields":
  [{"key": "children", "action": "new-field", "added": ["scripts/ANATOMY.md"]}]}]}`；
  `manifest.unexpected=[]`、`content_mismatches=[]`、`missing=[]`。
- 追平后：`check-anatomy-drift.py --strict` → **OK**（0 governance 发现）。**FAIL→OK 转绿
  独立复现成立**。
- 幂等：同参数立即重跑，`计划：... typed relation 追平 0`，receipt
  `typed_relation_sync=null`，`result=pass`——真正 no-op。
- TS-3 未受影响的旁证：追平后 `ANATOMY.md` 里 `ROOT HEAD v1.0.0 (downstream custom)` /
  `ROOT TAIL v1.0.0 (downstream custom, block outside sentinel)`（哨兵块外的下游自定义内容）
  逐字节原样保留，哨兵块内容正常换成上游新版本（`UPSTREAM SKELETON v1.1.0`）。

## 2. Union 语义 + 非 typed 字段/body 不动 — CONFIRMED

第二组独立 fixture（scaffold 场景，`/tmp/elf-verify-75/union/{up,down}`）：下游 `scaf.md`
已声明 `parent: downstream-root.md`、自定义非 typed 字段 `owner_note:`、`children:
[down-only-child.md]`、`contracts: [{component: shared-comp, owner: downstream-owner.md}]`、
`related_files: [downstream-only-note.md]`；上游声明不同的 `parent`、`children` 含两条
upstream-only 条目、`contracts` 里 `shared-comp` 用不同 owner + 新增 `new-comp`、不同的
`related_files`。追平后逐项核对：

- **scalar 语义**：`parent` 仍是 `downstream-root.md`（下游已声明未被上游覆盖）——负例成立。
- **list union 只增不删**：`children` = `down-only-child.md`（下游原有）∪
  `up-child-a.md`/`up-child-b.md`（上游新增），无丢失无覆盖。
- **contracts 负例**：`shared-comp` owner 仍是 `downstream-owner.md`（下游自定义值**未被**
  上游的 `upstream-owner.md` 覆盖）；`new-comp`（上游独有）被正确追加。
- **非 typed 字段不动**：`owner_note:`（自定义顶层键，夹在 typed 字段之间）与
  `related_files:`（仍是下游原值 `downstream-only-note.md`，未与上游值合并）逐字节未变——
  证明 TS-12 只认 `parent`/`children`/`contracts`/`contract_for` 四个字段，不误伤相邻/其余
  frontmatter 键。
- **body/哨兵块不动**：scaffold 主动作对已存在文件本就是 keep（TS-3/TS-11 既有语义），
  `DOWN HEAD (custom)` / `OLD SCAFFOLD CONTENT` / `DOWN TAIL (custom)` 全部原样，TS-12 未
  touch 任何 body 字节。
- receipt `typed_relation_sync.changes` 精确报告了实际改动（`children.append` 两条、
  `contracts.append` 一条 new-comp），未报告 `parent`（因为下游已声明、无需改动）——如实、
  不多报不少报。

## 3. TS-3 未弱化 — CONFIRMED

`git diff c681a18 2b72df0 -- scripts/CONTRACT.md`：TS-3 行（`scripts/CONTRACT.md:46`，
five-path-classes，"merge 文件只替换 `template:begin/end` 哨兵块内，块外内容保留"）字符级
未改一字；本次 diff 只新增独立 TS-12 表格行（`scripts/CONTRACT.md:55`）与
`related_files:` 索引里补 `check-anatomy-drift.py`/`anatomy-protocol.md` 两条引用。
`kind=framework` 在 `TYPED_RELATION_KINDS = frozenset({"merge", "scaffold"})`
（`scripts/template-sync.py:60`）被正确排除，且注释说明理由（整体字节覆盖已含 frontmatter，
重复计算是空 diff）——与 CONTRACT.md TS-12 措辞一致。

## 4. Plan 状态 — CONFIRMED（一处非阻断观察）

`memory/doc-lifecycle.yaml` 该条目 `status: approved`，`approval:` 字段完整记录 human
2026-07-17 经都督·统·治理路线批准方案 ①b 的四点决策，provenance 合理。**非阻断观察**：plan
doc 任务树最后一条「移交 worktree-pr-flow 另开分支实现」仍是 `[ ]` 未勾选，doc-lifecycle
状态也未从 `approved` 推进到 `implementing`，但实现事实上已经完成（commit `2b72df0`、PR
#77）——这是收尾时该同步的文档状态，不影响本次代码正确性判断，建议 merge 前顺手补上。

## 5. 门禁独立复跑 — 全绿

- `python scripts/validate-governance.py --strict` → `OK — 0 error(s), 0 warning(s)`。
- `python lab/evals/template-sync/run-template-sync-smoke.py`（含新增
  `check_typed_relation_propagation`）→ `OK`（19 组场景含 TS-12 新增 5 项断言全部通过）。
- `python scripts/check-anatomy-drift.py --self-test` → 16/16 `PASS`，未受 TS-12 影响。

## 总裁决：APPROVE

TS-12 实现与 plan doc ①b 逐条一致：ELF replay strict 转绿独立复现成立、union 语义（只增
不删）与 scalar「下游优先」语义均通过独立负例验证、非 typed 字段与 body/哨兵块逐字节不变、
TS-3 措辞未被触碰、门禁独立复跑全绿。仅一处文档状态收尾的非阻断观察（doc-lifecycle 未推进
到 implementing），不影响 APPROVE。
