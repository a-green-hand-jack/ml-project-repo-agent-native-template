---
contract_for:
  - component: template-sync
    anatomy: scripts/ANATOMY.md
---
# template-versioning-policy — 模板版本与上下游同步契约

> 这个模板会被多个下游 ml-research-project 采用。下游在使用中发现缺口 → 上报成本 repo 的 issue
> → 在本 repo 解决并发版 → 下游同步追平。这份 doctrine 定义「版本怎么判级」与「四站闭环」。

## 四站闭环

```
①发现缺口  →  ②登记成 issue  →  ③本 repo 解决(issue→PR→merge, 版本+1)  →  ④sync 回各下游
      ↑________________________________________________________________________|
                   每个下游 .template.toml 记着自己追到哪个版本
```

### ② 有两个入口（源头不同，都汇到 ③④）

- **②a 下游源（downstream → template）**：某个下游项目在使用中发现缺口。下游跑
  `template-feedback` skill，自动带上 `.template.toml` 的版本 + 涉及的框架层路径 + 场景/期望/复现，
  `gh issue create --repo <origin> --label from-downstream`。见
  `.claude/skills/template-feedback/SKILL.md`。
- **②b 模板源（template → template）**：直接在本 template repo 开发/试用时发现要改的东西——源头就是
  模板自己，不存在「下游上报」。**不要用 `template-feedback` skill**（它是下游专用），直接在本 repo
  建 issue（可打 `template-native` 标签区分）或直接进入 ③。判级与发版流程与 ②a 完全一致。

无论哪个入口，③（判级+发版）与 ④（sync 到所有下游）都一样——闭环的下半段是共用的。
- **③ 解决 + 发版**：正常 issue→PR→merge。合并影响**框架层**的 PR 后，agent 判级并跑
  `python scripts/bump-template-version.py --level <major|minor|patch>` 写 `VERSION` + 打 git tag。
- **④ 同步**：下游跑 `python scripts/template-sync.py`，按 `template-manifest.toml` 只覆盖框架层、
  保护项目层与下游私货，跑生成器 + `validate-governance.py` 验收，写回新版本。见 `scripts/ANATOMY.md`。

## semver 判级（agent 可判定的合同）

版本号 `vMAJOR.MINOR.PATCH`。语义**以「对下游 sync 的影响」为准**，不是代码行数：

| 级别 | 含义（对下游的影响） | 典型改动 |
| --- | --- | --- |
| **MAJOR** `vX.0.0` | 破坏性：sync **无法全自动**，下游必须人工 reconcile | manifest 路径分类变更、doctrine 文件重构/改名、hook/validator 契约变更、混合文件哨兵结构变、删除或重命名框架层能力 |
| **MINOR** `v_.Y.0` | 向后兼容的新能力：sync 干净落地，下游净得能力 | 新增 agent/skill/command/hook/validator、doctrine 增补一节、新增受管路径 |
| **PATCH** `v_._.Z` | 修复/微调：全自动可同步，无新表面 | hook/validator/script 的 bugfix、文案订正、无新增能力的内部重写 |

### 判级流程（agent）

1. 看已合并进本次发布的改动集 + 关联 issue + human 批注。
2. 按上表取**最高**适用级别（一次发布若同时含新能力与破坏性变更，取 MAJOR）。
3. **human 批注可覆盖**：若 human 在 issue/PR 注明期望级别，以 human 为准。
4. 跑 `bump-template-version.py --level <lvl>`，它写 `VERSION`、更 `CHANGELOG.md`、打 tag `vX.Y.Z`。

## human gate（见 `.agent/human-gates.md`）

- 打 tag 是本地 git 写操作，允许；**push tag / 建 release 需 human 批准**。
- 下游 sync 时：PATCH/MINOR 可自动落地 + validator 验收；**MAJOR 强制停下让 human 确认**
  （定义上就需要人工 reconcile）。`template-sync.py` 遇 MAJOR 跨越默认拒绝，除非 `--allow-major`。

## 混合文件的哨兵约定（merge kind）

`AGENTS.md` / `ANATOMY.md` / `CLAUDE.md` 这类导航文件，模板骨架与项目内容缠在一起，
既不能整体覆盖（会冲掉下游填的内容）也不能不同步（骨架更新传不下去）。用哨兵块切开：

```
# <标题>                      ← H1，块外
（frontmatter 若有，在 H1 之上，块外）
<!-- template:begin -->
… 模板拥有的骨架/doctrine（sync 只替换这一段）…
<!-- template:end -->

<!-- 项目自定义区（块外，sync 不碰）：下游在此追加项目特定内容 -->
```

- `template-sync.py` 对 merge 文件**只替换 begin/end 之间**；块外的自定义区与 frontmatter 原样保留。
- 下游**不要改块内**——要改模板骨架走 ②（上报 issue）。项目特定内容一律写块外自定义区。
- `validate-governance.py` 的 `check_merge_sentinels()` 强制每个 merge 文件都有成对哨兵，缺了即 FAIL
  （否则该文件会被 sync 整体跳过、静默漂移）。
- **已知边界**：frontmatter 在块外，不随 sync 更新（哨兵不能放 frontmatter 前，否则破坏 `^---` 解析）。
  frontmatter 的结构性变更需人工同步或把该文件改判为 framework。

## 什么算「框架层」

只有框架层变更才触发发版与 sync。分类的**唯一真源**是 `template-manifest.toml`。粗略地：
框架层 = `.agent/`、`.claude/{agents,skills,commands,hooks,settings}`、`scripts/` validator、
`.githooks/`、`.github/` CI/模板、以及混合文件里的 `template:` 哨兵块。项目层 =
`lab/`、`memory/`、`deliverables/`、`plans/`、`human/`、`PROJECT.md`、`DECISIONS.md`。

## template-sync 可观察 Contract（本节是规范 owner，见 issue #33）

本节是 `scripts/template-sync.py`（④ 同步站）可观察行为的**唯一规范正文 owner**。
`scripts/ANATOMY.md` 的 `template-sync.py` 行只反向链接本节，不复制规则正文；
`scripts/README.md` / `lab/evals/template-sync/README.md` 只描述运行入口与命令，不重写下列规则。
反向链接：implementation `scripts/template-sync.py`；分类真源 `template-manifest.toml`；
production-path fault-injection evidence `lab/evals/template-sync/run-template-sync-smoke.py`
（`python3 lab/evals/template-sync/run-template-sync-smoke.py`，复制真实脚本驱动，非 fake/parser-only）。

规则 id 稳定、粗粒度（不拆成微规则）；每条给出 evidence kind 与具体 scenario/function，
不接受「见测试文件」这类无具体指向的引用。

| id | 规则（可观察义务） | evidence kind | evidence |
| --- | --- | --- | --- |
| **TS-1** source-input | 每次 sync 的 `source` 必含 sha256 `content_digest`；上游若是 git 仓库，额外记录 40 位 HEAD SHA 与如实的 `dirty` 标记，且被同步的是当前工作树（含未提交改动）字节，不是「假装 clean 的 SHA」 | production-path positive | `check_dirty_upstream_source`（git+dirty 分支）、`check_happy_and_idempotent`（`source.content_digest` 断言，非 git 分支） |
| **TS-2** major-gate | MAJOR 跨越且无 `--allow-major` 是严格 pre-write no-op：exit 2、版本不动、不写任何文件、不写 receipt；带 `--allow-major` 才推进 | production-path positive + forbidden | `check_major_gate`（阻断分支断言零写入/无 receipt；放行分支断言推进） |
| **TS-3** five-path-classes | 五类 ownership：framework 仅在字节不同才覆盖（相同则不重写）；project 永不触碰；scaffold 缺失才建、已存在则保留；generated 在 apply 阶段绝不裸拷贝，只由下游生成器重建；merge 文件只替换 `template:begin/end` 哨兵块内，块外内容保留 | production-path positive + forbidden | `check_happy_and_idempotent` 的五类正/负断言段 |
| **TS-4** dry-run-shares-plan | `--dry-run` 与 `apply` 走同一条 `plan_sync()`/classify 路径计算计划，不存在会漂移的第二套「预览」实现；`receipt.manifest.expected` 必须等于同一 fixture 下真实 apply 会写入的路径集；dry-run 全程零下游 side effect（不跑生成器/validator、不推进版本、不改任何被同步文件），唯一例外是显式 `--receipt PATH` 时只写这一个文件 | production-path positive + forbidden | `check_dry_run_no_side_effect`（真实 CLI 端到端：断言 planned 路径集与 `check_happy_and_idempotent` 里同一 fixture 的真实 apply 写入集一致、exit 0、零文件/生成器/版本副作用、仅显式 receipt 路径被写出） |
| **TS-5** generated-full-set | 上报的 `generated` manifest（`expected`/`actual`/`actual_changed`/`missing`/`unexpected`/`content_mismatches`）是**完整 post-generator 下游快照**的分类结果，不是本次生成器 delta；路径存在但字节错 → `content_mismatches`，永不算 `missing`；运行前已存在、本次生成器未触碰的 rogue 文件仍算 `unexpected` | production-path positive + forbidden | `check_generated_missing`、`check_generated_wrong_bytes_content_mismatch`、`check_generated_arbitrary_unexpected`、`check_generated_stale_rogue_unexpected` |
| **TS-6** validate-before-commit | 阶段固定顺序 apply → generated_rebuild → validate → commit_version；仅当前面全部 `ok` 时 `commit_version` 才可能 `ok`；生成器/validator 失败或 `--no-verify` 跳过时版本必须保持旧值，`commit_version` 为 `skipped` 或非 `ok` | production-path positive + forbidden | `check_generator_fail`、`check_validator_fail`、`check_no_verify_no_advance` |
| **TS-7** receipt-result-states | apply-run（非 `--dry-run`）的 receipt `result` 只有四态：`pass`（全部阶段 ok 且无 warning）、`partial`（某阶段失败/跳过，或 validator 通过但有 warning——未分类路径/无哨兵 merge 文件）、`unknown`（超时/中断等不确定结果，永不显示为 `pass`）——`fail` 与 `unknown` 均不得被误记为 `pass`；`--dry-run` 是独立的第五态 `result="dry-run"`，与前述四态互斥、不参与 pass/partial/fail/unknown 判定 | production-path positive | `check_happy_and_idempotent`（pass）、`check_warnings_partial`（validator 通过但 partial）、`check_generator_fail`/`check_validator_fail`（阶段失败 partial）、`check_timeout_unknown`/`check_interrupt_unknown`/`check_commit_interrupt`（unknown）、`check_dry_run_no_side_effect`（dry-run） |
| **TS-8** atomic-commit-and-interrupt-honesty | 版本文件用「同目录临时文件 + `os.replace`」写入；替换前失败/中断保持旧值、无孤儿临时文件、旧值仍可解析；替换后中断必须如实报告 `version_advanced=true` 且 `result=unknown`，不得声称 `version_kept`/伪造 rollback | production-path positive + forbidden | `check_atomic_write_fail`、`check_commit_interrupt`（before/after 两支） |
| **TS-9** idempotent-rerun | 对已追平的下游立即重跑是真正 no-op：`result` 仍 `pass`、版本不动、`apply_changed` 为空 | production-path positive | `check_happy_and_idempotent` 的幂等重跑段 |

### template-sync Contract 变更矩阵（breaking vs non-breaking）

沿用上方 semver 判级表，针对本节规则细化：

| 变更 | 判级 | 说明 |
| --- | --- | --- |
| 弱化/删除 TS-1..TS-9 任一规则（如允许版本在 validator 成功前推进、允许 generated 裸拷贝、放宽 MAJOR gate、伪造 rollback） | **MAJOR** | 默认视为实现 bug，不得为让测试变绿而改弱本节；改变承诺需 human 在 issue/PR 明确批注批准 |
| receipt schema 增字段（向后兼容，既有字段语义不变） | MINOR | 下游读取代码通常无需改造 |
| receipt schema 删除/重命名既有字段、`result` 枚举增删值 | **MAJOR** | 下游解析 receipt 的代码可能失败 |
| 五类 ownership 语义变化（如 scaffold 改为总是覆盖、merge 哨兵约定改变） | **MAJOR** | 直接影响下游文件的实际落地结果 |
| CLI/manifest 输入收紧（新增必填参数、manifest 新增必填字段） | **MAJOR** | 下游需人工改造调用方式 |
| CLI/manifest 输入放宽（新增可选参数、manifest 新增可选 kind） | MINOR | 向后兼容 |
| 文案/内部重构、无表面行为变化的 bugfix | PATCH | — |
| 变更本节「唯一规范正文 owner」指定，或改变 truth direction（哪份文件是规范、哪份只做链接） | **MAJOR** | 需按 `.agent/human-gates.md` 走 human 批准路径，只引用该 doctrine，不复制其内容 |

发现实现偏离本节任一规则：默认判定为 correctness bug，走 `.agent/human-gates.md` 另开 bug issue 修复
production 实现；不得反向弱化本节规则去匹配当前实现的意外行为。
