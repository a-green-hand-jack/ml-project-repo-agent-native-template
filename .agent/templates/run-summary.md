# Run Summary 模板

每个实验结束后填写。只有满足证据门槛（见 `.agent/artifact-policy.md`）才进 evidence / 论文。
写完后存为 `lab/code/experiments/<run-id>.md` 并同步 ledger：status 转 `done`/`failed`
（`status_history` 追加），`run_summary` 字段必须是该目录内的 repo-relative、非 symlink
regular file；status=done 的闭环（安全 summary + artifact index 条目）由
`scripts/validate-experiment-state.py` 校验。

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
