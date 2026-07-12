# current-status.md

> **活文件**。这是当前状态的单一真相源。每次 session 结束、compact 前、完成小目标时更新。
> fresh session 应能只读本文件 + `session-tree.md` 就接续工作。

## 当前 objective

把模板从 Claude-Code-native 扩展为 Claude Code + Codex 都可直接使用的 agent-native 模板。
最新一轮新增 `coding-agent-quota` repo-local skill，用本地 usage snapshot 读取 Codex /
Claude Code 当前窗口与周额度，并把 `subagent-routing` / `subagent-router-agent` 升级为
配额感知的 provider/model 路由；验证已通过。

**分支 `feat/12-bootstrap-adoption-proof`（issue #12 part A，`.claude/worktrees/12-bootstrap-adoption-proof`）**：
实现新项目 bootstrap 命令，把 README「派生后的落地步骤」里能自动化的部分（`.template.toml` 版本
锚点、`core.hooksPath`、Codex adapters 同步、governance）收敛成一条幂等命令
`scripts/bootstrap-project.py`，经 `.claude/skills/bootstrap-project/SKILL.md` 引导调用；需要
human 信息的步骤（CODEOWNERS owner、`PROJECT.md`、删无用目录、Codex trust）只报告不代做。见
`plans/20260712-bootstrap-adoption-proof.zh.md`（任务树 A + D 里归属 A 的子项）。issue #12 的
part B（existing-repo 语义归类）与 part C（smoke 合同）已按 human 拍板拆到各自独立分支/PR。

**当前分支 `feat/12c-smoke-contract`（issue #12 part C，`.claude/worktrees/12c-smoke-contract`，
base 是 `feat/12-bootstrap-adoption-proof`，即已含 part A）**：实现统一的 runtime/smoke 验证合同
（任务树 C1-C4 + D 里归属 C 的部分）。`adopt-existing-repo.py` 的 `prove` phase 与
`check-adoption-integrity.py` 现在按 schema 写 smoke 结果（`command_source`/`command`/
`result`（pass/fail/skipped/unknown）/`unverified_reason`），且 exit code 与 smoke 结果解耦
——只在 adoption 自身完整性失败（tracked-byte hash 不一致，或 normalize 遗留未解决的 conflict/
受保护路径 blocker）时非 0；smoke 非 pass 时 exit code 仍为 0，但 report /
`check-adoption-integrity.py --json` 必须带显式、机器可读的 `warnings`/`smoke_warnings` 字段，不能
被静默吞掉（已决策，开放问题 5）。见
`plans/20260712-bootstrap-adoption-proof.zh.md`（任务树 C + D 里归属 C 的子项）。issue #12 的
part B（existing-repo 语义归类）未在本分支涉及。

## Constraints

- 遵守 `AGENTS.md` / `.agent/AGENTS.md` / `.agent/action-boundary.md`。
- 不编辑或删除 `lab/data/**`、`lab/runs/**`、`lab/models/**` bytes、`checkpoints/**`、`wandb/**`、
  `lab/infra/private/**`、`.env`。
- 不启动/kill/restart 长训练或远端作业。
- 不 push main、不开 PR、不 release。
- 两个 replay case worktree/branch 继续作为证据保留，不合入 main。

## Files inspected（issue #12 part A）

- `plans/20260712-bootstrap-adoption-proof.zh.md`（全文，含全部批注/决策历史）
- `scripts/adopt-existing-repo.py`、`scripts/template-sync.py`、`scripts/check-agent-harness.py`、
  `scripts/sync-codex-adapters.py`、`scripts/validate-governance.py`、`scripts/check-anatomy-drift.py`、
  `scripts/check-adoption-integrity.py`
- `.agent/template-versioning-policy.md`、`.github/CODEOWNERS`、`PROJECT.md`、`VERSION`
- `.claude/skills/adopt-existing-repo/SKILL.md`、`.claude/commands/adopt-existing-repo.md`
- `lab/evals/adoption/run-adoption-smoke.py`、`lab/ANATOMY.md`
- `README.md`、`DESIGN.md` §10、`scripts/ANATOMY.md`、`.claude/ANATOMY.md`、`scripts/README.md`、
  `scripts/CLAUDE.md`、`scripts/AGENTS.md`

## Files inspected（issue #12 part C）

- `plans/20260712-bootstrap-adoption-proof.zh.md`（全文，C1-C4 + 验证标准里对应 C 的部分）
- `scripts/adopt-existing-repo.py`、`scripts/check-adoption-integrity.py`（现状代码）
- `lab/evals/adoption/run-adoption-smoke.py`、`lab/docs/audits/agent-r1-adoption-replay-report.md`
  （既有 replay 报告的写法参考）
- `.claude/commands/adopt-existing-repo.md`
- 网络：候选真实 repo 调研（`docopt/docopt`、`kvesteri/validators`、`benjaminp/six`、
  `un33k/python-slugify`、`jaraco/inflect`、`tartley/colorama` 等，最终选 colorama，见下方决策）

## Files inspected

- `AGENTS.md`
- `.agent/AGENTS.md`
- `.agent/action-boundary.md`
- `.agent/tool-skill-interface.md`
- `.agent/model-routing-policy.md`
- `.agent/repo-documentation-topology.md`
- `ANATOMY.md`
- `.claude/ANATOMY.md`
- `.claude/agents/*.md`
- `.claude/skills/*/SKILL.md`
- `.claude/commands/*.md`
- `.claude/hooks/*.py`
- `.claude/settings.json`
- `.claude/skills/coding-agent-quota/SKILL.md`
- `.claude/skills/coding-agent-quota/scripts/read_agent_quota.py`
- `.claude/skills/subagent-routing/SKILL.md`
- `.claude/agents/subagent-router-agent.md`
- `.agent/model-routing-policy.md`
- `scripts/check-agent-harness.py`
- OpenAI/Codex docs：AGENTS.md、skills、subagents、hooks、config、rules

## Files modified（issue #12 part A，本轮新增）

- `scripts/bootstrap-project.py`：新增。把刚从模板派生的新 repo 落地成自洽状态：
  `.template.toml`（origin+version 锚点，`--origin` 显式传入不推断，origin 冲突默认报错、
  `--force` 才覆盖）、`git config core.hooksPath .githooks`、`sync-codex-adapters.py`、
  `validate-governance.py`；需 human 信息的步骤只报告（`human_todo_items`）不代做；写
  `lab/docs/audits/template-bootstrap/state/*.json` 与 `template-bootstrap-report.md`。
- `.claude/skills/bootstrap-project/SKILL.md`：新增 skill（非 slash command，见开放问题 1 已决策）。
- `.agents/skills/bootstrap-project/SKILL.md`：由 `sync-codex-adapters.py` 生成的 Codex adapter；
  未生成对应 `command-bootstrap-project`（按决策，bootstrap 本身就是 skill 形态）。
- `lab/evals/bootstrap/run-bootstrap-smoke.py`、`lab/evals/bootstrap/README.md`：新增 synthetic
  fixture，覆盖幂等/origin 冲突/`--force`/三个 validator 全绿。
- `lab/ANATOMY.md`：leaf 层清单加入 `evals/bootstrap/`。
- `scripts/ANATOMY.md`：加入 `bootstrap-project.py` 的 Components/Connections 行。
- `scripts/README.md`、`scripts/CLAUDE.md`：加入 bootstrap 用法；`CLAUDE.md` 把「三个脚本只读、
  无副作用」改写为「只读校验脚本 vs 有副作用的 mutating 脚本」两类描述（D5，措辞已与现实脱节）。
- `.claude/ANATOMY.md`：Connections 加入 `skills/bootstrap-project/` 调用关系。
- `README.md`：「派生后的落地步骤」改写为调用 `bootstrap-project.py`，人工兜底步骤（含
  Codex trust 前提）保留在命令输出的 human todo 里；快速门禁加入 bootstrap smoke 命令。
- `DESIGN.md` §10：Skills 12→13、Codex adapters skills 20→21、Validators/tools 9→10，补
  `bootstrap-project` 相关条目。
- `memory/current-status.md`、`memory/session-tree.md`：记录本 feature 落地状态（本节）。

## Files modified（issue #12 part C，本轮新增）

- `scripts/adopt-existing-repo.py`：`detect_test_command()` 现返回 `(command, command_source)`
  二元组（`explicit`/`auto-detected`/`none`）；新增 `evaluate_smoke()` 按 C1 schema
  （`command_source`/`command`/`result`/`unverified_reason`/`exec`）跑并分类被迁移项目自身原生测试；
  新增 `latest_normalize_blockers()`，`integrity_result()` 现把「最近一次 normalize 遗留未解决的
  conflict/受保护路径 blocker」也算进 adoption 自身完整性失败（`unresolved_blockers` 字段），不再
  只看 tracked-byte hash；`prove()` 生成结构化 `smoke` + `warnings` 字段并写进 report；`main()`
  改为按 `prove` 返回的 `integrity.ok` 决定 process exit code（此前 bug：`prove` 从不让整体进程非
  0 退出，即使 integrity 失败）——exit code 现在只受 adoption 自身完整性影响，与 smoke 结果解耦
  （已决策，开放问题 5）。`write_report()` 新增 Smoke / Warnings 小节。
- `scripts/check-adoption-integrity.py`：新增 `latest_smoke_warnings()`，从最近一次 `prove`
  phase-log 条目读出 `warnings` 并在文本/`--json` 输出里显式呈现（`SMOKE WARNING ...` /
  `smoke_warnings` 字段）；`unresolved_blockers` 同样在文本模式打印为 `BLOCKED <path>`；exit code
  语义不变（只反映 `integrity_result().ok`，现在天然覆盖 blocker 未解决的情况）。
- `lab/evals/adoption/run-adoption-smoke.py`：从单一 happy-path 扩成四个场景：
  `scenario_happy_path`（回归，新增断言 `smoke_result: pass` + 空 warnings）、
  `scenario_blocked_normalize`（受保护路径 `checkpoints/` 触发 blocker，断言
  `adopt-existing-repo.py` 与 `check-adoption-integrity.py` 均非 0 exit，blocker 文本可读）、
  `scenario_smoke_failing_command`（检测到但失败的原生测试，断言两脚本仍 exit 0 但 report/`--json`
  都带非空 warning）、`scenario_smoke_undetected`（无可探测测试命令，断言 `skipped` + 显式
  `unverified_reason`，同样 exit 0 + 非空 warning）。
- `.claude/commands/adopt-existing-repo.md`：步骤 4 汇报清单改写，区分 integrity/blocker（应非 0）
  与 smoke（不应非 0，但须转述显式 warning）。
- `.agents/skills/command-adopt-existing-repo/SKILL.md`：由 `sync-codex-adapters.py` 重新生成
  （same-commit）。
- `README.md`、`scripts/README.md`：补充 smoke 合同的 exit-code/warning 解耦说明。
- `lab/docs/audits/README.md`：登记新增的 `colorama-adoption-replay-report.md`。
- `lab/docs/audits/colorama-adoption-replay-report.md`：新增。真实 existing-repo replay（新找的
  `tartley/colorama`，不复用/复跑 Agent-R1 案例，见开放问题 6），命中 `Makefile` `test:` 检测路径，
  原生测试因目标 repo 未 bootstrap venv 而失败——验证 smoke 合同在真实「检测到但失败」场景下端到端
  可用：两脚本均 exit 0，report/`--json` 都有显式非空 warning。
- `memory/current-status.md`、`memory/session-tree.md`：记录本节。

## Decisions（issue #12 part C，本轮新增）

- 严格按 `plans/20260712-bootstrap-adoption-proof.zh.md` 已拍板的 C1-C4/开放问题 5 落地，未重新讨论：
  exit code 只反映 adoption 自身完整性（tracked-byte hash + 未解决 blocker），smoke 结果永远走
  warning 字段，不影响 exit code。
- 把「normalize 遗留未解决 blocker（受保护路径/目标已存在的冲突）」也纳入
  `integrity_result().ok` 的判定——这是本轮在读代码时发现的一个真实 gap：此前 `prove` 从不让
  `adopt-existing-repo.py` 整体进程非 0 退出（即使 integrity 失败），且 blocker 未解决时
  `check-adoption-integrity.py` 无法感知、会静默报 `OK`。这不是原 plan 显式写出的实现细节，但是
  C1「adoption 自身 integrity 失败（例如 tracked-byte hash 不匹配）」这句里「例如」二字暗示的
  应有覆盖范围，与验证标准「冲突文件/受保护路径命中……断言 check-adoption-integrity.py 非 0
  exit」直接对应，故按此实现，未额外请示。
- 真实 repo replay 选择 `tartley/colorama`（而非继续用 Agent-R1）：小（`.git` 316K）、有明确
  `Makefile` `test:` 目标（不同于 Agent-R1 的「完全未检测到」与本模板负向 fixture 常用的
  `tests/` 目录 pytest 检测路径），跑出「检测到但失败」的真实结果（本地环境未预装该 repo 所需
  virtualenv/pytest），是本轮最有代表性的新证据形态。
- `check-adoption-integrity.py` 的 `smoke_warnings` 直接从最近一次 `prove` 的 phase-log 条目读取，
  不重新解析 markdown report——避免报告格式变化时校验逻辑跟着漂移，保持单一结构化事实源
  （`lab/docs/audits/template-adoption/state/phase-log.jsonl`）。
- 未触碰 `.claude/skills/adopt-existing-repo/SKILL.md`（D2 显式归属 B），仅更新
  `.claude/commands/adopt-existing-repo.md` 步骤说明 + 同 commit 重新生成对应 Codex adapter
  （D2b same-commit rule）。

## Commands + results（issue #12 part C，本轮新增）

| command | 结论 |
| --- | --- |
| `python lab/evals/adoption/run-adoption-smoke.py`（happy-path + blocked-normalize + smoke-fail + smoke-undetected 四场景） | `[adoption-smoke] OK`，四场景全部通过，含新负向 fixture。 |
| 手工冒烟：`checkpoints/` 受保护路径 repo 跑 `adopt-existing-repo.py --phase all` | `exit 1`，stderr 含 `checkpoints` blocker；`check-adoption-integrity.py` 同样 `exit 1`，输出 `BLOCKED checkpoints`，`--json` 里 `ok=false`、`unresolved_blockers=["checkpoints"]`。 |
| 手工冒烟：失败测试 repo（`tests/test_broken.py` 故意断言失败） | `adopt-existing-repo.py --phase all` `exit 0`；report 含 `smoke_result: fail` 与显式 warning；`check-adoption-integrity.py` `exit 0`，`--json` 的 `smoke_warnings` 非空。 |
| `python scripts/adopt-existing-repo.py /tmp/colorama-adoption-replay/Colorama --phase all --policy conservative --project-name colorama`（真实 repo replay，`tartley/colorama` @ `841634e`） | `exit 0`；`integrity=ok`、`normalize blockers=0`、`smoke=fail`（`make test` 检测到但因目标 repo 未 bootstrap venv 而失败）。 |
| `python scripts/check-adoption-integrity.py /tmp/colorama-adoption-replay/Colorama` / `--json` | `exit 0`；`OK -- present 49/49`；`smoke_warnings` 非空，列出 `original_test` fail + reason。 |
| `python scripts/validate-governance.py --strict`（`uv run --with pyyaml`） | `OK — 0 error(s), 0 warning(s)`。裸 `python3`（无 PyYAML，本机预置环境缺口，非本轮引入）跑同一命令会因 4 条 YAML-related warning 在 `--strict` 下变 `FAIL`；已用 `git stash` 验证该 warning 在改动前后一致存在，不是本轮回归。 |
| `python scripts/check-agent-harness.py --strict`、`python scripts/check-anatomy-drift.py`、`python scripts/sync-codex-adapters.py --check` | 全部 `OK`。 |
| `python scripts/check-same-commit.py --staged` | `OK —— 1 处结构改动，对应 anatomy 已同变更集更新`。 |
| `git diff --check` | 通过，无空白错误。 |
| `python lab/evals/bootstrap/run-bootstrap-smoke.py`（回归，确认未破坏 part A） | `uv run --with pyyaml` 下 `OK`；裸 `python3` 因同一 PyYAML 缺口 `FAIL`（非本轮回归，见上）。 |

## Files modified

- `.codex/`：新增 Codex project config、rules、custom-agent adapters 与导航四件套。
- `.agents/`：新增 Codex repo-local skills adapters 与 command adapters，以及导航四件套。
- `.claude/hooks/pre_tool_guard.py`：支持 Codex `apply_patch` 输入与 `CODEX_ALLOW_PUSH_MAIN=1`。
- `.claude/hooks/format_changed_python.py`：新增 Claude/Codex 共用的 Python 格式化 advisory hook。
- `.claude/hooks/zh_review_advisory.py`：支持 Codex `apply_patch` 变更路径解析。
- `scripts/sync-codex-adapters.py`：新增从 `.claude/` canonical 能力生成 Codex adapters 的脚本。
- `scripts/check-agent-harness.py`：新增 Codex config/adapters 检查。
- `AGENTS.md`、`CLAUDE.md`、`README.md`、`DESIGN.md`、`.agent/*.md`、`lab/infra/*`：
  同步 Claude/Codex 双 surface 的 doctrine 与说明。
- `ANATOMY.md`、`.claude/ANATOMY.md`、`.codex/ANATOMY.md`、`.agents/ANATOMY.md`、`scripts/ANATOMY.md`：
  同步结构路由。
- `memory/change-control.yaml`、`memory/current-status.md`、`memory/session-tree.md`：记录本次能力变更。
- `.claude/skills/coding-agent-quota/`：新增 canonical quota skill、UI metadata 与读取脚本。
- `.agents/skills/coding-agent-quota/SKILL.md`：由 `scripts/sync-codex-adapters.py` 生成的 Codex adapter。
- `.claude/skills/subagent-routing/SKILL.md`、`.claude/agents/subagent-router-agent.md`：
  派发 child agent 前必须读取 quota snapshot，并把 provider/model/effort 推荐写进 launch packet。
- `.agent/model-routing-policy.md`、`.agent/templates/launch-packet.md`：
  增加 role、quota snapshot、usage velocity、Paseo preference、recommended provider 字段。
- `.agents/skills/subagent-routing/SKILL.md`、`.codex/agents/subagent-router-agent.toml`：
  由 `scripts/sync-codex-adapters.py` 同步更新。
- `.claude/ANATOMY.md`、`DESIGN.md`：登记新增 skill 与能力数量。
- `scripts/check-agent-harness.py`：将本地 `.omx/` runtime state 视作工具状态忽略，避免 strict gate 因本机 runtime 目录失败。

## Decisions（issue #12 part A，本轮新增）

- 严格按 `plans/20260712-bootstrap-adoption-proof.zh.md` human 已拍板的 6 条决策落地，未重新讨论：
  bootstrap 做成 skill（非 command）、`--origin` 显式传参不推断、origin 冲突默认报错 `--force`
  才覆盖、语义归类 v1 不做（不在本分支范围内）、真实 replay 用新 repo（不在本分支范围内）、B/C
  拆独立 PR（本分支只做 A）。
- `.template.toml` 只写 `origin`/`version` 两个字段（不额外塞 `bootstrapped_at` 等元数据），
  保持与 `scripts/template-sync.py` 的 `read_template_toml()` 解析预期一致、避免不必要的 schema 面。
- origin 冲突检测在 `bootstrap-project.py` 里发生在**任何**写操作之前（先读后判断），确保「报错并
  停止」是真的不碰任何文件，不是「跑到一半才报错」。
- `human_todo_items()` 对 CODEOWNERS/PROJECT.md 做轻量 placeholder 检测（复用仓库既有的 `<...>`
  占位符约定，以及本模板固定的默认 owner `@a-green-hand-jack` 字符串），只作为 report 里的
  `detected_state` 展示，不作为判定依据、不代替 human 填写——遵守「不猜测」底线。
- `agent_surface_checklist()` 的说明文字明确标注 Claude/Codex 文件计数只是辅助展示，机器事实源是
  `check-agent-harness.py --strict` 与 `sync-codex-adapters.py --check` 的返回码（plan A4 要求）。
- D2c（bootstrap 与 adoption 共用同一份 agent-surface postflight 数据结构/渲染函数）**不在本分支
  范围内**——上层任务指令明确排除 D2c，留给未来 B（B6）落地时决定是否重构复用。

## Decisions

- `.claude/` 继续作为 canonical capability source；Codex adapters 由 `scripts/sync-codex-adapters.py`
  机械生成，避免两套能力手写漂移。
- Codex skills 使用 `.agents/skills/`；Claude slash commands 生成 `command-*` skills，作为 Codex 的等价入口。
- Codex custom agents 使用 `.codex/agents/*.toml`；不写死 model，保留"预算不是身份"原则。
- 共享 hook 地板继续放在 `.claude/hooks/`，Codex 通过 `.codex/config.toml` 调用同一批脚本。
- `coding-agent-quota` 优先读 `~/.claude/.search-index/usage.db` 的 `api_usage_snapshots`；
  Codex 额外 fallback 扫 `~/.codex/sessions/**/*.jsonl` 与 archived sessions 的 `rate_limits`。
  脚本不读取 credential 文件。
- `~/.paseo/orchestration-preferences.json` 当前未发现；quota 脚本会显式标注 `missing/defaulted`，
  并使用内置保守默认，不会假装已经读到本地偏好。

## Commands + results（issue #12 part A，本轮新增）

| command | 结论 |
| --- | --- |
| `python scripts/bootstrap-project.py <tmp> --origin a-green-hand-jack/ml-project-repo-agent-native-template`（手工冒烟，四个 tmp repo 场景：首次创建/幂等确认/冲突拒绝/`--force` 覆盖） | 全部符合预期：`created`→`confirmed`→冲突 `exit 1` 且未改文件→`--force` 后 `overwritten`。 |
| 在上面 tmp repo 内跑 `validate-governance.py --strict` / `check-agent-harness.py --strict` / `sync-codex-adapters.py --check` | 全部 `OK`，`.template.toml` 可被 `template-sync.py` 的 `read_template_toml()` 正确解析。 |
| `python lab/evals/bootstrap/run-bootstrap-smoke.py` | `[bootstrap-smoke] OK`：覆盖幂等/冲突拒绝/`--force`/三个 validator 全绿。 |
| `python lab/evals/adoption/run-adoption-smoke.py`（回归，确认未破坏既有 adoption 路径） | `[adoption-smoke] OK`。 |
| `python scripts/validate-governance.py --strict` | `OK — 0 error(s), 0 warning(s)`。 |
| `python scripts/check-agent-harness.py --strict` | `OK — 0 error(s), 0 warning(s)`（含 DESIGN §10 清单数量校验）。 |
| `python scripts/check-anatomy-drift.py` | `OK — 扫描 15 个 ANATOMY.md，0 处漂移`。 |
| `python scripts/sync-codex-adapters.py --check` | `OK — 0 issue(s)`（`bootstrap-project` skill adapter 已生成，未生成对应 command-* skill）。 |
| `python scripts/check-same-commit.py --staged` | `OK —— 5 处结构改动，对应 anatomy 已同变更集更新`。 |
| `git diff --check` | 通过，无空白错误。 |
| `python -m py_compile scripts/bootstrap-project.py lab/evals/bootstrap/run-bootstrap-smoke.py` | 通过。 |

## Commands + results

| command | 结论 |
| --- | --- |
| `node /home/user/.codex/skills/.system/openai-docs/scripts/fetch-codex-manual.mjs` | 失败：官方 manual 响应缺 `x-content-sha256`；随后改用官方 OpenAI/Codex docs 页面核对。 |
| `python scripts/sync-codex-adapters.py` | 写入 34 个 adapter file。 |
| `python -m py_compile scripts/sync-codex-adapters.py scripts/check-agent-harness.py .claude/hooks/pre_tool_guard.py .claude/hooks/format_changed_python.py .claude/hooks/zh_review_advisory.py` | 通过。 |
| `python scripts/sync-codex-adapters.py --check` | 通过：0 issue。 |
| `codex execpolicy check --pretty --rules .codex/rules/default.rules -- sudo ls` | 返回 `forbidden`，匹配 `sudo` 规则。 |
| `codex execpolicy check --pretty --rules .codex/rules/default.rules -- git status --short` | 返回 `allow`，匹配低风险 git inspection 规则。 |
| `codex execpolicy check --pretty --rules .codex/rules/default.rules -- python -m pip install foo` | 返回 `forbidden`。 |
| `codex execpolicy check --pretty --rules .codex/rules/default.rules -- kill 123` | 返回 `prompt`。 |
| `codex execpolicy check --pretty --rules .codex/rules/default.rules -- gh pr create --fill` | 返回 `prompt`。 |
| `python .claude/hooks/pre_tool_guard.py` + synthetic Bash `sudo true` | 预期阻止：exit 2。 |
| `python .claude/hooks/pre_tool_guard.py` + synthetic Bash `python -m pip install foo` | 预期阻止：exit 2。 |
| `python .claude/hooks/pre_tool_guard.py` + synthetic Bash `rm -rf lab/data/foo` | 预期阻止：exit 2。 |
| `python .claude/hooks/pre_tool_guard.py` + synthetic Bash `rm -rf __pycache__` | 通过：exit 0。 |
| `python .claude/hooks/pre_tool_guard.py` + synthetic Bash `git push origin main` | 预期阻止：exit 2。 |
| `CODEX_ALLOW_PUSH_MAIN=1 python .claude/hooks/pre_tool_guard.py` + synthetic Bash `git push origin main` | 通过：exit 0。 |
| `python .claude/hooks/pre_tool_guard.py` + synthetic Codex `apply_patch` 写 `lab/data/foo.txt` | 预期阻止：exit 2，deny protected path。 |
| `python .claude/hooks/pre_tool_guard.py` + synthetic Codex `apply_patch` 写 `README.md` | 通过：exit 0。 |
| `python .claude/hooks/zh_review_advisory.py` + synthetic Codex `apply_patch` | 通过：exit 0。 |
| `python .claude/hooks/format_changed_python.py` + synthetic Codex `apply_patch` | 通过：exit 0。 |
| `python scripts/check-agent-harness.py --strict` | 通过：0 error / 0 warning。 |
| `python scripts/check-anatomy-drift.py` | 通过：扫描 41 个 ANATOMY.md，0 漂移。 |
| `python scripts/validate-governance.py --strict` | 通过：0 error / 0 warning。 |
| `git diff --check` | 通过。 |
| `python .claude/skills/coding-agent-quota/scripts/read_agent_quota.py --format table --codex-jsonl-files 50` | 通过：输出 Codex 与 Claude Code 当前窗口/周额度、reset、source 与 capacity hint。 |
| `python .claude/skills/coding-agent-quota/scripts/read_agent_quota.py --role impl --tier 2 --format table --codex-jsonl-files 50` | 通过：输出 route recommendation、Paseo preference 状态与 provider/model/effort 推荐。 |
| `python .claude/skills/coding-agent-quota/scripts/read_agent_quota.py --role audit --tier 3 --format json --codex-jsonl-files 50` | 通过：JSON 含 providers、usage_velocity、paseo_preferences、route_recommendation。 |
| `python /home/user/.codex/skills/.system/skill-creator/scripts/quick_validate.py .claude/skills/coding-agent-quota` | 通过：Skill is valid。 |
| `python scripts/sync-codex-adapters.py --check` | 通过：0 issue。 |
| `PYTHONDONTWRITEBYTECODE=1 python -m py_compile scripts/check-agent-harness.py .claude/skills/coding-agent-quota/scripts/read_agent_quota.py` | 通过。 |

## Subagent reports

本轮未派生 subagent。

## Open issues / blockers（issue #12 part A，本轮新增）

- **A5 的 fresh-Codex-session runtime smoke 已补齐（2026-07-12，监控员编排真实 Codex gpt-5.6-sol）**：
  用 `git archive main` 铺出真实模板内容到临时 repo、跑 `bootstrap-project.py`，再从该 bootstrapped
  repo 启动一次真实 Codex fresh session 观察：guidance（`AGENTS.md`）与 `.agents/skills/`（21 个）均
  确认可见/可发现；project hook（`format_changed_python.py`/`zh_review_advisory.py`）在 trusted 状态下
  仍未观察到可归因的触发痕迹，如实记录为 unknown（非已确认失效，也非已确认生效）。详见 plan doc A5
  条目与 Plan revision log 最新条目。
- 本分支未 push、未开 PR、未 merge——按边界要求，落地实现后交回上层/human 决定后续 gate。
- issue #12 的 part B（existing-repo 语义归类）与 part C（smoke 合同）按 human 拍板（开放问题 7）
  各自另开分支/worktree/PR，未在本分支涉及；D2c（bootstrap 与 adoption 共用 postflight 渲染函数）
  同样留给 B 落地时决定。

## Open issues / blockers（issue #12 part C，本轮新增）

- 本轮运行环境未预装 PyYAML；`validate-governance.py --strict` 等门禁在裸 `python3` 下会因 4 条
  YAML-related warning 变 `FAIL`（该 warning 在改动前后一致存在，用 `git stash` 验证过是预置环境
  缺口，非本轮改动引入）；本轮验证改用 `uv run --with pyyaml python ...` 绕过，全绿。后续在其他
  机器/CI 上重跑，若已装 PyYAML 应无需此 workaround。
- 真实 repo replay（colorama）只覆盖了「Makefile 检测到、跑失败」这一种真实场景；`pass`（原生测试
  真正跑通过）与 `unknown`（超时）两个 smoke 状态目前只有负向 fixture 层面的合成证据，没有真实
  repo 端到端证据——本机缺 `pytest` 是主因（详见 replay 报告 Follow-ups）。
- B（语义归类）未在本分支涉及；C4 replay 报告里提到的「`adopt-existing-repo.py` 是否该在 scaffold
  时顺带跑一次目标 repo 内的 `sync-codex-adapters.py`」是本轮读代码时发现的一个真实（但明确不在
  本轮范围内）后续问题，已记入 replay 报告 Follow-ups，未擅自实现。
- 本分支未 push、未开 PR、未 merge——按边界要求，落地实现后交回上层/human 决定后续 gate。

## Open issues / blockers

- main 仍未 push；如需共享当前 main，需 human 明确批准 push main。
- `.claude/worktrees/case+agent-r1-adoption-replay/` 与 `.claude/worktrees/case+elf-template-replay/`
  仍是本地 worktree checkout；它们在 main 视角显示为 untracked 是嵌套 worktree 的正常表现。
- Codex project hooks 需要用户信任本 repo 的 `.codex/` layer 后才会加载；新增/修改 hook 后 Codex 也需要按其 hook trust flow 审核。
- `coding-agent-quota` 的 Claude 数据来自本地 usage DB/cache；若 Claude Code 将来改变 `/usage` 存储 schema，脚本会降级为 unavailable/stale，需要按新 schema 更新。

## Exact next steps（issue #12 part A，本轮新增）

1. Human review 本分支改动；决定是否 commit 已 push/开 PR（本 worker 已按边界不做这两步）。
2. ~~找机会从一个真正 bootstrapped 的 repo 里跑一次 fresh Codex session，补齐 A5 缺的 runtime smoke
   证据~~ **已完成（2026-07-12）**，见上方 Open issues 条目。
3. 启动 issue #12 part B（语义归类，`feat/12b-semantic-classification` 建议命名）与 part C（smoke
   合同，`feat/12c-smoke-contract` 建议命名），各自新开分支/worktree，C 先于 B（改动面更小）。

## Exact next steps（issue #12 part C，本轮新增）

1. Human review 本分支改动；决定是否 commit 已 push/开 PR（本 worker 已按边界不做这两步）。
2. 启动 issue #12 part B（existing-repo 语义归类，`feat/12b-semantic-classification` 建议命名），
   新开分支/worktree（当前分支只做 C，未涉及 B1-B6）。
3. B 落地 B6（adoption 完成报告复用双 agent surface 加载清单）时，可考虑是否顺带解决 C4 replay
   报告里记录的 `sync-codex-adapters.py` in-target-repo 后续问题（本轮未做，仅记录）。

## Exact next steps

1. 如需要发布这次双 surface 支持，由 human 决定是否 commit/push main。
2. 后续改 `.claude/agents`、`.claude/skills` 或 `.claude/commands` 时，先跑
   `python scripts/sync-codex-adapters.py`，再跑 validator。
3. 调度 agent 前可运行
   `python .claude/skills/coding-agent-quota/scripts/read_agent_quota.py --format table`
   或显式调用 `$coding-agent-quota`。
4. 若要进一步压测，可用 Codex fresh session 明确调用 `$worktree-pr-flow`、`$command-checkpoint`
   和一个 `.codex/agents/*` custom agent 做端到端 smoke。

## Do-not-forget

- 需要 human 介入/过目的输出默认中文。
- `.claude/` 是 canonical；`.codex/` 与 `.agents/` 是生成/适配层，不手写生成内容。
- 两个 replay case 分支默认作为证据保留，不合入 main。
