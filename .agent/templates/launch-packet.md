# Subagent Launch Packet 模板

派发 child agent 前由 main / `subagent-router-agent` 生成。见 `.agent/model-routing-policy.md`。

```
agent_type:          <repo-researcher | feature-worker | test-runner | ...>
task:                <一句话可收敛任务>
budget tier:         <0-4>
recommended model:   <fast | standard | strong>
recommended effort:  <low | medium | high>
allowed paths:       <可读/可写路径>
forbidden paths:     <绝对不碰>
tools:               <允许工具>
context budget:      <如 read-only / <200 lines log>
evidence required:   <返回什么算完成>
stop condition:      <何时停>
escalate condition:  <何时上报 main / 升 tier>
report path:         <.claude/agent-reports/<task>.md>
```
