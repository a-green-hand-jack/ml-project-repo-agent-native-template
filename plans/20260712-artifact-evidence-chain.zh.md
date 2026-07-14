# artifact → evidence → claim → deliverable 端到端完整性 交互式计划

Status: verified · 2026-07-13 · fresh APPROVE 52f83aa；本地 merge 405c542；strict provenance/integration gates 全绿

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
  落在独立脚本 `scripts/check-provenance-chain.py`（已决策，见「当前决策」），由
  `validate-governance.py` 通过 `run_subcheck` 拉起，Claude 与 Codex 两侧就**自动等价触发**，
  无需在 `.codex/config.toml` 里重复挂钩、也不需要第二份实现。
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

以上 6 项功能范围不变；落地顺序按「任务树」顶部「执行顺序（决策 1）」分 Phase A（最短闭环
result-index→evidence→claims→deliverables/index.md）/ Phase B（横向扩展）两阶段推进，不是
一次性铺开（human 选择题拍板，2026-07-12）。

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

> 以下为终态允许路径全集；落地依「任务树」Phase A/B 顺序分批 touch，不代表第一批改动就要
> 碰完这里列出的所有文件（决策 1，human 选择题拍板 2026-07-12）。

- `lab/artifacts/*.yaml`（result/table/figure/trace/model index：新增共同字段）
- `lab/models/checkpoint-index.yaml`
- `lab/data/dataset-index.yaml`、`lab/data/manifests/`、`lab/data/checksums/`、
  `lab/data/schemas/`（扩展 manifest/checksum 约定到其余 artifact 类型时参考此处已有形态；
  只处理 manifest/checksum 文件本身，不碰数据 bytes）
- `lab/research/*.yaml`（`claims.yaml`/`evidence.yaml`/`experiment-ledger.yaml`/
  `regression-matrix.yaml`/`release-gates.yaml`：字段扩展、requirements 结构化字段）
- `deliverables/index.md`、`deliverables/*/README.md`（claim marker 约定说明；不改实际论文
  正文内容，只加最小语法示例）
- `scripts/validate-governance.py`（新增 `run_subcheck` 调用点）、新建独立脚本
  `scripts/check-provenance-chain.py`（已决策，仿 `scripts/check-same-commit.py` 先例，沿用
  「无第三方硬依赖、PyYAML 可选深检、可单独跑」惯例）
- fixture 正负例（已决策，决策 5，human 选择题拍板 2026-07-12）：内嵌在
  `scripts/check-provenance-chain.py`（或该脚本同目录的私有辅助模块，如需要拆分可加
  `scripts/_provenance_fixtures.py`）以 Python 数据结构/临时文件形式构造，不新建 `tests/`
  目录、不引入 pytest
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
- `.codex/rules/default.rules`（为新建的独立脚本 `scripts/check-provenance-chain.py` 补精确的
  `python scripts/check-provenance-chain.py` allow 规则；不扩大为 `python scripts/*`）。
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

### 执行顺序（决策 1，human 选择题拍板，2026-07-12）

不要一次性给全部 7 个 index + 5 个 research YAML 加齐字段/校验。分两阶段推进，Phase A
必须先跑通并通过验证标准里的「最短闭环」条目，才进入 Phase B：

- **Phase A —— 最短闭环**：只打通 `result-index.yaml → evidence.yaml → claims.yaml →
  deliverables/index.md`（含使闭环成立所必需的 `experiment-ledger.yaml` run 状态校验）。
  下面每条任务前的 `[Phase A]` 标签标出属于这一阶段的部分。
- **Phase B —— 横向扩展**：Phase A 验证通过后，把同一套 schema 字段、checksum/manifest、
  引用校验、fixture 覆盖，推广到 table/figure/trace/model index、dataset-index、
  checkpoint-index，以及 release-gates.yaml / regression-matrix.yaml（release gate 本身
  依赖 regression-matrix，不在「result→evidence→claims→deliverable」最短链路内，整体归入
  Phase B）。`[Phase B]` 标签标出的部分复用 Phase A 写好的同一份 `check-provenance-chain.py`
  逻辑（用 index 类型/字段做覆盖范围扩展，不是另起一套实现）。

- [ ] 1. 共同最小字段 schema
  - [ ] 1.1 [Phase A，一次性做完供两阶段共用] 盘点 7 个 index + 5 个 research YAML 现有
        字段，列出差异表（`storage_path`/`source_path`/`storage_path`(model)/checkpoint
        `storage_path` 等命名不一致）
  - [ ] 1.2 [Phase A，字段定义一次性做完，应用分阶段] 定义共同最小字段集：
        `location`(统一 URI/路径字段名)、`how_to_inspect`、`commit`/`config`/`run_id`
        三元组、`status`、`schema_version`(新增，决策 6)、checksum 三件套（决策 2）：
        - `checksum`：值（算法固定为 sha256，见任务 3.0/决策 8）
        - `checksum_algorithm`：固定取值 `sha256`（唯一取值，不按 artifact 类型/大小分流，
          已决策，决策 8）
        - `checksum_unavailable_reason`：**固定枚举**（无自由文本原因），取值：
          - `external-uri-no-checksum`：外部托管资源，未产出/未提供 checksum
          - `pending-upload`：bytes 尚未落地/上传，条目先行占位登记
          - `legacy-untracked`：历史遗留条目（迁移前创建），尚未回填 checksum
          - `oversized-defer-hash`：文件过大，暂不具备本地算 hash 条件（需在理由字段写明
            后续计划）
        - `checksum_unavailable_justification`：**人工必填**理由文本，非空、非占位符
          （如单纯写 "TBD"/"N/A" 判定无效），需写明具体情境。`reason` 枚举 +
          `justification` 必填理由**两者都要**，防止该字段被滥用成校验逃逸口——validator
          遇到 reason 不在枚举内，或 justification 为空/占位，一律判 **fail**（不是
          unknown，因为这是「该填而未填对」，不是「无法检查」）
  - [ ] 1.3 [Phase A] 更新 `lab/artifacts/result-index.yaml`、`lab/research/claims.yaml`、
        `lab/research/evidence.yaml`、`lab/research/experiment-ledger.yaml`、
        `deliverables/index.md` 的模板注释 + 示例占位行，落地新字段（含 `schema_version`）
  - [ ] 1.4 [Phase B] 推广到 `lab/artifacts/{table,figure,trace,model}-index.yaml`、
        `lab/data/dataset-index.yaml`、`lab/models/checkpoint-index.yaml`、
        `lab/research/regression-matrix.yaml`、`lab/research/release-gates.yaml`
  - [ ] 1.5 [Phase A] 同步更新 `.agent/artifact-policy.md`、`lab/research/ANATOMY.md` 里
        Phase A 触及字段的描述
  - [ ] 1.6 [Phase B] 同步更新 `lab/artifacts/ANATOMY.md`、`lab/data/ANATOMY.md`、
        `lab/models/ANATOMY.md`（若不存在需新建，遵循四件套要求）
  - [ ] 1.7 [Phase A 先，Phase B 补充] 更新 `artifact-indexing` skill 第 2 步的字段清单
        引用：Phase A 完成时先反映最短闭环适用字段，Phase B 完成后补齐其余 index 类型说明

- [ ] 2. 引用链校验器（run → artifact → evidence → claim → deliverable）
  - [ ] 2.0 校验器实现落在新建独立脚本 `scripts/check-provenance-chain.py`（已决策，仿
        `scripts/check-same-commit.py` 先例），由 `validate-governance.py` 通过
        `run_subcheck` 拉起；不写进 `validate-governance.py` 现有函数体内。Phase A/B 共用
        同一脚本，用参数/index 类型白名单区分覆盖范围，不建两份实现
  - [ ] 2.1 [Phase A] 校验 `result-index.yaml` 条目的 `commit`/`config`/`run_id` 三元组
        非占位、`run_id` 在 `experiment-ledger.yaml` 中存在（Phase B 时同一函数扩展到其余
        6 类 index）
  - [ ] 2.2 [Phase A] 校验「未闭环 run」：仅 `experiment-ledger` 中 `status: done` 且有
        `run_summary` 的 run 才允许被 evidence/result-index 引用为来源（Phase B 扩展到其余
        artifact 类型引用 run 的场景）
  - [ ] 2.3 校验 evidence → artifact index 交叉引用（`metric_source`/table/figure id 若指向
        `lab/artifacts/*-index.yaml` 条目，条目必须存在且未被 archived）：**[Phase A]**
        先只处理 evidence 引用 `result-index` 的情况；**[Phase B]** 同一份逻辑扩展覆盖
        table/figure/trace/model/dataset/checkpoint index
  - [ ] 2.4 [Phase A] 校验 `deliverables/index.md` → `claims.yaml` 引用存在、且状态与
        「evidence 齐全」列一致（最短闭环终点）
  - [ ] 2.5 输出三态：未检查（unknown，因缺依赖/无法定位）/ 检查失败（fail）/ 通过（pass），
        不把 unknown 计为 pass（Phase A/B 通用规则）

- [ ] 3. checksum / manifest 支持
  - [ ] 3.0 [Phase A 前置，已决策，决策 8，human 拍板 2026-07-12] checksum 算法**统一用
        sha256**，不按 artifact 类型/大小分流选择流式算法。落地前仍需先 Read 确认
        `lab/data/checksums/` 目录现有条目实际使用的算法：若已是 sha256，直接复用确认；
        若发现与 sha256 冲突的既有约定（例如历史条目用 md5/sha1 或其他算法），视为需要
        另行处理的迁移问题——在实现 PR 里标注冲突范围并升级给 human 拍板具体迁移方式
        （就地重算 / 保留旧值加 legacy 标记 / 分批迁移等），不得自行决定绕开「统一
        sha256」这一设计目标。见「未解决问题」条目 8（已决策）
  - [ ] 3.1 [Phase A，先覆盖 result artifact；Phase B 推广] 定义各 artifact 类型的 manifest
        格式（复用/扩展 `lab/data/manifests/` + `lab/data/checksums/` 已有约定）
  - [ ] 3.2 [Phase A 先覆盖 result artifact；Phase B 推广其余类型] 支持外部 URI：只要求
        manifest + checksum 记录字段存在，不强制 bytes 进 Git
  - [ ] 3.3 [Phase A 先覆盖 result artifact；Phase B 推广其余类型] checksum 校验器：本地
        bytes 存在则真算 checksum 比对；远端/不可达时按 1.2 的枚举 + 必填理由记录，不静默
        pass
  - [ ] 3.4 [Phase A] 具体枚举值与字段设计见任务 1.2（已决策，决策 2）；`checksum_algorithm`
        固定取值 `sha256` 见任务 3.0（已决策，决策 8）
  - [ ] 3.5 [Phase A/B 通用] checksum 计算走 `hashlib` **在进程内完成**，不 shell-out 到
        `sha256sum`/`md5sum`：(a) 保持 scripts/ 的「无第三方硬依赖、纯 Python、可单独跑」
        惯例；(b) 避免引入 runtime 间的 Bash allowlist 差异；进程内 hash 也减少外部命令与
        平台差异。

- [ ] 4. release gate 可执行化 [Phase B 全部——release gate 依赖 regression-matrix，不在
      「result→evidence→claims→deliverable」最短闭环内]
  - [ ] 4.1 在 `release-gates.yaml` 的 `requirements` 之外新增可选结构化字段
        `structured_checks: [{kind: ..., ...}]`。**结构化边界（已决策，决策 3）**：只覆盖
        「可客观机械验证」的类型——`artifact-exists`（文件/manifest 存在性）、
        `checksum-verified`（checksum 状态为已校验通过）、`run-closed`（引用的 run 在
        experiment-ledger 中 `status: done`）、`regression-status`（引用的
        regression-matrix 条目 `last_status` 命中期望值）、`evidence-grade-min`（evidence
        已有的 grade 枚举字段达到阈值）。涉及「结果够不够好」这类价值判断的 requirement
        （例如「审稿人认为叙述充分」）**继续留自然语言 + human approval**，不强行伪结构化
  - [ ] 4.2 validator 只校验结构化部分；非结构化 `requirements` 字符串继续留给人读
  - [ ] 4.3 校验通过/失败仅作为**建议信号**，`gate_status` 的 `open→passed/blocked` 翻转
        仍是 human 动作，不由 validator 自动写入
  - [ ] 4.4 `regression-matrix.yaml` 的 `last_status` 与 gate 结构化检查联动（gate 引用
        某 regression 时校验其 `last_status`）

- [ ] 5. deliverable claim marker 检查 [Phase A —— 最短闭环终点]
  - [ ] 5.1 claim marker 语法（**已决策，决策 4，human 拍板 2026-07-12**）：HTML 注释
        标记，不用侧车 YAML 文件。具体语法：
        `<!-- claim: id=<claim-id> [evidence=<evidence-id>[,<evidence-id>...]] -->`
        - `id=` 必填，引用 `claims.yaml` 中已存在的 claim id
        - `evidence=` 可选，逗号分隔的 evidence id 列表；若填写，每个 id 须存在于
          `evidence.yaml`
        - 覆盖范围：这是语法选择的自然推论（不是本轮单独决策的新问题）——HTML 注释只能
          嵌入文本类正文，因此只覆盖 Markdown 交付物（`deliverables/index.md`、
          `deliverables/*/README.md` 等 `.md` 文件）。非 Markdown 交付物（幻灯片、二进制
          格式）无法嵌入 HTML 注释，走 5.3 的「人工 review 证据」路径兜底，不强行覆盖
  - [ ] 5.2 校验：deliverable 正文中出现的 marker，其 `id`（及可选 `evidence`）引用必须
        存在于对应 YAML
  - [ ] 5.3 无法自动理解的正文段落（不可识别为 marker 覆盖）需在
        `deliverables/index.md` 或 `human/reviews/results/` 记录人工 review 证据，
        否则 evidence 齐全列不得为「是」

- [ ] 6. 正负向 fixture + CI 集成
  - [ ] 6.1 [Phase A] 搭建最短闭环的正负例（正例：result→evidence→claim→deliverable
        完整闭环；负例：missing file / bad checksum / 悬空引用 / 未闭环 run / 过强
        claim，本阶段能在最短闭环内构造的部分）
  - [ ] 6.1b [Phase B] 补齐 table/figure/trace/model/dataset/checkpoint 各类型负例，以及
        release gate 结构化校验负例（未过 gate）
  - [ ] 6.2 fixture 存放位置与运行方式（**已决策，决策 5，human 拍板 2026-07-12**）：跟随
        现有风格——脚本内嵌 fixture 数据 + 无第三方依赖的断言测试（例如在
        `check-provenance-chain.py` 内提供 `_selftest()`/`--selftest` 入口，用 Python
        数据结构或临时文件构造正负例并断言），**不新开 `tests/` 目录、不引入 pytest**
  - [ ] 6.3 更新 `.github/workflows/governance.yml`：[Phase A] 先接入最短闭环校验；
        [Phase B] 若有新增校验点再补 step，但优先复用同一份 `check-provenance-chain.py`
        调用，不因为 Phase B 另开新 workflow job
  - [ ] 6.4 [Phase A/B 通用] 复核 `--strict` 在缺 PyYAML 时不静默降级（新增检查延续现有
        warning→strict-fail 模式）
  - [ ] 6.5 [Phase A] 新建独立脚本 `scripts/check-provenance-chain.py` 后，同步在
        `.codex/rules/default.rules` 增加精确 allow；用 `codex execpolicy check --pretty --rules
        .codex/rules/default.rules -- python scripts/check-provenance-chain.py` 验证命中 `allow`

- [ ] 7. 文档与治理面同步（same-commit）
  - [ ] 7.1 [Phase A 先，Phase B 补充] 更新 `artifact-indexing` skill、`result-promote`
        command：Phase A 先反映最短闭环新字段/新校验，Phase B 补齐其余 index 类型说明
  - [ ] 7.2 [Phase A] 更新 `lab/research/ANATOMY.md`（Phase A 涉及的 4 个 research
        YAML）；[Phase B] 更新 `lab/artifacts/ANATOMY.md`、`lab/data/ANATOMY.md`、
        `lab/models/ANATOMY.md`（含新建 `lab/models/ANATOMY.md` 若当前缺失）
  - [ ] 7.3 更新 `DESIGN.md` §6（证据链描述）、§10（能力清单数量，若新增脚本/命令）：
        [Phase A] 完成时先更新一版反映最短闭环状态，[Phase B] 完成后再更新一次覆盖范围/数量
  - [ ] 7.4 结构改动同 commit 提交，过 `check-same-commit.py`（Phase A/B 各自独立检查）
  - [ ] 7.5 [Phase A，若已改 skill/command 就需要] 重跑
        `python scripts/sync-codex-adapters.py`，把生成的
        `.agents/skills/artifact-indexing/SKILL.md`、
        `.agents/skills/command-result-promote/SKILL.md` 同 commit 提交；跑
        `python scripts/sync-codex-adapters.py --check` 与
        `python scripts/check-agent-harness.py` 确认无 stale/unexpected adapter。
  - [ ] 7.6 双 runtime 触发对等 smoke（能做多少做多少）：[Phase A 完成后先做一次] 至少确认
        新 provenance 校验作为 `validate-governance.py` 的 subcheck / 内联函数被 CI 与手动
        `python scripts/validate-governance.py --strict` 拉起，输出与调用它的 runtime 无关；
        实现完成后在 Codex 侧再手动跑同一命令，核对新增 provenance 子检查确实出现在输出
        中。当前真实 Codex session 已证明现有 strict validator 可直接运行并以 exit 0、
        0 error / 0 warning 结束，但尚无新增脚本可验证。[Phase B 完成后建议再复测一次，
        非强制]

## Human 批注区

<!-- human 在这里直接写批注，Claude 会读 diff 收敛计划 -->

## 当前决策

- 沿用现有「7 个 artifact/data/model index + 5 个 research YAML」结构，扩展字段而非推翻重建。
- checksum/manifest 优先复用 `lab/data/manifests/` + `lab/data/checksums/` 已验证的目录约定，
  向其余 index 类型泛化，而非另起新格式。
- release gate 保持「human approval 触发 gate_status 翻转」不变；validator 只做建议信号。
- **provenance 校验落在 runtime-neutral 层（Codex 二审确立）**：新校验落在
  `scripts/check-provenance-chain.py`（独立脚本，见下一条决策），由 `validate-governance.py`
  通过 `run_subcheck` 拉起，触发只走 CI + 手动，**不挂 runtime hook**。这样 Claude 与 Codex
  天然共享同一份实现与同一次触发，符合 issue 「注意」段落要求（Codex 侧能触发同一份校验逻辑
  而不需要重复实现）。
- **新校验器落点：独立脚本（human 拍板，2026-07-12，已终局，不再是 open question）**：
  `scripts/check-provenance-chain.py`，仿 `scripts/check-same-commit.py` 先例——`scripts/`
  现有惯例是「可单独跑 + 无第三方硬依赖」，独立脚本便于单元测试、复用，且不无限膨胀
  `validate-governance.py` 单文件体积。硬约束：必须由 `validate-governance.py` 通过
  `run_subcheck("check-provenance-chain.py", strict)`（或等价机制）拉起，不能只在
  `.github/workflows/governance.yml` 里平行加 step——否则手动执行
  `python scripts/validate-governance.py --strict` 会漏跑该子检查，破坏 Claude/Codex 触发对等。
- **checksum 用 `hashlib` 进程内计算**，不 shell-out，避免跨 runtime 的 Bash 权限差异
  与外部命令依赖。
- **Codex 手动执行基线已实测**：本轮真实 Codex session 直接运行
  `python scripts/validate-governance.py --strict`，结果为 exit 0、0 error / 0 warning；其
  execpolicy 精确命中现有 validator 的 `allow` 规则。直接运行未被规则列出的现有
  `python scripts/check-same-commit.py --help` 也能执行，但 `codex execpolicy check` 对假定的
  `python scripts/check-provenance-chain.py` 返回 `matchedRules: []`、无 `allow` decision，故不能
  把「当前 session 可执行未列出脚本」误写成该新脚本已被 execpolicy 明确放行；落地时按任务 6.5
  补精确规则并复测。
- **Codex promote 入口说明已足够明确**：生成的
  `.agents/skills/command-result-promote/SKILL.md` 已明文说明 Codex 不加载项目级 Claude slash
  command，并要求在 Claude Code 使用 `/result-promote` 的场景改用本 skill；canonical command
  无需再掺入 Codex 专属调用说明。
- **本轮（2026-07-12）human 选择题拍板的 6 条决策已落地**：Phase A/B 推进顺序、checksum
  无法校验原因枚举 + 必填人工理由字段、release gate 结构化边界、claim marker 用 HTML 注释
  语法、fixture 内嵌无 `tests/` 目录、index YAML 加 `schema_version`。对应关闭「未解决问题」
  1/2/3/4/6/7；具体字段/语法/任务排布见任务树各 `[Phase A]`/`[Phase B]` 标签与「未解决问题」
  条目的关闭说明。
- **checksum 算法统一用 sha256（human 拍板，2026-07-12，已终局，不再是 open question）**：
  不按 artifact 类型/文件大小分流选择不同 hash 算法；`checksum_algorithm` 字段唯一取值为
  `sha256`。实现前仍需按任务 3.0 先 Read 确认 `lab/data/checksums/` 目录现状是否已有
  与 sha256 冲突的既有约定；如有冲突，在实现 PR 里升级给 human 处理迁移方式，不影响
  「设计目标就是统一 sha256」这一结论本身。对应关闭「未解决问题」条目 8（此前是本轮 6
  条决策唯一未覆盖的残留问题，现已一并收敛）。

## 未解决问题

1. **已决策（human 选择题拍板，2026-07-12）——推进顺序**：先打通
   `result-index → evidence → claims → deliverables/index.md` 最短闭环，验证通过后再横向
   扩展到 table/figure/trace/model/dataset/checkpoint 等其余 index 类型（不是一次性给全部
   7 个 index + 5 个 ledger 加齐字段）。理由：最短闭环覆盖 issue 核心诉求
   （run→artifact→evidence→claim→deliverable 反查），先验证 schema/校验器/marker 设计在
   真实数据上可行，再复制到其余类型，风险和返工成本都更低。已落地为任务树「执行顺序」与
   各任务 `[Phase A]`/`[Phase B]` 标签。
2. **已决策（human 选择题拍板，2026-07-12）——「无法校验原因」枚举设计**：固定枚举值
   （`external-uri-no-checksum` / `pending-upload` / `legacy-untracked` /
   `oversized-defer-hash`）+ 必填人工理由字段 `checksum_unavailable_justification`（非空、
   非占位符），不是允许自由文本原因。理由：纯自由文本原因等于没有约束，容易被写成「懒得
   填」的万能借口；固定枚举限定合法场景，叠加必填的具体理由说明，两道关卡防止字段被滥用
   成校验逃逸口。字段设计见任务 1.2、3.4。checksum 算法本身（是否统一用 sha256）此前是
   本轮 6 条决策未覆盖的残留子问题，已由后续拍板收敛，见下方条目 8（已决策）。
3. **已决策（human 选择题拍板，2026-07-12）——release gate 结构化边界**：只把可客观机械
   验证的部分结构化——文件/manifest 存在性、checksum 匹配状态、run 闭环状态
   （experiment-ledger `status: done`）、regression-matrix `last_status`、evidence 已有
   grade 枚举达到阈值。涉及「结果够不够好」这类价值判断的 requirement 继续留自然语言 +
   human 审批，不强行伪结构化。理由：机械可验证的部分交给 validator 能真正防止漏检，价值
   判断类交给 validator 只会产生假精确、掩盖真实的人工判断责任。具体清单落地为任务 4.1 的
   `structured_checks` kind 枚举。
4. **已决策（human 选择题拍板，2026-07-12）——claim marker 语法**：HTML 注释标记
   `<!-- claim: id=<claim-id> [evidence=<evidence-id>,...] -->`，不用侧车 YAML 文件。理由：
   侧车 YAML 需要额外维护「正文段落 ↔ YAML 条目」的对应关系，容易随正文改动漂移；HTML
   注释直接嵌在声明所在处，diff 里可见、离正文最近、维护成本最低。覆盖范围
   （Markdown-only）是语法选择的自然推论，不是本轮单独拍板的新问题：HTML 注释只能嵌入
   文本类正文，非 Markdown 交付物走任务 5.3 的人工 review 证据路径兜底。落地见任务 5.1。
5. **已决策（此前一轮，human 拍板，2026-07-12，不再是 open question）**——新校验器为独立
   脚本：`scripts/check-provenance-chain.py`，仿 `scripts/check-same-commit.py` 先例：
   `scripts/` 现有惯例是「可单独跑 + 无第三方硬依赖」，独立脚本便于单独测试、复用，且不
   无限膨胀 `validate-governance.py` 单文件体积。硬约束（二审已定，本轮强化）：必须由
   `validate-governance.py`（CI 里跑的那个）通过 `run_subcheck("check-provenance-chain.py",
   strict)` 拉起，才能保证 Claude/Codex 触发对等；不允许只在 `.github/workflows/governance.yml`
   里单加一个平行 step 而不接进 validator（那样手动 `python scripts/validate-governance.py
   --strict` 会漏跑）。详见「当前决策」与任务 2.0 / 6.5。
6. **已决策（human 选择题拍板，2026-07-12）——fixture 测试框架**：跟随现有风格，脚本内嵌
   fixture 数据 + 无第三方依赖的断言测试，不新开 `tests/` 目录、不引入 pytest。理由：仓库
   当前无 `tests/`/`pytest` 基础设施（root 无 `pyproject.toml`），
   `scripts/validate-governance.py` 本身就是「无依赖、可单独跑」的风格，新增校验器延续同一
   惯例，避免引入新的测试运行时依赖与两套「怎么跑测试」的心智负担。落地见任务 6.2。
7. **已决策（human 选择题拍板，2026-07-12）——schema 版本化**：给各 index YAML 加
   `schema_version` 字段。理由：为未来 `template-sync.py` 之类下游工具判断 schema 兼容性
   留钩子，成本低（一个整数字段），现在不加、以后要回填全部历史条目的成本更高。默认设计：
   `schema_version: 1`（整数，从 1 开始，每类 index 独立计数，该 index 的字段结构发生
   不兼容变更时递增）。落地见任务 1.2/1.3/1.4。

8. **已决策（human 拍板，2026-07-12）——checksum 算法选择**：统一用 **sha256**，不按
   artifact 类型/文件大小分流选择不同的流式 hash 算法。理由：单一算法降低实现复杂度
   （不用为每种 artifact 类型维护算法选择/分支逻辑）、降低 validator 与 fixture 的覆盖
   成本；`hashlib.sha256()` 本身支持分块 `update()`，可流式处理大文件，不需要为「文件
   过大」单独换算法——真正过大、暂不具备本地算 hash 条件的场景走任务 1.2 已定义的
   `oversized-defer-hash` 枚举 + 必填理由兜底，不是靠切换算法解决。实现前仍按任务 3.0
   先 Read 确认 `lab/data/checksums/` 目录现有条目实际使用的算法：若已是 sha256，直接
   复用确认即可；若发现与 sha256 冲突的既有约定（例如历史条目用 md5/sha1），视为需要
   另行处理的迁移问题，在实现 PR 里标注冲突范围并升级给 human 拍板具体迁移方式（就地
   重算 / 保留旧值加 legacy 标记 / 分批迁移等）——这一核实步骤是「确认现状是否冲突」，
   不是「重新选型」，不改变本条已定的「统一 sha256」设计目标。落地见任务 1.2、3.0、3.4。
9. **已决策（Codex 初审收敛，2026-07-13）——trace/dataset 的「无 run 来源」不豁免三元组
   要求本身**：Phase B 首版实现曾把 trace/dataset 的 `required_triplet` 静默清空（「填了
   才校验」），初审判定为 plan 未批准的例外，予以纠正。收敛后的设计：全部 7 类 index 共用
   同一 `commit`/`config`/`run_id` 必填要求；确无 run 来源的合法场景（外部数据集、
   human-cc/agent trace、历史遗留）用**显式豁免字段**承载——`provenance_unavailable_reason`
   （固定枚举：`external-origin` / `human-authored` / `legacy-untracked`）+
   `provenance_unavailable_justification`（非空、非占位的人工具体理由），复用决策 2 的
   「枚举 + 必填理由」双关卡模式；豁免只覆盖确实缺失的字段（`run_id` 已填仍校验 run
   闭环），三元组齐全时再填豁免字段判 fail。同轮一并收紧（同为初审 MAJOR）：release gate
   `artifact-exists` 除 index 条目存在外还查 repo 内 `location` 文件真实存在（外部/不可达
   location 查 checksum/manifest 记录完备）；`checksum-verified` 只在 validator 真算
   sha256 比对通过时为满足——checksum 豁免（waived）/ 登记未校验（recorded-unverified）
   ≠ verified；deliverable「evidence 齐全=是」的非 draft 行必须「正文含 claim marker」或
   「行内登记 `human/reviews/results/` 下存在的人工 review 证据」二选一（任务 5.3 落地，
   豁免仅限占位/示例行与 draft 状态）。

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
- [ ] 新 provenance 校验（独立脚本 `scripts/check-provenance-chain.py`，经 `run_subcheck` 拉起）
      确认由 `validate-governance.py` 拉起（CI 与手动同源），触发与 runtime 无关；实现完成后在
      Codex 侧实跑并确认输出包含新增子检查（现有 validator 的 Codex 手动执行基线已于本轮通过）。
- [ ] `artifact-indexing`、`result-promote`、`release-gate` 相关文档与 ANATOMY 同步更新，
      DESIGN.md §6/§10 与实际一致。
- [ ] Phase A 最短闭环（result-index → evidence → claims → deliverables/index.md）独立可
      验证：即使 Phase B 尚未开始，`check-provenance-chain.py` 对这条闭环的正负 fixture
      全部按预期 pass/fail（决策 1）。
- [ ] `checksum_unavailable_reason` 只接受固定枚举值之一，且
      `checksum_unavailable_justification` 非空、非占位符（如单纯 "TBD"/"N/A"）——validator
      对枚举外的值或空/占位理由一律判 fail，不当作 unknown（决策 2，防滥用）。
- [ ] `checksum_algorithm` 字段只接受 `sha256` 一种取值，不出现按 artifact 类型/大小切换
      的其他算法；`lab/data/checksums/` 现状核实若发现冲突条目，已在实现 PR 里升级给
      human 并记录处理方式（决策 8）。
- [ ] `release-gates.yaml` 的 `structured_checks` 只覆盖可机械验证的 kind（存在性/checksum
      匹配/run 闭环/regression last_status/evidence grade 阈值）；validator 不把未结构化的
      自然语言 requirement 当作「已校验」（决策 3）。
- [ ] deliverable 正文中的 `<!-- claim: id=... -->` HTML 注释 marker，其 `id`（及可选
      `evidence`）引用必须存在于对应 YAML；非 Markdown 交付物走人工 review 证据兜底，不
      强行套用 marker 语法（决策 4）。
- [ ] fixture 正负例以脚本内嵌形式跑通（`--selftest` 或等价入口），不依赖 `tests/`/pytest
      基础设施（决策 5）。
- [ ] Phase A 触及的 5 个 YAML（`result-index.yaml` + 4 个 research YAML）均带
      `schema_version` 字段；Phase B 完成后覆盖全部 7+5 类（决策 6）。

## 下一步

「未解决问题」1–8 已全部由 human 拍板收敛（含 2026-07-12 最新拍板的条目 8：checksum
算法统一用 sha256）。**核实结果：本文档当前没有剩余 open question**。任务 3.0 保留的
「先 Read 确认 `lab/data/checksums/` 现状」步骤是实现前的**核实/冲突检测**动作，不是待
决策的算法选型问题——若核实中发现与 sha256 冲突的既有约定，按任务 3.0 约定升级给 human
处理迁移方式，这属于实现期可能出现的执行细节，不构成新的开放决策项。下一步：等待 human
对本轮任务树排布/字段设计/枚举值的整体确认（或继续在文件里批注），确认后按任务树
Phase A 顺序开始实现，每个采纳的修订/实现小步做一个 commit（仍需 human 批准）。

## Plan revision log

- 2026-07-12 初稿
- 2026-07-12 二审修订（Claude Opus 4.8 代替额度耗尽的 Codex gpt-5.6-sol 二审）：补 Codex 侧
  触发对等分析（validator 为 runtime-neutral 纯 Python，走 CI + 手动，不挂 runtime hook）、
  adapter 漂移 CI 强约束、checksum 走 hashlib 免 Bash 权限差异、Codex adapter 重生成任务与
  验证项，新增 open questions 8–10（Codex 手动调用权限 / claim marker 在 Codex 工作流一致性 /
  Codex 侧实跑验证待补）。人类最终批准仍待定。
- 2026-07-12 Codex（gpt-5.6-sol，medium）真实二审：实跑 strict governance validator，核验
  execpolicy 对现有 validator 明确 allow、对拟新增 provenance 脚本尚无匹配规则，并确认生成的
  `command-result-promote` skill 已含 Codex 调用说明；据此关闭上一轮 open questions 8–10，补入
  新脚本精确 allow 与实现后复测任务。人类最终批准仍待定。
- 2026-07-12 human 拍板：新校验器采用独立脚本 `check-provenance-chain.py`，仿
  `check-same-commit.py` 先例（原 open question 5 关闭，落地为「当前决策」+ 任务 2.0/6.5）。
- 2026-07-12 human 选择题拍板（逐条，非批注 diff 形式）：一次性收敛剩余 6 条 open
  question——(1) 先打通 result→evidence→claims→deliverable 最短闭环再横向扩展（Phase A/B）；
  (2) checksum「无法校验原因」用固定枚举 + 必填人工理由字段；(3) release gate 只结构化可
  客观机械验证的部分，价值判断类留自然语言 + human 审批；(4) claim marker 用 HTML 注释
  语法，不用侧车 YAML；(5) fixture 测试跟随现有风格脚本内嵌/无依赖断言，不新开 `tests/`
  目录；(6) index YAML 加 `schema_version` 字段。据此重排任务树为 Phase A/B 标签、补全
  checksum 枚举值与 claim marker 语法细节、关闭「未解决问题」1/2/3/4/6/7（新增残留条目 8：
  checksum 算法选择本身未覆盖，需实现时核实）。人类最终批准仍待定。
- 2026-07-12 human 拍板收尾：checksum 算法**统一用 sha256**，不按 artifact 类型/大小
  分流选择流式算法（关闭最后一条 open question 8）。据此更新：`checksum_algorithm`
  字段唯一取值固定为 `sha256`（任务 1.2）；任务 3.0 从「先 Read 确认算法本身该怎么选」
  改写为「先 Read 确认 `lab/data/checksums/` 现状是否与 sha256 冲突，若冲突升级给
  human 处理迁移方式，不改变统一 sha256 的设计目标」；任务 3.4、「当前决策」、未解决
  问题条目 2/8、「下一步」同步更新。**核实结果：本文件「未解决问题」1–8 已全部标记为
  已决策，当前无剩余 open question**。人类最终批准仍待定。
- 2026-07-13 Codex 初审（gpt-5.6-sol，high）修复（3 MAJOR + 1 MINOR）：(1) deliverable
  「evidence 齐全=是」的非 draft 行强制 marker-or-review 二选一（任务 5.3 此前漏实现）；
  (2) release gate `artifact-exists` 查 location 文件/manifest 记录真实存在、
  `checksum-verified` 只认真算 sha256 比对通过（waived ≠ verified）；(3) trace/dataset
  恢复三元组必填，「无 run 来源」改走显式 provenance 豁免字段（新增决策 9，如实记录该
  设计）；(4) self-test 补 table/figure/trace/checkpoint 负例及上述各修复的正负 fixture
  （self-test 共 29 个 case）。
- 2026-07-13 fresh 终审修复：active artifact / active evidence / submitted deliverable /
  passed gate 不再用 placeholder 跳过；占位或不完整 evidence 不参与 claim 强度，claim 引用
  evidence 必须匹配 `supports_claim` 归属，deliverable marker 必须覆盖索引该行全部 claim；
  passed gate 遇 `artifact-exists` unknown 改为 fail-closed；artifact/manifest/deliverable/review
  本地路径统一拒绝 absolute、`..`、resolve 越 repo、symlink escape 与非 regular file，并补
  `how_to_inspect`、dataset split membership、duplicate ID 校验及对应内嵌对抗 fixtures。
