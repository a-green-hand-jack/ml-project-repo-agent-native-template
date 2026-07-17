# Branch Status: 57-g4-control-plane

## Purpose

issue #57（父 issue #52，P7 阶段，D 层「双 agent 场景」）：对多 agent 控制面
（`.agent/multi-agent-control-plane.md`，issue #14 落地）跑一个完整的双 agent 故事，逐条覆盖
7 个 T-ID（T-G4-1 ~ T-G4-7）的正例（按契约工作）+ 负例（越界被拒/正确降级），留可复现证据。
不是再造一个通用 runner——产物是一份薄的场景驱动脚本 + 报告，参照 issue #54/#59 的 A 层
qualification runner 的证据形态。

## Parent session

都督·统·治理路线（Paseo 主 tab）。本分支执行官：干将·演·控制面（G4，sonnet-5·auto）。

## Branch / base

**实际分支名是 `g4-dual-agent-verification`**（非 issue 交代文字里写的
`test/g4-control-plane`——worktree 目录名是 `g4-control-plane`，但 `git branch --show-current`
实测为 `g4-dual-agent-verification`；本分支执行官接手时分支已建好，未重命名，如实记录这处
命名不一致，供都督核对是否是有意为之）。base = `origin/main` @
`b588d59a2c276f7e5d0bd25786ac9f2f943fbfeb`（`docs(memory): P4 收口——#54/#59 经 PR #71 合入
关闭`）。

## Worktree

`/home/user/.paseo/worktrees/1kaz3672/g4-control-plane`（Paseo 分配的 linked worktree；控制面
根解析到主 checkout `/home/user/Projects/ml-project-repo-agent-native-template`，已用
`git branch --show-current` + `agent-state.py control_plane_root` 逻辑核实一致）。

## Linked issue / PR

issue #57（子任务），父 issue #52（P7）。PR 见下方「Exit condition」（待本文件所在 commit 完成
后开，不 merge）。

## Owned paths

`lab/evals/control-plane/`、`lab/docs/audits/qualification/report-g4.json`、
`lab/docs/audits/qualification/report-g4.md`、`memory/branches/57-g4-control-plane.md`、
`lab/ANATOMY.md`（新增一行）、`lab/docs/audits/README.md`（新增一段），已在
`scripts/agent-state.py register` 登记。

## Forbidden paths

`lab/data/`、`lab/runs/`、`lab/models/`、`wandb/`、`lab/infra/private/`（已登记）；四个控制面
脚本本体（`scripts/agent-state.py` 等）与 `.claude/hooks/agent_name_set.py` 只读复用，不改动
（发现的缺陷只报告，不顺手修）。

## Anatomy impact

- `lab/ANATOMY.md`：「只有 README 的 leaf 层」清单加入 `evals/control-plane/` 一行。
- `lab/docs/audits/README.md`：「当前内容」`qualification/` 条目补一句说明 `report-g4.*` 的
  来源与定位差异（测运行时协作机制，非静态门禁）。
- `lab/evals/control-plane/`、`lab/docs/audits/qualification/`（既有目录）均为 leaf，无独立
  ANATOMY.md，与 `lab/evals/qualification/` 既有惯例一致。
- `check-same-commit.py --staged` 已核验：4 处结构改动均与本变更集同步。

## Claim / evidence impact

无。本分支不写 `lab/research/claims.yaml`/`evidence.yaml`——G4 场景报告是运行证据（JSON+MD），
不是对外 paper-grade claim，与 issue #54/#59 的既有先例一致。

## Plan doc

无独立 plan doc；方案细节即本分支执行官接到的任务交代正文（human 已在交代里逐条拍板 7 个
T-ID 与隔离纪律），照案执行。

## Current state

**已完成，7/7 T-ID PASS，self-test backstop 76 项全部通过，结构性可重复性已验证。**

### 设计要点

- **每个 T-ID 独立隔离控制面根**（`tempfile.mkdtemp`，用后即 `shutil.rmtree`），调用四个核心
  脚本 CLI 时双保险：既设 `AGENT_CONTROL_PLANE_ROOT` env，又显式传 `--root`。TTL→stale 派生
  这一条 CLI 无 `--now` 开关表达不了，直接 importlib 复用 `agent-state.py` 的 `register(...,
  now=...)` 库函数把心跳时间戳设成 31 分钟前，不等真实 30 分钟、不重新实现过期逻辑。
- **T-G4-7（roster/identity）单独设计隔离手法**：`.claude/hooks/agent_name_set.py` 的 roster
  路径是硬编码到真实 worktree 根的全局变量，没有 env override；本 driver 用该脚本自己
  `_self_test()` 同款手法——importlib 载入一份新鲜模块实例，猴补 `mod.ROSTER` 指向隔离临时
  文件，调用 `_register_child()`（本就不写 `.agent-identity` 的「--register 子 agent」库函数）
  验证幂等与「改名」（同 paseo-id 换名字，roster 行原位替换）。唯一真实调用的 CLI 子进程
  （空名字负例）在写任何文件前就提前返回，额外用 sha256 比对确认真实 `.agent-identity`/
  `agents-roster.md` 前后字节不变。全程未污染真实控制面状态（已用 `git status` + roster grep
  验证）。
- fixture 全部走 Python 内部 `tempfile`/`shutil`，不经 Bash `rm`/`mv`（doc-lifecycle hook 会
  拦变量路径的 shell 删除/移动命令）。
- **复现性合同是"结构性"而非"字节级"**：连续两次运行 statuses/booleans 完全一致，但证据文本
  里嵌的临时路径/真实心跳时间戳/消息哈希 id 天然逐次不同——这是被测机制本身的设计（隔离根
  随机、心跳用真实 wall clock、消息 id 含时间戳），不是不确定性缺陷，已在 README 明确记录，
  区别于 `lab/evals/qualification/` 的严格 byte-for-byte 合同（那边的 git-clone fixture 内容
  静态）。

### 7 个 T-ID 逐项结论

| T-ID | 承诺 | 结论 | 证据指针 |
| --- | --- | --- | --- |
| T-G4-1 | register/heartbeat/TTL→stale 派生（不落盘改 status） | ✅ PASS | `report-g4.json#results[id=T-G4-1]` |
| T-G4-2 | mailbox send/read + decision/handoff 强制 ref 落盘 | ✅ PASS（负例三路：无 ref / `..` 逃逸 / 绝对路径，均拒绝） | 同上，`id=T-G4-2` |
| T-G4-3 | handoff ack 前 ownership 不转移 + 精确路径匹配拒绝 | ✅ PASS | 同上，`id=T-G4-3` |
| T-G4-4 | check-agent-conflicts scan（重叠→报警） | ✅ PASS | 同上，`id=T-G4-4` |
| T-G4-5 | worktree 声明 vs 实际 toplevel 检测 | ✅ PASS | 同上，`id=T-G4-5` |
| T-G4-6 | agent-status 聚合视图（±Paseo 降级） | ✅ PASS（负例两分支：无 paseo_id / PATH 剥掉 paseo 二进制，均优雅降级不 raise） | 同上，`id=T-G4-6` |
| T-G4-7 | roster/identity（agent_name_set 幂等/改名） | ✅ PASS | 同上，`id=T-G4-7` |

完整证据（含每项 positive/negative 的具体输出摘录）见
`lab/docs/audits/qualification/report-g4.{json,md}`。

### self-test backstop（确定性、优先复用）

| script | ok assertions | exit |
| --- | --- | --- |
| `scripts/agent-state.py` | 17 | 0 |
| `scripts/agent-mailbox.py` | 27 | 0 |
| `scripts/agent-status.py` | 10 | 0 |
| `scripts/check-agent-conflicts.py` | 16 | 0 |
| `.claude/hooks/agent_name_set.py` | 6 | 0 |

共 76 项，全部通过（`FAIL ` 前缀无一处出现）。

### 可重复性验证

commit `b588d59`（本分支未改任何脚本本体，被测 commit 恒为分支 base）上连续跑两次：7 个 T-ID
的 `status` 与所有断言布尔字段（`positive.ok`/`negative.ok`/各子标记）逐字节一致，
`meta.commit`/`meta.self_test.all_pass` 一致；`evidence` 文本因含真实时间戳/临时路径/消息 id
逐次不同（设计使然，见上方「设计要点」与 README）。

## Commands run

| command | 结论 |
| --- | --- |
| `python3 -m py_compile lab/evals/control-plane/run-g4-scenario.py` | 通过 |
| `python3 scripts/agent-state.py --self-test` 等四脚本 + `agent_name_set.py --self-test` | 76/76 ok |
| `uv run --with pyyaml python3 lab/evals/control-plane/run-g4-scenario.py`（首次） | 发现 2 处 driver 自身 bug：`render_markdown` 读错 `self_test` 嵌套层级、T-G4-7 rename 断言因新名字含旧名字为前缀子串导致误判——均已修复 |
| 修复后重跑 | 7/7 PASS |
| 连续第二次跑 + 自写 diff 脚本剔除 `generated_at`/`worktree_dirty`/证据文本内嵌时间戳类字段后结构比对 | `structural statuses identical: True`（7/7 一致），`commit identical: True` |
| `git status --short` + `grep -c 干将·改·g4demo memory/agents-roster.md` + `ls memory/agents/ \| grep g4demo` | 确认无测试场景 agent 泄漏进真实 roster/state，真实 `.agent-identity` 未被本次场景测试改动 |
| `uv run --with pyyaml python3 scripts/validate-governance.py --strict` | OK — 0 error(s), 0 warning(s)（含 anatomy-drift/doc-lifecycle/outcome-ledger/experiment-state/provenance-chain/capability-catalog 全部子检查） |
| `uv run --with pyyaml python3 scripts/check-same-commit.py --staged` | OK —— 4 处结构改动，对应 anatomy 已同变更集更新 |

## Latest result

7/7 T-ID PASS，5 个脚本 76/76 self-test 断言 PASS，治理门禁全绿，结构性可重复性已验证。

## 发现的观察（只报告，不顺手修；均非阻断性缺陷）

1. **分支名与 worktree 目录名不一致**（如实记录，非代码缺陷）：任务交代文字写
   `test/g4-control-plane`，实测 `git branch --show-current` 为
   `g4-dual-agent-verification`，worktree 目录名是 `g4-control-plane`。未影响 push/PR（仍是
   topic 分支），但供都督确认是否符合预期。
2. **`agent_name_set.py` 没有统一 rename 原语**（T-G4-7 场景验证得到的真实行为，非推测）：
   同一 paseo-id「换名字」时，roster 行会按 paseo-id 去重原位替换（新名字覆盖旧行），但旧
   名字对应的 `memory/agents/<旧名>.yaml` 状态文件不会被自动清理或合并进新文件——旧文件
   只是不再被 roster 引用，物理留存。这是已知设计边界（doctrine 里也没有承诺过「rename」
   语义，只承诺 `paseo agent update --name` 是改名机制），不构成缺陷，但若未来有人真的按
   「roster 一致 = 全局身份一致」的假设去查旧状态文件会踩到这处留痕，值得都督评估是否值得
   补一条 rename 时顺带迁移/标记旧 yaml 的增量。
3. **agent-status.py 的 paseo 交叉校验分支覆盖需要主动剥 PATH 才能在本机测到**（非缺陷，
   记录测试方法论）：本机真实装了 `paseo` CLI（`~/.local/bin/paseo`），T-G4-6 负例分支 b
   （"缺 Paseo 优雅降级"）靠子进程 `PATH=/usr/bin:/bin` 主动模拟；如果换一台没装 paseo 的
   机器跑本 runner，默认路径本身就会天然落进这条负例，不需要人为剥 PATH（README 已注明此
   UNAVAILABLE 语义的判定逻辑）。

## Open risks

- 本地环境（本 worktree）裸 `python3` 缺 PyYAML；`uv run --with pyyaml` 是稳定
  workaround，与 `lab/evals/qualification/` 同一既有环境缺口（未跨机验证，风险低）。
- T-G4-6 负例分支 a（"无 paseo_id 但 paseo CLI 真实可用"）依赖本机确实装了 `paseo` 且
  `paseo ls --json` 能正常返回——若未来该 CLI 行为变化（如输出格式改变导致
  `paseo_live_ids()` 解析失败），该子断言的判定逻辑（`presence == "-"`）仍然成立（因为判定
  的是"未登记 paseo_id 的 agent 不查 live_ids 集合直接给 `-`"这条与 paseo 输出格式无关的
  分支），风险低。

## Exit condition

- [x] 7 个 T-ID 全部有结论与证据。
- [x] 5 个脚本 self-test backstop 全通过（76 项）。
- [x] 结构性可重复性验证通过（同 commit 重跑两次，statuses/booleans 逐字节一致）。
- [x] 隔离纪律核实：无测试场景数据泄漏进真实控制面状态。
- [x] 治理门禁（`validate-governance.py --strict`）+ `check-same-commit.py --staged` 回归绿。
- [x] branch status 完整（本文件）。
- [ ] commits push 到当前分支（待本文件所在 commit 完成后统一 push）。
- [ ] 开 PR（base main，正文中文，说明 7 T-ID 结论 + 证据路径 + self-test 数目），不 merge，
      等独立 verifier + human。
