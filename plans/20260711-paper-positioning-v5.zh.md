# 论文定位 v5（重写稿）：一个可跨领域复用的 Repo-Native Agent Harness

> 这份文档只做一件事：用简单的话写清楚这个 template 是什么、为什么可能有用、以后怎么验证。
> 它不是论文正文，也不提前发明一套复杂理论。请直接在文件里批注、删改或写反例，我们再继续收敛。
> 它写的是 harness 的目标形态和开发方向，不是当前版本的 release note。已经支持的能力会明确写出；还没支持但
> 值得做的能力会进入 issue，由后续 agent 实现、验证并进入新版本。

---

## 0. 一句话

我做了一个以 Git repo 为载体的 **agent harness**。整个 repo 共同承担这个 harness：它为复杂项目提供
长期记忆、任务拆解、agent 调度、多 agent 协作、安全边界、过程记录、结果管理、验证和持续改进机制，
让 human 与不同 coding agent 能在同一个项目里持续工作。

`lab/` 是领域工作的主要工作区，但不是 harness 之外的一块“任务插件”，也不是所有内容都会直接交付给别人。
项目的入口、规则、能力、状态、人机协作、领域工作、最终交付和验证机制分布在 repo 的不同部分，合在一起
治理并支持整个开发过程。

同一套 repo 架构可以用于机器学习、深度学习、量化研究、AI for Science、AI Agent 开发，以及其他复杂、
需要持续推进并最终产出结果的项目。

---

## 1. 我到底做了什么

这个 template 不是某个具体算法，也不只是提前建好一批目录。它把一个复杂项目从开始到交付、再到后续升级的
工作环境放进 repo：

> 创建或迁移项目 → agent 定位项目 → human 与 agent 收敛目标和计划 → 拆任务并选择 agent/模型 →
> 在隔离 worktree 中实现或登记实验 → 监控并跨 session 恢复 → 整理产物、证据和交付 →
> 把真实使用中发现的问题反馈给 template，并把新版同步回来。

不同领域会替换代码、数据、实验和最终结果，但这条项目生命周期以及支撑它的记忆、协作、安全、验证和演化机制
可以继续复用。

这里的核心想法很简单：

> chat 只负责当前这一小段思考，整个 repo 才是 human 与多个 agent 共同使用的长期工作空间和开发 harness。

---

## 2. 整个 repo 怎么构成 harness

这个 harness 不是一个单独目录，而是下面这些部分的组合：

| Repo 部分 | 在开发过程中做什么 |
| --- | --- |
| 根入口与 `ANATOMY.md` 系统 | 说明项目是什么、agent 从哪里开始读，并把 agent 路由到当前任务真正相关的目录和 ownership |
| `.agent/` | 保存工作原则、动作边界、上下文策略、协作和验证规则 |
| `.claude/`、`.codex/`、`.agents/` | 提供 subagents、skills、commands、hooks、权限，以及 Claude Code 与 Codex 的适配 |
| `human/`、`plans/` | 保存 human 的目标、批注、决策和需要共同收敛的计划 |
| `memory/` | 保存当前状态、session/branch/worktree 树、handoff、变更记录和正在采用的工作方法 |
| `lab/` | 承载领域代码、数据索引、实验、运行记录、证据和中间产物 |
| `deliverables/` | 保存从 `lab/` 工作中选出并准备对外交付的论文、模型、算法、报告或 release |
| `scripts/`、`.githooks/`、CI | 检查 harness、项目结构、证据链和规则有没有失效或漂移 |

为了同时写清目标和现状，下面区分三种状态：

- **已经支持**：当前版本已有可执行代码，或已有 agent/human 可以实际采用的完整流程；
- **待开发或增强**：属于目标 harness 的能力，但当前支持还不够；后续登记 issue，派 agent 实现并验证；
- **由下游填充**：领域代码、数据、实验和交付本来就不应该由空 template 预先提供，不属于 template 缺陷。

### 它怎样陪一个项目走完整个周期

| 项目阶段 | Template 提供什么 | 当前支持与后续开发 |
| --- | --- | --- |
| 新建或迁移项目 | 新项目可以直接从 GitHub template 创建；已有 repo 可以依次 discover、记录 baseline、铺设控制面、保守归位原代码，再检查原 tracked bytes、测试和治理状态 | **已经支持**创建清单和保守迁移脚本，并在 Agent-R1 上 replay；更自动的新项目 bootstrap、更细的语义归类和 runtime 验证可以按真实 case 继续增强 |
| 进入项目、快速定位 | 固定入口告诉 agent 先读什么；逐层 `ANATOMY.md` 说明东西在哪里、谁负责、如何连接；`memory/current-status.md` 说明现在做到哪里 | **已经支持**入口、地图、活状态和相关检查；`lab/ANATOMY.md` 会随着下游真实代码进入而由项目继续填充，这符合 template 的设计 |
| Human 给目标并共同定计划 | `human/` 保存 brief、review 和 decision；中文 plan doc 允许 human 直接批注，agent 根据 diff 收敛 scope、禁止路径和验收标准 | **已经支持**这套人机协作流程；自动需求解析或审批状态机不是前提，只有真实使用证明有价值时再提 issue 增强 |
| 拆任务并选择 agent、模型和预算 | task packet 与 launch packet 写清 ownership、禁止路径、工具、停止条件；路由会参考角色、风险等级、Codex/Claude 当前额度和近期消耗 | **已经支持**任务 packet、quota 读取和路由建议；基于真实成功率、速度和准确价格的自动调度属于明确的后续增强方向 |
| 隔离实现或开展实验 | 代码改动走 issue、短分支、fresh worktree、定向测试和 review；实验走 experiment card、ledger、human 启动、只读监控、run summary 和产物登记 | **已经支持**代码工作流、安全护栏和实验流程；具体代码、配置、run 与 ledger 条目**由下游填充**，scheduler 等能力按 case 需要继续开发 |
| 长任务监控与跨 session 恢复 | monitor 只读查看有界日志、metric、checkpoint 和进程；current status、session tree、branch status 与 handoff 保存长期状态；context hook 在阈值提醒并在 compact/clear 后回注状态 | **已经支持**状态文件、只读监控和 context hook；后台告警、自动恢复和实时状态服务可以作为后续 issue，不是这一目标形态的固定上限 |
| 管理数据、产物、实验和结论 | 分开索引 dataset、checkpoint、result、table、figure、trace、experiment、evidence 和 claim；大 bytes 不进 Git；结果达到门槛后才升级为 evidence | **已经支持**schema、索引流程和部分 claim/evidence 检查；真实条目**由下游填充**；artifact 存在性、checksum 和实验闭环检查可以继续增强 |
| Review、验证和交付 | 定向测试、fresh review、governance validator、same-commit hook 和 CI 检查结构与部分证据关系；`deliverables/` 管理 paper、slides 和 release，外部动作走 human gate | **已经支持**validator、CI、review 和交付边界；真正的论文、模型或 release **由下游填充**；自动打包、投稿、发布或正文 claim 检查可按需要开发 |
| 从真实使用升级 template | 压力测试记录机制缺口；trace 可以沉淀为可复测 recipe；下游可以带版本和复现上报 issue；上游按 semver 发版后，下游 sync 新版并保护自己的项目内容 | **已经支持**压力测试、反馈、版本和同步机制；更多真实下游会继续暴露缺口，并驱动新 issue、新 agent 任务和新版本 |

所以，表里的“待开发或增强”不是不可克服的限制，而是 template 的 roadmap。所谓 template 自我升级，就是把
真实使用中发现的缺口变成 issue，再由独立 agent 在分支/worktree 中实现，经测试、review 和压力测试后进入新版，
最后同步回需要它的下游项目。

当前版本已经包含一组可直接调用和检查的 repo-local subagents、skills、commands、hooks、validators，以及从
`.claude/` canonical 定义生成的 Codex adapters。Claude Code 与 Codex 因此共享同一来源，但这不代表两个 runtime
的工具限制和运行语义完全相同；adapter 的作用是让差异可发现、可检查，而不是假装完全等价。

安全边界也要说准确：受保护数据和产物、危险删除、推送 `main` 等可以被 permission 或 hook 硬拦；依赖变更、
长实验启动、PR、merge、claim 升级和 release 等仍主要依赖 human gate 与 review。hook 是防误操作护栏，不是
对抗性 sandbox，也不能自动识别所有可能昂贵的领域命令。

### Lab 和最终结果不是一回事

`lab/` 是做事的地方。当前 template 里它具体分成下面几类内容：

| `lab/` 内容 | 保存什么 |
| --- | --- |
| `code/` | `src`、配置、脚本、测试和实验入口 |
| `infra/` | 权限理由、路径、存储、可复现启动命令、环境探针和不进 Git 的私密配置 |
| `data/` | 数据集索引、manifest、checksum、task set 和 schema；大数据 bytes 不进 Git |
| `runs/`、`models/` | 运行结果和 checkpoint 的存放约定；Git 主要保留索引与 summary，不保存大 bytes |
| `artifacts/` | result、model、trace、table、figure 的位置、来源、状态等元数据索引 |
| `research/` | hypothesis/claim、evidence、experiment ledger、regression matrix 和 release gate |
| `traces/`、`recipes/`、`evals/`、`reports/`、`docs/` | 人机轨迹、可复用工作方法、评测、分析报告和研究文档 |

这些内容既包含过程材料，也包含中间结果和最终结果的依据。真正交付给别人的通常只是其中一部分：

| 下游方向 | `lab/` 中的工作 | 最后可能交付什么 |
| --- | --- | --- |
| 机器学习 | 数据、模型代码、训练配置、run、checkpoint、metric | 一个模型及其使用与验证材料 |
| 深度学习研究 | 算法实现、实验、消融、表格和论文证据 | 一个算法、代码和论文结果 |
| 量化研究 | 数据版本、因子或策略、回测、成本假设 | 一个因子、策略结论或研究报告 |
| AI for Science | 仿真或计算代码、环境、参数、数据和实验 | 一个科学结果、方法或可复现实验 |
| AI Agent 开发 | agent 代码、工具、trace、eval 和失败案例 | 一个 agent、工具或经过验证的能力 |

### 多 agent 有三种协作方式

1. **隔离工作**：每个 agent 有自己的任务、目录或 worktree，尽量避免互相覆盖。
2. **通过 repo 了解同事**：agent 从共享的当前状态、session tree、branch 状态和报告中看到别人正在做什么、
   已经发现了什么、接下来由谁接手。
3. **运行时互相查看和直接沟通**：当运行环境支持 agent 列表、状态查询和消息时，agent 可以查看同事、继续追问、
   交换发现或主动 handoff；repo 继续保存稳定状态，避免重要信息只留在临时对话里。

当前 template 为第一种提供 task packet、ownership 和 worktree，为第二种提供 memory、session tree、branch status
和报告；自动文件锁、实时 presence 或 merge queue 可以在真实协作需要出现后继续开发。第三种依赖外部 runtime：
近期可以使用 Paseo 的 agent 状态与直接消息能力；[LingTai](https://github.com/Lingtai-AI/lingtai) 与
[lingtai-kernel](https://github.com/Lingtai-AI/lingtai-kernel) 可作为 durable mailbox 和 multi-agent network 的设计参考。

这里需要验证的不是“agent 能不能发消息”本身，而是互相查看和直接沟通是否真的减少重复劳动、转述成本和
协作错误，以及哪些信息仍然必须回写 repo 才能长期可信。

因此，多 agent 通信本身也是一个可以单独研究的问题：什么时候直接消息更有效，什么时候必须通过 repo 留下
可恢复的共同状态，以及两者怎样配合。

---

## 3. 我想验证的核心判断

### 判断 1：它有泛化性

同一套 harness 不需要绑定某一种算法或固定工作流程。下游项目会填充自己的 `lab/`、项目状态和交付内容，
也可以增加少量领域规则；repo 中关于 agent 协作、记忆、安全、追踪、验证和持续改进的整体架构继续使用。

### 判断 2：它能让复杂任务做得更好

这里的“更好”不是一个抽象口号，而是以后要观察这些事情：

- 任务是否更容易真正完成；
- 结果是否更可靠、更容易复现；
- agent 是否更少忘记上下文或重复做已经做过的事；
- 多个 agent 是否更少互相覆盖、跑偏或污染共享状态；
- 多个 agent 是否更容易了解彼此的工作并完成 handoff；
- 出现错误后是否更容易定位和恢复；
- human 是否减少了重复解释、盯进度和收拾残局的工作；
- human 给出的目标颗粒度，是否能通过 plan 和 task packet 转成 agent 能独立完成的任务颗粒度；
- human 是否可以停留在目标、边界和验收层，而不必反复给 agent 微观操作指令；
- 长任务中的目标漂移、范围膨胀和遗忘是否减少。

### 判断 3：它可能更省 token 和模型资源

我预期它会更省 token，原因包括：

- 长期信息保存在 repo，不需要每个新 session 都重新解释完整背景；
- agent 只读取当前任务需要的文件和状态，不必反复加载整个项目；
- 大任务被拆成有边界的小任务，child agent 只拿有限上下文；
- 简单任务可以使用便宜模型和低 effort，困难或高风险任务才使用昂贵模型；
- 长报告落盘，主 agent 只接收摘要和关键证据；
- agent 调度会参考任务类型、难度、模型能力、provider quota 和近期 token 消耗；
- 目标是进一步综合模型速度、能力、剩余额度和 token 价格，为不同任务选择合适的模型；
- human 不需要在每次 session 都重新解释背景，也不需要人工转述每个 agent 的进度；
- human 和 agent 都能从同一套入口、地图和状态文件掌握 repo 与 project，减少“双方理解的不是同一个项目”。

这里的效率不只是 agent API 的 token 数，还包括 human-agent 反复沟通消耗的 token、时间和精力。
当前 template 已经实现了上下文控制、任务分层和 quota-aware routing；速度、价格与实际任务效果之间的最优选择
还需要通过真实使用继续校准。
---

## 4. 当前实现与后续开发

### 当前已经支持的基础

- Claude Code 与 Codex 的项目入口、能力 adapter 和一致性检查；
- 权限规则、工具调用 hook、context 提醒与 compact/clear 后的状态回注；
- harness、ANATOMY、same-commit、部分 evidence/release/regression 关系的 validator 与 CI；
- 读取 provider quota 和近期消耗、给 child task 生成模型与 effort 建议的工具；
- 迁移已有 repo、校验迁移前后 tracked bytes、管理模板版本和向下游同步新版的脚本；
- human brief、批注式 plan、decision、review、human gate、subagent packet、worktree、handoff 和 fresh review；
- experiment card、ledger、只读监控、run summary、artifact index 与 claim/evidence promotion 流程。

ELF、Agent-R1 和模板同步测试已经为部分机制提供了 replay 证据：ELF 压测 hook、validator、skills 和 subagents；
Agent-R1 检查已有 repo 的保守迁移与文件保留；合成上下游测试检查版本同步不会覆盖项目内容。它们支持“这些机制
可以工作”，但不负责回答下游任务效果是否更好。

### 本来就由下游填充的内容

- `lab/code/` 中的领域实现、配置、测试和实验入口；
- 数据集、checkpoint、run、metric、table、figure 和 trace；
- hypothesis、experiment、evidence、claim 和 release gate 的真实条目；
- `deliverables/` 中的论文、模型、算法、报告或 release。

空 template 里没有这些内容是符合预期的。它提供位置、流程、边界和检查方式；真正的内容只能由 ML、量化、
AI for Science 或 Agent 等下游任务产生。

### 已经登记成 issue 的开发路线

生命周期审计发现的缺口已经压缩成八个可独立实现和验收的 issue：

| Issue | 要解决的能力 |
| --- | --- |
| [#12](https://github.com/a-green-hand-jack/ml-project-repo-agent-native-template/issues/12) | 自动化新项目 bootstrap，增强 existing-repo 的语义归类与 runtime adoption proof |
| [#13](https://github.com/a-green-hand-jack/ml-project-repo-agent-native-template/issues/13) | 让 human brief、plan、review 和 approval 形成可检查的生命周期状态 |
| [#14](https://github.com/a-green-hand-jack/ml-project-repo-agent-native-template/issues/14) | 建立 repo-native 多 agent 状态、直接通信、ownership 冲突检测与 handoff 控制面 |
| [#15](https://github.com/a-green-hand-jack/ml-project-repo-agent-native-template/issues/15) | 把真实任务结果、模型速度和价格加入 outcome-aware 路由 |
| [#16](https://github.com/a-green-hand-jack/ml-project-repo-agent-native-template/issues/16) | 完整化实验审批、运行状态、scheduler adapter、监控、告警与恢复 |
| [#17](https://github.com/a-green-hand-jack/ml-project-repo-agent-native-template/issues/17) | 加强 artifact→evidence→claim→deliverable 的端到端完整性与可复现交付 |
| [#18](https://github.com/a-green-hand-jack/ml-project-repo-agent-native-template/issues/18) | 加强 ANATOMY 语义漂移检查，以及 Claude/Codex 的 enforcement parity 与降级检测 |
| [#19](https://github.com/a-green-hand-jack/ml-project-repo-agent-native-template/issues/19) | 用多个真实下游验证 feedback→agent 实现→release→sync 的 template 自我升级闭环 |

现有 [#11](https://github.com/a-green-hand-jack/ml-project-repo-agent-native-template/issues/11) 继续作为下游采用与版本同步
追踪表。#12–#19 都写明了目标、范围、验收标准和边界，后续可以由 main agent 排优先级，再分别派 agent 在独立
worktree 中实现。实现通过测试、review 和压力测试后进入 template 新版本。

### 需要用下游实验回答的问题

- 还没有一个真正使用这个 template 完成的下游研究项目；
- 还没有证明它比普通 repo 更容易完成任务；
- 还没有证明它提高了结果质量或可复现性；
- 还没有证明它真的节省 token、时间或 human effort；
- 还不知道不同领域需要对 harness 做多少定制；
- 还没有系统验证 agent 直接沟通在不同 runtime 中能带来多少额外价值。

这些是经验问题，不能只靠继续写功能解决。需要在实验开始前冻结一个明确的 template 版本，列清该版本实际支持的
能力，再用同一任务和 evaluator 比较 baseline 与 harness。

### 两条持续改进循环

1. **下游 task repo → template repo → 下游 task repo**：真实项目发现 template 缺口，形成带版本和复现的反馈；
   缺口进入 issue；main agent 拆任务并指挥其他 agent 实现；template 测试、review、发版；下游再同步新版，同时
   保留自己的项目内容。
2. **template repo → 新版 template**：template 在自用、真实 case replay、trace 和压力测试中发现问题，把有效的
   agent、skill、hook、validator 或 workflow 沉淀下来，经验证后进入下一个版本。

这两条循环就是 template 的自我升级方式：不是要求当前版本一次性拥有所有能力，而是让缺口可以被发现、登记、
分派、实现、验证、发版并同步。当前第二条已有压力测试记录，第一条会随着真实下游 case 开始运转。
---

## 5. 怎么做下游测试

下游验证可以分成两层：先用公开 benchmark 做受控比较，再用真实项目检验跨领域泛化。

### 第一层：公开 benchmark

公开 benchmark 的好处是任务、测试和成功标准相对固定，适合比较“普通 repo”与“完整 harness”在结果、token、
长任务漂移和 human 介入上的差异。根据官方仓库，第一轮最值得保留的是下面四类：

| 优先级 | Benchmark | 为什么适合 |
| --- | --- | --- |
| 主 benchmark | [GitTaskBench](https://github.com/QuantaAlpha/GitTaskBench) | 54 个真实任务覆盖 7 类场景，要求 agent 理解并使用完整 repo、配置环境、执行任务和交付实际结果，还提供成本相关评价；与本文主张最接近 |
| 端到端项目，二选一 | [E2EDev](https://github.com/SCUNLP/E2EDev) / [ProjDevBench](https://github.com/zsworld6/projdevbench) | E2EDev 有 46 个项目和细粒度需求对应的 Gherkin/Behave 测试；ProjDevBench 从高层规格构建完整 repo，并评估架构、正确性和迭代改进 |
| 迭代压力测试 | [SlopCodeBench](https://github.com/SprocketLab/slop-code-bench) | 让 agent 在需求持续变化时扩展自己之前的代码，正好测试路径依赖、长期漂移和代码结构退化；官方目前把它定位为开放 evaluation primitive，适合定向压力测试而不是唯一总分 |
| 长周期已有 repo，少量抽样 | [SWE-bench Pro](https://github.com/scaleapi/SWE-bench_Pro-os) | 真实代码库中的长周期 issue，适合压力测试规划、探索和多轮修改；Docker/Modal 环境和运行成本较高，第一轮只抽少量任务 |

[FEA-Bench](https://github.com/microsoft/FEA-Bench)、[SWE-bench-Live](https://github.com/microsoft/SWE-bench-Live)
和 [DevBench](https://github.com/open-compass/DevEval) 都是可用备选，但与上面四类有较多重叠。FEA-Bench 适合
feature implementation，但完整数据需要额外抓取；SWE-bench-Live 适合降低数据污染并覆盖多语言；DevBench 适合
分阶段观察设计、环境、实现和测试。第一轮不必全部运行。

另一组 benchmark 只适合作为**诊断探针**，不应拿来证明整个 harness 有效：

- [MRG-Bench](https://github.com/MRG-Bench/MRG-Bench) 与
  [RepoExec](https://github.com/FSoft-AI4Code/RepoExec) 主要测试 repo context、函数生成、可执行性和依赖利用；
- [RepoBench](https://github.com/Leolty/repobench) 与
  [CrossCodeEval](https://github.com/amazon-science/cceval) 主要测试跨文件补全和 retrieval。

它们可以用来单独检查 anatomy、上下文检索或 token/context 策略是否有帮助，但任务太局部，测不到长期状态、
human-agent 颗粒度、多 agent 协作和最终项目交付。

### 第二层：真实跨领域 case

公开 coding benchmark 只能证明软件开发场景，不能单独证明对机器学习、量化研究或 AI for Science 的泛化性。
Human 已确认愿意尝试下面四个项目，但目前不预先锁定领域，也不直接宣布它们都是主实验：

| 领域 | 当前候选 | 为什么合适 | 使用前必须处理的问题 |
| --- | --- | --- | --- |
| ML / 深度学习 | [MLAgentBench](https://github.com/snap-stanford/MLAgentBench) | 任务要求检查数据、修改训练代码、反复实验并改善指标，且有独立 evaluator | 只使用任务、starter code 和 evaluator；它自带的 agent state、workspace snapshot 与调度不能只给完整 harness 条件使用 |
| 量化研究 | [Qlib](https://github.com/microsoft/qlib) | 可以完整承载因子、模型、组合、回测和研究报告，指标也比较完整 | Qlib 是研究平台，不是现成 benchmark；必须自己冻结数据版本、universe、时间切分、交易成本、调参次数和隐藏样本外评测 |
| AI for Science | [CORE-Bench v1.1/OOD](https://huggingface.co/collections/agent-evals/core-bench-v11) | 需要恢复真实科学代码环境、运行实验、读取产物并回答可自动核验的问题 | 任务答案已经公开，运行时要隔离答案和 evaluator，并限制可能导致泄漏的网络访问；优先先试 CPU/no-GPU capsule |
| AI Agent 开发 | [tau3-bench](https://github.com/sierra-research/tau2-bench) | 可以让 agent 在 repo 中开发工具调用、RAG 或 policy agent，再用固定任务检查最终状态与规则遵守 | 官方 benchmark 原本评的是已经做好的 agent；这里必须另行冻结 starter agent、开发集和不可见 held-out test，并固定 release/tag |

这四个候选的共同优点是都有明确产物和外部评价方法，分别覆盖模型实验、量化研究、科学复现和 agent 开发。
但它们是否真的适合当前 template，要先各做一个最小 integration pilot，实际测出安装难度、运行时间、数据许可、
GPU/CPU 消耗和 evaluator 隔离方式，再根据证据决定选哪两三个进入主实验，而不是先凭领域偏好锁定。表中的时间和
算力只能是 pilot 预算，不能当成项目官方保证。

MLAgentBench、CORE-Bench 和 tau-bench 也可以考虑通过统一的
[HAL harness](https://github.com/princeton-pli/hal-harness) 运行外部评测。这里的 HAL 只负责把任务和 evaluator
固定下来；被比较的仍然是任务 repo 采用普通工作方式还是本文的完整 harness。

### 最简单的比较方式

对相同任务，比较：

1. **Baseline**：普通 repo、基础 `AGENTS.md`、单 agent、固定模型策略，没有结构化跨 session memory、实验台账、
   自动任务拆分、多 agent 和预算路由；
2. **完整 harness**：允许使用 template 的 memory、ANATOMY、skills、subagents、实验与产物索引、模型路由、hooks
   和 validators。

两组必须使用相同起始任务、可用模型集合、总 token/费用/时间/算力上限和 human 介入规则。所有 agent 调用都计入
同一总预算。benchmark 自己的 task runner、隐藏数据和 evaluator 放在任务 repo 之外，开发过程中保持冻结，并且
两组完全相同。完整 harness 可以路由模型或并行，但不能因此得到额外总预算。

先做三种简单场景：

1. 正常持续运行；
2. 在首次得到有效实验结果后强制结束 session，再让一个 fresh session 只根据 repo 恢复；
3. 在中途加入一条预先写好的 human review，要求改计划或否决一个结论。

然后记录：

- 最终任务是否完成；
- 结果质量与可复现性；
- 总 token，以及昂贵模型使用量；
- 总时间和 agent 轮数；
- human 介入次数；
- human 提示、澄清、转述进度所花的消息数、时间和 token；
- human 任务描述与 agent 实际执行任务之间发生重新拆分或返工的次数；
- 重复读取、重复解释和返工次数；
- agent 之间成功或失败的协作与 handoff 次数；
- 与原目标、scope 或验收标准发生偏离的次数；
- 错误操作、状态丢失和恢复成本；
- 最终结论能否追到具体 commit、配置、数据、run 和 artifact；
- 安全违规、数据泄漏、未验证结论和试探 evaluator 的次数；
- 为适配该领域额外增加了多少配置、规则和维护工作。

如果完整 harness 没有改善结果，或者节省的 token 抵不过维护成本，也应该如实记录。

第一轮先比较整个 harness 作为一个完整系统是否有用。只有完整系统出现稳定差异后，再分别关闭 memory、
多 agent、模型路由或 validator 做消融，判断收益究竟来自哪里。

---

## 6. 论文最简单的故事

论文可以直接讲下面这件事：

> 复杂的 agent 项目不能只依赖一段越来越长的 chat。我们把整个 repo 设计成 agent 的开发 harness：
> 它同时承载入口、规则、能力、长期状态、人机协作、领域工作、交付和验证，并支持多个 agent 独立工作或协作。
> 我们在几个不同下游任务中测试这套 harness 是否能够复用，以及它对任务完成、结果质量、可追溯性、
> human effort、agent 协作和 token 消耗的影响。

论文的主要贡献可以是：

1. 一个完整、可运行、可复用的 repo-native agent harness；
2. 一种让 repo 的入口、规则、能力、状态、领域工作与交付相互配合的项目架构；
3. 一套面向复杂项目的状态管理、多 agent 协作、资源路由、安全和结果追踪机制；
4. 一套把下游反馈、压力测试发现和修复变成 template 新版本并同步回下游的演化机制；
5. 在不同下游任务上的真实使用结果，包括收益、成本、失败和不适用的地方。

这更像一篇 **system / artifact / empirical paper**，而不是一篇重新定义“治理”的纯理论论文。

---

## 7. 当前表述边界

- 当前还没实现的 harness 能力属于开发 roadmap，不自动构成 template 的长期边界；确认有价值后可以提 issue、
  派 agent 实现并进入新版本。
- “复杂、最终要产出结果的 repo-based 项目”是设计目标，不是已经证明覆盖所有任务的事实。
- 这个 harness 不替代领域本身的代码、数据、评测方法和专业知识。
- 现有 replay 说明 template 能承载真实项目，不说明它已经提高这些项目的最终效果。
- “效果更好”和“更省 token”目前都是核心假设，必须通过下游 case 验证后再写成结论。
- 如果某些领域需要大量改动 harness，也要把这种定制成本算进泛化性评价。
- runtime 提供的直接 agent 消息能力与 repo 自身提供的持久协作状态需要分开评价。
- 每轮正式实验都要冻结并记录所用 template 版本，不能把实验结束后才开发的能力倒算进当时结果。

---

## 8. 暂定标题

**A Repo-Native Harness for Complex Agentic Projects**

中文：**面向复杂 Agent 项目的 Repo-Native Harness**

也可以继续保留一句口号：

> **Design the harness, not just the agent.**

---

## 9. Human 批注区

前几轮已经确认：第 0 节表达的是你的想法；四个跨领域项目都愿意尝试；冻结外部 evaluator、只比较 repo harness
的边界正确；目前不锁定具体领域，由 integration pilot 决定主实验；“已经支持 / 待开发或增强 / 由下游填充”的
区分正确；template 自我升级闭环符合你的想法；生命周期地图继续保留。

生命周期地图与第 4 节发现的缺口已经压缩并创建为 #12–#19。接下来只需继续收敛：

1. #12–#19 中哪些是 integration pilot 前的 blocker，哪些可以边做 case 边增强；
2. 第一批 integration pilot 先尝试哪个候选；
3. 这份定位文档是否已经可以定稿，还是还要继续调整论文故事。

可以直接改正文，不需要保留我的措辞。下一轮以你的批注和 diff 为准继续收敛。

---

## Revision log

- 2026-07-11：根据 human 重新定调，撤掉 shape/invariant、5 对象 + 2 过程和 high-stakes governance 主线，
  改为“通用 repo-native harness + 可替换 lab + 跨领域下游验证”的简单版本。
- 2026-07-12：吸收 human 第一轮正文批注，改为“整个 repo 共同构成 harness”；补清 `lab/` 与最终交付的关系、
  多 agent 的隔离/共享/直接沟通、human-agent 沟通成本，以及下游反馈和 template 自我改进两条循环。
- 2026-07-12：吸收 human 第二轮正文批注；补入 human-agent 任务颗粒度、长任务漂移和共同项目理解；把 Paseo
  与 LingTai 记为多 agent 协作参考；核对公开 benchmark 后，将验证分成受控 coding benchmark 与真实跨领域 case 两层。
- 2026-07-12：复核第二批 benchmark；收敛为 GitTaskBench 主测、E2EDev/ProjDevBench 二选一、SlopCodeBench
  迭代压力测试和少量 SWE-bench Pro 长周期任务，并将 MRG-Bench、RepoExec、RepoBench、CrossCodeEval 降为诊断探针。
- 2026-07-12：吸收 human 对 ANATOMY、memory、skills/workflows/hooks/subagents 和 `lab/` 内容的批注；复核跨领域
  候选后，将 MLAgentBench、Qlib、CORE-Bench v1.1/OOD、tau3-bench 记为待 integration pilot 的候选池，并明确
  外部 evaluator 与被测 repo harness 必须隔离。
- 2026-07-12：吸收 human 第三轮批注；由只读 subagent 深挖 template 全生命周期后，把能力改写为“项目接入→定位→
  计划→拆分/路由→实现/实验→监控/恢复→证据/交付→反馈/升级”，并区分代码实现、流程实现和骨架；记录 human
  已接受四个跨领域候选与评测边界，且暂不锁定领域。
- 2026-07-12：吸收 human 第四轮澄清；明确本文写的是目标形态与开发方向，不是当前版本的静态能力判决；把状态
  改为“已经支持 / 待开发或增强 / 由下游填充”，并补入“缺口→issue→agent 实现→验证→发版→同步”的自我升级
  闭环。下游代码、数据、实验和交付尚未填入被记为预期状态，不再写成 template 限制。
- 2026-07-12：吸收 human 第五轮批注并保留生命周期地图；将生命周期与 roadmap 缺口压缩成 GitHub #12–#19，
  分别覆盖 bootstrap/adoption、人机计划状态、多 agent 协作、outcome-aware 路由、实验运行与恢复、端到端证据交付、
  ANATOMY/跨 runtime conformance，以及真实下游自我升级验证；#11 继续追踪下游版本与同步状态。
