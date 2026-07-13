# 真实双 runtime 冒烟 — 待跑清单 + 证据模板（留给监控员 / human）

> issue #13 plan 验证标准要求「Claude + Codex 双 runtime、fresh startup 与 compact/clear
> 两个边界」的**真实 session** 冒烟。worker agent 不启动新 session（任务边界），synthetic
> 探针已覆盖 hook 进程行为（见 `evidence-20260713-synthetic-probes.md`），但无法证明
> runtime 接线（matcher、hook trust、注入是否真正进上下文）。以下每项由监控员在合并前跑一次，
> 把证据填进模板后连同 PR 一起给 human 复核。

## 待跑清单

- [ ] **C1 Claude fresh startup**：在 repo 根新开 Claude Code session，不带任何历史。
  预期：无 continuity 注入（startup 不回注）；agent 按入口纪律（CLAUDE.md 先读第 3 条）
  主动读 `memory/current-status.md` 当前 plan 指针 + `memory/doc-lifecycle.yaml`，
  能说出当前活跃 plan 与 status。
- [ ] **C2 Claude /clear 恢复**：同一 session 内 `/clear`。
  预期：新上下文开头出现 `[continuity] clear 后回注 …「当前 plan 指针」` 注入块。
- [ ] **C3 Claude compact 恢复**：触发 compact（长会话或手动 `/compact`）。
  预期：同 C2（source=compact）。
- [ ] **X1 Codex fresh startup**：`codex` 新会话（确认 `.codex/` project hooks 已 trust）。
  预期：无 continuity 注入（matcher 不含 startup 调 continuity 属预期）；agent 按 AGENTS.md
  入口纪律主动读到当前 plan 指针。
- [ ] **X2 Codex /clear（SessionStart clear）**：预期同 C2。
- [ ] **X3 Codex compact（PostCompact 事件）**：预期注入块以 `[continuity] compact 后回注` 开头。
- [ ] **G1 拦截面实测（任一 runtime）**：真实 session 里尝试把某 plan 状态锚点改成
  `approved` 且缺必填段（可用临时草稿 plan），确认被 hook 拒绝且提示含
  `doc-lifecycle:`；再以 `DOC_LIFECYCLE_SKIP=1` 复跑确认显式放行。
- [ ] **G2 注册表删除拦截实测（任一 runtime）**：真实 session 里让 agent 执行
  `rm memory/doc-lifecycle.yaml`（或 Codex `apply_patch` Delete File），确认被拒绝。

## 证据要求（plan 已定案：不能以「session 能启动」代替）

每个 case 保留**可见注入输出或 hook 日志**：截图 / 会话转录片段 / `codex` debug 日志均可，
需能看到注入块文本或拦截提示原文。证据粘贴到下方模板，或存放路径写进表格。

## 证据模板

| case | 日期 | runtime 版本 | commit | 结果(PASS/FAIL) | 证据（原文片段或路径） | 执行人 |
| --- | --- | --- | --- | --- | --- | --- |
| C1 | | | | | | |
| C2 | | | | | | |
| C3 | | | | | | |
| X1 | | | | | | |
| X2 | | | | | | |
| X3 | | | | | | |
| G1 | | | | | | |
| G2 | | | | | | |

跑完后：把本文件的勾选与表格填齐，同 commit 更新 `evidence-*.md` 索引；若有 FAIL，
开 issue 挂回 `plans/20260712-plan-lifecycle-state.zh.md`（状态不得进 verified）。
