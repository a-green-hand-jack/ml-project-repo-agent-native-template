---
description: 以 fresh reviewer 审查当前 diff（correctness/回归/测试/复现/数据安全）
---

以 fresh reviewer 审查当前 diff。聚焦：
- correctness、regressions、missing tests
- research reproducibility
- data/checkpoint safety
- anatomy impact（结构改动是否同 commit 更新了 ANATOMY / ledger）
- 变更自检清单是否已被实现方过完（分类矩阵/三项前置声明/exact-base 双检+路径自报自查/验证纪律/
  授权分级——正文见 `.claude/skills/worktree-pr-flow/SKILL.md` 的「变更自检清单」，此处不复制）；
  缺失、明显未过、或与实际改动不符时应列为 finding

不要先写总结。按 severity 列出 findings，附文件引用与建议修复。
最后跑 `python scripts/validate-governance.py` 报告结果。
