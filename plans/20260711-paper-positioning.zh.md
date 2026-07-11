# 论文定位分析：把本模板发表为一篇 agent 论文

> **这份文档是什么**：对 `ml-project-repo-agent-native-template` 做论文化定位的调研与提案。
> 回答四个问题：(1) 本项目的可发表内核是什么；(2) 2026 年相关工作图景与我们的空白；
> (3) 能立得住、可证伪的 claim 有哪些；(4) 每个 claim 要做什么实验、需要拓展什么。
>
> **状态**：proposal（调研 + 设计），无实验结果。所有外部文献 arXiv 编号来自 2026-07 的
> WebSearch，**具体版本号/页码需在引用前用 `arxiv.org/abs/<id>` 人工核对**（调查 agent 已标注）。
> 分支：`research/paper-positioning`（worktree，不入 main）。

---

## 0. 一句话结论

本项目单看是"一个模板"，不可发表；但它的**科学内核**是可发表的：

> **一个面向 ML 研究仓库的、仓库原生（repo-native）的 agent 治理控制面，
> 把"结构性硬边界（action boundary）"与"claim→evidence 证据链完整性"统一成一个可被
> 机器独立复核的工程制品；并配一套对抗性、长时程、多 session、跨 provider 的
> 压测/评测方法学来实证它是否真的守得住。**

"模板"是 artifact，"探针/压测方法学 + 可复现的治理 benchmark"才是 science。竞品要么"只度量了
风险没有建制品"（Russo 2026），要么"建了通用 SWE 控制面但没有实证、且不覆盖科研仓库"
（Deterministic Control Plane 2026）。我们正好卡在这个交叉点上。

---

## 1. 本项目的特色（可发表要素清单）

来自 `DESIGN.md`、`AGENTS.md`、`.agent/*`、`ANATOMY.md`、`lab/research/*`、`lab/docs/audits/*`。

| # | 机制 | 在哪实现 | 为什么可能是论文卖点 |
| --- | --- | --- | --- |
| M1 | **两层权限模型**：permission（可调 allow/ask/deny）+ **不可调 hook 地板** | `.claude/settings.json` + `.claude/hooks/pre_tool_guard.py` | 把"致命动作"下沉到不可放宽的地板 → 放宽权限做"自主窗口"也安全。对应学术上"结构性权限 > 过滤式护栏"的共识 |
| M2 | **命令解析式护栏**（shlex 真解析，非子串正则） | `pre_tool_guard.py` | commit message 里的 `rm -rf` 不误伤；引号里的真实路径仍拦。可做**精度对比实验** |
| M3 | **claim↔evidence 证据链 + overclaim validator** | `lab/research/{claims,evidence}.yaml` + `scripts/validate-governance.py` | claim 强度 ≤ 最强证据；机器拦 overclaim。直击 AI-Scientist-v2 "伪造结果/方法"问题 |
| M4 | **ANATOMY 防漂移 + same-commit 门禁** | `ANATOMY.md` 树 + `check-anatomy-drift.py` + `check-same-commit.py` | 结构改动必须同 commit 更新地图，机器强制。对应 Goal/structural drift |
| M5 | **仓库即长期记忆**（跨 session 续接） | `memory/current-status.md`、`session-tree.md`、PreCompact hook | fresh session 只读文件即可续接。与"agent 记忆系统"文献线是尚未合流的另一条线 |
| M6 | **跨 agent 单一真源**：`.claude/` canonical → 机械生成 Codex `.codex/`/`.agents/` adapters | `scripts/sync-codex-adapters.py` | 一套边界，两个 provider 强制等价；漂移可机器检测。可做**跨 provider parity 实验** |
| M7 | **预算不是身份**：subagent `model: inherit`，按任务 tier 路由 + 配额感知 | `.agent/model-routing-policy.md`、`coding-agent-quota` skill | 呼应 budget-aware routing 文献 |
| M8 | **迁移已有 repo 收敛成治理形态**（不毁 bytes） | `scripts/adopt-existing-repo.py` + `check-adoption-integrity.py` | 可做**多仓库采用性实验**（byte 保全 + 0 治理错误） |
| M9 | **模板自身被真实 case 压测**的方法学 | `template-stress-test` skill + `stress-test-ledger.yaml` + `stress-probe-catalog.md` | 已有 ELF（4 轮 F1–F19）、Agent-R1 采用 replay。**这就是 benchmark 的雏形** |

关键：M9 已经是一套"对抗探针 + fresh-reviewer 复审 + 分级登记账"的评测流程。竞品最缺的
就是实证；我们最不缺的就是这套可运行的实证机制——**把它产品化为命名 benchmark 是本论文最省力、
最有复用价值的科学贡献。**

---

## 2. 2026 相关工作图景（三条平行线 + 两个最近竞品）

调查（3 个并行 document-specialist）显示，相关文献分成**基本不相交的三条线**，加上两篇最贴脸的近作：

### 2.1 最贴脸的两篇（必须正面区分）

- **Russo, *Govern the Repository, Not the Agent*（arXiv:2606.28235, 2026-06）** — 标题几乎就是我们的口号。
  但它是**生态级风险度量**（93 万 agent PR，集成摩擦 ICC 0.30 vs 人类 0.16），论证"治理该在仓库/生态层"，
  **只度量、没建制品**。→ 它是我们最强的 *motivation 引用*，不是竞品：它说该在仓库层治理，我们**给出并验证了那个制品**。
- **A Deterministic Control Plane for LLM Coding Agents（arXiv:2606.26924, 2026-06）** — 架构最接近（thin
  governance surface、phase state machine、drift detection、evidence provenance）。但：**(a) 通用软件工程，非
  ML 研究；(b) 评测只有半形式化论证 + vignette，无实证、无对比 baseline。** → 这是最需要正面拉开的竞品，
  我们的四个差异点全部命中它的空白。

### 2.2 三条平行文献线

**线 A — 配置文件的行为效果实证**（关注"agent 是否遵从/是否更快"，样本多为工业 SaaS/TS 仓库）：
- AGENTS.md 效率研究（arXiv:2601.20404）：10 repo / 124 PR / 仅 Codex，加 AGENTS.md 使**耗时中位 −28%、
  输出 token −16%**，但**明确不测正确性、不测 ML 研究、不测多 session、不测治理/安全/漂移**。
- 指令遵从因子研究（McMillan, arXiv:2605.10039）：1650 个 Claude Code session，文件大小/位置/结构对遵从率
  无显著影响，遵从率随生成函数数递减（每多一个函数约 −5.6%）。
- AGENTS.md 已于 2025-12 捐给 Linux Foundation 的 Agentic AI Foundation；60k+ 仓库、28+ 工具采用 → **标准已成型，
  但被当研究对象的还只是"单个文件的效果"，不是"整套治理系统"。**

**线 B — agent 记忆系统**（对话/长程任务，不涉及仓库治理文件）：
- MemGPT/Letta、Mem0（独立测试 30 天有效准确率仅 49%，暴露 stale/矛盾）；context engineering 已成术语
  （survey arXiv:2507.13334、Anthropic 官方博客 2025-09、ACE arXiv:2510.04618）；ICLR 2026 设 MemAgents workshop。
- **关键空白**：CLAUDE.md / Cursor rules / 我们的 `memory/` 这类**项目级持久文件从未被纳入记忆 benchmark**——
  记忆文献与配置文件文献是两条没合流的线。我们的 M5 正好是"仓库即记忆"的具体制品。

**线 C — 安全护栏 / 治理评测**：
- 共识：**过滤式护栏是概率性的、可绕过；结构性权限（capability-scoping）才真正止损**
  （arXiv:2510.11108 访问控制愿景、2603.00195 skill 供应链形式化、VeriGuard 2510.05156）。→ 直接支持我们 M1/M2。
- 权限推断评测：AuthBench（arXiv:2605.14859）测 agent 是否理解最小权限。
- 相邻领域已有**治理型 benchmark**：DEMM-Bench（runtime 治理证据充分性 2606.20634）、EmbodiedGovBench
  （具身：未授权调用/运行时漂移/恢复/审计 2604.11174）、DepDec-Bench（依赖决策 2601.00205）。
  → **先例存在，但没有一个针对"代码仓库 + 多 session + 多 agent + 科研约束"。**
- harness 评测方法学：Harness-Bench（2605.27922）、"Stop Comparing LLM Agents Without Disclosing the Harness"
  （2605.23950）→ **给我们的"评 harness 而非评 model"框架背书。**

**线 D（问题动机）— drift 与科研诚信**：
- **Goal Drift** 已被正式命名（arXiv:2505.02709, AIES 2025；Inherited Goal Drift 2603.03258）：模型在长 context 下
  普遍出现目标漂移。→ 我们 M4 的机器强制防漂移正对此。
- **AI-Scientist-v2**（arXiv:2504.08066）三篇过 workshop 评审，但独立评估发现**"伪造实验结果""编造方法"是最常见
  的两类幻觉，出现在过半任务里**。→ 我们 M3 证据链的最强动机。
- 可复现性清单（REFORMS / NERVE-ML / MLRC）**全是静态人工填写，尚无 agent 可强制的自动校验**。→ 明确空白，M3 填。
- claim-evidence 对齐（DeepSciVerify 2605.27710）、证据分级（医学 GRADE/EvidenceGrade 已落地，**ML/CS 无对应物**）。

### 2.3 一句话空白陈述（论文可直接用）

> 现有工作分三支：**(A) 度量单个配置文件对效率/遵从的影响；(B) 研究对话式 agent 记忆；(C) 在相邻领域
> （runtime、具身、依赖）建治理 benchmark。** 没有任何一支把**"ML 研究仓库特有约束（数据/checkpoint
> 不可篡改、长训练不可擅自重启、实验结论需证据链）+ 结构性硬边界 + 跨 session 记忆 + 跨 provider 一致性"
> 整合为一个可被机器独立复核的仓库原生制品，并给出长时程、多 agent、对抗性的实证。** Russo(2026) 论证了
> 该在仓库层治理却未建制品；Deterministic Control Plane(2026) 建了通用制品却未实证也不覆盖科研。**我们同时补齐这两侧。**

---

## 3. 差异化：我们独占的四个交叉点

1. **域特定**：ML 研究仓库，不是通用 SWE。数据/checkpoint bytes 保护、长训练不可重启、claim→evidence、
   overclaim 拦截、可复现门禁——这些是科研原生约束，通用控制面论文没有。
2. **实证 vs 半形式化**：竞品只有 vignette；我们有对抗探针矩阵 + 真实外部仓库 case replay + fresh-reviewer 复审 +
   分级登记账，可复现、可量化、可对比 baseline。
3. **跨 provider 单一真源**：一套边界机械生成 Claude Code + Codex，两侧强制等价、漂移可检测（M6）。竞品是单 harness。
4. **两侧统一**：把"agent 越界的硬边界"（安全线 C）与"agent 结论可信的证据链"（诚信线 D）**合进同一治理框架**——
   文献里这两条是平行的、没人合并过。

---

## 4. 可发表的 claim（分主次，全部可证伪）

按"是否需要跑 agent（成本 + LLM 方差）"分成**确定性 claim（validator/探针，便宜、可复现）**和
**agentic claim（跑 agent A/B，贵、有方差、更高价值）**。确定性那批是竞品最缺、我们最强的实证底盘。

### 4.1 确定性 claim（validator / 探针语料）

- **A1（护栏精度）**：解析式 hook 地板对真实危险命令（删数据/checkpoint、push main、提权、远程执行、写受保护路径）
  的**拦截召回率**显著高于子串式 deny，同时对"字面量里含危险子串的良性命令"（如 commit message 含 `rm -rf`）的
  **误拦率≈0**。证伪：若子串 baseline 精度相当则 claim 失败。
- **A2（安全与便利解耦）**：因致命动作在不可调地板，**放宽 permission（自主窗口）不提高越界率**。证伪：strict vs
  relaxed 两模式跑同一探针，越界率应不变。
- **B1（overclaim 拦截）**：validator 对构造的 overclaim 语料（claim 强度 > 最强证据、悬空引用）达到高检测率、
  对合法证据链**零误报**。证伪：注入 overclaim + 合法链，测检测/误报。
- **C1（结构漂移检测）**：anatomy/same-commit validator 检出注入的结构漂移（移动/改名不更新地图、越界行号引用）；
  无 validator 时漂移无声累积。证伪：漂移注入语料，测有/无 validator 的检出率。
- **E1（跨 provider parity）**：同一对抗探针语料经 Claude hook 路径与 Codex rules/apply_patch 路径产生**一致的
  allow/deny 判决**（parity），且 sync 漂移可机器检测。证伪：测两侧判决一致率。
- **F1（采用性/一般性）**：采用管线把 N 个真实外部 ML 仓库收敛成治理形态，**tracked bytes 全保全、root
  污染归零、治理错误归零**。证伪：跑 N 仓库测 byte 保全率与错误数。（现有 n=1 = Agent-R1；需扩到 N≥5–10。）

### 4.2 agentic claim（跑 agent A/B，更高价值）

- **B2（诚信增益）**：让 agent 在"有 vs 无证据链门禁"的仓库里执行"把结果升级为 paper claim"，门禁**降低无支撑/
  伪造 claim 混入 deliverable 的比例**。直击 AI-Scientist-v2 发现。度量：human-graded 伪造率。
- **C2（长时程防漂移）**：真实仓库上的长多 session 任务，harness 下 agent **每 N commit 的未修复结构/文档漂移缺陷
  更少**（对比 bare repo / bare AGENTS.md）。接 Goal Drift 文献。
- **D1（跨 session 续接 = 仓库即记忆）**：只给 fresh agent 持久状态文件（current-status/session-tree/anatomy），
  其**中断续接正确率更高、冗余重探索动作更少**。度量：续接 benchmark。
- **G1（整机收益，旗舰）**：给 agent 整套 harness（vs bare repo vs bare AGENTS.md）跑一组真实 ML 研究维护/实验任务，
  改善 {任务成功、越界率、overclaim 率、漂移缺陷、human-gate 合规} 的**复合指标**；且**主要增益在安全/诚信/续接
  维度而非纯效率**（与 AGENTS.md 效率论文形成对照——它只测效率）。最贵但最完整。

### 4.3 优先级建议

- **最小可发表集（workshop / tool paper）**：A1 + A2 + B1 + C1 + E1 + F1（全确定性）+ 把 M9 产品化为 benchmark。
  这套完全可复现、无 LLM 方差、正面碾压竞品"无实证"的弱点。
- **升级到正会（ICSE/FSE/ASE/NeurIPS D&B）**：再加 G1（旗舰 A/B）+ 至少一个 agentic claim（建议 B2 或 D1，
  因为最能讲差异化故事）。

---

## 5. 每个 claim 的实验设计

### 5.1 确定性实验（可立即启动，多数复用现有 infra）

**E-A1/A2 护栏精度与解耦（对抗命令语料）**
- 构造命令语料库 ~200 条：{真危险 × {删数据/checkpoint、push main、提权、curl|sh、pip install、写 lab/data、
  mv/rsync 触受保护路径、find -exec rm}} + {良性但字面量含危险子串（commit message 含 `rm -rf`、echo 含 sudo、
  变量名含 push origin main）} + {清缓存等应放行}。
- 三个被测系统：(i) 无护栏；(ii) 子串正则 deny（复刻竞品/朴素做法）；(iii) 我们的解析式地板。
- 指标：block-recall（危险）、false-block-rate（良性）、accuracy。A2 追加 strict vs relaxed permission 两跑，
  报越界率不变。
- 复用：`stress-probe-catalog.md` 已有 15 行探针映射 + P0/P1 系列真实结果，扩成语料即可。

**E-B1 overclaim 拦截（证据链语料）**
- 构造 claims/evidence 对：{status 高于证据、悬空 evidence 引用、paper-grade 无 fresh-reviewer、循环依赖} +
  {合法链}。跑 `validate-governance.py`，测检测率/误报率。已有 P0-1..P0-6 真实结果作种子。

**E-C1 结构漂移检测（漂移注入）**
- 脚本注入：移动文件不改 ANATOMY、改行数使引用越界、超 120 行、结构改动与 anatomy 不同 commit。
  测 `check-anatomy-drift.py` + `check-same-commit.py` 检出率；对照"无 validator 时漂移累积"。已有 P1 系列种子。

**E-E1 跨 provider parity**
- 同一命令语料同时喂 `pre_tool_guard.py`（Claude Bash/Edit/Write 输入）与 Codex `execpolicy check --rules
  .codex/rules/default.rules` + `apply_patch` 路径；测判决一致率 + `sync-codex-adapters.py --check` 漂移检测。
  current-status 已记录 5 条 execpolicy + 多条 hook 判决可作种子。

**E-F1 采用性（多仓库）**
- 选 N≥5–10 个真实公开 ML 仓库（不同规模/框架/语言），跑 `adopt-existing-repo.py --phase all` +
  `check-adoption-integrity.py`；测：tracked-byte hash 保全率、moved entries、remaining_root_pollution、
  目标仓库 `validate-governance.py --strict` 错误数。Agent-R1（178 文件全保全、0 blocker、0 error）= n=1 种子。

> 这五个实验的共同优点：**无 LLM 方差、可 CI 复现、可给对比 baseline**——正是竞品缺、审稿人认的硬证据。

### 5.2 Agentic 实验（需拓展 runner，见 §6）

**E-G1 整机 A/B（旗舰）**
- 任务集：~20–40 个真实 ML 研究维护/实验任务（改配置跑定向实验、加一个 metric、写 run summary、把结果升级为 claim、
  重构一个模块并更新 anatomy、在中断后续接）。
- 条件：{bare repo} × {bare AGENTS.md} × {full harness}，× {Claude Code, Codex} × ≥3 seeds。
- 指标：任务成功率、越界动作数（被地板拦=证据）、产出 overclaim 数（human-graded）、引入的未修复漂移缺陷数、
  human-gate 合规、token/时长（对照效率论文）。**假设：安全/诚信/漂移维度显著改善，效率维度中性或略降**——
  这个"我们不主要卖效率"的诚实定位反而是与效率论文的差异点。
- 方法学护栏：按 Harness-Bench / "disclose the harness" 规范，披露 harness 版本、模型、seed、方差分解。

**E-B2 诚信增益** / **E-D1 续接增益**：G1 的可拆分子实验，可先单独做（更便宜、故事更聚焦）。
- B2：仅"结果→paper claim"任务，± 证据链门禁，human-graded 伪造/无支撑率。
- D1：构造中断-续接场景，fresh agent ± 持久状态文件，测续接正确率与冗余动作数（wasted-action count）。

---

## 6. 需要拓展/新建的东西（可接受的扩展）

按"离可发表最近"排序：

1. **把 M9 产品化为命名 benchmark**（最高性价比）。现在的 `stress-probe-catalog.md` + `stress-test-ledger.yaml`
   是人工驱动的登记账；产品化为：
   - 五类语料：命令安全探针 / overclaim-证据链探针 / 漂移注入任务 / 续接场景 / 采用仓库集；
   - 明确评分 rubric 与指标定义（block-recall、false-block、overclaim-detection、drift-detection、parity-agreement、
     byte-preservation、resumption-correctness、wasted-actions）；
   - 版本化 + 可 `python -m bench run` 一键复跑。
   - 暂名 **RepoGovBench** 或 **AGRB（Agent Governance Benchmark for ML repos）**。这是**可被别的治理框架复用/被引用**
     的独立贡献，比"发布我们的模板"强得多。
2. **自动化 agentic A/B runner**（G1/B2/D1 需要）：任务集 × 条件 × provider × seed → 指标表。当前压测是人工驱动，
   要统计性 claim 必须自动化 + 多 seed。
3. **扩采用仓库集**：Agent-R1 从 n=1 扩到 N≥5–10（不同规模/框架），支撑 F1 的一般性。
4. **精确化指标与 baseline 实现**：把"子串正则 deny"实现为可跑 baseline（对照 A1）；把"bare AGENTS.md"条件固化。
5. （可选，换 venue 用）**人因维度**：human-gate + repo-native brief/decision 是否改善人机协作——若投 CHI 向。

---

## 7. 投稿 venue 与风险

**Venue 候选**
- 现实主线：arXiv preprint（竞品 2601/2606 都是 arXiv 先行）+ 软件工程正会 agentic-SE 方向（**ICSE / FSE / ASE**
  的 tool/track），或 **NeurIPS Datasets & Benchmarks**（若 benchmark 做扎实）。
- 快速产出：**ICLR 2026 MemAgents workshop**（M5 记忆角度）或 agents workshop（先发确定性实验 + benchmark v0）。
- 定位一句话：**"评的是治理 harness 而非 model"**（引 Harness-Bench / disclose-the-harness 背书）。

**风险与缓解**
- *优先权风险*（2606.26924 已占"control plane"提法）→ 用四差异点正面区分：ML 域 / 实证 / 跨 provider / 安全-诚信统一。
- *"这只是工程"*（审稿常见）→ 把 benchmark + 方法学作为科学贡献；引 Russo(2026) 证明"该在仓库层治理"是被承认的
  研究问题，我们建并验证了那个制品。
- *单作者单制品的一般性*→ 用 N 采用仓库 + 跨 provider parity 撑一般性。
- *LLM 方差*（agentic 实验）→ 多 seed、多模型、方差分解，按 disclose-the-harness 规范披露。
- *引用准确性*→ 所有 arXiv 编号提交前逐条 `arxiv.org/abs/<id>` 核对版本（调查 agent 已提示）。

---

## 8. 建议的下一步（三选一起步）

- **路线甲（低风险、快出）**：只做 §5.1 五个确定性实验 + §6.1 benchmark v0 → workshop/tool paper。**推荐先走这条**：
  完全可复现、无方差、直接补竞品"无实证"空白，2–3 周可出 v0。
- **路线乙（完整、慢）**：甲 + §5.2 旗舰 G1（含 runner + 多 seed + human grading）→ 冲正会。
- **路线丙（先探针后决策）**：先只把 `stress-probe-catalog` 扩成 A1/B1/C1/E1 的可跑语料 + baseline，用真实数字看
  差异是否够强，再决定投 workshop 还是正会。

---

## 附：本轮已核实的内部事实（避免 overclaim）

- `lab/research/claims.yaml` / `evidence.yaml` 目前仍是**模板占位符**，无正式研究 claim → 本论文的 claim 是新建。
- 已有实证种子：ELF case（`worktree-case+elf-template-replay`，4 轮，F1–F19，report 在
  `lab/docs/audits/agent-native-template-functional-test-report.md`）、Agent-R1 采用 replay（178 文件全保全、
  0 blocker、0 error）、上下游同步自测（adversarial-probe-matrix）。这些是 §5.1 的直接种子，但**尚未组织成
  统计化 benchmark**。
- 所有外部文献仅经一轮 WebSearch，**编号/版本待人工核对**。
