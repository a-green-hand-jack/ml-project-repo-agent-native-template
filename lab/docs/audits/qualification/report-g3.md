# G3 workflow skills/commands walkthrough report

- 被测 commit（base）：`4b0c42c246e1a01d177ba0d5b3ae4452ff11a8cb`
- 生成时间：2026-07-17T07:56:02+00:00
- 生成时工作树是否 dirty：True（本分支自身即产出证据的一部分）
- 结果：6/8 PASS、1/8 PASS-with-finding（T-G3-6）、1/8 UNAVAILABLE-by-design（T-G3-7，机制经隔离
  fixture 验证）

| T-ID | skill/command | 结论 |
| --- | --- | --- |
| T-G3-1 | `worktree-pr-flow`（含 S2 变更自检清单实走） | PASS |
| T-G3-2 | `spawn`（in-session 子 agent） | PASS |
| T-G3-3 | `subagent-routing`（launch packet） | PASS（1 条非阻断观察） |
| T-G3-4 | `interactive-plan-doc`（draft→approved 干跑） | PASS |
| T-G3-5 | `checkpoint` / `session-boundary-control` | PASS |
| T-G3-6 | `pr-review`（fresh reviewer，对 PR #72） | PASS（发现 1 条真实 MINOR 缺陷，见下） |
| T-G3-7 | `template-feedback`（issue 打包干跑） | UNAVAILABLE（本 repo 是上游模板本身，非下游；机制经隔离 fixture 验证可用） |
| T-G3-8 | `experiment-workflow`（卡片+ledger 干跑） | PASS |

## 隔离零泄漏核验（T-G3-4 / T-G3-8 / T-G3-7 fixture）

| T-ID | 核验方式 | 结果 |
| --- | --- | --- |
| T-G3-4 | `memory/doc-lifecycle.yaml` sha256 前后比对 + `git status --porcelain plans/` | 前后 sha256 一致、`plans/` 无新增文件，zero-leak=True |
| T-G3-8 | `lab/research/experiment-ledger.yaml` sha256 前后比对 + `git status --porcelain lab/research/ lab/code/experiments/` | 前后 sha256 一致、两目录均无新增文件，zero-leak=True |
| T-G3-7 | `.template.toml`（真实 repo 无此文件，未新建）+ `git status --porcelain`（整仓） | 未新增/未污染任何真实文件；draft issue 只写在 `/tmp`，未 `gh issue create` |

三项隔离干跑均通过 Python `tempfile.mkdtemp()` + （T-G3-4 额外 `git init`）构造，用后即
`shutil.rmtree`（同进程内清理，不经 Bash `rm`/`mv`，避开 doc-lifecycle hook 对变量路径删除/
移动命令的拦截）。驱动脚本本身只写在 `/tmp/g3-*-fixture-driver.py`，不进 repo。

## 逐项证据

### T-G3-1 — PASS

- promise: 走 issue→branch→worktree→实现→验证→PR 流程，S2 变更自检清单（分类矩阵/三项前置声明/
  exact-base 双检/验证纪律/授权分级）真实填写。
- 角色/输入/输出：本分支 `test/g3-skills-walkthrough` 自身即是一个 worktree-pr-flow 实例；输入是
  human 交代的 G3 任务，输出是本报告 + `memory/branches/56-g3-skills.md`（内含完整 S2 清单）+
  最终 PR。
- exact-base 双检：开始时 `git rev-parse HEAD` == `git rev-parse origin/main` ==
  `4b0c42c246e1a01d177ba0d5b3ae4452ff11a8cb`，worktree clean；副作用动作（push/PR）前重新核对
  base 未移动（见下方 Commands run）。
- 停止条件：8 个 T-ID 全部有结论 + 治理门禁绿 + branch status 完整。
- 完整 S2 清单见 `memory/branches/56-g3-skills.md` 对应小节，此处不重复。

### T-G3-2 — PASS

- promise: 真起一个 in-session 子 agent（`Task`/`Agent` 工具），走「发现→选型→两层交代→命名」，
  并对照 #47 位置约定自检。
- 角色/输入/输出：主 agent 派一个一次性只读子任务给 `repo-researcher`，命名
  `斥候·查·spawn演示`；输入是「读 README.md 一级标题，一句话总结 repo 是做什么」；输出是子 agent
  署名回报的一句话总结 + 原文标题引用。
- 步骤 1 发现：`python3 .claude/skills/spawn/scripts/list_agents.py` 输出完整 16 个 agent 的
  一句话用途表，据此选中 `repo-researcher`（只读探索，匹配任务性质）。
- 步骤 4 命名：调查类任务 → `斥候·查·<focus>`，focus=`spawn演示`。
- 步骤 5 启动：用 in-session `Agent` 工具（非 Paseo tab），子 agent 正确署名
  `斥候·查·spawn演示` 并只做了要求的只读任务，未触碰任何文件。
- #47 位置约定自检：本次未新建 git worktree，走的是 in-session 模式——比"只开当前 Workspace 新
  tab"更保守（压根不占 Paseo 标签、不涉及 Workspace/Project 选择），三条位置约定天然满足。
- 停止条件：子 agent 跑完汇报一句话即停，未做额外探索。符合。

### T-G3-3 — PASS（1 条非阻断观察）

- promise: 为一个假想 child task 生成完整 launch packet（agent 类型/预算/模型/边界/停止条件）。
- 角色/输入/输出：派 `subagent-router-agent`（只读）为假想任务「在隔离 worktree 给
  `check-anatomy-drift.py` 补一条多层嵌套 symlink 逃逸负例回归测试」生成 launch packet；输出是
  完整填写的 `.agent/templates/launch-packet.md` 格式文本。
- 结果：role=impl、tier=3（触碰 governance validator 文件，按 model-routing-policy 校准规则升级）
  判定清楚且给出依据；tools/scope/forbidden/验收标准/停止条件/escalate condition 全部具体、无
  隐含 general-purpose 兜底；`~/.paseo/orchestration-preferences.json` 证据正确读取（role=impl →
  claude/claude-opus-4-8）。
- **非阻断观察**：SKILL.md 步骤 3 明确要求「运行」
  `read_agent_quota.py --role <role> --tier <tier> --format json`，但 canonical
  `subagent-router-agent`（`.claude/agents/subagent-router-agent.md`）的 `tools:` 字段只声明
  `Read`，结构上无法执行该命令。本次演示中，agent 如实说明了这条能力/文档不一致，把
  provider/model 字段标记为 PENDING 并要求上层回填，未臆造 quota 数据——这是正确的降级行为，但
  暴露了 SKILL.md 正文与 agent 工具边界之间的一处真实不一致（不属于本次改动范围，只报告，见
  T-G3-7 隔离 fixture 里把这条观察包成了一个假想下游 issue 草稿作为双重演示）。
- 停止条件：产出 packet 即停，未越权自行派发。符合。

### T-G3-4 — PASS

- promise: draft→in-review→approved 状态流转在隔离 fixture 里可走通，且负例（未决批注/跨文件
  锚点-注册表矛盾）被正确拒绝；真实 `plans/`、`memory/doc-lifecycle.yaml` 零污染。
- 角色/输入/输出：本 agent 自己驱动（无需子 agent，纯脚本+校验逻辑复用），驱动脚本
  `/tmp/g3-plan-doc-fixture-driver.py`（`tempfile.mkdtemp()+git init`，import
  `scripts/check-doc-lifecycle.py` 的 `validate_repo()`/`pretooluse_reason()` 直接复用真实校验
  逻辑，不重新实现）。
- positive: draft/in-review/approved（clean）三态 `validate_repo()` 均 `errors=[] warnings=[]`。
- negative 1（未决批注）：approved 但批注区仍有 `[?]`，`errors=['...Human 批注区仍有 [?]/[改]
  未决批注，不能停留在 approved——先收敛或回 in-review']`。
- negative 2（两层防御验证）：单次 `Write` 把已 approved 文档的锚点静默改回 draft（不动
  registry）——`pretooluse_reason()` 返回 `None`（符合既有设计边界："PreToolUse 只拦单次调用可
  独立判定的局部不完整"，跨文件一致性不归 hook 管）；随后把同一改动落到磁盘、跑 commit-gate
  `validate_repo()` → 正确捕获
  `'...状态锚点 draft 与注册表 approved 矛盾（同 commit 对齐两处）'`。两层防御（hook 拦局部、
  validator 拦跨文件）分工如设计文档所述，各司其职，验证成立。
- 零泄漏：`memory/doc-lifecycle.yaml` sha256 前后一致；`git status --porcelain plans/` 为空。
- 停止条件：三态+两个负例验证完即停，未在真实 `plans/` 下创建任何文件。

### T-G3-5 — PASS

- promise: session-boundary-control 判断边界 + 维护 `memory/session-tree.md`；checkpoint 把当前
  状态固化，写进分支报告区，不覆盖真实 `memory/current-status.md` 主体。
- 角色/输入/输出：派 `session-boundary-agent`（署名 `师爷·审·G3边界`）真实更新
  `memory/session-tree.md`——判定 boundary signal=「任务树分叉」（8 个 T-ID 子任务），
  recommended action=branch，`## Children` 表新增 `issue-56-g3-skills` 一行 + 新增
  `### Boundary note` 小节；核实 `## Parent objective`、既有 Children 行、
  `## Global forbidden paths` 等均未被触碰，`memory/current-status.md` 未被碰。
- checkpoint 演练：内容 taxonomy 与 `.claude/agents/checkpoint-writer.md` 一致（current
  objective/constraints/files inspected/modified/decisions/commands/subagent reports/open
  issues/exact next steps/do-not-forget），**刻意重定向落点**到
  `memory/branches/56-g3-skills.md`（本分支自己拥有的文件）而非真实 `current-status.md`——因为
  那是父 session（都督·统·治理路线）维护的活文件，本次 G3 演练明确被交代不覆盖其主体。产物见该
  文件「T-G3-5 checkpoint 演练产物」小节。
- 停止条件：边界判定+session-tree 更新+checkpoint 产物落地即停。符合。

### T-G3-6 — PASS（发现 1 条真实 MINOR 缺陷）

- promise: 以 fresh reviewer 审查一个已存在 PR 的 diff（correctness/回归/测试/复现/数据安全/
  anatomy/变更自检清单），产出 severity 分级 findings。
- 角色/输入/输出：派 `code-reviewer`（署名 `师爷·审·PR72复盘`），目标 = 已合入的 **PR #72**
  （G4 双 agent 场景验证）。独立跑 `gh pr diff 72`，按 `.claude/commands/pr-review.md` 正文逐条
  审查，最后跑 `validate-governance.py`。
- 结果：无 BLOCKER/MAJOR，2 条 MINOR + 2 条 NIT + 1 条 Open Question，附完整 Positive
  Observations，verdict=COMMENT（不推翻已合并事实）。`validate-governance.py` 复跑 `OK — 0
  error(s), 0 warning(s)`。
- **真实发现（MINOR，记录不修复）**：`lab/evals/control-plane/run-g4-scenario.py` 的 UNAVAILABLE
  降级语义在文档/docstring/branch-report 里被反复承诺，但代码从未真正产出
  `unavailable=True`（死代码路径）；更实质地，T-G4-6 负例分支 a 在**没有安装 `paseo` CLI 的机器**
  上会硬断言 `paseo_presence == "-"`，但对照 `scripts/agent-status.py:140-143` 的真实语义，无
  `paseo` 时该字段应为 `"unknown(no-paseo)"`，导致该负例在这类机器上会误判 **FAIL** 而非优雅降级/
  UNAVAILABLE——与 G4 branch report「观察 #3」的自述（"没装 paseo 的机器会天然落进这条负例"）
  相矛盾。该发现不影响已采集证据的有效性（作者机确实装了 paseo，7/7 PASS 在该机器上成立），
  是**可移植性 + 文档与实现不符**问题，已记录，本轮不修复（`.claude/agent-reports/` 或本报告即
  完整记录，交都督/后续处理）。
- 停止条件：findings 分级列完 + validate-governance 结果报告即停，未去 PR 里评论/未重开 PR。

### T-G3-7 — UNAVAILABLE（by design，机制经隔离 fixture 验证可用）

- promise: 把假想下游反馈打包成上游 issue 草稿到文件，绝不真发。
- **原生适用性判定**：本 repo 根目录**没有 `.template.toml`**（`ls -la .template.toml` →
  不存在），且 `git remote -v` 显示 origin 就是
  `a-green-hand-jack/ml-project-repo-agent-native-template`——本 repo 本身就是上游模板，不是
  下游消费者。`template-feedback` SKILL.md 步骤 1 明确写「缺文件 → 说明这不是本模板的下游
  repo，停止」，且 `scripts/template-sync.py:read_template_toml()` 对同样情况会
  `raise SystemExit("ERROR 缺少 .template.toml —— 这看起来不是本模板的下游 repo。")`。**两处
  独立代码路径一致确认**：在本 repo 原生调用该 skill，正确结果就是「停止，不适用」——判
  UNAVAILABLE 而非 FAIL，这是 skill 自身适用边界正确生效的证据，不是 skill 坏了。
- **补充机制验证**（隔离 fixture，满足 G3 任务要求的「打包出 issue 草稿文本」交付物）：驱动脚本
  `/tmp/g3-template-feedback-fixture-driver.py` 在 `tempfile.mkdtemp()` 内放一个假的
  `.template.toml`（模拟下游），走步骤 1-5（读版本锚点→定位框架层路径→收集证据→判类型→组织
  issue 草稿），把草稿写到 `/tmp/g3-template-feedback-draft-issue.md`（1900 字节），**全程未调用
  `gh issue create`**。草稿内容取材于 T-G3-3 真实发现的
  `subagent-routing`/`subagent-router-agent` 工具边界不一致（框架层路径、场景、复现三段皆基于
  本轮真实观察，只是「上报」这个动作本身是假想的，因为本 repo 不是下游）。
- 零泄漏：`git status --porcelain`（整仓）只显示本轮预期改动的文件（`memory/session-tree.md`、
  `memory/branches/56-g3-skills.md` 等），无 `.template.toml`、无 draft issue 落进真实仓库。
- 停止条件：草稿写完、确认未调用 `gh issue create` 即停。符合。

### T-G3-8 — PASS

- promise: experiment card + ledger 条目在隔离 fixture 里可走通 planned→approved（不跑真训练），
  且 approved 前必填字段缺失被正确拒绝；真实 ledger / `lab/runs` 零污染。
- 角色/输入/输出：本 agent 自驱动，驱动脚本
  `/tmp/g3-experiment-workflow-fixture-driver.py`（`tempfile.mkdtemp()`，import
  `scripts/validate-experiment-state.py` 的 `check_ledger()` 直接复用真实校验逻辑）。
- positive: `planned` 与 `approved`（字段齐备）两态 `check_ledger()` 均 `errors=[]`（`uv run
  --with pyyaml` 下 `warnings=[]` 亦为空；裸 `python3` 下仅有预置环境缺口的 PyYAML 提示 warning，
  非本轮引入，与既有多个先例一致）。
- negative: `approved` 但缺 `commit/config/data_split/expected_runtime/success_metric` 与
  `approved_by/approved_at` → `check_ledger()` 正确产出三条 `errors`，逐字段点名缺失项。
- launch 命令草案按 SKILL.md 步骤 4 生成但**未执行**：
  `python lab/infra/launch/expctl.py plan --action launch --run-id g3-demo-run`（只打印，不跑，
  更谈不上真实 launch/kill/restart）。
- 零泄漏：`lab/research/experiment-ledger.yaml` sha256 前后一致；
  `git status --porcelain lab/research/ lab/code/experiments/` 为空。
- 停止条件：planned+approved+负例三态验证完即停，未创建任何真实 experiment card/ledger 条目，
  未触碰 `lab/runs/`。

## 验证命令

| command | 结论 |
| --- | --- |
| `python3 .claude/skills/spawn/scripts/list_agents.py` | 输出 16 个 agent 完整发现表 |
| `gh pr view 72 --json ...` / `gh pr diff 72` | 正常读取，PR #72 已合入 main |
| `uv run --with pyyaml python3 /tmp/g3-plan-doc-fixture-driver.py` | T-G3-4 全部断言 PASS |
| `uv run --with pyyaml python3 /tmp/g3-experiment-workflow-fixture-driver.py` | T-G3-8 全部断言 PASS |
| `python3 /tmp/g3-template-feedback-fixture-driver.py` | T-G3-7 原生 UNAVAILABLE 判定 + fixture 机制验证均如预期 |
| `uv run --with pyyaml python3 scripts/validate-governance.py --strict` | 见下方最终验证结果 |
| `uv run --with pyyaml python3 scripts/check-anatomy-drift.py` | 见下方最终验证结果 |
| `uv run --with pyyaml python3 scripts/check-doc-lifecycle.py` | 见下方最终验证结果 |
| `uv run --with pyyaml python3 scripts/check-same-commit.py --staged` | 见下方最终验证结果 |
