# SDK Agent 作为 mini_symphony 执行器

> 来源组合: [claude-agent-sdk-demos AgentDefinition] × [mini_symphony.py TASKS.md 队列]
> 日期: 2026-03-22
> **状态**: ❌ 已被取代（2026-03-28 验证）

> **验证结论**：Claude Code 已内置 Agent Teams（最多 10 sub-agents 并行）、Task Tool（subagent spawning）、Model Routing（per-task 模型选择）。mini_symphony 的核心价值（per-task tool whitelist, model routing, 任务队列编排）已被平台原生功能覆盖。竞品：Claude Code Agent Teams, LangGraph+Claude SDK 集成。

---

## 核心想法

在 mini_symphony 的 worker 层增加一个 `executor: sdk-agent` 类型。当前 mini_symphony 通过 `subprocess.Popen` spawn 通用的 claude/pi CLI 进程来执行任务，但这些进程拥有全部工具集，缺乏细粒度控制。

新方案：用 Claude Agent SDK 的 `AgentDefinition` 定义专用 agent，在 TASKS.md 中指定每个任务的工具白名单和自定义 prompt。

## 价值

1. **安全性提升**：每个任务只获得所需工具（搜索任务没有 Bash，写作任务没有 WebSearch）
2. **可编程性**：通过 hooks 拦截 tool 调用，实现审计、限流、成本控制
3. **混合编排**：同一个 TASKS.md 中可以混用 CLI spawn 和 SDK agent——简单任务用 CLI，敏感任务用 SDK

## TASKS.md 扩展语法

```markdown
- [ ] 搜索竞品定价信息
  executor: sdk-agent
  agent_type: researcher
  tools: [WebSearch, Write]
  model: haiku

- [ ] 基于搜索结果生成分析报告
  executor: sdk-agent
  agent_type: analyst
  tools: [Read, Glob, Write]
  model: sonnet
  depends_on: [搜索竞品定价信息]

- [ ] 重构 utils 模块
  executor: claude  # 传统 CLI spawn，完整能力
```

## 实现要点

1. mini_symphony 的 `Worker` 类增加 `SDKAgentWorker` 子类
2. 解析 TASKS.md 中的 `executor`/`tools`/`model` 字段
3. 用 `ClaudeSDKClient` + `AgentDefinition` 替代 `subprocess.Popen`
4. hooks 层统一对接 session_tracker 的 SQLite 事件记录

## 最小 Spike

1. 在 mini_symphony.py 中增加 `executor: sdk-agent` 的解析逻辑
2. 实现 `SDKAgentWorker`，用 `ClaudeSDKClient` 执行单个任务
3. 在一个测试项目上对比 CLI spawn vs SDK agent 的执行效果和安全性

## 风险

- Python SDK 稳定性：`claude-agent-sdk` Python 包版本 0.1.x，API 可能变
- 依赖增加：从"仅需 pyyaml"到"需要 claude-agent-sdk"
- 进程模型：SDK 底层还是 spawn CLI 进程，不确定嵌套 spawn 的资源开销

## Why

当前 mini_symphony 对所有任务给予相同的能力级别——这在任务复杂度和安全需求差异大的场景中是不够的。Research Agent demo 证明了通过 AgentDefinition 可以精细控制每个子 agent 的能力范围。

## How to Apply

当 mini_symphony 用于需要安全隔离的多任务场景（如同时执行搜索、代码修改、报告生成）时，优先考虑 SDK agent 执行器而非通用 CLI spawn。
