# 真实双 runtime 冒烟 - 完成记录

> issue #13 plan 验证标准要求「Claude + Codex 双 runtime、fresh startup 与 compact/clear
> 两个边界」的**真实 session** 冒烟。2026-07-13 已由集成 owner 在隔离 HOME + disposable
> clone 中完成；synthetic 探针仍是独立证据，不能替代本清单。详细断言、session id 与 raw log
> 见 `evidence-20260713-runtime-probes.md`。

**当前状态：8/8 PASS。** C1-C3/X1-X3 的 continuity/context 目标为 `68f1d43`；相关 hook
代码未再变化。main 集成后改变的 guard G1/G2 已在精确目标 `183a7fa` 的新 disposable
clones 中重跑。raw files 的 sha256 在 `raw/SHA256SUMS`；首次 C3 消息不足尝试保留在 raw 中
但不计 PASS，继续同一隔离顶层 session 后的第二次真实 compact 才是验收证据。

## 待跑清单

- [x] **C1 Claude fresh startup**：在 repo 根新开 Claude Code session，不带任何历史。
  预期：无 continuity 注入（startup 不回注）；agent 按入口纪律（CLAUDE.md 先读第 3 条）
  主动读 `memory/current-status.md` 当前 plan 指针 + `memory/doc-lifecycle.yaml`，
  能说出当前活跃 plan 与 status。
- [x] **C2 Claude /clear 恢复**：同一 session 内 `/clear`。
  预期：新上下文开头出现 `[continuity] clear 后回注 …「当前 plan 指针」` 注入块。
- [x] **C3 Claude compact 恢复**：触发 compact（长会话或手动 `/compact`）。
  预期：同 C2（source=compact）。
- [x] **X1 Codex fresh startup**：`codex` 新会话（确认 `.codex/` project hooks 已 trust）。
  预期：无 continuity 注入（matcher 不含 startup 调 continuity 属预期）；agent 按 AGENTS.md
  入口纪律主动读到当前 plan 指针。
- [x] **X2 Codex /clear（SessionStart clear）**：预期同 C2。
- [x] **X3 Codex compact（SessionStart source=compact）**：预期注入块以
  `[continuity] compact 后回注` 开头，且 runtime 日志中没有 invalid hook JSON。
- [x] **G1 拦截面实测（任一 runtime）**：真实 session 里尝试把某 plan 状态锚点改成
  `approved` 且缺必填段（可用临时草稿 plan），确认被 hook 拒绝且提示含
  `doc-lifecycle:`；再以 `DOC_LIFECYCLE_SKIP=1` 复跑确认显式放行。
- [x] **G2 注册表删除拦截实测（任一 runtime）**：真实 session 里让 agent 执行
  `rm memory/doc-lifecycle.yaml`（或 Codex `apply_patch` Delete File），确认被拒绝。

## 证据要求（plan 已定案：不能以「session 能启动」代替）

每个 case 保留**可见注入输出或 hook 日志**：截图 / 会话转录片段 / `codex` debug 日志均可，
需能看到注入块文本或拦截提示原文。证据粘贴到下方模板，或存放路径写进表格。

## 证据模板

| case | 日期 | runtime 版本 | commit | 结果(PASS/FAIL) | 证据（原文片段或路径） | 执行人 |
| --- | --- | --- | --- | --- | --- | --- |
| C1 | 2026-07-13 | Claude Code 2.1.202 / Opus 4.8 | `68f1d43` | PASS | `raw/13-C1-*`; startup hook stdout 空，主动读到 plan/status | Codex integration owner |
| C2 | 2026-07-13 | Claude Code 2.1.202 / Opus 4.8 | `68f1d43` | PASS | `raw/13-C2-C3-*`; `SessionStart:clear success` + continuity | Codex integration owner |
| C3 | 2026-07-13 | Claude Code 2.1.202 / Opus 4.8 | `68f1d43` | PASS | `raw/13-C2-C3-*`; 第二次 compact 成功 + `SessionStart:compact success` | Codex integration owner |
| X1 | 2026-07-13 | Codex 0.144.0 / gpt-5.6-sol | `68f1d43` | PASS | `raw/13-X1-*`; fresh startup 主动读到 plan/status | Codex integration owner |
| X2 | 2026-07-13 | Codex 0.144.0 / gpt-5.6-sol | `68f1d43` | PASS | `raw/13-X2-X3-*`; clear hook completed + continuity | Codex integration owner |
| X3 | 2026-07-13 | Codex 0.144.0 / gpt-5.6-sol | `68f1d43` | PASS | `raw/13-X2-X3-*`; Context compacted + hook completed，无 invalid JSON | Codex integration owner |
| G1 | 2026-07-13 | Claude Code 2.1.207 / Opus 4.8 | `183a7fa` | PASS | `raw/13-G1-*-183a7fa.*`; 默认 deny，独立 SKIP session allow | Codex integration owner |
| G2 | 2026-07-13 | Claude Code 2.1.207 / Opus 4.8 | `183a7fa` | PASS | `raw/13-G2-*-183a7fa.*`; `env -C memory rm ...` 被 deny，注册表仍存在 | Codex integration owner |

结果已同步到 `evidence-20260713-runtime-probes.md`；feature 仍保持 `implementing`，直到 fresh
exact-head review APPROVE、合入 main 与合并后验证完成，才可转 `verified`。
