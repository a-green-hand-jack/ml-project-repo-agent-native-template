---
name: bootstrap-project
description: 把一个刚从本模板派生（Use this template / gh repo create --template / clone+reinit）的新 repo 落地成自洽状态——写 .template.toml 版本锚点、启用 core.hooksPath、同步 Codex adapters、跑 governance；不猜测需要 human 信息的步骤，只报告待办。
---

> Codex adapter: generated from `.claude/skills/bootstrap-project/SKILL.md`. Do not edit this copy by hand; run `python scripts/sync-codex-adapters.py`.

# bootstrap-project

这是新项目落地器，不是迁移工具。目标 repo 已经拥有完整模板目录形态（GitHub template 派生本身
就会复制整棵树）；这个 skill 只负责把 README「派生后的落地步骤」里能自动化的部分收敛成一次
幂等命令，并把需要 human 信息的步骤显式列成待办。

## 适用边界

适用：刚用 "Use this template" / `gh repo create --template` / clone+`rm -rf .git && git init`
派生出的新 repo，目录形态已经是模板形态，只是版本锚点/hooksPath/adapters/governance 还没跑过。

不适用：迁移一个内容无关的已有 Git repo（用 `adopt-existing-repo` skill）；需要人工判断
CODEOWNERS owner、`PROJECT.md` 内容、要不要删无用目录的步骤（本 skill 只报告，不代做）。

## 输入 / 输出 artifact

- 输入：目标 repo 路径（已 `git init`/`git clone`）、`--origin <owner/repo>`（必须显式传入，不推断）。
- 输出：目标 repo 的 `.template.toml`、`lab/docs/audits/template-bootstrap/state/*.json`、
  `lab/docs/audits/template-bootstrap-report.md`。

## 需要读取的 ledger

- `plans/20260712-bootstrap-adoption-proof.zh.md`：当前 feature contract（任务树 A）。
- `.agent/template-versioning-policy.md`：`.template.toml` 与四站闭环的语义。
- `scripts/ANATOMY.md`：脚本维护点。

## 步骤

1. 确认目标已是 Git repo（`.git` 存在）。主路径是 **self-bootstrap**：在派生 repo 内运行它
   自己的脚本、目标就是自身（`.`）；用上游 checkout 的脚本对另一个路径运行也可以。脚本会拒绝
   把**上游模板 repo 自身**当目标（判据只看**身份 remote `origin`**：URL 归一化后——大小写
   不敏感、剥 `.git` 后缀——与 `--origin` 同 slug 即拒绝；`upstream` 等其它 remote 不参与，
   派生 repo 保留指回模板的 `upstream` remote 不会被误拒）。这是 best-effort 防呆护栏、不是
   安全边界：没有 remote 或 `origin` 被改名/改指向的模板 checkout 识别不出来，属已知残余风险。
2. 运行（在派生出的新 repo 内）：

   ```bash
   python scripts/bootstrap-project.py . --origin <owner/repo>
   ```

   这会依次做：写/确认 `.template.toml`（origin+version 锚点）、
   `git config core.hooksPath .githooks`（目标缺 `.githooks/` 视为模板树不完整，**硬失败**、
   非零退出，不会静默跳过）、`python scripts/sync-codex-adapters.py`（写入+`--check`）、
   `python scripts/validate-governance.py`。第二次以相同 `--origin` 重跑是幂等的
   （`.template.toml` 状态是 `confirmed` 而不是 `created`，不会报错；state/report 内容无实质
   变化时不改写、时间戳也不变——`created_at` 表示内容最后变化时间；`state/run-log.jsonl`
   是追加式审计日志，每次运行必追加一行，属预期行为）。
3. 若目标已存在 `.template.toml` 且其中 origin 与传入的不一致，命令会**报错并停止**、不碰任何文件；
   确认要覆盖再显式加 `--force`。
4. 读命令输出与 `lab/docs/audits/template-bootstrap-report.md`：
   - `human_todo`：CODEOWNERS owner、`PROJECT.md` 填写、是否删无用目录、Codex trust——这些不会被
     脚本代做，只会报告检测到的状态（如 `.github/CODEOWNERS` 是否仍是模板默认 owner）。
   - `agent_surface`：Claude/Codex 两侧配置文件就位情况与计数，机器事实源是随后单独跑的
     `check-agent-harness.py --strict` 与 `sync-codex-adapters.py --check`，不是这份 checklist 自己
     判定的。
5. 把上一步的 human todo 列表转成给 human 的简短清单，明确标注哪些是「已自动完成」（`.template.toml`、
   `core.hooksPath`、Codex adapters、governance）、哪些「仍需 human」（CODEOWNERS、PROJECT.md、
   删减目录、**Codex trust 本 repo**——这条无法脚本化，Codex 的 `.codex/config.toml` hooks 要先被
   human trust 才会加载）。

## 验证命令

```bash
python lab/evals/bootstrap/run-bootstrap-smoke.py
python /path/to/new-project/scripts/validate-governance.py --strict
python /path/to/new-project/scripts/check-agent-harness.py --strict
python /path/to/new-project/scripts/sync-codex-adapters.py --check
git diff --check
```

三个 validator 只能证明 Claude/Codex 两侧配置与 adapter 的**静态自洽**；不能证明当前 Codex
session 已经 trust 本 repo、已加载 project hooks。这一条运行时证据需要从目标 repo 启动一个
fresh Codex session 另行确认（见 plan A5），不能用静态检查结果替代。

## 失败时的 handoff

- `.template.toml` origin 冲突且未加 `--force`：命令已报错停止，不需要清理——没有任何文件被改动。
  确认是否真的要覆盖，再决定加不加 `--force`。
- `sync_codex_adapters` 或 `governance` 状态为 `failed`：读 report 里的 `stdout_tail`/`stderr_tail`，
  先在目标 repo 内单独重跑对应脚本定位问题，不要忽略后继续。
- `scripts/sync-codex-adapters.py` 或 `scripts/validate-governance.py` 状态为 `missing`：说明目标
  repo 的目录形态不完整（不是真正的模板派生 repo），停下确认目标路径是否选对。
