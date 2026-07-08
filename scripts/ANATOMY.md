---
related_files:
  - ../ANATOMY.md
  - check-agent-harness.py
  - check-anatomy-drift.py
  - validate-governance.py
maintenance: |
  新增/删除检查脚本时同 commit 更新本表。检查项与 .agent/ doctrine 对应关系变化时也更新。
---

# scripts/ ANATOMY

## What this is

repo 的可运行门禁层。三个独立脚本，无第三方硬依赖，只读、只报告、返回退出码。

## Components

| 文件 | 角色 | 对应 doctrine |
| --- | --- | --- |
| `check-agent-harness.py` | 结构/必需文件/根污染/四件套/能力索引/settings 校验 | `.agent/repo-editing-guardrails.md` · `repo-documentation-topology.md` |
| `check-anatomy-drift.py` | ANATOMY related_files 与 line citation 漂移 | `.agent/anatomy-protocol.md` |
| `validate-governance.py` | 聚合上两者 + gitignore/YAML/tracked-bytes 治理规则 | `.agent/action-boundary.md` · `artifact-policy.md` |

## Connections

Inbound:
- `.github/workflows/` CI 调用 `validate-governance.py --strict`。
- `.claude/settings.json` 把三个脚本列入 allow。

Outbound:
- `validate-governance.py` 以 subprocess 调用另两个脚本（用 `sys.executable`）。

## Notes

- validator 只能挡结构性漂移（missing file / out-of-range line / 根污染 / 误 track bytes）；语义正确性仍需 human/agent 打开代码验证。
- 退出码：0 通过，1 失败；`--strict` 让 warning 也算失败（用于 CI）。
