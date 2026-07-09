# scripts/ — 门禁层

把「不要漂移」做成**可运行检查**，而不是只写成愿望。口头纪律不如 validator。

```bash
python scripts/validate-governance.py        # 总门禁（跑下面两个 + 治理规则 + 证据链/overclaim）
python scripts/check-agent-harness.py         # 结构 / 必需文件 / 根污染 / 能力索引 / settings / DESIGN 清单
python scripts/check-anatomy-drift.py         # ANATOMY 引用与行号漂移 + 120 行硬上限
python scripts/check-same-commit.py --staged  # same-commit rule：结构改动 <-> ANATOMY 同变更集
```

加 `--strict` 让 warning 也算失败（适合 CI）。脚本**无第三方依赖**（PyYAML 可选，用于 YAML 深度解析）。

`check-same-commit.py` 不进 `validate-governance`（它需要 diff 上下文，干净 checkout 上会 no-op）。
两处接入：**pre-commit hook**（`.githooks/pre-commit`，每 clone 一次性启用 `git config core.hooksPath .githooks`）+ **CI**（对 PR base / push before 跑 `--against <ref>`）。逃生 `SAME_COMMIT_SKIP=1` / `git commit --no-verify`。

改结构 / 改 doctrine / 改能力后先跑总门禁；PR 前也跑。见 `.agent/repo-editing-guardrails.md`。
