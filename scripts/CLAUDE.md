# scripts/ — Claude Code 入口

- 改动前后跑 `python scripts/validate-governance.py`。
- 两类脚本，别混着看：**只读校验脚本**（`check-agent-harness.py` / `check-anatomy-drift.py` /
  `validate-governance.py` / `check-adoption-integrity.py` / `check-same-commit.py`）只读、只报告、
  只返回退出码；**有写副作用的 mutating 脚本**（`adopt-existing-repo.py` / `bootstrap-project.py` /
  `sync-codex-adapters.py` / `bump-template-version.py` / `template-sync.py`）会写文件/跑 `git config`
  等，改动前确认目标 repo 路径正确。全部无第三方硬依赖。
- `_agent_surface.py` 不属于以上两类：没有 `__main__`，不能直接运行，是
  `bootstrap-project.py`/`adopt-existing-repo.py` 共用的 postflight 渲染 helper（`importlib`
  按路径加载）。
- 新增检查项时对应到某条 `.agent/` doctrine，并更新 `README.md`。
