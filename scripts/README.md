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
`discover` phase 给每个 root entry 打内置保守四类标签（`template_control_item` /
`conservative_import` / `protected` / `conflict`，v1 不做外部规则文件覆盖），`normalize`
消费这份归类计划而非硬编码判断；`prove` 还会生成 Claude/Codex 双 agent surface 加载清单。
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

`bootstrap-project.py` 是新项目落地工具，也不是 validator：它在目标 repo 内写
`.template.toml`（origin+version 锚点，`--origin` 必须显式传，不推断）、跑
`git config core.hooksPath`、同步 Codex adapters、跑 governance，并把
`lab/docs/audits/template-bootstrap/` state/report 写进目标 repo。第二次以相同 `--origin`
重跑是幂等的；origin 冲突默认报错停止，需要覆盖必须显式加 `--force`。
