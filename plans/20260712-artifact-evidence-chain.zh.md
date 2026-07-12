# artifact → evidence → claim → deliverable 端到端完整性 交互式计划

> 这是 human 与 Claude Code 的协商界面：Claude 写初稿 → human 在文件里批注 → Claude 读 diff、
> 收敛计划 → 每次采纳的修订做一个小 commit。实现只在 scope / forbidden paths / verification
> 清楚后开始。

## 当前目标

为 `run → artifact(dataset/model/result/table/figure/trace) → evidence → claim →
deliverable` 建立**可机器检查**的 provenance 链，同时兼容外部 storage 与不同领域 artifact。

现状（已读代码确认）：
- 7 个产物类 index：`lab/artifacts/{result,table,figure,trace,model}-index.yaml`、
  `lab/models/checkpoint-index.yaml`、`lab/data/dataset-index.yaml`，字段各不相同
  （`storage_path` vs `source_path`，`supports` vs `supports_claim`，都没有 checksum 字段）。
- `lab/research/` 5 个 YAML（`claims.yaml`/`evidence.yaml`/`experiment-ledger.yaml`/
  `regression-matrix.yaml`/`release-gates.yaml`）已有 claim↔evidence 引用与 overclaim 校验
  （`scripts/validate-governance.py::check_evidence_chain`），以及 release-gate /
  regression-matrix 的枚举字段 + claim 引用校验（离开占位状态才校验）。
- **没有**：任何 checksum/存在性校验、artifact index 之间/与 experiment-ledger 的引用校验、
  release-gates.yaml 里 `requirements` 目前是纯自然语言字符串（不可执行）、deliverables
  正文里的 claim 没有可机器检查的 marker（只有 `deliverables/index.md` 表格手工登记
  「evidence 齐全」列）。
- `--strict` 模式下，若某检查函数因缺 PyYAML 而 `warnings.append(...)` 后 `return`，因为
  `ok = not n_e and not (strict and n_w)`，warning 会让 strict 失败——**当前实现已经不会
  静默通过**；本轮要保证新增的 checksum/manifest 相关检查延续这个模式，而不是引入新的
  "缺依赖就 return None/跳过且不计 warning" 路径。
- **触发面（已读配置确认，Codex 二审补充）**：`validate-governance.py` 是**纯 Python、
  runtime-neutral** 的门禁，触发点只有两处——(a) CI `.github/workflows/governance.yml`
  在每次 push/PR 上 `pip install pyyaml` 后跑 `python scripts/validate-governance.py --strict`；
  (b) 人/agent 手动 `python scripts/validate-governance.py`。它**不挂在任何 runtime 的
  PreToolUse/PostToolUse hook 上**：`.claude/settings.json` 与 `.codex/config.toml` 的
  hooks 只接 `pre_tool_guard.py` / `format_changed_python.py` / `zh_review_advisory.py` /
  continuity / identity 这几个 lifecycle 脚本，都不调用 validator。因此新的 provenance 校验
  只要落在 `validate-governance.py`（或它 `run_subcheck` 拉起的子脚本），Claude 与 Codex
  两侧就**自动等价触发**，无需在 `.codex/config.toml` 里重复挂钩、也不需要第二份实现。
- **adapter 漂移已被 CI 拦（已读 `check-agent-harness.py::check_codex_adapters` 确认）**：
  该子检查会 `subprocess` 跑 `sync-codex-adapters.py --check`，并由 `validate-governance.py`
  作为 subcheck 在 CI 里拉起。也就是说：一旦本轮改了 canonical `.claude/skills/artifact-indexing/`
  或 `.claude/commands/result-promote.md` 却忘记重跑 sync、把 `.agents/skills/**` 生成物一起
  提交，CI 会因「stale generated adapter」直接红。这条约束是硬的，不是软提醒。

本轮要交付：
1. 各类 index 的共同最小字段 schema（location/URI、inspection method、
   commit/config/run、status、checksum-或-无法校验原因）。
2. 引用链校验器：run→artifact→evidence→claim→deliverable 的引用完整性、状态、
   promotion 条件。
3. checksum / manifest：外部 URI、大 bytes 可以只登记 manifest + checksum，不要求进 Git；
   有本地 bytes 时真校验。
4. release gate 从纯自然语言 requirements 逐步长出「可执行」的一小部分（阈值/状态/布尔类），
   仍保留 human approval，不自动 flip `gate_status`。
5. deliverable claim marker：无法自动理解的正文要求显式 claim marker 或人工 review 证据。
6. 新校验一律区分「未检查 / 检查失败 / 通过」三态，不把 unknown 当 pass。

## 非目标

- **不做通用 LLM 自动审读整篇论文/deliverable 正文**（issue 明确排除）。第一版只用结构化
  claim marker + 引用 + 人工复核记录（落在 `human/reviews/results/`）。
- 不引入新的重型 artifact/对象存储基础设施；第一版基于现有 `lab/data/manifests/` +
  `lab/data/checksums/` 目录约定扩展到其余 index 类型，不新增服务或数据库。
- 不改变现有 human gate 语义：release / promote 仍需人工批准；validator 只能拦截「不该放行」，
  不能自动放行。
- 不删除/搬移任何 data / checkpoint / run bytes；沿用 `artifact-librarian` 边界，只做
  index / manifest / checksum 文件层面的读写与校验。
- 不要求这一轮把 `release-gates.yaml` 所有 requirement 都改成可执行检查；复杂的人类判断类
  要求继续留自然语言 + human approval，只把能结构化的部分（evidence grade 阈值、
  regression last_status、verified_by_fresh_reviewer 之类已有布尔/枚举字段的组合）迁移。
- 不产出新的实验结果或改变现有 claim/evidence 的判定；这是治理基础设施 issue，不是研究产出。

## Branch / worktree

- Branch: `feat/17-artifact-evidence-chain`
- Worktree: `.claude/worktrees/17-artifact-evidence-chain`

## Linked issue / PR

- Issue #17：`feat: 加强 artifact → evidence → claim → deliverable 端到端完整性`

## Allowed paths

- `lab/artifacts/*.yaml`（result/table/figure/trace/model index：新增共同字段）
- `lab/models/checkpoint-index.yaml`
- `lab/data/dataset-index.yaml`、`lab/data/manifests/`、`lab/data/checksums/`、
  `lab/data/schemas/`（扩展 manifest/checksum 约定到其余 artifact 类型时参考此处已有形态；
  只处理 manifest/checksum 文件本身，不碰数据 bytes）
- `lab/research/*.yaml`（`claims.yaml`/`evidence.yaml`/`experiment-ledger.yaml`/
  `regression-matrix.yaml`/`release-gates.yaml`：字段扩展、requirements 结构化字段）
- `deliverables/index.md`、`deliverables/*/README.md`（claim marker 约定说明；不改实际论文
  正文内容，只加最小语法示例）
- `scripts/validate-governance.py`、新增校验脚本（如
  `scripts/check-provenance-chain.py`，沿用「无第三方硬依赖、PyYAML 可选深检、可单独跑」惯例）
- 新增 fixture（正/负例）目录，路径待定——见「未解决问题」
- `.agent/artifact-policy.md`、`.agent/human-gates.md`（如需新增 provenance 相关条款）
- `lab/research/ANATOMY.md`、`lab/artifacts/ANATOMY.md`、`lab/data/ANATOMY.md`、
  `lab/models/ANATOMY.md`（若不存在需新建，遵循四件套要求）、root `ANATOMY.md`
- `.claude/skills/artifact-indexing/SKILL.md`、`.claude/commands/result-promote.md`
- `.github/workflows/governance.yml`（如需新增 job/step 跑新校验或 fixture）
- `DESIGN.md`（§6 证据链、§10 能力清单，若数量/机制变化）
- 改动 canonical `.claude/` 能力后跑 `python scripts/sync-codex-adapters.py`，同步
  `.codex/` / `.agents/` adapters。具体到本轮：改 `.claude/skills/artifact-indexing/SKILL.md`
  会重生成 `.agents/skills/artifact-indexing/SKILL.md`；改 `.claude/commands/result-promote.md`
  会重生成 `.agents/skills/command-result-promote/SKILL.md`（Codex 不加载 `.claude/commands/`，
  slash command 以「command-*」skill 形式适配）。这两份**生成物**允许写，但只能由 sync 脚本
  产出、不得手改，且必须与 canonical 同 commit 提交（否则 CI adapter 漂移检查红）。
- 本轮**新增/改动的 provenance 校验器不落在任何 runtime hook**（不改 `.codex/config.toml`
  的 PreToolUse/PostToolUse，也不改 `.claude/settings.json` hooks）——见「当前决策」。

## Forbidden paths

- `lab/data/**`、`lab/runs/**`、`lab/models/**` 权重 bytes、`checkpoints/**`、`wandb/**`、
  `lab/infra/private/**`、`.env` —— 不碰实际 bytes，只处理 index/manifest/checksum 文件。
- `deliverables/paper/`、`deliverables/slides/` 等正文的语义内容改写 —— 除新增 claim marker
  语法所需的最小示例外不编辑实际论文内容。
- 不修改 `release-gates.yaml`/`regression-matrix.yaml`/`claims.yaml` 里任何**已有真实
  （非模板占位）**条目的判定结果（`gate_status`/`last_status`/`status`）——本 issue 是加校验
  能力，不是改判定。
- `.claude/settings.json` 的 deny/hook 逻辑本身不在本轮改动范围内（若新校验需要新的权限边界，
  先在 plan 里标出、经 human 确认再动）。
- `.codex/config.toml` 的 hooks 段同样不在本轮改动范围。provenance 校验是 runtime-neutral 的
  纯 Python 门禁，走 CI + 手动调用，不需要（也不应该）把它塞进任一 runtime 的 PreToolUse/
  PostToolUse——否则要么只挂 Claude 侧导致 Codex 漏检，要么两侧各挂一份产生双实现。
- 不建远端 repo / 不开 PR / 不 merge / 不 release（沿用 `.agent/human-gates.md`）。

## 任务树

- [ ] 1. 共同最小字段 schema
  - [ ] 1.1 盘点 7 个 index + 5 个 research YAML 现有字段，列出差异表
        （`storage_path`/`source_path`/`storage_path`(model)/checkpoint `storage_path` 等命名不一致）
  - [ ] 1.2 定义共同最小字段集：`location`(统一 URI/路径字段名)、`how_to_inspect`、
        `commit`/`config`/`run_id` 三元组、`status`、`checksum`（值或「无法校验原因」枚举）
  - [ ] 1.3 更新各 index YAML 模板注释 + 示例占位行，体现新字段
  - [ ] 1.4 同步更新 `.agent/artifact-policy.md`、各 ANATOMY.md 里的字段描述
  - [ ] 1.5 更新 `artifact-indexing` skill 第 2 步的字段清单引用

- [ ] 2. 引用链校验器（run → artifact → evidence → claim → deliverable）
  - [ ] 2.1 校验 artifact index 条目的 `commit`/`config`/`run_id` 三元组非占位、`run_id` 在
        `experiment-ledger.yaml` 中存在
  - [ ] 2.2 校验「未闭环 run」：仅 `experiment-ledger` 中 `status: done` 且有
        `run_summary` 的 run 才允许被 evidence/artifact index 引用为来源
  - [ ] 2.3 校验 evidence → artifact index 交叉引用（`metric_source`/table/figure id 若指向
        `lab/artifacts/*-index.yaml` 条目，条目必须存在且未被 archived）
  - [ ] 2.4 校验 `deliverables/index.md` → `claims.yaml` 引用存在、且状态与「evidence 齐全」列一致
  - [ ] 2.5 输出三态：未检查（unknown，因缺依赖/无法定位）/ 检查失败（fail）/ 通过（pass），
        不把 unknown 计为 pass

- [ ] 3. checksum / manifest 支持
  - [ ] 3.1 定义各 artifact 类型的 manifest 格式（复用/扩展 `lab/data/manifests/` +
        `lab/data/checksums/` 已有约定）
  - [ ] 3.2 支持外部 URI：只要求 manifest + checksum 记录字段存在，不强制 bytes 进 Git
  - [ ] 3.3 checksum 校验器：本地 bytes 存在则真算 checksum 比对；远端/不可达时记录
        「无法校验 + 原因」而非静默 pass
  - [ ] 3.4 明确 checksum 算法与「无法校验原因」的允许枚举（见未解决问题）
  - [ ] 3.5 checksum 计算走 `hashlib` **在进程内完成**，不 shell-out 到 `sha256sum`/`md5sum`：
        (a) 保持 scripts/ 的「无第三方硬依赖、纯 Python、可单独跑」惯例；(b) 避免引入
        runtime 间的 Bash allowlist 差异（`.claude/settings.json` 虽 allow 了 `sha256sum`/
        `md5sum`，但 Codex 侧 execpolicy 未逐一核实，进程内 hash 直接绕开这一整块不确定性）。

- [ ] 4. release gate 可执行化
  - [ ] 4.1 在 `release-gates.yaml` 的 `requirements` 之外新增可选结构化字段（如
        `structured_checks: [{kind: evidence-grade-min, ...}, {kind: regression-status, ...}]`）
  - [ ] 4.2 validator 只校验结构化部分；非结构化 `requirements` 字符串继续留给人读
  - [ ] 4.3 校验通过/失败仅作为**建议信号**，`gate_status` 的 `open→passed/blocked` 翻转
        仍是 human 动作，不由 validator 自动写入
  - [ ] 4.4 `regression-matrix.yaml` 的 `last_status` 与 gate 结构化检查联动（gate 引用
        某 regression 时校验其 `last_status`）

- [ ] 5. deliverable claim marker 检查
  - [ ] 5.1 定义 claim marker 语法（候选：HTML 注释 `<!-- claim: claim-000 -->`，
        Markdown-only；需 human 确认是否要覆盖非 Markdown 交付物）
  - [ ] 5.2 校验：deliverable 正文中出现的 marker 引用的 claim 必须存在于 `claims.yaml`
  - [ ] 5.3 无法自动理解的正文段落（不可识别为 marker 覆盖）需在
        `deliverables/index.md` 或 `human/reviews/results/` 记录人工 review 证据，
        否则 evidence 齐全列不得为「是」

- [ ] 6. 正负向 fixture + CI 集成
  - [ ] 6.1 搭建 fixture（正例：完整闭环；负例：missing file / bad checksum / 悬空引用 /
        未闭环 run / 过强 claim / 未过 gate 各一个）
  - [ ] 6.2 fixture 存放位置与运行方式待 human 确认（见未解决问题）
  - [ ] 6.3 更新 `.github/workflows/governance.yml`，视需要新增 step 跑新校验/fixture
  - [ ] 6.4 复核 `--strict` 在缺 PyYAML 时不静默降级（新增检查延续现有 warning→strict-fail 模式）

- [ ] 7. 文档与治理面同步（same-commit）
  - [ ] 7.1 更新 `artifact-indexing` skill、`result-promote` command 引用新字段/新校验
  - [ ] 7.2 更新相关 ANATOMY.md（含新建 `lab/models/ANATOMY.md` 若当前缺失）
  - [ ] 7.3 更新 `DESIGN.md` §6（证据链描述）、§10（能力清单数量，若新增脚本/命令）
  - [ ] 7.4 结构改动同 commit 提交，过 `check-same-commit.py`
  - [ ] 7.5 若改了 `.claude/skills/artifact-indexing/` 或 `.claude/commands/result-promote.md`：
        重跑 `python scripts/sync-codex-adapters.py`，把生成的 `.agents/skills/artifact-indexing/SKILL.md`、
        `.agents/skills/command-result-promote/SKILL.md` 同 commit 提交；跑
        `python scripts/sync-codex-adapters.py --check` 与 `python scripts/check-agent-harness.py`
        确认无 stale/unexpected adapter。
  - [ ] 7.6 双 runtime 触发对等 smoke（能做多少做多少）：至少确认新 provenance 校验作为
        `validate-governance.py` 的 subcheck / 内联函数被 CI 与手动 `python scripts/validate-governance.py --strict`
        拉起，输出与调用它的 runtime 无关；若条件允许，在 Codex 侧手动跑一次同一命令核对退出码/
        输出一致（本二审无 Codex 一手环境，Codex 侧实跑留待 human/后续，见未解决问题）。

## Human 批注区

<!-- human 在这里直接写批注，Claude 会读 diff 收敛计划 -->

## 当前决策

- 沿用现有「7 个 artifact/data/model index + 5 个 research YAML」结构，扩展字段而非推翻重建。
- checksum/manifest 优先复用 `lab/data/manifests/` + `lab/data/checksums/` 已验证的目录约定，
  向其余 index 类型泛化，而非另起新格式。
- release gate 保持「human approval 触发 gate_status 翻转」不变；validator 只做建议信号。
- **provenance 校验落在 runtime-neutral 层（Codex 二审确立）**：新校验并入
  `validate-governance.py` 或其 `run_subcheck` 拉起的独立子脚本，触发只走 CI + 手动，
  **不挂 runtime hook**。这样 Claude 与 Codex 天然共享同一份实现与同一次触发，符合 issue
  「注意」段落要求（Codex 侧能触发同一份校验逻辑而不需要重复实现）。
- **checksum 用 `hashlib` 进程内计算**，不 shell-out，避免跨 runtime 的 Bash 权限差异
  与外部命令依赖。

## 未解决问题

1. **推进顺序**：是先给全部 7 个 index + 5 个 ledger 一次性加齐共同字段，还是先打通
   `result-index → evidence → claims → deliverables/index.md` 这条最短闭环，验证模式可行后
   再横向扩到 table/figure/trace/model/dataset/checkpoint？（倾向后者，但需要 human 拍板。）
2. **checksum 算法与「无法校验原因」枚举**：用 sha256 单一算法，还是允许按 artifact 类型
   选择（大文件流式 hash vs 小文件）？「无法校验原因」的合法值集合是什么（例如
   `external-storage-unreachable` / `too-large-to-hash-locally` / `pending-upload`），
   如何防止这个字段被滥用成「逃避校验」的借口？
3. **release gate 可执行化边界**：哪些 requirement 类型可结构化（阈值/状态/布尔组合），
   哪些必须保留自然语言 + human 判断？需要 human 给出一版「可结构化 requirement 分类」。
4. **claim marker 语法与覆盖范围**：HTML 注释 vs 独立 YAML 侧车文件 vs 其他；是否需要覆盖
   非 Markdown 交付物（如幻灯片、release notes）？
5. **新校验器落点**：并入 `validate-governance.py` 现有函数，还是拆成独立
   `scripts/check-provenance-chain.py` 再由 `validate-governance.py` 聚合调用（`scripts/`
   现有惯例是「可单独跑 + 无第三方硬依赖」，`check-same-commit.py` 是先例）？
   —— 二审补充：无论哪种，都必须由 `validate-governance.py`（CI 里跑的那个）拉起，才能保证
   Claude/Codex 触发对等；不要只在 CI workflow 里单加一个 step 而不接进 validator（那样手动
   `validate-governance.py` 会漏跑）。若拆独立脚本，还要确认它进 CI 的方式：靠
   `run_subcheck("check-provenance-chain.py", strict)`（推荐），而非只在 `governance.yml` 里
   平行加 step。
6. **fixture 测试框架**：仓库当前未见 `tests/`/`pytest` 测试目录（root 无 `pyproject.toml`，
   `lab/code/` 是否有独立测试环境未核实）。新增正负 fixture 应该：(a) 作为脚本内嵌 fixture
   yaml + 断言测试（类似当前 validator 无依赖风格），还是 (b) 引入 `pytest` 到 `lab/code/`
   下已有测试栈？需要 human 指明现有测试基础设施位置。
7. **schema 版本化**：是否给各 index yaml 加 `schema_version` 字段，便于未来
   `template-sync.py` 下游识别 schema 变更？

8. **Codex 侧手动调用权限（二审新增）**：若最终拆出独立 `scripts/check-provenance-chain.py`
   并希望它也能被人/agent 单独手动跑，需确认 Codex 的 execpolicy（`.codex/rules/default.rules`
   + `lab/infra/permissions/`，本二审未逐一读）是否放行 `python scripts/check-provenance-chain.py`。
   `.claude/settings.json` 侧已被 `Bash(python scripts/*)` 广义 allow 覆盖，Codex 侧待核。
   （作为 subcheck 由 `validate-governance.py` subprocess 拉起时无此问题——继承父进程权限。）

9. **claim marker 在 Codex 交付物工作流里的一致性（二审新增）**：claim marker 是写进
   `deliverables/**` 正文的纯文本约定 + 纯 Python 校验，本身 runtime-neutral。但生成/维护
   marker 的操作指引写在 `artifact-indexing` skill / `result-promote` command 里——这些经
   sync 适配成 Codex 的 `command-result-promote` skill 后，触发方式从 slash command 变成
   「按 skill 描述手动调用」。需 human 确认：是否要在 canonical 文档里显式提示「Codex 侧用
   command-result-promote skill 代替 /result-promote」，还是靠 adapter 生成的 note 已够。

10. **Codex 侧实跑验证（二审新增）**：本轮由 Claude Opus 4.8 代 Codex 二审，无 Codex 一手
    运行环境。任务 7.6 的「Codex 侧手动跑同一 validator 命令核对退出码/输出」需 human 或后续
    在真实 Codex runtime 里补做一次，作为双 runtime 对等的实证，而非仅凭静态推断。

## 验证标准

- [ ] 正常 fixture：可从 deliverable 反查到 claim、evidence、artifact、run、config、commit、
      data split（端到端反查脚本或校验通过即证明）。
- [ ] 负向 fixture 全部覆盖且被拦截：missing file、bad checksum、悬空引用、未闭环 run、
      过强 claim（overclaim）、未通过 gate。
- [ ] 外部 URI / 大 bytes 场景：只有 manifest + checksum 记录也能通过校验，不要求写入 Git。
- [ ] deliverable build/export 可重复产生相同 manifest（若本轮涉及 build/export 步骤）；
      release/promote 动作本身仍需 human 批准才生效。
- [ ] validator 输出明确区分「未检查」「检查失败」「通过」三态；unknown 不计为 pass。
- [ ] `python scripts/validate-governance.py --strict` 通过（含新校验），CI
      `.github/workflows/governance.yml` 绿。
- [ ] `python scripts/check-anatomy-drift.py`、`python scripts/check-agent-harness.py`、
      `python scripts/check-same-commit.py --staged` 均通过。
- [ ] `python scripts/sync-codex-adapters.py --check` 干净（无 missing/stale/unexpected
      adapter）；若改了 canonical skill/command，生成的 `.agents/skills/**` 已同 commit 提交。
- [ ] 新 provenance 校验确认由 `validate-governance.py` 拉起（CI 与手动同源），触发与 runtime
      无关；Codex 侧实跑核对留待 human/后续（见未解决问题 10），本轮以静态证据 + CI 绿为准。
- [ ] `artifact-indexing`、`result-promote`、`release-gate` 相关文档与 ANATOMY 同步更新，
      DESIGN.md §6/§10 与实际一致。

## 下一步

等待 human 在本文件批注（尤其是「未解决问题」7 条），Claude 读 diff 收敛任务树的推进顺序与
schema/marker 语法细节，再落地小步 commit（每个采纳的修订一个 commit，仍需 human 批准）。

## Plan revision log

- 2026-07-12 初稿
- 2026-07-12 二审修订（Claude Opus 4.8 代替额度耗尽的 Codex gpt-5.6-sol 二审）：补 Codex 侧
  触发对等分析（validator 为 runtime-neutral 纯 Python，走 CI + 手动，不挂 runtime hook）、
  adapter 漂移 CI 强约束、checksum 走 hashlib 免 Bash 权限差异、Codex adapter 重生成任务与
  验证项，新增 open questions 8–10（Codex 手动调用权限 / claim marker 在 Codex 工作流一致性 /
  Codex 侧实跑验证待补）。人类最终批准仍待定。
