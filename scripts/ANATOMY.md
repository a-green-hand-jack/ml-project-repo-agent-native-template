---
related_files:
  - ../ANATOMY.md
  - check-agent-harness.py
  - check-anatomy-drift.py
  - check-capability-catalog.py
  - check-doc-lifecycle.py
  - check-outcome-ledger-schema.py
  - check-provenance-chain.py
  - validate-governance.py
  - validate-experiment-state.py
  - adopt-existing-repo.py
  - check-adoption-integrity.py
  - bootstrap-project.py
  - _agent_surface.py
  - sync-codex-adapters.py
  - bump-template-version.py
  - template-sync.py
  - agent-state.py
  - agent-status.py
  - agent-mailbox.py
  - check-agent-conflicts.py
  - ../template-manifest.toml
  - ../VERSION
maintenance: |
  新增/删除检查脚本时同 commit 更新本表。检查项与 .agent/ doctrine 对应关系变化时也更新。
---

# scripts/ ANATOMY

## What this is

repo 的可运行门禁层、迁移工具层与新项目落地工具层。validator 无第三方硬依赖，只读、只报告、返回退出码；
adoption 脚本用于把外部 repo 收敛成本模板形态，并自带 proof/integrity 检查；bootstrap 脚本用于把刚
派生的新 repo 落地成自洽状态（有写副作用，见 `CLAUDE.md`）；
Codex adapter 同步脚本把 `.claude/` canonical 能力生成到 `.codex/` 与 `.agents/`。

## Components

| 文件 | 角色 | 对应 doctrine |
| --- | --- | --- |
| `check-agent-harness.py` | 结构/必需文件/根污染/四件套/能力索引/settings/DESIGN 清单 校验 | `.agent/repo-editing-guardrails.md` · `repo-documentation-topology.md` |
| `check-anatomy-drift.py` | ANATOMY related_files 与 line citation 漂移 + 120 行硬上限 | `.agent/anatomy-protocol.md` |
| `validate-governance.py` | 聚合 harness/anatomy/doc-lifecycle/outcome-ledger/实验状态/provenance-chain/capability-catalog 七个子检查 + gitignore/YAML/tracked-bytes + 证据链一致性(overclaim 拦截) | `.agent/action-boundary.md` · `artifact-policy.md` · `principles.md` |
| `check-capability-catalog.py` | 声明式能力目录 `.agent/capability-catalog.toml` ↔ 真实 `.claude/` 能力面 ↔ 生成 adapter 的三向一致：登记齐全(missing)/无幽灵条目(unexpected)/adapter parity + schema(profile=research, chassis-spec pin/compatibility)；`--self-test` 跑内嵌对抗 fixture | `.agent/tool-skill-interface.md` · `.agent/capability-catalog.toml` · issue #28 |
| `check-doc-lifecycle.py` | brief/plan/review/decision 生命周期：唯一顶部状态锚点↔注册表一致、引用完整、活跃 plan 的 issue/Git branch/worktree 关联、进阶态证据、过期 approval；validator 在 commit 粒度权威校验跨文件一致性，`pretooluse_reason()` 只拦单次写入局部不完整并对常见 Bash 删除模式尽力兜底；`--self-test` 跑内嵌对抗 fixtures | `plans/ANATOMY.md` · `plans/20260712-plan-lifecycle-state.zh.md` |
| `validate-experiment-state.py` | 实验状态机（planned→approved→running→done/failed→superseded，经 status_history 逐步校验）+ approved 必填字段 + alert command/workdir、批准审计与 provenance/consume/execution/resolved 不变量 + done 闭环（run summary 路径/regular-file 安全）。PyYAML 可选（内置受限 block-style 解析器回退）；`--self-test` 内嵌对抗 fixture | `plans/20260712-experiment-control-plane.zh.md` · `.agent/human-gates.md` |
| `check-provenance-chain.py` | provenance 链：run→artifact→evidence→claim→deliverable；双向 claim/evidence 归属边、行级 marker 覆盖、run 闭环、checksum（sha256）、active-only gate artifact、安全 repo-relative regular-file path、dataset split、ID 唯一性；active/submitted/passed 状态 fail-closed，`--self-test` 跑内嵌对抗 fixture | `.agent/artifact-policy.md` |
| `check-same-commit.py` | same-commit rule：结构改动(A/D/R)未同变更集更新对应 ANATOMY → 拦。diff 驱动，不进 governance；由 `.githooks/pre-commit` + CI 调用 | `.agent/anatomy-protocol.md` |
| `check-outcome-ledger-schema.py` | outcome ledger/fixture schema、decision↔outcome 生命周期、完整具体路线证据隔离、正样本地板/零样本与 stale fallback、replay 确定性、credential/写边界防线；经 importlib 复用 skill 内 `outcome_ledger.py` | `.agent/model-routing-policy.md` · `plans/20260712-outcome-aware-routing.zh.md` |
| `adopt-existing-repo.py` | 分 phase 迁移已有 Git repo：discover（语义归类，B1-B3）/baseline/scaffold/normalize（消费归类计划，B4）/prove（含双 agent surface 报告，B6） | `plans/20260709-adopt-existing-repo.zh.md` · `plans/20260712-bootstrap-adoption-proof.zh.md` · `.claude/skills/adopt-existing-repo/SKILL.md` |
| `check-adoption-integrity.py` | 读取 adoption baseline，按 hash 证明原 tracked bytes 仍存在 | `.claude/skills/adopt-existing-repo/SKILL.md` |
| `bootstrap-project.py` | 把刚从模板派生的新 repo 落地：`.template.toml` 锚点、`core.hooksPath`、Codex adapters 同步、governance，幂等；需 human 信息的步骤只报告不代做 | `plans/20260712-bootstrap-adoption-proof.zh.md` · `.claude/skills/bootstrap-project/SKILL.md` |
| `_agent_surface.py` | 非独立脚本（无 `__main__`）：`bootstrap-project.py`（A4）与 `adopt-existing-repo.py`（B6）共用的 Claude/Codex postflight 渲染函数，避免两套加载清单文案/判定漂移 | `plans/20260712-bootstrap-adoption-proof.zh.md`（D2c） |
| `sync-codex-adapters.py` | 从 `.claude/agents` / `skills` / `commands` 生成并校验 Codex adapters | `.agent/tool-skill-interface.md` |
| `bump-template-version.py` | 按 agent 判定的 level 递增 `VERSION`、更 `CHANGELOG.md`、打本地 git tag | `.agent/template-versioning-policy.md` |
| `template-sync.py` | 下游按 `template-manifest.toml` 追平上游框架层，分阶段事务：preflight/plan/apply/verify/commit-version。可观察行为承诺（rule id TS-1..TS-9：来源身份、major gate、五类 ownership、dry-run/apply 共用 plan、generated 全集语义、验收先于推进、receipt 四态、原子写/中断如实、幂等重跑）的**唯一规范正文 owner** 是 `.agent/template-versioning-policy.md`「template-sync 可观察 Contract」一节，本行只反向链接、不复制正文 | `.agent/template-versioning-policy.md` · `template-manifest.toml` |
| `agent-state.py` | 多 agent 控制面状态文件（`memory/agents/<name>.yaml`）写侧 + 格式唯一 owner（解析/staleness/root 锚定 helpers） | `.agent/multi-agent-control-plane.md` |
| `agent-status.py` | 只读 list/status：roster + 状态 yaml + 可选 `paseo ls` presence，30min TTL 派生 stale | `.agent/multi-agent-control-plane.md` |
| `agent-mailbox.py` | agent 间消息/handoff 落盘（inbox/outbox 对、decision/handoff 强制 ref、ack 转移 ownership） | `.agent/multi-agent-control-plane.md` |
| `check-agent-conflicts.py` | ownership 重叠扫描 + 写错-worktree 检测 + `pretooluse_reason()` 供 hook 写入前拦截 | `.agent/multi-agent-control-plane.md` |

## Connections

Inbound:
- `.github/workflows/` CI 调用 `validate-governance.py --strict` 与 `check-same-commit.py --against`。
- `.githooks/pre-commit` 调用 `check-same-commit.py --staged`。
- `.claude/settings.json` 与 `.codex/rules/default.rules` 把关键脚本列入 allow。
- `.claude/commands/adopt-existing-repo.md` 与 `.claude/skills/adopt-existing-repo/SKILL.md`
  调用 adoption 脚本；`lab/evals/adoption/run-adoption-smoke.py` 是它的 27 场景 synthetic fixture，
  同时覆盖 B 的语义归类/安全边界与 C 的结构化 smoke 合同。
- `.claude/skills/bootstrap-project/SKILL.md` 调用 `bootstrap-project.py`；
  `lab/evals/bootstrap/run-bootstrap-smoke.py` 是它的 synthetic fixture。
- `lab/evals/template-sync/run-template-sync-smoke.py` 是 `template-sync.py` 的故障注入 fixture
  （generator fail / validator fail / 原子 version-write fail / 未分类/无哨兵 warning / MAJOR gate /
  成功幂等重跑；五类路径正负例）；它把本脚本复制进合成下游、用 stub 生成器/validator 端到端驱动。
- `.codex/agents/*.toml` 与 `.agents/skills/*/SKILL.md` 由 `sync-codex-adapters.py` 生成。

Outbound:
- `validate-governance.py` 以 subprocess 调用 harness/anatomy/doc-lifecycle/outcome-ledger/
  experiment-state/provenance-chain/capability-catalog 七个子检查（用 `sys.executable`）。
- `check-agent-harness.py` 另有能力目录存在性地板（`check_capability_catalog`），与
  `check-capability-catalog.py` 的完整 parity 校验互补。
- `.claude/hooks/pre_tool_guard.py` 通过 `importlib` 加载 `check-doc-lifecycle.py` 的
  `pretooluse_reason()`，hook 与 validator 共用 parser 和局部判定；coverage 与跨文件一致性只由
  validator 在 commit/治理门禁粒度检查。
- `check-adoption-integrity.py` 通过 `importlib` 加载 `adopt-existing-repo.py` 的
  `integrity_result()`，避免两份 hash 逻辑漂移。
- `agent-status.py` / `agent-mailbox.py` / `check-agent-conflicts.py` 通过 `importlib` 加载
  `agent-state.py` 的解析/staleness/root helpers（同一先例）；`.claude/hooks/pre_tool_guard.py`
  与 `agent_name_set.py` 反向以 `importlib` 薄接线加载本目录的 `check-agent-conflicts.py` /
  `agent-state.py`（冲突拦截与状态初始化）。
- `bootstrap-project.py` 与 `adopt-existing-repo.py` 都通过 `importlib`（同 `_load_sibling()`
  helper）加载 `_agent_surface.py` 的 `agent_surface_checklist()`，共用同一份 Claude/Codex
  postflight 渲染逻辑（D2c）。
- `lab/infra/launch/expctl.py` 通过 `importlib` 复用 `validate-experiment-state.py` 的
  `load_yaml`（PyYAML 优先 + 受限解析器回退），避免两份 YAML 解析逻辑漂移。

## Notes

- validator 只能挡结构性漂移（missing file / out-of-range line / 根污染 / 误 track bytes）；语义正确性仍需 human/agent 打开代码验证。
- 退出码：0 通过，1 失败；`--strict` 让 warning 也算失败（用于 CI）。
