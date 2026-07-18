# issue #78 — runtime enforcement 地板加固（干将·修）

分支 `fix/78-runtime-hardening`（基于 main `bbd54fa`）。修 5 处可在仓内验证的 runtime enforcement 缺陷。
不 commit / 不 push / 不 merge。

## 改动清单

| 文件 | 缺陷 | 改动 |
| --- | --- | --- |
| `.claude/hooks/pre_tool_guard.py` | D3（绝对路径保护死代码）+ D3/Bash（写入受保护路径未拦） | 新增 `_repo_rel()` 归一化绝对路径→相对 REPO_ROOT；`_is_protected_file`/`_touches_protected_dir` 改用之；新增 `_redirect_targets`/`_is_write_redirect` 拦重定向写目标；`_check_bash` 内加 touch/ln/tee 目标检测 |
| `.claude/settings.json` | D6（NotebookEdit 盲区）+ D3/D6（mlruns permission 缺口）+ D5（PostToolUse 接线不符文档） | PreToolUse matcher `Bash\|Edit\|Write`→`Bash\|Edit\|Write\|NotebookEdit`；deny 补 6 受保护目录的 `NotebookEdit(**)` + `mlruns/**` 的 Edit/Write/NotebookEdit；PostToolUse 裸 `ruff format` 换成调 `format_changed_python.py` |
| `.claude/hooks/format_changed_python.py` | D5（ruff 缺失静默） | ruff 缺失从静默 exit 0 改为「打印可见 stderr 提示后 exit 0」，且仅在确有待格式化 `.py` 时提示（非 py 编辑不刷屏） |
| `.claude/ANATOMY.md` | D5（文档措辞） | line 39 明确「Claude PostToolUse 与 Codex 均调此脚本」+ ruff 缺失可见提示 |
| `.codex/config.toml` | D7（compact 后两表面身份重申不等价） | SessionStart identity matcher `startup\|resume\|clear`→`+compact`，更新注释说明与 Claude 对齐 |
| `.githooks/pre-push`（新增，+x） | D2（git 层无 push-main 拦截，Codex 表面绕过） | 纯 sh surface-agnostic git hook，逐行查 stdin 的 remote ref，refs/heads/main\|master 默认拒绝，逃生 `CLAUDE_ALLOW_PUSH_MAIN`/`CODEX_ALLOW_PUSH_MAIN` ∈ {1,true,yes} 或 `--no-verify`；删除 ref 到 main 同样拦 |

## 设计要点

- `_repo_rel`：绝对路径 `Path(p).resolve().relative_to(REPO_ROOT)`；repo 外绝对路径 ValueError→返回原样（受保护目录都在 repo 内，故不受保护为正确行为）；相对路径去引号/去 `./` 原样返回，**既有相对路径行为不回退**。
- 重定向检测复用 shlex(posix, punctuation_chars)：`>` `>>` `&>` 为独立 token，fd 数字（`1`/`2`）被拆开，故 `2>/dev/null` 目标是 `/dev/null`（非受保护，天然放行）。引号字面量被 posix 去引号成单 token，无重定向算子 → 无误伤。
- touch/ln/tee 只查非选项参数（`-` 开头跳过），`tee -a`/`ln -s` 正确。
- 未碰 launch-gate / doc-lifecycle / agent-conflict / rm-mv 逻辑；未动 D1/D4（Codex apply_patch/identity）。

## 自测（确切命令 + 输出）

### D3 + D3/Bash（`/tmp/test_guard.py` 驱动，24 例全 OK）
`python3 /tmp/test_guard.py` → 全部 `[OK]`：
- Write abs `lab/data`/`mlruns`/`.env` → exit 2；rel `lab/data/x` → exit 2（不回退）；abs `/tmp/x`、abs `README.md` → exit 0
- NotebookEdit abs `lab/data/n.ipynb` → exit 2
- `touch lab/data/x`、`echo hi > mlruns/y`、`echo hi >> mlruns/y`、`tee lab/models/z`、`echo x | tee -a lab/models/z`、`ln -s /etc/passwd lab/data/l`、`cmd &> lab/data/x`、`cmd 2> lab/data/x` → 各 exit 2
- 负例 `echo "lab/data 是受保护的"`、`cat lab/data/x`、`echo hi > /tmp/ok`、`echo x > ./scratch.txt`、`echo hi 2>/dev/null`、`touch ./scratch.txt` → 各 exit 0
- 回归 `rm -rf lab/data` exit 2、`git push origin main` exit 2、`git push origin fix/...` exit 0

### D6
`python3 -m json.tool .claude/settings.json` → `settings.json OK`（JSON 合法）；matcher 含 NotebookEdit；deny 含 6 目录 NotebookEdit + mlruns 三条。

### D5
- ruff 不在 PATH（`which ruff`→none）。喂 `.py` payload → stderr `[format_changed_python] ruff 不在 PATH：跳过格式化（安装 ruff 或 uvx ruff 以启用）`，exit=0
- 喂 `README.md`（非 py）payload → 静默 exit=0
- settings.json PostToolUse 第一条已改为调 `format_changed_python.py`

### D7
`grep 'matcher = "startup|resume|clear|compact"' .codex/config.toml` → line 80 命中；`/tmp/toml_check.py`（tomllib.load）→ `toml OK`

### D2（`.githooks/pre-push`，未真 push）
- `refs/heads/main` → exit 1 拒绝；`refs/heads/master` → exit 1；删除 ref（local sha 全 0）到 main → exit 1
- `refs/heads/topic` → exit 0；`CLAUDE_ALLOW_PUSH_MAIN=1` 喂 main → exit 0；`CODEX_ALLOW_PUSH_MAIN=yes` 喂 main → exit 0
- 多行含一个 main → exit 1

### 全量门禁
`uv run --with pyyaml python3 scripts/validate-governance.py --strict` → exit 0 全绿。
`python3 scripts/check-anatomy-drift.py` → 0 漂移（.githooks 未在任何 ANATOMY 做文件粒度登记，新增 pre-push 不触发 same-commit）。

### 末态 git status
仅 `M .claude/ANATOMY.md`、`M .claude/hooks/format_changed_python.py`、`M .claude/hooks/pre_tool_guard.py`、`M .claude/settings.json`、`M .codex/config.toml`、`?? .githooks/pre-push`。无测试残留（测试脚本在 /tmp）。

## 已知风险 / 未覆盖
- `_redirect_targets` 在不平衡引号时 shlex 抛 ValueError→返回空（保守放行该向量），与既有 `_commands` 回退风格一致。
- pre-push 仅在 clone 配了 `core.hooksPath=.githooks` 时生效（与 pre-commit 同前提，bootstrap 已启用）；docstring 已点明。
- 未动 D1/D4（Codex apply_patch 绝对路径 / Codex identity），按边界另行处理。
