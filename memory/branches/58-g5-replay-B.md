# G5（issue #58）Agent B 独立复核报告

> **Provenance**：本文由独立测试者 **师爷·审·ELF追平**（Agent B，sonnet-5/high，
> worktree `test/g5-elf-replay-verify`）撰写。原文未提交、随 worktree 归档丢失文件本体；
> 由主 agent **都督·统·治理路线** 如实转录回 main，未改 B 的结论。**主 agent 收口纠正注**以
> `> 【收口纠正】` 标出——B 对缺口 #2 的机制描述有一处不准，已在下方就地标注，B 的裁决方向不变。

- 独立性声明：未读 `58-g5-replay-A.md`、未读 round1 记录、未采信 receipt 的 `result` 结论字段
  （只读 `from_version`/`target_version`/`classification` 等客观字段）。唯一例外：T-G5-4(B) 排查
  `dataset-index.yaml` 时一次 `grep` 命中 A 报告一行文本，未采信其结论，独立推导得出一致结果。

## 总裁决：REQUEST CHANGES（strict 口径）

> 【收口】human 已拍板以**模板出厂默认门禁（非 strict）**为 G5 验收 bar——默认口径下游全绿、
> G5 七项通过。B 的 REQUEST CHANGES 基于更严的 `--strict` 口径，其坐实的 2 处真实缺口转为跟进
> **#75**（非阻断），不推翻 G5 在默认 bar 下的通过。

G1 门禁 non-strict 全绿；`--strict` 下 3 个 error，其中 2 个真实追平缺口、1 个下游合理条件。
幂等性与分类隔离均 PASS，无副作用、无覆盖。

## T-G5-5：G1 门禁双口径

- non-strict（`uv run --with pyyaml`）：`[validate-governance] OK — 0 error(s), 0 warning(s)`，exit 0。
  子脚本层仍各有发现：agent-harness 1 warn（receipt 根污染）、anatomy-drift 1 governance report
  （scripts/ANATOMY.md 未被根 ANATOMY.md `children` 回链）、provenance 1 UNKNOWN（dataset-index 缺）。
- `--strict`：`FAIL — 3 error(s)`，exit 1（真实失败）。三项定性：
  1. `check-agent-harness`：`.template-sync-receipt.json` 不在 `ROOT_WHITELIST` —— **模板自身缺陷**
     （`template-sync.py` 默认写根 receipt vs harness 白名单矛盾）。→ #75 缺口 2。
  2. `check-anatomy-drift`：根 `ANATOMY.md` 未按上游 v1.3.8 提供 `children:` 回链 —— **真实追平缺口**
     （ANATOMY.md 是 merge 分类，frontmatter 未追平）。→ #75 缺口 1。
     > 【收口纠正】B 原文写「frontmatter 用旧字段 `related_files:` 未改成 `children:`」不准确：主 agent
     > 核对上下游 diff，上游 v1.3.8 **`related_files:` 与 `children:` 并存**（children 是新增块，非改名）。
     > 真实机制是 **merge 分类不传播 frontmatter 的 schema 新增**。B 的「真实追平缺口」定性正确，机制描述已更正。
  3. `check-provenance-chain`：`lab/data/dataset-index.yaml` 缺 → **下游合理条件**（classification=project，
     ELF 模拟下游从未建数据集索引），非追平责任。

**结论**：默认口径 G1 全绿；strict 下 2 项真实缺口（→ #75）+ 1 项下游合理缺失。

## T-G5-6：G3 抽测（4 skill/command，超 ≥3 门槛）—— 4/4 PASS

spawn / worktree-pr-flow / checkpoint / pr-review：frontmatter 可解析、引用的脚本与 subagent 全部
存在且可跑。下游可用。

## T-G5-7：幂等（零副作用）—— PASS

- `sync-codex-adapters.py` ×2：均 `changed 0/38`，`git status --short` 全空。
- `template-sync.py --dry-run` ×2：计划一致（framework 0/新建 0/merge 0/protect 257/scaffold 3）、
  两次输出逐字节相同、receipt 一致（from=target=committed=v1.3.8, version_advanced=false）、零 git 副作用。

## T-G5-4（B 侧）：分类不覆盖下游 —— PASS

round2 sync commit（`05fc58c`）对 project 层仅 18 文件改动（178+/2-），2 处删除是 `memory/ANATOMY.md`
文档同步的良性更新，非覆盖。另 145 个 project 文件是 round1 建立模拟下游时就有、与本次 round2 无关。
下游内容未被框架层覆盖。
