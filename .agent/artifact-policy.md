# Artifact 政策

repo 需要 artifact memory，因为 human 会忘记「东西在哪里、哪个 run 还有效、哪个 checkpoint 过期、哪个 table 是旧口径」。保持 repo 干净不是洁癖，是研究记忆压缩。

## 索引文件

```
lab/artifacts/result-index.yaml    结果
lab/artifacts/table-index.yaml     表格
lab/artifacts/figure-index.yaml    图
lab/artifacts/trace-index.yaml     agent/实验 trace
lab/artifacts/model-index.yaml     模型（逻辑索引，bytes 不进 Git）
lab/models/checkpoint-index.yaml   checkpoint
lab/data/dataset-index.yaml        dataset split
deliverables/index.md              对外交付物
```

## 每个资产至少回答

- 在哪里（`location`：路径 / URI）？怎么看（`how_to_inspect`）？
- 对应哪个 commit / config / run id（可复现三元组）？
- 支持哪个 claim / table / figure？
- 状态：`active` / `superseded` / `archived` / `unknown`？
- checksum 是什么？无法校验时为什么（见下）？
- 缺哪些 metadata？何时该归档或删索引？

## provenance 链（机器可检查）

`run → artifact → evidence → claim → deliverable` 由 `scripts/check-provenance-chain.py`
校验（`validate-governance.py` 拉起；三态输出 pass/fail/unknown，unknown 不算 pass）：

- 各 index / ledger YAML 带 `schema_version`（整数，从 1 起，逐 index 独立计数）。
- index 条目离开占位状态后，`commit`/`config`/`run_id` 非占位（全部 7 类统一要求）；
  确无 run 来源的合法场景（外部数据集、human-cc/agent trace、历史遗留）必须**显式豁免**：
  `provenance_unavailable_reason`（固定枚举：`external-origin` / `human-authored` /
  `legacy-untracked`）+ `provenance_unavailable_justification`（非空、非占位的人工具体
  理由）两者都填，不允许静默留空；三元组齐全时再填豁免字段判 fail。`run_id` 已填时须
  指向 `experiment-ledger.yaml` 中已闭环 run（`status: done` + `run_summary` 已填）。
- evidence 的 `metric_source`/`checkpoint`/`data_split` 指向 index 条目 id 时，
  条目必须存在且未 `archived`。
- deliverables 正文的 claim marker：`<!-- claim: id=<claim-id> evidence=<ev-id>,... -->`
  （只覆盖 Markdown；非 Markdown 交付物走 `human/reviews/results/` 人工 review 兜底）。
  「evidence 齐全=是」的非 draft 交付物必须二选一：正文含 claim marker，或在
  `deliverables/index.md` 行内引用 `human/reviews/results/` 下存在的 review 记录；
  两者皆无判 fail（豁免仅限占位/示例行与 draft 状态）。
- release gate 的 `structured_checks`：只把可客观机械验证的 requirement 结构化
  （`artifact-exists` / `checksum-verified` / `run-closed` / `regression-status` /
  `evidence-grade-min`）；价值判断类留自然语言 + human 审批。校验结果仅建议信号，
  `gate_status` 翻转仍是 human 动作；唯一 FAIL 情形：`passed` 却有检查不满足。
  语义：`artifact-exists` 除 index 条目存在外还查 repo 内 `location` 文件真实存在
  （外部/不可达 location 查 checksum/manifest 记录完备）；`checksum-verified` 只在
  validator 真算 sha256 比对通过时满足——checksum 豁免（waived）与登记未校验
  （recorded-unverified）**≠ verified**，豁免不是校验。

## checksum 政策

- 算法统一 **sha256**（`checksum_algorithm` 唯一取值），进程内 `hashlib` 计算，不 shell-out。
- 本地 bytes 可达：validator 真算比对；外部 URI / 集群路径：记录完备（checksum 或
  manifest）即通过，不要求 bytes 进 Git。
- 无法校验必须同时填 `checksum_unavailable_reason`（固定枚举：`external-uri-no-checksum`
  / `pending-upload` / `legacy-untracked` / `oversized-defer-hash`）与
  `checksum_unavailable_justification`（非空、非占位的人工具体理由）。枚举外的值或
  TBD 类占位理由判 **fail**，不是 unknown——这两道关卡防止该字段沦为校验逃逸口。
- 多文件产物可用 `manifest: lab/data/manifests/<id>.yaml`（`files:` 每条 `path`/`uri` +
  `sha256` 或 reason+justification），checksum 落 manifest，不必逐条写进 index。

## 维护方式

不靠 human 记忆。用 `artifact-librarian` agent + `artifact-indexing` skill，在实验结束、table 更新、figure 生成、checkpoint 选择、paper claim promotion 后主动维护索引。

## 结果进入 evidence 的门槛

只有 run 可定位、config 可复现、metric 来源清楚、与 baseline 比较清楚、caveat 写明、且经 fresh verifier 或本人复核，结果才进 `lab/research/evidence.yaml` / `lab/artifacts/result-index.yaml` / 论文。

## bytes 边界

data / checkpoint / run / wandb bytes 不进 Git，只留 index。删除/移动 bytes 走 human gate；agent 只生成归档提案。
