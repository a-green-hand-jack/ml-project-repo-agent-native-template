# #78 D1/D4（Codex runtime）根因取证——项目 hook 未被 Codex 信任/加载

> 主 agent **都督·统·治理路线** 在自主窗口用**本机真实 codex-cli 0.144** 取证，非只读代码推断。
> 结论：D1/D4 的 Codex 侧**不是 `pre_tool_guard.py` 脚本 bug，而是该脚本在 Codex 表面根本没被调用**。

## 取证方法（都在本机真跑）

1. `codex --version` → `codex-cli 0.144.0`；真实二进制 `~/.codex/packages/standalone/releases/0.144.0-.../bin/codex`。
2. `strings` 该二进制：确认 Codex **支持** PreToolUse 拦截——嵌入 JSON schema 有
   `PreToolUseDecisionWire`/`PreToolUsePermissionDecisionWire`/`PreToolUseHookSpecificOutputWire`，
   且有运行时串 `"Command blocked by PreToolUse hook: "`。故「Codex 不能 deny」被排除——它能。
3. 起隔离 worktree，塞一个诊断 hook（matcher `^.*$`，把 stdin dump 到 /tmp），挂进该 worktree 的
   `.codex/config.toml` PreToolUse 首位，跑
   `codex exec --cd <wt> -s workspace-write -c approval_policy=never --dangerously-bypass-hook-trust`
   让 Codex 真的 `echo` + 新建文件。**结果：文件成功创建（apply_patch 落地），但诊断 dump 为空**
   —— 项目 `.codex/config.toml` 的 PreToolUse hook **一次都没触发**（即便 `^.*$` + bypass-hook-trust）。
4. `codex doctor`：`config loaded` 只列 `~/.codex/config.toml`（用户级），**全程无**项目
   `.codex/config.toml` 的加载记录。
5. 读 `~/.codex/config.toml`（只读，未改）：
   - `[features] hooks = true`；真实 Codex hook 来自用户级 `~/.codex/hooks.json`（OMX 管理，事件名是
     snake_case `pre_tool_use`/`post_tool_use`/`session_start`/`user_prompt_submit`/`stop`/`permission_request`）。
   - `[hooks.state.*]` 是**逐路径 sha256 信任表**：hook 必须先被信任才会跑。
   - 其中**唯一**与本 repo 项目 config 相关的信任项是一个**旧 worktree 路径**：
     `.../ml-project-repo-agent-native-template/.claude/worktrees/18-runtime-codex-62086fb/.codex/config.toml:pre_tool_use:0:0`（及同批 post_tool_use/session_start/... ）。
   - `grep -c "ml-project-repo-agent-native-template/.codex/config.toml:" ~/.codex/config.toml` → **0**：
     **repo 主 `.codex/config.toml` 从未进过 Codex 信任表**。

## 根因（证据充分）

Codex 0.144 的 project-scoped `.codex/config.toml` hook 要**逐路径 hash 信任**（持久化在
`~/.codex/config.toml [hooks.state]`）才会运行；主 repo 的 `.codex/config.toml` **不在信任表**里
（只有一个陈旧 worktree 副本曾被信任）。所以在**当前 repo 表面（及任何 fresh clone/worktree）**上，
模板声明的 Codex 安全地板 hook（`pre_tool_guard.py` / formatter / identity / continuity）**全部 inert，
Codex 从不调用它们**。这与 G2（Paseo Codex，`55-g2-codex.md`）和本次 `codex exec` 探针**两个独立表面
都 FAIL** 完全一致。

- **D1（保护路径写入无拦截）**：`pre_tool_guard.py` 判定代码有效（synthetic payload 能 deny），但它在
  Codex 上**没被 runtime 调用** → 无地板。**不是脚本 bug，是 hook 未加载/未信任。**
- **D4（identity 链未完成）**：同理——项目 identity hook 未被信任加载；G2 里看到的 marker 很可能来自
  用户级 `~/.codex/hooks.json`（OMX）而非 repo hook。repo 的 identity 链在未注册信任前不成立。

## 为什么本窗口不自动修

真正的修复要么 **(a)** 在 bootstrap 里把项目 `.codex/config.toml` 的每个 hook **注册进 Codex 用户级信任表**
（写 `~/.codex/config.toml [hooks.state]` 的 sha256），要么 **(b)** 改用 OMX 式用户级 `~/.codex/hooks.json`。
两者都要**改用户机器全局 Codex 状态**、且等于「让 hook 脚本自动运行」的信任授权——是**有安全含义、机器
特定、需 human 拍板**的动作。headless 自动改用户全局 Codex 信任，违反动作边界，故**不做**。

## 已有的真实缓解（不依赖 Codex hook）

- **D2 已由 `.githooks/pre-push` 修复（PR #80）**：git 层 push-main 地板，**surface-agnostic**，Codex 表面
  真实 `git push origin main` 也会被 git 拦（与 Codex hook 是否加载无关）。这是当前 Codex 表面**唯一
  真正生效**的技术地板之一。

## 给 human 的建议（发版门 P8）

三选一：
1. **真修**：在 `scripts/bootstrap-project.py` 增加「注册并信任项目 Codex hook」步骤（写 `~/.codex/config.toml
   [hooks.state]` 或生成 `~/.codex/hooks.json` 条目），并在 fresh clone 上真机复验 Codex PreToolUse 能 deny
   受保护写入 + 完成 identity 链。**需 human 批准改用户全局 Codex 状态**。
2. **收窄承诺**：v1.4.0 明确把「runtime 保护地板」承诺限定在 **Claude 表面 + git 层（pre-push/pre-commit）**，
   文档写明 **Codex 表面的技术地板依赖用户级 Codex hook 信任配置（OMX/bootstrap 注册），非模板文件自动保证**。
2 与现实相符、诚实。
3. **豁免**：human 明确豁免 D1/D4 后发版，留作后续版本。

## 边界

全程只读用户 `~/.codex/config.toml`（未改）；探针 worktree 与诊断 hook 已删；未改用户全局 Codex 状态；
未碰 `lab/data|runs|models`。
