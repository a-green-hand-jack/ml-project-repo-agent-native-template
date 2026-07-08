#!/usr/bin/env bash
# repo-local statusline：把 model / 目录 / git 分支 / worktree / cost 变成可见仪表盘。
# 对齐 .agent/principles.md「没有仪表盘就别开长途」。
#
# Claude Code 通过 stdin 传入 JSON（model / workspace / cost 等字段随版本可能变化）。
# 本脚本防御式解析：无 jq 或字段缺失时优雅降级为最小行，绝不报错、绝不阻断。
# adopter 可直接删除 settings.json 的 statusLine 段以回退到全局 statusline。

input="$(cat)"

# --- 取字段：有 jq 用 jq，否则留空降级 ---
model=""; cur_dir=""; cost=""
if command -v jq >/dev/null 2>&1; then
  model="$(printf '%s' "$input"  | jq -r '.model.display_name // empty' 2>/dev/null)"
  cur_dir="$(printf '%s' "$input" | jq -r '.workspace.current_dir // .cwd // empty' 2>/dev/null)"
  cost="$(printf '%s' "$input"    | jq -r '(.cost.total_cost_usd // empty) | select(. != null)' 2>/dev/null)"
fi

# 目录：优先 JSON，退回 $PWD
[ -z "$cur_dir" ] && cur_dir="$PWD"
dir_name="$(basename "$cur_dir" 2>/dev/null)"

# git 分支 + worktree 名（best-effort，非 git 仓库则留空）
branch=""; worktree=""
if git -C "$cur_dir" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  branch="$(git -C "$cur_dir" branch --show-current 2>/dev/null)"
  [ -z "$branch" ] && branch="$(git -C "$cur_dir" rev-parse --short HEAD 2>/dev/null)"
  top="$(git -C "$cur_dir" rev-parse --show-toplevel 2>/dev/null)"
  [ -n "$top" ] && worktree="$(basename "$top")"
fi

# --- 拼装：只展示拿到的字段 ---
parts=()
[ -n "$model" ]    && parts+=("$model")
[ -n "$dir_name" ] && parts+=("📁 $dir_name")
[ -n "$branch" ]   && parts+=("⎇ $branch")
[ -n "$worktree" ] && [ "$worktree" != "$dir_name" ] && parts+=("wt:$worktree")
if [ -n "$cost" ]; then
  printf -v cost_fmt '$%.4f' "$cost" 2>/dev/null && parts+=("$cost_fmt")
fi

# 用 " | " 连接
out=""
for p in "${parts[@]}"; do
  [ -z "$out" ] && out="$p" || out="$out | $p"
done
[ -z "$out" ] && out="claude-code"
printf '%s' "$out"
