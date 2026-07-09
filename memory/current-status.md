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
- Round 2（本次追加）：`.claude/settings.json`（F2 修复后版本，三条 hook 命令 + `statusLine.command`
  均已锚定 `$CLAUDE_PROJECT_DIR`）、`.agent/behavior-contract.md`（新增「文档默认语言」小节）、
  `human/decisions/20260709-doc-language-default-chinese.md`、
  `lab/traces/human-cc/2026-07-09/hook-cwd-drift-stuck-recovery/trace.md`（本 session 自己写的第二轮
  复测记录）。

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
- F2（hook 自锁）修复走了独立的 `worktree-agent-a3c6377d6ce9ebc36`（off `main`）分支，而不是在本
  case 分支里直接改：把 `.claude/settings.json` 的三条 hook 命令 + `statusLine.command` 全部锚定到
  `$CLAUDE_PROJECT_DIR` 绝对路径；同时新增了跨 agent 通用的 doctrine 规则——`.agent/behavior-contract.md`
  「文档默认语言」小节 + ADR `human/decisions/20260709-doc-language-default-chinese.md`：书面文档默认
  中文，除非 human 另有要求。该分支已 PR（#1）squash-merge 进 `main`（commit `6fed240`），随后
  `git merge origin/main` 合入本 case 分支——clean merge，validators 仍全过。
- 修复后在**同一个仍在运行的 session** 里做了一次真实（非合成）复测：真 `cd` 进
  `lab/code/external/ELF`，故意重现原触发条件——**仍然复现了修复前的报错**（报错里的命令还是旧的裸
  相对路径，不是磁盘上已经锚定的新版本）。用 ExitWorktree(keep) + EnterWorktree(path=...) 试图刷新
  hook 配置后重试，**依然复现同样的失败**。结论记为假设而非确证的 bug：hook 的锚定路径修复经独立
  subagent 用合成 JSON 测试确认逻辑本身是对的，但**已经在运行中的 session 似乎在 session 开始时就
  固定了 hook 配置**，不会因为磁盘上 `.claude/settings.json` 改了、或者 Exit/EnterWorktree 而重新加载；
  修复要在**全新 session**里复测才能验证是否对新 session 生效。完整记录见
  `lab/traces/human-cc/2026-07-09/hook-cwd-drift-stuck-recovery/trace.md`（"事件序列（第二轮，修复后，
  同一 session 内复测）"一节）。

## Commands + results

| command | 结论 |
| --- | --- |
| `python scripts/validate-governance.py`（migration-baseline commit `c164232`） | OK — 0 error(s), 0 warning(s)（含 check-agent-harness / check-anatomy-drift 子检查） |
| `python scripts/check-same-commit.py --staged`（同上） | OK —— 结构改动均在同变更集更新了对应 ANATOMY.md |
| 阴性探针：临时把 `claim-elf-source-identity` 改成 `status: supported`（证据仍是 log 级）再跑 validator | 按预期 FAIL：`overclaim：... 但最强证据低于 metric`；验证后立即 revert |
| `git -C lab/code/external/ELF clone` lillian039/ELF → checkout `pytorch_elf`（commit `b29d8833609e9ab7f67cd9da39435ac5cea04837`） | 独立 re-clone 到本仓库 `lab/code/external/ELF`（gitignored），commit 与 2026-07-08 迁移记录一致 |
| `uv pip install --python lab/code/external/.venv-elf-cpu/bin/python --extra-index-url https://download.pytorch.org/whl/cpu -r lab/code/external/ELF/requirements.txt` | torch==2.13.0+cpu, transformers==4.44.2, datasets==2.19.1, einops==0.8.2, huggingface-hub==0.36.2, sacrebleu==2.6.0, rouge-score==0.1.2, wandb==0.28.0, muon-optimizer==0.1.0（import 名 `muon`）全部导入成功 |
| （cwd=`lab/code/external/ELF`, `PYTHONPATH=$PWD/src`）`configs.config.load_config_from_yaml("src/configs/training_configs/train_owt_ELF-B.yml")` + `apply_config_overrides(..., batch_size=2, max_length=4)` | 配置加载与 override 均 OK |
| `modules.model.ELF(text_encoder_dim=8, max_length=4, hidden_size=16, depth=1, num_heads=2, vocab_size=32, num_time_tokens=1, num_self_cond_cfg_tokens=0)` tiny 合成前向（`decoder_step_active=True`） | 输出 shape (2,4,8)，decoder logits shape (2,4,32)；`torch.cuda.is_available()` 为 False（本机 CPU-only，无 GPU/EPFL 访问） |
| `python3 -m compileall -q src eval experiments scripts tests`（`lab/code/`，迁移 scaffold 本身） | exit 0 |
| `uv run --no-project --with pytest --python 3.11 python -m pytest -q tests`（`lab/code/`） | 2 passed |
| 未做：数据集加载、checkpoint 加载、GPU 执行、训练/生成循环、指标复现 | 明确排除在本次 replay 范围外 |
| 落地：新增 `run-elf-pytorch-runtime-smoke-replay-claude`（`lab/research/experiment-ledger.yaml`）、新增证据 `ev-elf-pytorch-runtime-smoke-replay-claude`（`evidence.yaml`，grade=log），并挂到既有 `claim-elf-pytorch-runtime-smoke` 的 evidence 列表（`claims.yaml`，status 仍为 partial，未 promote） | 未新建 claim；`verified_by_fresh_reviewer` 保持 false（非正式 fresh-reviewer session-boundary 复核） |
| hook 探针：`sudo echo`、`curl\|sh`、`rm -rf lab/data/...`、`mv ... lab/data/...`、Write 到 `lab/data/...` | 全部按预期被 permission-deny 层或 `pre_tool_guard.py` 拦截 |
| hook 探针（合成 stdin JSON，避免真推）：`git push origin HEAD:main`（无 escape） / 同命令 + `CLAUDE_ALLOW_PUSH_MAIN=1` / `git push origin <topic 分支>` | 依次：deny（exit 2）/ allow（exit 0）/ allow（exit 0），符合预期 |
| 意外发现：cwd 漂进 `lab/code/external/ELF`（vendored，有自己的 `.git`）后，`pre_tool_guard.py`（相对路径定位）导致后续所有 Bash/Edit/Write 被挡，且自锁（`cd` 回去的命令也被挡） | 用 ExitWorktree(keep) + EnterWorktree(path=worktree 根) 绕过恢复；已写入测试报告 |
| 5 个代表性 subagent（artifact-librarian / experiment-orchestrator / repo-doc-steward / branch-reporter / test-runner）并行派生 | 全部完成，行为符合各自边界契约；repo-doc-steward 额外发现并修了 `lab/docs/` 缺 README、`lab/code/README.md`/`AGENTS.md` 过期；branch-reporter 发现并修了 `memory/ANATOMY.md` 漏登记 `worktree-status.md` |
| subagent-router-agent 把「把功能测试报告 + human review 文档翻成中文」路由给某执行 agent（commit `ab599ac`） | 完成，两份文档（本轮功能测试报告、human review 文档）已译为中文 |
| （独立分支 `worktree-agent-a3c6377d6ce9ebc36`）F2 修复：锚定 3 条 hook 命令 + `statusLine.command` 到 `$CLAUDE_PROJECT_DIR`，新增文档默认语言 doctrine | 独立 subagent 用合成 JSON 实测确认 `$CLAUDE_PROJECT_DIR` 在 hook 子进程里存在；PR #1 squash-merge 进 `main`（commit `6fed240`） |
| `git merge origin/main`（把含 F2 修复的 main 合进本 case 分支） | clean merge，`python scripts/validate-governance.py` 仍全过 |
| 同一 session 内真实复测 F2：`cd lab/code/external/ELF` → 后续命令；ExitWorktree(keep)+EnterWorktree(path=...) 后重试同一操作 | 两次均**仍复现修复前的旧报错**（裸相对路径），怀疑是"运行中 session 的 hook 配置在 session 开始时已固定，不随磁盘改动或 Exit/EnterWorktree 刷新"；已写入 `lab/traces/human-cc/2026-07-09/hook-cwd-drift-stuck-recovery/trace.md`，未在全新 session 里复测确认 |

## Subagent reports

- **artifact-librarian**：登记 `result-001/002`、`trace-001/002` 到 `lab/artifacts/{result,trace}-index.yaml`；只提 proposal，未删/未动任何 bytes；把「evidence.yaml 是否要补一条」正确转给了后续 owner。
- **experiment-orchestrator**：新增 `run-elf-pytorch-runtime-smoke-replay-claude`（ledger）+ `ev-elf-pytorch-runtime-smoke-replay-claude`（evidence，grade=log，如实标注依赖版本漂移），挂到既有 claim 但未 promote；主动补上了 artifact-librarian 留的 index 交叉引用缺口。
- **repo-doc-steward**：发现 `lab/docs/` 完全没有人类可读导航，新增 `lab/docs/README.md`；发现 `lab/code/README.md`/`AGENTS.md` 相对 `ANATOMY.md` 过期（只列旧 5 个子目录），已更新；发现 `lab/docs/overview.md` 有一处指向旧路径 `code/docs/` 的悬空引用但按契约不改非导航文件，正确上报而非越权修改。
- **branch-reporter**：写 `memory/worktree-status.md` + `memory/branches/case-elf-template-replay.md`；发现并指出「migration commit message 说 validator 全过，但当时提交的 current-status.md 表格还写着未跑」的自相矛盾（已在本文件修正）；正确将 merge_target 记为「无——独立 case 分支」。
- **test-runner**：只跑了指定的 `pytest -q tests` 命令，未擅自扩大范围，正确避开了 `lab/code/external/ELF` 的 cwd 陷阱，2 passed。
- **（翻译执行 agent，commit `ab599ac`）**：把本轮功能测试报告与 human review 文档译为中文；未改动其余
  文件、未改结论内容，仅语言转换。
- **checkpoint-writer（本 subagent，本次调用）**：只更新了 `memory/current-status.md`，增量补写 F2 修复
  → merge → 同 session 复测失败的完整链条；未碰源码/配置/其他 memory 文件。

## Open issues / blockers

- `lab/docs/overview.md` 里一处指向旧路径 `code/docs/` 的悬空引用未修（repo-doc-steward 权限边界之外，留给下一步）。
- `lab/artifacts/*.yaml` 的两条新 index（result-002/trace-002，scaffold compileall/pytest）目前没有对应 claim，是有意的空缺（不是 ELF 复现研究主张，只是 scaffold 自检），留给 human 判断是否要建 claim。
- 本 case 分支不打算合并回 main；push 与否由 human 事后决定。
- **F2 修复未在全新 session 里确证**：同一运行中 session 的两次实测复现了旧的失败行为（见上表 +
  trace.md）。这不推翻修复本身（磁盘上 `.claude/settings.json` 已确认是锚定版本，独立合成 JSON 测试
  也确认逻辑对），但意味着「F2 已修好」目前只是**推断**，还需要一次全新 session 里的 `cd` 进
  `lab/code/external/ELF` 复测才能算实测确证——这是 round 2 待办里优先级较高的一项，但可能超出本
  checkpoint-writer 调用者的当前 session 能力范围（因为按 trace.md 的假设，必须是全新 session）。

## Exact next steps

1. Round 2：依次派生并观察剩余未测的 subagent——experiment-monitor、hook-maker-agent、
   interactive-plan-writer、repo-researcher、session-boundary-agent、sub-agent-maker-agent、
   workflow-recipe-harvester（subagent-router-agent 已在 round 1/翻译任务里用过）——以及至少一个
   `.claude/skills/*` 入口（目前 0 个真正走完的 skill workflow），记录各自是否符合边界契约、有无
   越权/漏做。
2. 若有机会开一个全新 session（非本 worktree 内 Exit/EnterWorktree 那种）：复测 F2——`cd` 进
   `lab/code/external/ELF` 后跑任意后续 Bash/Edit/Write，确认不再报旧的裸相对路径错误。这是唯一
   能真正确证 F2 的方法；结果无论正反都要写回 trace.md 和本文件。
3. 写/更新最终功能测试报告到 `lab/docs/audits/`（汇总 round 1 + round 2 全部发现，含 F2 的
   两阶段验证记录）。
4. human 视需要修 `lab/docs/overview.md` 的悬空引用（非阻塞）。
5. human 决定：是否 push 这个 case 分支到远程、round 2 subagent/skill 覆盖是否已经够（本轮目标是把
   15 个 subagent 里剩下的都过一遍 + 至少部分 skill）。

## Do-not-forget

- 这个 worktree 分支叫 `worktree-case+elf-template-replay`，路径
  `.claude/worktrees/case+elf-template-replay/`；退出时用 ExitWorktree，`action: keep`
  （测试产物要保留，不要 remove）。
- `~/Projects/ELF-template-case` 是只读参考源，不要改；真正复现执行环境只能是本机 CPU。
- 用户已明确：测试深度 = 同时重跑 ELF smoke；落地位置 = 模板仓库自己的新分支/新目录
  （即本 worktree）；远程动作 = 全程本地，push 由用户事后决定。
- 新增 doctrine：`.agent/behavior-contract.md`「文档默认语言」——书面文档默认中文，除非 human 另有
  要求（本文件也遵守这条，continue 用中文写）。
- **改了 `.claude/settings.json` 的 hook/statusLine 配置后，不要在同一个已经运行中的 session 里
  指望它立刻生效**——哪怕用了 ExitWorktree/EnterWorktree。要验证必须开一个全新 session。这条是本轮
  用真实（非合成）操作两次复现出来的强证据，不是猜测。
- F2 相关的两个关键 commit：修复本身 `6fed240`（squash-merge 进 `main`）、翻译工作 `ab599ac`
  （本 case 分支上）；F2 修复源分支是 `worktree-agent-a3c6377d6ce9ebc36`（off `main`，非本 case
  分支的子节点）。
