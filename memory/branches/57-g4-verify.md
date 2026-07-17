# 57-g4-verify —— G4 多 agent 控制面独立复核报告

> **Provenance**：本文由独立复核官 **师爷·审·控制面**（sonnet-5/high，PR #72 独立 worktree）
> 作者撰写并逐条独立取证。原文写在其复核 worktree、随 worktree 归档丢失文件本体；由主 agent
> **都督·统·治理路线** 从该复核官的复核报告与活动记录**如实转录**回 main 以持久化独立复核证据，
> 未改动结论。被审对象是 writer 干将·演·控制面 的 `memory/branches/57-g4-control-plane.md`
> 与 `lab/docs/audits/qualification/report-g4.{json,md}`（PR #72，已 squash-merge `a6152b6`）。

## 复核方法（authoring/review 分离）

先读被测的 4 个控制面脚本（`agent-state.py` / `agent-mailbox.py` / `agent-status.py` /
`check-agent-conflicts.py`）+ `.claude/hooks/agent_name_set.py` + 驱动脚本
`lab/evals/control-plane/run-g4-scenario.py` **源码**，独立想清每条 T-ID 正/负例的通过判据；
再重跑取证；**最后**才对照 `report-g4`。不以 writer 的分支叙述为判断依据。

## 逐条 T-ID 独立结论

| T-ID | 独立裁决 | 证据 |
| --- | --- | --- |
| T-G4-1 | **CONFIRMED-PASS** | `agent-state.py:effective_status` 显式区分「派生态」与「存储态」：`register(now=31min前)` 只改 `heartbeat`，`status` 字段本身不动；重跑两次均得 `derived=stale, stored_status_before=active, stored_status_after=active` —— 真负例，非脚本吞异常。 |
| T-G4-2 | **CONFIRMED-PASS** | 独立读 `_validate_ref`：三条独立 `raise ValueError`（无 ref / 绝对路径 / `resolve().relative_to()` 判逃逸）。重跑捕获三条真实 stderr。绝对路径分支专门验证「目标文件真实存在于控制面根内」也照样拒绝——负例问对了问题。 |
| T-G4-3 | **CONFIRMED-PASS** | 独立读 `_validate_transfer`：仅 `_norm_path(p) in owned_norm` 精确匹配放行；命中「拥有父目录」分支显式 `raise` 且不触碰 `_rewrite_field`。重跑：C 只 owned `shared/`、handoff 子文件 `shared/detail.txt` 后 ack 非零、stderr 含「目录」、消息 `state` 仍 `pending`、C 的 `owned_paths` 未变——三处独立断言。 |
| T-G4-4 | **CONFIRMED-PASS** | `find_overlaps` 用 `path_under`（目录前缀/文件精确）两两比较 `is_enforceable` agent；正例命中 1、负例 0，exit 1/0，重跑一致。 |
| T-G4-5 | **CONFIRMED-PASS** | `worktree_mismatch` 纯路径 `resolve()` 比较，无 try/except 吞逃逸；declared 改到 `elsewhere`、`--actual-toplevel` 传 `actual` → exit 非零、stderr 点名两个绝对路径。 |
| T-G4-6 | **CONFIRMED-PASS** | 本机 `paseo` 是真实二进制（非模拟），负例分支 a（无 `paseo_id` 但 CLI 真实可用）是货真价实的活路径。重跑：`no_pid presence=-`、`no_cli presences=['unknown(no-paseo)','unknown(no-paseo)']`，两条独立命令 exit 均 0。 |
| T-G4-7 | **CONFIRMED-PASS** | 猴补 `mod.ROSTER` 复用 `agent_name_set.py` 自身 `_self_test()` 同款隔离手法，未触碰真实 `.agent-identity`/roster。空名字负例额外做 sha256 摘要比对；重跑前后主 checkout `ls memory/agents/ | grep g4demo` + roster grep 均空。 |

## self-test backstop（独立计数）

`agent-state 17 + agent-mailbox 27 + agent-status 10 + check-agent-conflicts 16 +
agent_name_set 6 = **76**`。先独立数出 76、后对照报告发现吻合，非抄报告。

## 隔离 / 零泄漏独立验证（D 层证据命门）

主 checkout 与复核 worktree 两次重跑前后 `git status --porcelain` / roster / `memory/agents/`
目录均无 `g4demo` 系列泄漏。每 T-ID 独立 `tempfile.mkdtemp` 控制面根、用后即弃。**成立**。

## 对 writer 3 条观察的独立看法

均独立核实属实、同意非阻断定性：① 分支实际名 `g4-dual-agent-verification` 与交代文字
`test/g4-control-plane` 不一致（worktree 目录名 `g4-control-plane`）；② `agent_name_set.py`
无统一 rename 原语，改名后旧状态 yaml 不自动清理（已知设计边界）；③ T-G4-6 缺-Paseo 降级
分支本机需主动剥 PATH 才能测到（本机真装 paseo）。另报两处极小非阻断方法论观察（见原活动记录）。

## 总裁决

**APPROVE** —— 7/7 T-ID 独立 CONFIRMED-PASS，76 项 self-test 独立计数吻合，结构性可重复性
（同 commit 两跑 `jq` 结构 diff 逐字节一致，仅时间戳/临时路径/消息 id 波动）独立验证通过，
零泄漏独立验证通过，`validate-governance.py --strict` 独立复跑全绿。未发现 writer 未报告的
阻断性缺陷。
