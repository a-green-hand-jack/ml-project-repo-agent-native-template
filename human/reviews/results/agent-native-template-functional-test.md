# 结果 review：agent-native 模板功能测试（ELF-template-case 迁移）

## 摘要

把 `~/Projects/ELF-template-case`（一个更早的 `.harness/` 谱系模板 case，围绕真实公开的
`lillian039/ELF` 项目搭建）迁移进本模板的 `lab/` + `deliverables/` + `human/` + `memory/` 结构，
落在分支 `worktree-case+elf-template-replay` 上，然后对模板自身的 validators、hooks，以及一部分
subagent 做了实测。完整发现见：
`lab/docs/audits/agent-native-template-functional-test-report.md`。

## 跑了什么（可验证）

- `python scripts/validate-governance.py`、`check-anatomy-drift.py`、`check-agent-harness.py`、
  `check-same-commit.py --staged` —— 在 commit `c164232`、`fdfa519`、`0828a94` 上全部干净通过。
- 真实 `lillian039/ELF`（`pytorch_elf` @ `b29d8833609e9ab7f67cd9da39435ac5cea04837`）重新 clone +
  全新 CPU-only 依赖安装 + 一次微型合成前向传播，独立复现了旧审计记录的输出形状 `(2,4,8)` /
  `(2,4,32)`。
- Hook 探测（sudo、curl|sh、受保护路径的 rm/mv/Write、git-push-to-main/topic-branch/escape）——
  全部按设计行事。
- 15 个 subagent 里实测了 5 个（artifact-librarian、experiment-orchestrator、
  repo-doc-steward、branch-reporter、test-runner）；全部停留在其声明的边界内。

## 证据指针

- `lab/research/{claims,evidence,experiment-ledger}.yaml` —— 迁移内容 + 一条新的回放条目。
- `lab/artifacts/{result,trace}-index.yaml` —— smoke 测试索引条目（result-001/002、
  trace-001/002）。
- `memory/current-status.md` —— 完整的命令/结果记录与决策。
- `memory/branches/case-elf-template-replay.md`、`memory/worktree-status.md` ——
  branch-reporter 的清点结果。

## 尚未证实 / 明确超出范围

- 没有对 ELF 做 GPU、数据集、checkpoint、训练/生成循环、指标复现（仅 smoke，与旧证据自身的范围
  限制一致）。
- 15 个 subagent 中的 10 个，以及所有 `.claude/skills/`/命令入口，本轮尚未实测。
- 被归类为 template gap/摩擦的 6 条发现（见报告 F2、F3、F5、F6、F7）已记录，尚未修复——这一轮按
  任务范围是 test-first。

## 需要人类决策

- 是否要处理 F2（嵌套 vendored 仓库 + 相对 hook 路径导致的自锁失败）——可以说是最重要的发现，因为
  它能卡死整个 session。
- 是否/何时把这个 case 分支 push 到远端，以及是否要再来一轮覆盖剩下的 10 个 subagent 与 skill 层级
  （Skill 工具/斜杠命令）入口。

## Round 2 追加（2026-07-09）

按 human 要求：F2 已修（独立分支 `hook-self-lock-fix` → PR #1 → squash-merge 进 `main`
commit `6fed240` → 合回本分支），并新增了「书面文档默认中文」doctrine。随后跑了 round 2：
剩余 9 个 subagent（8 个完成、1 个被 auto-mode classifier 正确拦下）+ 2 个 skill
（`anatomy-drift-control`、`session-boundary-control`）。关键新发现：F2 的修复本身验证充分，
但本 session 无法现场自证生效（hook 配置似乎在 session 启动时缓存）；`repo-researcher` 发现
同一类 bug 在别处还有未修实例；一个不带 Bash 的 subagent 曾把文件误写进主仓库（已发现并清理）。
完整记录见 `lab/docs/audits/agent-native-template-functional-test-report.md` 的「第二轮」一节。

状态：**待人类 review**——尚未批准。round 2 的具体待决项：是否扩大 F2 修复范围（F11）、是否需要
一个全新 session 独立复验 F2（F10）、是否启动 `plans/20260709-round3-template-functional-test.zh.md`
提出的 round 3。
