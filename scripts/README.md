# scripts/ — 门禁层

把「不要漂移」做成**可运行检查**，而不是只写成愿望。口头纪律不如 validator。

```bash
python scripts/validate-governance.py        # 总门禁（跑下面两个 + 治理规则）
python scripts/check-agent-harness.py         # 结构 / 必需文件 / 根污染 / 能力索引 / settings / DESIGN 清单
python scripts/check-anatomy-drift.py         # ANATOMY 引用与行号漂移
```

加 `--strict` 让 warning 也算失败（适合 CI）。三个脚本**无第三方依赖**（PyYAML 可选，用于 YAML 深度解析）。

改结构 / 改 doctrine / 改能力后先跑总门禁；PR 前也跑。见 `.agent/repo-editing-guardrails.md`。
