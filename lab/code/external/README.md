# lab/code/external/ — 外部 vendored 第三方源码（bytes 不进 Git）

本目录存放为**本地参考 / 复现基线**克隆进来的外部第三方源码（含其自带 `.git`）。

## 规则（`human/decisions/20260709-lab-docs-reference-and-external-vendor-placement.md` F6）

- **bytes 不进 Git**：整个 clone 目录被 `.gitignore` 忽略（`lab/code/external/*`），git 不递归进入；
  只有本 `README.md` 被 track。第三方源码有自己的版本历史，克隆是为参考/复现，不是维护其历史。
- **provenance 唯一真源**：来源 URL、branch、exact commit、baseline commit、可见性、导入方式与理由
  记录在 `lab/docs/reference/provenance.md`。可复现性完全依赖该记录准确。
- 与 `lab/code/imported/`（`adopt-existing-repo` 把已有 repo 收敛成模板形态、bytes 进 Git 的迁移面）
  不同：这里是**只读引用**，不是被收编的一等公民产物。

## 当前内容

| 目录 | 来源 | 用途 | provenance |
| --- | --- | --- | --- |
| `ELF/` | `lillian039/ELF`（ELF: Embedded Language Flows，JAX/TPU 扩散语言模型，MIT） | #83/#88 ELF case v2 刷新的只读复现基线 | `lab/docs/reference/provenance.md#elf` |

> 独立测试者按 provenance 里的 exact commit 重新 `git clone` 即得逐字节一致的源；本目录在
> fresh worktree 检出 case 分支时为空（gitignored），不是缺失。
