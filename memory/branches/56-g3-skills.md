# Branch Status: 56-g3-skills

## Purpose

issue #56（父 issue #52，P7 阶段，D 层「工作流 skills/commands 端到端演练」）：对
`.claude/skills/` 与 `.claude/commands/` 里挑出的 8 个能力，逐一按其 `SKILL.md`/command 正文
用一个真实小任务/干跑走通，记录命令与产物、判 PASS/FAIL/UNAVAILABLE。参考 G4（issue #57）的
证据形态（`lab/docs/audits/qualification/report-g4.{json,md}`、
`memory/branches/57-g4-control-plane.md`）。

## Parent session

都督·统·治理路线（Paseo 主 tab）。本分支执行官：干将·演·工作流（G3，sonnet-5·auto）。

## Branch / base

**实际分支名是 `56-g3-skills`**（session 开始时 gitStatus/任务交代文字写的是
`test/g3-skills-walkthrough`；`git reflog` 显示中途发生过一次
`Branch: renamed refs/heads/test/g3-skills-walkthrough to refs/heads/56-g3-skills`——非本 agent
的 Bash 操作触发，推测是 Paseo/harness 侧的自动 rename，如实记录，供都督核对是否符合预期。
这与 G4 branch report 记录的「分支名与 worktree 目录名不一致」是同一类观察，非本次新增缺陷）。
base = `main` @ `4b0c42c246e1a01d177ba0d5b3ae4452ff11a8cb`
（`docs(memory): G4 收口——#57 经 PR #72 合入关闭，独立复核 APPROVE`）。**exact-base 双检**：
开始时 `git rev-parse HEAD` == `git rev-parse origin/main` == 上述 SHA，worktree clean，
HEAD 与声明 base 完全一致；**push/PR 前二次核对**：`git rev-parse HEAD` 与
`git rev-parse origin/main` 仍均为 `4b0c42c...`（base 全程未移动），无需 rebase/重放。

## Worktree

`/home/user/.paseo/worktrees/1kaz3672/g3-skills-walkthrough`（Paseo 分配的 linked worktree）。

## Linked issue / PR

issue #56（子任务），父 issue #52（P7）。PR 见下方「Exit condition」（待本文件所在 commit 完成
后开，不 merge）。

## Owned paths

`lab/docs/audits/qualification/report-g3.md`、`memory/branches/56-g3-skills.md`、
`memory/session-tree.md`（仅追加 `issue-56-g3-skills` 一行 + boundary note，不动既有内容）、
`lab/docs/audits/README.md`（新增一句话说明 report-g3 定位）。未产出 `report-g3.json`——本轮
证据以 markdown 单一形态为准（G3 是人工/agent 逐条走查而非确定性脚本产出，不像 G1/G4 有
runner 天然产出结构化 JSON，故不强造一份）。

## Forbidden paths

`lab/data/`、`lab/runs/`、`lab/models/`、`wandb/`、`lab/infra/private/`（硬边界，未触碰）；
真实 `plans/`、`memory/doc-lifecycle.yaml`、`lab/research/experiment-ledger.yaml`（T-G3-4/
T-G3-8 的治理型注册表隔离对象，只在 `/tmp` fixture 里演练，绝不落到这些真实路径——见下方
「隔离零泄漏核验」）；不改任何 `SKILL.md`/command 正文（non-goal）；不 `gh issue create` 真发
（T-G3-7 non-goal）；不启动真训练（T-G3-8 non-goal）；不 push main、不 merge、不打 tag。

## Anatomy impact

无结构改动（沿用既有 `lab/docs/audits/qualification/` leaf 目录，参照 G4 先例）。若
`lab/docs/audits/README.md` 补一句话说明，属于既有条目扩写，非新增结构，参照 `check-same-commit.py`
对该改动的判定结果记录在下方「S2 变更自检清单」。

## Claim / evidence impact

无。本分支不写 `lab/research/claims.yaml`/`evidence.yaml`——G3 场景报告是运行证据（JSON+MD），
不是对外 paper-grade claim，与 issue #54/#59/#57 的既有先例一致。

## Plan doc

无独立 plan doc；方案细节即本分支执行官接到的任务交代正文（human 已在交代里逐条拍板 8 个
T-ID 与隔离纪律），照案执行。

---

## S2 变更自检清单（T-G3-1，`worktree-pr-flow` 实走）

### 1. 变更分类矩阵

| 变更类型 | 是否命中 | 说明 |
| --- | --- | --- |
| 改结构 | 否（轻量） | 新增文件落在既有 leaf 目录（`lab/docs/audits/qualification/`、`memory/branches/`），不改变「东西在哪/谁负责」；`lab/docs/audits/README.md` 若补一句描述，是既有条目扩写，非结构迁移，沿用 G4 先例不新增独立 `ANATOMY.md` |
| 改承诺 | 否 | 不改任何 `.agent/*.md` policy 正文、不改任何 validator/hook 行为语义 |
| 改操作 | 否 | 不改任何 `SKILL.md`/`.claude/commands/*.md` 正文（明确 non-goal） |
| 改决策 | 否 | 本次是测试/证据性质，未产生需要 `DECISIONS.md` 记录的模板级设计决策；过程中发现的观察记入本文件「发现的观察」小节，不升级为决策 |

### 2. 三项前置声明

| 声明 | 内容 |
| --- | --- |
| Invariant | 不改任何 skill `SKILL.md` 正文；不写脏真实治理注册表（`plans/`、`memory/doc-lifecycle.yaml`、`lab/research/experiment-ledger.yaml`、`lab/data\|runs\|models`）；不真发外部副作用（`gh issue create`、真训练启动、merge、push main）；发现的缺陷只报告，不顺手修 |
| Variation axis | 每个 skill 走一个真实小任务/干跑并留证据（角色/输入/输出/停止条件），判 PASS/FAIL/UNAVAILABLE |
| Non-goals | 不重建通用测试框架；不修复过程中发现的任何缺陷；除本分支自身（T-G3-1）外不再嵌套一个 worktree-pr-flow 实例；不测 user 全局 skills，只测 repo-local `.claude/skills/` |

### 3. exact-base 双检 + 路径自报自查

- **开始时**：见上方「Branch / base」，HEAD == origin/main == 声明 base，worktree clean。
- **副作用动作前（push/PR 前）**：待补——见下方「Commands run」末尾的第二次 exact-base 复核。
- **预期改动路径自报**（动手前列出）：
  - `lab/docs/audits/qualification/report-g3.md`（+ 可选 `.json`）——新增
  - `memory/branches/56-g3-skills.md`——新增（本文件）
  - `memory/session-tree.md`——追加一行 + 一小节（已由 T-G3-5 完成）
  - `lab/docs/audits/README.md`——可能追加一句话说明
  - `/tmp/g3-*` 系列 fixture 脚本——不进 repo，仅本地临时产物
  - 实际 `git diff --stat` 对照见「Commands run」末尾。

### 4. 验证纪律

只跑与本分支改动相关的定向命令：`validate-governance.py`、`check-anatomy-drift.py`、
`check-doc-lifecycle.py`、`check-same-commit.py --staged`；不跑无关全量 suite。命令与输出见
下方「Commands run」，均为确切命令+结果，不推断补全。

### 5. 副作用授权分级

本分支涉及的副作用动作：`git push`（topic 分支，按 `.agent/action-boundary.md` 属 allow 档）、
`开 PR`（需 human gate，本分支只开 PR 不 merge）。无依赖变更、无有损 git 操作。

---

## Current state

**已完成，8/8 T-ID 有结论**（6 PASS / 1 PASS-with-real-finding / 1 UNAVAILABLE-by-design），
隔离干跑零泄漏核验通过，治理门禁全绿。

### 8 个 T-ID 逐项结论

| T-ID | skill/command | 结论 | 证据指针 |
| --- | --- | --- | --- |
| T-G3-1 | `worktree-pr-flow` + S2 清单 | ✅ PASS | 本文件「S2 变更自检清单」小节 |
| T-G3-2 | `spawn`（in-session） | ✅ PASS | `report-g3.md#T-G3-2` |
| T-G3-3 | `subagent-routing` | ✅ PASS（1 条非阻断观察） | `report-g3.md#T-G3-3` |
| T-G3-4 | `interactive-plan-doc` | ✅ PASS | `report-g3.md#T-G3-4` |
| T-G3-5 | `checkpoint`/`session-boundary-control` | ✅ PASS | `report-g3.md#T-G3-5` |
| T-G3-6 | `pr-review`（对 PR #72） | ✅ PASS（发现 1 条真实 MINOR 缺陷） | `report-g3.md#T-G3-6` |
| T-G3-7 | `template-feedback` | ⚪ UNAVAILABLE（by design） | `report-g3.md#T-G3-7` |
| T-G3-8 | `experiment-workflow` | ✅ PASS | `report-g3.md#T-G3-8` |

完整逐项证据（角色/输入/输出/停止条件/命令输出）见 `lab/docs/audits/qualification/report-g3.md`。

## T-G3-5 checkpoint 演练产物（`checkpoint` / `session-boundary-control`）

> 本节是 `checkpoint` command 的干跑产物：内容taxonomy 与 `.claude/agents/checkpoint-writer.md`
> 一致（current objective / constraints / files inspected / files modified / decisions /
> commands+tests / subagent reports / open issues / exact next steps / do-not-forget），但
> **刻意重定向落点到本分支报告**而非真实 `memory/current-status.md`——那是父 session
> （都督·统·治理路线）维护的文件，本次 G3 走查不覆盖它的主体，只在完成/交接时由都督自己决定
> 要不要摘要收进去。这是本次 T-G3-5 演练对「产物写进你自己的 branch 报告区」这条边界指令的
> 具体落地方式。

- **current objective**：走通 G3 的 8 个 T-ID，留证据，开 PR（不 merge）。
- **constraints**：不改 SKILL.md 正文；治理型注册表（plans/doc-lifecycle/experiment-ledger）
  只能在隔离 fixture 里演练；不真发外部副作用；不碰 `lab/data|runs|models`。
- **files inspected**：见「Commands run」引用的所有 `SKILL.md`/命令/模板/policy 文件。
- **files modified（至此）**：`memory/session-tree.md`（T-G3-5，追加）、
  `memory/branches/56-g3-skills.md`（本文件）。
- **decisions made**：T-G3-4/T-G3-8 用 `tempfile.mkdtemp()+git init` 隔离 fixture、Python
  脚本而非 Bash `rm`/`mv`（避开 doc-lifecycle hook 对变量路径删除/移动命令的拦截，做法沿用
  `memory/feedback_doc_lifecycle_hook_scratch_tests.md` 的既有经验）；checkpoint 演练重定向到
  本文件而非真实 `current-status.md`（理由见上）。
- **commands / tests run**：见下方「Commands run」表。
- **subagent reports**：`斥候·查·spawn演示`（T-G3-2）、subagent-router-agent（T-G3-3）、
  `师爷·审·G3边界`（T-G3-5 session-boundary 部分）。
- **open issues**：T-G3-6 发现的 G4 `run-g4-scenario.py` UNAVAILABLE 语义死代码 + 无 paseo 机器
  上 T-G4-6 分支 a 误判 FAIL 的 MINOR 缺陷（不属于本分支范围，只报告，交都督/后续处理）；T-G3-3
  发现的 `subagent-routing` SKILL.md 步骤 3 与 `subagent-router-agent` 工具边界不一致（同样只
  报告不修复）。
- **exact next steps**：push 本分支 → 开 PR（base main，正文中文，8 T-ID 结论 + 证据路径 + 上述
  两条发现）→ 不 merge，等独立 verifier + human。
- **do-not-forget**：PR 正文中文；不 merge，等独立 verifier + human；发现的真实缺陷立即停下
  回报，不扩大测试面（已照做：T-G3-6/T-G3-3 的发现均只记录，未顺手修复任何 G4 代码或
  subagent-router-agent 定义）。

## Commands run

| command | 结论 |
| --- | --- |
| `python scripts/agent_name_set.py "干将·演·工作流"`（首次路径错，改用 `.claude/hooks/agent_name_set.py`） | 已命名，写 `.agent-identity` + roster + state |
| `git rev-parse HEAD` / `git rev-parse origin/main`（开始时） | 均为 `4b0c42c...`，exact-base 双检通过 |
| `python3 .claude/skills/spawn/scripts/list_agents.py` | 输出 16 个 agent 完整发现表（T-G3-2） |
| `Agent(repo-researcher, "斥候·查·spawn演示")` | 正确署名回报，只读未改文件（T-G3-2） |
| `Agent(subagent-router-agent)` | 产出完整 launch packet，如实标注 quota 字段 PENDING 并说明原因（T-G3-3） |
| `uv run --with pyyaml python3 /tmp/g3-plan-doc-fixture-driver.py` | 三态 positive 全绿 + 两个 negative 均正确拒绝，零泄漏（T-G3-4） |
| `Agent(session-boundary-agent, "师爷·审·G3边界")` | 真实更新 `memory/session-tree.md`（新增 1 行 + 1 节），核实其余内容未动、`current-status.md` 未碰（T-G3-5） |
| `gh pr view 72` / `gh pr diff 72` | 正常读取，PR #72 已合入 main |
| `Agent(code-reviewer, "师爷·审·PR72复盘")` | 独立 fresh review，2 MINOR + 2 NIT，发现 1 条真实缺陷（T-G3-6） |
| `python3 /tmp/g3-template-feedback-fixture-driver.py` | 原生 UNAVAILABLE 判定 + fixture 打包机制均如预期（T-G3-7） |
| `uv run --with pyyaml python3 /tmp/g3-experiment-workflow-fixture-driver.py` | 两态 positive 全绿 + 1 个 negative 正确拒绝，零泄漏（T-G3-8） |
| `uv run --with pyyaml python scripts/validate-governance.py --strict` | `OK — 0 error(s), 0 warning(s)`（含 anatomy-drift/doc-lifecycle/outcome-ledger/experiment-state/provenance-chain(13 pass)/capability-catalog(46 项) 全部子检查） |
| `uv run --with pyyaml python scripts/check-anatomy-drift.py` | `OK — 扫描 17 个 ANATOMY.md，0 处结构漂移` |
| `uv run --with pyyaml python scripts/check-doc-lifecycle.py` | `OK — 0 error(s), 0 warning(s)` |
| `git add <4 files>` + `uv run --with pyyaml python scripts/check-same-commit.py --staged` | `OK —— 2 处结构改动，对应 anatomy 已同变更集更新` |
| `git rev-parse HEAD` / `git rev-parse origin/main`（push/PR 前二次核对） | 均仍为 `4b0c42c...`，base 全程未移动 |
| `git diff --stat`（对照预期改动路径自报） | 实际改动 = 预期改动（`report-g3.md` 新增、`memory/branches/56-g3-skills.md` 新增、`memory/session-tree.md` 修改、`lab/docs/audits/README.md` 修改），无多余路径、无遗漏路径 |

## Latest result

8/8 T-ID 全部有结论（6 PASS / 1 PASS-with-real-finding / 1 UNAVAILABLE-by-design），治理门禁
全绿，隔离干跑零泄漏核验通过。

## 发现的观察（只报告，不顺手修）

1. **分支名中途漂移**（如实记录，非本 agent 操作触发）：session 开始时的 gitStatus 与任务交代
   文字写的是 `test/g3-skills-walkthrough`，`git reflog` 显示中途发生一次
   `Branch: renamed refs/heads/test/g3-skills-walkthrough to refs/heads/56-g3-skills`——推测是
   Paseo/harness 侧自动 rename，非本 agent 的 Bash 操作。与 G4 branch report 记录的「分支名与
   worktree 目录名不一致」是同一类现象，供都督核对是否符合预期。开 PR 时会用实际分支名
   `56-g3-skills`。
2. **T-G3-6 真实发现（MINOR，PR #72 已合入代码）**：`lab/evals/control-plane/run-g4-scenario.py`
   的 UNAVAILABLE 降级语义从未真正接线（死代码路径）；更实质地，T-G4-6 负例分支 a 在没装
   `paseo` CLI 的机器上会误判 FAIL 而非优雅降级——与该分支自己 branch report「观察 #3」的自述
   矛盾。详见 `report-g3.md#T-G3-6`。本轮不修复，只报告。
3. **T-G3-3 真实发现（非阻断，能力/文档不一致）**：`subagent-routing` SKILL.md 步骤 3 要求
   router agent「运行」quota 脚本，但 canonical `subagent-router-agent` 的 `tools:` 只声明
   `Read`，结构上做不到。详见 `report-g3.md#T-G3-3`；T-G3-7 用这条观察作为假想下游反馈的
   fixture 内容做了双重演示。
4. **本地环境裸 `python3` 缺 PyYAML**（非本轮引入，既有环境缺口，与 P3/P4/G4 等历史分支记录
   一致）：全程用 `uv run --with pyyaml` 绕过。

## Open risks

- 上述观察 2/3 是真实缺陷/不一致，但按任务交代「发现基础缺陷阻断 G3 立即停下」的判断标准——
  两者均不阻断 G3 walkthrough 本身继续（不是"skill 测不了"级别的阻断），故记录后继续完成
  全部 8 个 T-ID，未提前终止。是否需要为观察 2/3 单独开 issue，交都督裁定。
- 本地环境缺 PyYAML 的 workaround（`uv run --with pyyaml`）与既有分支一致，未跨机验证，风险低。

## Exit condition

- [x] 8 个 T-ID 全部有结论与证据（PASS/FAIL/UNAVAILABLE）。
- [x] 隔离干跑项（T-G3-4/T-G3-8，+T-G3-7 fixture）零泄漏核验通过。
- [x] 治理门禁（`validate-governance.py --strict`）+ `check-same-commit.py --staged` 回归绿。
- [x] branch status 完整（本文件）。
- [ ] commits push 到当前分支（`56-g3-skills`）。
- [ ] 开 PR（base main，正文中文，说明 8 T-ID 结论 + 证据路径 + 2 条真实发现），不 merge，等
      独立 verifier + human。
