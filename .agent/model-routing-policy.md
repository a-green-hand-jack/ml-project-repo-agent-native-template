# 模型与 Effort 路由

main agent 可用最好模型 + 最高 effort（它负责目标/权衡/整合/验收）。需要自动化的是 **child agent 的预算选择**：高模型/高 effort 是子任务预算，不是 agent 身份。

## Tier 分层

```
tier 0  no subagent；直接 shell / grep / rg
tier 1  fast model / low effort / read-only：查找、文件定位、bounded log 摘要
tier 2  standard model / medium effort：bounded 实现、定向测试、小 doc 更新
tier 3  strong model / high effort：深度 debug、架构、shared contract、anatomy/validator 改动
tier 4  strong model / high effort / fresh context：final verifier、paper claim review、release gate、贵实验决策
```

## 自动路由流程

```
human 说「开 subagent 做 X」
→ main 读本文件；明显就直接选 tier
→ 不明显就用 subagent-router-agent 生成 launch packet
→ main 用选定 model/effort/tools 派发 child
→ 结果后 main 记录预算过低/过高/合适
→ 模式稳定后经 issue/branch/PR 更新本 policy
```

## 预算落到实处：为什么 frontmatter 是 `model: inherit`

「预算不是身份」要能在**执行层**成立，不能只写在文档里：

- `.claude/agents/*.md` 的 frontmatter 一律 `model: inherit` 是**刻意的**——不给角色钉死模型档位，避免「repo-researcher 天生最贵」这类身份化。
- 真正的档位在**派发时**决定：main 按 launch packet 的 `recommended model` / `recommended effort`，在启动 child 时逐次覆盖（Agent 调用的 per-call model/effort 参数）。tier→model 映射随 CC 版本与预算变化，由 main 在派发点决定具体 model id，不硬编码进 repo。
- 因此 `inherit` 是「无固定身份、等派发时定预算」的默认，不是「永远继承 main 的最高档」。若某次派发不带覆盖，child 才回退到继承——这只应发生在 tier 与 main 同档的任务上。

`fast / standard / strong` 是**抽象档**，不是 model id：低成本查找 / 常规实现 / 高风险决策。落到当前可用模型由派发方决定，稳定后可在本 policy 记映射并定期复校（同 recipe 防漂移）。

## 已知例外（`model: inherit` 不适用的情况）

- `.claude/agents/zh-review-gate.md` 的 frontmatter 显式锁定 `model: haiku`，不遵循上面"model: inherit，不写死"的默认原则。这是刻意的、经 human 明确要求的窄例外，不是遗漏。
- 理由：`zh-review-gate` 是"文档默认中文"doctrine（见 `human/decisions/20260709-doc-language-default-chinese.md`）的翻译安全网，其存在价值恰恰在于成本要独立于主 session 当次用的模型——哪怕主 session 用最贵的模型，这个兜底检查也应该几乎零成本；若它 inherit 主 session 的模型，就失去了作为「低成本安全网」的意义。
- 这是目前**唯一**的已知例外。以后若出现类似「职责决定必须用便宜模型、不能 inherit」的新 subagent，应在本节补充记录，而不是只散落在各 agent 自己的文件里、让本 policy 本身看不出该原则已有先例。

## 选 tier 的问题

- 是不是 read-only？
- 会不会改 shared contract / ANATOMY / validator / paper claim？
- 错了会不会浪费 GPU / 污染数据 / 误导论文？
- 需要的是文件定位、普通实现、复杂 debug，还是 final verifier？
- 输出是否需要 claim-grade evidence？

## Launch packet

模板见 `.agent/templates/launch-packet.md`。

## 校准规则

- 子 agent 返工多 → 提高该类 tier 或收紧 task packet。
- 输出过长污染主线程 → 改成 report file + summary。
- 经常只是读文件 → 降级 tier 0/1。
- 触碰 shared contract → 升级 tier 3 并要 fresh verifier。

不要把 `ls` / `grep` / tail / 改 typo / 重复 boilerplate 交给最高 effort。
