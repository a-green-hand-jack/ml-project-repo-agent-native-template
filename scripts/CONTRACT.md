---
name: template-sync
contract_version: 2
root_contract: ../CONTRACT.md
contract_for:
  - component: template-sync
    anatomy: scripts/ANATOMY.md
related_files:
  - template-sync.py
  - sync-codex-adapters.py
  - init-governance-data.py
  - ANATOMY.md
  - ../template-manifest.toml
  - ../lab/evals/template-sync/run-template-sync-smoke.py
  - ../lab/evals/bootstrap/run-bootstrap-smoke.py
  - ../.agent/template-versioning-policy.md
---

# template-sync CONTRACT

本文件是 `template-sync` component（`scripts/template-sync.py`，④ 同步站）可观察行为的
**唯一规范正文 owner**（issue #33 建立，issue #48 v4 S3 从 `.agent/template-versioning-policy.md`
迁移到本文件；见 root [`CONTRACT.md`](../CONTRACT.md) 的受治理组件索引）。
`scripts/ANATOMY.md` 的 `template-sync.py` 行只反向链接本文件，不复制规则正文；
`.agent/template-versioning-policy.md` 同理只保留一行链接，不复制。

反向链接：implementation `template-sync.py`；分类真源 `../template-manifest.toml`；
production-path fault-injection evidence
`../lab/evals/template-sync/run-template-sync-smoke.py`
（`python3 lab/evals/template-sync/run-template-sync-smoke.py`，复制真实脚本驱动，非
fake/parser-only）。TS-10（`sync-codex-adapters.py --check` 的 context 合同）的真实 Git
fixture evidence 单独在 `../lab/evals/bootstrap/run-bootstrap-smoke.py`（复用 bootstrap 已有的
`git archive HEAD` + 真实 harness 基础设施，不重铺第二套 fixture owner）。

规则 id 稳定、粗粒度（不拆成微规则）；每条给出 evidence kind 与具体 scenario/function，
不接受「见测试文件」这类无具体指向的引用。

## Contract rules

| id | 规则（可观察义务） | evidence kind | evidence |
| --- | --- | --- | --- |
| **TS-1** source-input | 每次 sync 的 `source` 必含 sha256 `content_digest`；上游若是 git 仓库，额外记录 40 位 HEAD SHA 与如实的 `dirty` 标记，且被同步的是当前工作树（含未提交改动）字节，不是「假装 clean 的 SHA」 | production-path positive | `check_dirty_upstream_source`（git+dirty 分支）、`check_happy_and_idempotent`（`source.content_digest` 断言，非 git 分支） |
| **TS-2** major-gate | MAJOR 跨越且无 `--allow-major` 是严格 pre-write no-op：exit 2、版本不动、不写任何文件、不写 receipt；带 `--allow-major` 才推进 | production-path positive + forbidden | `check_major_gate`（阻断分支断言零写入/无 receipt；放行分支断言推进） |
| **TS-3** five-path-classes | 五类 ownership：framework 仅在字节不同才覆盖（相同则不重写）；project 永不触碰；scaffold 缺失才建、已存在则保留；generated 在 apply 阶段绝不裸拷贝，只由下游生成器重建；merge 文件只替换 `template:begin/end` 哨兵块内，块外内容保留 | production-path positive + forbidden | `check_happy_and_idempotent` 的五类正/负断言段；`check_root_contract_framework`（root `CONTRACT.md` 作为 framework 的 missing/stale/dry-run/receipt/幂等回归） |
| **TS-4** dry-run-shares-plan | `--dry-run` 与 `apply` 走同一条 `plan_sync()`/classify 路径计算计划，不存在会漂移的第二套「预览」实现；`receipt.manifest.expected` 必须等于同一 fixture 下真实 apply 会写入的路径集；dry-run 全程零下游 side effect（不跑生成器/validator、不推进版本、不改任何被同步文件），唯一例外是显式 `--receipt PATH` 时只写这一个文件 | production-path positive + forbidden | `check_dry_run_no_side_effect`（真实 CLI 端到端：断言 planned 路径集与 `check_happy_and_idempotent` 里同一 fixture 的真实 apply 写入集一致、exit 0、零文件/生成器/版本副作用、仅显式 receipt 路径被写出） |
| **TS-5** generated-full-set | 上报的 `generated` manifest（`expected`/`actual`/`actual_changed`/`missing`/`unexpected`/`content_mismatches`）是**完整 post-generator 下游快照**的分类结果，不是本次生成器 delta；路径存在但字节错 → `content_mismatches`，永不算 `missing`；运行前已存在、本次生成器未触碰的 rogue 文件仍算 `unexpected`。对 Codex adapter surface，`.claude` 源到生成路径的 config/rules/navigation 不能误列 generated（分类真源仍是 `template-manifest.toml`，见 TS-10 关于 `sync-codex-adapters.py --check` 自身 tracked-set 语义的 context 划分） | production-path positive + forbidden | `check_generated_missing`、`check_generated_wrong_bytes_content_mismatch`、`check_generated_arbitrary_unexpected`、`check_generated_stale_rogue_unexpected`、`check_adapter_ownership_exact_set` |
| **TS-6** validate-before-commit | 阶段固定顺序 apply → generated_rebuild → validate → commit_version；仅当前面全部 `ok` 时 `commit_version` 才可能 `ok`；生成器/validator 失败或 `--no-verify` 跳过时版本必须保持旧值，`commit_version` 为 `skipped` 或非 `ok` | production-path positive + forbidden | `check_generator_fail`、`check_validator_fail`、`check_no_verify_no_advance` |
| **TS-7** receipt-result-states | apply-run（非 `--dry-run`）的 receipt `result` 只有四态：`pass`（全部阶段 ok 且无 warning）、`partial`（某阶段失败/跳过，或 validator 通过但有 warning——未分类路径/无哨兵 merge 文件）、`unknown`（超时/中断等不确定结果，永不显示为 `pass`）——`fail` 与 `unknown` 均不得被误记为 `pass`；`--dry-run` 是独立的第五态 `result="dry-run"`，与前述四态互斥、不参与 pass/partial/fail/unknown 判定 | production-path positive | `check_happy_and_idempotent`（pass）、`check_warnings_partial`（validator 通过但 partial）、`check_generator_fail`/`check_validator_fail`（阶段失败 partial）、`check_timeout_unknown`/`check_interrupt_unknown`/`check_commit_interrupt`（unknown）、`check_dry_run_no_side_effect`（dry-run） |
| **TS-8** atomic-commit-and-interrupt-honesty | 版本文件用「同目录临时文件 + `os.replace`」写入；替换前失败/中断保持旧值、无孤儿临时文件、旧值仍可解析；替换后中断必须如实报告 `version_advanced=true` 且 `result=unknown`，不得声称 `version_kept`/伪造 rollback | production-path positive + forbidden | `check_atomic_write_fail`、`check_commit_interrupt`（before/after 两支） |
| **TS-9** idempotent-rerun | 对已追平的下游立即重跑是真正 no-op：`result` 仍 `pass`、版本不动、`apply_changed` 为空 | production-path positive | `check_happy_and_idempotent` 的幂等重跑段 |
| **TS-10** adapter-check-context（issue #67） | `sync-codex-adapters.py --check` 的 generated manifest 断言按 `--context {source,downstream,auto}` 区分合同：`source` 保留 #61 的 tracked exact-set（generated manifest 精确等于 `expected_files()`）；`downstream` 不要求已 `git add`，只要求 `template-manifest.toml` 把每个 expected adapter path 分类为 generated，正确但未跟踪的输出必须 PASS；`auto`（CLI 默认）按 `.template.toml` 角色锚点判定 source/downstream，锚点是 symlink 或无法解析为合法 TOML 时 fail-closed（非零退出、明确报错），绝不静默降级为较弱检查；磁盘 missing/stale/unexpected 检查对两种 context 都无条件执行；`write()` 输出区分实际 changed 计数与 expected 总数，不再无论是否改动都声称写了全部 | production-path positive + forbidden，真实 `git init` fixture（非 mock） | `check_untracked_generated_adapters`（`lab/evals/bootstrap/run-bootstrap-smoke.py`：真实 adopt-style 未跟踪 adapters 下 downstream PASS、显式 source 仍 FAIL、missing/stale/unexpected 仍 FAIL、malformed/symlink 锚点 fail-closed） |
| **TS-11** governance-data-gap-report（issue #63 D1） | apply 后若 plan 里存在新创建（此前下游不存在）、匹配 `scripts/check-*.py`/`scripts/validate-*.py` 的 framework 文件，receipt 新增 `governance_data_gap` 字段：`new_validators`（新落地路径清单）+ `gap`（`init-governance-data.py --dry-run` 的诚实 changed/skipped/flagged 计数，脚本不存在或预览异常时为 `null`/`{"error":...}`，不影响 sync 本身结果）+ `suggested_command`；validator 已存在（本次 action≠create）时 `governance_data_gap` 为 `null`；template-sync 全程绝不自动执行 init（下游数据文件字节不变） | production-path positive + forbidden | `check_governance_data_gap_report`（首次落地 3 个 G1 validator 断言字段与 gap 计数非空、命中已知缺口、数据文件未被动过；第二次同步已存在 validator 断言字段为 `null`） |

## template-sync Contract 变更矩阵（breaking vs non-breaking）

沿用 `.agent/template-versioning-policy.md` 的 semver 判级表，针对本文件规则细化：

| 变更 | 判级 | 说明 |
| --- | --- | --- |
| 弱化/删除 TS-1..TS-11 任一规则（如允许版本在 validator 成功前推进、允许 generated 裸拷贝、放宽 MAJOR gate、伪造 rollback、静默不报 governance_data_gap、自动执行 init） | **MAJOR** | 默认视为实现 bug，不得为让测试变绿而改弱本文件；改变承诺需 human 在 issue/PR 明确批注批准 |
| receipt schema 增字段（向后兼容，既有字段语义不变） | MINOR | 下游读取代码通常无需改造 |
| receipt schema 删除/重命名既有字段、`result` 枚举增删值 | **MAJOR** | 下游解析 receipt 的代码可能失败 |
| 五类 ownership 语义变化（如 scaffold 改为总是覆盖、merge 哨兵约定改变） | **MAJOR** | 直接影响下游文件的实际落地结果 |
| CLI/manifest 输入收紧（新增必填参数、manifest 新增必填字段） | **MAJOR** | 下游需人工改造调用方式 |
| CLI/manifest 输入放宽（新增可选参数、manifest 新增可选 kind） | MINOR | 向后兼容 |
| 文案/内部重构、无表面行为变化的 bugfix | PATCH | — |
| 变更本文件「唯一规范正文 owner」指定，或改变 truth direction（哪份文件是规范、哪份只做链接） | **MAJOR** | 需按 `.agent/human-gates.md` 走 human 批准路径，只引用该 doctrine，不复制其内容 |

发现实现偏离本文件任一规则：默认判定为 correctness bug，走 `.agent/human-gates.md` 另开 bug
issue 修复 production 实现；不得反向弱化本文件规则去匹配当前实现的意外行为。
