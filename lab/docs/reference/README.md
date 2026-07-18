# lab/docs/reference/ — 参考资料 / provenance 平面

`lab/docs/` 三平面之一（`reference/` · `research-narrative/` · `audits/`），用途见
`human/decisions/20260709-lab-docs-reference-and-external-vendor-placement.md`（F5/F6）。

本目录是 leaf 层：只有 `README.md`，不需要独立 `ANATOMY.md`，也不是 validator 校验对象；
对外 claim 仍须能追溯到 `lab/research/evidence.yaml`。

## 内容

- `provenance.md` —— 第三方 vendored 源码（`lab/code/external/`，bytes 不进 Git）的来源、
  exact commit、checksum、license、导入方式记录。是这些外部依赖唯一的可复现真源。

## 约定

- 来源材料可能私密/有版权限制，默认**不假设可提交**；只提交已脱敏的卡片与项目笔记。
- 第三方源码 bytes 走 `lab/code/external/`（gitignored），此处只留 provenance。
