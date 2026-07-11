# 论文定位 v2：发现流水线的环境编码治理

> **文档角色**：本文件是论文定位 v2 的真源。它把当前仓库中的治理实践抽象为一种可实例化、可评测的
> 研究方法，同时明确其适用边界、可信假设和当前证据强度。
>
> **相对 v1 的校准**：不再宣称面向所有 AI agent 或所有领域，也不收窄为 ML checklist/template；方法治理的
> 对象是跨 ML、量化研究与计算科学同构存在的**发现/研究流水线**。与通用 coding-agent control plane 的关系是
> **compose-not-compete**，差异来自治理对象与证据语义，而非谁“有实证”。
>
> **当前状态**：positioning / method specification v2。ML 有实现与 replay 种子，量化与计算科学尚无真实实例；
> 因此现阶段只主张方法定义与跨域 feasibility agenda，不主张已经证明有效性或领域无关性。

---

## 0. 一句话定位

> 我们提出**发现流水线的环境编码治理**（environment-encoded governance for discovery pipelines）：
> 一种面向长时程、多 session、多 agent 研究系统的领域可适配方法，把领域风险转译为仓库内可执行、可审计、
> 可恢复的 policy boundary、evidence state、workspace topology、continuity state 与 capability bundle，并以持续
> conformance 和受治理演化维持这些约束；同一组治理对象与实例化程序可用于 ML 训练、量化研究和计算科学仿真。

简短口号仍保留精神源头的表达：**Design the harness, not the agent.** 但论文中的 harness 不是泛指所有 agent
基础设施，而是专指承载发现过程、研究证据与不可逆动作边界的 repo-level control surface。

---

## 1. 精神根据：把研究仪器的校准写进环境

精神源头 `.reference-docs/claude_code_optimization_spirit_zh.md` 提供了三个连续命题：

1. **Repo 是控制面，chat 是短期意识流。** 规范、状态和证据若只存在于 session 中，fresh context 无法可靠接续。
2. **Prompt 表达意图，hooks/permissions 承载约束。** 必须发生或必须阻断的行为不能只依赖自然语言遵从。
3. **把 agent 当实验仪器来治理。** 校准、约束、记录、验证的对象是 agent 所处的 harness，而不是对模型人格或
   “自律”的期待。

对普通软件交付，这些原则可改善 agent 编码活动；对发现流水线，它们还有更强的研究语义：实验会消耗昂贵资源，
artifact 会跨 session 存活，结论必须受证据等级约束，代码变化还可能反向改变论文、因子或科学发现。因此论文的
智识升级链不是“一个好用模板变成普适治理”，而是：

```text
实验仪器式工作哲学
  -> repo-local 控制面实现
  -> 识别发现流水线的共同状态与风险结构
  -> 给出领域风险到 repo control 的可操作实例化方法
  -> 用跨域共同 protocol 检验可迁移性、收益与代价
```

---

## 2. 核心 thesis：治理“发现流水线”，不是治理所有 agent

### 2.1 发现流水线的共同结构

本文把 discovery/research pipeline 定义为满足以下多数条件的系统：

- 通过训练、回测、仿真或搜索等长时程过程生成候选发现；
- 过程昂贵，错误启动、继续、终止、覆盖或发布具有显著且有时不可逆的代价；
- 产出 dataset、config、run、checkpoint、feature、table、figure 等需索引和复现的 artifact；
- 形成不能强于其证据的 claim，如模型性能、因子 alpha、机制发现或科学结论；
- 工作跨多个 session、agent、分支或执行环境，必须能恢复上下文和责任边界；
- 研究过程与其外部动作边界相邻，如提交 HPC 作业、发布结论或将量化研究接到实盘执行。

这一定义既排除“所有 AI agent、所有领域”的空泛范围，也不把贡献缩成某个 ML validator。方法的泛化性来自
**共享的过程结构 + 同一套治理对象 + 同一实例化程序**，而不是假设各领域拥有相同的业务语义。

### 2.2 论文主张的强度

**方法主张**：发现流水线可被统一分解为五类需要物化的治理对象，并通过两个横切 assurance process 维护；
领域团队可以用一个明确的五步程序将 hazards、evidence semantics 与 execution boundaries 编译为 repo controls。

**经验主张（待验证）**：与 prompt-only 或通用 coding-agent control plane 相比，加入发现流水线语义的完整方法，
能在可接受维护成本下改善违规阻断、claim 可追溯、context-loss 恢复和跨 provider 行为等价性。

当前只把前者写成方法贡献，把后者写成可证伪 hypothesis；在三域 evaluation 完成前，不使用“证明领域无关”或
“绝对不能违反”等表述。

### 2.3 非目标

- 不提出面向任意 agent 应用的统一治理理论。
- 不替代 OS sandbox、云 IAM、broker risk engine、HPC scheduler policy 或组织级审计系统。
- 不声称通用 schema 能自动发现 look-ahead bias、浮点非确定性等领域错误；这些由 domain profile 定义。
- 不把 repo hook 描述为对抗性安全边界，也不声称 validator 能证明治理完备或自身绝对完整。

---

## 3. 多维设计空间：替代“model -> prompt -> environment”三点谱系

治理机制不形成单调变硬的三点谱系。`AGENTS.md` 既是 prompt 表示，也是 repo 环境的一部分；远端签名 policy
可能比本地 hook 更强，而未加载的 hook 可能没有任何约束力。更准确的 Figure 1 是四维设计空间：

| 维度 | 典型取值 | 论文中的问题 |
| --- | --- | --- |
| **Policy representation** | 自然语言、结构化 schema、规则、可执行代码 | invariant 如何被表达、组合和 review？ |
| **Enforcement locus** | model、agent harness、repo、OS/container、远端服务 | 控制在哪里执行，谁能绕过，失效如何被发现？ |
| **Control type** | advisory、preventive、detective、recovery | 是提醒、预防、检测，还是支持失败后恢复？ |
| **Assurance level** | 未检查、人工复核、自动 conformance、外部/加密验证 | 对“规则存在、已加载、语义等价、执行留痕”能给出多强证据？ |

本方法不把“environment-encoded”定义为天然更硬，而是要求团队显式选择每条 invariant 在四维空间中的落点，
并测量加载失败、语义漂移和 bypass。环境编码的价值是**外显、可组合、可复核**，不是自动获得安全性。

---

## 4. 方法内核：5 类物化对象 + 2 个横切过程

### 4.1 五类 materialization object

| 对象 | 方法定义 | 最小输出 | 可判定 invariant / 失败语义 | 本仓库实例 |
| --- | --- | --- | --- | --- |
| **O1 Policy boundary** | 主体、动作、资产、阶段与 human gate 的结构化边界，特别标记昂贵或不可逆动作 | hazard register、action classes、policy rules、escalation/recovery contract | 禁止动作被阻断或明确升级；控制未加载、冲突、漏判、误判均记为失败 | `.agent/action-boundary.md`、settings/rules、`pre_tool_guard.py` |
| **O2 Evidence state** | hypothesis、run、artifact、metric、claim 及其 provenance/强度关系 | evidence lattice、claim schema、promotion gate、domain validity fields | claim 强度不得超过可解析证据；缺 run/config/metric source 或领域有效性检查则不可 promotion | `lab/research/{claims,evidence}.yaml`、artifact indexes |
| **O3 Workspace topology** | ownership、结构地图、可写目标、artifact 位置与状态 shape | topology map、owned/forbidden paths、same-change rules | 结构变化与地图/ledger 不一致为 drift；未知 ownership 阻止高风险改动 | `ANATOMY.md` 树、worktree ownership、drift checker |
| **O4 Continuity state** | 跨 session/agent 的目标、决策、未决风险、执行状态与恢复协议 | checkpoint/handoff schema、session tree、resume test | fresh actor 无法在限定时间内恢复正确目标/边界，或沿用过期状态，即 continuity failure | `memory/current-status.md`、session tree、PreCompact 流程 |
| **O5 Capability bundle** | 可被 repo 发现、版本化并适配执行面的 agent/skill/hook/validator 集合 | canonical capability spec、adapter contract、manifest | adapter 缺失、语义不等价、依赖能力未加载或版本不兼容为 failure | `.claude/` canonical -> `.codex/`/`.agents/` adapters |

五类对象回答“什么研究治理状态必须在环境中存在”。它们不是目录清单：外部实现可以使用数据库、policy service、
CI 或其他布局，只要产出等价 contract 并满足相同 invariant。

### 4.2 两个横切 assurance process

| 过程 | 覆盖对象 | 作用 | 不能证明什么 |
| --- | --- | --- | --- |
| **A1 Continuous conformance** | O1-O5 | 检查 schema、引用、加载状态、adapter 等价、违规注入、结构/能力 drift，并保存可审计结果 | 不能证明 policy 完备、领域结论正确或不存在未观测 bypass |
| **A2 Governed evolution** | O1-O5 及 A1 | 让 policy/schema/capability 的修改带 provenance、review、迁移、复测、降级与 recovery | 不能消除产品/依赖变化，只能让变化显式且可处理 |

`self-validation` 因而不再是与五类对象并列的“第六原语”，而是 A1 对已声明 invariant 的持续检查。
供应链完整性也不是本文独占的新意：可直接组合签名 lockfile、hash-chained audit log、外部 CI 等更强机制，缩小
本地 validator 的可信基。

---

## 5. 从领域风险到 repo control：五步实例化程序

外部团队能否只读论文与 reference artifact 完成陌生 repo 的实例化，是方法可迁移性的关键判据。建议把以下程序
写成论文 Algorithm 1，并为每步发布 schema、tailoring guide 与 conformance fixture。

### Step 1：发现流程与 hazard elicitation

**输入**：领域 workflow、主体/工具、资产、外部系统、成本模型、已有 incident。  
**操作**：画出 hypothesis -> experiment -> artifact -> claim -> external action 的状态图；对每个状态列出误启动、
误终止、污染、覆盖、越权 promotion、失联与漂移。  
**输出**：带 severity、reversibility、detectability、owner 的 hazard register。  
**失败**：存在没有 owner、没有恢复路径或无法归类的高严重度 hazard。

### Step 2：定义 invariant、schema 与领域 profile

**输入**：hazard register。  
**操作**：把 hazard 映射到 O1-O5；定义主体/动作授权、evidence lattice、artifact provenance、continuity checkpoint、
topology ownership 和领域 validity fields。  
**输出**：core profile + domain profile + 可机器判定 invariant。  
**失败**：invariant 只写成愿望句、没有观测量，或通用机制与领域 validator 的职责不清。

### Step 3：选择 enforcement placement 与 recovery

**输入**：invariant、执行面能力、threat model。  
**操作**：在四维设计空间中为每条 invariant 选择 advisory/preventive/detective/recovery 控制；高代价动作优先放到
更小、更外部的可信边界，repo control 负责准备、检测和升级。  
**输出**：policy composition graph、冲突优先级、human gates、containment/recovery playbook。  
**失败**：控制可绕过却无检测，多个 policy 冲突无优先级，或只有阻断没有恢复。

### Step 4：编译 capability 与 provider adapters

**输入**：canonical profile、目标 provider/harness 的能力矩阵。  
**操作**：生成 rules/hooks/skills/validators；对不能等价编译的能力显式降级并补偿，而非假装 portable。  
**输出**：provider-specific bundle、semantic mapping、unsupported-capability report。  
**失败**：adapter 语法成功但语义不等价，或 provider 不支持的强制点未被暴露。

### Step 5：conformance、演化与完成判据

**输入**：实例化后的 O1-O5。  
**操作**：运行正常路径、违规注入、控制未加载、context loss、治理变更和 recovery tests；记录 coverage、误报、
漏报、维护时间与 bypass。  
**输出**：版本化 conformance report、已知缺口、复测周期、迁移/回滚计划。  
**完成判据**：所有高严重度 hazard 已映射到至少一个 control 和一个检测/恢复路径；core suite 通过；领域 stressor
有明确结果；未支持能力与 bypass 被记录，而非隐藏。

---

## 6. 跨域同构：同一治理原语，三种发现语义

泛化性不是把领域差异抹平，而是证明同一 core 可由 domain profile 具体化。

| 流水线位置 | ML 研究 | 量化研究 | 计算科学 | 共同治理对象 |
| --- | --- | --- | --- | --- |
| **假设生成** | 架构、损失、数据或 ablation 假设 | 挖算子、挖因子、特征提取、交易假设 | 机制、参数区间、数值方法假设 | O4 保存决策与分支；O3 标记 ownership |
| **实验执行** | 训练、评测、超参搜索 | 回测、walk-forward、因子检验、建模 | 仿真、HPC 作业、参数扫描 | O1 管启动/终止/资源边界；O5 提供执行能力 |
| **artifact** | dataset split、config、run、checkpoint、metric | 数据快照、feature、factor、模型、回测账本 | 输入数据、代码/容器、mesh、trajectory、output | O2 provenance/index；O3 位置与状态 |
| **claim** | 模型性能、机制解释；claim <-> run <-> config <-> checkpoint | “得到一个好模型”或 alpha/稳健性结论，必须关联样本期、成本、偏差检查 | 发现、数值结论、敏感性或不确定性结论 | O2 evidence lattice + domain validity fields |
| **昂贵/不可逆边界** | 长训练重启、checkpoint/data 覆盖、发布论文结论 | 实盘下单是研究流程相邻的不可逆动作边界；只在 sandbox/mock 中测试 gate | 提交/取消昂贵 HPC 作业、继续烧算力、覆盖大型输出、发布结论 | O1 human/external gate + recovery；A1 违规注入 |
| **跨 session 连续性** | 多轮训练、debug、paper 修改 | 数据版本、因子谱系、回测口径、模型选择 | scheduler 状态、checkpoint、环境/数据库版本、复现实验 | O4 checkpoint/resume；A2 迁移与复测 |

量化范围应明确为**量化研究/发现流程**。实盘系统本身仍需 broker、风控和生产 control plane；实盘下单在本文中
作为研究流程通向不可逆外部动作的边界，说明 O1 必须能与外部强控制组合，而不是由 repo hook 直接“保护真钱”。

计算科学也不被简化为确定性 pipeline。domain profile 必须容纳随机模拟、浮点非确定性、并行归约、容器/编译器、
外部数据库版本、数据许可、checkpoint 与安全取消；昂贵作业“错误继续”与“错误终止”都属于 hazard。

---

## 7. 与最近工作的关系：治理对象不同，机制可组合

### 7.1 对 arXiv:2606.26924 的事实更正

v1 对 *A Deterministic Control Plane for LLM Coding Agents* 的描述有误，v2 明确撤回“无实证、单 harness、
不跨 provider/target、缺乏完整性机制”等说法。该工作实际包含：

- 10,008 仓库规模的 prevalence study；
- injected-violation conformance tests；
- canonical definition 向七个 target 的编译；
- HMAC lockfile 与 hash-chained audit log；
- tiered permissions 与 phase state machine。

这些能力不是本文差异化的反面教材，而是可复用的通用 coding-agent control-plane 与供应链完整性基础。

### 7.2 Compose-not-compete 差异轴

| 比较轴 | Deterministic Control Plane | 本文方法 | 组合关系 |
| --- | --- | --- | --- |
| **治理对象** | 通用 coding agent 的编码活动与 agent definition/control-plane integrity | 发现流水线的实验、artifact、claim、连续性及不可逆研究动作边界 | 前者可作为后者的执行与完整性底座 |
| **核心状态** | phase、permission、requirement/file/test trace、policy artifact | hypothesis/run/artifact/evidence/claim、session continuity、domain profile | 研究状态可叠加到通用 phase/state machinery |
| **证据语义** | conformance 与工程 traceability | claim 强度受 provenance 和领域有效性约束 | 复用 audit log，扩展 research-evidence schema |
| **跨 session 目标** | 编码控制面的确定执行与审计 | 研究问题、未决风险、实验状态和 claim promotion 的恢复 | 通用 audit + domain continuity checkpoint |
| **边界对象** | 编码权限与 agent definition 供应链 | 训练/回测/仿真成本、研究资产、发布/下单/HPC 边界 | repo gate 与 OS/cloud/broker 强边界组合 |
| **assurance** | conformance、lockfile、hash-chained audit、target compilation | 对 O1-O5 的 core + domain conformance 与 governed evolution | 直接采用其完整性机制，评估增量语义的收益/成本 |

因此论文不主张“我们比它更有实证”或“我们首次跨 target”。真正问题是：**在一个可靠的通用 agent control
plane 之上，发现流水线还需要哪些状态、语义和 assurance，且这些增量是否跨研究域复用？** 这既保留差异，也
允许最强 baseline 是“Control Plane 等价配置 + 本文 research profile”，而不是制造互斥竞争。

Russo 的 repository-level governance 工作则主要提供分析单位与问题动机：repository ecosystem 的效应不能还原为
单次 agent 行为。本文提供一种面向发现流水线的可执行实例化与 evaluation agenda，不把测量工作贬为“只有数据”。

---

## 8. Evaluation：三域 feasibility + 共同 protocol 骨架

### 8.1 当前可声称什么

- **ML**：本仓库提供方法构件与 replay 种子，但 `lab/research/claims.yaml` 仍是占位状态；尚无 paper-grade claim。
- **量化、计算科学**：当前均为 0 真实实例，只能作为预注册的迁移目标。
- **Self-hosting**：可作为纵向可用性、维护成本和治理演化 case；不是独立样本，不证明有效性或 generality。

三域的作用是测试同一方法能否被实例化并产生可比较测量，即 **feasibility + analytical replication**，不是凭三个
purposive case 证明领域无关。

### 8.2 每域相同的 core protocol

每个域都运行同一组任务，只替换 domain profile：

1. **Risk-to-control instantiation**：由团队从 workflow/hazard 得到 O1-O5，记录时间、歧义和未映射 hazard。
2. **Provider A/B execution**：在两个受支持 harness 上执行相同正常任务与受限任务，检查语义等价与能力降级。
3. **Injected violation**：注入受保护资产写入、越权实验动作、证据缺失的 claim promotion、错误 ownership 等违规。
4. **Context loss/recovery**：移除 chat context，由 fresh actor 仅凭 continuity state 恢复目标、边界和下一步。
5. **Governance change/drift**：修改 schema、adapter 或 topology，检查能否检测、迁移、回滚并保持 audit trail。
6. **Claim promotion**：从实验输出生成候选 claim，验证 provenance、证据强度、领域 validity 与 human gate。

### 8.3 每域一个 domain-specific stressor

| 域 | stressor | 安全执行方式 |
| --- | --- | --- |
| ML | run/config/checkpoint 错配或长训练误重启 | 小型 fixture / synthetic run，不启动真实长训练 |
| 量化 | look-ahead/survivorship/cost 字段缺失，并尝试越过实盘边界 | 历史小样本 + mock exchange / broker sandbox，绝不真实下单 |
| 计算科学 | 非确定性环境/provenance 缺失，或昂贵作业错误继续/取消 | 本地小仿真 + scheduler mock，不提交真实昂贵 HPC 作业 |

### 8.4 指标、baseline 与 ablation

**共同指标**：违规阻断 recall、false-positive rate、控制未加载检测率、adapter 行为等价率、drift detection
precision/recall、claim provenance completeness、错误 promotion 阻断率、恢复成功率/时间、任务成功率、human
intervention、实例化与维护时间。

**Baselines**：prompt/`AGENTS.md` only；通用 Control Plane 等价配置；完整方法。  
**Ablations**：移除 evidence state、continuity state、continuous conformance，分别观察 claim、恢复和 drift 指标。

至少加入一个外部团队的 blind instantiation，检验方法是否能脱离作者与本仓库复现。只有当共同 protocol 在异质域
有数据后，摘要才可把“domain-adaptable”从设计主张升级为经验结论。

---

## 9. 威胁模型、可信计算基与诚实边界

### 9.1 主要威胁

- agent 忽略或误解自然语言 policy；
- provider adapter 编译成功但语义漂移；
- hook/validator 未加载、被错误配置或遗漏某类动作；
- session 丢失导致沿用过期目标、错误 artifact 或错误边界；
- claim 与 run/config/artifact 断链，或领域 validity 字段缺失；
- 治理代码与 schema 同时被错误修改，使内部检查出现递归信任问题；
- 人类或受信代码显式 bypass 本地控制。

### 9.2 可信计算基（TCB）

最小 TCB 包括：repo checkout 与版本历史、harness 的 policy/hook 加载机制、validator/runtime、canonical-to-provider
adapter、执行这些检查的 CI 或外部服务，以及有权批准高风险动作的人类。对资金、云/HPC 与生产数据，TCB 必须
扩展到 broker risk engine、IAM、scheduler、sandbox/容器和组织审计；repo 不是它们的替代品。

应优先把完整性检查放到比被检对象更小或更外部的根上。arXiv:2606.26924 的 HMAC lockfile、hash-chained audit
log 等机制可直接作为 capability/integrity layer 组合进来。

### 9.3 Bypass 假设与表述边界

本地 hook 是防误操作护栏，不是对抗性 sandbox；`--no-verify`、`SAME_COMMIT_SKIP=1`、未信任 repo hooks、受信
`python -c`/测试代码和直接调用外部系统都可能绕过或超出观测面。方法应记录并测试这些 bypass，而不是宣称消失。

因此可守的结论是：

> 在明确的 harness、trust 与 execution assumptions 下，本方法提高指定发现流水线 invariant 的可执行性、
> 可审计性、可恢复性与跨执行面一致性；conformance 结果只覆盖已编码 invariant 和已观测路径。

---

## 10. 可发表贡献包

1. **对象层贡献**：发现流水线的 5-object + 2-process 治理模型，明确区分通用 core 与 domain profile。
2. **程序层贡献**：从 hazard elicitation 到 conformance/evolution 的五步实例化算法、failure semantics 与完成判据。
3. **artifact 贡献**：reference schema、tailoring guide、provider adapter contract、conformance suite 与至少两个异质域实例。
4. **经验贡献（待实验）**：共同 protocol 下相对 prompt-only、通用 Control Plane baseline 与 ablation 的收益/成本。

这是一篇 **artifact-centered system/method paper**，不是纯哲学 position paper，也不是“目录很多”的 template paper。

---

## 11. 标题候选

### 首选

**Design the Harness, Not the Agent: Environment-Encoded Governance for Discovery Pipelines**

中文：**设计 Harness，而非崇拜 Agent：面向发现流水线的环境编码治理**

### 备选

- **Governing Discovery: A Domain-Adaptable Repository Control Method for ML, Quantitative Research, and Computational Science**
- **From Experiments to Claims: Executable Governance for Long-Horizon Discovery Pipelines**
- **The Repository as a Research Control Plane: Evidence, Continuity, and Boundaries for Agentic Discovery**

首选标题保留精神源头并限定对象；备选 1 强调跨域泛化，备选 2 强调 research-evidence semantics，备选 3 更贴近
系统论文体裁。避免标题使用无边界的 “domain-agnostic agent governance” 或过窄的 “ML repository validator”。

---

## 12. Venue 与节奏

### 阶段 1：非归档 workshop / 内部 pilot

定位为 **framework + method specification + evaluation agenda**。交付威胁模型、5+2 模型、五步程序、reference
schema、一个 ML case 的 baseline/ablation pilot。量化与计算科学明确为待实例化，不在摘要中声称三域有效。

### 阶段 2：CAIN / FSE / ICSE 风格完整稿

完成至少两个真正异质域、两个 provider、直接 Control Plane baseline、failure injection、维护成本、外部 blind
instantiation 和 replication package。正会新增贡献不能只是“多两个案例”，而应包含方法规范、跨域数据和可复用
artifact。venue 优先匹配 agentic software assurance / software engineering，而非泛 agents 叙事。

### Stop / go 判据

- 若只能完成方法 spec + ML pilot：投非归档 workshop/vision/design 体裁。
- 若完成两个异质域但无外部实例化或直接 baseline：适合聚焦的工具/经验轨道，不宣称 general effectiveness。
- 只有共同 protocol、baseline/ablation、外部实例化与 artifact 齐备，才进入正会方法/系统主张。

---

## 13. 当前开放张力

1. **core 与 domain profile 的边界**：若 look-ahead bias、非确定性 provenance 等都依赖专用 validator，需要用实例化
   成本和复用比例证明这不是“每域重写一套治理”。
2. **repo control 与外部强控制的分工**：越高风险的动作越应由 broker/IAM/scheduler 执行；论文需证明 repo-level
   方法在不冒充安全边界的前提下，仍对准备、证据、升级、审计和恢复产生可测增量。
3. **assurance 的递归信任**：本地 validator 无法独立证明自身；应决定采用多大程度的外部 CI、签名和 hash-chain，
   以及这些机制是方法必选 core 还是可组合 capability profile。
4. **泛化性证据门槛**：三域 feasibility 足以说明可实例化，但不足以证明普遍有效；最终摘要中“domain-adaptable”
   的经验强度必须由外部实例化和共同 protocol 数据决定。

这些张力不是通过扩大口号解决，而应成为 evaluation 与 artifact 设计的显式问题。

---

## 14. 防 overclaim 记录

- `lab/research/claims.yaml` 当前仍为占位 claim；本文是定位与方法规范，不是已支持的 paper claim。
- ML 现有实现/replay 只作为 feasibility seed；self-hosting 只作为纵向可用性 case。
- 量化和计算科学当前没有真实实例。
- 对外部文献的精确引文、版本与机制边界，在论文写作阶段仍须回到原文逐项核验。
- 本方法不保证“绝对不能违反”，只在声明的 TCB、加载与执行假设下对已编码 invariant 提供 assurance。
