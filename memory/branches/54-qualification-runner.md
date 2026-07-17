# Branch Status: 54-qualification-runner

## Purpose

issue #54（G1 静态门禁 validator 正例+负例）+ issue #59（G6 Codex 适配 parity）P4 落地：
实现 A 层可重复 qualification runner，重新验收 G1（9 项）与 G6（4 项），共 13 个 T-ID。
human 已批准方案 D1-D3（原话：「review #54/#59 完成，批准」）。

## Parent session

都督·统·治理路线（Paseo 主 tab）。本分支执行官：干将·铸·资格评测（P4，sonnet-5·high·auto）。

## Branch / base

`54-qualification-runner`，base = `origin/main` @ `35c9bd58820379bebebd1c93b0c747868fc882ae`
（`Merge pull request #70 from a-green-hand-jack/fix/63-downstream-data-init`）。

## Worktree

`/home/user/.paseo/worktrees/1kaz3672/54-qualification-runner`（独立 worktree，Paseo 分配）。

## Linked issue / PR

- issue #54（G1 九项，方案 D1-D3 正文）
- issue #59（G6 四项，与 #54 共用同一 runner）
- 未开 PR（按交代不擅自开 PR/merge）。

## Owned paths

`lab/evals/qualification/`、`lab/docs/audits/qualification/`、
`memory/branches/54-qualification-runner.md`（已在 `scripts/agent-state.py register` 登记）。

## Forbidden paths

`lab/data/`、`lab/runs/`、`scripts/`（只读不改；发现的 validator 缺陷只报告不顺手修）。

## Anatomy impact

- `lab/ANATOMY.md`：leaf 层清单加入 `evals/qualification/` 一行（同 commit `3ada78a`）。
- `lab/docs/audits/README.md`：「当前内容」加入 `qualification/` 子目录说明（同 commit）。
- `lab/evals/qualification/`、`lab/docs/audits/qualification/` 本身均为 leaf（只有
  README，无独立 ANATOMY.md），与 `lab/evals/bootstrap/`、`lab/docs/audits/` 既有惯例一致。

## Claim / evidence impact

无。本分支不写 `lab/research/claims.yaml`/`evidence.yaml`——qualification runner 是
评测工具产出的运行证据（JSON+MD），不是对外 paper-grade claim，符合 issue #54 明文
「runner 不挂进 validate-governance.py，不是新门禁」。

## Plan doc

无独立 plan doc；方案细节即 issue #54 正文「提议方案（D1-D3）」节（human 已批准，照案执行）。

## Current state

**已完成，13/13 T-ID PASS，可重复性已验证。**

### 设计要点

- fixture 用 **`git clone --no-hardlinks`** 而非纯 `git archive`：`check-agent-harness.py`
  （经 `sync-codex-adapters.py --context source`）与 `validate-governance.py` 的
  tracked-bytes/merge-sentinel 子检查内部依赖 `git ls-files`，纯 tar 物化没有 `.git` 会让
  这些子检查静默降级或直接报错误判——`git clone` 保留真实 git 历史，且是
  `.agent/action-boundary.md` 明文允许的两种 fixture 手段之一，未偏离硬边界。
- fixture 用后即弃（`shutil.rmtree`），绝不在真实 repo/worktree 内注入，绝不 copytree
  任何 worktree。
- 复用优先：G1 的 5 项（T-G1-2/3/6/7/8）对应 validator 已有 `--self-test`，runner 直接
  调用并把其 exit code + 输出摘要登记为证据，不重复造 fixture。
- 环境细节：本机裸 `python3` 缺 PyYAML，`validate-governance.py --strict` 等门禁会把
  「跳过 YAML 深度解析」warning 计成 FAIL（非本分支引入，是既有环境缺口，
  `scripts/CLAUDE.md` 早有 workaround 记录）；runner 统一用
  `uv run --with pyyaml python3` 调用子进程校验脚本绕开，已在 README 与代码注释里说明。

### 13 个 T-ID 逐项结论

| T-ID | validator | 负例注入点 | mode | 结论 | 证据指针 |
| --- | --- | --- | --- | --- | --- |
| T-G1-1 | `validate-governance.py`（含 `--strict`） | `.gitignore` 删除全部 `lab/data` 行 | 自建 fixture | ✅ PASS | `report-all.json#results[id=T-G1-1]` |
| T-G1-2 | `check-anatomy-drift.py` | governed_components 断链/orphan/mismatch | 复用 `--self-test` | ✅ PASS | 同上，`id=T-G1-2` |
| T-G1-3 | `check-doc-lifecycle.py` | 锚点/注册表状态矛盾 + 跃迁缺字段 | 复用 `--self-test` | ✅ PASS（见下方发现 1，语义有出入但复用正当） | 同上，`id=T-G1-3` |
| T-G1-4 | `check-same-commit.py` | staged 新增结构文件不带 anatomy | 自建 fixture（`git clone`，需要真实 `--staged` diff） | ✅ PASS | 同上，`id=T-G1-4` |
| T-G1-5 | `check-agent-harness.py` | 删除 `.claude/hooks/subagent_report_index.py`（settings.json 引用） | 自建 fixture | ✅ PASS | 同上，`id=T-G1-5` |
| T-G1-6 | `check-capability-catalog.py` | 未登记能力（missing） | 复用 `--self-test` | ✅ PASS | 同上，`id=T-G1-6` |
| T-G1-7 | `check-provenance-chain.py` | 悬空引用（evidence/claim/dataset/checkpoint/review/figure 多类） | 复用 `--self-test` | ✅ PASS | 同上，`id=T-G1-7` |
| T-G1-8 | `validate-experiment-state.py` | 非法状态机转移（`planned→running` 跳过 approved、`done→running` 回转） | 复用 `--self-test` | ✅ PASS | 同上，`id=T-G1-8` |
| T-G1-9 | `check-outcome-ledger-schema.py` | 截断 sample ledger 首行，制造非法 JSON | 自建 fixture | ✅ PASS（见下方发现 2） | 同上，`id=T-G1-9` |
| T-G6-1 | `sync-codex-adapters.py`（幂等） | 无对立负例——单一幂等性质：先删一个 adapter 制造初始未同步（第一次 write changed≥1），验证第二次 write 收敛为真正 no-op（changed=0 且产物树摘要不变） | 自建 fixture | ✅ PASS | 同上，`id=T-G6-1` |
| T-G6-2 | `sync-codex-adapters.py --check` | 手改一个已生成 `.codex/agents/*.toml` | 自建 fixture | ✅ PASS | 同上，`id=T-G6-2` |
| T-G6-3 | `sync-codex-adapters.py`（38 files 逐项对应） | 单点 content drift | 自建 fixture（`importlib` 复用 `expected_files()`） | ✅ PASS，实测 38 个 expected adapter path，与 issue 表格标注一致 | 同上，`id=T-G6-3` |
| T-G6-4 | `check-agent-harness.py`（Codex 侧可发现性，复用 `check_codex_config()`） | `.codex/config.toml` 一处 hook 指向不存在脚本 | 自建 fixture | ✅ PASS | 同上，`id=T-G6-4` |

完整证据（含每项 positive/negative 的 exit code、注入描述、输出尾部摘录）见
`lab/docs/audits/qualification/report-all.{json,md}`；`report-g1.*`/`report-g6.*` 是同一份
逻辑按组拆分的子集（`--group g1`/`--group g6` 单独跑时落盘，内容与 `report-all` 对应条目
一致）。

### 可重复性验证（D2 合同）

在 commit `3ada78a`（runner 落地那一提交）上用 `--group all` 连续跑两次，JSON 剔除
`generated_at`/`worktree_dirty` 两个显式隔离的易变字段后逐字节相等（`python3` 脚本对比，
非人工目测）。之后又各跑一次 `--group g1`/`--group g6`/`--group all`，把三份证据一并落进
`ada31a0`（评测证据 commit，被测 commit=`3ada78a`）。

## Commands run

| command | 结论 |
| --- | --- |
| `python3 -m py_compile lab/evals/qualification/run-qualification.py` | 通过 |
| `python3 lab/evals/qualification/run-qualification.py --group g6` | 4/4 PASS |
| `python3 lab/evals/qualification/run-qualification.py --group g1`（首次，未接 `uv --with pyyaml`） | 8/9 PASS，T-G1-1 FAIL——定位为环境缺 PyYAML 导致 `validate-experiment-state.py` 在 `--strict` 下把 warning 计成 FAIL，非注入逻辑问题 |
| 改用 `uv run --with pyyaml python3` 后重跑 `--group g1` | 9/9 PASS |
| `python3 lab/evals/qualification/run-qualification.py --group all` | 13/13 PASS |
| `uv run --with pyyaml python3 scripts/validate-governance.py --strict`（真实 repo，加完新文件后回归） | OK — 0 error(s), 0 warning(s) |
| `uv run --with pyyaml python3 scripts/check-anatomy-drift.py` | OK — 扫描 17 个 ANATOMY.md，0 处结构漂移 |
| `uv run --with pyyaml python3 scripts/check-agent-harness.py --strict` | OK — 0 error(s), 0 warning(s) |
| `uv run --with pyyaml python3 scripts/check-same-commit.py --staged`（commit 前） | OK —— 8 处结构改动，对应 anatomy 已同变更集更新 |
| commit `3ada78a` 后 `--group all` ×2 + 自写 diff 脚本剔除易变字段比对 | `REPRODUCIBLE: byte-identical after stripping generated_at/worktree_dirty` |
| commit `3ada78a` 后 `--group g1`、`--group g6`、`--group all` 各跑一次，落 `ada31a0` | 13/13 PASS，三份证据的 `meta.commit` 均为 `3ada78a` |

## Latest result

13/13 T-ID PASS。分支 2 commits（`3ada78a` 实现、`ada31a0` 证据），均未 push（见 Exit
condition）。

## 发现的 validator 缺陷 / 观察（只报告，不顺手修）

1. **`check-doc-lifecycle.py` 没有跨时间的状态转移图校验**（静态代码阅读结论，未做动态
   复现，建议都督定级前先验证）。`memory/doc-lifecycle.yaml` 每条只存快照 `status:` 字段，
   全文 grep 不到 `status_history`/`git log`/`git show` 等历史追溯逻辑。self-test 实际
   覆盖的是「锚点与注册表状态矛盾」+「跃迁进某状态时必填字段缺失」两类，不是像
   `validate-experiment-state.py`（有显式 `status_history` 与 `非法状态转换 {a} → {b}`
   拒绝规则，见该脚本 233 行）那样的有向状态机图。理论上只要锚点和注册表被同步改成同一个
   合法枚举值，一份文档可以被手改「倒退」（例如 `verified` 改回 `draft`）而不触发任何
   报错。这不影响 T-G1-3 复用 `--self-test` 的正当性——该 self-test 确实完整覆盖了这个
   validator 实际承诺的语义（锚点/注册表一致性），只是 issue #54 表格给 T-G1-3 建议的负例
   描述「非法状态转移」字面上暗示了一个这个 validator 目前并不做的检查。是否值得补一条
   基于 commit 历史的倒退检测，留给都督判断优先级。
2. **`check-outcome-ledger-schema.py` 的负例注入有较宽的级联爆炸半径**（已动态复现，非
   推测）。T-G1-9 负例只截断了 `outcome-ledger.sample.jsonl` 第一行（一条 decision 记录）
   的末尾字符，结果不仅触发预期的 `invalid JSON` 解析错误，还级联出另外 3 条不直接相关的
   ERROR（该 decision 的 outcome 记录变成「引用未知 decision_id」、codex 路线样本量不足、
   frozen fixture 意外触发 degraded）——因为这条 fixture 记录同时被四个不同的断言函数复用
   （`check_fixture_ledgers`/`route_stats`/`check_fallback_and_determinism`）。这不是
   validator 的正确性 bug（每条 ERROR 都指向真实被破坏的不变量，报错本身是对的），但对
   未来想在这份 sample fixture 上做更细粒度负向测试的人是个陷阱：牵一发动全身，很难只
   隔离触发一种失败模式。建议若要精细化 T-G1-9 或类似负例，改用独立的一次性 fixture
   副本，不复用被多处引用的现有 sample ledger（本 runner 当前的用法仍然是安全的，因为
   我们只要求「非零退出且可定位」，没有要求「只有一条 ERROR」）。
3. **T-G6-1（幂等）本质是单一性质，没有对立的「负例」概念**——runner 里已如实用
   `negative: None` + notes 说明，不是遗漏，是刻意的诚实登记，避免为凑「正例+负例」格式
   而编造一个不存在的负面场景。

## Open risks

- 本地环境（本 worktree）裸 `python3` 缺 PyYAML；`uv run --with pyyaml` 是稳定 workaround，
  但换一台已预装 PyYAML 的机器/CI 重跑，行为应等价（未跨机验证，风险低——`uv run` 本身
  就是为此设计的可移植方案）。
- runner 假设 `git clone --no-hardlinks` 在本机 `/tmp` 与 worktree 之间可用（linked
  worktree 场景下已验证：`git clone` 能正确解析 worktree 的 `.git` 指针文件并克隆出独立
  `.git`，不共享 HEAD/index，不复现 P3 事故）。

## Exit condition

- [x] 13 个 T-ID 全部有结论与证据。
- [x] 可重复性验证通过（同 commit 重跑两次逐字节一致，剔除显式隔离的易变字段）。
- [x] branch status 完整（本文件）。
- [ ] commits push 到 topic 分支 `54-qualification-runner`（待本文件所在 commit 一并完成
      后统一 push）。
- 未开 PR / 未 merge / 未改 GitHub issue 正文——回填 ⚪→✅ 与关闭 issue 留给都督。
