# lab/docs/audits/ — 一致性审计 / 功能测试报告

长文审计记录:模板功能测试、一致性审计、就绪检查。落地位置由
`human/decisions/20260709-lab-docs-reference-and-external-vendor-placement.md`(ADR)确定。

- 是 `lab/ANATOMY.md` 归类下的 leaf 层:只有本 README,不需要独立 `ANATOMY.md`。
- 不是 validator 校验对象;对外 claim 仍须能追溯到 `lab/research/evidence.yaml`。
- 多 case 压力测试的登记账见 `stress-test-ledger.yaml`;流程见
  `.claude/skills/template-stress-test/SKILL.md`。

## 当前内容

- `agent-native-template-functional-test-report.md`——ELF-template-case(round 1-3)
  完整功能测试报告,原产于 `worktree-case+elf-template-replay` 分支,原样 promote
  进 main(零编辑)。round 4 的三项后续修复(F2 复验/F4/`sub-agent-maker-agent`
  重试)记在 `stress-test-ledger.yaml` 的对应条目里,不回填进本报告正文。
- `stress-probe-catalog.md`——ELF case round 3 的对抗性探针历史记录(具体
  mutate/expected/actual)。与 `.claude/skills/template-stress-test/references/
  probe-surface-catalog.md`(面向未来、随模板演化持续维护)是两份不同定位的文件。
- `stress-test-ledger.yaml`——多 case 登记账,首条记录即 ELF case。
- `agent-r1-adoption-replay-report.md`——`adopt-existing-repo` 的真实 replay:
  将 AgentR1/Agent-R1 迁移成模板形态,验证 hash integrity、template governance
  与 root pollution 收敛。
- `colorama-adoption-replay-report.md`——issue #12 任务树 C(统一 runtime/smoke 验证合同)的真实
  replay:将 tartley/colorama 迁移成模板形态,新增验证 smoke 合同(`command_source`/`result`/
  `unverified_reason`/显式 warning)在 exit code 与 tracked-byte integrity 解耦后仍然可读、
  不被静默吞掉;与 Agent-R1 replay 是不同 repo 案例,覆盖不同的原生测试命令检测类型
  (`Makefile` `test:` target,而非 undetected)。
- `qualification/`——issue #54/#59 的 A 层 qualification runner
  (`lab/evals/qualification/run-qualification.py`)产出的 G1(9 项静态门禁)+ G6(4 项
  Codex adapter parity)证据双形态(`report-{g1,g6,all}.{json,md}`),含被测 commit sha;
  同目录下 `report-g4.{json,md}` 是 issue #57 的 D 层 G4 双 agent 场景驱动
  (`lab/evals/control-plane/run-g4-scenario.py`)产出的 7 项 T-ID 证据,格式同构但覆盖对象
  不同(运行时多 agent 协作机制,非静态门禁)。同目录下 `report-g3.md` 是 issue #56 的 D 层
  workflow skills/commands 端到端演练:对 8 个 `.claude/skills/`/`.claude/commands/`
  逐一走一个真实小任务/干跑留证据,判 PASS/FAIL/UNAVAILABLE;无独立驱动脚本(人工/agent
  按各 SKILL.md 逐条执行,隔离干跑项用 `/tmp` fixture,不进 repo)。
