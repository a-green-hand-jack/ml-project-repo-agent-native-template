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
