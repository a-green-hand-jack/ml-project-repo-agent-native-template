# 53 issue topology + 实验阶段隔离（干将·修·阶段隔离doctrine）

分支：`fix/53-issue-topology-phase-isolation`（基于 main）
worktree：`/home/user/Projects/wt-53`
范围：**只改文档/模板**，无新依赖、无 issue 编排器、无第二套 plan 格式。未 commit。

## 改了什么（6 文件，+52 行）

1. `AGENTS.md` — 硬边界后新增 `## issue topology（长任务拆分）`：列出应拆 child/sub-issue 的五种情况（独立 PR / 独立 run / 独立 blocker / 不同 owner·worktree / parent 已混入多阶段）；parent 只保留目标·已接受决策·child 索引·最终汇总；写明非目标（不强制全拆、不自动批量建 child）。
2. `plans/README.md` — 新增 `## 两阶段实验协议（prepare/freeze vs execute/observe）`：freeze commit 必录 允许/禁止写入路径 + config/prompt/schema hash + 停止条件；execute 阶段不得改冻结面，需改则标 `calibration/invalid`、停止评分、转 child issue。
3. `.agent/templates/plan-doc.zh.md` — 在 `## Linked issue / PR` 加 `parent issue` / `child issue / phase` 两行；新增 `## 实验冻结面（仅实验类 plan；非实验填 n/a）` 段含 `frozen commit` / `allowed writes` / `forbidden writes` / `on drift`。未新增第二套格式，沿用现有 `## 段` 风格。
4. `.agent/action-boundary.md` — 「可做」后新增 `## execution-only agent（评分 run 中）`：允许动作只含 运行/读取/写 trace·result·state·log/机械汇总·报告；schema/prompt/adapter/strategy/runner/依赖/产品源码属冻结面，评分 run 中不得改。
5. `lab/code/experiments/README.md` — 新增「定义 vs 产物（冻结纪律）」：此处是定义文件=冻结面，缺陷→停止+建 child issue。
6. `lab/runs/README.md` — 新增「定义 vs 产物（冻结纪律）」：此处是运行产物，缺陷处理=停止+建 child issue+标 invalid，不现场修补。

## 第 6 步（validate-governance）判断结论：不改 validator

先查：`check-doc-lifecycle.py` **确实**解析 plan doc 段——`REQUIRED_PLAN_SECTIONS = ("Allowed paths","Forbidden paths","验证标准")`，且仅对 `approved`/`implementing`（`SCOPE_REQUIRED`）态强制。

但**未**为本任务加字段存在性校验，理由：
- 新增的阶段隔离字段（frozen commit / allowed writes / forbidden writes / on drift）是**实验类 plan 专属**，非所有 plan 通用。把它们加进 `REQUIRED_PLAN_SECTIONS` 会对所有 approved/implementing plan（含 doc/refactor 类）强制这些实验专属字段，语义错误且与模板「仅实验类」定位冲突。
- 对模板文件本身做「字段存在性」检查是一种**新的校验面/解析器**，issue 明确「不为此新建解析器」。
- 二者都违背 issue 的最小 diff 与非目标约束。

故遵 issue 最小性与「不新建解析器」，模板字段作为脚手架自立，不加 validator 强制。此为判断取舍，已上报父级。

## 验证

`uv run --with pyyaml python3 scripts/validate-governance.py --strict` → **EXIT=0**，`[validate-governance] OK — 0 error(s), 0 warning(s)`。
`git diff --stat` → 仅上述 6 个文档/模板文件，+52 行，无文件新增/移动（不触发 same-commit ANATOMY 规则）。
