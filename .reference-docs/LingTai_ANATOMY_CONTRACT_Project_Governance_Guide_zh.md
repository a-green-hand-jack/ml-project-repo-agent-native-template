# 借鉴 LingTai 的 ANATOMY / CONTRACT

> **防止项目文档漂移与治理膨胀的实践指南**

**PROJECT GOVERNANCE PLAYBOOK**

| 防漂移 | 防膨胀 | 可验证 |
| --- | --- | --- |
| 明确真相方向<br>同一变更同步维护 | 一个规则一个 owner<br>只治理真实边界 | 双向链接<br>契约测试与 CI 门禁 |

本指南将 LingTai 两个仓库中的 ANATOMY / CONTRACT 机制，提炼为一套可迁移到软件研发、跨团队协作、服务运营和一般项目管理中的治理方法。重点不是复制文件名，而是建立“结构地图、行为承诺、操作手册、决策记录和任务状态”之间清晰且可验证的所有权边界。

- **版本：** 1.0（2026-07-13）
- **研究基线：** `Lingtai-AI/lingtai` 与 `Lingtai-AI/lingtai-kernel` 的 `main` 快照

## 执行摘要
> **最重要的五句话**
>
> ANATOMY 管现实结构，CONTRACT 管批准承诺。结构变了，地图跟着现实更新；行为偏了，实现必须回到契约。一个规则只有一个 owner，其他地方只做链接。不是每个目录都值得拥有文档，只治理真正的架构边界。所有关键承诺都必须有测试、指标或验收证据。


LingTai 的方法可以理解为五种信息载体之间的职责分离。只要这些职责混在一个万能文档中，文档就会同时承担导航、规范、教程、历史和任务状态，最终必然出现漂移与膨胀。

| **载体**            | **回答的问题**                             | **主要事实来源**       | **不应该放什么**               |
|---------------------|--------------------------------------------|------------------------|--------------------------------|
| **ANATOMY**         | 在哪里、由什么组成、如何连接、状态归谁     | 当前代码与项目结构     | 行为承诺、操作教程、历史讨论   |
| **CONTRACT**        | 可以怎样使用、必须保证什么、失败意味着什么 | 经批准的产品或接口承诺 | 文件清单、详细调用链、操作步骤 |
| **MANUAL / SKILL**  | 具体怎么做、怎么排障、怎么验证             | 当前操作流程           | 核心规范和架构所有权           |
| **ADR / Decision**  | 为什么选择这个方案、权衡是什么             | 决策时的证据与授权     | 当前任务状态和操作教程         |
| **Issue / Tracker** | 谁在做什么、何时完成、当前阻塞             | 当前执行状态           | 长期架构规范和稳定承诺         |

### 一页版执行框架
| 序号 | 要点 |
| --- | --- |
| **1** | **先分类事实**<br><br>这是结构事实、行为承诺、操作流程、历史决策，还是任务状态？先决定唯一 owner，再写内容。 |
| **2** | **规定真相方向**<br><br>代码与 Anatomy 冲突时通常修地图；实现与已批准 Contract 冲突时通常修实现，不能偷偷弱化承诺。 |
| **3** | **同一变更维护**<br><br>代码、文档、验收证据在同一 PR 或同一变更单中完成；不要把“以后补文档”当作流程。 |
| **4** | **显式纳管**<br><br>根 Contract 明确列出受治理组件。旧项目一次迁移一个真实边界，不做全仓库形式主义改造。 |
| **5** | **机械验证**<br><br>路径、链接、章节、版本、测试文件和契约行为尽可能进入 CI；所有权冲突只报告，不自动决定。 |


### 适用场景
- 多人或多团队共同维护的代码库、服务或业务流程。

- 接口、数据格式、交付标准、错误语义或责任边界经常发生争议的项目。

- 文档很多，但团队仍然不知道应该相信哪一份的项目。

- 正在从遗留架构逐步迁移到更清晰模块边界的项目。

- 希望让 Coding Agent 或自动化工具可靠参与维护的项目。

## 1. ANATOMY 与 CONTRACT 的核心分工
### 1.1 ANATOMY：项目的分布式导航地图
ANATOMY 只描述当前结构：组件在哪里、包含什么、彼此如何连接、由谁组合、持久和临时状态归谁所有。它不是用户手册，也不是接口规范。

- Components：关键文件、模块、团队、服务、交付物或子组件。

- Connections：调用关系、数据流、控制流和团队交接关系。

- Composition：父组件、子组件、相邻组件以及谁负责最终装配。

- State：数据库、文件、文档、缓存、队列、看板等状态的所有权。

- Notes：代码或流程表面不明显，但确实会影响理解的限制和陷阱。


> **阅读原则**
>
> 对于“系统是什么形状、这个能力在哪里、状态由谁拥有”这类结构问题，沿 Anatomy 图逐层下钻；对于“所有调用点、所有匹配文件”这类枚举问题，仍然使用搜索。地图用于定位，真实代码和项目记录才是证据。


### 1.2 CONTRACT：项目的分布式承诺系统
CONTRACT 定义一个组件如何被使用以及它必须保证什么。它不只是函数签名或交付清单，还应覆盖输入输出、错误、顺序、时间、并发、重试、取消、兼容性、持久性和非目标。

- Purpose：这个边界保护什么，以及谁依赖它。

- Behavior：使用者、开发者和运营者必须遵守的可观察义务。

- Port：技术无关的接口或跨团队交接面。

- Adapters：当前生产实现和测试替身，以及哪些机制不得泄漏到上层。

- Contract rules：明确、可验证、可判定的不变量。

- Contract tests：证明承诺的自动化测试、指标、审计记录或验收清单。

### 1.3 四种文档的边界
| **问题**                   | **唯一归属**    |
|----------------------------|-----------------|
| “支付模块在哪里？”         | ANATOMY         |
| “重复提交是否必须幂等？”   | CONTRACT        |
| “如何执行退款或排查失败？” | MANUAL          |
| “为什么选择异步清算？”     | ADR             |
| “退款重构做到哪一步？”     | Issue / Tracker |


> **防膨胀的第一原则**
>
> 同一事实只能有一个规范 owner。其他文档只提供链接和上下文，不复制正文。复制一条规则到四份文档，不是冗余保障，而是制造四个未来漂移点。


## 2. 防止漂移：先规定“真相方向”
项目文档最常见的失败，不是信息缺失，而是出现冲突时没人知道应该改代码、改流程还是改文档。LingTai 的关键做法是为不同类型的冲突规定不同方向。

| **冲突**                             | **默认事实方向**                       | **默认处理**                                             |
|--------------------------------------|----------------------------------------|----------------------------------------------------------|
| **实际结构与 ANATOMY 不一致**        | 实际代码、组织和状态归属通常是当前事实 | 修复 ANATOMY；若现实本身是缺陷，则修复现实并保留冲突证据 |
| **实现行为与受批准 CONTRACT 不一致** | CONTRACT 是规范                        | 优先视为实现缺陷；只有得到授权后才能改变承诺             |
| **实际操作与 MANUAL 不一致**         | 先判断是违规操作还是操作流程已经失效   | 修复执行或更新 Manual，不能自动假设其中一方正确          |
| **当前方案与旧 ADR 不一致**          | ADR 是历史记录                         | 创建 superseding ADR，不改写过去的决策记录               |
| **当前进度与项目计划不一致**         | 项目系统中的当前状态                   | 更新 Tracker，不污染架构文档                             |


> **不可接受的“修复”**
>
> 发现实现不符合既有承诺后，为了让文档重新一致而直接把 Contract 改弱。这会把缺陷合法化，并让所有下游使用者失去稳定边界。


### 2.1 结构真相为什么通常来自现实
ANATOMY 是地图。文件被移动、团队职责被调整、状态所有权已经改变后，地图不能要求现实迁就旧路径。结构性变化应在同一变更中更新 Anatomy。

### 2.2 行为真相为什么来自批准的契约
CONTRACT 表达的是对消费者、客户、相邻团队或系统的批准承诺。实现偶然返回错误结果、遗漏状态或改变顺序，不会自动获得修改承诺的权力。真正改变承诺时，应有明确授权、版本变化、受影响方评估和验收证据。

## 3. 七个防漂移机制
| 序号 | 要点 |
| --- | --- |
| **1** | **同一变更更新**<br><br>结构、行为、操作或证据发生变化时，在同一 PR、变更单或发布批次中更新对应文档。文档不是后续清理任务，而是完成定义的一部分。 |
| **2** | **组件共址**<br><br>让 Anatomy、Contract 和 Manual 靠近它们描述的组件或工作流，利用代码审查和 Git 历史暴露漂移。 |
| **3** | **双向链接**<br><br>Anatomy 与 Contract 互相链接；父子 Anatomy 双向链接；Contract 与相关 Contract 在存在规范依赖时互相链接。 |
| **4** | **显式受治理集合**<br><br>由根 Contract 列出已纳管组件。只有被明确索引的边界才承担完整约束，允许遗留系统逐步迁移。 |
| **5** | **每条承诺有证据**<br><br>关键 Contract 规则必须对应自动化测试、指标、审计、fixture 或人工验收清单。无法观察的承诺通常还不够具体。 |
| **6** | **失败要响亮**<br><br>缺失 owner、重复 owner、单向链接和行为冲突应阻塞或报告；自动化工具不能擅自创建、删除或重写架构边界。 |
| **7** | **统一维护契约**<br><br>对受治理文档使用标准维护说明、固定章节和版本规则，让维护义务本身可以被机械检查。 |


### 3.1 同一变更的分类规则
- 文件、模块、团队职责、依赖、调用关系或状态所有权变化：更新 ANATOMY。

- 输入输出、错误、顺序、时限、重试、取消、兼容性或行为承诺变化：更新 CONTRACT 和验收证据。

- 操作命令、排障步骤或例行流程变化：更新 MANUAL。

- 架构选择、权衡和授权变化：新增或替代 ADR。

- 以上都没变化：记录已检查即可，不要制造无意义的文档 churn。

### 3.2 双向链接的诊断价值
双向链接不是为了增加文档数量，而是为了让不一致变得可检测。只要关系是单向的，就很容易出现已删除组件仍被引用、两个 owner 同时认领同一边界，或一个组件没有任何规范 owner。

| **链接**                                    | **意义**                                 |
|---------------------------------------------|------------------------------------------|
| **ANATOMY ↔ CONTRACT**                      | 结构地图与行为承诺互相可达，但不复制内容 |
| **父 ANATOMY ↔ 子 ANATOMY**                 | 可以从根下钻，也可以从局部返回上层       |
| **CONTRACT ↔ 相关 CONTRACT**                | 仅在确有规范依赖时建立，且双方都承认关系 |
| **Owner CONTRACT ↔ implementation ANATOMY** | 实现目录没有独立承诺时，明确唯一 owner   |
| **ANATOMY / CONTRACT ↔ MANUAL**             | 能力的结构入口和规范入口都能发现操作指导 |

## 4. 七个防膨胀机制
| 序号 | 要点 |
| --- | --- |
| **1** | **不是每个目录都需要文档**<br><br>只有能够作为独立架构单元被理解、修改、测试和负责的组件，才值得拥有 Anatomy / Contract。 |
| **2** | **根文档只做路由**<br><br>根层只列一级结构、全局边界和规范入口，不复制局部组件的详细事实。 |
| **3** | **一个规则只有一个 owner**<br><br>错误码、状态语义、操作步骤、历史原因和任务进度分别归 Contract、Manual、ADR 和 Tracker。 |
| **4** | **保持尺寸压力**<br><br>普通 Anatomy 应保持简短；文档持续变大通常意味着组件粒度或信息所有权出了问题。 |
| **5** | **不写历史流水账**<br><br>Anatomy 和 Contract 只描述当前结构和当前承诺，历史原因放 ADR，变更历史交给 Git。 |
| **6** | **不写任务状态**<br><br>负责人、完成百分比、短期计划和 TODO 属于项目系统，不能污染长期架构文档。 |
| **7** | **一次迁移一个真实切片**<br><br>先选择真实能力，再完成 Port、生产 Adapter、组合、契约测试和文档配对；不先创建空目录和空接口。 |


### 4.1 组件是否值得纳管的判断问题
- 这个单元是否拥有独立、可观察的行为承诺？

- 它是否隔离了一个会变化的外部机制、供应商、操作系统或团队交接？

- 它是否拥有独立状态、失败域、兼容性或生命周期？

- 一个不了解全部兄弟模块的人，能否把它作为一个单元理解和负责？

- 它是否需要独立的测试、监控或验收证据？


> **不应创建空壳**
>
> 单函数 helper、纯 value object、无独立承诺的 Adapter、临时脚本和生成目录通常不需要本地 Contract。为了文件名对称创建空文档，只会提高导航成本。


### 4.2 渐进披露
入口应当简短，细节按需加载。一个健康的阅读路径是：


```text
Root ANATOMY
  -> Domain ANATOMY
    -> Component ANATOMY
      -> exact code / project record

Root CONTRACT
  -> Component CONTRACT
    -> Port / Adapter / contract tests
      -> MANUAL when procedures are needed
```


## 5. 如何迁移到一般项目管理
在非代码项目中，可以把 Port 理解为跨团队交接接口，把 Adapter 理解为具体执行渠道或工具，把 Composition Root 理解为负责选择渠道、安排资源和完成装配的人或流程。

| **架构概念**         | **项目管理对应物**                              |
|----------------------|-------------------------------------------------|
| **Core / Use Case**  | 稳定的业务决策、验收标准和流程策略              |
| **Port**             | 跨团队交付接口、输入输出标准、审批面或服务目录  |
| **Adapter**          | Jira、Slack、邮件、表单、供应商、脚本或具体平台 |
| **Composition Root** | 项目启动、发布编排、负责人或工作流配置层        |
| **Contract test**    | 验收清单、SLA 报告、审计日志、自动校验或演练    |

### 5.1 示例：设计团队向工程团队交付
> **ANATOMY 应描述**

- 设计稿、组件库、需求文档和验收记录分别在哪里。

- 产品、设计、工程和测试各自负责什么。

- 评审、反馈、冻结和交付状态如何流转。

- 最终状态记录在哪个系统，哪些渠道只是通知。

> **CONTRACT 应描述**

- 工程开始开发前必须收到哪些输入。

- 设计稿达到什么状态才算 Ready for Development。

- 缺失项在多长时间内确认或退回。

- 接受后哪些修改属于 breaking change，如何重新评估排期。

- 什么记录构成正式变更，哪些聊天消息不具有规范效力。

- 最终以什么验收证据判断完成。


```markdown
## Contract rules

1. 交付必须包含最终设计链接、交互说明、响应式规则和异常状态。
2. 交付状态必须为 Ready for Development。
3. 工程团队在两个工作日内确认接受或给出缺失项。
4. 接受后修改核心流程视为 breaking change，必须重新评估排期。
5. 即时消息不构成正式需求变更；变更必须记录到项目系统。
6. 验收以测试环境中的 acceptance checklist 为准。
```


### 5.2 其他适用边界
| **场景**       | **适合写入 Contract 的内容**                                   |
|----------------|----------------------------------------------------------------|
| **发布管理**   | 发布输入、审批、回滚条件、责任人、窗口、成功/部分成功/失败定义 |
| **数据交付**   | Schema、字段语义、更新频率、延迟、缺失值、兼容性和数据质量阈值 |
| **客户支持**   | 响应时限、升级条件、信息最小集、交接状态和关闭标准             |
| **安全事件**   | 严重度、通知顺序、保全证据、授权边界、恢复和复盘要求           |
| **供应商集成** | 可用性、错误分类、重试、账务边界、变更通知和退出策略           |

## 6. 可直接采用的模板
> **使用方法**
>
> 先在根文档中定义约定，再选择一个高风险、反复出问题的真实边界试点。不要批量为所有目录生成模板。


### 6.1 ANATOMY 模板
```markdown
---
related_files:
  - CONTRACT.md
  - ../ANATOMY.md
  - src/component.py
  - tests/test_component.py
maintenance: |
  Keep related_files complete, repo-relative, and duplicate-free.
  Code and the current project structure are the structural source of truth.
  Update this Anatomy in the same change whenever files, responsibilities,
  dependencies, composition, or state ownership change.
---

# Component Name Anatomy

一句话定义这个组件作为一个架构单元是什么。

## Components

- `ComponentService` — 负责核心编排
  (`src/component.py:20-85`)。
- `StorageAdapter` — 负责持久化机制
  (`src/adapters/storage.py:10-73`)。
- `tests/test_component.py` — 主要边界测试。

## Connections

- 谁调用这个组件。
- 这个组件调用哪些外部能力。
- 数据、控制或交付物如何流动。

## Composition

- Parent: `../ANATOMY.md`
- Paired contract: `CONTRACT.md`
- Children: 子组件 Anatomy
- Composition root: 谁负责选择实现并完成 wiring

## State

- 持久状态：数据库、文件、文档、外部系统。
- 临时状态：缓存、内存状态、处理中任务。
- 状态由谁创建、读取、修改和清理。

## Notes

- 结构上不明显但很重要的限制。
- 已知陷阱和明确不属于本组件的职责。
```


### 6.2 CONTRACT 模板
```markdown
---
name: component-name
contract_version: 1
root_contract: ../../CONTRACT.md
related_files:
  - ANATOMY.md
  - src/port.py
  - src/adapters/production.py
  - tests/test_component_contract.py
  - MANUAL.md
maintenance: |
  This Contract is normative for observable behavior.
  Update the Port, affected implementations, acceptance evidence, and this
  Contract in the same change. Do not weaken the Contract merely to match
  accidental implementation behavior. Bump contract_version for breaking changes.
---

# Component Name Contract

## Purpose

这个组件保护什么边界、为谁提供什么能力。

## Behavior

- 必须保持的可观察义务。
- 明确禁止的行为。
- 安全、隐私、恢复和敏感数据要求。

## Port

### Inputs

- 输入字段、前置条件、单位、取值域和默认值。

### Outputs

- 成功、部分成功、失败和未知结果。

### Timing and ordering

- 超时、顺序、并发、重试和取消。

## Adapters

- 当前生产实现。
- 测试 fake。
- 哪些技术细节只能存在于 Adapter。
- Composition Root 在哪里完成选择和注入。

## Contract rules

1. 明确且可验证的不变量。
2. 错误传播规则。
3. 幂等或重复提交规则。
4. 兼容性规则。
5. 状态和持久性规则。
6. 明确的非目标。

## Contract tests

- 自动化测试、指标、审计或人工验收证据。

## Maintenance

- 什么变化需要更新 Contract。
- 什么变化属于 breaking change。
- 谁可以批准承诺变化。
```


### 6.3 写作检查
| **ANATOMY 应回答**   | **CONTRACT 应回答**                |
|----------------------|------------------------------------|
| 它是什么、在哪里？   | 它承诺什么？                       |
| 它由哪些部分组成？   | 输入、输出和失败如何定义？         |
| 它连接谁、由谁组合？ | 顺序、时间、重试和兼容性是什么？   |
| 它拥有什么状态？     | 哪些实现可以替换，哪些语义不能变？ |
| 下一层应该去哪里读？ | 用什么测试、指标或审计证明？       |

## 7. 变更判断矩阵
| **变更内容**                 | **ANATOMY**   | **CONTRACT**   | **MANUAL** | **ADR**         |
|------------------------------|---------------|----------------|------------|-----------------|
| **文件、模块或团队职责移动** | 更新          | 视影响         | 否         | 可选            |
| **调用关系或交付流程变化**   | 更新          | 承诺变化则更新 | 可能       | 可选            |
| **输入输出字段变化**         | 可能          | 更新           | 可能       | breaking 时建议 |
| **错误语义变化**             | 通常否        | 更新           | 可能       | 重大变化时      |
| **SLA 或响应时限变化**       | 通常否        | 更新           | 可能       | 建议            |
| **操作命令变化**             | 否            | 通常否         | 更新       | 否              |
| **排障流程变化**             | 否            | 通常否         | 更新       | 否              |
| **技术实现替换但行为不变**   | 更新位置/组合 | 通常不改       | 可能       | 重大选择时      |
| **持久状态或 Schema 变化**   | 更新          | 更新兼容规则   | 可能       | breaking 时建议 |
| **项目进度或负责人变化**     | 否            | 否             | 否         | 否；放 Tracker  |
| **未来计划和 TODO**          | 否            | 否             | 否         | 否；放 Roadmap  |

### PR / 变更单自检
> 1\. 本次变化是否改变文件、职责、依赖、组合或状态所有权？
>
> 2\. 本次变化是否改变输入输出、错误、顺序、时间、重试、兼容性或其他可观察承诺？
>
> 3\. 本次变化是否只改变操作步骤或排障方法？
>
> 4\. 本次变化是否需要新的授权、权衡或决策记录？
>
> 5\. 受影响文档和证据是否与实现处于同一变更中？
>
> 6\. 是否复制了一个已有规则，而不是链接到其 owner？
>
> 7\. 是否无必要地创建了新的 Anatomy、Contract、目录或接口？

## 8. 自动化检查与 CI 门禁
自动化的目标不是替代架构判断，而是便宜地捕获确定性漂移。先检查路径、配对和结构，再逐步增加符号、依赖和契约行为验证。

### 8.1 第一阶段：基础结构检查
> 1\. Frontmatter 能正确解析。
>
> 2\. related_files 中的文件真实存在。
>
> 3\. 不允许绝对路径、..、空路径和重复链接。
>
> 4\. ANATOMY 与 CONTRACT 必须双向链接。
>
> 5\. 父子 ANATOMY 必须双向链接。
>
> 6\. 受治理 Contract 必须被根 Contract 索引。
>
> 7\. 每个受治理 Contract 必须有唯一 name 和正整数版本。
>
> 8\. 必需章节存在且顺序正确。
>
> 9\. Components 中的代码引用目标存在。
>
> 10\. 引用行号没有超过文件长度。
>
> 11\. Contract 中列出的测试、指标或验收文件真实存在。
>
> 12\. 不允许只有标题和空章节的文档。

### 8.2 第二阶段：架构与语义检查
> 1\. 使用 AST 或符号索引验证类、函数和接口，而不只验证行号。
>
> 2\. 检查 Contract Port 与生产 Adapter 的接口签名一致。
>
> 3\. 检查 Core 不导入、构造或判断具体 Adapter。
>
> 4\. 检查至少一个真实生产 Adapter 参加 contract test。
>
> 5\. 检查每项用户或模型可调用能力的 Manual 同时从 Anatomy 和 Contract 可达。
>
> 6\. 生成只读架构图、孤儿节点、重复 owner 和版本报告。


> **自动化边界**
>
> 路径和格式问题可以自动修复；所有权、组件粒度、承诺变化和边界迁移只能报告并由负责人决定。CI 不应为了变绿而自动创建空 Contract 或重新指定 owner。


### 8.3 建议的失败报告字段
```yaml
component_or_directory: payments/settlement
actual_state:
  anatomy: present
  local_contract: absent
  owner_contracts:
    - payments/CONTRACT.md
    - finance/CONTRACT.md
violated_rule: exactly one owning governed Contract
missing_or_conflicting_links:
  - Anatomy links to two owners
  - finance/CONTRACT.md has no reciprocal link
suggested_action: >-
  Report the ownership conflict; do not auto-create or delete files.
```


## 9. 推荐的落地路线
| **阶段**                 | **主要动作**                                                                           | **完成标志**                                   |
|--------------------------|----------------------------------------------------------------------------------------|------------------------------------------------|
| **阶段 1：建立根规则**   | 创建根 ANATOMY、根 CONTRACT 和开发/贡献指南；定义职责、真相方向、模板和最小验证。      | 没有批量创建子文档。                           |
| **阶段 2：选择一个试点** | 选择高风险、反复争议的真实边界，完成 Anatomy、Contract、真实接口、生产实现和验收证据。 | 一个完整、可运行的垂直切片。                   |
| **阶段 3：建立验证**     | 先实现路径、链接、章节和版本检查，再增加符号、依赖和契约测试。                         | CI 能阻止确定性漂移。                          |
| **阶段 4：按问题扩展**   | 只在组件反复发生责任、兼容性、错误语义或文档漂移问题时纳管。                           | 治理范围随真实风险增长，而不是随目录数量增长。 |

### 9.1 第一个试点应该怎样选择
- 多个团队或模块共同依赖。

- 错误、重试、顺序或兼容性语义复杂。

- 状态所有权不清，曾经出现重复写入或互相覆盖。

- 经常因为“文档说法不同”导致返工。

- 能够在较小范围内补上真实验收测试。

### 9.2 不建议的启动方式
- 一次性为整个仓库或所有工作流生成空模板。

- 先创建 core/ports/adapters 目录，再寻找内容填充。

- 把现有 Wiki 全部复制进新文档。

- 要求所有历史文档立即符合完整新规范。

- 先开发复杂文档平台，再验证团队是否需要。

## 10. 可直接放入 CONTRIBUTING 的规则
```markdown
## Architecture and Contract Maintenance

Before changing a governed component:

1. Read the nearest ANATOMY.md to locate its files, dependencies,
   composition, and state.
2. Read the paired CONTRACT.md to understand its observable promises,
   errors, ordering, compatibility, and acceptance evidence.
3. Classify the change:
   - structure, ownership, dependency, or state changed: update ANATOMY;
   - interface or observable behavior changed: update CONTRACT and its tests;
   - operating procedure changed: update the Manual;
   - design rationale changed: add or supersede an ADR.
4. Keep affected implementation, documentation, and evidence in the same PR.
5. Code is normally the structural truth for ANATOMY.
6. CONTRACT is normative for approved behavior. Do not weaken it merely to
   match accidental implementation behavior.
7. Do not create empty ANATOMY or CONTRACT files for filename symmetry.
8. Do not duplicate a rule across documents. Link to its single owner.
9. Run architecture graph validation and affected contract tests before merge.
10. If ownership or pairing is ambiguous, report the conflict; do not auto-fix it.
```


### 10.1 最小 Definition of Done
- 实现或项目记录已经更新。

- 对应的结构地图和行为契约已经检查。

- 受影响的 Manual、ADR 或 Tracker 已按职责更新。

- 关键承诺有自动化测试、指标、审计或验收记录。

- 架构图和链接验证通过。

- 没有新增无 owner 的规则、空壳文档或第二份手工注册表。

## 11. 最终原则
| 序号 | 要点 |
| --- | --- |
| **1** | **地图服从现实**<br><br>ANATOMY 描述结构。结构发生变化时，在同一变更中修复地图。 |
| **2** | **承诺约束实现**<br><br>CONTRACT 表达经批准的可观察行为。实现偏离时，不能靠弱化契约消除冲突。 |
| **3** | **规则单一归属**<br><br>结构、承诺、操作、决策和任务状态分别由不同载体拥有。 |
| **4** | **只治理真实边界**<br><br>组件要先拥有独立责任、状态、失败域或接口，才值得纳管。 |
| **5** | **证据胜过口号**<br><br>每项关键承诺都需要测试、指标、审计或验收证据。 |


> **推荐的第一步**
>
> 不要批量创建几十份 Markdown。选择一个真实、经常出问题的跨模块或跨团队边界，为它建立第一组完整的 ANATOMY + CONTRACT + 验收证据。只有这个切片真正改善了理解、变更和验证，再扩展到第二个组件。


## 附录 A：术语表
| **术语**             | **含义**                                                                |
|----------------------|-------------------------------------------------------------------------|
| **受治理组件**       | 被根 CONTRACT 明确索引，必须遵守完整配对、版本、维护和验证规则的组件。  |
| **Port**             | 由稳定业务边界拥有的技术无关接口；在项目管理中也可以表示跨团队交接面。  |
| **Adapter**          | 把具体技术、工具、平台、供应商或执行渠道转换为 Port 的实现。            |
| **Composition Root** | 只负责选择具体实现、读取部署配置和完成装配的外层入口。                  |
| **Contract test**    | 对同一 Port 的生产 Adapter 和测试替身验证相同语义的共享测试或验收证据。 |
| **Breaking change**  | 使以前合规的消费者、团队或 Adapter 不再合规的承诺变化。                 |
| **渐进披露**         | 入口只提供路由和必要规则，细节沿链接按需加载。                          |
| **Fail loud**        | 发现边界或所有权不一致时明确报告并阻塞，而不是静默忽略或擅自修复。      |
| **Truth direction**  | 当现实、实现和文档冲突时，预先规定哪一方是默认事实以及如何修复。        |

## 附录 B：研究来源
本指南是对以下公开仓库机制的提炼，不是 LingTai 官方规范。研究基线为 2026-07-13 的 main 快照：lingtai 5fb554b69f966b39cb9eca32a70c84d628714d18；lingtai-kernel 86a1a84356111ff020c1be77fdcbb85c2fd0e64b。

- [Lingtai-AI/lingtai](https://github.com/Lingtai-AI/lingtai)

- [lingtai 根 ANATOMY.md](https://github.com/Lingtai-AI/lingtai/blob/main/ANATOMY.md)

- [lingtai 根 CONTRACT.md](https://github.com/Lingtai-AI/lingtai/blob/main/CONTRACT.md)

- [lingtai 开发指南](https://github.com/Lingtai-AI/lingtai/blob/main/dev-guide-skill/SKILL.md)

- [Lingtai-AI/lingtai-kernel](https://github.com/Lingtai-AI/lingtai-kernel)

- [lingtai-kernel 根 ANATOMY.md](https://github.com/Lingtai-AI/lingtai-kernel/blob/main/ANATOMY.md)

- [lingtai-kernel 根 CONTRACT.md](https://github.com/Lingtai-AI/lingtai-kernel/blob/main/CONTRACT.md)

- [架构文档验证测试](https://github.com/Lingtai-AI/lingtai-kernel/blob/main/tests/test_architecture_documents.py)

- [ANATOMY 漂移检查器](https://github.com/Lingtai-AI/lingtai-kernel/blob/main/src/lingtai/intrinsic_skills/lingtai-kernel-anatomy/scripts/check_anatomy_drift.py)


> **版本提醒**
>
> 仓库会持续演进。将这套方法用于自己的项目时，应把本项目的根 ANATOMY、根 CONTRACT、开发指南和验证器视为唯一当前规范，而不是长期依赖外部仓库的某个历史版本。
