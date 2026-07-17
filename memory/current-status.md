# current-status.md

## 2026-07-17 #74/#75 修复收口（主 agent：都督·统·治理路线）

- **PR #76 合入（`c681a18`）**：writer 干将·修·门禁缺口 + 独立 verifier 师爷·审·门禁缺口 分离作业。
  - **块 A（#74）已修并 CONFIRMED**：`run-g4-scenario.py` 死代码 `unavailable=` 真接线——装 paseo→
    T-G4-6 PASS 7/7、剥 PATH 模拟无 paseo→T-G4-6 UNAVAILABLE（不再误判 FAIL）。**#74 关闭**。
    次要非阻断观察：UNAVAILABLE 时 runner 整体 exit 仍 1（该 runner 未接入任何 strict 门禁，不影响 CI）。
  - **块 B（#75 缺口②）已修并 CONFIRMED**：`.template-sync-receipt.json` 加入 check-agent-harness
    `ROOT_WHITELIST`（精确 membership）；独立造未知文件负例证明**白名单未被过度放宽**、g1 runner 9/9。
- **块 C（#75 缺口①：merge 分类 ANATOMY.md frontmatter 不传播）→ human 拍板「真修，走 plan」**：
  执行官调查确认它触及**锁定合同 TS-3**（merge 只换哨兵块）+ template-versioning doctrine，未擅改。
  **下一步：派 interactive-plan-writer 起草改 TS-3/anatomy 的中文 plan doc 落 `plans/` 供 human 批注**，
  收敛→批准→实现→独立 verifier。**#75 保持 open**（缺口②已修、缺口①走 plan）。
- 证据：`memory/branches/74-75-strict-gaps.md`（writer 含块 C 调查+4 方案）、`74-75-verify.md`（独立复核）。
- 两 agent + 两 worktree 归档，分支 `fix/74-75-qualification-strict-gaps` 本地+远端已删。
- **v1.4.0 剩余**：块 C plan 真修（#75 缺口①）→ **G2（#55，最后一组）** → 发版门 P8。

## 2026-07-17 G5 收口（主 agent：都督·统·治理路线）

- **#58 通过（默认门禁口径）**：G5 干净 ELF replay（P5）round2——硬分工更新者 A（干将·迁·ELF追平）
  ≠ 测试者 B（师爷·审·ELF追平）。#60–63 修复后 sync 事务**干净跑通**：版本真推进 v1.1.0→v1.3.8、
  receipt=pass、下游**默认 G1 门禁全绿**、G3 抽测 4/4、幂等零副作用、分类未覆盖下游。round1 的
  两个卡点（版本不推进 / 4validator FAIL）本轮全部转 PASS。
- **主 agent 独立核查**（不信自证 receipt）：亲自重跑门禁确认默认全绿、版本真提交为 v1.3.8；
  并独立发现 strict 缺口，与 B 独立结论一致（authoring/review 分离奏效）。
- **human 拍板以默认门禁为验收 bar → G5 过**。strict 口径浮出 **2 处真实模板缺口**转跟进 **#75**
  （非阻断）：① merge 分类锚文件 frontmatter schema 新增不随 sync 传播（ANATOMY.md 无 children:）；
  ② `.template-sync-receipt.json` 不在 check-agent-harness 根白名单。**纠正 B 一处误诊**：非
  `related_files→children` 改名（上游两字段并存），而是 merge 分类不传播 frontmatter schema。
- 证据：`memory/branches/58-g5-replay-A.md`（更新者）+ `58-g5-replay-B.md`（独立测试者，含收口纠正注）。
- 两 agent + 两 worktree 已归档，测试分支 `test/g5-elf-replay-r2` / `test/g5-elf-replay-verify`
  已删（standing ELF case `worktree-case+elf-template-replay` 保留）。两 sonnet agent 又均自切到
  bypassPermissions 模式（同 G4 观察，工作已独立核验，影响低）。
- **#52 剩余**：P1–P5、P7 全完成；仅剩 **P6 / G2**（#55，fresh 双表面 runtime，最硬）+ 发版门 P8；
  外加 **#74**（G4 driver 缺陷）、**#75**（G5 strict 缺口）v1.4.0 前修/豁免。完成度约 ~80%。

## 2026-07-17 G3 收口（主 agent：都督·统·治理路线）

- **#56 已关闭**：G3 工作流 skills/commands 端到端演练（P7，D 层）经 **PR #73**
  squash-merged（`3211825`）。writer 干将·演·工作流 + 独立 verifier 师爷·审·工作流 分离：
  8/8 T-ID 独立确认——6 CONFIRMED-PASS + T-G3-7 CONFIRMED-UNAVAILABLE-by-design（本 repo 是
  上游模板本身非下游）+ T-G3-6 PASS 含真实发现；**干跑零泄漏独立成立**（plans/doc-lifecycle/
  experiment-ledger 字节未动）；门禁独立复跑全绿。总裁决 **APPROVE**。
- 证据：`lab/docs/audits/qualification/report-g3.md`、`memory/branches/56-g3-skills.md`（writer）、
  `memory/branches/56-g3-verify.md`（独立复核，原文随 worktree 归档丢失、如实转录回 main）。
- **衍生 #74**：G3 的 pr-review 复审 G4 driver 时发现、verifier 独立坐实——
  `run-g4-scenario.py` UNAVAILABLE 降级为死代码、无 paseo CLI 机器上 T-G4-6 负例误判 FAIL。
  MINOR，不影响本轮 G4 结论（本机装了 paseo），但 v1.4.0 前应修或 human 豁免。
- 两 agent + 两 worktree 已归档，分支 `56-g3-skills` 本地+远端已删，`memory/session-tree.md`
  stale 行已更新。
- **另清理**：并发遗留 orchestrator「都督·统·P2收口」(`98b55ecc`，P2/#67 已完成) 与本 session
  共用同一 main checkout，属冲突隐患，经 human 批准已归档；现仅本 session 单一 orchestrator。
- **#52 剩余**：**P7 已全数完成（G3+G4）**；剩 **P5**（G5 干净 ELF replay，#58）、**P6**
  （G2 fresh 双表面 runtime，#55）两组；全过后 v1.4.0（human 批）。资格测试完成度约 ~70%。

## 2026-07-17 G4 收口（主 agent：都督·统·治理路线）

- **#57 已关闭**：G4 多 agent 控制面全链路（P7，D 层「双 agent 场景」）经 **PR #72**
  squash-merged（`a6152b6`）。writer 干将·演·控制面 + 独立 verifier 师爷·审·控制面 分离作业：
  7/7 T-ID 独立 CONFIRMED-PASS（负例逐一验证真拒绝、非吞异常）、5 脚本 76 项 self-test 独立
  计数吻合、场景两跑 `jq` 结构逐字节一致、**隔离零泄漏两跑确认**（D 层证据命门）、
  `validate-governance --strict` 全绿。总裁决 **APPROVE**。
- 证据：`lab/evals/control-plane/run-g4-scenario.py`+README、
  `lab/docs/audits/qualification/report-g4.{json,md}`、writer 报告
  `memory/branches/57-g4-control-plane.md`、独立复核报告 `memory/branches/57-g4-verify.md`
  （原文随复核 worktree 归档丢失、由主 agent 如实转录回 main，provenance 已注明）。
- 两个 agent + 两个 worktree 已归档，分支 `g4-dual-agent-verification` 本地+远端已删。
- 三条非阻断观察（分支命名漂移、`agent_name_set` 无统一 rename 原语、T-G4-6 降级负例本机需
  剥 PATH）已记录，双方独立核实属实。
- **#52 剩余**：P5（G5 干净 ELF replay，#58）、P6（G2 fresh 双表面 runtime，#55）、
  P7 另一半（G3 skills 全量，#56）仍冻结/未开；全过后 v1.4.0（human 批）。

## 2026-07-17 P4 收口（主 agent：都督·统·治理路线）

- **#54/#59 已关闭**：P4 qualification runner 经 **PR #71** merged（`fda5ef0`）。13/13 T-ID
  正负例 PASS；D2 可重复性经主 agent 独立 review worktree 复跑验证（results 逐字节一致，
  仅 meta.commit 合法差异）。执行官干将·铸·资格评测与 writer/review 两个 worktree 均已归档，
  分支本地远端已删。
- 两条 validator 观察待 human 定级（详见 `memory/branches/54-qualification-runner.md`）：
  ① check-doc-lifecycle 无跨时间状态倒退检测；② outcome-ledger sample fixture 负例级联半径宽。
- 本地 main 曾领先 1 个 checkpoint commit（629b132）与 PR #71 分叉，已 merge 收拢（6bcd378）
  并 push；工作树 clean。
- **#52 剩余**：G2（runtime enforcement，fresh 双表面）、G3（skills 全量）、G4（多 agent
  控制面）三组未开测；全过后 v1.4.0（human 批）。

> **活文件**。这是当前状态的单一真相源。每次 session 结束、compact 前、完成小目标时更新。
> fresh session 应能只读本文件 + `session-tree.md` 就接续工作。

## 最近完成 plan（doc-lifecycle，fresh session 先看这里）

- 最近完成 plan：`plans/20260712-plan-lifecycle-state.zh.md`（issue #13）· status: **verified** ·
  approved source `3704d33` · local main merge `8ee6760`。
- 2026-07-14 主控审计确认：原 issue 是轻量生命周期/审批证据；注册表 Bash 删除 guard 是初审后
  追加的防御性扩展，逐命令完备化导致非收敛 review/evidence 循环。旧执行 agent 已中断，保持 idle。
- human 随后明确回复“ok do it”，首次真实批准冻结边界：PreToolUse 只拦单次调用可独立判定的局部
  不完整；文档锚点/注册表跨文件一致性由 commit/治理门禁 validator 权威强制；Bash 删除 guard
  仅保留现有常见路径尽力拦截，不再扩展 Shell parser。
- `c9a8bf2` 提交说明及接班 agent 的旧 status 在 human 回答前声称“human 拍板 Option 1”，属于错误
  provenance；本收口改动显式纠正，不把后续授权追溯成先前授权。
- 既有 C1-C3/X1-X3 与 G1/G2 runtime 证据保留在
  `lab/evals/doc-lifecycle/evidence-20260713-runtime-probes.md`。source `3704d33` 已获独立 fresh
  `APPROVE`；human 明确授权后以双亲 merge `8ee6760` 合入，合并 tree 与 source 完全一致。
- 合并提交上 lifecycle self-test normal/`python -S` 各 410 PASS、真实 hook regression 242 PASS、
  launch 66/66、continuity 8/8；adapter sync、strict harness/anatomy/doc-lifecycle/governance、
  same-commit 与 py_compile 全绿。
- 权威状态注册表：`memory/doc-lifecycle.yaml`（brief/plan/review/decision 四类统一，语义见 `plans/ANATOMY.md`）。
- 其余存量 plan 均已 `verified`，decisions 均 `approved`（详见注册表）。
- 本节由 agent 在状态流转时更新；compact/clear 后 `context_continuity.py` 会把本文件回注新上下文。

## 2026-07-15 issue 治理轮（主 agent：都督·统·治理路线）

- human 决策落地：**#23、#46、#47 关闭**（#46 是"本阶段先关、下一阶段与模板功能全面测试一起重启"，
  非裁撤）；**#25、#22 已 pin**；#26/#27 建议标 blocked（依赖 Bridge repo 契约，human 未拍板）。
- **#47 已实现并关闭**：paseo agent 位置选择约定（无 worktree→同 Workspace 新 tab；有 worktree→
  可新 Workspace+tab；永不开新 Project）落进 `.claude/skills/spawn/SKILL.md`（单一 owner），
  commit `de94973`（本地 main，未 push）。
- **#48（open，tracking，v4）**：LingTai 治理对照总起，覆盖两份指南，「已吸收/弃/取」结构
  （human 认可）。三片：**S2** 变更自检清单（G1，分类矩阵 + Invariant/Variation/Non-goals +
  exact-base 双检自报 + 验证纪律 + 副作用授权段，挂 worktree-pr-flow/pr-review）；**S3**
  ANATOMY↔CONTRACT 配对文件（human 2026-07-15 拍板推翻 v3 的弃——root CONTRACT 索引 +
  template-sync 单边界试点先行，红线：不批量/不造双 owner/承诺带证据指针，先走
  interactive-plan-doc）；S1 承诺→证据闭环随 #46 下一阶段。exact path scope 硬门维持弃
  （#32/#43/#44 反面证据）。
- **#49（open，pinned，常驻进度条）**：仿 OpenAlice#183 形制——现状盘点（human/agent 两侧
  便利）、对照 #22 的 11 轴里程碑地图、差距清单、更新日志；初始估算 **~55%**（机制层成形、
  真实验证闭环三件套未完成：真实下游 sync #19、runtime enforcement #46、真实实验/证据链）。
  里程碑后由主 agent 更新。
- **执行官已交付（2026-07-15）**：干将·改·灵台缺口（Paseo `1f683d03`，sonnet-5/high/auto，
  独立 worktree）完成 #48 **S2 实现 + S3 plan doc**。分支 **`feat/48-checklist-contract`**
  （已 push；名字与授权指令 `feat/48-lingtai-round2` 不一致是 launcher 预置命名差异，执行官已
  在 branch status 中说明并判断不重命名）。3 commits：S2 清单挂 worktree-pr-flow +
  pr-review command（9079b5f）、S3 plan doc + doc-lifecycle 注册（25812cb）、branch status
  （5cc9976）。base=origin/main `327e76a`，与本地 main（072af38，领先 7 个未 push commit）
  改动路径无重叠。主 agent 已独立复跑 validate-governance / check-doc-lifecycle 全绿。
  详见 `memory/branches/48-lingtai-round2.md`（在该分支上）。
- **#48 主体收口（2026-07-15 下午）**：S2 经 PR #50、S3 全量实现经 **PR #51**（`9683a71`）
  合入 main 并 push。S3 一步到位（human 批注）：root `CONTRACT.md` + `scripts/CONTRACT.md`
  （TS-1..TS-9 唯一 owner，policy 改链接）+ `check-anatomy-drift.py` `validate_governed_index()`
  （self-test 16/16）+ plan doc approved→implementing。两位执行官（干将·改·灵台缺口 /
  干将·铸·契约配对）与 worktree/分支均已归档删除。#48 仅剩 S1（随 #46）。#49 进度 ~58%。
- **下一步：#52（open，tracking）系统测试总起**——取代 #46 重启职责；六组（G1 静态门禁 /
  G2 runtime enforcement / G3 skills / G4 多 agent 控制面 / G5 版本同步 / G6 Codex parity）+
  测试登记表 + ELF 真实 replay（`origin/worktree-case+elf-template-replay` 开新 worktree，
  Agent A 更新 template、Agent B 独立测试，硬分工防自证据）。human review 后按组开 6 个
  sub-issue 分阶段测；全过后 bump **v1.4.0** + tag（human 批）。遗留注意：`gh pr merge
  --delete-branch` 在本地分支被 worktree 占用时会连远端删除一起中止，合并后需
  `git push origin --delete <branch>` 兜底（#50/#51 的残留远端分支已补删）。

## 2026-07-16 P3 完成 + P4 方案待批（主 agent：都督·统·P2收口）

- **P3/#63 完成**：candidate `2ce1278`（执行官 干将·迁·下游数据层，sonnet-5·high·bypass）经
  fresh review 一轮 REQUEST CHANGES（MAJOR-1：`validate-governance.py:210` 漏 legacy 豁免，
  reviewer 师爷·审·数据迁移 opus-4-8 自构探针发现）→ 修复 + 回归固化（撤销→FAIL→恢复→OK 杀伤力
  验证双方独立完成）→ delta re-review **APPROVE** → **PR #70** merge，`origin/main = 35c9bd5`，
  #63 关闭。交付：`scripts/init-governance-data.py`（幂等、零造假、诚实计数）+ 三 validator 及
  `check_evidence_chain()` 的 legacy 三态 + receipt `governance_data_gap`。ELF fixture 验收
  4-FAIL→全绿→幂等，writer/reviewer 独立复现一致。B1/B2/B3 三个设计决策均获 reviewer 裁断成立
  （contract_version 保持 2 正确）。
- **P3 过程事故（已修复+复盘）**：writer copytree 了 ELF worktree（.git 指针致共享元数据被 /tmp
  副本改写）；文件字节零损伤，HEAD/index 按指定顺序修复三重验证；教训固化：**复制 worktree 一律
  git clone/git archive**。ELF worktree 现基线：status 全空 @ 4f1a9ec。
- **P3 清场完成**：两 agent 归档、worktree 删除、topic 分支本地+远端删除、/tmp fixtures 清理。
- **P4（#54 G1 + #59 G6）方案已写入两 issue 待 human review**：单一入口
  `lab/evals/qualification/run-qualification.py`（--group g1|g6|all；正例+负例隔离 /tmp fixture；
  复用既有 --self-test 优先；JSON+MD 双证据落 `lab/docs/audits/qualification/`；同 commit 重跑
  一致；runner 不挂进 governance；缺陷开独立 issue 不顺手修）。**human 批准后才建分支/agent。**
  P5–P8 冻结。#52 路线图已同步。
- 本地 main 仅领先 origin 一个 memory checkpoint commit，未 push。

## 2026-07-16 P2 收口完成（主 agent：都督·统·P2收口，前名 军师·谋·P2收口）

- **P2 局势**：#62 已经 PR #66 合入 `main@934f42c`（= origin/main）；#60 approved candidate =
  `origin/fix/60-adoption-template-anchor@5e40ad3`（两轮 fresh APPROVE，未合入）；本地
  `p2a-60-adoption-template-anchor@1dc232a` 是 #60+#62 集成证据分支，**未合并、不可当残留清理**。
- **#67（P2c blocker）**：human 2026-07-16 批准 D1–D3 全部推荐方案（issue 正文复选框/状态行/评论已同步）。
  执行官 **干将·改·双境合同**（claude-sonnet-5·high·auto，Paseo worktree
  `~/.paseo/worktrees/1kaz3672/fix-67-downstream-adapter-context`）交付 candidate
  **`7992478`**（+branch status `7e12b87`），branch `fix/67-downstream-adapter-context`，base `main@934f42c`。
  内容：`sync-codex-adapters.py --context {source,downstream,auto}` 拆分（source 保留 #61 exact-set；
  downstream 不要求进 git index 但磁盘 missing/stale/unexpected 仍严查；malformed/symlink 锚点
  fail-closed）；`write()` 诚实计数 `changed N/expected M`；bootstrap-smoke 新增真实 git-index 回归
  （修复前 FAIL 已复现）。详见 `memory/branches/67-downstream-adapter-context.md`（在该分支上）。
- **fresh review**：**师爷·审·双境合同**（claude-opus-4-8·high，独立 session）verdict **APPROVE**，
  无 BLOCKER/MAJOR；独立复现 pre-fix FAIL + 全套门禁复跑全绿；3 个 MINOR/NIT 仅记录（空 TOML 锚点
  边界、check-agent-harness auto 时序假设 LOW、contract_version 1→2 判级合理）。主 agent 亦独立复跑
  bootstrap/adoption/template-sync smoke + governance strict 全绿。
- **#67 已合入（2026-07-16 下午）**：human 授权 push+PR+merge 一并执行。**PR #68** merge 后
  `origin/main = 604a02a`；remote topic `fix/67-downstream-adapter-context` 已删；本地 main 已 rebase
  到 origin/main 之上（memory checkpoint commit 在顶）。
- **#60 集成合入（P2 完成，2026-07-16 下午）**：干将·改·双境合同建
  `integrate/60-adoption-anchor-refresh`（base `604a02a`）双亲 merge `a73143c`（5e40ad3 未改写；
  冲突恰两处均双侧保留：bootstrap-smoke import、scripts/README 注释）。三方验证一致：writer 自验
  全绿；主 agent 机械核查（merge 与自动合并树仅差 8 行冲突标记）；师爷·审·双境合同独立 /tmp fixture
  复现端到端——真实 adopt → `.template.toml`（origin 正确，v1.3.8）→ 同版本首次 sync
  **receipt=pass（原 P2 失败点为 partial）**、CONTRACT=framework 字节一致、38 generated adapters
  全程 untracked 仍通过 → 二次 sync 幂等（`apply_changed=[]`）→ fixture 内 `--check` 报
  `context=downstream OK`，verdict **APPROVE** 无 BLOCKER/MAJOR。human 授权后 **PR #69** merge，
  `origin/main = deeda67`。证据：main 上 `memory/branches/integrate-60-refresh.md`、PR #68/#69 正文。
- **issue 状态**：#67、#60 随 PR 自动关闭；#62 手工关闭（最终验收达成）；#52 已留 P2 完成评论。
  **#63/P3–P8 继续冻结，等 human 启动下一阶段。**
- **清场完成**：远端删 `fix/67-downstream-adapter-context`、`fix/60-adoption-template-anchor`、
  `integrate/60-adoption-anchor-refresh`；本地删 `p2a-60-adoption-template-anchor`（双亲已进 main）、
  `61-codex-adapter-ownership`、`fix/48-lifecycle-verified`、`root-contract-template-framework`、
  `fix/67-*`、`integrate/60-*`；移除 `/tmp/ml-template-61-integration-a01c3fe` worktree；Paseo 归档
  干将·改·双境合同（e6335bbd）、师爷·审·双境合同（347186cc）及 `fix-67-downstream-adapter-context`
  worktree，roster 置 done。证据分支保留：`test/52-gate-check`、`elf-replay-sync-v14rc`、
  `worktree-case+elf-template-replay`、`research/paper-positioning`（无关活跃工作）。
- **已知 NIT（不阻断，留给后续）**：adopt prove 阶段 pre-sync `governance_rc=1` 属预期（首次 sync
  后转绿）；空但可解析的 `.template.toml` 判 downstream（正常流程不可达）；`--context auto` 依赖
  anchor 先写后 check 的时序（现有调用点均满足，LOW）。
- 本地 main 仅领先 origin/main 一个 memory checkpoint commit，未 push（push main 需 human 放行）。

## 当前 objective

2026-07-14 human 明确授权发布当前本地 `main`：#18 的 fresh runtime 证据证伪 Codex hook
enforcement，已关闭并延期，未合入本次发布。当前发布只包含 #12/#12b/#12c/#13/#14/#15/#16/#17
八项已 fresh-approved 且本地集成的能力；按既有“每项一个 PATCH”覆盖，版本为 `v1.3.8`。

八项本地集成能力均有 fresh `APPROVE`：#12/#12b/#12c/#13/#14/#15/#16/#17。#18 未满足真实
runtime enforcement 契约，已关闭并延期；不将其计入本次发布。

2026-07-15 分支清理：`integrate/18-anatomy-semantic-parity` 分支/worktree 已删除（其 C1-C7/X1-X7
self-attestation 与独立 fresh 复核结果不一致，不可信）；归档记录见
`memory/branches/18-anatomy-semantic-parity.md`。#18 范围的静态可判定部分已拆分为 #34（closed,
merged → `#42`）；运行时 hook enforcement parity 部分重开为新 issue **#46**（open，待 human
review，未纳入任何发布范围）。同时合并 `feat/spawn-paseo-launch-notes`（本地 merge `6feca10`），
沉淀为 issue #45（closed）；分支/worktree 已删除。`feat/13-plan-lifecycle-state`（已合并入 main）
与 `feat/18-anatomy-semantic-parity`（工作已被 `integrate/18-anatomy-semantic-parity` 吸收）分支/
worktree 也已删除。

## 发布状态（human 明确授权）

- 发布级矩阵仅覆盖已合入的八项能力；#18 明确延期，不作为阻塞条件。
- 版本覆盖为从 `v1.3.0` 跳至 `v1.3.8`；本次只创建一个本地 annotated tag `v1.3.8`，随后按 human
  授权 push `main`、tag 并创建 GitHub release。

## #13 本地集成（2026-07-14）

- exact source `3704d33317dde678c0f88e80c7d69d63842e8f1f` 获独立 Codex fresh `APPROVE`，确认
  hook/validator 边界与错误授权归因均已修正；Bash 删除 guard 明确保留为尽力减速带。
- human 明确回复“合并 #13”后，本地 `main` 生成双亲 merge
  `8ee67604e2440c9e28db90127c517e1e68853af8`。merge tree 与 source tree 均为
  `246c24ccc74b9177c274c44679a164728660b08a`；未 push、未 tag、未 release。
- 合并提交上的定向回归、runtime probes、adapter/parity、strict governance 与 same-commit 全绿。

## #17 本地集成（2026-07-13）

- exact source `52f83aafe54b6891e5963c2d5c4e731717132ff2` fresh `APPROVE`；合并时发现 #17
  provenance 枚举漏掉 #16 合法的 `approved` run 状态。集成修复后，完整状态机可被解析，
  但只有 `status=done` 且 `run_summary` 已填才贡献 provenance 或满足 `run-closed`。
- staged integration candidate 再获 fresh `APPROVE`；merge commit
  `405c5421d7721111e14a4f9e7a745c41ec83630f`。normal/`python -S` self-test 与 strict provenance、
  experiment-state/outcome strict、adapter sync、strict harness/anatomy/governance 全绿。

## 未合入 blocker

- （已解除，2026-07-15）原 #18 blocker：分支已删除，范围拆分为 #34（已交付）+ #46（新开，运行时
  hook enforcement parity，待 human review，无阻塞发布的既定时间表）。

## #16 fresh-review handoff（2026-07-13）

- launch hook 命中即拒，`CLAUDE_ALLOW_LAUNCH` / `CODEX_ALLOW_LAUNCH` 永不放行；覆盖
  `env -S`、shell/python `-c`、内部 `.`/`..`、`python -m`、`_worker`、带 operand 的
  `timeout --signal TERM 60` 与 `env -u FOO`。
- agent 使用 `expctl validate-recovery` 只读校验；`/tmp` 与 canonical ledger 的 actual
  `apply-recovery` 都因无可信 provenance/原子消费 fail-closed。
- alert schema 新增 proposal.workdir、approval_provenance、consume/execution/resolved 状态；
  当前 provenance 必须为 null，非 null 自称批准由 validator 拒绝。
- `fake_job.py` 仅接受无 symlink 的字面 `/tmp/.../<run-id>`，核对受信解释器/status/worker argv，
  以 control lock 串行控制动作，并用 pidfd 避免 PID reuse signal。
- status=done 的 `run_summary` 必须位于 `lab/code/experiments/`，且是 repo-relative、无
  traversal/symlink 的 regular file。
- 不运行真实训练/scheduler；验证只使用脚本内置 fake/local self-test。
- fresh validation：launch gate 66/66、fake job 12/12，`expctl` 与 experiment-state self-test
  均在 `python`/`python -S`/`python3`/`python3 -S` 四模式通过；experiment-state strict、adapter
  sync、harness strict、anatomy、governance strict、same-commit/diff/pycompile 全绿。planner/watch/
  recovery command 使用运行中 `expctl` 的 canonical `sys.executable`，不同 Python 安装不能串用。

本地 `main` 已集成 issue #14 多 agent 控制面第一版——
`.agent/multi-agent-control-plane.md` doctrine、`scripts/agent-{state,status,mailbox}.py` +
`check-agent-conflicts.py` 四脚本（自带 --self-test）、`pre_tool_guard.py` 冲突/写错-worktree
薄接线、spawn skill 并入 list/status 查询、`agent_name_set.py` 挂接控制面状态。
详见 `memory/branches/14-multi-agent-control-plane.md`（含遗留：真实 Paseo-tab / Codex
smoke 留给监控员在非沙箱环境跑）。

本地 `main` 已集成 issue #12 part A（来源 `feat/12-bootstrap-adoption-proof`）：
实现新项目 bootstrap 命令，把 README「派生后的落地步骤」里能自动化的部分（`.template.toml` 版本
锚点、`core.hooksPath`、Codex adapters 同步、governance）收敛成一条幂等命令
`scripts/bootstrap-project.py`，经 `.claude/skills/bootstrap-project/SKILL.md` 引导调用；需要
human 信息的步骤（CODEOWNERS owner、`PROJECT.md`、删无用目录、Codex trust）只报告不代做。见
`plans/20260712-bootstrap-adoption-proof.zh.md`（任务树 A + D 里归属 A 的子项）。issue #12 的
part C、part B 随后按依赖顺序经独立 fresh Codex review 合入本地 `main`。

本次本地 merge 集成 issue #12 part C（来源 `feat/12c-smoke-contract`，approved HEAD
`35c619678ff1eba0b4ca22cec4fe8e72369e96cd`）：实现统一的 runtime/smoke 验证合同
（任务树 C1-C4 + D 里归属 C 的部分）。`adopt-existing-repo.py` 的 `prove` phase 与
`check-adoption-integrity.py` 现在按 schema 写 smoke 结果（`command_source`/`command`/
`result`（pass/fail/skipped/unknown）/`unverified_reason`），且 exit code 与 smoke 结果解耦
——只在 adoption 自身完整性失败（tracked-byte hash 不一致，或 normalize 遗留未解决的 conflict/
受保护路径 blocker）时非 0；smoke 非 pass 时 exit code 仍为 0，但 report /
`check-adoption-integrity.py --json` 必须带显式、机器可读的 `warnings`/`smoke_warnings` 字段，不能
被静默吞掉（已决策，开放问题 5）。见
`plans/20260712-bootstrap-adoption-proof.zh.md`（任务树 C + D 里归属 C 的子项）。

本次本地 merge 集成 issue #12 part B（approved source HEAD `f33ff9c`）：给
`adopt-existing-repo.py` 的 `discover`/`normalize`
phase 加内置保守四类语义归类（`template_control_item` / `conservative_import` / `protected` /
`conflict`，v1 不做外部规则文件/参数覆盖，见开放问题 4 已决策），`normalize` 消费该归类计划而非
硬编码二元判断（B1-B4）；`prove` phase 新增 Claude/Codex 双 agent surface 报告，复用抽取出的
`scripts/_agent_surface.py` 共享渲染函数（与 `bootstrap-project.py` 共用，即 D2c，B6）。见
`plans/20260712-bootstrap-adoption-proof.zh.md`（任务树 B + D 里归属 B 的子项：D1/D2/D2c/D3/D4/D6）。
冲突解法以 B 的 21 个语义/安全场景为基础，补回 C 的 clean-pass 断言与 6 个专项负向场景，
合并后 adoption smoke 共 27 场景。

2026-07-13 fresh review 的 BLOCKER 与后续 MAJOR 均已修复：canonical state 目录之外，
`adoption-plan.json` / `baseline.json` / `phase-log.jsonl` 三个叶节点现在也参加 symlink
门禁；canonical 命中后，确定性 `/tmp/template-adoption-state-<digest>` fallback 会从绝对路径根逐段
lstat 到 fallback 根与三个叶节点，root/intermediate/leaf 任一 symlink 均非零 fail-closed，不再写穿。
`normalize` 现在把 persisted classification 当提案，对当前 root 做完整、先验、两阶段重验：discover 后新增且
未在 classification / `scaffold_control_items` 声明中登记的 root 会阻断；所有 planned entry 的
kind/category/blocker/target_path 都按当前树重算；
`template_control_item` 仅允许真实 `CONTROL_ITEMS` 且不再先于 nested protected scan `continue`；默认模式
任一 blocker 都在所有搬移前退出。adoption smoke 已从 19 扩为 21 组，加入新增 root 与伪造 control-item
两类对抗 fixture，并保留原 19 组回归。

本次本地 merge 集成 issue #15（approved source HEAD `94cb678`）：

- `feat/15-outcome-aware-routing` fresh review 四项门槛已修：ledger 写入只允许 canonical
  `.outcome-ledger/` 与字面 `/tmp`；outcome 证据按完整具体路线七维键隔离；两个 decision
  写入口 append 前拒绝重复 ID；`--min-samples >= 1` 且零 outcome 保守回退。
- 新增 repo 根、`.env*`、symlink/越界、跨 model/effort/policy 污染、重复 decision ID、
  零/非法样本阈值对抗测试。定向结果：47/47 unittest 通过，outcome strict schema gate
  0 error / 0 warning；fresh Codex reviewer verdict 为 `APPROVE`。

## Constraints

- 遵守 `AGENTS.md` / `.agent/AGENTS.md` / `.agent/action-boundary.md`。
- 不编辑或删除 `lab/data/**`、`lab/runs/**`、`lab/models/**` bytes、`checkpoints/**`、`wandb/**`、
  `lab/infra/private/**`、`.env`。
- 不启动/kill/restart 长训练或远端作业。
- 不 push main、不开 PR、不 release。
- 两个 replay case worktree/branch 继续作为证据保留，不合入 main。

## Files inspected（issue #12 part A）

- `plans/20260712-bootstrap-adoption-proof.zh.md`（全文，含全部批注/决策历史）
- `scripts/adopt-existing-repo.py`、`scripts/template-sync.py`、`scripts/check-agent-harness.py`、
  `scripts/sync-codex-adapters.py`、`scripts/validate-governance.py`、`scripts/check-anatomy-drift.py`、
  `scripts/check-adoption-integrity.py`
- `.agent/template-versioning-policy.md`、`.github/CODEOWNERS`、`PROJECT.md`、`VERSION`
- `.claude/skills/adopt-existing-repo/SKILL.md`、`.claude/commands/adopt-existing-repo.md`
- `lab/evals/adoption/run-adoption-smoke.py`、`lab/ANATOMY.md`
- `README.md`、`DESIGN.md` §10、`scripts/ANATOMY.md`、`.claude/ANATOMY.md`、`scripts/README.md`、
  `scripts/CLAUDE.md`、`scripts/AGENTS.md`

## Files inspected（issue #12 part C）

- `plans/20260712-bootstrap-adoption-proof.zh.md`（全文，C1-C4 + 验证标准里对应 C 的部分）
- `scripts/adopt-existing-repo.py`、`scripts/check-adoption-integrity.py`（现状代码）
- `lab/evals/adoption/run-adoption-smoke.py`、`lab/docs/audits/agent-r1-adoption-replay-report.md`
  （既有 replay 报告的写法参考）
- `.claude/commands/adopt-existing-repo.md`
- 网络：候选真实 repo 调研（`docopt/docopt`、`kvesteri/validators`、`benjaminp/six`、
  `un33k/python-slugify`、`jaraco/inflect`、`tartley/colorama` 等，最终选 colorama，见下方决策）

## Files inspected

- `AGENTS.md`
- `.agent/AGENTS.md`
- `.agent/action-boundary.md`
- `.agent/tool-skill-interface.md`
- `.agent/model-routing-policy.md`
- `.agent/repo-documentation-topology.md`
- `ANATOMY.md`
- `.claude/ANATOMY.md`
- `.claude/agents/*.md`
- `.claude/skills/*/SKILL.md`
- `.claude/commands/*.md`
- `.claude/hooks/*.py`
- `.claude/settings.json`
- `.claude/skills/coding-agent-quota/SKILL.md`
- `.claude/skills/coding-agent-quota/scripts/read_agent_quota.py`
- `.claude/skills/subagent-routing/SKILL.md`
- `.claude/agents/subagent-router-agent.md`
- `.agent/model-routing-policy.md`
- `scripts/check-agent-harness.py`
- OpenAI/Codex docs：AGENTS.md、skills、subagents、hooks、config、rules

## Files modified（issue #12 part A，本轮新增）

- `scripts/bootstrap-project.py`：新增。把刚从模板派生的新 repo 落地成自洽状态：
  `.template.toml`（origin+version 锚点，`--origin` 显式传入不推断，origin 冲突默认报错、
  `--force` 才覆盖）、`git config core.hooksPath .githooks`、`sync-codex-adapters.py`、
  `validate-governance.py`；需 human 信息的步骤只报告（`human_todo_items`）不代做；写
  `lab/docs/audits/template-bootstrap/state/*.json` 与 `template-bootstrap-report.md`。
- `.claude/skills/bootstrap-project/SKILL.md`：新增 skill（非 slash command，见开放问题 1 已决策）。
- `.agents/skills/bootstrap-project/SKILL.md`：由 `sync-codex-adapters.py` 生成的 Codex adapter；
  未生成对应 `command-bootstrap-project`（按决策，bootstrap 本身就是 skill 形态）。
- `lab/evals/bootstrap/run-bootstrap-smoke.py`、`lab/evals/bootstrap/README.md`：新增 synthetic
  fixture，覆盖幂等/origin 冲突/`--force`/三个 validator 全绿。
- `lab/ANATOMY.md`：leaf 层清单加入 `evals/bootstrap/`。
- `scripts/ANATOMY.md`：加入 `bootstrap-project.py` 的 Components/Connections 行。
- `scripts/README.md`、`scripts/CLAUDE.md`：加入 bootstrap 用法；`CLAUDE.md` 把「三个脚本只读、
  无副作用」改写为「只读校验脚本 vs 有副作用的 mutating 脚本」两类描述（D5，措辞已与现实脱节）。
- `.claude/ANATOMY.md`：Connections 加入 `skills/bootstrap-project/` 调用关系。
- `README.md`：「派生后的落地步骤」改写为调用 `bootstrap-project.py`，人工兜底步骤（含
  Codex trust 前提）保留在命令输出的 human todo 里；快速门禁加入 bootstrap smoke 命令。
- `DESIGN.md` §10：Skills 12→13、Codex adapters skills 20→21、Validators/tools 9→10，补
  `bootstrap-project` 相关条目。
- `memory/current-status.md`、`memory/session-tree.md`：记录本 feature 落地状态（本节）。

## Files modified（issue #12 part C，本轮新增）

- `scripts/adopt-existing-repo.py`：`detect_test_command()` 现返回 `(command, command_source)`
  二元组（`explicit`/`auto-detected`/`none`）；新增 `evaluate_smoke()` 按 C1 schema
  （`command_source`/`command`/`result`/`unverified_reason`/`exec`）跑并分类被迁移项目自身原生测试；
  新增 `latest_normalize_blockers()`，`integrity_result()` 现把「最近一次 normalize 遗留未解决的
  conflict/受保护路径 blocker」也算进 adoption 自身完整性失败（`unresolved_blockers` 字段），不再
  只看 tracked-byte hash；`prove()` 生成结构化 `smoke` + `warnings` 字段并写进 report；`main()`
  改为按 `prove` 返回的 `integrity.ok` 决定 process exit code（此前 bug：`prove` 从不让整体进程非
  0 退出，即使 integrity 失败）——exit code 现在只受 adoption 自身完整性影响，与 smoke 结果解耦
  （已决策，开放问题 5）。`write_report()` 新增 Smoke / Warnings 小节。
- `scripts/check-adoption-integrity.py`：新增 `latest_smoke_warnings()`，从最近一次 `prove`
  phase-log 条目读出 `warnings` 并在文本/`--json` 输出里显式呈现（`SMOKE WARNING ...` /
  `smoke_warnings` 字段）；`unresolved_blockers` 同样在文本模式打印为 `BLOCKED <path>`；exit code
  语义不变（只反映 `integrity_result().ok`，现在天然覆盖 blocker 未解决的情况）。
- `lab/evals/adoption/run-adoption-smoke.py`：从单一 happy-path 扩成七个场景
  （**2026-07-13 按 Codex 两轮复审修正，初版为四场景且证据声明不成立，见下**）：
  `scenario_happy_path`（回归，新增断言 `smoke_result: pass` + 空 warnings）、
  `scenario_blocked_normalize`（受保护路径 `checkpoints/` 触发 blocker，断言
  `adopt-existing-repo.py` 与 `check-adoption-integrity.py` 均非 0 exit，blocker 文本可读）、
  `scenario_blocked_conflict`（**2026-07-13 补**：destination-exists 冲突，目标位置
  `lab/code/imported/<slug>/data.txt` 已存在不一致内容；断言 adopter 非 0 exit 停下、冲突两侧
  字节未动、`BLOCKED destination exists: ...` 文本与 `--json unresolved_blockers` 可读——初版
  声称一个 fixture 覆盖「冲突/受保护」两个子类，实际只测了受保护路径）、
  `scenario_smoke_failing_command`（检测到但失败的原生测试，断言两脚本仍 exit 0 但 report/`--json`
  都带非空 warning——**2026-07-13 修**：初版 fixture 是 pytest 风格模块级函数，`unittest
  discover` 不收集，实际 Ran 0 tests（Python ≤3.11 exit 0 记成 `pass`，≥3.12 靠 NO_TESTS_RAN
  exit 5 碰巧记成 fail），从未真正验证「检测到且真实跑失败」；现改为必然被收集且失败的
  `unittest.TestCase`，并从 phase-log smoke exec 断言 `Ran 1 test` + `FAILED` 防再退化）、
  `scenario_smoke_undetected`（无可探测测试命令，断言 `skipped` + 显式
  `unverified_reason`，同样 exit 0 + 非空 warning）、
  `scenario_smoke_timeout`（显式命令超时，断言 `unknown` + `timeout=true` + 非空 warning）、
  `scenario_legacy_phase_state_rejected`（旧 v1 state 缺 `test_command_source` 时拒绝 prove 并要求
  重新 discover，防止来源/命令自相矛盾）。
- `.claude/commands/adopt-existing-repo.md`：步骤 4 汇报清单改写，区分 integrity/blocker（应非 0）
  与 smoke（不应非 0，但须转述显式 warning）。
- `.agents/skills/command-adopt-existing-repo/SKILL.md`：由 `sync-codex-adapters.py` 重新生成
  （same-commit）。
- `README.md`、`scripts/README.md`：补充 smoke 合同的 exit-code/warning 解耦说明。
- `lab/docs/audits/README.md`：登记新增的 `colorama-adoption-replay-report.md`。
- `lab/docs/audits/colorama-adoption-replay-report.md`：新增。真实 existing-repo replay（新找的
  `tartley/colorama`，不复用/复跑 Agent-R1 案例，见开放问题 6），命中 `Makefile` `test:` 检测路径，
  原生测试因目标 repo 未 bootstrap venv 而失败——验证 smoke 合同在真实「检测到但失败」场景下端到端
  可用：两脚本均 exit 0，report/`--json` 都有显式非空 warning。
- `memory/current-status.md`、`memory/session-tree.md`：记录本节。

## Decisions（issue #12 part C，本轮新增）

- 严格按 `plans/20260712-bootstrap-adoption-proof.zh.md` 已拍板的 C1-C4/开放问题 5 落地，未重新讨论：
  exit code 只反映 adoption 自身完整性（tracked-byte hash + 未解决 blocker），smoke 结果永远走
  warning 字段，不影响 exit code。
- 把「normalize 遗留未解决 blocker（受保护路径/目标已存在的冲突）」也纳入
  `integrity_result().ok` 的判定——这是本轮在读代码时发现的一个真实 gap：此前 `prove` 从不让
  `adopt-existing-repo.py` 整体进程非 0 退出（即使 integrity 失败），且 blocker 未解决时
  `check-adoption-integrity.py` 无法感知、会静默报 `OK`。这不是原 plan 显式写出的实现细节，但是
  C1「adoption 自身 integrity 失败（例如 tracked-byte hash 不匹配）」这句里「例如」二字暗示的
  应有覆盖范围，与验证标准「冲突文件/受保护路径命中……断言 check-adoption-integrity.py 非 0
  exit」直接对应，故按此实现，未额外请示。
- 真实 repo replay 选择 `tartley/colorama`（而非继续用 Agent-R1）：小（`.git` 316K）、有明确
  `Makefile` `test:` 目标（不同于 Agent-R1 的「完全未检测到」与本模板负向 fixture 常用的
  `tests/` 目录 pytest 检测路径），跑出「检测到但失败」的真实结果（本地环境未预装该 repo 所需
  virtualenv/pytest），是本轮最有代表性的新证据形态。
- `check-adoption-integrity.py` 的 `smoke_warnings` 直接从最近一次 `prove` 的 phase-log 条目读取，
  不重新解析 markdown report——避免报告格式变化时校验逻辑跟着漂移，保持单一结构化事实源
  （`lab/docs/audits/template-adoption/state/phase-log.jsonl`）。
- 未触碰 `.claude/skills/adopt-existing-repo/SKILL.md`（D2 显式归属 B），仅更新
  `.claude/commands/adopt-existing-repo.md` 步骤说明 + 同 commit 重新生成对应 Codex adapter
  （D2b same-commit rule）。

## Commands + results（issue #12 part C，本轮新增）

| command | 结论 |
| --- | --- |
| `python3 lab/evals/adoption/run-adoption-smoke.py`（happy-path + blocked-normalize + blocked-conflict + smoke-fail + smoke-undetected + smoke-timeout + legacy-state 七场景） | **2026-07-13 两轮复审修正后真实重跑（Python 3.12.3）**：`[adoption-smoke] OK`，七场景全部通过。新增 timeout/`unknown` 合同与旧 v1 phase state 缺 provenance 时的 fail-closed 回归；此前「四/五场景全部通过」证据已被本行取代。 |
| 手工冒烟：`checkpoints/` 受保护路径 repo 跑 `adopt-existing-repo.py --phase all` | `exit 1`，stderr 含 `checkpoints` blocker；`check-adoption-integrity.py` 同样 `exit 1`，输出 `BLOCKED checkpoints`，`--json` 里 `ok=false`、`unresolved_blockers=["checkpoints"]`。 |
| 手工冒烟：失败测试 repo（`tests/test_broken.py`） | **2026-07-13 更正**：初版该 fixture 是 pytest 风格函数，`unittest discover` 实际 Ran 0 tests（本机 Python 3.12 靠 NO_TESTS_RAN exit 5 记成 fail，并非「故意断言失败」被真实跑出）；修正后（`unittest.TestCase`）复核：`adopt-existing-repo.py --phase all` `exit 0`；phase-log smoke exec 含 `Ran 1 test` + `FAILED (failures=1)`；report 含 `smoke_result: fail` 与显式 warning；`check-adoption-integrity.py` `exit 0`，`--json` 的 `smoke_warnings` 非空。 |
| `python scripts/adopt-existing-repo.py /tmp/colorama-adoption-replay/Colorama --phase all --policy conservative --project-name colorama`（真实 repo replay，`tartley/colorama` @ `841634e`） | `exit 0`；`integrity=ok`、`normalize blockers=0`、`smoke=fail`（`make test` 检测到但因目标 repo 未 bootstrap venv 而失败）。 |
| `python scripts/check-adoption-integrity.py /tmp/colorama-adoption-replay/Colorama` / `--json` | `exit 0`；`OK -- present 49/49`；`smoke_warnings` 非空，列出 `original_test` fail + reason。 |
| `python scripts/validate-governance.py --strict`（`uv run --with pyyaml`） | `OK — 0 error(s), 0 warning(s)`。裸 `python3`（无 PyYAML，本机预置环境缺口，非本轮引入）跑同一命令会因 4 条 YAML-related warning 在 `--strict` 下变 `FAIL`；已用 `git stash` 验证该 warning 在改动前后一致存在，不是本轮回归。 |
| `python scripts/check-agent-harness.py --strict`、`python scripts/check-anatomy-drift.py`、`python scripts/sync-codex-adapters.py --check` | 全部 `OK`。 |
| `python scripts/check-same-commit.py --staged` | `OK —— 1 处结构改动，对应 anatomy 已同变更集更新`。 |
| `git diff --check` | 通过，无空白错误。 |
| 本地 B+C 集成候选 `python lab/evals/adoption/run-adoption-smoke.py` | `[adoption-smoke] OK`，27/27；B 的 21 场景与 C 的 pass/protected/conflict/fail/skipped/timeout/legacy 合同同时通过。 |
| `python lab/evals/bootstrap/run-bootstrap-smoke.py`（回归，确认未破坏 part A） | `uv run --with pyyaml` 下 `OK`；裸 `python3` 因同一 PyYAML 缺口 `FAIL`（非本轮回归，见上）。 |

## Files modified

- `.codex/`：新增 Codex project config、rules、custom-agent adapters 与导航四件套。
- `.agents/`：新增 Codex repo-local skills adapters 与 command adapters，以及导航四件套。
- `.claude/hooks/pre_tool_guard.py`：支持 Codex `apply_patch` 输入与 `CODEX_ALLOW_PUSH_MAIN=1`。
- `.claude/hooks/format_changed_python.py`：新增 Claude/Codex 共用的 Python 格式化 advisory hook。
- `.claude/hooks/zh_review_advisory.py`：支持 Codex `apply_patch` 变更路径解析。
- `scripts/sync-codex-adapters.py`：新增从 `.claude/` canonical 能力生成 Codex adapters 的脚本。
- `scripts/check-agent-harness.py`：新增 Codex config/adapters 检查。
- `AGENTS.md`、`CLAUDE.md`、`README.md`、`DESIGN.md`、`.agent/*.md`、`lab/infra/*`：
  同步 Claude/Codex 双 surface 的 doctrine 与说明。
- `ANATOMY.md`、`.claude/ANATOMY.md`、`.codex/ANATOMY.md`、`.agents/ANATOMY.md`、`scripts/ANATOMY.md`：
  同步结构路由。
- `memory/change-control.yaml`、`memory/current-status.md`、`memory/session-tree.md`：记录本次能力变更。
- `.claude/skills/coding-agent-quota/`：新增 canonical quota skill、UI metadata 与读取脚本。
- `.agents/skills/coding-agent-quota/SKILL.md`：由 `scripts/sync-codex-adapters.py` 生成的 Codex adapter。
- `.claude/skills/subagent-routing/SKILL.md`、`.claude/agents/subagent-router-agent.md`：
  派发 child agent 前必须读取 quota snapshot，并把 provider/model/effort 推荐写进 launch packet。
- `.agent/model-routing-policy.md`、`.agent/templates/launch-packet.md`：
  增加 role、quota snapshot、usage velocity、Paseo preference、recommended provider 字段。
- `.agents/skills/subagent-routing/SKILL.md`、`.codex/agents/subagent-router-agent.toml`：
  由 `scripts/sync-codex-adapters.py` 同步更新。
- `.claude/ANATOMY.md`、`DESIGN.md`：登记新增 skill 与能力数量。
- `scripts/check-agent-harness.py`：将本地 `.omx/` runtime state 视作工具状态忽略，避免 strict gate 因本机 runtime 目录失败。

## Decisions（issue #12 part A，本轮新增）

- 严格按 `plans/20260712-bootstrap-adoption-proof.zh.md` human 已拍板的 6 条决策落地，未重新讨论：
  bootstrap 做成 skill（非 command）、`--origin` 显式传参不推断、origin 冲突默认报错 `--force`
  才覆盖、语义归类 v1 不做（不在本分支范围内）、真实 replay 用新 repo（不在本分支范围内）、B/C
  拆独立 PR（本分支只做 A）。
- `.template.toml` 只写 `origin`/`version` 两个字段（不额外塞 `bootstrapped_at` 等元数据），
  保持与 `scripts/template-sync.py` 的 `read_template_toml()` 解析预期一致、避免不必要的 schema 面。
- origin 冲突检测在 `bootstrap-project.py` 里发生在**任何**写操作之前（先读后判断），确保「报错并
  停止」是真的不碰任何文件，不是「跑到一半才报错」。
- `human_todo_items()` 对 CODEOWNERS/PROJECT.md 做轻量 placeholder 检测（复用仓库既有的 `<...>`
  占位符约定，以及本模板固定的默认 owner `@a-green-hand-jack` 字符串），只作为 report 里的
  `detected_state` 展示，不作为判定依据、不代替 human 填写——遵守「不猜测」底线。
- `agent_surface_checklist()` 的说明文字明确标注 Claude/Codex 文件计数只是辅助展示，机器事实源是
  `check-agent-harness.py --strict` 与 `sync-codex-adapters.py --check` 的返回码（plan A4 要求）。
- D2c（bootstrap 与 adoption 共用同一份 agent-surface postflight 数据结构/渲染函数）**不在本分支
  范围内**——上层任务指令明确排除 D2c，留给未来 B（B6）落地时决定是否重构复用。

## Decisions

- `.claude/` 继续作为 canonical capability source；Codex adapters 由 `scripts/sync-codex-adapters.py`
  机械生成，避免两套能力手写漂移。
- Codex skills 使用 `.agents/skills/`；Claude slash commands 生成 `command-*` skills，作为 Codex 的等价入口。
- Codex custom agents 使用 `.codex/agents/*.toml`；不写死 model，保留"预算不是身份"原则。
- 共享 hook 地板继续放在 `.claude/hooks/`，Codex 通过 `.codex/config.toml` 调用同一批脚本。
- `coding-agent-quota` 优先读 `~/.claude/.search-index/usage.db` 的 `api_usage_snapshots`；
  Codex 额外 fallback 扫 `~/.codex/sessions/**/*.jsonl` 与 archived sessions 的 `rate_limits`。
  脚本不读取 credential 文件。
- `~/.paseo/orchestration-preferences.json` 当前未发现；quota 脚本会显式标注 `missing/defaulted`，
  并使用内置保守默认，不会假装已经读到本地偏好。

## Commands + results（issue #12 part B fresh review BLOCKER + MAJOR，2026-07-13）

| command | 结论 |
| --- | --- |
| `PYTHONDONTWRITEBYTECODE=1 python lab/evals/adoption/run-adoption-smoke.py` | `[adoption-smoke] OK`，21/21；新增 discover 后 `checkpoints/model.bin` root 与伪造 `src -> template_control_item` 两组无搬移/无外写对抗测试，原 19 组保持通过。 |
| `PYTHONDONTWRITEBYTECODE=1 python -m py_compile scripts/adopt-existing-repo.py lab/evals/adoption/run-adoption-smoke.py` | 通过，无输出。 |
| `python scripts/sync-codex-adapters.py` | `[sync-codex-adapters] wrote 37 adapter file(s)`；本轮未改 canonical adapter 输入，工作树无生成物 diff。 |
| `python scripts/sync-codex-adapters.py --check` | `OK — 0 issue(s)`。 |
| `python scripts/check-agent-harness.py --strict` | `OK — 0 error(s), 0 warning(s)`。 |
| `python scripts/check-anatomy-drift.py` | `OK — 扫描 15 个 ANATOMY.md，0 处漂移`。 |
| `python scripts/validate-governance.py --strict` | `OK — 0 error(s), 0 warning(s)`。 |
| `git diff --check` | 通过，无空白错误。 |

## Commands + results（issue #12 part A，本轮新增）

| command | 结论 |
| --- | --- |
| `python scripts/bootstrap-project.py <tmp> --origin a-green-hand-jack/ml-project-repo-agent-native-template`（手工冒烟，四个 tmp repo 场景：首次创建/幂等确认/冲突拒绝/`--force` 覆盖） | 全部符合预期：`created`→`confirmed`→冲突 `exit 1` 且未改文件→`--force` 后 `overwritten`。 |
| 在上面 tmp repo 内跑 `validate-governance.py --strict` / `check-agent-harness.py --strict` / `sync-codex-adapters.py --check` | 全部 `OK`，`.template.toml` 可被 `template-sync.py` 的 `read_template_toml()` 正确解析。 |
| `python lab/evals/bootstrap/run-bootstrap-smoke.py` | `[bootstrap-smoke] OK`：覆盖幂等/冲突拒绝/`--force`/三个 validator 全绿。 |
| `python lab/evals/adoption/run-adoption-smoke.py`（回归，确认未破坏既有 adoption 路径） | `[adoption-smoke] OK`。 |
| `python scripts/validate-governance.py --strict` | `OK — 0 error(s), 0 warning(s)`。 |
| `python scripts/check-agent-harness.py --strict` | `OK — 0 error(s), 0 warning(s)`（含 DESIGN §10 清单数量校验）。 |
| `python scripts/check-anatomy-drift.py` | `OK — 扫描 15 个 ANATOMY.md，0 处漂移`。 |
| `python scripts/sync-codex-adapters.py --check` | `OK — 0 issue(s)`（`bootstrap-project` skill adapter 已生成，未生成对应 command-* skill）。 |
| `python scripts/check-same-commit.py --staged` | `OK —— 5 处结构改动，对应 anatomy 已同变更集更新`。 |
| `git diff --check` | 通过，无空白错误。 |
| `python -m py_compile scripts/bootstrap-project.py lab/evals/bootstrap/run-bootstrap-smoke.py` | 通过。 |

## Commands + results

| command | 结论 |
| --- | --- |
| `node /home/user/.codex/skills/.system/openai-docs/scripts/fetch-codex-manual.mjs` | 失败：官方 manual 响应缺 `x-content-sha256`；随后改用官方 OpenAI/Codex docs 页面核对。 |
| `python scripts/sync-codex-adapters.py` | 写入 34 个 adapter file。 |
| `python -m py_compile scripts/sync-codex-adapters.py scripts/check-agent-harness.py .claude/hooks/pre_tool_guard.py .claude/hooks/format_changed_python.py .claude/hooks/zh_review_advisory.py` | 通过。 |
| `python scripts/sync-codex-adapters.py --check` | 通过：0 issue。 |
| `codex execpolicy check --pretty --rules .codex/rules/default.rules -- sudo ls` | 返回 `forbidden`，匹配 `sudo` 规则。 |
| `codex execpolicy check --pretty --rules .codex/rules/default.rules -- git status --short` | 返回 `allow`，匹配低风险 git inspection 规则。 |
| `codex execpolicy check --pretty --rules .codex/rules/default.rules -- python -m pip install foo` | 返回 `forbidden`。 |
| `codex execpolicy check --pretty --rules .codex/rules/default.rules -- kill 123` | 返回 `prompt`。 |
| `codex execpolicy check --pretty --rules .codex/rules/default.rules -- gh pr create --fill` | 返回 `prompt`。 |
| `python .claude/hooks/pre_tool_guard.py` + synthetic Bash `sudo true` | 预期阻止：exit 2。 |
| `python .claude/hooks/pre_tool_guard.py` + synthetic Bash `python -m pip install foo` | 预期阻止：exit 2。 |
| `python .claude/hooks/pre_tool_guard.py` + synthetic Bash `rm -rf lab/data/foo` | 预期阻止：exit 2。 |
| `python .claude/hooks/pre_tool_guard.py` + synthetic Bash `rm -rf __pycache__` | 通过：exit 0。 |
| `python .claude/hooks/pre_tool_guard.py` + synthetic Bash `git push origin main` | 预期阻止：exit 2。 |
| `CODEX_ALLOW_PUSH_MAIN=1 python .claude/hooks/pre_tool_guard.py` + synthetic Bash `git push origin main` | 通过：exit 0。 |
| `python .claude/hooks/pre_tool_guard.py` + synthetic Codex `apply_patch` 写 `lab/data/foo.txt` | 预期阻止：exit 2，deny protected path。 |
| `python .claude/hooks/pre_tool_guard.py` + synthetic Codex `apply_patch` 写 `README.md` | 通过：exit 0。 |
| `python .claude/hooks/zh_review_advisory.py` + synthetic Codex `apply_patch` | 通过：exit 0。 |
| `python .claude/hooks/format_changed_python.py` + synthetic Codex `apply_patch` | 通过：exit 0。 |
| `python scripts/check-agent-harness.py --strict` | 通过：0 error / 0 warning。 |
| `python scripts/check-anatomy-drift.py` | 通过：扫描 41 个 ANATOMY.md，0 漂移。 |
| `python scripts/validate-governance.py --strict` | 通过：0 error / 0 warning。 |
| `git diff --check` | 通过。 |
| `python .claude/skills/coding-agent-quota/scripts/read_agent_quota.py --format table --codex-jsonl-files 50` | 通过：输出 Codex 与 Claude Code 当前窗口/周额度、reset、source 与 capacity hint。 |
| `python .claude/skills/coding-agent-quota/scripts/read_agent_quota.py --role impl --tier 2 --format table --codex-jsonl-files 50` | 通过：输出 route recommendation、Paseo preference 状态与 provider/model/effort 推荐。 |
| `python .claude/skills/coding-agent-quota/scripts/read_agent_quota.py --role audit --tier 3 --format json --codex-jsonl-files 50` | 通过：JSON 含 providers、usage_velocity、paseo_preferences、route_recommendation。 |
| `python /home/user/.codex/skills/.system/skill-creator/scripts/quick_validate.py .claude/skills/coding-agent-quota` | 通过：Skill is valid。 |
| `python scripts/sync-codex-adapters.py --check` | 通过：0 issue。 |
| `PYTHONDONTWRITEBYTECODE=1 python -m py_compile scripts/check-agent-harness.py .claude/skills/coding-agent-quota/scripts/read_agent_quota.py` | 通过。 |

## Subagent reports

本轮由 Codex 接管已停止的 Paseo agent，并使用隔离 worktree 的 native subagents 做实现/终审切片。
截至当前：#12/#12b/#12c/#13/#14/#15/#16/#17 已 fresh `APPROVE` 并合入本地 main；#13 source
`3704d33` 以 merge `8ee6760` 集成且组合门禁全绿。#18 仍待纳入 main 上的 #13 hook 后完成最终
runtime 矩阵与 fresh review。

## Open issues / blockers（issue #12 part A，本轮新增）

- **A5 的 fresh-Codex-session runtime smoke 已补齐（2026-07-12，监控员编排真实 Codex gpt-5.6-sol）**：
  用 `git archive main` 铺出真实模板内容到临时 repo、跑 `bootstrap-project.py`，再从该 bootstrapped
  repo 启动一次真实 Codex fresh session 观察：guidance（`AGENTS.md`）与 `.agents/skills/`（21 个）均
  确认可见/可发现；project hook（`format_changed_python.py`/`zh_review_advisory.py`）在 trusted 状态下
  仍未观察到可归因的触发痕迹，如实记录为 unknown（非已确认失效，也非已确认生效）。详见 plan doc A5
  条目与 Plan revision log 最新条目。
- issue #12 A/C/B 已依次通过 fresh Codex review 并完成本地 `main` 集成；对应 feature
  branch/worktree 在验证后清理。远端仍未授权、未改动。

## Open issues / blockers（issue #12 part C，本轮新增）

- 本轮运行环境未预装 PyYAML；`validate-governance.py --strict` 等门禁在裸 `python3` 下会因 4 条
  YAML-related warning 变 `FAIL`（该 warning 在改动前后一致存在，用 `git stash` 验证过是预置环境
  缺口，非本轮改动引入）；本轮验证改用 `uv run --with pyyaml python ...` 绕过，全绿。后续在其他
  机器/CI 上重跑，若已装 PyYAML 应无需此 workaround。
- 真实 repo replay（colorama）只覆盖了「Makefile 检测到、跑失败」这一种真实场景；`pass`（原生测试
  真正跑通过）与 `unknown`（超时）两个 smoke 状态目前只有负向 fixture 层面的合成证据，没有真实
  repo 端到端证据——本机缺 `pytest` 是主因（详见 replay 报告 Follow-ups）。
- C4 replay 报告里提到的「`adopt-existing-repo.py` 是否该在 scaffold 时顺带跑一次目标 repo 内的
  `sync-codex-adapters.py`」仍是明确的后续问题，本轮未擅自扩大范围实现。

## Open issues / blockers

- main 仍未 push；如需共享当前 main，需 human 明确批准 push main。
- `.claude/worktrees/case+agent-r1-adoption-replay/` 与 `.claude/worktrees/case+elf-template-replay/`
  仍是本地 worktree checkout；它们在 main 视角显示为 untracked 是嵌套 worktree 的正常表现。
- Codex project hooks 需要用户信任本 repo 的 `.codex/` layer 后才会加载；新增/修改 hook 后 Codex 也需要按其 hook trust flow 审核。
- `coding-agent-quota` 的 Claude 数据来自本地 usage DB/cache；若 Claude Code 将来改变 `/usage` 存储 schema，脚本会降级为 unavailable/stale，需要按新 schema 更新。

## Exact next steps（issue #12 part A，本轮新增）

1. ~~找机会从一个真正 bootstrapped 的 repo 里跑一次 fresh Codex session，补齐 A5 缺的 runtime smoke
   证据~~ **已完成（2026-07-12）**，见上方 Open issues 条目。
2. A/C/B 已完成本地集成；如需共享，等待 human 单独授权 push `main`。

## Exact next steps（issue #12 part C，本轮新增）

1. C 已与 B 的分类/共享 postflight 合同一起通过 27 场景集成 smoke。
2. 是否处理 C4 replay 记录的 in-target-repo adapter sync 后续问题，另开独立 scope，不在本次集成扩张。

## Exact next steps

1. 如需要发布这次双 surface 支持，由 human 决定是否 commit/push main。
2. 后续改 `.claude/agents`、`.claude/skills` 或 `.claude/commands` 时，先跑
   `python scripts/sync-codex-adapters.py`，再跑 validator。
3. 调度 agent 前可运行
   `python .claude/skills/coding-agent-quota/scripts/read_agent_quota.py --format table`
   或显式调用 `$coding-agent-quota`。
4. 若要进一步压测，可用 Codex fresh session 明确调用 `$worktree-pr-flow`、`$command-checkpoint`
   和一个 `.codex/agents/*` custom agent 做端到端 smoke。

## Do-not-forget

- 需要 human 介入/过目的输出默认中文。
- `.claude/` 是 canonical；`.codex/` 与 `.agents/` 是生成/适配层，不手写生成内容。
- 两个 replay case 分支默认作为证据保留，不合入 main。
