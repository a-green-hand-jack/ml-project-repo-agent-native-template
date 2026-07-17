# fix/74-75-qualification-strict-gaps 分支报告

> Provenance：本文由执行官 **干将·修·门禁缺口**（sonnet-5，同 worktree in-place 修复）撰写。
> 任务：修 #74（G4 runner UNAVAILABLE 死代码）+ #75（G5 strict 两缺口，块 A/B/C 对应关系见下）。

## 总结

- 块 A（#74）：**已修复**，装 paseo / 剥 PATH 模拟无 paseo 两种情形均验证，T-G4-6 不再误判 FAIL。
- 块 B（#75 缺口②，receipt 不在根白名单）：**已修复**，`--strict` 全绿，新增回归覆盖。
- 块 C（#75 缺口①，merge frontmatter schema 不传播）：**调查完毕，NEEDS-HUMAN-DECISION**——
  未改代码。见下方选项分析与推荐。

---

## 块 A —— #74：G4 scenario runner UNAVAILABLE 死代码

### 缺陷复述

`lab/evals/control-plane/run-g4-scenario.py`：
1. `outcome(unavailable=...)` 全文件零赋值——文档承诺的 UNAVAILABLE 降级语义是死代码。
2. T-G4-6 负例分支 a（`agent-status.py` 不带 `--no-paseo`、验证未登记 `paseo_id` 的 agent presence
   降级为 `"-"`）隐含前提是「本机真装了 paseo CLI」。在没装 paseo 的机器上，
   `scripts/agent-status.py` 的 `paseo_live_ids()`（`shutil.which("paseo")` 为 `None` 时直接返回
   `None`）会让全部 presence 整体降级成 `"unknown(no-paseo)"`，与断言期望的 `"-"` 矛盾 → 误判
   FAIL，而不是优雅降级。

### 修法

`t_g4_6()` 的负例分支 a 先用 `shutil.which("paseo")` 探测本机是否真装了 paseo：
- 装了 → 按原断言要求 `paseo_presence == "-"`。
- 没装 → 该分支的证明前提本身不成立，标 `outcome(unavailable=True)`（真正接线既有死代码），
  断言改期望 `"unknown(no-paseo)"`（与该机器上分支 b 的证据同构，不伪造 PASS）。

`make_result()` 原有的 `if positive.get("unavailable") or negative.get("unavailable"): status =
"UNAVAILABLE"` 判定链路本就存在（此前一直死代码），本次是首次真实触发。

### 验证

| 情形 | 命令 | T-G4-6 结果 |
| --- | --- | --- |
| 本机装了 paseo（`/home/user/.local/bin/paseo`） | `uv run python3 lab/evals/control-plane/run-g4-scenario.py` | `PASS`，全体 7/7 |
| 剥 PATH 模拟无 paseo CLI（`env -i PATH="/usr/bin:/bin" ...`） | 同上 | `UNAVAILABLE`（不是 FAIL），全体 6/7、self-test 仍全绿 |

两种情形下 T-G4-6 都不再误判 FAIL，符合任务验收要求。`report-g4.{json,md}` 已用「装了 paseo」
情形重新生成为最新证据（commit `bf04236`）。

---

## 块 B —— #75 缺口②：receipt 不在根白名单

### 缺陷复述

`scripts/template-sync.py` 的 `DEFAULT_RECEIPT = DOWNSTREAM / ".template-sync-receipt.json"`
默认把 sync receipt 写在下游根目录，但 `scripts/check-agent-harness.py` 的 `ROOT_WHITELIST`
没收录该文件名 → 任何下游用默认路径跑一次 `template-sync.py --commit`，`--strict` harness
门禁必挂（两个模板组件自相矛盾）。

### 修法

把 `.template-sync-receipt.json` 加进 `ROOT_WHITELIST`，归入既有「模板版本 / 上下游同步锚点」
注释分组（与 `VERSION`/`CHANGELOG.md`/`template-manifest.toml`/`.template.toml` 同类）。

### 测试

`check-agent-harness.py` 自身没有 `--self-test` CLI（是只读静态校验脚本，见
`scripts/CLAUDE.md`），它唯一的 fixture-based 回归覆盖是
`lab/evals/qualification/run-qualification.py` 的 `T-G1-5`。已扩展该 T-ID：

- 正例新增：fixture 根目录放一份 `.template-sync-receipt.json`，断言 `--strict` 仍 `exit 0`
  且输出里不出现该文件名（证明不再被误判污染）。
- 负例新增第二个注入点（与原有「删 hook 脚本」注入并存）：fixture 根目录额外放一个真正未知的
  探针文件 `_qual_unknown_root_probe.md`，断言仍会触发「根目录疑似污染」告警——证明
  `ROOT_WHITELIST` 加了 receipt 后**没有被顺手改宽**，真实污染依旧能拦。

### 验证结果

- `T-G1-5` 单独跑：`PASS`（修复前跑同一 fixture 会在正例分支得到
  `WARN 根目录疑似污染（不在白名单）：.template-sync-receipt.json` → `FAIL`，已用未提交状态
  复现过一次，见 commit 历史前的验证记录）。
- `python scripts/check-agent-harness.py --strict`：`OK — 0 error(s), 0 warning(s)`。
- `uv run --with pyyaml python3 lab/evals/qualification/run-qualification.py --group g1`：
  `9/9 PASS`（`report-g1.{json,md}` 已重新生成，commit `c81641c`）。

---

## 块 C —— #75 缺口①：merge 分类锚文件 frontmatter schema 不传播

### 结论：NEEDS-HUMAN-DECISION（未改代码）

### 背景澄清（重要）

本 repo（`ml-project-repo-agent-native-template`）**本身就是上游模板**，不是下游消费者
（`git remote -v` 确认；`.template.toml` 在本 repo 不存在）。本 repo 根 `ANATOMY.md` 的
frontmatter 已经是「正确的最终态」（`children: [scripts/ANATOMY.md]` 与
`scripts/ANATOMY.md` 的 `parent: ANATOMY.md` 双向声明齐全，`validate-governance.py --strict`
在本 repo 完全 OK）。缺口只在「下游 repo 用 `merge` 分类同步这个新增 frontmatter 键」时才会
触发——本 repo 无法从这里直接修复某个具体下游的字节，只能修 `template-sync.py`/
`check-anatomy-drift.py`/doctrine 本身，让**未来**的同步行为正确。

### 调查发现：这不是一个全新的开放问题——高层设计已有既定答案，但从未被操作化

`.agent/template-versioning-policy.md:53-73`「混合文件的哨兵约定（merge kind）」一节，**已经
明文写死**这个场景是已知边界：

> 已知边界：frontmatter 在块外，不随 sync 更新（哨兵不能放 frontmatter 前，否则破坏 `^---`
> 解析）。frontmatter 的结构性变更需人工同步或把该文件改判为 framework。

`scripts/CONTRACT.md` 的 **TS-3**（five-path-classes）把「merge 文件只替换
`template:begin/end` 哨兵块内，块外内容保留」列为**正式锁定的可观察合同**，其页脚明文：
「弱化/删除 TS-1..TS-11 任一规则……默认视为实现 bug，不得为让测试变绿而改弱本文件；改变承诺
需 human 在 issue/PR 明确批注批准」。

也就是说：**选项①（template-sync 对 merge 文件也合并 frontmatter 结构键）直接触碰一个需要
human 显式批准才能改的锁定合同（TS-3）**，不是一个可以在本分支「顺手」实现的改动。

### 四个候选选项评估

| 选项 | 说明 | 评估 |
| --- | --- | --- |
| ① sync 时合并 merge 文件的 frontmatter 结构键（保留下游 body） | 直接改 TS-3 锁定合同，需 human 在 issue/PR 明确批准；且「合并」本身有语义歧义——`children:` 的**值**是仓库特定的（不同下游子目录结构不同），机械 union 只在「双方都是 framework 路径」时安全，需要更细的规则设计，不是一行 patch | 需要设计 + 需要合同变更批准，不可直接实现 |
| ② 把 ANATOMY.md 从 merge 改判 framework 全覆盖 | 会连累 body 里下游自定义的「分层地图」表格（各下游实际子目录结构不同，这部分内容天然不能被上游覆盖），blast radius 过大 | **不推荐**，基本排除 |
| ③ checker 端不再要求显式 `children:` frontmatter，而是反向扫描全仓库 `parent:` 声明来派生 | 消除传播需求（子节点单侧声明即可生效），但改变了 `.agent/anatomy-protocol.md` 明文记载的「双向声明」设计意图（该文档称这是故意的 opt-in 治理边界，父节点的显式 children 声明起到「知情确认」作用，改成反向派生会移除这层显式确认） | 需要改另一份 doctrine（anatomy-protocol.md）的既定设计，同样是设计变更，不是纯 bug 修复 |
| ④ 文档化下游显式迁移步骤（现状） | `.agent/template-versioning-policy.md` 已经这样写了——但目前是**纯 prose，从未被操作化**：sync 跑完 receipt 可以是 `result=pass`，却对这个已知边界完全沉默，下游不会主动意识到需要手工同步 frontmatter | 已经是「官方立场」，但当前实现是沉默的，构成 #75 抱怨的「自相矛盾」本身 |

### 推荐（供 human 决策，非最终结论）

不建议现在实现 ①/③（都需要单独的 human 批准 + 更细致的设计），也排除②。**推荐的最小后续
动作**是把 ④ 从「纯文档」升级成「主动信号」：`template-sync.py` 在 `plan_sync()` 对 `merge`
分类文件额外做一次 frontmatter 顶层 key 的 diff（上游 vs 下游），若上游新增了下游没有的顶层
key，在 dry-run/apply 输出与 receipt `warnings` 里显式提示「frontmatter 结构性变更，需人工
同步」，指向 `.agent/template-versioning-policy.md` 的既有说明——**不改写任何字节**，只是把
已经存在但沉默的已知边界变成可观察信号。这本身仍然是一处新增行为，需要新的 self-test 证据
（本 repo 的 evidence-chain doctrine 要求），且可能牵涉 receipt schema/TS 表新增一条（TS-12），
超出本分支「块 A/B 直接修」的范围，故未在本分支实现，留给 human 决定是否批准并开新 issue 承接。

### 未改动的文件

块 C 未产生任何代码改动；上表分析基于对 `scripts/template-sync.py`、
`scripts/check-anatomy-drift.py`、`.agent/template-versioning-policy.md`、
`.agent/anatomy-protocol.md`、`scripts/CONTRACT.md` 的只读调查。

---

## 验证命令汇总

```bash
# 块 A
uv run python3 lab/evals/control-plane/run-g4-scenario.py                      # 装 paseo：7/7 PASS
env -i PATH="/usr/bin:/bin" HOME="$HOME" python3 lab/evals/control-plane/run-g4-scenario.py  # 剥 PATH：6/7，T-G4-6=UNAVAILABLE

# 块 B
python3 scripts/check-agent-harness.py --strict                                 # OK
uv run --with pyyaml python3 lab/evals/qualification/run-qualification.py --group g1  # 9/9 PASS

# 全量
uv run --with pyyaml python3 scripts/validate-governance.py --strict            # OK — 0 error(s), 0 warning(s)
python3 scripts/check-anatomy-drift.py --self-test                              # OK，16/16
```

## 关联

- #74（父 #52 P7，源 #57/PR #72，发现于 #56/PR #73）
- #75（父 #52 P5，源 #58，round1 前例 #60–#63）
