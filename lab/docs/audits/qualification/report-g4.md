# G4 control-plane scenario report

- 被测 commit：`b588d59a2c276f7e5d0bd25786ac9f2f943fbfeb`
- 生成时间：2026-07-17T06:34:53.172779+00:00
- 生成时工作树是否 dirty：True
- 结果：7/7 PASS（self-test backstop：76 项全部通过，覆盖 5 个脚本）

| T-ID | promise | status |
| --- | --- | --- |
| T-G4-1 | register/heartbeat/TTL→stale 派生 | PASS |
| T-G4-2 | mailbox send/read + decision/handoff 强制 ref 落盘 | PASS |
| T-G4-3 | handoff ack 前 ownership 不转移 + 精确路径匹配拒绝 | PASS |
| T-G4-4 | check-agent-conflicts scan（重叠→报警，无重叠→clean） | PASS |
| T-G4-5 | worktree 声明 vs 实际 toplevel 检测 | PASS |
| T-G4-6 | agent-status 聚合视图（±Paseo 降级） | PASS |
| T-G4-7 | roster/identity（agent_name_set 幂等/改名） | PASS |

## self-test backstop

| script | ok assertions | exit |
| --- | --- | --- |
| `scripts/agent-state.py` | 17 | 0 |
| `scripts/agent-mailbox.py` | 27 | 0 |
| `scripts/agent-status.py` | 10 | 0 |
| `scripts/check-agent-conflicts.py` | 16 | 0 |
| `.claude/hooks/agent_name_set.py` | 6 | 0 |

## 逐项证据

### T-G4-1 — PASS

- promise: register/heartbeat/TTL→stale 派生
- notes: 正例：A/B register 后心跳内 → active。负例：直接复用 agent-state.py 的 register(now=...) 库函数把 A 心跳时间戳设成 31 分钟前（TTL=30），agent-status.py 派生显示 stale，同时校验磁盘上 status 存储字段本身未被改写（派生不落盘）。
- positive: ok=True
```
    "name": "干将·改·g4demo-A",
    "status": "active",
    "stored_status": "active",
    "heartbeat_age_minutes": 0.0,
    "heartbeat": "2026-07-17T06:34:47Z",
    "task": "G4 demo A",
    "worktree": "/home/user/.paseo/worktrees/1kaz3672/g4-control-plane",
    "branch": "g4-dual-agent-verification",
    "paseo_id": "-",
    "paseo_presence": "unknown(no-paseo)",
    "unread_inbox": 0,
    "owned_paths": [],
    "state_file": "/tmp/g4-1-a1an07fw/memory/agents/干将·改·g4demo-A.yaml"
  }
]
```
- negative: ok=True
```
    "name": "干将·改·g4demo-A",
    "status": "stale",
    "stored_status": "active",
    "heartbeat_age_minutes": 31.0,
    "heartbeat": "2026-07-17T06:03:48Z",
    "task": "G4 demo A",
    "worktree": "/home/user/.paseo/worktrees/1kaz3672/g4-control-plane",
    "branch": "g4-dual-agent-verification",
    "paseo_id": "-",
    "paseo_presence": "unknown(no-paseo)",
    "unread_inbox": 0,
    "owned_paths": [],
    "state_file": "/tmp/g4-1-a1an07fw/memory/agents/干将·改·g4demo-A.yaml"
  }
]
```

### T-G4-2 — PASS

- promise: mailbox send/read + decision/handoff 强制 ref 落盘
- notes: 正例：A→B info send，B inbox 读到未读消息、mark-read 后未读清零。负例三路：decision 不带 --ref 拒绝；ref 经 `..` 逃逸控制面根拒绝；ref 绝对路径拒绝（即使目标文件真实存在于控制面根内——只认控制面 repo 内相对路径）。
- positive: ok=True
```
[mailbox] 已标记 1 条为已读
```
- negative: ok=True
```
no_ref: [mailbox] 失败：kind=decision 是关键消息，必须 --ref 指向 repo 落盘记录（验收 #5）
escape: [mailbox] 失败：--ref 逃逸控制面根（/tmp/g4-2-za27yiek）：../outside.md
abs: [mailbox] 失败：--ref 拒绝绝对路径：/tmp/g4-2-za27yiek/memory/handoffs/demo.md（用控制面 repo 内的相对路径）
```

### T-G4-3 — PASS

- promise: handoff ack 前 ownership 不转移 + 精确路径匹配拒绝
- notes: 正例：A 先 register 明细 owned_path（文件级，非目录）→ handoff → ack 前查 A/B 状态确认未转移 → B ack → 转移进 B + A 收到 ack 回执。负例：C 只拥有父目录 shared/、想转移其子文件shared/detail.txt → ack 拒绝（不做目录所有权分裂）、消息保持 pending、C 的 owned_paths 不变。
- positive: ok=True
```
[mailbox] handoff a6962a47 accepted；转移 paths：['shared/detail.txt']；回执 fa477026
[mailbox] handoff 已发起：a6962a47（pending，等待 师爷·审·g4demo-B ack）
```
- negative: ok=True
```
[mailbox] 失败：handoff d4a337df 被拒：待转移路径无法从发起方「干将·改·g4demo-C」完整移出——shared/detail.txt（发起方拥有的是目录 shared/：不做目录所有权分裂，先让发起方 register 拆细 owned_paths 再 handoff）
```

### T-G4-4 — PASS

- promise: check-agent-conflicts scan（重叠→报警，无重叠→clean）
- notes: 正例：A owned src/core/、B owned src/core/db.py（目录 vs 子文件）→ scan 检出 1 处重叠、exit=1。负例：A/B 各自 owned 互不相交路径 → scan 干净、exit=0。
- positive: ok=True
```
[
  {
    "agent_a": "师爷·审·g4demo-B",
    "path_a": "src/core/db.py",
    "agent_b": "干将·改·g4demo-A",
    "path_b": "src/core/"
  }
]
```
- negative: ok=True
```
[]
```

### T-G4-5 — PASS

- promise: worktree 声明 vs 实际 toplevel 检测
- notes: 正例：declared worktree == 实际 toplevel → clean。负例：把 A 的 declared worktree 改成另一目录（elsewhere），传入不同的 --actual-toplevel → 报错并点名两个具体路径。
- positive: ok=True
```
[conflicts] worktree 一致：干将·改·g4demo-A @ /tmp/g4-5-vmnwwf2j/actual-toplevel
```
- negative: ok=True
```
[conflicts] agent「干将·改·g4demo-A」登记的 worktree 是 /tmp/g4-5-vmnwwf2j/elsewhere，但当前写入发生在 /tmp/g4-5-vmnwwf2j/actual-toplevel。疑似写错 worktree——先 pwd + git rev-parse --show-toplevel 核对，或更新状态文件（python scripts/agent-state.py register）。确属误报/human 授权可 AGENT_CONFLICT_SKIP=1 显式放行（先与对方 agent/监控员协调）。
```

### T-G4-6 — PASS

- promise: agent-status 聚合视图（±Paseo 降级）
- notes: 正例：--no-paseo 纯 repo 视图列出 A/B 的 status/heartbeat/unread。负例两分支：(a) 本机真实 paseo CLI 可用但 agent 未登记 paseo_id → presence='-'，不 raise；(b) PATH 剥掉 paseo 二进制模拟缺 Paseo → 全体 presence 降级为 unknown(no-paseo)，exit 仍为 0。
- positive: ok=True
```
    "name": "干将·改·g4demo-A",
    "status": "active",
    "stored_status": "active",
    "heartbeat_age_minutes": 0.0,
    "heartbeat": "2026-07-17T06:34:50Z",
    "task": "demo A",
    "worktree": "/home/user/.paseo/worktrees/1kaz3672/g4-control-plane",
    "branch": "g4-dual-agent-verification",
    "paseo_id": "-",
    "paseo_presence": "unknown(no-paseo)",
    "unread_inbox": 0,
    "owned_paths": [],
    "state_file": "/tmp/g4-6-q6j69142/memory/agents/干将·改·g4demo-A.yaml"
  }
]
```
- negative: ok=True
```
no_pid presence=-
no_cli presences=['unknown(no-paseo)', 'unknown(no-paseo)']
```

### T-G4-7 — PASS

- promise: roster/identity（agent_name_set 幂等/改名）
- notes: 正例：`_register_child`（--register 子 agent 模式的库函数，猴补 ROSTER 到隔离路径，与脚本自身 --self-test 同款手法）重复调用幂等；同 paseo-id 换名字模拟改名 → roster 行原位替换（非追加），状态 yaml 随新名字一致存在。负例：空名字调用真实 CLI（该路径本就在写任何文件前提前返回）→ exit 0 优雅提示，且验证真实 .agent-identity/roster 字节前后不变（未被误触碰）。已知边界（如实记录、非缺陷）：控制面没有统一 rename 原语，改名后旧名字对应的状态 yaml 不会被自动清理/合并，只是不再被 roster 引用。
- positive: ok=True
```
| 干将·改·g4demo-C改名 | 干将·改 | g4demo-C改名 | demo-branch (wt) | pid-g4-7 | active | 2026-07-17 09:34 | memory/agents/干将·改·g4demo-C改名.yaml |
```
- negative: ok=True
```
[agent-name] 用法：agent_name_set.py "<persona·动作·focus>"（名字为空，未改动）
```
