# qualification evals

`run-qualification.py` 是 issue #54 / #59（P4，D1-D3）落地的 A 层可重复 qualification
runner，对 G1（9 项静态门禁 validator）与 G6（4 项 Codex adapter parity 承诺）逐 T-ID 跑
「正例 + 负例」：

- 正例：在 `git clone` 物化的干净 fixture（被测 commit = HEAD）上跑 validator，期望全绿。
- 负例：同类隔离 fixture 内注入该 T-ID 指定的一处违规，期望非零退出且报错文本可定位到
  注入点。

fixture 用后即弃；绝不在真实 repo / 任何 worktree 内注入违规，绝不 copytree 任何
worktree（见 `.agent/action-boundary.md` 的 P3 事故教训）。

## 复用优先

G1 的 5 项（T-G1-2/3/6/7/8）对应 validator 已有 `--self-test` 覆盖同等语义的对抗
fixture，runner 直接调用并把其结果登记为证据，不重复造 fixture。其余 8 项（G1 的
T-G1-1/4/5/9 + 全部 G6）由 runner 自建正负例注入逻辑。

## 用法

```bash
python lab/evals/qualification/run-qualification.py --group {g1,g6,all}
```

输出落 `lab/docs/audits/qualification/report-<group>.{json,md}`，含被测 commit sha；
`generated_at`/`worktree_dirty` 之外的字段在同一 commit 上重跑应逐字节一致（D2 可重复性
合同）。runner 本身是评测工具，不是新门禁，不挂进 `validate-governance.py`。

本机裸 `python3` 缺 PyYAML 时，`validate-governance.py --strict` 等门禁会把「跳过 YAML
深度解析」warning 计成 FAIL——这是既有环境缺口（见 `scripts/CLAUDE.md`），不是 runner
或被测 validator 的 bug；runner 统一用 `uv run --with pyyaml python3` 调用子进程校验脚本
绕开。

发现的 validator 缺陷只报告，不在本目录顺手修——见
`memory/branches/54-qualification-runner.md`。
