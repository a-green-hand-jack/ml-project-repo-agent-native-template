# 论文定位 v5：不固定工作形状的 Lab-Class Agentic 工作空间治理

> **相对 v3 吸收 fable-5 六条硬伤。** 本版不是重新 pivot，而是在 v3 的 5 对象 + 2 过程、五步实例化程序、
> 四维设计空间、威胁模型/TCB、feasibility 协议与防 overclaim 骨架上定点加固：形式化 shape 与 invariant，
> 为 workspace pivot 增加可执行机制；钉死第 4 域边界；取消 self-hosting 的证据膨胀；把自举案例接入真实
> capability claim 证据链；把 compose-not-compete 降为待验证假设；补齐身份、授权、资源预算与 policy 组合语义。
>
> **当前证据状态**：四个候选域均为 **0 个非 self 实例**；现有证据只有 **1 个 self-hosting case**。
> `lab/research/claims.yaml` 仍是占位台账。本文因此只提出方法规范、可证伪机制与 feasibility agenda。
> 外部团队的 blind instantiation 是任何 effectiveness 表述的前置条件；在满足前，论文摘要不得出现
> effectiveness 词族，第 4 域也不得被计为“已有实例”。

---

## 0. 一句话定位

> 我们提出一种面向 **lab-class workspace** 的环境编码治理框架：它把领域风险转译为可执行、可审计、
> 可恢复的边界、证据、拓扑、连续性与能力状态，并通过持续 conformance 与受治理演化，使 lab-class 的
> evidence、continuity 和 boundary assurance **不以固定领域工作拓扑为前提**。

简短口号仍是 **Design the harness, not the agent.** 这里的 harness 是 workspace-level governance surface，
不是预设生产线，也不是对 OS、IAM、scheduler、deployment control plane 或领域 validator 的替代。

### 核心命题

1. **治理对象是 workspace，不是 workflow。** 框架物化治理状态，不规定领域活动必须按统一阶段运行。
2. **贡献是“灵活性 + 保证”的联合命题。** Prompt-only 同样可能不规定形状；本文要检验的是不固定工作形状时，
   evidence、continuity 与 boundary invariant 是否仍可保持，以及保持它们的代价。
3. **产出类型开放，但范围有门槛。** 产出可为 metric、dataset、model、发现、tool、harness 或 research-grade
   agent；开放产出不等于覆盖所有软件开发或产品发布。
4. **通用性限于 lab-class workspace。** 是否准入由 §2.1 的可操作判据决定，而非仅凭“用了 agent”。

---

## 1. 精神根据与可证伪 pivot

框架继承四个校准：repo 是控制面而 chat 是短期意识流；prompt 表达意图而可执行控制承载硬边界；研究 claim
必须受证据约束；造 agent 时外层 development harness 与内层 artifact 必须分开。v5 不再把 workspace pivot
只写成叙事，而把它压成定义、机制和主实验。

### 1.1 Shape 与 invariant 的形式定义

令一次领域工作实例为迁移系统 `W = (A, E, ->_W)`：

- `A` 是领域活动集合，例如提出假设、训练、回测、仿真、调试、红队或重写 contract；
- `E` 是领域产物与事件；
- `->_W` 是实际发生的迁移关系。领域工作 **shape** 是对 `A` 的偏序或对 `->_W` 可接受路径施加的约束
  `S(W)`，例如“训练必须在评测前”“所有任务必须依次经过五个 phase”。

令治理状态为 `G = (g1, ..., g5)`，分别对应 O1-O5。治理 **invariant** 是状态谓词
`I_k(G, obs) -> {true, false, unknown}`；它约束治理对象当前是否满足边界、证据、ownership、连续性或能力语义，
而不是规定任意两个领域活动的先后。`unknown` 必须物化为未加载、证据不足或观测面缺失，不能静默当作通过。

对某个 profile `P`，若改变 `W` 的合法拓扑而不改变已声明 hazard 后，所有 core invariant 仍可被迁移和判定，且
framework 没有额外要求统一的 `S(W)`，则称该 profile 对这次 shape change 保持 shape-agnostic。

### 1.2 五对象的状态谓词与两个诚实例外

| 对象 | 状态谓词示例 | 是否约束领域活动 shape |
| --- | --- | --- |
| O1 Boundary | 主体有可解析授权；昂贵动作有 gate；policy 组合无静默冲突 | 否；约束 action state |
| O2 Epistemic evidence | claim 强度不超过其 provenance/eval 所支持的层级 | 一般否 |
| O3 Topology | ownership、位置、结构地图与当前 workspace 一致 | 否；描述当前形状而不规定形状 |
| O4 Operational continuity | fresh actor 能恢复当前目标、下一步与 O2 引用 | 否 |
| O5 Capability | canonical spec、adapter 与加载状态可解析，非等价可被检测 | 否 |

有两个必须承认的例外：**promotion gate** 要求证据满足条件后 claim 才能升级；**human gate** 要求批准发生后
昂贵/不可逆动作才可越界。二者确实约束治理状态迁移，但只约束 claim/action 的授权迁移，不规定研究、构建或
探索活动的全局排序。v5 不把这两个例外重新命名后藏掉，而把 gate 数量、延迟和误阻率纳入主实验。

### 1.3 Pivot 的机制足迹：Shape-Change Invariant Checker

v5 新增一个由 pivot 直接驱动的 reference mechanism：**shape-change invariant checker**。它不是普通 schema lint。

- **输入**：变化前后的 workspace topology、O1-O5 快照、已声明 hazard/invariant、允许的 migration rule。
- **操作**：对 branch、merge、回退、循环、任务重规划或产出类型变化生成状态映射；检查每个 invariant 是
  preserved、migrated、violated 还是 unknown；禁止用“拓扑改变”自动解释掉 violation。
- **输出**：逐 invariant preservation report、悬空 ownership/O2 引用、过期 gate、unsupported migration 与恢复建议。
- **失败语义**：无法映射的状态、静默丢失的 evidence/authorization、过期 continuity、checker 未加载或把 unknown
  当 pass 均计为失败。
- **artifact 要求**：reference schema、正负 fixtures、至少四类 shape change、provider-neutral report contract。

该 checker 与“固定 phase profile vs shape-agnostic profile”的对照共同构成主实验，而非附带 ablation。

---

## 2. 核心 thesis 与范围判据

### 2.1 Lab-class 的可操作准入

一个 workspace 只有同时满足以下三项必要条件，才进入本文 core scope：

1. **Evidence-constrained claim**：存在强度不得超过证据的实质 claim，且错误 promotion 会造成真实后果；
2. **Costly or irreversible action**：存在昂贵、外部或不可逆的启动、继续、终止、覆盖、发布、部署或接入动作；
3. **Cross-session state**：目标、授权、证据与执行状态必须跨 session/actor 恢复，不能只依赖当前 chat。

加重因子包括：artifact 密集、多 agent ownership、长运行、外部强控制邻接、目标随新证据变化、多个执行 surface、
以及资源消耗需归因。加重因子影响 assurance 强度，不替代三项必要条件。准入 checklist 必须给出每项的 artifact
锚点、owner 与反例；无法给出则不准入。

该判据确实会放行少数 high-stakes 软件工程。v5 对第 4 域作明确选择：**收窄为 research-grade agent/harness
development**，即行为目标随 trace/eval 演化、capability spec 尚未稳定、claim 仍处于研究性证据积累阶段的开发
workspace。成熟产品的常规发布、稳定 SLO 服务的日常 release engineering、生产运行时治理与组织合规流程不在
本文范围；它们可以提供外部 control，也不是本文要替代的对象。

### 2.2 论文主张强度

**当前方法主张**：lab-class workspace 可分解为五类物化治理对象和两个横切过程；团队可用五步程序把 hazard、
evidence semantics 与 execution boundary 编译为 controls，而不要求统一领域工作拓扑。

**待验证联合假设 H1**：相对 prompt-only、通用 control plane 和固定 phase profile，完整框架能在 shape change
下保持更多已声明 invariant，并以 §8 指标量化误阻、gate、延迟、维护与恢复代价。

**经验措辞门槛**：在外部 blind instantiation 完成前，不作 effectiveness 表述；只报告 feasibility、存在性、
检测结果与观测到的代价。跨 provider 目标是 **非等价的可检测性**：当前仅两个同源、同作者机械生成的 surface，
相似输出很大程度上是构造结果，实验应检验偏差能否被暴露。

### 2.3 四维设计空间

| 维度 | 典型取值 | 需要回答的问题 |
| --- | --- | --- |
| Policy representation | 自然语言、schema、规则、代码 | invariant 如何表达、组合、review 与迁移？ |
| Enforcement locus | model、harness、repo、OS/container、远端服务 | 谁执行、谁可绕过、未加载如何发现？ |
| Control type | advisory、preventive、detective、recovery | 阻断、检测与恢复如何配套？ |
| Assurance level | 未检查、人工、自动 conformance、外部/加密验证 | 证据覆盖什么，TCB 在哪里？ |

四维治理控制包围可变化的领域活动。某个 domain profile 可以选 phase machine，但不能把它误写为 framework 本体。

---

## 3. 方法内核：5 类对象 + 2 个横切过程

### 3.1 五类 materialization object

| 对象 | 方法定义与最小输出 | 可判定 invariant / 失败语义 |
| --- | --- | --- |
| **O1 Policy boundary** | 主体、授权、动作、资产、情境、资源与 gate 的边界；最小输出含 hazard register、**subject registry + attribution rule**、authorization matrix、policy composition graph、resource/budget ledger、escalation/recovery contract | 未登记主体、不可归因操作、授权过期、昂贵动作未升级、累计成本无归因、policy 静默冲突、控制未加载/漏判/误判均失败 |
| **O2 Epistemic evidence state** | 只保存“相信什么、凭什么、强度几何”：hypothesis、artifact、metric/eval、claim、provenance、domain validity；输出 evidence lattice、claim schema、promotion rule | claim 超过证据层级、缺 run/config/eval source、引用不可解析或 validity 未检查则不可 promotion |
| **O3 Workspace topology** | ownership、结构地图、可写目标、artifact 位置、并行隔离与当前 shape；输出 topology map、owned/forbidden paths、same-change rules | 结构与地图/ledger 不一致、未知 ownership、shape migration 后悬空引用为 drift |
| **O4 Operational continuity state** | 只保存“正在做什么、下一步是什么”：目标、决策、执行状态、未决风险、恢复协议；对 O2 **只持稳定引用，不复制证据内容** | fresh actor 无法恢复、沿用过期状态、O2 引用失效或复制后口径漂移为 continuity failure |
| **O5 Capability bundle** | 可发现、版本化、可适配的 agent、skill、hook、validator 与工具；输出 canonical spec、adapter contract、manifest | adapter 缺失、非等价不可检测、能力未加载、版本不兼容或外层权限泄漏给内层 artifact 为失败 |

资源/预算台账至少记录累计消耗、剩余额度、预算 owner、成本所归属的 hypothesis/task/run，以及启动/继续/取消的
授权状态。对量化与 HPC，它是一等治理状态，不得只作为日志附注。多层 policy 的 effective result、优先级、冲突、
降级和来源同样必须物化；静默冲突本身就是可注入、可检测的 failure。

### 3.2 两个横切 assurance process

| 过程 | 作用 | 边界 |
| --- | --- | --- |
| **A1 Continuous conformance** | 检查 O1-O5 schema、引用、加载、预算、policy 组合、adapter 非等价、违规注入、shape migration 与 drift | 只覆盖已声明 invariant 与已观测路径 |
| **A2 Governed evolution** | 让 policy、schema、capability、topology 和 A1 自身的变化带 provenance、review、迁移、复测、降级与 recovery | 是 **governance of governance**：同一框架对治理自身的反身应用，但仍需外部信任根 |

A2 的反身性解释了为何治理变化也要被治理，但不消除递归信任；外部 CI、签名、hash-chain 或更小的 verifier 仍是
缩小 TCB 的候选 capability。

---

## 4. 从领域风险到 workspace control：五步实例化程序

以下是治理框架的设计与校准程序，不是领域工作的 pipeline。

### Step 1：准入、workspace 描绘与 hazard elicitation

先执行 §2.1 checklist；不满足三项必要条件则记录为边界外项目并停止完整实例化。对准入项目描绘主体、资产、
活动、分支、交接、资源与外部系统，列出误启动、误继续、误终止、越权 promotion、错误发布、失联和漂移。
输出 workspace map、subject seed、cost model 与带 severity/reversibility/detectability/owner 的 hazard register。

### Step 2：定义 invariant、schema 与 domain profile

把 hazard 映射到 O1-O5；定义授权、policy composition、budget、evidence lattice、artifact provenance、O2/O4 引用、
topology ownership 与领域 validity。每条 invariant 必须是可观测的状态谓词，并注明是否属于 promotion/human gate
例外。输出 core/domain profile、predicate catalog 与 failure semantics。

### Step 3：选择 enforcement placement、组合与 recovery

在四维空间选择 advisory、preventive、detective、recovery placement；高代价动作优先交给更小、更外部的可信边界。
输出 effective-policy graph、冲突优先级、human gates、budget gates、containment/recovery playbook。没有优先级、
只有阻断无恢复、或冲突被静默吞掉都不合格。

### Step 4：编译 capability、provider adapter 与 shape migration

生成 rules、hooks、skills、validators、adapter 和 shape-change invariant checker fixtures。不能等价编译的能力必须
显式降级并可检测；外层 development authorization 不得继承给内层 agent/tool artifact。输出 semantic mapping、
unsupported-capability report、layer boundary 与 migration contract。

### Step 5：conformance、演化与完成判据

运行正常路径、违规注入、policy 冲突、budget overrun、control unload、context loss、shape change、治理变更和 recovery。
完成要求：所有高严重度 hazard 有 control + 检测/恢复路径；core suite 通过；shape checker 不把 unknown 当 pass；
已知 bypass 和 unsupported migration 被登记；报告可由 fresh actor 复核。

---

## 5. 四域实例化与第 4 域边界

四域只是预注册的 analytical-replication agenda，当前均为 0 个非 self 实例。

| 域 | Domain profile 重点 | 安全 stressor |
| --- | --- | --- |
| ML 研究 | split/config/run/checkpoint、训练预算、metric provenance、claim promotion | synthetic run 错配或长训练误重启，不启动真实长训练 |
| 量化研究 | 数据修订、look-ahead/survivorship/cost、回测预算、实盘边界 | 历史小样本 + mock exchange，绝不真实下单 |
| 计算科学 | 非确定性、环境/数据库许可、HPC 预算、checkpoint 与安全取消 | 本地小仿真 + scheduler mock，不提交昂贵作业 |
| Research-grade agent/harness 开发 | 行为目标随 trace/eval 演化、capability claim 未稳定、外层/内层授权边界 | synthetic agent fixture + sandbox target，不接生产系统 |

### 5.1 第 4 域明确收窄

第 4 域只研究 **development workspace 的治理**：capability hypothesis、trace/eval provenance、failure-driven contract
演化、跨 session continuity、工具权限和候选 release artifact 的边界。成熟产品常规发布、生产部署批准、运行时安全、
合规 certification 和 SLO change management 由既有 release/deployment governance 负责，不是本文贡献。

第 4 域只有出现至少一个 **非 self 的 research-grade agent/tool 项目 case** 才能计为“有实例”。self-hosting 不得
把有实例域从 0/4 写成 1/4，更不能与同仓库的多个 replay/stress 记录重复计数。

### 5.2 第 4 域 related-work 轴

完整论文需单列并核验以下工作族：release engineering 与 change management；eval-gated deployment；MLOps/model
registry；model/agent cards；preparedness/release policy；NIST AI RMF 等风险治理框架。本文与它们的差异不在“首次
用 eval 决定发布”，而在 **capability spec 尚未稳定时 development workspace 的证据、连续性、授权、资源与演化
如何共同治理**。精确文献、版本和边界在写作阶段回到原文核验，不以二手数字扩散。

### 5.3 边界外阴性对照

evaluation 加入一个成熟、低变动、无 research claim 的常规 CRUD/service 项目。预注册预期是 §2.1 准入失败，
完整框架相对 prompt-only/control plane 的增量小而维护成本上升。若它反而被准入或显著受益，应重新审查范围，
不能事后把项目改称 lab-class。

---

## 6. Self-hosting：只算一个退化 case，并修成证据链

现有 self-hosting 演练的是退化情形：内层产物就是 harness 本身，从未跨真实 release/deployment 边界；validator
证明治理制品的一致性，不等于证明模板 capability。因此它目前只支持“框架能参与治理自身构建”的存在性观察，
只覆盖第 4 域 hazard 子集。

v5 选择推荐修复路径：把 `lab/research/claims.yaml` 从占位变成 **模板能力台账**。每条 capability claim 必须经过：

`capability hypothesis -> versioned eval/probe specification -> run/fixture + commit/config -> evidence.yaml entry ->
claim promotion -> fresh reviewer -> deliverable reference`

首批候选 claim 应覆盖 hook/validator 缺陷检测、anatomy drift、context recovery、adapter 非等价检测与 shape-change
invariant preservation。stress-test ledger 可作 evidence source，但不得直接把“case complete”提升为 capability supported；
每条 claim 仍需可证伪假设、scope、负例、metric source 与 fresh review。完成这条链后 self-hosting 仍是 self case，
但不再是“自家 claim 台账为空却宣称活证据”的退化叙述。

---

## 7. Related work 与 compose-not-compete 假设

通用 coding-agent control plane、repository-level governance、release/eval governance 与本文分析不同层次的对象。
它们可能组合，但 **compose-not-compete 目前只是组合假设 H2，不是既有结论**：对方 canonical 格式能否表达
evidence lattice、O2/O4 引用、budget ledger、policy composition 和 continuity schema，尚未经检验。

Phase 1 必须做最小组合 spike：

1. 选一个最小 lab profile 和两条核心 invariant；
2. 尝试编译进对方公开 target/extension surface；
3. 注入无法表达、语义降级和 target divergence；
4. 报告 expressible / extension-required / inexpressible，而非只报语法生成成功。

因此“Control Plane 等价配置 + lab profile”只是 **待验证的目标 baseline**。若 spike 失败，baseline 改为可实现的
通用 control-plane 配置，并把不可组合语义作为结果；不得用 compose 修辞掩盖表达力缺口。

---

## 8. Evaluation：主实验、共同 protocol 与证据门槛

### 8.1 当前事实与 effectiveness 前置条件

- ML、量化、计算科学、第 4 域：均为 **0 个非 self 实例**。
- 全部现有材料只构成 **1 个 self-hosting case**；公开仓库 stress/adoption replay 是模板机制压测，不自动等于
  四域方法实例化，更不等于独立 effectiveness evidence。
- 第 4 域必须有非 self case 才计入“有实例”。
- 任何 effectiveness 表述都要求：至少一个外部团队仅凭论文/artifact 完成 blind instantiation；实例化过程、
  失败、修改请求与复核结果留痕；violation 用例至少部分由非作者提出。

### 8.2 主实验：保证是否以固定 shape 为代价

对相同任务、hazard 与资源预算，比较：

1. prompt/`AGENTS.md` only；
2. 可实现的通用 control plane；
3. **固定 phase profile**；
4. **shape-agnostic profile + shape-change invariant checker**；
5. 完整框架的 O2/O4/A1 等 ablation。

在 branch、回退、循环、临时重规划与产出类型变化下测量 invariant preservation、violation recall、unknown 暴露率、
合法探索误阻率、额外 gate、任务延迟、重规划成功率、恢复时间、human intervention 与维护时间。H1 只有在第 4 组
相对第 3 组保持相当 assurance 且减少 shape 代价时才获支持；若 prompt-only 更灵活但无 assurance，也不能被写成
本文“赢得 shape-agnostic”。

### 8.3 每域共同 protocol

1. risk-to-control instantiation 与准入 checklist；
2. provider A/B，目标是检测非等价与降级；
3. 非作者参与的 injected violation；
4. context loss/recovery，O4 只凭 O2 引用恢复；
5. policy conflict、budget overrun 与 control-unload test；
6. governance change/drift 与 A2 反身迁移；
7. claim promotion；
8. shape-change checker + 固定 phase 主对照；
9. 边界外阴性对照。

共同指标另含 claim provenance completeness、错误 promotion 阻断率、成本归因完整率、主体归因覆盖率、policy 冲突
检测率、实例化/维护时间与 task success。四域数据用于 feasibility 和 analytical replication；外部 blind case 完成后，
才讨论更强的经验主张。

---

## 9. Threats to Validity、TCB 与表述边界

本节集中承载 v3 分散在非目标、威胁模型、开放免责声明与防 overclaim 中的限制；正文不重复设防。

### 9.1 Construct validity

Shape/invariant 的划分可能把真实顺序约束重新包装成状态谓词；promotion/human gate 已作为显式例外，主实验还需测
gate 代价。Lab-class checklist 也可能放行 high-stakes SE 或排除有价值的开放工作，故设置阴性对照并预注册判据。

### 9.2 Internal validity

规则、adapter、case 与判定目前同源，self-hosting 近似构造性通过；两个 provider surface 也由同一 canonical source
机械生成。fresh reviewer、非作者 violation 与 blind instantiation 只能缓解，不能完全消除作者效应。

### 9.3 External validity

当前 0 个非 self 域实例 + 1 个退化 self case，不支持 effectiveness、necessity、sufficiency 或 generality。
量化、计算科学和 research-grade agent/harness 均只是预注册目标。第 4 域不外推到成熟产品发布与生产运行。

### 9.4 TCB、bypass 与递归信任

最小 TCB 包括 checkout/history、policy 加载机制、validator/runtime、adapter、外部 CI/服务和授权人。Repo hook 是
防误操作护栏，不是对抗性 sandbox；未加载、配置错误、显式 bypass 或直接调用外部系统可能越过观测面。资金、
HPC、生产数据和部署仍由 broker/IAM/scheduler/deployment control plane 承担强边界。A2 是治理对自身的反身应用，
不能独立证明自身；外部签名、hash-chain、CI 或更小 verifier 用于缩小而非消灭 TCB。

### 9.5 文献与措辞风险

外部工作的精确机制、数字和版本必须回到原文核验。标题与正文统一使用 **high-stakes**，避免暗示监管分类。
Provider 只主张非等价可检测性。框架不声称对工作零影响，而以 §8 指标量化其代价。摘要在 blind external
instantiation 前不得使用 effectiveness 词族。

---

## 10. 可发表贡献包

1. **对象层**：经身份/授权、预算、policy 组合语义与 O2/O4 切分加固的 5-object + 2-process 模型。
2. **机制层**：形式化 shape/invariant、两个诚实例外与 shape-change invariant checker。
3. **程序层**：含准入、谓词、placement、migration 和 conformance 的五步实例化方法。
4. **Artifact 层**：reference schema、checker fixtures、capability claims ledger、adapter contract 与 conformance suite。
5. **经验层（待实验）**：固定 phase vs shape-agnostic 主实验、目标 control-plane 组合 spike、外部 blind 实例化、
   非 self 第 4 域 case 与边界外阴性对照。

论文身份是 artifact-centered method/system paper about governing lab-class workspaces，不是 workflow 产品、通用 agent
发布治理或“目录很多”的 template paper。

---

## 11. 标题候选

### 首选

**Assurance Without a Fixed Workflow: Governing Evidence, Continuity, and Boundaries in High-Stakes Agentic Labs**

中文：**不固定工作流程的保证：高利害 Agentic Lab 中的证据、连续性与边界治理**

标题把联合命题放在第一位，不把 shape-agnostic 当作单独贡献。

### 备选

- **Governing the Lab Without Fixing the Work: Evidence and Boundary Assurance for Long-Horizon Agentic Workspaces**
- **The Workspace as a Governance Surface: Evidence, Continuity, and Boundaries for Agentic Labs**
- **Design the Harness, Not the Workflow: Verifiable Governance for High-Stakes Research Workspaces**

---

## 12. Venue 与节奏

1. **先发 self-hosting experience report**：只报告纵向存在性、真实缺陷、维护代价与负面结果，并完成模板
   capability claim -> eval evidence 台账；不包装成跨域效果证明。
2. **再投 framework workshop / CAIN 或 assurance workshop**：交付形式定义、checker、五步程序、组合 spike、
   主实验 pilot 与诚实的 0 non-self 状态。
3. **最后考虑正会**：至少两个真正异质域、外部 blind instantiation、非 self 第 4 域 case、共同 protocol、目标
   baseline、阴性对照和 replication package 齐备后再升级。

Stop/go：只有 self case 则走 experience report；有方法 artifact 但无 blind external case 则停在 framework/feasibility；
blind external、主实验、非 self case 与跨域数据未齐，不进入 effectiveness 或普遍方法主张。

---

## 13. 仍需实验解决的开放张力

1. **灵活性 vs assurance**：checker 能否在减少固定 phase 代价时保持违规检测与恢复能力？
2. **Core vs domain profile**：身份、预算、证据与 continuity 的复用是否足以抵消每域专用 validator 的成本？
3. **范围边界**：三项必要条件与阴性对照能否稳定区分 research-grade lab 与成熟常规软件发布？
4. **Self-hosting 非退化性**：能力台账能修复 claim 链，但何种非 self case 才真正覆盖 release-artifact 权限泄漏？
5. **组合表达力**：通用 control plane 能否承载 evidence lattice、continuity 与 budget 语义，还是必须扩展 canonical？
6. **身份/授权可观测性**：在 provider/hook 无可靠 actor identity 时，归因能做到多强而不制造伪精确？
7. **递归信任**：A2、外部 CI、签名与小 verifier 如何分工，才能以可接受成本缩小 TCB？
8. **证据门槛**：blind instantiation、两个异质域与非 self 第 4 域 case 分别支持多强的经验措辞？

这些张力是预注册实验问题，不靠扩大标题或重复免责声明解决。

---

## 14. v5 的最小审稿人读法

> 对同时具有证据受约束 claim、昂贵/不可逆动作与跨 session 状态的 workspace，能否用 5 对象 + 2 过程和五步
> 方法，把 hazard 编译为可执行、可恢复的治理状态；相对 prompt-only、通用 control plane 与固定 phase profile，
> shape-change checker 能否在不固定领域拓扑时保持 evidence/continuity/boundary invariant，其误阻、预算、维护和
> 恢复代价是什么？

若论文不能用组合 spike、主实验、阴性对照、外部 blind instantiation、非 self 第 4 域 case 与诚实 TCB 回答，
它就停留在 framework / experience / feasibility 体裁，不升级为已验证的 effectiveness 结论。
