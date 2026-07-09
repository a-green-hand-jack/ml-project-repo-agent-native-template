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

## Subagent reports

- **artifact-librarian**：登记 `result-001/002`、`trace-001/002` 到 `lab/artifacts/{result,trace}-index.yaml`；只提 proposal，未删/未动任何 bytes；把「evidence.yaml 是否要补一条」正确转给了后续 owner。
- **experiment-orchestrator**：新增 `run-elf-pytorch-runtime-smoke-replay-claude`（ledger）+ `ev-elf-pytorch-runtime-smoke-replay-claude`（evidence，grade=log，如实标注依赖版本漂移），挂到既有 claim 但未 promote；主动补上了 artifact-librarian 留的 index 交叉引用缺口。
- **repo-doc-steward**：发现 `lab/docs/` 完全没有人类可读导航，新增 `lab/docs/README.md`；发现 `lab/code/README.md`/`AGENTS.md` 相对 `ANATOMY.md` 过期（只列旧 5 个子目录），已更新；发现 `lab/docs/overview.md` 有一处指向旧路径 `code/docs/` 的悬空引用但按契约不改非导航文件，正确上报而非越权修改。
- **branch-reporter**：写 `memory/worktree-status.md` + `memory/branches/case-elf-template-replay.md`；发现并指出「migration commit message 说 validator 全过，但当时提交的 current-status.md 表格还写着未跑」的自相矛盾（已在本文件修正）；正确将 merge_target 记为「无——独立 case 分支」。
- **test-runner**：只跑了指定的 `pytest -q tests` 命令，未擅自扩大范围，正确避开了 `lab/code/external/ELF` 的 cwd 陷阱，2 passed。

## Open issues / blockers

- `lab/docs/overview.md` 里一处指向旧路径 `code/docs/` 的悬空引用未修（repo-doc-steward 权限边界之外，留给下一步）。
- `lab/artifacts/*.yaml` 的两条新 index（result-002/trace-002，scaffold compileall/pytest）目前没有对应 claim，是有意的空缺（不是 ELF 复现研究主张，只是 scaffold 自检），留给 human 判断是否要建 claim。
- 本 case 分支不打算合并回 main；push 与否由 human 事后决定。

## Exact next steps

1. 写最终功能测试报告到 `lab/docs/audits/`（本 session 剩余工作）。
2. human 视需要修 `lab/docs/overview.md` 的悬空引用（非阻塞）。
3. human 决定：是否 push 这个 case 分支到远程、是否需要更多轮 subagent/skill 覆盖（本轮只覆盖了 5/15 个 subagent、0 个真正走完的 skill workflow，是有意抽样，不是全量）。

## Do-not-forget

- 这个 worktree 分支叫 `worktree-case+elf-template-replay`，路径
  `.claude/worktrees/case+elf-template-replay/`；退出时用 ExitWorktree，`action: keep`
  （测试产物要保留，不要 remove）。
- `~/Projects/ELF-template-case` 是只读参考源，不要改；真正复现执行环境只能是本机 CPU。
- 用户已明确：测试深度 = 同时重跑 ELF smoke；落地位置 = 模板仓库自己的新分支/新目录
  （即本 worktree）；远程动作 = 全程本地，push 由用户事后决定。
