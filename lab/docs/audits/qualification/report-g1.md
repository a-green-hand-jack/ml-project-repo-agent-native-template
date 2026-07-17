# Qualification report — group=g1

- 被测 commit：`d8e05f62acb5ce3d746d4aa4969ec5a5ef4d1953`
- 生成时间：2026-07-17T11:29:22.667089+00:00
- 生成时工作树是否 dirty：False
- 结果：9/9 PASS（复用 self-test 5 项，自建 fixture 4 项）

| T-ID | validator | mode | status | notes |
| --- | --- | --- | --- | --- |
| T-G1-1 | `scripts/validate-governance.py` | custom-fixture | PASS | 负例注入 check_gitignore()：.gitignore 不再提及 lab/data 保护 token，触发子门（本文件自身治理规则，非 subcheck 子进程）。 |
| T-G1-2 | `scripts/check-anatomy-drift.py` | self-test-reuse | PASS | 复用 --self-test：内嵌 governed_components 断链(governed-index-missing) / orphan(governed-index-orphan) / owner 不一致(governed-index-mismatch) 三类对抗 fixture （scripts/check-anatomy-drift.py 源码 620-640 行区间），逐条 PASS/FAIL 均无条件打印。 |
| T-G1-3 | `scripts/check-doc-lifecycle.py` | self-test-reuse | PASS | 复用 --self-test：内嵌"锚点/注册表状态矛盾被报错"与"跃迁 approved 缺段"两类场景（对应「非法状态转移」——doc-lifecycle 校验的是锚点/注册表一致性 + 跃迁时字段齐全，不是像 validate-experiment-state 那样的显式有向状态机图，如实标注该差异，不过度声称）。 |
| T-G1-4 | `scripts/check-same-commit.py` | custom-fixture | PASS | fixture 用 git clone（需要真实 git 历史支持 --staged diff）；正例证明合规改动放行，负例证明结构改动未同步更新 anatomy 会被拦。 |
| T-G1-5 | `scripts/check-agent-harness.py` | custom-fixture | PASS | 正例额外覆盖 issue #75 缺口②回归：根目录放一份 template-sync.py 默认路径落盘的 .template-sync-receipt.json，证明 --strict 不再误判根污染。负例删一处被 .claude/settings.json hooks 声明引用的脚本文件（触发 check_settings() 的 hook 存在性校验）同时在根目录放一个真正未知文件，证明 ROOT_WHITELIST 加了 receipt 后依旧能拦真污染，没有被顺手改宽。 |
| T-G1-6 | `scripts/check-capability-catalog.py` | self-test-reuse | PASS | 复用 --self-test：16 个 catalog 对抗场景含显式 "missing"（能力未登记，scripts/check-capability-catalog.py:459/379）用例；该 self-test 只在失败时打印case 标签，正常通过时静默——exit 0 + 无 FAIL 行即为全部 16+5 场景符合预期的证据。 |
| T-G1-7 | `scripts/check-provenance-chain.py` | self-test-reuse | PASS | 复用 --self-test：7+ 个悬空引用负例（evidence/claim/dataset/checkpoint/review/figure，scripts/check-provenance-chain.py:1712-2001 区间的 negative-dangling-* 用例族）；_run_case 只在失败时 append，正常通过时静默。 |
| T-G1-8 | `scripts/validate-experiment-state.py` | self-test-reuse | PASS | 复用 --self-test：显式非法状态转换用例（run-skip-approval「planned → running」跳过 approved、run-zombie「done → running」回转，命中 scripts/validate-experiment-state.py:233 的状态机拒绝规则）；expect() 只在失败时打印，正常通过时静默。 |
| T-G1-9 | `scripts/check-outcome-ledger-schema.py` | custom-fixture | PASS | check-outcome-ledger-schema.py 无独立 --self-test CLI 开关，但正常 main() 每次都会用内置合成记录对 schema 拒绝逻辑做内部负向断言（check_negative_schema_rejection）——clean fixture 正例 OK 本身已经内在验证过该负向逻辑未被破坏；本 T-ID 额外做一次外部注入（破坏真实 fixture ledger 文件字节），证明对真实文件的 schema 违规同样可定位报错。 |

## 逐项证据

### T-G1-1 — PASS

- validator: `scripts/validate-governance.py`（mode=custom-fixture, reused_self_test=False）
- notes: 负例注入 check_gitignore()：.gitignore 不再提及 lab/data 保护 token，触发子门（本文件自身治理规则，非 subcheck 子进程）。
- positive: exit=0 ok=True
```
PASS    schema_version：lab/artifacts/result-index.yaml = 1
PASS    schema_version：lab/artifacts/table-index.yaml = 1
PASS    schema_version：lab/artifacts/figure-index.yaml = 1
PASS    schema_version：lab/artifacts/trace-index.yaml = 1
PASS    schema_version：lab/artifacts/model-index.yaml = 1
PASS    schema_version：lab/models/checkpoint-index.yaml = 1
PASS    schema_version：lab/data/dataset-index.yaml = 1
PASS    schema_version：lab/research/evidence.yaml = 1
PASS    claim marker：deliverables 下暂无 marker（无 marker 的活跃交付物由 deliverables/index.md 的 marker-or-review 检查兜底）
PASS    schema_version：lab/research/regression-matrix.yaml = 1
PASS    schema_version：lab/research/release-gates.yaml = 1

[check-provenance-chain] OK — 0 fail, 0 unknown, 13 pass

=== check-capability-catalog.py ===
[check-capability-catalog] OK — 登记 46 项，0 error(s), 0 warning(s)

=== governance ===

[validate-governance] OK — 0 error(s), 0 warning(s)
```
- negative: exit=1 ok=True injection='删除 .gitignore 中全部含 lab/data 的行'
```
PASS    schema_version：lab/artifacts/table-index.yaml = 1
PASS    schema_version：lab/artifacts/figure-index.yaml = 1
PASS    schema_version：lab/artifacts/trace-index.yaml = 1
PASS    schema_version：lab/artifacts/model-index.yaml = 1
PASS    schema_version：lab/models/checkpoint-index.yaml = 1
PASS    schema_version：lab/data/dataset-index.yaml = 1
PASS    schema_version：lab/research/evidence.yaml = 1
PASS    claim marker：deliverables 下暂无 marker（无 marker 的活跃交付物由 deliverables/index.md 的 marker-or-review 检查兜底）
PASS    schema_version：lab/research/regression-matrix.yaml = 1
PASS    schema_version：lab/research/release-gates.yaml = 1

[check-provenance-chain] OK — 0 fail, 0 unknown, 13 pass

=== check-capability-catalog.py ===
[check-capability-catalog] OK — 登记 46 项，0 error(s), 0 warning(s)

=== governance ===
ERROR .gitignore 未提及受保护路径：lab/data

[validate-governance] FAIL — 1 error(s), 0 warning(s)
```

### T-G1-2 — PASS

- validator: `scripts/check-anatomy-drift.py`（mode=self-test-reuse, reused_self_test=True）
- notes: 复用 --self-test：内嵌 governed_components 断链(governed-index-missing) / orphan(governed-index-orphan) / owner 不一致(governed-index-mismatch) 三类对抗 fixture （scripts/check-anatomy-drift.py 源码 620-640 行区间），逐条 PASS/FAIL 均无条件打印。
- positive: exit=0 ok=True
```
[self-test] PASS 1 合法 root<->child + contract 双向图不产生 comp-ok 相关发现
[self-test] PASS 2 单向 parent-child 被检出
[self-test] PASS 3 单向 anatomy-contract 被检出
[self-test] PASS 4 duplicate owner 被检出
[self-test] PASS 5 orphan governed node 被检出
[self-test] PASS 6 绝对路径 target 被拒绝
[self-test] PASS 7 '..' target/escape 被拒绝
[self-test] PASS 8 duplicate relation 被检出
[self-test] PASS 9 合法 ungoverned leaf 不产生发现
[self-test] PASS 10 顶层 typed key 重复声明被检出
[self-test] PASS 11 不支持的 inline/flow shape 被检出
[self-test] PASS 12 maintenance 内 typed-key-looking prose 合法不误报
[self-test] PASS 13 root CONTRACT.md 正例 comp-ok 与真实双向声明一致，不产生 governed-index 发现
[self-test] PASS 14 governed-index-missing 被检出
[self-test] PASS 15 governed-index-mismatch 被检出
[self-test] PASS 16 governed-index-orphan 被检出
[self-test] 共 16 条 governance 发现（fixture 图）
[self-test] OK
```
- negative: n/a（见 notes 说明）

### T-G1-3 — PASS

- validator: `scripts/check-doc-lifecycle.py`（mode=self-test-reuse, reused_self_test=True）
- notes: 复用 --self-test：内嵌"锚点/注册表状态矛盾被报错"与"跃迁 approved 缺段"两类场景（对应「非法状态转移」——doc-lifecycle 校验的是锚点/注册表一致性 + 跃迁时字段齐全，不是像 validate-experiment-state 那样的显式有向状态机图，如实标注该差异，不过度声称）。
- positive: exit=0 ok=True
```
  PASS  hook 拦 Allowed paths='> TODO'
  PASS  Allowed paths='> [ ] TODO' 被 validator 报错
  PASS  hook 拦 Allowed paths='> [ ] TODO'
  PASS  Allowed paths='[TODO](#replace)' 被 validator 报错
  PASS  hook 拦 Allowed paths='[TODO](#replace)'
  PASS  Allowed paths='| |\n| --- |' 被 validator 报错
  PASS  hook 拦 Allowed paths='| |\n| --- |'
  PASS  合法 prose/code section 不误判：'- prose documents how the TODO detector was verified'
  PASS  hook 放行合法 prose/code section：'- prose documents how the TODO detector was verified'
  PASS  合法 prose/code section 不误判：'```bash'
  PASS  hook 放行合法 prose/code section：'```bash'
  PASS  合法 prose/code section 不误判：'- `python scripts/check-doc-lifecycle.py`'
  PASS  hook 放行合法 prose/code section：'- `python scripts/check-doc-lifecycle.py`'
  PASS  合法 prose/code section 不误判：'> approved scope path'
  PASS  hook 放行合法 prose/code section：'> approved scope path'
  PASS  合法 prose/code section 不误判：'[implementation](#section)'
  PASS  hook 放行合法 prose/code section：'[implementation](#section)'
  PASS  合法 prose/code section 不误判：'| Path |'
  PASS  hook 放行合法 prose/code section：'| Path |'
[check-doc-lifecycle] self-test OK — 0 failure(s)
```
- negative: n/a（见 notes 说明）

### T-G1-4 — PASS

- validator: `scripts/check-same-commit.py`（mode=custom-fixture, reused_self_test=False）
- notes: fixture 用 git clone（需要真实 git 历史支持 --staged diff）；正例证明合规改动放行，负例证明结构改动未同步更新 anatomy 会被拦。
- positive: exit=0 ok=True
```
[same-commit] OK —— 1 处结构改动，对应 anatomy 已同变更集更新
```
- negative: exit=1 ok=True injection='只 staged scripts/_qualification_probe.py（A），不更新 scripts/ANATOMY.md'
```
[same-commit] FAIL —— 结构改动未同步更新对应 ANATOMY.md：
  · 改了 scripts/_qualification_probe.py（等结构文件），但同变更集未更新 scripts/ANATOMY.md

修复：在同一 commit 里更新上述 ANATOMY.md（组件表/调用关系/状态/citation）。
见 .agent/anatomy-protocol.md 的 same-commit rule。
确属误报或本次无关结构语义：SAME_COMMIT_SKIP=1 或 git commit --no-verify。
```

### T-G1-5 — PASS

- validator: `scripts/check-agent-harness.py`（mode=custom-fixture, reused_self_test=False）
- notes: 正例额外覆盖 issue #75 缺口②回归：根目录放一份 template-sync.py 默认路径落盘的 .template-sync-receipt.json，证明 --strict 不再误判根污染。负例删一处被 .claude/settings.json hooks 声明引用的脚本文件（触发 check_settings() 的 hook 存在性校验）同时在根目录放一个真正未知文件，证明 ROOT_WHITELIST 加了 receipt 后依旧能拦真污染，没有被顺手改宽。
- positive: exit=0 ok=True
```
[check-agent-harness] OK — 0 error(s), 0 warning(s)
```
- negative: exit=1 ok=True injection='删除 .claude/hooks/subagent_report_index.py（settings.json 与 .codex/config.toml 均引用）+ 根目录放一个真正未知文件'
```
WARN  根目录疑似污染（不在白名单）：_qual_unknown_root_probe.md —— 长文/报告/实验记录不应堆在 root
WARN  DESIGN.md 能力清单过时：hooks 写 11，实际 10。更新 DESIGN.md §10 清单表（repo-doc-steward 职责）。
ERROR hook 脚本不存在：.claude/hooks/subagent_report_index.py（SubagentStop）
ERROR Codex hook 脚本不存在：.claude/hooks/subagent_report_index.py（SubagentStop）
[check-agent-harness] FAIL — 2 error(s), 2 warning(s)
```

### T-G1-6 — PASS

- validator: `scripts/check-capability-catalog.py`（mode=self-test-reuse, reused_self_test=True）
- notes: 复用 --self-test：16 个 catalog 对抗场景含显式 "missing"（能力未登记，scripts/check-capability-catalog.py:459/379）用例；该 self-test 只在失败时打印case 标签，正常通过时静默——exit 0 + 无 FAIL 行即为全部 16+5 场景符合预期的证据。
- positive: exit=0 ok=True
```
[check-capability-catalog --self-test] OK — catalog 16 + hook-resolve 5 对抗场景全部符合预期
```
- negative: n/a（见 notes 说明）

### T-G1-7 — PASS

- validator: `scripts/check-provenance-chain.py`（mode=self-test-reuse, reused_self_test=True）
- notes: 复用 --self-test：7+ 个悬空引用负例（evidence/claim/dataset/checkpoint/review/figure，scripts/check-provenance-chain.py:1712-2001 区间的 negative-dangling-* 用例族）；_run_case 只在失败时 append，正常通过时静默。
- positive: exit=0 ok=True
```
[check-provenance-chain --self-test] OK — 正负 fixture 全部符合预期
```
- negative: n/a（见 notes 说明）

### T-G1-8 — PASS

- validator: `scripts/validate-experiment-state.py`（mode=self-test-reuse, reused_self_test=True）
- notes: 复用 --self-test：显式非法状态转换用例（run-skip-approval「planned → running」跳过 approved、run-zombie「done → running」回转，命中 scripts/validate-experiment-state.py:233 的状态机拒绝规则）；expect() 只在失败时打印，正常通过时静默。
- positive: exit=0 ok=True
```
[validate-experiment-state --self-test] OK
```
- negative: n/a（见 notes 说明）

### T-G1-9 — PASS

- validator: `scripts/check-outcome-ledger-schema.py`（mode=custom-fixture, reused_self_test=False）
- notes: check-outcome-ledger-schema.py 无独立 --self-test CLI 开关，但正常 main() 每次都会用内置合成记录对 schema 拒绝逻辑做内部负向断言（check_negative_schema_rejection）——clean fixture 正例 OK 本身已经内在验证过该负向逻辑未被破坏；本 T-ID 额外做一次外部注入（破坏真实 fixture ledger 文件字节），证明对真实文件的 schema 违规同样可定位报错。
- positive: exit=0 ok=True
```
[check-outcome-ledger-schema] OK — 0 error(s), 0 warning(s)
```
- negative: exit=1 ok=True injection='截断 outcome-ledger.sample.jsonl 首行末尾字符，制造非法 JSON 记录'
```
ERROR outcome-ledger.sample.jsonl: outcome-ledger.sample.jsonl:1: invalid JSON (Unterminated string starting at: line 1 column 634 (char 633))
ERROR outcome-ledger.sample.jsonl: outcome for d-fx0001: references unknown decision_id 'd-fx0001'
ERROR fixture 完整路线统计异常：codex/gpt-5.6-terra@medium 的 impl/bounded-implementation/tier2 样本不足
ERROR frozen fixture 不应触发 degraded（fixture 或阈值漂移）
[check-outcome-ledger-schema] FAIL — 4 error(s), 0 warning(s)
```
