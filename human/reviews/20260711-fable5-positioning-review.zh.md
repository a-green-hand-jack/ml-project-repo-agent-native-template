# 对论文定位 v3 的独立批判性审核（fable5）

> **审核对象（历史固定 revision）**：[论文定位 v3](https://github.com/a-green-hand-jack/ml-project-repo-agent-native-template/blob/415f865b2b3222727532d173b729a5d581e98655/plans/20260711-paper-positioning-v3.zh.md)
> **当前状态**：v3 已从当前 tree 删除并由 `plans/20260711-paper-positioning-v5.zh.md` supersede；本文件只保留为审稿过程证据。
> **审核人立场**：独立资深审稿人（agent 系统 / 软件工程 / 研究方法）。本审核先给独立判断，末节说明与
> `human/reviews/20260711-codex-positioning-review.zh.md`（针对 v1 的上一轮审核）的增量与分歧。
> **已核对制品**：`DESIGN.md`、`AGENTS.md`、`.agent/principles.md`、`.reference-docs/claude_code_optimization_spirit_zh.md`
> （§3.3、§5、§6）、`lab/research/claims.yaml`（仍为占位）、`ANATOMY.md`，以及 v2 定位文档全文。

---

## 总评

v3 在方法卫生上是这三版里最干净的：竞品误述已撤回、主张强度分层明确、防 overclaim 记录（§14）与开放张力
（§13）诚实到罕见的程度。5+2 模型、五步程序、四维设计空间、共同 protocol 都已具备"可以开始写论文"的骨架。

但我的核心判断是：**v3 的 pivot 是一次纯 framing 层的改写，没有产生新机制。** 对照 v2 §4.1 与 v3 §4.1，
五类对象的定义几乎逐字相同（"阶段"→"工作情境"、"hypothesis、run"→"intent/hypothesis、execution"），
两个 assurance process 完全一致。v3 真正新增的可检验内容只有两处：shape-change test（§8.2.7）与灵活性
测量（§8.4 的"被误判合法探索比例"等指标）。这意味着论文若以"从治理 workflow 转向治理 workspace"为
第一贡献，审稿人会问：这个转向改变了哪个 schema、哪条 invariant、哪个 validator？目前答案是：一个也没有。

同时，v3 为修补 v2 的问题引入了两个新的结构性风险：(a) "shape-agnostic" 在当前表述下**按构造不可证伪**；
(b) 第 4 域的准入判据**同样放行高风险软件工程**，刚在 §2.5 关掉的"面向所有 agentic 工作"的门被从侧面
重新打开。此外四域证据结构存在"以分类法扩充证据"的嫌疑：新增第 4 域后，"有实例的域"从 1 变 2，但没有
增加任何一份非作者产生的证据。

结论先行：**framework/design 体裁的 workshop 版本可行且值得写；正会版本在拿到外部实例化与非 self 的
第 4 域 case 之前不应启动。** 另有一条与上一轮审核不同的路线建议，见第 6 节。

---

## 1. 身份是否立住："治理框架、shape-agnostic、产出可到 agent"

### 1.1 workspace / workflow 的分界没有可判定标准（最大空洞）

v3 全篇依赖"治理工作所在的空间，不规定工作的形状"这组对偶，但从未给出**判定一个约束属于哪边**的标准。
考察框架自己的机制：

- O2 的 promotion gate 规定"evidence 必须先于 claim 升级"——这是一条**顺序约束**；
- O1 的 human gate 规定"不可逆动作前必须有人类批准"——这是工作序列中的一个**强制步骤**；
- same-commit rule 规定"结构改动与 anatomy 更新必须同 commit"——这是对提交**形状**的约束。

这些都可以被辩护为"约束的是治理对象的状态迁移，不是领域活动的顺序"——claim 的状态机不等于研究者的
日程。这个辩护是成立的，而且是唯一成立的辩护。但 v3 没有把它作为形式判据写出来（§4.3 只有一句
"不要求活动依次经过 O1→O5"）。后果是：**任何**被指为"强加形状"的机制都可以事后重新归类为"治理
invariant 而非工作形状"，shape-agnostic 就成了按定义不可证伪的主张。§8.4 的灵活性指标测量的是"治理
是否误伤探索"，这是代价测量，救不了定义层的循环。

**加固**：给"shape"下形式定义——例如 shape = 对领域活动集合上的偏序/迁移图施加的约束；invariant =
对治理对象状态的谓词。然后逐条证明（或承认例外）：五类对象的 invariant 均可表达为状态谓词，唯二例外
是 promotion gate 与 human gate，它们约束的是 claim/action 的状态迁移而非活动排序。有了这个判据，
shape-agnostic 才从口号变成可检查性质。

### 1.2 shape-agnostic 单独不构成贡献

prompt-only / `AGENTS.md`-only 基线天然 shape-agnostic（它什么都不强制）；Control Plane 的作者也可以
主张 phase state machine 是可选 profile。所以卖点不能是"我们 shape-agnostic"，只能是
**"在不强加工作形状的前提下仍保持 lab-class 的 evidence / continuity / boundary assurance"**——即
灵活性与保证的联合成立。v3 的正文（§13.2）明白这一点，但 §0 一句话定位与首选标题仍把 shape-agnostic
放在第一顺位宣传，容易被审稿人当作平凡性质打掉。建议一句话定位改为强调"assurance 不以固定拓扑为
前提条件"这个联合命题。

### 1.3 "lab-class workspace" 是家族相似清单，没有成员判据

§2.1 列了 7 个特征，用"结构性特征组合"回避了 v2 的"满足多数条件"——实际上更模糊了。§2.5 排除 CRUD
是宣告式的，不是从定义推出的。审稿人会构造边界反例（见第 2 节）。**加固**：指明哪几个特征是单独必要的
（我判断是：证据受约束的 claim + 昂贵/不可逆动作 + 跨 session 状态这三条），其余为加重因子；给出一个
可操作的准入 checklist，并在 evaluation 里对一个"边界外"项目做阴性对照（框架实例化收益应显著低）。

### 1.4 "产出可到 agent"本身不矛盾，但引入了第 2 节的所有问题

命题 3（产出开放性）与 O5 双层区分在概念上自洽。问题不在逻辑，在范围与文献（见下节）。

---

## 2. 第 4 域是否真的一等

### 2.1 准入判据放行了整个高风险软件工程（范围重新失控的具体机制）

§6.4 论证 agent/工具开发是 lab-class 的理由：capability claim 受 eval 约束、trace/eval 昂贵、部署边界
不可逆、跨 session 多 agent。逐条检查：一个有昂贵生产部署、SLO 承诺（=受证据约束的 claim）、多团队
长周期的普通 SRE 密集型服务**同样全部满足**。也就是说，第 4 域的准入判据无法把"造 agent"与"高风险
软件工程"区分开。这有两个后果：

- 刚在 §2.5 声明的"不治理所有软件项目"被侧面击穿——不是通过扩大口号，而是通过判据泄漏；
- 论文一旦被读作覆盖高风险 SE，related work 就必须面对 release engineering、change management、
  deployment gates、合规审计这些有几十年积累的领域，§7 只对比两篇近期工作完全不够。

**加固**（二选一，必须显式选）：(i) 承认 lab-class 是结构性质，某些高风险 SE 项目确实在范围内——
诚实但要补 SE 治理文献并调整 venue 叙事；(ii) 把第 4 域收窄为"research-grade agent/harness 开发"
（行为目标随 trace/eval 演化、capability claim 尚无稳定 spec），显式排除成熟产品的常规发布——保住
边界但牺牲"产出可到 production agent"的部分说法。当前文本在两者之间漂移。

### 2.2 缺失的文献轴：agent 发布治理与 eval-gating

第 4 域一旦一等，"capability claim 受 eval evidence 约束 + release gate"就直接撞上 agent 评测与发布
治理的现有实践（eval-gated deployment、model/agent card、MLOps registry、各家 preparedness 式发布
政策、NIST AI RMF 一类框架）。§7 对此零覆盖。审稿人只需一句"你们的 O2+release gate 与 eval-gated
deployment 有何差异"就能造成实质伤害。**加固**：为第 4 域单独写一段 related work，把差异压到
"development workspace 的治理"（构建过程的边界/连续性/证据）而非"发布决策本身"。

### 2.3 self-hosting：证据膨胀嫌疑 + 恰好演练了退化情形

两点独立于"不是独立样本"这个已承认的问题：

- **以分类法扩充证据**。新增第 4 域后，"有实例的域"从 1/3 变为 2/4，而唯一新增实例是作者自己的
  模板治理自己。规则由作者写、conformance 由作者跑、通过是准同义反复（规则本来就是在这个 repo 上
  调到通过的）。§8.1 的诚实声明不能消除这个结构性激励。**加固**：承诺第 4 域的 evaluation 必须包含
  至少一个非 self 的 agent/工具项目 case，否则该域在摘要中不计入"有实例"。
- **退化情形**。第 4 域特有的 hazard 是"外层开发权限泄漏到 release artifact"与"capability claim 未经
  eval 就 promotion"（§8.3 自己列的 stressor）。但 self-hosting 的"内层产物"是模板/harness 本身——
  它从未跨越真实的 release/deployment 边界，也没有一个把模板当作 agent 产品的 eval harness（validator
  验证的是治理一致性，不是产品能力 claim）。所以 self-hosting 恰好**没有**演练第 4 域最有代表性的
  两个 hazard，它对第 4 域的支撑比 v3 暗示的更弱。**加固**：要么给模板本身建立 capability
  claim→eval evidence 链（把 `claims.yaml` 从占位变成模板自己的能力台账——这同时解决"claims.yaml
  为空"的尴尬，一石二鸟且完全在作者可控范围内），要么明说 self-hosting 只覆盖第 4 域 hazard 子集。

---

## 3. 5 对象 + 2 过程：正交性、冗余、缺失

### 3.1 O2 / O4 在 intent 上有残留重叠

v3 把 "intent/hypothesis" 加进了 O2 的方法定义，而 O4 同时保存"目标、决策、**证据状态**、未决风险"；
§6 表格第一行又说"O4 保存意图"。hypothesis 到底住在哪？"证据状态"同时出现在 O2 本体与 O4 的快照里。
**加固**：明确切分——O2 = 认知状态（相信什么、凭什么、强度几何），O4 = 操作状态（正在做什么、下一步、
指向 O2 的引用而非副本）；O4 对证据只持引用，禁止复制内容，否则两处口径漂移就是新的 drift 源。

### 3.2 仍然缺失的候选对象

- **身份与归因（最重要）**。上一轮审核已点名"身份/主体与授权模型"，v3 只在 O1 定义里留了"主体"二字，
  没有任何 materialization：没有 agent 注册表、没有"这个 claim / 这次 promotion / 这个 commit 是哪个
  agent 以何种授权做的"的归因规则。本 repo 自身也没有该机制（hook 无法区分调用者是谁）。多 agent
  workspace 的问责链条以此为底座；它应当成为 O1 最小输出的强制组成（subject registry + attribution
  rule），或诚实列入 §13 开放张力。**v3 吸收了上一轮几乎所有意见，唯独这条没有落地，需要解释原因。**
- **资源/预算台账**。lab-class 的定义性特征是"执行昂贵"，但没有任何对象物化消耗状态：烧了多少算力、
  剩余预算、成本归因到哪个 hypothesis。O1 管动作准入，无人管累计消耗；对量化与 HPC 域，预算本身就是
  治理对象。可作为 O2 的 domain validity 字段或 O1 的扩展，但目前完全没提。
- **Policy 组合语义的失败语义**。Step 3 产出 composition graph 与优先级，是程序性的；O1 的 invariant
  列没有"两条 policy 静默冲突"这一失败类。多层 policy（user 全局 / repo / worktree / 远端）并存时，
  组合结果应当是可物化、可检查的状态，而不只是设计期产物。

### 3.3 A2 的地位

A2（受管演化）本质上是"框架对治理层自身的反身应用"——治理对象的变更也要有 provenance、review、
recovery，这就是 O1-O5 语义作用于 `.agent/`/`.claude/`/schema 自身。当前把它列为独立过程可以接受，
但论文若指出这层反身性（governance of governance = 同一框架的递归实例），既更优雅，也顺手回答了
§13.6 的递归信任张力的一半。

---

## 4. 残留 overclaim / 事实风险

1. **"ML 有实现与 replay 种子"（§0 状态声明、§8.1）**。我在 repo 中能核实的是：治理机制齐备、
   `claims.yaml` 为占位、无真实 run/experiment 证据链实例。"replay 种子"具体指什么没有 artifact 锚点。
   若它实际上就是"模板机制本身"，那么诚实的表述是：**四个域全部为 0 个非 self 实例，仅有一个
   self-hosting case**。这句话必须在论文里能被作者自己接受，否则 §8.1 第一行就是残留 overclaim。
2. **compose-not-compete 是未经检验的可行性假设**。§7.2 断言"前者可作为后者的执行与完整性底座"、
   §8.4 把"Control Plane 等价配置 + lab profile"设为最强 baseline——但没有任何组合实验证明对方的
   canonical 格式能表达 lab 语义（evidence lattice、continuity schema 能否编译进其七个 target？）。
   若不能，compose 叙事塌为 related-work 修辞。应降格为"组合假设，Phase 1 需做最小组合 spike 验证"。
3. **对 arXiv:2606.26924 的具体描述是二手的**（来自上一轮审核对摘要的转述）。§14 已写"须回到原文
   逐项核验"，好；但 10,008 仓库、七 target、HMAC lockfile 等数字在写作阶段前不应再向外扩散。
4. **provider 等价性证据先天偏软**。仅 Claude Code + Codex 两个 surface，adapter 由同一作者从同一
   canonical 机械生成——"行为等价"在很大程度上是构造出来的，不是被检验出来的。§2.4 把"跨 provider
   行为等价性"列为期望收益时，应改为"非等价的可检测性"，并承认 n=2 且同源。
5. **"高风险"（High-Risk）标题用词**。在 2026 年语境下会与监管分类（如 EU AI Act 的 high-risk）产生
   不必要的联想，引来错误的审稿人期待。考虑 "high-stakes" 或副标题限定。
6. **小项**：§6.4 "不臆造任何私有项目细节"——在论文里这句话没有指称对象，反而泄漏"存在一个私有
   项目"的背景；删除。§2.4 "不显著压缩有效探索空间"中的"显著"暗示统计检验，而设计里没有对应的
   检验计划；措辞降为"以 §8.4 指标量化其代价"。

---

## 5. 狠心审稿人最强的 2-3 条拒稿理由与加固

### R1：pivot 无机制增量，核心概念不可证伪

> "v3 相对 v2 只是把 'pipeline' 改写为 'workspace'：五类对象与两个过程逐字未变，没有任何 schema、
> invariant 或 validator 因 pivot 而改变。核心卖点 shape-agnostic 要么平凡（prompt-only 也不规定形状），
> 要么不可证伪（任何被指强加形状的机制都被重新归类为 invariant）。这是 framing 论文，不是方法论文。"

**加固**：(a) 形式化 shape 与 invariant 的区分（§1.1 的判据），使 shape-agnostic 成为可检查性质并主动
承认 promotion/human gate 两个例外；(b) 把"固定 phase profile vs shape-agnostic profile"的对照实验
（§8.4 已列）升为论文主实验，用数据而非定义回答"灵活性是否以保证为代价"；(c) 在方法层做出至少一处
由 pivot 驱动的真实变更（例如 shape-change 下的 invariant 保持检查器），让 pivot 有机制足迹。

### R2：证据基座是同一个自建 repo 的多重计数

> "四个域中三个为 0 外部实例，第四个是作者的模板治理自己；规则、adapter、conformance test、通过判定
> 全部出自同一批作者。新增第 4 域使'有实例的域'翻倍，却没有增加一份非作者证据。这不是 evaluation，
> 是 taxonomy。"

**加固**：外部 blind instantiation 从"至少加入一个"升级为任何 effectiveness 表述的**前置条件**；第 4 域
必须有非 self case 才计入；violation injection 的用例改由非作者出题；把模板自身的 capability claim 录入
`claims.yaml` 并走完整证据链，至少消除"自家台账为空"的直接矛盾。

### R3：第 4 域溶解了范围边界，且撞上未处理的成熟文献

> "准入判据同样放行高风险软件工程；'产出可到 production/trading agent' 使论文事实上宣称与 agent 发布
> 治理相关，而 related work 对 release engineering、eval-gated deployment、MLOps registry 零覆盖。作者
> 在 §2.5 关上的门被自己的第 4 域重新打开。"

**加固**：按 §2.1 的选择显式收窄或显式扩大（不能漂移）；为第 4 域补 agent 发布治理文献轴，把本文差异
钉在"development workspace 治理"而非"发布决策"；给 lab-class 准入一个可操作判定程序并做一个阴性对照。

---

## 6. 体裁与 venue

1. **framework paper 与 system paper 之间的第三条路**。v3 规划"workshop framework 稿 → 正会完整稿"，
   方向可行，但有一个被忽略的选项：**先写 self-hosting 的纵向经验报告**（experience report / SEIP-FSE
   industry 类轨道）。理由：这是作者手里唯一真实的纵向数据——数月的 PR、hook 修复、stress test、
   治理演化轨迹都在 git 历史里，维护成本、违规拦截、误伤率可以直接从历史测量，不需要任何新域实例化。
   经验报告体裁对"n=1、作者即用户"完全宽容，而这恰是 framework 稿的最大软肋。发表顺序改为：
   经验报告（数据实、姿态诚）→ framework workshop 稿（概念）→ 正会稿（外部实例化后）。
2. **framework 稿的最大文体风险是过度设防**。v3 有 §2.5、§9、§13、§14 四层免责结构；positioning 文档
   如此可以，论文如此会显得作者自己不信任贡献。审稿人奖励"一个尖锐主张 + 硬证据"，不奖励"十个
   被围栏保护的主张"。写作时把防御集中到一节 threats-to-validity，正文只留一条主线。
3. **venue 判断**：CAIN 仍最自然（agentic software + assurance + 接受 design contribution）；第 4 域
   使 agent-safety / assurance 类 workshop 成为额外选项。FSE/ICSE 主轨在拿到两个真异质域 + 外部实例化
   之前不要碰——这与上一轮审核一致，不再展开。stop/go 判据（§12）本身写得好，建议原样保留并加一条：
   **R2 的前置条件（外部实例化）未满足时，任何版本的摘要不得出现 effectiveness 词族**。

---

## 新增 / 不同于 codex 上一轮审核的点

codex 审核针对 v1，其主要火力（竞品误述、七原语非方法、三域证据不足、5+2 重构建议）已被 v2/v3 吸收；
我确认这些修复基本到位，不再复述。本审核的增量：

1. **pivot 无机制增量的证据**：逐字对比 v2/v3 的 §4.1，指出五类对象定义几乎未变——"workspace 转向"
   目前只存在于叙事层（codex 未见过 v3，无从指出）。
2. **shape-agnostic 的不可证伪性**：指出 promotion gate / human gate / same-commit rule 本身就是顺序
   约束，"治理状态迁移 vs 领域活动排序"的区分是唯一出路且必须形式化——这是 v3 新引入概念的新问题。
3. **第 4 域判据泄漏**：准入条件同样放行高风险 SE，范围边界被侧面击穿；以及由此缺失的整条 related-work
   轴（agent 发布治理 / eval-gating / MLOps registry）。
4. **证据膨胀机制**：新增第 4 域使"有实例的域"翻倍而零新增外部证据——比"self-hosting 非独立样本"
   （codex 已指出）更进一步的结构性批评。
5. **self-hosting 演练的是退化情形**：内层产物本身是 harness、从未跨越真实 release 边界，恰好覆盖不了
   第 4 域特有的两个 hazard；并给出可立即执行的补救（把模板能力录入 claims.yaml 走证据链）。
6. **compose-not-compete 是未检验假设**：需要最小组合 spike，否则最强 baseline 无法成立。
7. **对象层新缺口**：O2/O4 在 intent/证据状态上的残留重叠；资源/预算台账缺失；并指出 codex 点名的
   身份/授权是 v3 唯一未吸收的上轮意见。
8. **路线分歧**：codex 建议 workshop position 稿先行；我建议把 self-hosting 纵向经验报告提到最前——
   它是唯一现在就有真数据支撑的论文，且体裁对 n=1 宽容。

---

## 一句话结论

**v3 的诚实度与方法骨架已达 workshop 水准，但"workspace pivot"目前只是换了叙事没换机制：
先把 shape-agnostic 形式化到可证伪、把第 4 域的边界钉死、拿到第一份非作者证据（或先发 self-hosting
经验报告），再谈 framework 论文的正会版本。**
