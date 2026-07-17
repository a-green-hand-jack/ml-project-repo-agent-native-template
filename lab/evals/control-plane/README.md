# control-plane evals

`run-g4-scenario.py` 是 issue #57（父 issue #52，P7 阶段，D 层「双 agent 场景」）落地的
G4 场景驱动：对多 agent 控制面（`.agent/multi-agent-control-plane.md`，issue #14）跑一个完整
的双 agent 故事，逐条覆盖 7 个 T-ID（T-G4-1 ~ T-G4-7）的正例（按契约工作）+ 负例（越界被拒/
正确降级）。

不是新 runner 框架——是一份薄的场景驱动脚本，复用四个控制面脚本
（`scripts/agent-state.py` / `scripts/agent-mailbox.py` / `scripts/agent-status.py` /
`scripts/check-agent-conflicts.py`）已有的 CLI 契约，加 `.claude/hooks/agent_name_set.py` 的
roster 逻辑。参照 issue #54/#59 的 A 层 qualification runner（`lab/evals/qualification/`）的
证据形态（`report-<group>.{json,md}` 双形态、含被测 commit sha），但两者定位不同：
qualification runner 测的是**静态门禁 validator**（G1/G6），本 runner 测的是**运行时多 agent
协作机制**（状态/mailbox/handoff/冲突检测/聚合视图/身份）。

## 隔离纪律（务必遵守）

- 每个 T-ID 各自 `tempfile.mkdtemp` 出一份隔离控制面根，用后即 `shutil.rmtree`。调用四个核心
  脚本的 CLI 时**双保险**：既设 `AGENT_CONTROL_PLANE_ROOT` env，又显式传 `--root`——两者语义
  一致（`agent-state.py:control_plane_root` 里 env 优先于 `--root` 缺省逻辑，但四个脚本的
  `--root` 参数本身就是显式覆盖，双设不冲突，只是防止某条调用路径漏传其中一种）。
- **绝不**在真实 `memory/agents/`、`memory/mailbox/`、`memory/agents-roster.md`、
  `.agent-identity` 上做写测试——那些是运行时真相层，被本 repo 大量真实 agent 状态占用，测试
  写脏会破坏其他 agent 的发现/冲突检测。
- T-G4-7 涉及 `.claude/hooks/agent_name_set.py`：该脚本的 roster 路径（`ROSTER` 全局变量）
  硬编码指向真实 worktree 根，没有 env override；本 driver 用它自己 `--self-test` 同款隔离
  手法——`importlib` 载入一份**新鲜模块实例**，猴补该实例的 `mod.ROSTER` 指向隔离临时文件，
  再调用其 `_register_child()`（"--register 子 agent" 模式的库函数，本就不写
  `.agent-identity`）。全程不调用会写真实 `.agent-identity` 的自命名主路径；唯一真实调用的
  CLI 子进程（空名字负例）在写任何文件前就提前返回，且脚本额外用 sha256 校验真实
  `.agent-identity`/`agents-roster.md` 前后字节不变，双重确认未被误触碰。
- 本 repo 有 doc-lifecycle hook：变量路径的 `rm`/`mv`/`cp`/`ln` 会被 Bash 静态扫描拦截（哪怕
  `/tmp`）。所以隔离根的 setup/teardown 全部走 Python（`tempfile.mkdtemp` + `shutil.rmtree`，
  在本脚本进程内部执行，不经过会被扫描的 Bash `rm`/`mv` 命令）。
- 全程不碰 `lab/data/`、`lab/runs/`、`lab/models/`、`lab/infra/private/` 等受保护路径，不启停
  任何训练/远端作业。

## 用法

```bash
uv run --with pyyaml python3 lab/evals/control-plane/run-g4-scenario.py
```

（本机裸 `python3` 缺 PyYAML 时，四个脚本的受限解析器兜底可用，但 `uv run --with pyyaml` 更
接近真实生产环境；与 `lab/evals/qualification/` 用法一致，同一环境缺口，见
`scripts/CLAUDE.md`。）

输出落 `lab/docs/audits/qualification/report-g4.{json,md}`（复用 issue #54/#59 同一输出目录、
同构证据形态：机器可读 JSON + Markdown 摘要，含被测 commit sha、self-test backstop 明细）。

## 复现性

先跑四个核心脚本 + `agent_name_set.py` 各自的 `--self-test` 作确定性 backstop（这部分是
byte-for-byte 确定性的：脚本内置合成 fixture，不涉及真实时间戳）。

场景层（7 个 T-ID）连续两次运行，**结构性可重复**（每个 T-ID 的 `status`/各断言布尔值逐字节
一致，`meta.commit`/`meta.self_test.all_pass` 一致），但证据文本（`evidence` 字段）里嵌的
`tempfile.mkdtemp` 临时路径、真实心跳时间戳（`_now_iso()` 用真实 wall clock）、mailbox 消息 id
（`sha1(时间戳|...)`）每次运行天然不同——这是被测机制本身的设计（隔离根路径随机、心跳用真实
时间、消息 id 含时间戳去重），不是不确定性缺陷。不像 `lab/evals/qualification/` 的 git-clone
fixture（内容静态、可做严格 byte-for-byte 对比），本 runner 的隔离根 fixture 内容本就含运行时
可变量，因此可重复性合同是"结构性"（statuses/booleans 一致）而非"字节级全文一致"。

## UNAVAILABLE 语义

若某 T-ID 依赖的外部二进制/环境在本机不可用，且该依赖恰好是待证负例的必要前提，对应子断言
标记 `UNAVAILABLE`（而非伪造 PASS 或静默跳过）。当前唯一涉及外部二进制的是 T-G4-6（Paseo
交叉校验）：脚本先探测 `paseo` CLI 是否可用——

- 若可用（本机默认情况）：分别验证"agent 未登记 paseo_id → presence 优雅降级为 `-`"与"PATH
  剥掉 paseo 二进制模拟缺 Paseo → 全体 presence 降级为 `unknown(no-paseo)`"两条真实降级路径。
- 若本机确实没有 `paseo` 二进制：默认运行（不剥 PATH）天然就落进"缺 Paseo"分支，仍是有效负例
  （不需要人为剥 PATH），不标 UNAVAILABLE。

发现的控制面缺陷只报告，不在本目录顺手修——见 `memory/branches/57-g4-control-plane.md`。
