# current-status.md

> **活文件**。这是当前状态的单一真相源。每次 session 结束、compact 前、完成小目标时更新。
> fresh session 应能只读本文件 + `session-tree.md` 就接续工作。

## 当前 plan 指针（doc-lifecycle，fresh session 先看这里）

- 当前活跃 plan：`plans/20260712-plan-lifecycle-state.zh.md`（issue #13）· status: **implementing** ·
  branch `feat/13-plan-lifecycle-state`（worktree `.claude/worktrees/13-plan-lifecycle-state`）。
- 真实 runtime 验收已 8/8 PASS：C1-C3/X1-X3 的 continuity/context 目标为 `68f1d43`；
  fresh review 后变更的 guard G1/G2 已在精确代码 `06c98f2` 的新 disposable clones 中重跑。
  raw 转录、debug log 与 sha256 见 `lab/evals/doc-lifecycle/evidence-20260713-runtime-probes.md`。
  当前只剩 evidence-only HEAD 严格门禁与 fresh exact-head review；未 APPROVE 前不标 verified、不合入。
- 权威状态注册表：`memory/doc-lifecycle.yaml`（brief/plan/review/decision 四类统一，语义见 `plans/ANATOMY.md`）。
- 其余存量 plan 均已 `verified`，decisions 均 `approved`（详见注册表）。
- 本节由 agent 在状态流转时更新；compact/clear 后 `context_continuity.py` 会把本文件回注新上下文。

## 当前 objective

把模板从 Claude-Code-native 扩展为 Claude Code + Codex 都可直接使用的 agent-native 模板。
最新一轮新增 `coding-agent-quota` repo-local skill，用本地 usage snapshot 读取 Codex /
Claude Code 当前窗口与周额度，并把 `subagent-routing` / `subagent-router-agent` 升级为
配额感知的 provider/model 路由；验证已通过。

## Constraints

- 遵守 `AGENTS.md` / `.agent/AGENTS.md` / `.agent/action-boundary.md`。
- 不编辑或删除 `lab/data/**`、`lab/runs/**`、`lab/models/**` bytes、`checkpoints/**`、`wandb/**`、
  `lab/infra/private/**`、`.env`。
- 不启动/kill/restart 长训练或远端作业。
- 不 push main、不开 PR、不 release。
- 两个 replay case worktree/branch 继续作为证据保留，不合入 main。

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

## Open issues / blockers

- main 仍未 push；如需共享当前 main，需 human 明确批准 push main。
- `.claude/worktrees/case+agent-r1-adoption-replay/` 与 `.claude/worktrees/case+elf-template-replay/`
  仍是本地 worktree checkout；它们在 main 视角显示为 untracked 是嵌套 worktree 的正常表现。
- Codex project hooks 需要用户信任本 repo 的 `.codex/` layer 后才会加载；新增/修改 hook 后 Codex 也需要按其 hook trust flow 审核。
- `coding-agent-quota` 的 Claude 数据来自本地 usage DB/cache；若 Claude Code 将来改变 `/usage` 存储 schema，脚本会降级为 unavailable/stale，需要按新 schema 更新。

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
