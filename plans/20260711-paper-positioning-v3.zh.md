# 论文定位 v3：高风险长时程 Agentic 工作空间的治理框架

> **文档角色**：本文件是论文定位 v3 的真源。它以 v2 的方法严谨性为基线，但对论文身份作框架层 pivot：
> 治理对象不再是“发现流水线”，而是承载高风险、长时程、多 session、多 agent 研究与构建活动的
> **工作空间 / lab**。本文不规定工作必须呈现何种形状，而是为其提供可实例化、可评测的治理框架。
>
> **相对 v2 的核心变化**：从治理工作本身的流程形状，改为治理工作所在的 workspace。治理与工作形状正交
> （shape-agnostic）：线性流程、分支探索、循环试验、开放式发现、工具构建和 agent 开发都可被同一组边界、
> 证据、连续性与防漂移机制包围，而不被压成固定 workflow。
>
> **当前状态**：positioning / method specification v3。ML 有实现与 replay 种子；agentic-system / 工具开发有本模板
> 的 self-hosting 纵向可用性 case；量化研究与计算科学尚无真实实例。因此现阶段只主张框架定义、实例化方法与
> 四域 feasibility agenda，不主张已经证明有效性、充分性或普遍 generality。

---

## 0. 一句话定位

> 我们提出一种面向 **lab-class workspace** 的环境编码治理框架：针对高风险、长时程、多 session、多 agent、
> artifact 密集且 claim 受证据约束的研究与构建工作，把领域风险转译为可执行、可审计、可恢复的
> policy boundary、evidence state、workspace topology、continuity state 与 capability bundle，并以持续
> conformance 和受治理演化维持这些约束；该框架治理工作所在的空间而不规定工作的形状，可由 domain profile
> 实例化到 ML 研究、量化研究、计算科学以及 agentic-system / 工具开发。

简短口号保留精神源头的表达：**Design the harness, not the agent.** 这里的 harness 不是一条预设生产线，也不是
包办所有 agent 基础设施的总称，而是承载边界、证据、状态、能力与恢复机制的 workspace-level governance surface。

### 核心命题

1. **治理对象是 workspace，不是 workflow。** 框架约束工作发生的环境，不把工作本身建模为固定顺序。
2. **治理与工作形状正交。** 同一框架既能包围一条严格 pipeline，也能包围分支、循环、协作、临时重规划和开放式
   agent 构建；工作形状可以改变，治理 invariant 仍可持续。
3. **产出类型不封顶于某类研究结果。** 产出可以是 metric、feature、factor、dataset、model、科学发现，也可以是
   tool、harness 或 agent 本身；框架约束产出如何形成、被证据支持、被交接和越过外部边界，而不预设产出内容。
4. **通用性限于 lab-class workspace。** 本文不治理所有 agent 或所有软件；普通 CRUD 项目若没有证据受约束的
   claim、昂贵或不可逆动作、长时程状态和 artifact provenance 等结构，不是本文的目标对象。

---

## 1. 精神根据：把 lab 的校准写进工作空间

精神源头 `.reference-docs/claude_code_optimization_spirit_zh.md` 提供了四个连续命题：

1. **Repo 是控制面，chat 是短期意识流。** 规范、状态和证据若只存在于 session 中，fresh context 无法可靠接续。
2. **Prompt 表达意图，hooks/permissions 承载约束。** 必须发生或必须阻断的行为不能只依赖自然语言遵从。
3. **研究不是普通 feature delivery。** 目标会变化、证据有等级、计算昂贵、代码与 claim 耦合，实验事实必须能
   追溯到 command、commit、run、config、artifact 与 verifier。
4. **造 agent 时必须区分外层 development harness 与内层 release agent。** 前者治理构建工作空间，后者是被构建、
   评测或发布的产出；两者相关但不能混成同一套 prompt 或状态。

这些原则的关键不是把研究或构建活动改造成一台机器，而是把 agent 当作在 lab 中工作的可变执行者：agent、模型、
工具、计划和任务拓扑都可能变化，workspace 则保存较稳定的边界、证据、责任与连续性。因此智识升级链应写为：

> 实验仪器式工作哲学  
> → repo-local 控制面实现  
> → 识别 lab-class workspace 的共同风险与持久状态  
> → 将治理与具体工作形状解耦  
> → 给出领域风险到 workspace control 的可操作实例化方法  
> → 用跨域共同 protocol 检验可迁移性、收益与代价

这条升级链不声称“一个好模板就是普适治理”，也不把 repo 目录结构本身当贡献。贡献候选是：对一类有明确风险结构
的工作空间，给出独立于具体实现布局的治理对象、实例化程序、assurance 过程与可证伪评测。

---

## 2. 核心 thesis：治理 lab-class workspace，而不是规定工作如何流动

### 2.1 什么是 lab-class workspace

本文把 lab-class workspace 定义为具有以下结构性特征组合的研究或构建环境：

- 工作跨多个 session、agent、分支、工具或执行环境，目标与路径可能在新证据出现后重规划；
- 执行可能昂贵或长时程，错误启动、继续、终止、覆盖、部署或发布具有显著且有时不可逆的代价；
- 产生大量需要索引、追溯、复现和生命周期管理的 artifact；
- 形成不得强于证据的 claim，例如模型性能、因子稳健性、科学发现，或 agent 的安全性、能力和发布就绪性；
- 工作状态不能只存在于 chat，fresh actor 必须能恢复当前目标、边界、证据、未决风险和下一步；
- 工作邻接外部强动作，例如云/HPC 作业、论文发布、实盘边界、生产部署或高权限工具接入；
- 多 agent 协作需要 ownership、可写面、责任和集成边界，且这些边界会随工作演化。

这些条件描述的是 workspace 的风险与状态结构，而不是一条必经顺序。同一个 lab 可以在一天内同时包含分支探索、
迭代调试、严格 benchmark、人工 review、工具临时构建和结果 promotion；框架不要求它们组成 DAG，更不要求每项
工作依次经过统一阶段。

### 2.2 Shape-agnostic 是方法要求，不是口号

**Shape-agnostic governance** 指治理 invariant 不依赖某个固定任务拓扑才成立：

- 若工作是严格 pipeline，框架可以治理其阶段边界、artifact 与 promotion；
- 若工作是循环实验，框架可以维持每轮证据、版本和恢复点；
- 若工作是分支探索，框架可以维持 ownership、分支关系和废弃状态；
- 若工作是开放式 agent 构建，框架可以约束工具权限、eval evidence、release gate 与部署边界；
- 若工作形状在 session 之间改变，治理状态仍能被迁移、检查和审计。

因此，框架规定的是**边界与证据纪律**，而不是**工作顺序**。它可以包围 pipeline，但不是 pipeline generator；
可以承载 workflow，但不是 workflow 产品。工作能做什么的上限主要取决于 agent、工具、资源与领域能力，而不是被
治理框架预先限定为某一种产出。

### 2.3 产出的开放性

被治理工作的产出可位于不同抽象层：

- 观测与中间对象：metric、日志、特征、因子、数据切片、table、figure；
- 研究与工程 artifact：dataset、checkpoint、model、仿真输出、代码、benchmark；
- 受证据约束的知识：性能结论、稳健性结论、机制解释、科学发现；
- 能力本身：tool、eval harness、agent development harness、production-grade agent 或交易类 agent。

当产出是 agent 或工具时，O2 不只记录“构建成功”，还必须关联 capability eval、failure trace、适用边界与 release
claim；O1 同时区分构建期 agent 的权限和待发布 agent 的生产权限；O5 则区分治理 workspace 的外层 capability
bundle 与作为内层交付物的 agent/tool。框架没有把“造 agent”降为软件工程附例，而把它视为一等 lab 域。

### 2.4 论文主张的强度

**方法主张**：lab-class workspace 可被统一分解为五类需要物化的治理对象，并通过两个横切 assurance process
维护；团队可以用明确的五步程序将 hazards、evidence semantics 与 execution boundaries 编译为 workspace controls，
而无需把领域工作压成固定流程。

**经验主张（待验证）**：与 prompt-only 或通用 coding-agent control plane 相比，加入 lab-class evidence、
continuity、artifact 与 irreversible-action semantics 的完整框架，能在可接受维护成本下改善违规阻断、claim
可追溯、context-loss 恢复和跨 provider 行为等价性，同时不显著压缩有效探索空间。

当前只把前者写成方法贡献，把后者写成可证伪 hypothesis。在四域共同评测完成前，不使用“证明领域无关”、
“适用于所有 agent”、“不限制创新”或“绝对不能违反”等表述。

### 2.5 非目标

- 不提出面向任意 agent 应用或任意软件项目的统一治理理论。
- 不把开放式工作改造成统一 pipeline、阶段机或预定义产物清单。
- 不替代 OS sandbox、云 IAM、broker risk engine、HPC scheduler policy、deployment control plane 或组织审计。
- 不声称通用 schema 能自动识别 look-ahead bias、浮点非确定性、agent reward hacking 等领域错误；这些由
  domain profile 和专用 validator 定义。
- 不把 repo hook 描述为对抗性安全边界，也不声称 validator 能证明治理完备、自身绝对完整或产出本身正确。
- 不把普通 CRUD web 项目仅因使用了 coding agent 就纳入范围；使用 agent 不是 lab-class 的充分条件。

---

## 3. 多维设计空间：治理机制不等于工作拓扑

工作形状与治理机制应画在不同层。任务可能线性、分支、循环、事件驱动或持续演化；治理机制则沿以下四个维度选择。
`AGENTS.md` 既是 prompt 表示，也是 repo 环境的一部分；远端签名 policy 可能比本地 hook 更强，而未加载的 hook
可能没有约束力。更准确的 Figure 1 是与工作拓扑正交的四维设计空间：

| 维度 | 典型取值 | 论文中的问题 |
| --- | --- | --- |
| **Policy representation** | 自然语言、结构化 schema、规则、可执行代码 | invariant 如何表达、组合、review，并在工作改形后继续成立？ |
| **Enforcement locus** | model、agent harness、repo、OS/container、远端服务 | 控制在哪里执行，谁能绕过，失效如何被发现？ |
| **Control type** | advisory、preventive、detective、recovery | 是解释偏好、阻断动作、检测偏离，还是支持失败后恢复？ |
| **Assurance level** | 未检查、人工复核、自动 conformance、外部/加密验证 | 对规则存在、已加载、语义等价和执行留痕能给出多强证据？ |

本方法不把 environment-encoded 定义为天然更硬，而要求团队显式选择每条 invariant 在四维空间中的落点，并测量
加载失败、语义漂移和 bypass。环境编码的价值是**外显、可组合、可复核、可跨 session 延续**，不是自动获得安全性。

Shape-agnostic 也不等于 process-free：某些领域可以选择 phase state machine，某些任务可以使用 pipeline 或审批流；
这些都是 domain profile 或局部 control placement，而不是框架对所有工作的本体假设。Figure 1 应把“工作拓扑”
画成可变化的内层活动，把四维治理控制画成包围它的外层选择空间。

---

## 4. 方法内核：5 类物化对象 + 2 个横切过程

### 4.1 五类 materialization object

| 对象 | 方法定义 | 最小输出 | 可判定 invariant / 失败语义 | 本仓库实例 |
| --- | --- | --- | --- | --- |
| **O1 Policy boundary** | 主体、动作、资产、工作情境与 human gate 的结构化边界，特别标记昂贵、外部或不可逆动作 | hazard register、action classes、policy rules、escalation/recovery contract | 禁止动作被阻断或明确升级；控制未加载、冲突、漏判、误判均记为失败 | `.agent/action-boundary.md`、settings/rules、`pre_tool_guard.py` |
| **O2 Evidence state** | intent/hypothesis、execution、artifact、metric/eval、claim 及其 provenance 和强度关系 | evidence lattice、claim schema、promotion gate、domain validity fields | claim 强度不得超过可解析证据；缺 run/config/eval source 或领域有效性检查则不可 promotion | `lab/research/{claims,evidence}.yaml`、artifact indexes |
| **O3 Workspace topology** | ownership、结构地图、可写目标、artifact 位置、并行隔离与状态 shape | topology map、owned/forbidden paths、same-change rules | 结构变化与地图/ledger 不一致为 drift；未知 ownership 阻止高风险改动 | `ANATOMY.md` 树、worktree ownership、drift checker |
| **O4 Continuity state** | 跨 session/agent 的目标、决策、证据状态、未决风险、执行状态与恢复协议 | checkpoint/handoff schema、session tree、resume test | fresh actor 无法在限定时间内恢复正确目标/边界，或沿用过期状态，即 continuity failure | `memory/current-status.md`、session tree、PreCompact 流程 |
| **O5 Capability bundle** | 可由 workspace 发现、版本化并适配执行面的 agent、skill、hook、validator 与工具集合 | canonical capability spec、adapter contract、manifest | adapter 缺失、语义不等价、依赖能力未加载或版本不兼容为 failure | `.claude/` canonical → `.codex/` / `.agents/` adapters |

五类对象回答“什么治理状态必须在 workspace 中持续存在”。它们不是目录清单，外部实现可以使用数据库、policy
service、CI、artifact store 或其他布局，只要产出等价 contract 并满足相同 invariant。

O5 尤其需要区分两层：**外层 governance capability bundle** 是支持构建工作的控制面；**内层 agent/tool artifact**
是工作产出。内层产出可以被外层框架构建和评测，但不能因为两者都包含 agent、tool、policy 或 eval 文件就混为一体。

### 4.2 两个横切 assurance process

| 过程 | 覆盖对象 | 作用 | 不能证明什么 |
| --- | --- | --- | --- |
| **A1 Continuous conformance** | O1-O5 | 检查 schema、引用、加载状态、adapter 等价、违规注入、结构/能力 drift，并保存可审计结果 | 不能证明 policy 完备、领域 claim 正确、探索空间未受任何影响或不存在未观测 bypass |
| **A2 Governed evolution** | O1-O5 及 A1 | 让 policy、schema、capability 与 workspace topology 的修改带 provenance、review、迁移、复测、降级与 recovery | 不能消除目标变化、产品漂移或依赖变化，只能让变化显式且可处理 |

`self-validation` 不是与五类对象并列的“第六原语”，而是 A1 对已声明 invariant 的持续检查。供应链完整性也不是
本文独占的新意；可以组合签名 lockfile、hash-chained audit log、外部 CI 等更强机制，缩小本地 validator 的可信基。

### 4.3 框架如何保持形状中立

O1-O5 只要求治理状态可识别和可检查，不要求活动依次经过 O1→O5，也不要求所有任务共享同一 phase。一个 agent
可以先构建 eval tool，再回到 hypothesis；一个量化研究分支可以被废弃；一个计算科学作业可以从 checkpoint 恢复；
一个 agent 产品可以多轮红队后重写行为契约。只要这些变化没有丢失边界、证据、ownership、连续性和 capability
语义，框架就不把非线性视为失败。

---

## 5. 从领域风险到 workspace control：五步实例化程序

外部团队能否只读论文与 reference artifact，在陌生 workspace 中完成实例化，是方法可迁移性的关键判据。Algorithm 1
应发布 schema、tailoring guide 与 conformance fixture，同时避免把算法误读为被治理工作的运行顺序：以下五步是
**治理框架的设计与校准程序**，不是领域工作的 pipeline。

### Step 1：工作空间描绘与 hazard elicitation

**输入**：研究/构建意图、参与主体与工具、资产、执行环境、外部系统、成本模型、已有 incident。  
**操作**：描绘可能反复出现的活动、状态、分支、循环、交接和外部边界；列出误启动、误继续、误终止、污染、
覆盖、越权 promotion、错误部署、失联与漂移。无需把活动强行排成单线状态图。  
**输出**：workspace map 与带 severity、reversibility、detectability、owner 的 hazard register。  
**失败**：存在没有 owner、没有恢复路径或无法归类的高严重度 hazard；或 workspace map 只能描述预想 happy path。

### Step 2：定义 invariant、schema 与 domain profile

**输入**：workspace map 与 hazard register。  
**操作**：把 hazard 映射到 O1-O5；定义主体/动作授权、evidence lattice、artifact provenance、continuity checkpoint、
topology ownership 和领域 validity fields；区分 core invariant 与 domain-specific validity。  
**输出**：core profile、domain profile 与可机器判定 invariant。  
**失败**：invariant 只写成愿望句、没有观测量；把领域正确性伪装成通用机制；或将某种工作顺序误设为全局 invariant。

### Step 3：选择 enforcement placement、composition 与 recovery

**输入**：invariant、执行面能力、工作拓扑变化方式、threat model。  
**操作**：在四维设计空间中为每条 invariant 选择 advisory、preventive、detective、recovery 控制；高代价动作优先
放到更小、更外部的可信边界，workspace control 负责准备、证据、检测和升级；定义多层 policy 的优先级与组合语义。  
**输出**：policy composition graph、冲突优先级、human gates、containment/recovery playbook。  
**失败**：控制可绕过却无检测；多个 policy 冲突无优先级；只有阻断没有恢复；或控制只在固定工作形状下有效。

### Step 4：编译 capability 与 provider adapters

**输入**：canonical profile、目标 provider/harness 能力矩阵、外层与内层 agent/tool 边界。  
**操作**：生成或配置 rules、hooks、skills、validators 与 adapter；对不能等价编译的能力显式降级并补偿，而非
假装 portable；当产出本身是 agent/tool 时，分别维护 development governance 与 release artifact contract。  
**输出**：provider-specific bundle、semantic mapping、unsupported-capability report、layer-boundary declaration。  
**失败**：adapter 语法成功但语义不等价；provider 不支持的强制点未暴露；或外层开发权限被错误继承到内层产品。

### Step 5：conformance、演化与完成判据

**输入**：实例化后的 O1-O5。  
**操作**：运行正常路径、非线性重规划、违规注入、控制未加载、context loss、治理变更和 recovery tests；记录
coverage、误报、漏报、维护时间、工作干扰与 bypass。  
**输出**：版本化 conformance report、已知缺口、复测周期、迁移/回滚计划。  
**完成判据**：所有高严重度 hazard 已映射到至少一个 control 和一个检测/恢复路径；core suite 通过；domain stressor
有明确结果；至少一种工作拓扑变化不破坏治理状态；未支持能力与 bypass 被记录而非隐藏。

---

## 6. 跨域实例化：四类 lab，共同治理关注点

泛化性不是把领域差异抹平，也不是假设四域共享工作顺序，而是检验同一 core 是否能由 domain profile 具体化。
下表的行是 lab-class workspace 反复出现的治理关注点，不是流程阶段。

| 治理关注点 | ML 研究 | 量化研究 | 计算科学 | Agentic-system / 工具开发 | 共同治理对象 |
| --- | --- | --- | --- | --- | --- |
| **假设或构建意图** | 架构、损失、数据、ablation 假设 | 算子、因子、特征、交易假设 | 机制、参数区间、数值方法假设 | capability、tool contract、agent behavior、eval 或 release 假设 | O4 保存意图、决策与分支；O3 标记 ownership |
| **昂贵或长时程执行** | 训练、评测、超参搜索 | 回测、walk-forward、因子检验、建模 | 仿真、HPC 作业、参数扫描 | trace 收集、benchmark、红队、长时 agent eval、部署前验证 | O1 管启动/继续/终止/资源边界；O5 提供受控能力 |
| **Artifact 与 provenance** | dataset split、config、run、checkpoint、metric | 数据快照、feature、factor、模型、回测账本 | 输入数据、代码/容器、mesh、trajectory、output | prompt/policy、tool schema、trace、eval set、harness、agent build、release bundle | O2 管 provenance/index；O3 管位置、ownership 与状态 |
| **受证据约束的 claim** | 模型性能、稳健性、机制解释 | alpha、稳健性、成本后表现、偏差控制 | 发现、数值结论、敏感性、不确定性 | capability、安全性、可靠性、适用边界、release readiness | O2 evidence lattice、domain validity fields 与 promotion gate |
| **产出类型** | metric、feature、dataset、model、paper claim | feature、factor、model、研究结论 | dataset、simulation、method、科学发现 | tool、eval harness、development harness、agent 或生产/交易类 agent | 框架不限定产出；O2 约束证据，O3/O4 维持生命周期 |
| **不可逆或外部动作边界** | 长训练重启、数据/checkpoint 覆盖、发布论文结论 | 实盘连接或下单边界、共享数据与模型发布 | 提交/取消昂贵 HPC 作业、继续烧算力、覆盖输出、发布结论 | 高权限 tool 接入、production deployment、发布 agent、接入真实交易/生产系统 | O1 human/external gate + recovery；A1 违规注入 |
| **跨 session / agent 连续性** | 多轮训练、debug、paper 修改 | 数据版本、因子谱系、回测口径、模型选择 | scheduler 状态、checkpoint、环境/数据库版本 | agent spec、tool contract、eval baseline、failure trace、release decision | O4 checkpoint/resume；A2 迁移与复测 |
| **工作形状变化** | 从探索转为 ablation，或多分支并行 | 因子淘汰、组合重构、口径回溯 | 参数分支、失败恢复、方法替换 | 从工具原型转为 agent、从 eval 失败回到 contract 重写 | O3 维护 topology；O4 保存决策；A2 治理变化 |

### 6.1 ML 研究边界

ML domain profile 需要处理 run/config/checkpoint 对齐、dataset split、长训练成本、metric provenance 与 paper claim
promotion。现有仓库只提供实现和 replay 种子，不等于已有 paper-grade effectiveness evidence。

### 6.2 量化研究边界

量化范围明确为**量化研究 workspace**。实盘系统本身仍需 broker、风控与 production control plane；实盘下单是
研究 workspace 通向不可逆外部动作的边界，只在 mock exchange 或 broker sandbox 中测试 gate，绝不以真钱压测。
Look-ahead bias、survivorship bias、交易成本和数据修订由量化 domain profile 负责，通用 schema 不会自动识别。

### 6.3 计算科学边界

计算科学不能被简化为确定性执行。domain profile 必须容纳随机模拟、浮点非确定性、并行归约、容器/编译器、
外部数据库版本、数据许可、checkpoint 与安全取消；昂贵作业的错误继续和错误终止都属于 hazard。

### 6.4 Agentic-system / 工具开发是一等域

构建、评测和发布 agent 或工具本身具有 lab-class 结构：行为目标会随 trace 和 eval 改变；产物包含 policy、tool
schema、harness、dataset、trace、benchmark 和 release bundle；capability claim 必须受 eval evidence 约束；高权限
tool、生产部署或交易接入是昂贵或不可逆边界；工作天然跨 session、多 agent 和多个执行 surface。

“构建生产级/交易类 agent”可作为该域的代表性场景，但本文不臆造任何私有项目细节，也不声称 repo control 可替代
生产 IAM、deployment gate、broker risk engine 或实时监控。

本模板的 self-hosting 应归入此域：它使用该框架治理“构建一个 agent development harness”这项工作，因而是
**用框架造 agent/harness 的活证据**。但它仍只是作者内生、纵向的可用性与演化 case，不是独立样本，不能单独证明
因果有效性、充分性或跨域 generality。

---

## 7. 与最近工作的关系：治理对象不同，机制可组合

### 7.1 对 arXiv:2606.26924 的事实更正

v1 对 *A Deterministic Control Plane for LLM Coding Agents* 的描述有误；v3 延续 v2 的明确更正，撤回“无实证、
单 harness、不跨 provider/target、缺乏完整性机制”等说法。该工作实际包含：

- 10,008 仓库规模的 prevalence study；
- injected-violation conformance tests；
- canonical definition 向七个 target 的编译；
- HMAC lockfile 与 hash-chained audit log；
- tiered permissions 与 phase state machine。

这些能力不是本文差异化的反面教材，而是可复用的通用 coding-agent control-plane 与供应链完整性基础。

### 7.2 Compose-not-compete 差异轴

| 比较轴 | Deterministic Control Plane | 本文框架 | 组合关系 |
| --- | --- | --- | --- |
| **治理对象** | 通用 coding agent 的编码活动与 agent definition/control-plane integrity | lab-class workspace 的证据、artifact、连续性、拓扑及昂贵/不可逆动作边界 | 前者可作为后者的执行与完整性底座 |
| **工作形状** | 可使用 phase state machine 组织编码控制 | 对工作拓扑不作统一规定，允许线性、分支、循环、开放式构建 | phase machinery 可作为某个 profile，而非框架本体 |
| **核心状态** | phase、permission、requirement/file/test trace、policy artifact | intent/hypothesis、execution、artifact、evidence/claim、session continuity、domain profile | lab 状态可叠加到通用 state machinery |
| **证据语义** | conformance 与工程 traceability | claim 强度受 provenance、eval 和领域有效性约束 | 复用 audit log，扩展 lab-evidence schema |
| **跨 session 目标** | 编码控制面的确定执行与审计 | 研究/构建意图、未决风险、证据状态和 claim promotion 的恢复 | 通用 audit + domain continuity checkpoint |
| **边界对象** | 编码权限与 agent definition 供应链 | 训练、回测、仿真、部署、研究资产、发布/下单/HPC 边界 | repo gate 与 OS/cloud/broker/deployment 强边界组合 |
| **产出范围** | 主要治理 coding activity 与 agent definition | 从 metric、dataset、model、发现到 tool、harness、agent | 通用控制面可承载构建，本文补充产出证据与生命周期语义 |
| **Assurance** | conformance、lockfile、hash-chained audit、target compilation | 对 O1-O5 的 core + domain conformance 与 governed evolution | 直接采用其完整性机制，评估增量语义的收益与成本 |

因此本文不主张“我们比它更有实证”或“我们首次跨 target”。真正问题是：

> 在可靠的通用 agent control plane 之上，lab-class workspace 还需要哪些证据、artifact、连续性、拓扑与外部边界
> 语义；这些增量能否在不规定工作形状的前提下跨研究和 agent-building 域复用？

最强 baseline 应是“Control Plane 等价配置 + 本文 lab profile”，而不是制造互斥竞争。

Russo 的 repository-level governance 工作主要提供分析单位与问题动机：repository ecosystem 的效应不能还原为
单次 agent 行为。本文提供面向 lab-class workspace 的可执行实例化与 evaluation agenda，不把测量贡献贬为
“只有数据”，也不声称 artifact system 与 ecosystem measurement 是对称替代品。

---

## 8. Evaluation：四域 feasibility + 共同 protocol

### 8.1 当前可声称什么

- **ML 研究**：本仓库提供方法构件与 replay 种子，但 `lab/research/claims.yaml` 仍是占位状态；尚无 paper-grade claim。
- **量化研究**：当前为 0 真实实例，只能作为预注册迁移目标。
- **计算科学**：当前为 0 真实实例，只能作为预注册迁移目标。
- **Agentic-system / 工具开发**：本模板提供 self-hosting 纵向可用性 case，说明该框架能够参与构建和演化一个
  agent development harness；它不是外部独立验证。
- **Self-hosting 的证据边界**：可测量持续使用、维护成本、治理演化和恢复行为；不单独证明 effectiveness、
  necessity、sufficiency 或 generality。

四域的作用是测试同一方法能否被实例化并产生可比较测量，即 **feasibility + analytical replication**，不是凭四个
purposive case 证明领域无关。原三域 protocol 不撤销，而是增加 agentic-system 域，并让 self-hosting 成为该域的
具体 case。

### 8.2 每域相同的 core protocol

每个域运行同一组任务，只替换 domain profile 和领域 artifact：

1. **Risk-to-control instantiation**：从 workspace/hazard 得到 O1-O5，记录时间、歧义、未映射 hazard 和所需专用机制。
2. **Provider A/B execution**：在两个受支持 harness 上执行相同正常任务与受限任务，检查语义等价与能力降级。
3. **Injected violation**：注入受保护资产写入、越权昂贵动作、证据缺失的 claim promotion、错误 ownership 等违规。
4. **Context loss/recovery**：移除 chat context，由 fresh actor 仅凭 continuity state 恢复目标、边界、证据和下一步。
5. **Governance change/drift**：修改 schema、adapter、capability 或 topology，检查检测、迁移、回滚和 audit trail。
6. **Claim promotion**：从输出生成候选 claim，验证 provenance、证据强度、domain validity 与 human gate。
7. **Shape-change test**：在执行中引入分支、回退、重规划或产出类型变化，检查治理是否仍成立且没有强迫回到固定流程。

### 8.3 每域一个 domain-specific stressor

| 域 | Stressor | 安全执行方式 |
| --- | --- | --- |
| ML | run/config/checkpoint 错配或长训练误重启 | 小型 fixture / synthetic run，不启动真实长训练 |
| 量化 | look-ahead、survivorship 或 cost 字段缺失，并尝试越过实盘边界 | 历史小样本 + mock exchange / broker sandbox，绝不真实下单 |
| 计算科学 | 非确定性环境/provenance 缺失，或昂贵作业错误继续/取消 | 本地小仿真 + scheduler mock，不提交真实昂贵 HPC 作业 |
| Agentic-system / 工具开发 | eval evidence 缺失却 promotion，外层开发权限泄漏到 release agent，或尝试越权部署 | synthetic agent/tool fixture + sandbox deployment target，不接生产或真实交易系统 |

### 8.4 指标、baseline 与 ablation

**共同指标**：违规阻断 recall、false-positive rate、控制未加载检测率、adapter 行为等价率、drift detection
precision/recall、claim provenance completeness、错误 promotion 阻断率、恢复成功率/时间、任务成功率、human
intervention、实例化时间、维护时间，以及 shape-change 后治理 invariant 保持率。

为检验“治理不压缩工作形状”，还应记录：被 governance 阻断但经 adjudication 判定合法的探索比例、额外 human
gate 数量、重规划成功率和治理导致的任务延迟。Shape-agnostic 不能只靠定义成立，必须测量框架是否把合法的非线性
活动误判为 drift 或越权。

**Baselines**：prompt/`AGENTS.md` only；通用 Control Plane 等价配置；完整框架。  
**Ablations**：移除 evidence state、continuity state、continuous conformance；另加入“固定 phase/pipeline profile”
与 shape-agnostic profile 的对照，观察灵活性、违规检测和恢复指标。

至少加入一个外部团队的 blind instantiation，检验方法能否脱离作者与本仓库复现。只有共同 protocol 在异质域有数据
后，摘要才可把 domain-adaptable 从设计主张升级为经验结论。

---

## 9. 威胁模型、可信计算基与诚实边界

### 9.1 主要威胁

- agent 忽略或误解自然语言 policy；
- provider adapter 编译成功但语义漂移；
- hook/validator 未加载、被错误配置或遗漏某类动作；
- session 丢失导致沿用过期目标、错误 artifact 或错误边界；
- claim 与 run/config/artifact/eval 断链，或 domain validity 字段缺失；
- 工作拓扑改变后，治理继续引用过期 ownership、状态或假设；
- 治理代码与 schema 同时被错误修改，使内部检查出现递归信任问题；
- 构建 agent/tool 时，外层 development harness 与内层 release artifact 权限或 contract 混淆；
- 人类或受信代码显式 bypass 本地控制；
- 过强或过窄的治理误阻合法探索，使 shape-agnostic 退化为空洞承诺。

### 9.2 可信计算基（TCB）

最小 TCB 包括：workspace checkout 与版本历史、harness 的 policy/hook 加载机制、validator/runtime、
canonical-to-provider adapter、执行这些检查的 CI 或外部服务，以及有权批准高风险动作的人类。

对资金、云/HPC、生产数据和 production agent deployment，TCB 必须扩展到 broker risk engine、IAM、scheduler、
sandbox/container、deployment control plane、runtime monitoring 和组织审计；repo 不是它们的替代品。

应优先把完整性检查放到比被检对象更小或更外部的根上。arXiv:2606.26924 的 HMAC lockfile、hash-chained audit
log 等机制可直接作为 capability/integrity layer 组合进来。

### 9.3 Bypass 假设与表述边界

本地 hook 是防误操作护栏，不是对抗性 sandbox；`--no-verify`、`SAME_COMMIT_SKIP=1`、未信任 repo hooks、受信
`python -c`/测试代码和直接调用外部系统都可能绕过或超出观测面。方法应记录并测试这些 bypass，而不是宣称消失。

Shape-agnostic 也有诚实边界：任何 schema 都会对工作施加表示成本，任何 gate 都可能影响探索。本文只主张不把
某一种任务拓扑设为框架必要条件，不主张治理对行为完全中性或没有机会成本。

因此可守的结论是：

> 在明确的 harness、trust 与 execution assumptions 下，本框架提高 lab-class workspace 中已指定 invariant 的
> 可执行性、可审计性、可恢复性与跨执行面一致性，同时允许领域工作采用不同和可变化的拓扑；conformance 结果
> 只覆盖已编码 invariant 与已观测路径，不证明治理完备、产出正确或探索不受任何影响。

---

## 10. 可发表贡献包

1. **对象层贡献**：面向 lab-class workspace 的 5-object + 2-process 治理模型，明确区分通用 core、domain profile、
   外层 governance harness 与内层 agent/tool artifact。
2. **框架层贡献**：把治理对象从工作流程移到 workspace，提出并可操作化 shape-agnostic governance，允许结果从
   metric、dataset、model、科学发现延伸到 tool、harness 与 agent。
3. **程序层贡献**：从 workspace/hazard elicitation 到 conformance/evolution 的五步实例化算法、failure semantics
   与完成判据；该算法用于校准治理，不规定领域工作的运行顺序。
4. **Artifact 贡献**：reference schema、tailoring guide、provider adapter contract、conformance suite，以及覆盖至少
   两个异质域且包含 agentic-system 开发的实例。
5. **经验贡献（待实验）**：共同 protocol 下相对 prompt-only、通用 Control Plane baseline、固定流程 profile 与
   ablation 的收益、成本和工作形状保持情况。

这是一篇 **artifact-centered system/method paper about governing lab-class workspaces**，不是 workflow 产品论文、
纯哲学 position paper，也不是“目录很多”的 template paper。

---

## 11. 标题候选

### 首选

**Governing the Lab, Not Shaping the Work: A Framework for High-Risk, Long-Horizon Agentic Workspaces**

中文：**治理 Lab，而非规定工作形状：面向高风险长时程 Agentic 工作空间的框架**

首选标题直接表达这次 pivot：论文提供治理框架，不把开放式工作压成机器或流水线。

### 备选

- **Design the Harness, Not the Agent: Shape-Agnostic Governance for Long-Horizon Research and Agent-Building Workspaces**
- **The Workspace as a Governance Surface: Evidence, Continuity, and Boundaries for Agentic Labs**
- **From Metrics to Agents: Environment-Encoded Governance for High-Risk, Evidence-Constrained Workspaces**
- **Governing Open-Ended Agentic Work: A Domain-Adaptable Method for Research and System-Building Labs**

避免标题使用 “discovery pipeline”、“universal agent governance” 或无边界的 “governance for all agentic work”。
“Lab”应由副标题中的高风险、长时程和 evidence-constrained 限定，避免被理解为所有软件仓库。

---

## 12. Venue 与节奏

### 阶段 1：非归档 workshop / 内部 pilot

定位为 **framework + method specification + evaluation agenda**。交付威胁模型、5+2 模型、五步程序、reference
schema、一个 ML pilot，以及 agentic-system self-hosting 的纵向描述。量化与计算科学明确为待实例化，不在摘要中
声称四域有效。

### 阶段 2：CAIN / FSE / ICSE 风格完整稿

完成至少两个真正异质域、两个 provider、直接 Control Plane baseline、failure injection、shape-change test、
维护成本、外部 blind instantiation 和 replication package。正会新增贡献不能只是多几个 case，而应包含方法规范、
跨域数据、灵活性测量和可复用 artifact。Agentic-system 域使 CAIN / agentic software assurance 更自然，但不能因
“造 agent”而扩大为面向所有 agent 的普适理论。

### Stop / go 判据

- 若只能完成方法 spec + ML pilot + self-hosting 描述：投非归档 workshop/vision/design 体裁。
- 若完成两个异质域但无外部实例化、直接 baseline 或 shape-change 测量：适合聚焦工具/经验轨道，不宣称 general
  effectiveness 或 shape neutrality 已被证实。
- 只有共同 protocol、baseline/ablation、外部实例化、灵活性测量与 artifact 齐备，才进入正会方法/系统主张。

---

## 13. 当前开放张力

1. **Shape-agnostic 与必要结构之间的张力**：框架必须保存 evidence、ownership 和 continuity，却不能悄然把这些
   schema 变成统一 workflow；需要定义哪些是最小治理结构，哪些只是 profile 选择。
2. **灵活性与 assurance 的张力**：边界太弱无法提供保证，太强会阻断合法探索；应以误报、重规划成功率、额外
   human gate 和任务延迟测量，而不是只在叙事中宣称“不限制工作”。
3. **Core 与 domain profile 的边界**：若 look-ahead bias、非确定性 provenance、agent reward hacking 都依赖专用
   validator，需要用实例化成本和复用比例证明这不是“每域重写一套治理”。
4. **外层 harness 与内层 agent 的边界**：造 agent 时两层都包含 policy、tool、eval 和 action boundary；需要稳定
   schema 防止开发权限、治理 claim 或 trace 被错误继承到 release artifact。
5. **Repo control 与外部强控制的分工**：越高风险的动作越应由 broker、IAM、scheduler、deployment system 执行；
   论文需证明 workspace-level 方法在不冒充安全边界的前提下，仍对准备、证据、升级、审计和恢复产生可测增量。
6. **Assurance 的递归信任**：本地 validator 无法独立证明自身；应决定外部 CI、签名和 hash-chain 是必选 core 还是
   可组合 capability profile。
7. **泛化性证据门槛**：ML seed、self-hosting 和两个预注册域足以构成 feasibility agenda，不足以证明普遍有效；
   最终摘要中 domain-adaptable 的经验强度必须由外部实例化和共同 protocol 数据决定。

这些张力不是通过扩大口号解决，而应成为 evaluation 与 artifact 设计的显式问题。

---

## 14. 防 overclaim 记录

- `lab/research/claims.yaml` 当前仍为占位 claim；本文是定位与方法规范，不是已支持的 paper claim。
- ML 现有实现/replay 只作为 feasibility seed。
- Agentic-system self-hosting 是“用框架构建 agent development harness”的纵向可用性 case，不是独立样本，不单独
  证明 effectiveness、necessity、sufficiency 或 generality。
- 量化研究和计算科学当前没有真实实例。
- 四域是 analytical replication agenda，不是统计代表性样本，也不证明适用于所有领域。
- Shape-agnostic 只表示框架不要求固定工作拓扑，不表示治理完全不影响行为或没有表示、维护和审批成本。
- “产出可到 agent/工具”是适用范围陈述，不是已经构建或安全发布 production/trading agent 的经验 claim。
- 对外部文献的精确引文、版本与机制边界，在论文写作阶段仍须回到原文逐项核验。
- 本框架不保证“绝对不能违反”，只在声明的 TCB、加载与执行假设下对已编码 invariant 提供 assurance。
- 普通 CRUD 项目不会仅因使用 coding agent 自动成为本文所称 lab-class workspace。

---

## 15. v3 的最小审稿人读法

审稿人应能把本文压缩为以下可检验问题：

> 对于高风险、长时程、多 agent、artifact 密集且 claim 受证据约束的 workspace，能否用同一组治理对象和实例化
> 方法，在不规定工作拓扑与产出类型的前提下，把领域 hazard 转译为可执行、可审计、可恢复的控制；相对
> prompt-only 和通用 coding-agent control plane，这些增量是否带来可测收益，其灵活性与维护代价是什么？

若论文无法用共同 protocol、直接 baseline、shape-change test、外部实例化和诚实 TCB 回答这一问题，就应停留在
framework / design paper，而不升级为已验证的通用方法。
