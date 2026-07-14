# evals/template-sync

`scripts/template-sync.py` 的故障注入 synthetic smoke（issue #35）。

```bash
python lab/evals/template-sync/run-template-sync-smoke.py
```

在临时目录里搭一对合成的「上游 template + 下游 repo」，把**真实**的
`scripts/template-sync.py` 复制进合成下游（使其 `DOWNSTREAM` 解析到临时 repo），
并用 stub 的 `sync-codex-adapters.py` / `validate-governance.py` 控制生成器/validator 的退出码，
端到端验证事务合同：

- **happy + 幂等**：framework 覆盖 / 相同 framework 不重写 / generated 不裸拷但重建生成器会跑 /
  project 字节保留 / scaffold 缺才建、已存在则保留 / merge 只换哨兵块且块外内容保留；
  版本原子推进到上游版本，receipt `result=pass`；紧接着重跑幂等（仍 pass、版本不动、零写入）。
- **generator_fail / validator_fail**：进程非零、`result=partial`、`.template.toml` 仍是旧版本
  （这正是本 issue 修复的 bug：版本不得在生成器/validator 成功前推进），failure 段给出可重跑命令。
- **warnings**：未分类上游文件 + 无哨兵 merge 文件 → `result=partial`（永不 pass），validator 通过
  时版本仍推进但如实标 partial；无哨兵文件不被误建。
- **timeout_unknown**：validator 在 `--timeout` 内不返回 → `result=unknown`（永不 pass）、版本不动、
  进程非零（超时/中断/unknown 不能显示为 pass）。
- **major_gate**：MAJOR 且无 `--allow-major` 是严格 pre-write no-op（exit 2、版本不动、不写 receipt）；
  加 `--allow-major` 后推进。
- **atomic_write**（进程内）：注入 `os.replace` 失败，断言 `.template.toml` 保持旧的、可解析的值，
  且无孤儿临时文件——version-write 中断绝不留半行。

无第三方依赖；无外部 fixture 目录，所有 case 现搭现拆。
