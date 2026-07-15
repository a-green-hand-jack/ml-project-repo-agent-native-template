---
related_files:
  - ANATOMY.md
  - .agent/anatomy-protocol.md
  - scripts/CONTRACT.md
governed_components:
  - component: template-sync
    owner: scripts/CONTRACT.md
maintenance: |
  新增/移除受治理组件时，同 commit 更新本索引与对应组件的 contracts/contract_for 声明。
  只登记已通过 human 批准、有真实 owner 文件的边界；不为尚无 CONTRACT.md 的组件占位。
---

# repo CONTRACT（root，受治理组件索引）

## 这是什么

列出当前**显式纳管**的行为承诺边界（LingTai guide A 机制 4「显式受治理集合」，见 issue #48
v4 S3）。只有出现在下表的 component 才承担完整 CONTRACT 约束；未出现的目录/组件维持现状
（承诺正文留在 `.agent/` policy 文件，或尚无独立承诺），不受本索引影响。

## 受治理组件

| component | 归属 ANATOMY | Contract owner | contract_version | 状态 |
| --- | --- | --- | --- | --- |
| `template-sync` | `scripts/ANATOMY.md` | `scripts/CONTRACT.md` | 1 | active |

## 如何新增一条

1. 边界必须真实、独立、已出现过争议或反复问题——不批量、不预建（见
   `.agent/anatomy-protocol.md`「不批量」红线）。
2. 新建组件目录下的 `CONTRACT.md`（模板见
   `.reference-docs/LingTai_ANATOMY_CONTRACT_Project_Governance_Guide_zh.md` §6.2，按本 repo
   载体裁剪）。
3. 在对应 `ANATOMY.md` 声明 `contracts:`，在新 `CONTRACT.md` 声明 `contract_for:`
   （字段语义见 `.agent/anatomy-protocol.md`，本文件不复制判定逻辑）。
4. 在本文件「受治理组件」表加一行 `governed_components` 索引条目。
5. 走 `worktree-pr-flow` 的变更自检清单（分类：这属于「改承诺」，需要证据指针）。

`governed_components` 的 owner 路径必须与该 component 真实的 `contracts`/`contract_for` 双向
声明一致；`scripts/check-anatomy-drift.py` 的 `validate_governed_index()` 校验三类不一致
（登记缺失/索引 orphan/owner 路径不一致），字段语义见 `.agent/anatomy-protocol.md`。
