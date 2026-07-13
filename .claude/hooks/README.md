# .claude/hooks/

repo-local lifecycle hooks（可执行，以本机权限运行——保持小而可审计）。

| 文件 | 事件 | 作用 | 阻止能力 |
| --- | --- | --- | --- |
| `pre_tool_guard.py` | `PreToolUse(Bash\|Edit\|Write\|NotebookEdit)`（Codex 侧另含 `apply_patch`） | 拦截危险 Bash、受保护路径写入、push 到 `main`/`master`；另薄接线 doc-lifecycle 完整性与 `scripts/check-agent-conflicts.py` 多 agent ownership/写错 worktree 检查（对应显式逃生变量见下） | 硬阻止（exit 2） |
| `pre_compact_memory_check.py` | `PreCompact` | 提醒落盘 `memory/current-status.md` | 仅提醒（exit 0） |
| `subagent_report_index.py` | `SubagentStop` | 向 `agent-reports/index.md` 追加时间线 | 仅记录（exit 0） |
| `zh_review_advisory.py` | `PostToolUse(Edit\|Write)` | 命中 `human/reviews/**`、`human/decisions/**`、`lab/docs/audits/**`、`DECISIONS.md` 时，用中日韩字符占比启发检查是否忘了用中文；不做翻译判断，只提醒派发 `zh-review-gate` | 仅提醒（exit 0） |
| `context_threshold_notice.py` | `UserPromptSubmit` | 上下文 ≥65%/≥80% 时向本轮注入「派 checkpoint-writer + 考虑 compact」建议；每 session 每档只提醒一次 | 仅注入建议（exit 0） |
| `context_continuity.py` | `SessionStart(compact\|clear)` | compact/clear 后把 `memory/current-status.md` 摘要回注新上下文，接续不断档 | 仅注入（exit 0） |
| `context_usage.py` | —（库/CLI，非注册 hook） | 共用 helper：读 transcript `usage` 求精确上下文 token%，供 statusline 与上面阈值 hook 调用 | N/A |
| `agent_identity.py` | —（库/CLI，非注册 hook） | 解析当前 agent 名字（`AGENT_NAME` env / `.agent-identity` 文件），供 statusline `🤖 <name>` 段；doctrine 见 `.agent/agent-identity.md` | N/A |
| `agent_identity_hook.py` | `UserPromptSubmit` + `SessionStart` | 未命名时首个 prompt 注入「自命名」指令（每 session 一次）；已命名时 SessionStart 重申「你是 &lt;name&gt;」 | 仅注入（exit 0） |
| `agent_name_set.py` | —（agent 调用的 setter） | agent 选定名后调用：写 `.agent-identity` + 默认 `paseo rename`（`AGENT_NO_AUTORENAME=1` 关）+ upsert `memory/agents-roster.md` + 尽力初始化控制面状态文件 `memory/agents/<name>.yaml`（经 `scripts/agent-state.py`）；`--register --paseo-id <id>` 只登记子 agent（`spawn` skill launcher 用，不改自身） | N/A |

## 上下文调配（信号层，见 `plans/20260711-context-orchestration.zh.md`）

`context_usage.py` / `context_threshold_notice.py` / `context_continuity.py` + `statusline.sh` 的
`🧠 NN%` 段共同补齐「主动调配」链：statusline 让占用**可见**，UserPromptSubmit hook 在 65/80 档
把建议**注入**，SessionStart hook 在压缩后**回注** status 保连续性。

**硬边界**：这三者只发信号/注入文本，**不 block、不自动 `/compact`**——真正按下 compact 需宿主 CLI +
主 agent 在任务边界判断（repo hook 无法可靠按 token 阈值自动压缩）。token% 精确来自 transcript
`usage`（`input+cache_read+cache_creation`）。

**窗口感知（默认就是动态的，无需手配）**：hook 对本会话窗口的感知**主要靠 statusline 动态驱动**——
statusline 每次渲染都读 `.model.id`（含 `[1m]`），认出当前模型的窗口并写进
`$TMPDIR/claude_ctx_window_<session_id>` 缓存；hook 据 session_id 读缓存。于是**选了 1M 模型 → 下一帧
statusline 就把 1M 传给 hook；切回 200k 模型 → statusline（权威，绕过旧缓存）改写 200k**，全程跟随模型动态变化，
不需要人工设任何东西。之所以只能靠 statusline：`[1m]` 标记**只**出现在 statusline 的 `.model.id`——hook 的
stdin 没有 model，transcript 又只存 base id（不带 `[1m]`），故 statusline 是唯一能动态感知窗口的源。

完整优先级链（前者短路后者）：`CLAUDE_CTX_WINDOW` 环境变量 > 本会话窗口缓存（statusline 动态写）>
model id 推断 > 证据推断（观测上下文一旦超过 200k → snap 到 1M）> 默认 200k（安全方向：宁早提醒不漏）。
- **`CLAUDE_CTX_WINDOW` 是兜底、不是常规路径**：只在 statusline 不渲染的表面（某些 headless/嵌入 UI）才需要，
  设在 `.claude/settings.local.json` 的 `env` 块，值固定不随模型变——所以能动态感知时优先靠 statusline，别写死它。
- 前提就一条：**statusline 要渲染**（交互式 session 默认持续渲染，本就是使用 code agent 时该有的仪表盘）。

**运行表面（Claude + Codex 已对等）**：
- Claude：`.claude/settings.json` 注册 `UserPromptSubmit` + `SessionStart(compact|clear)`。
- Codex：`.codex/config.toml` 注册 `UserPromptSubmit` + `SessionStart(compact|clear)`。Codex 0.144
  的 `PostCompact` 输出协议不提供 `additionalContext`，所以不能承担模型上下文回注；continuity
  必须走支持 `source=compact` 的 `SessionStart`。`PreCompact` 落盘提醒本就两表面对等。

所有注入类 hook 的非空 stdout 都是单个 JSON 对象：`SessionStart` / `UserPromptSubmit` 文本放在
`hookSpecificOutput.additionalContext`，不得打印裸文本。Claude Code 与 Codex 都接受此协议；静默路径
保持 0 字节 stdout。

## 协议

hook 从 stdin 读 JSON（`tool_name` / `tool_input` 等）。`pre_tool_guard` 以 exit code 2 + stderr 表示阻止；两者解析失败时保守放行。

## `pre_tool_guard` 拦什么（地板层，bypass/自主窗口也拦）

- 用 **shlex 真正解析命令**（非子串正则）：引号里的字面量（commit message、`echo "..."`）不误伤；引号里的真实路径/分支（`rm -rf "lab/data"`、`git push origin "main"`）仍识别。
- 提权/远程执行：`sudo`、`curl|sh`、`wget|sh`。
- 依赖：`pip install`、`python -m pip install`（用 `uv add`）。
- `rm -r` **目标分级**：数据/产物 bytes、`.git`、绝对路径(非 `/tmp`)、`~`、仓库根、`..` → 拦；缓存/构建/临时目录（`__pycache__` 等）→ 放行。另有兜底正则拦 `find -exec rm ... lab/data` 类嵌套。
- `mv`/`cp`/`rsync`/`dd` 触碰受保护路径 → 拦。
- 受保护路径的 `Edit`/`Write` → 拦。
- push 到 `main`/`master` → 拦，除非 `CLAUDE_ALLOW_PUSH_MAIN=1`。
- 多 agent 协作完整性（issue #14，安全地板之外的增量层）：`Edit`/`Write`/`NotebookEdit`/`apply_patch`
  写入其他**活跃** agent 声明的 owned path、自己声明的 forbidden path、或 declared worktree 与实际
  不符 → 拦。判定本体在 `scripts/check-agent-conflicts.py`（薄接线 + importlib，仿
  `check-adoption-integrity` 先例）；判定层异常/身份未知/无状态文件 → 保守放行；
  `AGENT_CONFLICT_SKIP=1` 显式绕过。见 `.agent/multi-agent-control-plane.md`。

## `pre_tool_guard` 的 doc-lifecycle 层（完整性层，非安全地板；issue #13）

对 brief/plan/review/decision 四类文档与 `memory/doc-lifecycle.yaml` 的
`Edit|Write|apply_patch|Bash` 写入/删除，加载 `scripts/check-doc-lifecycle.py` 的
`pretooluse_reason()`（与 validator 同一份逻辑）：

- 写入四类受管文档但缺唯一正文状态锚点、锚点不在标题后的第一条非空行、或只在代码围栏里
  放了 `Status:` 示例 → 拦。
- 写入使文档标 `approved`/`implementing` 但 plan 缺非空「Allowed paths / Forbidden paths / 验证标准」段 → 拦。
- 上述状态下 Human 批注区残留 `[?]`/`[改]` 未决批注、或上游引用已 `superseded`（过期 approval）→ 拦。
- 写注册表引入悬空引用/非法枚举/缺 approval 证据/kind 与路径类别不符（谎报 kind），或活跃
  plan 的 issue 为占位、branch 不存在、implementing worktree 未登记/未绑定同一 branch → 拦。
- 删除/移走注册表（`apply_patch` Delete/Move、Bash `rm`/`mv`/`git rm` 等）→ 拦；会先展开
  `command`/`env` wrapper，并跳过 `git -C`、`--literal-pathspecs` 等全局选项：注册表是治理面，
  删除等于静默关闭校验（validator 侧「有受管文档但注册表缺失」同为 error）。
- `cp` 覆盖判定按 GNU 语义解析 `-t`/`--target-directory` 及无歧义长选项缩写、`--parents`
  和 `$PWD`/`${PWD}`；其余会改变目的路径但无法安全静态求值的活动 shell 展开 fail-closed。
- `apply_patch` 的 Update 会保留 `@@ <anchor>` section 定位并按 hunk 重建 patch 后全文（与 Edit
  同语义）；anchor 缺失/重复或上下文无法可靠定位时**保守拦截**并提示改用 Edit——不猜落点。
- **边界**：只判可判定事实，不判研究方向/风险/是否真收敛（那是 human gate）；提示明确指出缺哪个字段/哪条引用悬空。
- **注册表删除拦截是「尽力而为的减速带」，非完备安全边界**：静态命令分析无法可靠拦解释器
  （`python`/`perl`/`awk`…）、`eval`/`$(...)`、`find -delete`/`xargs` 及无界写工具尾巴
  （`install`/`ln -sf`/`rsync`/`sed -i`…）；只兜底常见/可判定模式。**权威保证是事后 validator**
  （`check-doc-lifecycle.py`：注册表缺失/损坏即 error）+ 注册表纳入 git 追踪（删除在 diff/门禁/review 暴露）。
  不要把本 hook 堆成完备 Bash 解析器。
- 逃生：`DOC_LIFECYCLE_SKIP=1`（human 明示时用；validator 仍事后校验）。判定层自身异常一律保守放行，不反噬安全地板。
- 状态语义/注册表 schema 见 `plans/ANATOMY.md`；synthetic/runtime 冒烟见 `lab/evals/doc-lifecycle/`。

## 注意

- hook 与 `.claude/settings.json` 的 deny/ask、`.agent/action-boundary.md` 必须一致。
- worktree/desktop/remote surface 下 hook 行为可能不一致——高风险 workflow 仍需 permission + Git + manual review 兜底。
- 改动后用 `/hooks` 或 debug mode 验证触发。
- push 分支感知：topic/实验分支放行；`main`/`master` 被 hook 拦（exit 2），除非命令带 `CLAUDE_ALLOW_PUSH_MAIN=1` 或 session 内 export。见 `.agent/autonomous-window.md`。
- 本地手测（构造串避免误触自身守卫）：
  `python3 -c "import json,subprocess as s;print(s.run(['python3','.claude/hooks/pre_tool_guard.py'],input=json.dumps({'tool_name':'Bash','tool_input':{'command':'git push origin main'}}),capture_output=True,text=True).returncode)"`（在 main 之外的分支上应为 2）。`
