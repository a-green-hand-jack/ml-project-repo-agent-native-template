# G2（issue #55，P6）Claude 表面 runtime hooks 独立测试

> **Provenance**：本文由独立测试者 **游侠·测·Claude运行时**（fresh session，非实现者，
> claude-sonnet-5/high，worktree `test/g2-claude-runtime-fresh`）撰写并逐条实际触发取证。
> 原文写在其测试 worktree、随 worktree 归档丢失文件本体；由主 agent **都督·统·治理路线** 如实
> 转录回 main 以持久化独立测试证据，未改结论。

方法：全程实际触发（Write/Edit/Bash/git push + 直接管道模拟 hook stdin），不靠读代码下结论。

## 总裁决（5 组）

- **T-G2-2（push main guard）PASS**、**T-G2-4（context 续接）PASS**：独立实际触发，行为与声明一致。
- **T-G2-1（保护路径写入）**：表面字面验证 PASS，但**归因排查发现 hook 本体是死代码**（见下）。
- **T-G2-5（formatter hook）FAIL**。
- **T-G2-6（双表面比对）**：发现 4 类不等价。

## T-G2-1：表面 PASS，但机制归因 = hook 自身对 Edit/Write 路径保护是死代码

- 表面行为：Write 四个受保护路径全部被拒（`File is in a directory that is denied by your
  permission settings.`），`/tmp` 负例成功。字面验证 PASS。
- **但归因**：拦截来自 `settings.json.permissions.deny`（Claude Code 内置声明式引擎，通用英文
  提示），**不是** `pre_tool_guard.py`。`_is_protected_file()` 用**相对路径前缀匹配**
  （`"lab/data/"`、`"mlruns/"` 等），而 Claude Write/Edit **始终传绝对路径**（schema 明确 must be
  absolute）→ `"/home/.../mlruns/x".startswith("mlruns/")` 恒 False → **该检查对 Edit/Write 在
  Claude 表面是死代码，从未生效**。
- 隔离探针证实：`mlruns/` 在 hook 的 `PROTECTED_PREFIXES` 里、但**不在** `permissions.deny` 里
  → `Write mlruns/__g2_probe__.txt` **成功创建**（`git status --ignored=matching` 确认落地，
  是 `.gitignore` 遮蔽不是没写）。Bash `echo > mlruns/...` 同样成功；`_check_bash()` 只查
  `rm/mv/cp/rsync/dd/curl|sh/launch-gate/git push`，**无任何普通 `>`/`>>`/`tee` 重定向目标检查**。
- **真实缺陷**：hook docstring 声称"即使 permission 层放开，本 hook 仍拦截红线写产物 bytes"——这个
  承诺在 Claude 表面是**假的**；任何只在 `PROTECTED_PREFIXES` 声明、漏加进 `permissions.deny` 的
  目录（`mlruns/` 就是活例）在 Claude 表面 Edit/Write 完全不受阻拦。全靠 `permissions.deny` 冗余兜底。
- 清理：所有探针已 rm，`mlruns/` 空目录已 rmdir，`git status` 干净。

## T-G2-2：PASS，hook 自身确认生效

- `git push origin main` → 报 hook 自定义中文文案（"push 到受保护分支需 human 明确放行..."，逐字
  核对源码一致，非 git 原生错误、非 permission 通用英文提示）→ 确认 hook 在联网前拦下。
- 负例 `git push origin test/g2-claude-runtime-fresh` → 成功（topic 分支不受限）。
- **副作用**：此负例是真实网络 push，在 GitHub 远端**创建了新分支 `test/g2-claude-runtime-fresh`**。
  未加 escape env，是预期行为，但产生了远端 ref，需 human 决定是否清理。
  > 主 agent 收口注：human 拍板删除，已清理（见 current-status.md）。

## T-G2-4：PASS，合成 stdin 独立复现（非只读代码）

- `context_continuity.py` 挂 SessionStart `matcher: compact|clear`；`context_threshold_notice.py`
  挂 UserPromptSubmit（全触发）；`context_usage.py` 未直接挂事件，是共用 helper（被 threshold
  hook import + statusline CLI 调用）——与既有 memory 记录一致。
- 管道实测：compact source → 正确回注 `current-status.md`；startup source → 空输出（负例符合声明）。
- 合成 transcript 精确验证阈值：70% → 黄线文案（≥65%）；85% → 红线更紧急文案（≥80%）；同 session
  黄线去重生效；黄线升级红线不被去重吞。全部与声明（阈值 65/80、去重、compact/clear 才回注）一致。
- 清理：合成 transcript 与测试 marker 已删；其他真实 session 遗留 marker 未动。

## T-G2-5：FAIL

1. **Claude 表面实际接线的不是 `format_changed_python.py`**：`settings.json` PostToolUse
   （`Edit|Write`）实跑裸 `ruff format "$CLAUDE_FILE_PATHS" 2>/dev/null || true`；
   `format_changed_python.py` 只在 `.codex/config.toml` 被真正调用。
2. **ruff 缺失时静默假装成功**：本环境 `which ruff` exit 127（`uvx ruff` 0.15.22 仅 ephemeral）。
   真实 Write scratch `.py`（故意留 `def   foo( x,y ):`）→ 内容原样未格式化（裸命令 `2>/dev/null || true`
   吞错强制 exit 0，对 agent/用户完全不可见）。直接跑 `format_changed_python.py` → 无输出 exit 0
   （源码 `if shutil.which("ruff") is None: sys.exit(0)`，无 print），违反"ruff 不可用应显式报错"。
3. 正向路径确认：用 `uvx ruff` shim 临时加 PATH → 文件被正确格式化为 `def foo(x, y):`，证明核心
   逻辑没坏，问题精确在"ruff 缺失时错误可见性"+"Claude 表面没接这个脚本"。

## T-G2-6：双表面静态比对——4 类不等价

- **对齐**：`pre_tool_guard.py` PreToolUse、`pre_compact_memory_check.py`、
  `subagent_report_index.py`、`context_threshold_notice.py`、`context_continuity.py`、
  `zh_review_advisory.py` 六项语义等价（Codex 多覆盖 `apply_patch` 合理）。
- **不等价①**：格式化 hook——Claude 表面根本没接 `format_changed_python.py`（跑裸 ruff 命令），
  只有 Codex 接。ANATOMY.md 描述读起来像两表面共用同一逻辑，**文档与实际接线不符**。
- **不等价②**：SessionStart 身份重申——Claude 无 matcher（含 compact 都重申），Codex
  `startup|resume|clear` **显式不含 compact**（config 注释自承）。compact 后 Claude 重申、Codex 不。
  有代码注释佐证的已知设计差异。
- **不等价③**：`NotebookEdit` 不在 Claude PreToolUse matcher（`Bash|Edit|Write`）里，但
  `pre_tool_guard.py` 有 `elif tool in ("Edit","Write","NotebookEdit")` 分支 → Claude 表面
  该分支是**死代码盲区**。行为验证 UNAVAILABLE（仓内无 `.ipynb`、工具强制先 Read 已存在文件）；
  若未来受保护目录出现 `.ipynb`，其 `NotebookEdit` 写入既不受此 hook、也不受 `permissions.deny`
  （无 `NotebookEdit(...)` 规则）保护。
- **不等价④**：Codex `default.rules` 全是 Bash argv 前缀规则，**无文件路径级 deny**；Codex 表面对
  写入受保护路径的唯一防线就是 `pre_tool_guard.py` 本身。`_patch_paths()` 从 apply_patch 补丁头
  解析的是**相对路径**（理论上能前缀匹配，纯代码分析未行为验证），而 Claude Edit/Write 传绝对路径
  已行为证实失效——**同一份共享 hook 因上游路径形态不同，两表面保护力可能完全不对称**。

## 发现的真实缺陷（按严重性，供开 issue 真修）

1. `pre_tool_guard.py._is_protected_file()` 对 Claude Edit/Write 绝对路径不匹配相对前缀 = 死代码；
   全靠 `permissions.deny` 冗余兜底，任何未同步的 `PROTECTED_PREFIXES` 条目（已证 `mlruns/`）
   在 Claude 表面**无实际保护**。Bash 任意 `>` 重定向也从未受此 hook 保护。
2. Claude PostToolUse 格式化命令与文档描述的 `format_changed_python.py` 不是同一实现且更简陋；
   两者 ruff 缺失时都不满足"显式报错"（裸命令更彻底静默）。
3. `NotebookEdit` 不在 Claude PreToolUse matcher，对应分支死代码（当前受限于"无已存在受保护 notebook"）。
4. SessionStart 身份重申 compact 后 Claude/Codex 行为不同（已知设计差异，仍列为不等价点）。

全程只在隔离 worktree 操作，`lab/data|runs|models|infra/private` 真实内容未受影响，未用 escape
env，未 push main；唯一触达远端是题面要求的负例 topic push（已单独标注，human 已拍板删除）。
