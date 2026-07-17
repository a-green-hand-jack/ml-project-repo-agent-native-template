# 56-g3-verify —— G3 工作流 skills 演练独立复核报告

> **Provenance**：本文由独立复核官 **师爷·审·工作流**（sonnet-5/high，PR #73 独立 worktree）
> 撰写并逐条独立取证。原文写在其复核 worktree、未提交、随 worktree 归档丢失文件本体；由主 agent
> **都督·统·治理路线** 从该复核官的最终汇报**如实转录**回 main 以持久化独立复核证据，未改结论。
> 被审对象是 writer 干将·演·工作流 的 `memory/branches/56-g3-skills.md` 与
> `lab/docs/audits/qualification/report-g3.md`（PR #73，已 squash-merge `3211825`）。

## 复核方法（authoring/review 分离）

先自读 8 个被测 skill 的 `SKILL.md`（`.claude/skills/`）与相关 command（`.claude/commands/`）
+ 证据报告，独立形成判断，再核验；不以 writer 的分支叙述为判断依据。

## 逐条 T-ID 独立结论

| T-ID | skill/command | 独立裁决 |
| --- | --- | --- |
| T-G3-1 | worktree-pr-flow（含 S2 自检清单） | **CONFIRMED-PASS**（`diff --stat` 与预期路径自报完全对应）|
| T-G3-2 | spawn（in-session 子 agent） | **CONFIRMED-PASS**（16 agent 数量核实、结构一致）|
| T-G3-3 | subagent-routing（launch packet） | **CONFIRMED-PASS** + 非阻断观察独立证实：`subagent-router-agent` tools 只有 `Read`，SKILL.md 却要求「运行」quota 脚本 |
| T-G3-4 | interactive-plan-doc（draft→approved 干跑） | **CONFIRMED-PASS**（`validate_repo()`/`pretooluse_reason()` 复用方法论核实存在）|
| T-G3-5 | checkpoint / session-boundary-control | **CONFIRMED-PASS**（附 1 条需处理项，见下）|
| T-G3-6 | pr-review（fresh reviewer，对 PR #72） | **CONFIRMED-PASS** + 真实发现独立复核为真（见下）|
| T-G3-7 | template-feedback（issue 打包干跑） | **CONFIRMED-UNAVAILABLE**（`.template.toml` 确实不存在、`template-sync.py` 逻辑一致，判定正确非逃避）|
| T-G3-8 | experiment-workflow（卡片+ledger 干跑） | **CONFIRMED-PASS**（`check_ledger()` 复用方法论核实存在）|

## 干跑零泄漏独立验证

成立。`git log main..HEAD` 对 `plans/`、`memory/doc-lifecycle.yaml`、
`lab/research/experiment-ledger.yaml`、`.template.toml`、`lab/data|runs|models` 全部空输出；
`git diff --stat` 只有 4 个文件改动。

## PR diff 范围

基本干净，未误并 `current-status.md` / 治理注册表。唯一问题：`memory/session-tree.md` 新增的
Children 行是 T-G3-5 对该 skill 的真实（非 fixture）合法演练（`session-boundary-control` 本就
声明可写此文件），但**内容已过期**（写旧分支名 `test/g3-skills-walkthrough` + 「in progress」，
实际早已 rename 完成并开 PR #73）。**建议 merge 前后更新该行**，非阻断。
> 主 agent 收口注：已于 merge 后更新该行为 `APPROVE + integrated`（merge `3211825`）。

## 两条真实发现独立定性

1. **G4 缺陷（属实，独立读源码确认）**：`run-g4-scenario.py` 的 UNAVAILABLE 降级语义死代码
   （`unavailable=` 全文件零赋值）；T-G4-6 负例分支 a 在无 `paseo` CLI 机器上，`agent-status.py`
   的 `paseo_live_ids()` 返回 `None` 使 `paseo_presence` 变成 `"unknown(no-paseo)"` 而非断言
   期望的 `"-"`，导致误判 FAIL，且与该分支自述「观察 #3」矛盾。**建议对 #57 开跟进 issue。**
   > 主 agent 收口注：已开 **#74**。
2. **subagent-routing 工具边界不一致（属实，独立 grep 确认）**：低严重度，非阻断。

## 门禁复跑（独立执行）

`validate-governance.py --strict`、`check-anatomy-drift.py`、`check-doc-lifecycle.py` 全部
独立复跑 OK。未发现证据造假或空跑冒充 PASS。

## 总裁决

**APPROVE**
