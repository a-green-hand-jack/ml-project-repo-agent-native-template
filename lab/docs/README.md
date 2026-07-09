# lab/docs/ — 项目级长文档

这里放**项目级长文档**：那些既不适合塞进某目录的 `README.md`（太长/太叙事），也不属于
`lab/research/*.yaml`（不是结构化 claim/evidence）的内容——审计报告、设计文档、实验计划、
时间线、进度更新、参考资料、叙事性记录。

这是本模板「不设通用根级 `docs/`，改用嵌套 `lab/docs/`」设计决定的落地（见
`.agent/repo-documentation-topology.md` 与根 `DESIGN.md` §12）。它属于 `lab/ANATOMY.md`
里归类的 leaf 层，只有 `README.md`，无独立 `ANATOMY.md`（内容是文档而非多文件协作的代码/状态）。

## 子目录

| 目录 | 是什么 |
| --- | --- |
| `overview.md` | 项目级概览：研究方向、目标 venue/里程碑、当前阻塞、下一阶段 |
| `audits/` | 一致性审计、就绪检查、结果审计、来源可见性审计、投稿准备评审 |
| `designs/` | 方法 / 系统 / 算法的分阶段设计文档（成为实现任务或论文正文前） |
| `experiments/` | 跨组件实验计划、消融矩阵、claim-evidence 计划（可执行的实验逻辑在 `../code/experiments/`；权威实验对象在 `lab/research/experiment-ledger.yaml`） |
| `timelines/` | 回顾性时间线、里程碑计划、前瞻排期 |
| `updates/` | 导师汇报、组内更新、合作者摘要、进度备忘 |
| `reference/` | 项目本地来源、来源卡片、处理状态、来源-项目笔记；含迁移 provenance（如 `reference/provenance.md`） |
| `research-narrative/` | 不落在 `lab/research/*.yaml` 结构化 schema 里的叙事性研究记录（如迁移自旧周期的 risk/action board） |
| `code/` | 贴近 `../code/` 的代码运行记录/笔记（细粒度、非项目级） |

## 常见入口

- 想知道当前研究方向与阻塞：`overview.md`。
- 想找一次功能测试/审计的完整记录：`audits/`。
- 想知道某个第三方源的 provenance（clone 来源、commit、可见性）：`reference/provenance.md`。
- 结构化事实（claim/evidence/台账）**不在这里**，在 `../research/`；这里只放长文/叙事补充。

## 边界

- 本目录的文档不是 validator 校验对象（不同于 `../research/*.yaml`）；不得据此对外 overclaim——对外
  claim 仍必须能追溯到 `lab/research/evidence.yaml`。
- 私密/敏感来源材料：`reference/` 下的原始来源可能私密或有版权限制，不要默认可提交；只提交已脱敏的
  卡片与项目笔记。
