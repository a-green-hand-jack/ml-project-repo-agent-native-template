# Run Summary 模板

每个实验结束后填写。只有满足证据门槛（见 `.agent/artifact-policy.md`）才进 evidence / 论文。
写完后同步 ledger：status 转 `done`/`failed`（`status_history` 追加），`run_summary` 字段指向本文件；
status=done 的闭环（summary 存在 + artifact index 有条目）由 `scripts/validate-experiment-state.py` 校验。

```markdown
# Run Summary

## Run id
## Final status
done / failed / superseded（与 ledger 一致）
## Commit
## Config
## Data
## Checkpoint
## Metrics
## Comparison
## Interpretation
## Failure / caveats
（含 ledger alerts 里发生过的异常与 resume/recovery 记录，如有）
## Artifact links
## Should promote to paper?
yes / no / unclear
```
