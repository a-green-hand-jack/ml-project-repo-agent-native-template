# LingTai 代码防漂移与防膨胀机制

> **从基线、范围、架构、测试、迁移与构建，到运行时的系统治理指南**

**LINGTAI CODE GOVERNANCE PLAYBOOK**

基于 LingTai 实践提炼的可迁移框架，适用于软件工程、平台治理、产品运营与跨团队协作。

> **核心命题**
>
> ANATOMY / CONTRACT 让边界可见；基线门、最小变更、负向架构测试、迁移纪律、真实发布物验证和运行时指纹，让这些边界不容易退化。

| 文档信息 | 内容 |
| --- | --- |
| **文档用途** | 建立可执行的代码漂移与工程膨胀治理机制 |
| **适用对象** | 技术负责人、架构师、工程经理、平台团队、Coding Agent 维护者 |
| **整理日期** | 2026 年 7 月 13 日 |
| **研究基线** | `Lingtai-AI/lingtai @ 5fb554b`；`Lingtai-AI/lingtai-kernel @ bb411e8` |

*本文是源码机制的管理学提炼，不是对 LingTai 内部规范的逐字复制。*

## 使用说明

这份文档既可以作为团队讨论材料，也可以直接作为代码治理制度的初稿。建议先读“一页总览”和“优先落地的八项机制”，再选择一个高风险模块作为试点。不要一次性为整个项目制造大量接口、文档或 CI 规则。


### 目录

- 1\. 一页总览：四层防线与八项高价值机制

- 2\. 漂移与膨胀：先辨认问题类型

- 3\. 基线与来源门：确保改的是正确代码

- 4\. 范围控制：最小完整变更

- 5\. 架构边界：阻止 Core 重新耦合

- 6\. 可执行证据：精确接口与负向测试

- 7\. 持久化状态：迁移纪律与版本锁步

- 8\. 发布产物：验证用户真正拿到的内容

- 9\. 运行时漂移：发现仍在执行的旧代码

- 10\. 知识与流程治理：防止规则系统自身膨胀

- 11\. 落地优先级与分阶段路线

- 12\. 团队检查清单与 CI 门禁

- 附录 A：PR 模板

- 附录 B：测试与门禁示例

- 附录 C：研究基线与源码索引

## 1. 一页总览：四层防线与八项高价值机制

LingTai 的 ANATOMY / CONTRACT 是“可见层”：它们让结构、边界和承诺可以被人和 Agent 找到。真正让这些边界不容易退化的，是下方多层流程、测试、状态和运行时机制。

**四层防线**


```text
开发基线与范围门
        ↓
架构依赖与唯一所有权
        ↓
精确接口、负向测试与真实产物验证
        ↓
迁移纪律、原子持久化与运行时漂移检测
```


### 治理强度分级

| **级别**      | **含义**                                    | **典型机制**                                    |
|---------------|---------------------------------------------|-------------------------------------------------|
| G0 设计原则   | 给出判断方向，但通常不直接阻断提交。        | 渐进披露、Port 必须由真实边界挣得。             |
| G1 流程门     | 要求开发者或 Agent 在执行副作用前完成检查。 | exact base、non-goals、PR 前复核 live base。    |
| G2 CI 硬门    | 违反规则会导致测试或构建失败。              | 精确接口面、负向架构测试、wheel manifest 检查。 |
| G3 运行时保护 | 程序运行后继续发现陈旧代码或不一致状态。    | source fingerprint、版本拒绝、租约与原子写。    |

### 优先借鉴的八项机制

| **优先级** | **机制**                               | **直接收益**                                          |
|------------|----------------------------------------|-------------------------------------------------------|
| 1          | Invariant / Variation / Non-goals      | 低成本抑制 scope creep。                              |
| 2          | 开始与提交前双重 exact-base 检查       | 避免基于陈旧主线做出内部自洽但整体错误的改动。        |
| 3          | 公共接口“精确集合”测试                 | 阻止 API 只增不减。                                   |
| 4          | 负向架构测试                           | 阻止 Core 再次导入 Adapter、Path 或 service locator。 |
| 5          | Fake 与生产 Adapter 共享契约测试       | 防止测试替身成为另一个产品。                          |
| 6          | Append-only migration + 成功后推进版本 | 避免半迁移与 schema 回退。                            |
| 7          | 构建真实发布物再检查                   | 发现源码与 wheel/image 的分叉。                       |
| 8          | 兼容层必须有删除条件                   | 控制长期双路径与历史负担。                            |


> **判断原则**
>
> 凡是只靠“大家记得”维持的边界，迟早会漂移；凡是只允许增加、没有退出机制的表面，迟早会膨胀。


## 2. 漂移与膨胀：先辨认问题类型

“漂移”是不同事实副本逐渐不一致；“膨胀”是接口、路径、文档、兼容层或工具不断增加，却没有相应的删除和边界收缩机制。二者往往互相强化：表面越多，维护副本越多，漂移概率越高。

### 常见漂移类型

| **类型**   | **表现**                                                 | **LingTai 对应防线**                                   |
|------------|----------------------------------------------------------|--------------------------------------------------------|
| 基线漂移   | 开发者以为基于最新主线，实际在旧分支或错误 worktree。    | exact base、clean worktree、live-base reconciliation。 |
| 边界漂移   | Core 又开始直接构造数据库、POSIX、Telegram 或 Git 实现。 | Port/Adapter 方向、Composition Root、负向架构测试。    |
| 行为漂移   | 实现与批准承诺、错误语义或顺序语义不一致。               | CONTRACT、共享 contract tests。                        |
| 状态漂移   | schema 版本与实际迁移进度不一致。                        | append-only registry、成功后写版本、原子替换。         |
| 分发漂移   | 源码树有文档/资源，发布包中却缺失或多出意外文件。        | 真实 wheel 构建与 exact manifest 检查。                |
| 运行时漂移 | 磁盘已升级，长运行进程仍执行旧 import。                  | startup fingerprint 与定时 source-drift 检查。         |
| 知识漂移   | Wiki、README、Manual、Contract 分别复制同一规则。        | 单一 owner、渐进披露、repo-local dev guide。           |

### 常见膨胀类型

| **类型** | **典型症状**                                        | **收缩策略**                                              |
|----------|-----------------------------------------------------|-----------------------------------------------------------|
| 范围膨胀 | 一个修复顺手包含重构、清理、配置和发布变更。        | 明确 variation axis 与 non-goals。                        |
| 抽象膨胀 | 为每个类创建 Interface、Factory、Manager。          | Port 必须由真实架构边界挣得。                             |
| API 膨胀 | 方法只加不减，出现万能 execute/run/raw 接口。       | 精确公共面与“没有第八类操作”式断言。                      |
| 兼容膨胀 | 新旧 API、双 migration route、多个 alias 长期共存。 | 单一 canonical path；兼容层有 owner、截止版本和删除条件。 |
| 文档膨胀 | 根文档复制每个局部规则，入口越来越长。              | 短入口、局部 Contract、按需 Manual/reference。            |
| 产物膨胀 | 过宽 glob 将临时文件、嵌套文档一并打包。            | 同时检查缺失和意外新增，必要时锁定 exact count。          |

## 3. 基线与来源门：确保改的是正确代码

代码治理的第一步不是设计接口，而是证明“当前工作树到底是哪一份代码”。如果基线错误，后续测试、文档和设计可能全部内部一致，却与真实主线不一致。

### 3.1 开始前证明 exact baseline

1.  明确本次 baseline：通常是实时 origin/main，或维护者指定的 tag / commit。

2.  证明 worktree 干净；目录名称或口头确认不算证据。

3.  证明 HEAD 与选定 baseline 相等。

4.  使用聚焦 branch 和独立 worktree，避免触碰其他进行中的本地工作。

**建议记录的最小证据**


```text
BASE_SHA=<selected baseline>
HEAD_SHA=<current HEAD>
WORKTREE_CLEAN=true
BASE_EQUALS_HEAD=true
```


### 3.2 副作用前重新确认 live base

开始时的验证不能永久有效。提交、推送、开 PR 或发布前，应重新检查主线是否移动；如果 base 已变化，应先重放、复核重叠路径并重新执行受影响验证。


> **为什么这很重要**
>
> “三小时前测试通过”只能证明三小时前那份代码。主线发生变化后，旧验证不能自动继承到新组合。


### 3.3 Exact path scope

高风险 PR 应声明预期修改的路径集合，并在最终 diff 中核对“没有多余路径，也没有漏掉预期路径”。这比只看文件数量更可靠，尤其适合 Agent 执行的批量修改。

### 3.4 Exact-checkout provenance

Python 项目还需验证测试导入的是当前 checkout，而不是 site-packages 中的旧安装。LingTai 的测试会断言包的 `__file__` 指向当前仓库。该检查成本极低，却能消除一类极隐蔽的假绿测试。

**可移植示例**


```python
from pathlib import Path

import mypackage


def test_imports_current_checkout():
    actual = Path(mypackage.__file__).resolve()
    expected = (REPO_ROOT / "src/mypackage/__init__.py").resolve()
    assert actual == expected
```


### 基线门检查表

**□** 已记录 exact base SHA。

**□** 当前 worktree 干净。

**□** HEAD 等于声明的 baseline。

**□** 提交/推送/开 PR 前再次确认 live base。

**□** 最终 diff 与 exact path scope 一致。

**□** 测试确认 import / build 来源是当前 checkout。

## 4. 范围控制：最小完整变更

LingTai 用“最小完整”替代“最小文件数”。一个变更可以跨多个文件，但只能围绕一个明确不变量和一个真实边界闭环；不应顺手吸收相邻问题。

### 4.1 三项前置声明

| **声明**       | **要回答的问题**                   | **示例**                                    |
|----------------|------------------------------------|---------------------------------------------|
| Invariant      | 哪些行为、顺序或安全属性必须保持？ | 同一 workdir 最多只有一个 live holder。     |
| Variation axis | 本次允许改变的唯一维度是什么？     | 将 POSIX 锁机制从 Core 移至 Adapter。       |
| Non-goals      | 本次明确不解决什么？               | 不增加 Windows 实现；不改变超时和错误文本。 |

### 4.2 最小完整 vertical slice

**完整的边界迁移**


```text
一个真实 use case
+ 一个 Core-owned Port
+ 一个真实生产 Adapter
+ Composition Root wiring
+ 共享契约测试
+ 必要的 Anatomy / Contract 更新
```


只创建接口、目录或空文档不算完成；只有生产路径已注入、测试证明语义一致，才可以声明该边界完成迁移。

### 4.3 明确拒绝“文档合规表演”

- 如果结构与行为都未变化，不要为了显得合规而制造文档 churn。

- 不要批量创建空 ANATOMY、CONTRACT、ports/ 或 adapters/ 目录。

- 不要把顺手清理、重命名和格式化混进一个高风险行为变更。

- 不要以“以后可能需要”为理由增加第二条生产路径。


> **范围判断**
>
> 最小完整变更不是“只改一行”，而是“只解决一个边界，并把该边界需要的代码、测试、文档和 wiring 一次做完整”。


## 5. 架构边界：阻止 Core 重新耦合

很多架构重构会在数月后回退：某个开发者为了方便，重新在 Core 中 import 具体数据库、文件系统或 SDK。LingTai 不只写依赖规则，还用接口形状和源代码负向测试锁住它。

### 5.1 Port 必须由真实边界挣得

Port 不是按文件数量分配的。纯算法、value object 和普通 helper 应保持普通代码；只有独立承诺、真实副作用边界或可替换机制，才值得成为 Port。

| **值得建立 Port**                                  | **不值得建立 Port**                    |
|----------------------------------------------------|----------------------------------------|
| 外部存储、消息、模型、操作系统、支付或供应商机制。 | 单函数 helper 或单一 value object。    |
| 具有明确错误、时序、并发、持久性承诺的能力。       | 只有一个调用方且没有变化轴的内部封装。 |
| 需要 fake 与多个 Adapter 共享语义测试。            | 为了目录整齐创建的空 interface。       |

### 5.2 依赖方向与 Composition Root

**允许的方向**


```text
Adapter  →  Port  ←  Core

部署配置 → 选择 Adapter → 构造 Adapter → 注入 Port → 启动 Core
```


- Core 不得 import、构造、判断或命名具体 Adapter。

- Composition Root 只负责 wiring，不承载业务决策、fallback policy 或 provider-specific 分支。

- 不得通过 service locator、module singleton 或运行时全局注册表让 Core 隐式获取实现。

### 5.3 Capability-native interface

不同能力不需要强制统一成 execute()、run() 或万能 Service。统一的应是语义治理方式，而不是方法名：单位、错误、顺序、并发、状态、持久性和非目标应被明确并验证。

### 5.4 单一所有权与单一 canonical path

- 每个能力只有一个 Core owner。

- 旧路径在新路径稳定后应退休，而不是永久保留双路。

- 不接受 path-or-port、optional production dependency 或 hidden default adapter。

- 兼容层必须有 owner、真实调用方、截止版本、删除条件和专项测试。

### 5.5 架构约束矩阵

| **风险**              | **禁止项**                                 | **验证方式**                               |
|-----------------------|--------------------------------------------|--------------------------------------------|
| 机制泄漏              | Core 出现 Path、os、subprocess、SDK 类型。 | AST / import / source negative tests。     |
| 隐式构造              | Core 在缺省参数下创建生产 Adapter。        | 构造签名与源码断言。                       |
| 双路径                | legacy route 与新 route 同时存在。         | 调用图、公开 export 与专项测试。           |
| Composition Root 膨胀 | 启动层承载业务 policy。                    | 限制 wiring 范围，审查分支和 domain 逻辑。 |
| 接口泛化              | 增加 raw、generic、execute-anything 方法。 | 精确 public surface test。                 |

## 6. 可执行证据：精确接口与负向测试

普通测试证明“允许的行为可以工作”；防漂移测试还要证明“不允许的结构没有重新出现”。LingTai 的关键做法是同时锁定正向行为、公共接口面积和禁止项。

### 6.1 精确公共接口面

不要只断言三个方法存在；应断言公开方法集合恰好等于预期集合。这样任何“临时加一个 raw()”都会触发失败。

**API 面积预算**


```python
EXPECTED = {"load", "save", "delete"}
assert public_methods(MyPort) == EXPECTED
```


### 6.2 负向架构测试

**典型禁止项**


```python
assert "lingtai.adapters" not in core_source
assert "import subprocess" not in core_source
assert "pathlib.Path" not in port_source
assert "service_locator" not in core_source
assert not hasattr(Port, "execute_raw")
```


### 6.3 Fake 与生产 Adapter 共用 contract tests

Fake 只能证明调用者可测试，不能证明生产机制符合相同语义。应把 independent fake 与 production adapter 放进同一套 conformance suite，再为生产机制补充文件系统、网络或进程级测试。

**共享契约测试骨架**


```python
@pytest.mark.parametrize("factory", [FakeAdapter, ProductionAdapter])
def test_contract(factory, tmp_path):
    adapter = factory(tmp_path)
    assert_contract(adapter)
```


### 6.4 生产 Adapter 必须真正被执行

不能让 fake 单独满足 conformance；CI 必须至少运行一个真实生产 Adapter。否则测试通过的可能只是一个理想化模型。

### 6.5 分层验证

1.  先运行最窄、最能决定正确性的测试。

2.  架构图变化时运行 architecture-document validator。

3.  边界变化时运行 contract tests 和 negative tests。

4.  跨包、构建或发布边界时运行更广的 package/build tests。

5.  任何超时、中断或未完成的 suite 都不得报告为通过。


> **证据优先级**
>
> 行为测试优于源码字符串搜索；真实 Adapter 优于只测 fake；真实发布物优于只检查构建配置。


## 7. 持久化状态：迁移纪律与版本锁步

状态漂移比代码漂移更危险，因为错误版本可能已经写入用户目录或数据库。LingTai 使用 append-only、forward-only、成功后推进版本和原子替换，确保状态演进可恢复且不可含糊。

### 7.1 Append-only、forward-only registry

- 迁移只追加，不删除、不重排。

- 不提供隐式 downgrade；遇到未来版本时 fail loud。

- 当前版本由 registry head 推导，避免同时维护常量和列表。

- 已经发布的空槽位用 no-op tombstone 保留版本语义。

### 7.2 成功后才推进版本

**正确顺序**


```text
读取持久版本 N
→ 执行迁移 N+1
→ transform 成功
→ 原子持久化版本 N+1
→ 更新进程内状态

任何一步失败：持久版本仍为最后一个完整成功版本
```


如果先写版本再执行 transform，崩溃会留下“版本已经前进、数据尚未完成”的不可恢复状态。

### 7.3 原子替换与明确失败域

- 使用同目录临时文件写完整内容，再 replace。

- 归档失败、版本写失败和 transform 失败必须有明确传播规则。

- best-effort audit 可以失败开放，但不能伪造主迁移成功。

### 7.4 跨消费者版本锁步

当两个二进制或服务共享同一 schema/version space 时，版本推进必须锁步。单边行为可以通过另一边的 no-op slot 保持编号一致；共享迁移则必须保持相同语义。

### 7.5 版本碰撞恢复

如果两个并行分支错误占用了同一 migration number，并且真实环境已经写入该版本，不能简单改号假装事故没发生。更安全的做法是在下一个空闲版本建立幂等 catch-up migration，先补齐一方逻辑，再执行另一方逻辑。

### 迁移检查表

**□** Registry 连续、append-only，当前版本从 head 推导。

**□** 每个 transform 幂等或有明确重试语义。

**□** 版本只在 transform 成功后持久化。

**□** 替换采用同目录临时文件 + 原子 replace。

**□** 未来版本 fail loud，不自动降级。

**□** 多消费者共享 version space 时已同步版本槽位。

**□** 旧版本 tombstone 未被删除或重排。

**□** 碰撞恢复考虑了已经写入真实环境的版本。

## 8. 发布产物：验证用户真正拿到的内容

源码树正确不等于发布产物正确。package-data glob、Docker copy、编译嵌入和打包工具都可能悄悄遗漏 Contract、Manual、schema 或资源，也可能把临时文件打进去。

### 8.1 构建真实产物

1. 真实构建 wheel、tarball、容器镜像或单文件二进制。

2. 检查最终 archive / image filesystem，而不是只 grep 构建配置。

3. 在可能的情况下安装该产物并运行资源加载测试。

### 8.2 同时防“打少了”和“打多了”

| **检查方向** | **示例**                                    | **目的**                             |
|--------------|---------------------------------------------|--------------------------------------|
| 缺失检查     | 每个内建工具都必须带 CONTRACT.md。          | 防止代码安装了，规范资源没安装。     |
| 意外新增检查 | 必须正好 N 个 Contract，而不是至少 N 个。   | 防止过宽 glob 将嵌套/临时文件打包。  |
| 路径检查     | 资源必须位于运行时真正查找的 archive 路径。 | 防止构建工具放入错误目录。           |
| 语言集合检查 | 必须只有 en/zh/wen 三套 glossary。          | 防止缺失、重复或未经批准的语言扩张。 |

### 8.3 Validator 与 Runtime 共用 Parser

验证器不要复制一套生产规则。应直接调用运行时 parser、schema 或 domain validator，确保 CI 接受的输入就是运行时真正能读取的输入。


> **发布门**
>
> 真正的交付边界是用户安装的 artifact，而不是仓库目录。任何只检查源码、不检查 artifact 的发布流程，都存在分发漂移盲区。


## 9. 运行时漂移：发现仍在执行的旧代码

长运行进程可能在磁盘升级后继续持有旧 import。LingTai 在启动时捕获源代码指纹，并在运行中重新比较，从而识别“磁盘已新、进程仍旧”的状态。

### 9.1 双指纹

- Git revision：快速识别已提交版本变化。

- Source digest：识别 revision 未变但源码字节变化，或无法使用 Git 的情况。

### 9.2 防噪声设计

| **设计**            | **作用**                              |
|---------------------|---------------------------------------|
| 定时节流            | 避免每个 heartbeat 都重复计算与提醒。 |
| 同一 drift key 去重 | 相同漂移只提醒一次。                  |
| 恢复一致时清除      | 磁盘回退或进程刷新后撤销旧提醒。      |
| 建议而非强制中断    | 允许先完成当前任务，再安全 refresh。  |
| 异常 fail-open      | 指纹检查失败不应破坏主业务循环。      |

### 9.3 开发环境有意跳过

Editable/source/dev checkout 中源码变化是正常过程。自动提醒甚至自动重启，可能把一个暂时不可运行的工作树放大成运行故障。因此同一机制在生产和开发环境中采用不同策略。

### 9.4 可迁移到其他系统

- Web 服务：比较启动 artifact digest 与当前部署版本。

- 插件系统：比较已加载插件 manifest 与磁盘/registry 版本。

- Notebook / Worker：检测运行环境与代码包 lockfile 不一致。

- 边缘设备：检测配置版本与当前进程使用的配置快照不一致。

## 10. 知识与流程治理：防止规则系统自身膨胀

治理机制本身也会膨胀。LingTai 通过渐进披露、单一规则 owner、repo-local 开发指南和工具增长门，限制文档与内部平台不断扩张。

### 10.1 Progressive disclosure

**按需下钻**


```text
短入口 / Root rule
  → 局部 Anatomy / Contract
    → 具体 Manual
      → 深层 reference / troubleshooting
```


根文档负责路由，不复制所有局部内容；每层只拥有自己的规则。这样既减少文档漂移，也减少 Agent 的上下文负担。

### 10.2 Contract 与 Manual 分工

| **文档**  | **负责**                               | **不负责**                   |
|-----------|----------------------------------------|------------------------------|
| Contract  | 必须保证什么、错误与顺序语义、禁止项。 | 逐步操作、命令和排障教程。   |
| Manual    | 做什么、怎么做、为什么这样做。         | 重新定义行为承诺。           |
| Dev guide | 开发、验证和 PR 工作流。               | 复制架构事实和局部接口规则。 |

### 10.3 i18n 人工确认门

只有真正用户可见的表面才默认值得国际化。内部枚举、代码接口和 Agent-only 表面新增 i18n 前，需要人类确认，以免一个内部标识扩张成三套资源、别名、文档和测试。

### 10.4 Repo-local dev guide

开发规则与代码一起版本化，而不是只存在于开发者机器的全局 prompt 或外部 Wiki。这样每个 tag / checkout 都携带与其架构相匹配的工作流。

### 10.5 工具增长门

- 只有真实重复工作证明其价值后，才增加 scripts、references 或 assets。

- 禁止空目录、占位工具、一次性报告和 speculative wrapper。

- 支持文件必须由一个入口文档路由，不复制根规则。

### 10.6 副作用授权门

分析、编辑、提交、推送、开 PR、合并、发布、安装和改配置是不同级别的副作用。获得“修改代码”的授权，不自动包含“合并或发布”的授权。该规则能防止 Agent 工作流从代码变更膨胀为未经批准的运维动作。

## 11. 落地优先级与分阶段路线

不建议一次复制 LingTai 的全部规则。应先选择能直接消除真实事故的机制，再逐步建立架构和发布硬门。

### 11.1 投入产出优先级

| **阶段**  | **先落地**                                                                | **暂缓**                    |
|-----------|---------------------------------------------------------------------------|-----------------------------|
| 第 1 周   | PR 三项声明、exact base、禁止无关 diff、超时不得报绿。                    | 复杂文档图、全仓 AST 分析。 |
| 第 2-4 周 | 关键 Port 的精确接口测试、负向 import 测试、fake/production conformance。 | 为所有目录批量创建接口。    |
| 第 2 月   | 迁移顺序、原子写、artifact manifest、exact-checkout provenance。          | 自研通用架构平台。          |
| 稳定后    | 运行时 fingerprint、图报告、跨仓库 schema fixture。                       | 自动重写架构 owner。        |

### 11.2 试点选择标准

- 经常出现职责争议或多个 owner。

- 错误、重试、并发、持久化语义复杂。

- 真实生产实现与测试 fake 已经出现分叉。

- 存在新旧双路径或兼容层堆积。

- 状态迁移曾经失败或多个消费者共享 schema。

- 发布包曾遗漏必要资源。

### 11.3 建议的四阶段路线

1. 范围门：把 invariant、variation、non-goals 和 exact base 写进 PR。

2. 边界门：选择一个真实能力，建立 Port、生产 Adapter、wiring 和 contract tests。

3. 状态与产物门：锁住 migration 顺序、原子写和最终 artifact manifest。

4. 运行时门：针对长进程或分布式系统增加版本/指纹观测。

### 11.4 不建议照搬的部分

- 不要为了形式为每个目录建立 Anatomy / Contract。

- 不要把行号引用当成长期稳定的唯一身份；优先考虑符号锚点。

- 不要在没有真实多实现需求时建立过度抽象的 Port。

- 不要把所有规则第一天就变成硬失败；先从真实重复缺陷中提炼门禁。

- 不要让自动修复工具自行决定架构所有权。


> **成熟度目标**
>
> 最好的治理不是规则最多，而是：关键边界有明确 owner，重大漂移会自动失败，普通开发仍然能够快速完成。


## 12. 团队检查清单与 CI 门禁

### 12.1 Drift & Bloat Gate

**Baseline**

**□** 当前 worktree 干净；HEAD 等于声明的 base。

**□** 副作用前重新确认 live base。

**□** 最终 diff 只包含审阅范围。

**Scope**

**□** 已写明 invariant、variation axis 和 non-goals。

**□** 没有顺手重构、无关清理或发布配置变更。

**□** 变更构成一个最小但完整的 vertical slice。

**Architecture**

**□** 新接口对应真实边界，而不是文件数量。

**□** Core 不 import / 构造具体 Adapter。

**□** Composition Root 只负责 wiring。

**□** 没有 service locator、optional production dependency 或第二条 route。

**□** 公共接口面没有意外扩大。

**Tests**

**□** 正向行为、负向架构和错误路径都有证据。

**□** Fake 与生产实现共享 contract tests。

**□** 生产实现确实被执行。

**□** 测试 import / build 来源是当前 checkout。

**□** 超时、中断或未完成 suite 没有被报告为通过。

**State & Distribution**

**□** Migration append-only，成功后才推进版本。

**□** 写入采用原子替换。

**□** 构建了真实发布物并检查 missing / unexpected entries。

**□** 运行时 parser 与 validator 使用同一语法。

### 12.2 推荐 CI 检查

| **层级** | **检查**                                             | **失败条件**                     |
|----------|------------------------------------------------------|----------------------------------|
| 基础     | git diff --check；导入当前 checkout；目标测试。      | 空白错误、错误包来源、行为回归。 |
| 接口     | Public method set / signature exact match。          | 新增、删除或参数漂移未被批准。   |
| 架构     | 禁止 import、机制词汇、隐式构造、双路径。            | Core/Adapter 边界回退。          |
| 状态     | Migration contiguity、order、retry、future version。 | 版本或持久化语义漂移。           |
| 产物     | 真实 wheel/image manifest 与安装后资源加载。         | 缺失、意外新增或路径错误。       |
| 文档     | Anatomy/Contract links、路径、heading、owner。       | 孤儿、重复 owner、规范图断裂。   |

### 12.3 兼容层准入规则

**□** 存在真实、已识别的旧调用方。

**□** 有单一 owner。

**□** 有截止版本或删除日期。

**□** 有遥测或使用证据，可以判断何时安全删除。

**□** 有专项测试，且不会成为第二条永久生产路径。

**□** 文档明确 canonical path，兼容层不得反向定义新语义。

## 附录 A：可直接使用的 PR 模板


```markdown
## Invariant

本次变更必须保持的不变量：

## Intended variation

本次唯一允许变化的维度：

## Non-goals

- 不做：
- 不新增兼容层：
- 不改变发布 / 配置 / 数据格式：

## Exact baseline

- Base SHA:
- HEAD SHA:
- Worktree clean:
- Base equality verified:

## Exact path scope

Expected paths:
-

Actual paths:
-

## Architecture assessment

- Anatomy impact:
- Contract impact:
- Port / Adapter / Composition impact:
- Public surface changed: yes / no

## Validation evidence

- Focused behavior tests:
- Contract / conformance tests:
- Negative architecture tests:
- Migration / artifact checks:
- git diff --check:

## Remaining risks

-

## Side-effect authorization

- Commit: approved / not approved
- Push / PR: approved / not approved
- Merge / release: approved / not approved
```


## 附录 B：测试与门禁示例

### B.1 精确接口集合


```python
def public_methods(cls):
    return {
        name
        for name, member in vars(cls).items()
        if callable(member) and not name.startswith("_")
    }


EXPECTED = {"acquire", "release"}
assert public_methods(WorkdirLeasePort) == EXPECTED
assert public_methods(PosixWorkdirLeaseAdapter) == EXPECTED
```


### B.2 禁止 Core 泄漏具体机制


```python
core = CORE_PATH.read_text(encoding="utf-8")
for forbidden in [
    "lingtai.adapters",
    "import subprocess",
    "pathlib.Path",
    "service_locator",
]:
    assert forbidden not in core
```


### B.3 Migration 顺序锁


```python
events = []
workspace = FakeWorkspace(events)
run_migrations(workspace)

assert events == [
    "transform:1",
    "store_version:1",
    "transform:2",
    "store_version:2",
]

# 任何 transform 失败时，不得出现对应 store_version。
```


### B.4 Artifact exact manifest


```python
entries = inspect_built_artifact(wheel_path)
expected = {
    "pkg/tools/read/CONTRACT.md",
    "pkg/tools/read/MANUAL.md",
    "pkg/tools/read/schema.json",
}
assert expected <= entries
assert not unexpected_entries(entries)
assert count_contracts(entries) == EXPECTED_CONTRACT_COUNT
```


## 附录 C：研究基线与源码索引

本指南依据两个公开仓库当前 main 快照进行源码审阅和方法提炼。提交 SHA 用于说明研究时点；仓库继续演进后，具体路径和实现可能变化。

| **仓库 / 文件**                              | **研究用途**                                                              |
|----------------------------------------------|---------------------------------------------------------------------------|
| Lingtai-AI/lingtai @ 5fb554b                 | Go 侧 TUI / Portal、共享迁移版本空间和项目开发工作流。                    |
| Lingtai-AI/lingtai-kernel @ bb411e8          | Python runtime、Ports & Adapters、契约测试、构建与运行时漂移机制。        |
| lingtai-kernel/CONTRACT.md                   | 根设计原则：渐进披露、真实边界、Composition Root、能力原生接口。          |
| lingtai-kernel/dev-guide-skill/SKILL.md      | Exact baseline、最小完整变更、分层验证和副作用授权。                      |
| src/lingtai/kernel/migrate/CONTRACT.md       | Append-only / forward-only migration、成功后版本推进、原子写与七类 Port。 |
| src/lingtai/kernel/workdir_lease/CONTRACT.md | 精确接口、生产/fake conformance、负向架构约束。                           |
| src/lingtai/kernel/nudge/source_drift.py     | 启动指纹、60 秒节流、去重和开发环境跳过。                                 |
| src/lingtai/tools/glossary_validator.py      | Registry / resource cross-check 与运行时共享 parser。                     |
| tests/test_tools_package_data.py             | 构建真实 wheel、检查 exact Contract / Manual / glossary manifest。        |
| lingtai/tui/internal/migrate/ANATOMY.md      | 共享 meta.json version space、no-op slot 与碰撞恢复案例。                 |


> **最终总结**
>
> ANATOMY / CONTRACT 负责让架构边界和行为承诺可见；基线门控制“从哪里开始”，范围门控制“改到哪里为止”，负向测试控制“哪些东西绝不能回来”，迁移和 artifact 测试控制“状态与交付是否真实一致”，运行时指纹则控制“进程是否仍在执行旧世界”。
