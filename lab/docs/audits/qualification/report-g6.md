# Qualification report — group=g6

- 被测 commit：`35c9bd58820379bebebd1c93b0c747868fc882ae`
- 生成时间：2026-07-16T17:10:14.582257+00:00
- 生成时工作树是否 dirty：True
- 结果：4/4 PASS（复用 self-test 0 项，自建 fixture 4 项）

| T-ID | validator | mode | status | notes |
| --- | --- | --- | --- | --- |
| T-G6-1 | `scripts/sync-codex-adapters.py` | custom-fixture | PASS | 幂等性是单一性质（连续两次 write 第二次 changed=0 且产物树摘要不变），无对立负例概念——本 T-ID 只有 positive 断言，不强行造一个不存在的"负例"。先人为删掉一个 adapter 制造初始未同步（第一次 write 必须 changed>=1），再验证第二次 write 收敛为真正 no-op。 |
| T-G6-2 | `scripts/sync-codex-adapters.py` | custom-fixture | PASS | 负例手改一个已生成的 .codex/agents/*.toml，验证 --check 能定位到具体 stale 文件路径。 |
| T-G6-3 | `scripts/sync-codex-adapters.py` | custom-fixture | PASS | 逐项 byte-for-byte 比对 expected_files()（复用 sync-codex-adapters.py 自身生成规则，不重新实现）与磁盘实际内容；正例上实测 expected 文件数为 38（issue #54 表格建议数字 38 仅供参考，以本次实测计数为准，如实登记，不强行凑数）。 |
| T-G6-4 | `scripts/check-agent-harness.py` | custom-fixture | PASS | Codex 侧可发现性的权威检查已在 check-agent-harness.py 的 check_codex_config()（复用，不重复造 fixture）；负例改 .codex/config.toml 一处 hook 引用指向不存在文件。 |

## 逐项证据

### T-G6-1 — PASS

- validator: `scripts/sync-codex-adapters.py`（mode=custom-fixture, reused_self_test=False）
- notes: 幂等性是单一性质（连续两次 write 第二次 changed=0 且产物树摘要不变），无对立负例概念——本 T-ID 只有 positive 断言，不强行造一个不存在的"负例"。先人为删掉一个 adapter 制造初始未同步（第一次 write 必须 changed>=1），再验证第二次 write 收敛为真正 no-op。
- positive: exit=0 ok=True
```
[sync-codex-adapters] changed 0/38 adapter file(s)
```
- negative: n/a（见 notes 说明）

### T-G6-2 — PASS

- validator: `scripts/sync-codex-adapters.py`（mode=custom-fixture, reused_self_test=False）
- notes: 负例手改一个已生成的 .codex/agents/*.toml，验证 --check 能定位到具体 stale 文件路径。
- positive: exit=0 ok=True
```
[sync-codex-adapters] context=source OK — 0 issue(s)
```
- negative: exit=1 ok=True injection='手改 .codex/agents/artifact-librarian.toml 追加一行非生成内容'
```
ERROR stale generated adapter: .codex/agents/artifact-librarian.toml
[sync-codex-adapters] context=source FAIL — 1 issue(s)
```

### T-G6-3 — PASS

- validator: `scripts/sync-codex-adapters.py`（mode=custom-fixture, reused_self_test=False）
- notes: 逐项 byte-for-byte 比对 expected_files()（复用 sync-codex-adapters.py 自身生成规则，不重新实现）与磁盘实际内容；正例上实测 expected 文件数为 38（issue #54 表格建议数字 38 仅供参考，以本次实测计数为准，如实登记，不强行凑数）。
- positive: exit=0 ok=True
```
38 expected adapter path(s) 比对：missing=[] mismatches=[]
```
- negative: exit=0 ok=True injection='追加字节到 .agents/skills/adopt-existing-repo/SKILL.md'
```
注入单点 content drift 后 mismatches=['.agents/skills/adopt-existing-repo/SKILL.md']（期望仅命中 .agents/skills/adopt-existing-repo/SKILL.md）
```

### T-G6-4 — PASS

- validator: `scripts/check-agent-harness.py`（mode=custom-fixture, reused_self_test=False）
- notes: Codex 侧可发现性的权威检查已在 check-agent-harness.py 的 check_codex_config()（复用，不重复造 fixture）；负例改 .codex/config.toml 一处 hook 引用指向不存在文件。
- positive: exit=0 ok=True
```
[check-agent-harness] OK — 0 error(s), 0 warning(s)
```
- negative: exit=1 ok=True injection='.codex/config.toml 里一处 hook command 指向不存在的脚本文件名'
```
ERROR Codex hook 脚本不存在：.claude/hooks/context_threshold_notice_MISSING.py（UserPromptSubmit）
[check-agent-harness] FAIL — 1 error(s), 0 warning(s)
```
