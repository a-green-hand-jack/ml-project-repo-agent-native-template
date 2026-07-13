# scripts/ — 门禁层

把「不要漂移」做成**可运行检查**，把「迁移」做成可复验工具，而不是只写成愿望。
口头纪律不如 validator。

```bash
python scripts/validate-governance.py        # 总门禁（harness + anatomy + provenance + 治理规则 + 证据链/overclaim）
python scripts/check-agent-harness.py         # 结构 / 必需文件 / 根污染 / 能力索引 / settings / DESIGN 清单
python scripts/check-anatomy-drift.py         # ANATOMY 引用与行号漂移 + 120 行硬上限
python scripts/check-provenance-chain.py      # provenance 链 + 安全路径 + fail-closed gate；--self-test 跑内嵌对抗 fixture
python scripts/check-same-commit.py --staged  # same-commit rule：结构改动 <-> ANATOMY 同变更集
python scripts/check-outcome-ledger-schema.py # outcome schema / 具体路线隔离 / 正样本与 fallback / 写入与 credential 防线
python scripts/sync-codex-adapters.py --check # Codex adapters 与 .claude canonical 能力是否同步
python scripts/adopt-existing-repo.py <repo> --phase all  # 迁移已有 repo 到 template 形态
python scripts/check-adoption-integrity.py <repo>         # 校验 adoption baseline bytes 仍存在
python scripts/bootstrap-project.py <new-repo> --origin <owner/repo>  # 落地刚派生的新 repo（幂等）
python scripts/bump-template-version.py --level minor --note "..."   # 发版：递增 VERSION + tag（上游）
python scripts/template-sync.py --from /path/to/upstream             # 追平上游框架层（下游）
python scripts/agent-status.py                # 多 agent 控制面：谁在跑/状态/心跳/未读（只读）
python scripts/agent-state.py register "<name>" --task "..." --owned <paths>  # 登记状态/心跳
python scripts/agent-mailbox.py send|inbox|handoff|ack ...   # agent 间消息与 ownership handoff 落盘
python scripts/check-agent-conflicts.py scan  # 活跃 agent owned_paths 重叠扫描（写入前拦截的判定本体）
```

上下游同步闭环（`bump-template-version.py` + `template-sync.py`）见 `.agent/template-versioning-policy.md`：
上游发版打 tag，下游按 `template-manifest.toml` 分类追平（framework 覆盖 / project 保护 / merge 换哨兵块），
MAJOR 跨越需 `--allow-major` 人工确认。

加 `--strict` 让 warning 也算失败（适合 CI）。脚本**无第三方依赖**（PyYAML 可选，用于 YAML 深度解析）。

`validate-governance.py` 还包含 `check_release_gates()` / `check_regression_matrix()`：校验
`lab/research/release-gates.yaml` / `regression-matrix.yaml` 的枚举字段合法，且一旦
`gate_status` / `last_status` 离开占位默认值（`open` / `unknown`），对应的 `for_claim` /
`guards_claim` 必须指向 `claims.yaml` 中真实存在的 claim（而非未填占位符或不存在的 id）。
仍处于占位默认状态时跳过引用校验，模板 scaffold 天然通过。

`check-provenance-chain.py`（`validate-governance.py` 的子检查，也可单独跑）校验
run→artifact→evidence→claim→deliverable 的 provenance 链：引用完整性、run 闭环
（`status: done` + `run_summary`）、checksum（统一 sha256，进程内 hashlib；无法校验需
固定枚举 reason + 非占位人工理由，否则判 fail）、deliverables 的 claim marker
（`<!-- claim: id=... -->`，核对 supports_claim 归属与行级 claim 覆盖）、安全 repo-relative
regular-file path、dataset split membership 与 duplicate ID。claim/evidence 归属边必须双向完整；
release-gate 的 artifact-exists / checksum-verified 只接受 active artifact。active/submitted/passed
状态不接受 placeholder；passed gate 遇 unknown 也 fail-closed。三态输出：pass / fail / unknown，unknown 不算 pass，
`--strict` 下 unknown 也算失败。字段与枚举定义见 `.agent/artifact-policy.md`。

`check-same-commit.py` 不进 `validate-governance`（它需要 diff 上下文，干净 checkout 上会 no-op）。
两处接入：**pre-commit hook**（`.githooks/pre-commit`，每 clone 一次性启用 `git config core.hooksPath .githooks`）+ **CI**（对 PR base / push before 跑 `--against <ref>`）。逃生 `SAME_COMMIT_SKIP=1` / `git commit --no-verify`。

改结构 / 改 doctrine / 改能力后先跑总门禁；PR 前也跑。见 `.agent/repo-editing-guardrails.md`。

`adopt-existing-repo.py` 是迁移工具，不是 validator：它会在目标 repo 内写入
`lab/docs/audits/template-adoption/` state/report，并按 conservative policy 保留原文件。
`prove` phase 的 exit code（`check-adoption-integrity.py` 同理）只反映 adoption 工具自身完整性
（tracked-byte hash 一致 + 无未解决的 conflict/受保护路径 blocker）；被迁移项目自身原生测试的
smoke 结果（`pass`/`fail`/`skipped`/`unknown`）与该 exit code 解耦，非 pass 时以 report/`--json`
里显式的 `warnings`/`smoke_warnings` 字段呈现，不会被静默吞掉（见
`plans/20260712-bootstrap-adoption-proof.zh.md` 开放问题 5）。

`discover` phase 给每个 root entry 打内置保守四类标签（`template_control_item` /
`conservative_import` / `protected` / `conflict`，v1 不做外部规则文件覆盖），`normalize`
消费这份归类计划而非硬编码判断。归类计划只视为提案：`normalize` 会先对当前全部 root entry
重算 kind/category/blocker/target_path、检查 discover 后未在 classification 或
`scaffold_control_items` 声明中登记的新增项，并在默认模式下完成整轮预检后
才开始搬移；伪造 `template_control_item` 不能绕过 nested protected scan。`prove` 还会生成
Claude/Codex 双 agent surface 加载清单。
所有 repo 内写路径（state / report / 冲突归档 / 移动目的地）用 `safe_target_path` 逐段
lstat；canonical state 的三个叶文件也参与检查，命中 symlink 时 state/report 改道到
确定性的 `/tmp` fallback 并登记 blocker。fallback 在使用前从绝对路径根逐段检查到状态
叶文件；fallback 根、中间段或叶节点命中 symlink 时直接 fail-closed，不做二次改道。
归档/移动路径命中 symlink 同样直接拒绝。**Residual risk（已接受）**：lstat/resolve 检查与随后的
mkdir/copy/move 不是原子操作 —— 上述保护均以「运行期间目标 repo 无并发敌对修改」
为前提（TOCTOU），不要对一个正被其他进程改写的 repo 跑 adoption。

`_agent_surface.py` 不是独立脚本（没有 `__main__`），是 `bootstrap-project.py` 与
`adopt-existing-repo.py` 共用的 Claude/Codex postflight 渲染 helper，通过 `importlib`
按路径加载（同 `check-adoption-integrity.py` 加载 `adopt-existing-repo.py` 的模式）。

多 agent 控制面四脚本（`agent-state` / `agent-status` / `agent-mailbox` / `check-agent-conflicts`）
见 `.agent/multi-agent-control-plane.md`：状态/mailbox 内容是运行时（gitignored），各脚本自带
`--self-test`（内嵌 fixtures，无外部 fixture 目录）；`check-agent-conflicts.py` 的
`pretooluse_reason()` 由 `.claude/hooks/pre_tool_guard.py` 在写入前调用（冲突/写错-worktree 拦截）。
冲突检测本轮**不**进 `validate-governance`（human 拍板：先验证写入前 hook 有效，再评估 validator 层）。

`bootstrap-project.py` 是新项目落地工具，也不是 validator：它在目标 repo 内写
`.template.toml`（origin+version 锚点，`--origin` 必须显式传，不推断）、跑
`git config core.hooksPath`、同步 Codex adapters、跑 governance，并把
`lab/docs/audits/template-bootstrap/` state/report 写进目标 repo。第二次以相同 `--origin`
重跑是幂等的；origin 冲突默认报错停止，需要覆盖必须显式加 `--force`。
