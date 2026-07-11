# 经验报告 outline：自举一套 agent 治理框架（self-hosting experience report）

> **这份是什么**：fable-5 力荐的第一篇论文体裁——**经验报告 / experience report**。它不主张普遍有效性，
> 只报告"我们用这套治理框架治理它自己的开发"这一个真实、被全程 instrument 的案例。经验报告体裁对
> "n=1、作者即用户"宽容，正好补 framework 稿最大的软肋。**这是 outline，不是成稿。**
>
> **定位真源仍是** `...-v3.zh.md`（严谨）/ `-v4-plain.zh.md`（人话）。本 outline 是"先发哪篇、用什么数据"的落地。
> 分支 `research/paper-positioning`，不入 main。

---

## 0. 一句话

> 我们把一套"环境编码"的治理框架**用在它自己的开发上**，并用 git 历史 + repo 内台账把这个过程全程记录。
> 本文报告：这套治理在自己的构建中**抓到了哪些真实缺陷、拦住了什么、维护代价多大、哪里没守住**。

诚实定位：这是**单案例、作者即用户、时间跨度短**的经验报告，不是效果证明。价值在于**闭环可观测**——
治理框架 + 被治理对象是同一个 repo，所以它对自己的每一次拦截/漏判/演化都留了痕。

---

## 1. 现有真实数据快照（2026-07-11）

**规模（诚实）**：45 commits / 4 天（2026-07-08→07-11）；3 个 merge PR + 多个编号 PR（#1/#2/#5/#10）走 fresh-reviewer。
提交类型：docs 18 / feat 10 / fix 6 / chore 6。→ **强项是密度与闭环，不是时长**（见 §5 威胁）。

**能力面（DESIGN §10 真值，validator 防漂移）**：16 subagents / 12 skills / 8 commands / 8 hooks / 9 validators / 20 doctrine md。

**三次对抗性 stress-replay（`lab/docs/audits/stress-test-ledger.yaml`）**：
- **ELF case**：外部真实公开仓库，4 轮，产出 **F1–F19** findings，多数已修（fix 提交 6fed240 / bd1266a / f523992 / 18281c1 / 62a9413）。
- **Agent-R1 采用 replay**：真实 existing-repo 迁移，178 个 tracked 文件按 hash 全保全、0 blocker、目标 repo 0 error。
- **upstream-sync 自测**：adversarial-probe-matrix，fresh sonnet5 复审（fb70fb1）出 1 HIGH + 4 MEDIUM + 1 LOW，HIGH 已修。

---

## 2. 报告方法：git + 台账即 instrumentation

经验报告的"测量仪器"不是新搭的实验台，而是**框架自带的可观测面**——这本身也是论点：治理把自己的运行留了痕。

可从现成历史直接测的量：
- **自我缺陷拦截**：validator / fresh-reviewer / hook 在自己构建中抓到的缺陷数、类别、修复延迟（提交距离）。
- **PR 门控**：每个 PR 的 fresh-reviewer findings 数与分级、折叠修复的提交。
- **结构防漂移**：same-commit / anatomy-drift gate 触发与拦截次数（F3/F4/F17 类）。
- **stress-replay**：三案例的 findings、闭环轮次、byte 保全率。
- **维护代价**：fix vs feat 比例、一个 finding 从发现到闭环的轮次/提交数。
- **能力演化**：change-control 台账条目、能力数量随 validator 防漂移的一致性。

---

## 3. 观察（按主题组织，全部可回溯到提交/台账）

**主题 A：治理抓到了自己构建中的真实 bug。**
最有说服力的一组——框架的护栏/检查/复审在**开发框架自身**时命中真缺陷：
- hook 路径自锁 bug（F2/F11，相对路径导致 hook 在新顶层 session 失效）→ 修复并扩面（6fed240/bd1266a），round4 用真实嵌套仓库 cwd 漂移复验闭环。
- PR#10 复审抓出缓存粘滞 / 原子写缺失 / stdin 守卫缺失（1e155e7）。
- subagent 因 cwd 不持久化误写主仓库（F13/F19）→ 4 处加"写操作前 pwd 自查"（f523992）。

**主题 B：fresh-reviewer 门控稳定产出 findings。**
每个编号 PR 都折叠了独立复审发现（#1/#2/#5/#10）；upstream-sync 的 fresh sonnet5 出 1 HIGH+4 MED+1 LOW。
→ "作者写、他人（fresh 模型）审"的分离在实践中确实拦下东西，不是摆设。

**主题 C：结构防漂移 gate 命中。**
same-commit / anatomy-drift 拦住"改结构不更新地图"（F3 已知边界、F4 补修、F17 skill-实践漂移修复）。

**主题 D：外部真实仓库压测的可迁移信号。**
Agent-R1 迁移 178 文件 0 破坏 0 error；ELF 4 轮把治理逼出 19 条 findings 并逐轮闭环。

**主题 E（诚实的负面）：**
- hook 自锁 bug 曾存在一段时间才被发现 → 护栏本身也会有洞。
- 纪律面（experiment closure / artifact index）**没有 validator 强制**，round2 实际执行时就漏了 experiment card / run summary（F17 类）→ "机器强制"与"靠纪律"的边界是真实的。
- self-hosting 的退化性（见 §5）。

---

## 4. 这份报告支持 / 不支持什么

**支持**：
- 治理**可以**被自举、且在自己的开发中拦到真实缺陷（存在性证明）。
- "机器强制 vs 靠纪律"的边界在实践中可见（有 validator 的守住了，纯纪律的漂移了）。
- 三次对抗压测给出可迁移性的**弱信号**（外部真实仓库 0 破坏迁移 + 逐轮闭环）。

**不支持（明写）**：
- 不证明对**别的团队/别的领域**有效（n=1、作者即用户）。
- 不证明"因果收益"（没有对照组：无 baseline 的 A/B）。
- 时间跨度短（4 天），不是纵向长期运维数据——**这点必须诚实，别学别人假装"几个月生产使用"**。

---

## 5. 威胁到效度（集中一节，别到处设防）

- **n=1 且自指**：框架治理自己，规则作者写、conformance 作者跑，"通过"接近同义反复。
- **作者即用户**：无独立使用者，学习成本/可用性有偏。
- **时间短、规模小**：45 commits / 4 天；findings 数受"我们主动做了多少 stress"影响，非自然暴露率。
- **self-hosting 退化性（fable-5 指出）**：内层产物就是 harness 本身，从未跨真实 release/deploy 边界，
  覆盖不了"造 production agent"域最该测的 hazard。→ 经验报告**只声称"治理开发过程"，不声称"治理产品发布"**。
- **缓解**：把可回溯性做满（每个观察都挂提交/台账 id）；负面结果照报（§3 主题 E）；明确 scope 到"开发过程"。

---

## 6. 为什么先发这篇（vs framework 稿）

- **唯一手握真数据的论文**：git 历史 + 三次 stress-replay 是现成的，不依赖任何新域实例化。
- **体裁对 n=1 宽容**：experience report / SEIP-FSE industry 类轨道接受"作者即用户"的诚实单案例。
- **给 framework 稿铺路**：这篇把"框架能自举、能抓自己的 bug"坐实后，framework 稿再谈跨域，梯子更稳。
- **顺带修一个尴尬**：写这篇会自然逼着把 `lab/research/claims.yaml` 从占位变成**模板自己的能力台账**
  （fable-5 的"一石二鸟"建议）——经验报告的每条 claim 都能挂上证据链。

**建议发表顺序**：经验报告（数据实、姿态诚）→ framework workshop 稿（概念）→ 正会稿（外部实例化后）。

---

## 7. 候选标题

- **Governing Its Own Construction: An Experience Report on a Self-Hosting Agent Governance Framework**
- **When the Harness Catches Its Own Bugs: A Self-Application Experience Report**
- 中文工作名：**治理自己的构建：一套自举 agent 治理框架的经验报告**

---

## 8. 待补 / 下一步（把 outline 变成可写稿）

1. **让数据长一点**：这份 outline 是 07-11 快照；再积累若干周的自举使用 + 每次 stress 都登记，纵向信号会更硬。
2. **把 claims.yaml 变成模板能力台账**：给每条"我们声称的治理能力"挂 stress-probe / 提交 / 复审证据（同时喂 §6）。
3. **量化维护代价**：统计 finding→闭环的轮次/提交数、fix/feat 比随时间的变化。
4. **补一个非 self 的小 case**（哪怕一个外部小仓库的采用 replay），把"仅自指"稍微撑开。
5. 与 framework 稿(v3)对齐：经验报告负责"存在性 + 诚实数据"，framework 稿负责"对象/方法/跨域概念"。
