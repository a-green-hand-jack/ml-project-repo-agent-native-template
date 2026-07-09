# Trace：嵌套 vendored git 仓库导致 hook 自锁，两轮 stuck → recovery

## 背景

在 `worktree-case+elf-template-replay` 分支上做模板功能测试。`.claude/settings.json` 的
`PreToolUse` hook 命令原本是裸相对路径 `python3 .claude/hooks/pre_tool_guard.py`。

## 事件序列（第一轮，修复前）

1. `git clone` 真实的 `lillian039/ELF`（有自己的 `.git`）到 `lab/code/external/ELF`。
2. 用一条 `cd lab/code/external/ELF && ...` 顶层命令（非 subshell）跑 smoke 测试，cwd 停留在该目录。
3. 下一条 Bash 调用：hook 因为在这个 cwd 下找不到 `.claude/hooks/pre_tool_guard.py` 而报错，
   工具调用被整体拦截（fail closed）。
4. 尝试用 `cd <repo根>` 命令恢复：同样被同一个坏掉的 hook 挡住——因为 hook 在命令体执行前就已经
   报错，`cd` 命令本身根本没机会跑。自锁。
5. 恢复方式：`ExitWorktree(action=keep)` → `EnterWorktree(path=<worktree 根>)`——这两个工具不走
   这条 hook，成功脱困。

## 修复

把 `.claude/settings.json` 里三个 hook 命令 + `statusLine.command` 都改成用
`$CLAUDE_PROJECT_DIR` 锚定绝对路径（如 `python3 "$CLAUDE_PROJECT_DIR/.claude/hooks/pre_tool_guard.py"`），
经独立 subagent 实测确认该环境变量在 hook 子进程里确实存在，并通过 PR #1 squash-merge 进
`main`（commit `6fed240`），随后 merge 进本 case 分支。

## 事件序列（第二轮，修复后，同一 session 内复测）

1. `git merge origin/main` 把修复合进本分支，`.claude/settings.json` 磁盘内容已确认是新版本。
2. **在同一个已经运行中的 session 里**，故意重现同一操作：`cd lab/code/external/ELF`（顶层命令），
   再跑一条后续命令 —— **仍然复现了同样的报错**，报错信息里的命令还是旧的裸相对路径
   `python3 .claude/hooks/pre_tool_guard.py`，不是修复后的锚定版本。
3. 用 `ExitWorktree(keep)` → `EnterWorktree(path=...)` 重新进入这个 worktree，以为这样能让 hook
   配置重新加载——结果**再次复现同样的报错**，说明单纯重新进入 worktree 也不会刷新。
4. 再次用同一对工具脱困。

## 结论 / 假设

- hook 命令的锚定路径修复（`$CLAUDE_PROJECT_DIR`）本身经独立合成 JSON 测试确认是正确的。
- 但**已经在运行中的 session，似乎在会话开始时就固定了 hook 配置**（或至少在
  ExitWorktree/EnterWorktree 这个粒度不会重新读取 `.claude/settings.json`），修复只对
  修复落地之后**新开的** session 生效，对本 session 这种"边跑边改配置"的情况不生效。
- 这是一条有强行为证据支撑的经验：**改了 `.claude/settings.json` 的 hook 配置后，验证要开一个
  全新 session，不能指望在同一个 session 里用 Exit/EnterWorktree 验证生效**。

## 复测方法

在一个全新的 Claude Code session 里（不是靠 Exit/EnterWorktree），cd 进同样的嵌套仓库，确认
不再报错，即可复测此修复是否真的对新 session 生效。
