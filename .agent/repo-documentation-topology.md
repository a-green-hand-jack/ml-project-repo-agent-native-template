# 文档拓扑（导航四件套）

不是每个 leaf 目录都要写文档，但重要目录应有一个轻量 navigation quartet。

## 四件套分工

```
README.md    给 human：这里是什么、什么时候来、常见入口。不要写成长 spec。
AGENTS.md    给 agent：允许改什么、禁止改什么、必须验证什么、禁止路径。
CLAUDE.md    给 Claude Code：薄路由，优先读哪些本目录文件与 repo-local assets。
ANATOMY.md   给 coding agent：组件、调用关系、持久状态、line-addressed citations。
```

## 优先拥有四件套的目录

```
<repo>/   human/   .claude/   lab/   lab/code/   lab/code/src/
lab/infra/   lab/research/   lab/artifacts/   memory/   deliverables/   scripts/
```

（`.agent/` 用 `AGENTS.md` 作 doctrine 索引，是扁平 doctrine 面，不需要 ANATOMY。）

## 规则

- `CLAUDE.md` 应薄，只做本目录入口与读文件顺序；超 80-120 行通常错了。
- `ANATOMY.md` 只给有真实协作关系/状态/调用图/ownership 边界的目录；写成教程就该拆到 README 或 `.agent/`。
- 只有静态资源或简单 leaf helper 的目录，不要为整齐制造空文档。
- 由 `repo-doc-steward` 维护，避免 repo 只对 agent 可读或只对 human 友好。

## 防止两种失衡

- 只对 agent 可读、对 human 不可读 → 补 README。
- 只对 human 友好、agent 找不到边界 → 补 AGENTS / ANATOMY。
