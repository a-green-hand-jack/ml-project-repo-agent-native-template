# scripts/ — 门禁层

把「不要漂移」做成**可运行检查**，把「迁移」做成可复验工具，而不是只写成愿望。
口头纪律不如 validator。

```bash
python scripts/validate-governance.py        # 总门禁（harness + anatomy + 治理规则 + 证据链/overclaim）
python scripts/check-agent-harness.py         # 结构 / 必需文件 / 根污染 / 能力索引 / settings / DESIGN 清单
python scripts/check-anatomy-drift.py         # ANATOMY 引用与行号漂移 + 120 行硬上限
python scripts/check-same-commit.py --staged  # same-commit rule：结构改动 <-> ANATOMY 同变更集
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
