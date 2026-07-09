# current-status.md

> **活文件**。这是当前状态的单一真相源。每次 session 结束、compact 前、完成小目标时更新。
> fresh session 应能只读本文件 + `session-tree.md` 就接续工作。
> 下面是模板骨架，逐项填写，不要留空占位而不说明。

## 当前 objective

把 `ELF-template-case`（旧模板世代的案例仓库）迁移进本模板结构，然后测试
validators / hooks / skills / subagents 是否如预期工作；先测试，不急着修模板本身的问题。

## Constraints

- 本机无 EPFL 集群 / GPU 访问，只能做 CPU-only 本地验证。
- 不 push 到任何远程，除非 human 事后要求。
- 不改 `~/Projects/ELF-template-case`（只读参考源）。
- 测试阶段发现模板问题只记录，不修复（见 `PROJECT.md` 与 human 的迁移深度决定）。

## Files inspected

- `~/Projects/ELF-template-case`：README.md、PROJECT.md、docs/audits/*、memory/current-status.md、
  human/reviews/results/elf-case-smoke-result.md、memory/boards/*.yaml、
  `.harness/skills/skills/research-template-case-harness-test/`（旧压测方法论）。
- 本模板：AGENTS.md、DESIGN.md、ANATOMY.md 全链路、`.claude/skills/worktree-pr-flow`、
  `scripts/validate-governance.py`、`check-anatomy-drift.py`、`check-agent-harness.py`、
  `check-same-commit.py`、`lab/{code,research,artifacts,infra}/ANATOMY.md`、
  `deliverables/ANATOMY.md`、`memory/ANATOMY.md`、`human/ANATOMY.md`。

## Files modified

- 迁移落地：`lab/code/{src/project_code,eval,experiments,scripts,configs,pyproject.toml,...}`、
  `lab/infra/launch/{envs,submit/slurm}`、`lab/infra/paths/remote-projects.yaml`、
  `lab/docs/{code,audits,designs,experiments,timelines,updates,overview.md,reference/,research-narrative/}`、
  `deliverables/paper/*`、`human/reviews/results/elf-case-smoke-result.md`、`.gitignore`。
- Schema 转换：`lab/research/{claims,evidence,experiment-ledger}.yaml`（旧 `memory/boards/*.yaml`
  按新证据分层重新分级，`supported` 降级为 `partial`，见下方 Decisions）。
- 同步更新：`lab/code/ANATOMY.md`（新增 `eval/`、`external/` 子目录）、`lab/ANATOMY.md`
  （新增 `docs/` leaf）、`lab/infra/ANATOMY.md`（`launch/`、`paths/` 落地说明）、`PROJECT.md`。

## Decisions

- 旧 `memory/boards/claims.yaml` 里 4 条 `status: supported` 的 claim，迁移时如实降级为
  `status: partial`：它们的证据只是 clone/py_compile/依赖导入/一次 CPU 前向 smoke，按新模板
  `lab/research/ANATOMY.md` 的证据分层只够 `grade: log`，不够 `supported` 要求的
  `>= metric`。这本身是一条测试发现（新 validator 比旧 boards.yaml 的自由文本 certainty
  字段更严格地拦住了 overclaim），完整记录见 `lab/docs/audits/` 下本轮的功能测试报告。
- `risks.yaml` / `actions.yaml` / `provenance.yaml` / `source-visibility.yaml` 在新模板没有
  专属 YAML 槽位，落地为 `lab/docs/research-narrative/project-board-risks-actions.md` 与
  `lab/docs/reference/provenance.md`（纯文档，非 validator 校验对象）。
- `reference/`、`research-artifact/`、`docs/` 三个旧顶层目录统一落到 `lab/docs/` 下的子目录，
  遵守新模板「不设通用 docs/、根目录白名单」的设计（`scripts/check-agent-harness.py` 的
  `ROOT_WHITELIST`）。
- 真实的 `lillian039/ELF` 上游代码不 vendor 进这个 case 分支的 git 历史，clone 到
  `lab/code/external/ELF`（gitignore），只登记 provenance——沿用旧周期 `code/external/ELF`
  的位置约定，但这是本次迁移新增、模板本身未预定义的槽位。

## Commands + results

| command | 结论 |
| --- | --- |
| （迁移阶段尚未跑 validator，见 Exact next steps） | |

## Subagent reports

（尚未派生 subagent；计划在「Exercise representative subagents and skills」阶段派生并在此追加摘要。）

## Open issues / blockers

- `lab/artifacts/*.yaml` 尚未登记任何真实 index（旧 `artifact/README.md` 只是占位说明，
  没有真实产物）；计划在 ELF smoke test 产出后由 artifact-librarian 补登记。
- 尚未运行任何 validator / 尚未重新 clone 真实 ELF 代码 / 尚未做 hook 探针测试。

## Exact next steps

1. 运行 `python scripts/validate-governance.py`（含 check-agent-harness / check-anatomy-drift）
   与 `python scripts/check-same-commit.py --staged`，记录结果。
2. 视需要修正迁移引入的 anatomy/gitignore 问题（迁移本身的自洽性，非模板 bug）。
3. `git add` + commit 这次迁移基线（提交信息说明来源与迁移映射）。
4. re-clone `lillian039/ELF`（`pytorch_elf` 分支）到 `lab/code/external/ELF`，跑 CPU-only 依赖
   导入 + tiny forward smoke（无 GPU/EPFL）。
5. 用 artifact-librarian 把 smoke 结果登记进 `lab/artifacts/*-index.yaml`。
6. 派生代表性 subagent/skill（experiment-orchestrator、checkpoint-writer、repo-doc-steward、
   branch-reporter、test-runner + worktree-pr-flow/experiment-workflow/artifact-indexing/
   anatomy-drift-control），观察行为是否符合各自 SKILL.md/agent 定义。
7. 做几个安全的 hook/权限探针（受保护路径 Edit、push-to-main 尝试等），预期均被拦截。
8. 把发现写成 `lab/docs/audits/` 下的功能测试报告 + `human/reviews/results/` 摘要，更新本文件。

## Do-not-forget

- 这个 worktree 分支叫 `worktree-case+elf-template-replay`，路径
  `.claude/worktrees/case+elf-template-replay/`；退出时用 ExitWorktree，`action: keep`
  （测试产物要保留，不要 remove）。
- `~/Projects/ELF-template-case` 是只读参考源，不要改；真正复现执行环境只能是本机 CPU。
- 用户已明确：测试深度 = 同时重跑 ELF smoke；落地位置 = 模板仓库自己的新分支/新目录
  （即本 worktree）；远程动作 = 全程本地，push 由用户事后决定。
