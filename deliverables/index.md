# deliverables/index.md — 交付物索引

所有对外交付物的单一索引。**No overclaim**：每一个对外 claim 都必须在 `lab/research/evidence.yaml` 有支撑；下表的「evidence 齐全」列用来强制这一点。

| id | 类型 | 路径 | 支撑 claim | 状态 | evidence 齐全 |
| --- | --- | --- | --- | --- | --- |
| _(示例)_ | paper | `deliverables/paper/` | `claims.yaml#c1` | draft | 否 |

## 列说明

- **类型**：`paper` / `slides` / `release`。
- **路径**：交付物在 repo 内的位置。
- **支撑 claim**：指向 `lab/research/claims.yaml` 中的 claim id（可多个）。
- **状态**：`draft` / `submitted` / `published`。
- **evidence 齐全**：该交付物引用的每条 claim 是否都在 `lab/research/evidence.yaml` 有证据。**只要有一条 claim 缺证据，就填「否」，且该 claim 在交付物中必须标为 not yet proven 或移除。**

## claim marker（机器可检查）

Markdown 交付物正文中，每个对外 claim 的落点用 HTML 注释显式标记：

```
<!-- claim: id=<claim-id> evidence=<evidence-id>,<evidence-id> -->
```

- `id=` 必填，必须存在于 `lab/research/claims.yaml`。
- `evidence=` 可选，逗号分隔；若填写，每个 id 必须存在于 `lab/research/evidence.yaml`。
- 只覆盖 Markdown 交付物（本文件、`deliverables/*/README.md` 等 `.md` 正文）。
  非 Markdown 交付物（slides、二进制格式）无法嵌 marker，改在 `human/reviews/results/`
  记录人工 review 证据，否则「evidence 齐全」列不得为「是」。
- 校验：`python scripts/check-provenance-chain.py`（由 `validate-governance.py` 拉起）。
  本表的 claim 引用、「evidence 齐全」列与 `claims.yaml` 的一致性也由它机器校验：
  引用不存在的 claim、「齐全=是」但 claim 无 evidence、submitted/published 却非「齐全=是」，
  都会被拦截。
- **「齐全=是」还必须有机器可见的支撑动作（二选一）**：交付物路径下的 `.md` 正文含
  claim marker，或本表该行内引用 `human/reviews/results/` 下**存在的** review 记录
  （可加一列填路径，如 `human/reviews/results/<id>-review.md`；引用不存在的文件判 fail）。
  两者皆无判 fail。豁免仅限两类：占位/示例行；`draft` 状态（尚未对外，允许先标「齐全」，
  提升到 submitted/published 时本检查生效）。

## 纪律

- 交付物不得引入 `evidence.yaml` 之外的结论。
- 提升状态（draft → submitted → published）前，evidence 齐全列必须为「是」，且经 human gate（见 `.agent/human-gates.md`）。
- 无法被 marker 覆盖的正文段落，需在本表或 `human/reviews/results/` 留人工 review 证据。
