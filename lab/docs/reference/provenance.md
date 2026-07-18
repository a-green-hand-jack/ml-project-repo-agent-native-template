# 外部来源 provenance 记录

第三方 vendored 源码（`lab/code/external/`，bytes 不进 Git）的**唯一可复现真源**。
约定见 `human/decisions/20260709-lab-docs-reference-and-external-vendor-placement.md`（F6）。

> 可复现性完全依赖本文件准确：独立测试者按下方 exact commit 重新 `git clone` 即得逐字节一致
> 的源；缺元数据或过期按 `.agent/artifact-policy.md`「缺元数据」精神对待。

---

## ELF

- **source URL**：`https://github.com/lillian039/ELF`（GitHub）
- **可见性**：public（公开仓）
- **项目**：*ELF: Embedded Language Flows* —— 基于 continuous-time Flow Matching 的连续扩散
  语言模型，官方 **JAX/TPU** 实现（arXiv:2605.10938；另有 `pytorch_elf` / `distillation` 分支）
- **license**：**MIT**（`LICENSE`，Copyright (c) 2026 ELF authors）——源码 MIT 许可，但按 F6
  约定 vendored bytes 默认不提交，仅登记 provenance
- **branch**：`main`
- **exact commit（frozen source SHA）**：`5098bf28b5e9b52c329970a7e4e1cc28251c76e6`
  - commit date：`2026-06-26 12:28:29 -0400`，message：`update`
- **HEAD tree SHA（内容锚，可独立核）**：`19cd64ec64537d6eee1df50971c0626f29ffb58a`
- **tracked-file 内容指纹**（`git ls-files -s | git hash-object --stdin`）：
  `bf7ba438f148484bf5d7319400b290b047191053`
- **tracked file 数**：29（16 `.py` 源码 + 7 `.yml` config + 3 图片 asset + LICENSE/README/requirements）
- **clone 时 dirty state**：clean（`git status --porcelain` 0 行）
- **working tree 体积**：~14M（其中 ~13M 是 `assets/` 图示 gif/jpg，非训练 data/model bytes）
- **是否用 LFS**：否（无 `.gitattributes` LFS filter）
- **本地落位**：`lab/code/external/ELF/`（gitignored，见 `lab/code/external/README.md`）
- **导入方式与理由**：#83/#88 ELF case v2 刷新的**只读复现基线**。重新 clone 公共仓，
  形成可由独立测试者从 exact SHA 复验的冻结 handoff；不改上游 bytes、不进 Git。

### 复现命令（独立测试者据此重建逐字节一致的源）

```bash
GIT_LFS_SKIP_SMUDGE=1 git clone https://github.com/lillian039/ELF lab/code/external/ELF
cd lab/code/external/ELF && git checkout 5098bf28b5e9b52c329970a7e4e1cc28251c76e6
# 核对内容锚：
git rev-parse HEAD^{tree}            # 期望 19cd64ec64537d6eee1df50971c0626f29ffb58a
git ls-files -s | git hash-object --stdin   # 期望 bf7ba438f148484bf5d7319400b290b047191053
```

### 冻结的模板侧锚点（case 所测的模板版本）

- 本 case 针对的模板：`ml-project-repo-agent-native-template`
- 模板 VERSION：**v1.3.8**
- case 冻结基线 commit（= 本次 handoff base，`origin/main`）：
  `7c09e90e79c083de1f5db24c593ca40c929cf370`
- 说明：ELF v2 baseline 是在此模板 commit 上落成的；#84/#85 的 replay/probe 以本模板 commit
  为「所测对象」，其精确范围由后续阶段在 ledger v2 条目回填。

---

## 变更日志

- 2026-07-18（#88，干将·迁·ELF基线）：首次登记 ELF v2 复现基线；重新 clone `lillian039/ELF`
  @ `5098bf2`，落位 `lab/code/external/ELF/`（gitignored）。
