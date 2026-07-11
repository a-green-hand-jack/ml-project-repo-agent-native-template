# 论文定位：环境编码治理（Environment-Encoded Governance）

> **这份文档是什么**：把 `ml-project-repo-agent-native-template` 定位为一篇 **方法 / agentic-system
> 创新**论文的真源。回答：(1) 可发表的方法内核是什么、其精神根据；(2) 用什么框架陈述它的新意；
> (3) 方法由哪些领域无关的原语构成；(4) 用 ML/science/quant 三域如何验证；(5) 与 2026 相关工作的差异。
>
> **定位决定（human 已拍板）**：作为**领域无关的方法**来卖（不是 benchmark、不是"ML 专用模板"），
> 用 **ML / 计算科学 / 量化金融** 三域验证，self-hosting 作为亮点。节奏：**先 workshop 试水拿审稿意见，
> 再打磨投正会**。
>
> **状态**：positioning（无实验结果）。claim→experiment 细节本轮**刻意暂缓**（human 指示）。
> 外部文献 arXiv 编号来自 2026-07 WebSearch，**引用前需逐条 `arxiv.org/abs/<id>` 核对版本**。
> 分支：`research/paper-positioning`（worktree，不入 main）。

---

## 0. 一句话定位

> 我们提出 **环境编码治理（environment-encoded governance）**：一种把"agent 绝对不能违反的规范"
> 物化为**可执行、自验证、抗漂移、跨 provider 可移植**的仓库结构的**领域无关方法**；并证明它在
> **ML 研究、计算科学、量化金融**三个高风险长时程工作空间上成立，还能治理自身的开发（self-hosting）。

口号（来自源精神，直接可作标题）：**Design the harness, not the agent.**

---

## 1. 精神根据与智识升级链（motivation）

本方法的精神源头是 `.reference-docs/claude_code_optimization_spirit_zh.md`。其中三处原句已经埋好了本论文的
哲学命题：

- §3.3：**"精神必须体现在 repo 里。否则它只是一段在某个 session 里说得很漂亮的话，下一次 fresh
  context 就会变成传闻。"** → 活在 chat 里的规范，下一个上下文即退化为传闻；**规范必须物化进环境才能存活**。
- §3.7：**"想让 Claude 理解偏好用 CLAUDE.md；想让某事必然发生用 hooks；想限制危险用 permissions。"**
  → "控制权位置"的原始表述：意图归 prompt，硬约束归环境。
- §8 maxim：**"把 Claude Code 当作实验仪器：校准它、约束它、记录它、验证它。不要崇拜 agent，要设计
  harness。"** → 优化对象是 harness/环境，不是 agent。

论文只需走完最后一次抽象：

```
个人 maxim（spirit 文档：一个人用 Claude Code 做 ML 研究的哲学）
  → 物化的 harness（template v1：把 maxim 变成 repo 原生、机器强制、validator 可验的制品，单 provider）
  → 跨 provider（v1.1：一套治理，Claude Code + Codex 强制等价）
  → 【本论文】领域无关的方法 + 三域实证 + self-hosting
```

**贡献 = 完成从"一个仓库的做法"到"一种可移植、可验证、领域无关方法"的抽象，并证明它跨领域成立。**

---

## 2. 核心命题：治理编码的"三点谱系"（Figure 1 装置）

治理可编码在三个位置，越往下越硬、越可验、越抗漂移：

| 编码位置 | 代表 | 性质 | 致命弱点 |
| --- | --- | --- | --- |
| **Model-encoded** | RLHF / guardrail 模型 | 概率性、内隐 | 不可审计、不随任务迁移 |
| **Prompt-encoded** | system prompt / AGENTS.md / CLAUDE.md | 可读但"软" | 遵从随长度衰减（McMillan −5.6%/函数）；长 context 下 goal drift |
| **Environment-encoded（本方法）** | 可执行、自验证、抗漂移的 repo 结构 | 硬、外显、可复核 | 需工程化 + 需能自证未腐烂 |

**命题一句话**：
> 长时程、多 agent、授权自主的场景里，前两层治理恰恰在最需要它的地方腐烂（有独立实证）；因此必须把
> "绝对不能违反"的治理下沉到第三层——环境——并让它能**持续自证没有腐烂**。"设计 harness，不崇拜
> agent"就是这件事的操作化。

这个谱系同时（a）立住新意（无人系统性做第三层 + 自验证），（b）用现成文献（遵从衰减 / goal drift /
context rot）为设计选择背书。

---

## 3. 方法：七个领域无关的"治理物化原语"

要被认作**方法**而非模板，必须能脱离本仓库被别人套用。template 收敛为一组 governance materialization
primitives——任何 lab-class 工作空间皆可应用：

| # | 原语 | 做什么 | 本仓库实现锚点 |
| --- | --- | --- | --- |
| P1 | **边界物化** | 约束切成{可调 permission，不可调地板}；地板装"不可逆伤害集"，解析式精确、跨 provider 可移植 | `.claude/settings.json` + `pre_tool_guard.py` + `.codex/rules` |
| P2 | **证据物化** | 每个结论是带 provenance 的类型化对象，强度 ≤ 证据等级；overclaim = validator 错误 | `lab/research/{claims,evidence}.yaml` + `validate-governance.py` |
| P3 | **结构物化** | 地图（anatomy）与领土原子同变更；漂移 = validator 错误 | `ANATOMY.md` 树 + `check-anatomy-drift.py` + `check-same-commit.py` |
| P4 | **记忆物化** | 工作状态落文件 + 续接协议；连续性是环境属性而非上下文窗口属性 | `memory/current-status.md`、`session-tree.md` + PreCompact hook |
| P5 | **能力物化** | agent/skill/hook repo-local、单一真源、机械跨 provider 生成；能力漂移可机器检测 | `.claude/` canonical + `sync-codex-adapters.py` → `.codex/`/`.agents/` |
| P6 | **自验证** | 治理自带可执行 validator 证明自身完整；**不能自证的治理不被信任** | `scripts/*validate*.py` + CI `governance.yml` |
| P7 | **治理演化** | maker-agent + recipe 状态机从真实轨迹提炼、带过期与复测，抗产品漂移 | `lab/recipes/`、`lab/evals/cc-workflow/`、maker agents |

**元原则（统摄七条）**：
> *任何必须在 fresh context 与对抗性自主下存活的规范，都必须物化为自验证的环境结构。*

---

## 4. 三域验证设计：每个域压不同的原语（purposive，非 convenience）

不讲"跑了三遍"，讲"每个域被特意挑来最大化压测某条原语"——把 convenience sampling 变 purposive
validation：

| 域 | 最大化压测的原语 | 该域特有的锋利边 |
| --- | --- | --- |
| **ML 研究（主场）** | P2 证据物化 + 可复现 | claim↔run↔config↔checkpoint；checkpoint/data byte 保护；长训练不可重启 |
| **计算科学**（生信/物理仿真等） | P4 记忆物化 + 长过程安全 + 科学 provenance | 长仿真不可 kill；大数据集；结论要追溯到确定性 pipeline。测 P2 能否泛化到非 ML 科学 claim |
| **量化金融** | P1 边界物化那层地板 | "不可逆伤害"= 真金白银实盘下单（远超删 checkpoint）；领域特有 overclaim：回测有 look-ahead bias 即"证据不成立" |

**三域各击穿一条不同原语 → 合起来才证明"方法领域无关"**，而不是"在 ML 近亲上都行"。这是三域设计的
真正价值。

**诚实缺口**：science / quant 目前是 **0 实例**（现有仅 ML 主场 + self-hosting）。三域实证需真的把方法
实例化到一个 science repo 和一个 quant repo（= human 已同意的"拓展"部分）。→ 见 §8 节奏。

---

## 5. Self-hosting：第四个、自指的实例

本方法**正在治理定义它自己的那个仓库**（ai-agent/tooling 域）。严格说有**四个实例，其一自指**：
*方法治理着定义方法的仓库。* 它不是外部验证，但是**内部一致性的最强证据**——"我们的方法连自己的开发
都管得住"，天然回应"这只是 PPT 治理"的质疑。可作论文一个 punch。

---

## 6. 2026 相关工作图景与差异化

调查（3 个并行 document-specialist，均带出处；编号待人工核对）显示相关文献分**三条基本不相交的线**，
外加两篇最贴脸的近作。

### 6.1 两篇必须正面区分的近作

- **Russo, *Govern the Repository, Not the Agent*（arXiv:2606.28235, 2026-06）**：标题即口号，但是**生态级
  风险度量**（93 万 agent PR，集成摩擦 ICC 0.30 vs 人类 0.16），**只度量、没建制品**。→ 是我们最强的
  *motivation 引用*：它论证"该在仓库层治理"，我们**给出并验证了那个可移植、自验证的制品**。
- **A Deterministic Control Plane for LLM Coding Agents（arXiv:2606.26924, 2026-06）**：架构最接近（thin
  governance surface、phase state machine、drift detection、evidence provenance）。但 **(a) 通用软件工程非
  研究工作空间；(b) 评测只有半形式化论证 + vignette，无实证、无对比、无跨域；(c) 单 harness、无自验证泛化。**
  → 我们在**域类（lab-class）原语、自验证、实证+跨域、跨 provider** 四点上正面拉开。

### 6.2 三条平行线（各自的空白正是我们的落点）

- **线 A — 配置文件的行为效果实证**：AGENTS.md 效率研究（arXiv:2601.20404，10 repo/124 PR/仅 Codex，
  耗时 −28% / 输出 token −16%，**不测正确性/安全/漂移/研究场景/多 session**）；指令遵从因子研究
  （McMillan, arXiv:2605.10039，遵从率随生成函数数 −5.6%/个）。→ 只测"单文件效果"，非"整套自验证治理"。
- **线 B — agent 记忆系统**：MemGPT/Letta、Mem0（独立测 30 天有效准确率 49%）；context engineering 已成
  术语（survey 2507.13334、Anthropic 博客 2025-09、ACE 2510.04618）；ICLR 2026 MemAgents workshop。
  → **CLAUDE.md/`memory/` 这类持久文件从未被纳入记忆 benchmark**——P4 记忆物化正是这条空白的具体制品。
- **线 C — 安全护栏 / 治理评测**：共识"结构性权限 > 过滤式护栏"（2510.11108、2603.00195、VeriGuard
  2510.05156）支持 P1；AuthBench（2605.14859）测最小权限理解；相邻领域已有治理型 benchmark（DEMM-Bench
  2606.20634、EmbodiedGovBench 2604.11174、DepDec-Bench 2601.00205），**但无一针对"代码仓库+多 session+
  多 agent+研究约束"**。harness 评测方法学（Harness-Bench 2605.27922、"disclose the harness" 2605.23950）
  为"评 harness 而非评 model"的框架背书。
- **线 D（问题动机）**：Goal Drift（2505.02709, AIES 2025；Inherited 2603.03258）为 P3/P4 抗漂移动机；
  AI-Scientist-v2（2504.08066）"伪造结果/编造方法"是最常见两类幻觉 → P2 证据物化的最强动机；可复现性
  清单（REFORMS/NERVE-ML/MLRC）**全静态人工、无 agent 可强制自动校验** → P2/P6 填的空白；证据分级（医学
  GRADE/EvidenceGrade 已落地，**ML/CS 无对应物**）。

### 6.3 一句话空白陈述

> 现有工作三支：(A) 度量单个配置文件对效率/遵从的影响；(B) 研究对话式 agent 记忆；(C) 在相邻领域建治理
> benchmark。**无一支把"高风险研究工作空间约束 + 结构性硬边界 + 跨 session 记忆 + 跨 provider 一致性"
> 整合为一个可被机器独立复核、且领域无关的环境编码治理方法，并给出跨域实证。** Russo(2026) 论证该在仓库
> 层治理却未建制品；Control-Plane(2026) 建了通用制品却不自验、不实证、不跨域。**我们同时补齐两侧。**

### 6.4 差异化四点（即使领域无关也守得住）

1. **域类特定的原语**：证据物化、byte 保护、长过程安全——通用 SWE 控制面没有这些原语。
2. **自验证**：治理自带 validator 持续机器自证，非一次性半形式化论证。
3. **实证 + 跨域**：真实 case replay + 三域 purposive 验证，非 vignette。
4. **跨 provider 可移植**：一套边界机械生成 Claude Code + Codex，漂移可检测——非单 harness。

> 关键：**通用性 ≠ 通用得没特色**。是"跨研究领域通用"，但机制专门针对 lab-class 痛点——这既满足方法
> 创新高度，又不滑进通用控制面红海。

---

## 7. 标题候选

- **Design the Harness, Not the Agent: Environment-Encoded Governance for Long-Horizon Research Workspaces**（首选：把源 maxim 抬成标题，有立场、好记、与竞品"评 model/度量风险"锋利对照）
- The Repository as Control Plane: A Domain-Agnostic Method for Self-Verifying Agent Governance
- Environment-Encoded Governance: Making Agent Constraints Executable, Self-Verifying, and Portable

**Venue / 节奏**：arXiv 先行 + 软件工程正会 agentic-SE（ICSE/FSE/ASE）或 agents workshop。**先 workshop
拿意见，再正会**。定位句："评的是治理 harness 而非 model"（Harness-Bench 背书）。

---

## 8. 节奏与诚实取舍

- **Workshop 版（快、低风险）**：ML 主场 + self-hosting 实证 + 三点谱系 + 七原语 + **science/quant 作为
  "设计已就绪、正在实例化"的 generality 论证**。先拿审稿意见。
- **正会版（完整、慢）**：补齐 science repo + quant repo 两个真实实例，让 purposive 三域实证成立；
  （claim→experiment 的具体设计到此阶段再展开——本轮 human 指示暂缓。）

**最大不确定性不在"有没有故事"，而在为 science/quant 两个新实例的实例化投多少工程成本。** 这与 human
已接受的"可以拓展"一致。

---

## 附：本轮已核实的内部事实（防 overclaim）

- `lab/research/claims.yaml` / `evidence.yaml` 仍是**模板占位符**，无正式研究 claim → 本论文的方法/claim 是新建。
- 现有实证种子：ELF case（`worktree-case+elf-template-replay`，4 轮 F1–F19，report 在
  `lab/docs/audits/agent-native-template-functional-test-report.md`）、Agent-R1 采用 replay（178 文件全保全、
  0 blocker、0 error）、上下游同步自测（adversarial-probe-matrix）。它们是 ML 主场 + self-hosting 的实证种子。
- science / quant 域：**当前 0 实例**，需拓展。
- 外部文献仅经一轮 WebSearch，编号/版本待人工核对。
- claim→experiment 的详细设计本轮**刻意未展开**（human 指示先聚焦定位）。
