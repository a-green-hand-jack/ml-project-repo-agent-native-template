# Human Gates

外部副作用与不可逆动作必须经过人类审批点。agent 可以**准备**，但不能**触发**。

## 必须门禁的动作

| 动作 | 为什么 | agent 可做的准备 |
| --- | --- | --- |
| 建远端 repo / 首次推到新远端 / 改远端基础设施 | 外发、不可逆、可能被索引缓存 | 写好 commit、给出 diff 摘要 |
| 开/合 PR、merge | 影响共享分支 | 起草 PR body（evidence + risks） |
| release / 更新 deliverables 对外材料 | 影响导师/合作者可见 | 起草并标注 evidence 支持 |
| 启动/kill/restart 训练或远端作业 | 真实计算成本 | 准备可复现 launch 命令 + checklist |
| 删除/移动 data / checkpoint / run bytes | 不可逆、毁事实来源 | 生成归档提案，不执行 |
| 新增依赖 | 影响可复现环境 | 说明必要性与最小集 |
| promote 结果为 paper claim | 证据升级 | 附 run id/config/commit/metric + fresh verifier 结论 |

> 例外（分支感知 push）：`git push` 到 **topic / 实验分支** 是 `allow`——agent 可做，不打断。
> push 到 `main`/`master` 由 hook 地板拦，需 human 显式放行 `CLAUDE_ALLOW_PUSH_MAIN=1`
> 或 `CODEX_ALLOW_PUSH_MAIN=1`（单次），见 `.agent/autonomous-window.md`。开 PR / merge /
> release / 建远端 repo 仍是完整门禁。

## 四类文档的 approved 证据（doc-lifecycle，issue #13）

brief / plan / review / decision 的 `draft → in-review → approved` 由 human 批注驱动，
**approved 是 human gate**。机器只强制可判定事实（hook `pre_tool_guard.py` + validator
`scripts/check-doc-lifecycle.py`，状态语义见 `plans/ANATOMY.md`）：

- 标 `approved`/`implementing` 前：plan 的 Allowed paths / Forbidden paths / 验证标准 非空、非占位；
  Human 批注区无 `[?]`/`[改]` 未决批注。
- `memory/doc-lifecycle.yaml` 的 `approval` 字段引用真实批准证据（批注 diff / 拍板记录 / PR）；
  upstream/downstream/path 引用不悬空；上游被 `superseded` 则本条 approval 过期，需重新走 gate。
- `approved → implementing → verified` 由 agent 据证据自主标记，human 审 PR 时复核。
- human 明示例外可 `DOC_LIFECYCLE_SKIP=1` 绕过 hook（validator 仍事后校验）。

## launch 门禁（launch registry）

「启动/kill/restart 训练或作业」这一行的机器层由 **launch registry** 承载：
`lab/infra/launch/registry.yaml` 的 `gated_prefixes` 是「哪条命令算 launch/kill/restart」
的单一真源，三层门禁同步消费：

- 地板：共享 `pre_tool_guard.py` hook（经 `lab/infra/launch/launch_gate.py`）拦截命中前缀
  的命令，匹配 wrapper-robust（`env python -u …`、`nohup sbatch` 等包装绕不过；即使
  bypass/自主窗口下仍生效）。相对路径中的 `.`/`..`、`python -m` 与私有 `_worker`
  入口也覆盖；带 operand 的 `timeout --signal TERM 60`、`env -u FOO` 不会藏住真实命令。
  `env -S`、`env --split-string`、`bash|sh|zsh|dash -c/-lc`、`python -c`（含
  `-c<command>` attached argv token）属调用者可编程的动态执行面，在 agent hook 内整体
  fail-closed。`nice -n10 <command>` 等 GNU attached wrapper operand 也会先被剥离再检查。
  该地板只覆盖 registry 入口和已知别名，
  不宣称是通用进程 sandbox。
  `CLAUDE_ALLOW_LAUNCH=1` / `CODEX_ALLOW_LAUNCH=1` 是调用者可写输入，**永不放行**；
  human 必须在 agent hook 外亲自运行审阅过的命令。
- permission 层（额外提示，不是 override）：`.claude/settings.json` 的 `ask` 与
  `.codex/rules/default.rules` 的 `prompt`，与 registry 手工双写、同 commit 对齐。静态
  模式覆盖 canonical 直写形态 + 有限 wrapper / shell-eval 变体；Codex execpolicy 只能做
  literal argv prefix，因而对 direct CPython CLI 采用 broad prompt，精确区分仍由共享 hook
  完成；无论 human 是否在
  permission prompt 点确认，agent 命令仍受 hook 地板拒绝。
- 新增任何 launch 入口（含薄 wrapper）必须同 commit 登记进 registry 并补两侧规则，
  否则等于绕过门禁。

resume/recovery 的 `approved_by` / `approved_at` / `approved_action` 只是**审计记录**，不是
可执行 capability：repo-local YAML 可由调用者伪造，当前又没有外部可信 human provenance
verifier，也没有「先原子消费、再执行、崩溃后状态可恢复」的 consumer。因此：

- `expctl.py validate-recovery` 是 agent 可直接使用的只读校验入口；
- `expctl.py apply-recovery` 是实际恢复入口，当前一律 fail-closed；
- `/tmp` 测试 ledger 仅可配合只读校验/self-test，永不产生 launch/kill/restart 副作用；
- 校验会把 proposal 绑定到同一 run 的字面 `/tmp/.../<run-id>` workdir、受信 Python 与 repo 内
  canonical `fake_job.py`，并在执行前拒绝 resolved/consumed/non-pending 记录；
- alert 必须带 `approval_provenance: null`、consume/execution/resolved 状态字段；非 null
  provenance 在没有 verifier 时反而是错误，不能靠自称 human 获得信任。

human 若决定恢复，应在 agent hook 外亲自执行审阅过的确切命令并更新审计记录。未来只有在
外部可信 provenance + 原子一次性 consumer 合同落地后，才能重新开放半自动 actual recovery。

## 门禁形态

- 机器层：`.claude/settings.json` 与 `.codex/rules/default.rules` 里对应 `ask` / `deny` / `prompt`；
  `PreToolUse(Bash|Edit|Write|apply_patch)` hook。
- 流程层：`.github/pull_request_template.md` + `CODEOWNERS` review。
- 记录层：批准与理由落到 `human/decisions/`。

## 提示格式

请求门禁时，agent 给出：动作、影响半径、可逆性、已做准备、期望批准范围（一次性 / 本 session / 持久）。批准仅在被授予的范围内有效，不自动延伸到下一个上下文。
