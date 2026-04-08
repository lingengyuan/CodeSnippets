# HKUDS/nanobot 精读：极简 Agent 架构——用 1% 代码实现 99% 核心能力

**来源**: [HKUDS/nanobot](https://github.com/HKUDS/nanobot)
**日期**: 2026-04-03
**标签**: agent-architecture, minimalist-design, tool-loop, memory-system, multi-channel, python-agent, open-source
**统计**: ⭐ 37.7K stars · 6.5K forks · 2 个月（2026-02-01 创建）· MIT 协议

---

## 30秒 TL;DR

> nanobot 是香港大学 HKUDS 团队的超轻量 AI 助手，声称用 **99% 更少的代码** 实现 OpenClaw 的核心能力。核心 agent 代码约 1200 行 Python，却完整包含：工具注册表 + while(tool_calls) 循环 + 两层记忆（MEMORY.md + HISTORY.md）+ 渐进式 Skill 加载 + 子 Agent 生成 + Hook 生命周期 + 12 个聊天平台集成 + MessageBus 异步通信 + 上下文裁剪 + MCP 支持。与我们之前分析的 Claude Code（512K LOC）形成完美对照：**nanobot 证明了 Agent 的核心抽象只需要 7 个组件，其余 99% 是产品化开销**。

---

## 概念总览

| 概念/模式 | 核心思想 | 适用场景 |
|---------|---------|---------|
| **AgentRunner 提取** | 工具循环与产品逻辑解耦——runner 只管"调 LLM → 执行工具 → 喂回结果" | 需要在不同上下文复用 agent 循环（CLI/SDK/subagent） |
| **两层记忆** | MEMORY.md（长期事实）+ HISTORY.md（可 grep 日志），LLM 合并 + 原始归档降级 | 长会话 agent 的记忆持久化 |
| **渐进式 Skill 加载** | system prompt 只注入摘要 XML，agent 需要时用 read_file 加载完整内容 | Skill 多但 context 有限 |
| **MessageBus pub/sub** | InboundMessage → 处理 → OutboundMessage，频道解耦 | 多频道 agent（Telegram/Discord/WeChat/...） |
| **会话级锁 + 全局并发门** | per-session asyncio.Lock 串行 + Semaphore(3) 跨会话并发限制 | 多用户并发场景 |
| **Tool 并发批次** | read_only + exclusive 属性决定批次划分，安全工具并行执行 | 加速多工具调用 |
| **raw-archive 降级** | 记忆合并 LLM 连续失败 3 次后，直接 dump 原始消息到 HISTORY.md | 不丢数据比精确合并更重要 |

---

## 深读

### 1. 核心架构：7 个必要组件

```
nanobot/
├── agent/
│   ├── loop.py (34KB)      ← 核心：消息分发、Agent 循环、MCP 连接
│   ├── runner.py (23KB)    ← 可复用工具循环（与产品逻辑解耦）
│   ├── context.py (9KB)    ← system prompt 组装
│   ├── memory.py (14KB)    ← 两层记忆 + LLM 合并
│   ├── skills.py (8KB)     ← 渐进式 Skill 加载
│   ├── subagent.py (11KB)  ← 子 Agent 生成与管理
│   ├── hook.py (4KB)       ← 生命周期钩子
│   └── tools/              ← 工具注册表 + 具体工具
│       ├── base.py (8KB)   ← Tool 抽象基类
│       ├── registry.py (3KB) ← 注册/执行/验证
│       ├── filesystem.py   ← read/write/edit/list
│       ├── shell.py        ← exec（subprocess）
│       ├── web.py          ← web_search + web_fetch
│       ├── mcp.py          ← MCP 客户端集成
│       ├── spawn.py        ← 子 Agent 生成工具
│       ├── message.py      ← 跨频道消息发送
│       └── cron.py         ← 定时任务
├── bus/                    ← MessageBus（异步队列）
├── channels/               ← 12 个聊天平台适配器
├── providers/              ← LLM provider 适配器
├── config/                 ← 配置 schema + 加载器
├── session/                ← 会话管理
└── nanobot.py (6KB)        ← Python SDK facade
```

**关键数字**：核心 agent 代码（排除 channels/providers/cli/api）约 **1200 行**。

### 2. AgentRunner——与产品逻辑解耦的工具循环

`AgentRunner.run(spec: AgentRunSpec)` 是最核心的 50 行逻辑：

```
for iteration in range(max_iterations):
    messages = snip_history(messages)           ← 上下文裁剪
    response = await request_model(messages)    ← 调 LLM
    if response.has_tool_calls:
        results = await execute_tools(calls)    ← 执行工具
        messages.append(tool_results)
        continue                                ← 继续循环
    else:
        final_content = response.content        ← 结束
        break
```

**设计精妙之处**：AgentRunner 不知道 CLI、频道、SDK 的存在。它只接收 `AgentRunSpec`（消息+工具+模型+配置）并返回 `AgentRunResult`。所有产品逻辑通过 `AgentHook` 注入。

这实现了三处复用：
- `AgentLoop` 用它处理主循环消息
- `SubagentManager` 用它运行子 Agent
- `Nanobot` SDK 用它提供 programmatic API

### 3. 两层记忆系统

| 层 | 文件 | 用途 | 更新方式 |
|----|------|------|---------|
| **Long-term** | `memory/MEMORY.md` | 持久化事实和偏好 | LLM 合并（新旧记忆→统一更新） |
| **History** | `memory/HISTORY.md` | 可 grep 搜索的事件日志 | 每次合并追加一条 `[YYYY-MM-DD HH:MM]` 格式条目 |

**合并机制**：用 LLM 调用 `save_memory` 工具（forced tool_choice），传入当前 MEMORY.md + 对话历史，LLM 返回 `{history_entry, memory_update}`。

**降级策略（raw-archive）**：LLM 连续失败 3 次后，直接把原始消息 dump 到 HISTORY.md。**不丢数据比精确合并更重要**——这是一个非常实用的工程判断。

**Token 驱动的自动合并**：`MemoryConsolidator.maybe_consolidate_by_tokens()` 在 prompt token 超过 `(context_window - max_completion - safety_buffer) / 2` 时触发。最多 5 轮合并，每轮找到 user-turn 边界，合并老消息后重新估算。

### 4. 渐进式 Skill 加载

```
System Prompt 注入:
  <skills>
    <skill available="true">
      <name>web-search</name>
      <description>Search the web for information</description>
      <location>/path/to/SKILL.md</location>
    </skill>
    ...
  </skills>

Agent 需要时: read_file("/path/to/SKILL.md") → 获取完整 Skill 内容
```

两层来源：workspace skills（优先）→ builtin skills。`always=true` 的 skill 直接注入 system prompt。

**对比 Claude Code**：Claude Code 用 `estimateSkillFrontmatterTokens()` 做 token 预算控制。nanobot 更简单——只注入 XML 摘要，让 agent 自己决定何时加载。**两种策略的本质区别**：Claude Code 是"预分配预算"，nanobot 是"按需自取"。

### 5. 子 Agent 系统

SubagentManager 的设计非常精简：
- **生成**：`asyncio.create_task(self._run_subagent(...))`
- **隔离**：子 Agent 没有 message 和 spawn 工具（不能给用户发消息，不能递归生成子 Agent）
- **通信**：完成后通过 MessageBus 注入 InboundMessage（role=system, sender=subagent）
- **管理**：按 session_key 跟踪，支持 cancel_by_session

**对比 Claude Code**：Claude Code 的 Worker 用 setState=no-op 隔离。nanobot 更直接——子 Agent 的工具集里根本没有 message/spawn。**不是"禁止调用"，而是"工具不存在"**。这是更彻底的隔离。

### 6. Hook 系统

```python
class AgentHook:
    def wants_streaming(self) -> bool: ...
    async def before_iteration(self, ctx): ...
    async def on_stream(self, ctx, delta): ...
    async def on_stream_end(self, ctx, *, resuming): ...
    async def before_execute_tools(self, ctx): ...
    async def after_iteration(self, ctx): ...
    def finalize_content(self, ctx, content): ...
```

7 个钩子覆盖完整生命周期。CompositeHook 做错误隔离——async 钩子 catch 异常不影响其他钩子，但 `finalize_content` 不隔离（pipeline 模式，bug 应该暴露）。

### 7. litellm 供应链中毒事件

2026-03-21，nanobot 发现 `litellm` 依赖存在供应链攻击，紧急移除并替换为原生 `openai` + `anthropic` SDK。这是一个活生生的"依赖最小化"案例——用抽象层（litellm）的代价是引入了供应链风险。

---

## 心智模型

> **"Agent 的核心抽象只有 7 个组件，其余都是产品化开销"**

nanobot 与 Claude Code（512K LOC）的对比揭示了一个清晰的分层：

| 层 | 组件 | nanobot | Claude Code |
|----|------|---------|-------------|
| **必要层** | Tool Registry + Agent Loop + Context + Memory + Skills + Hooks + Bus | ✅ ~1200 LOC | ✅ 包含但淹没在产品代码中 |
| **产品层** | Permission System, Feature Flags, Bridge Protocol, Plugin Marketplace, Observable Store, Coordinator Mode, Cost Tracking, Companion Sprite... | ❌ 不需要 | ✅ ~510K LOC |

**适用条件**：个人助手、研究原型、教育场景——不需要企业级权限和安全的场景
**失效条件**：多用户 SaaS、企业部署（需要权限/审计/合规）、IDE 集成（需要 Bridge 协议）
**在我的工作中如何用**：mini_symphony 和 insight_agent 目前处于"必要层"阶段，应该对标 nanobot 的精简度而非 Claude Code 的完备度

---

## 非显见洞见

### 洞见 1：子 Agent 隔离最彻底的方式是"工具不存在"，而非"调用被拒绝"

nanobot 的 SubagentManager 在创建子 Agent 时，工具集里根本没有 message 和 spawn 工具。Claude Code 的做法是 setState=no-op（工具存在但调用无效）。

- 所以：nanobot 的方式更安全——LLM 在 tool_definitions 里看不到这些工具，就不会尝试调用
- 所以：这解释了为什么 nanobot 不需要权限系统——通过"工具集裁剪"就实现了能力隔离
- 因此可以：mini_symphony 的子任务可以用"传入不同的工具列表"来控制能力范围，而不是在运行时检查权限

### 洞见 2：raw-archive 降级——"不丢数据"比"精确合并"优先级更高

MemoryStore 连续 3 次 LLM 合并失败后，直接 dump 原始消息到 HISTORY.md。

- 所以：这是一个"容错优先于优雅"的设计——宁可有噪声但完整的记录，也不能因为 LLM 抽风而丢失历史
- 所以：所有依赖 LLM 的关键路径（合并、分类、摘要）都应该有非 LLM 降级方案
- 因此可以：insight_agent.py 的 URL 分析如果 LLM 失败，可以直接保存原始网页内容到 `analysis/raw/` 目录，而不是什么都不做

### 洞见 3：AgentRunner 解耦是 Python agent 框架最有价值的抽象

runner.py 把"调 LLM → 执行工具 → 拼结果"循环提取为无产品依赖的纯函数。三个不同的调用者（主循环、子 Agent、SDK）共享同一个 runner。

- 所以：大多数 Python agent 框架（LangChain、CrewAI）的问题是把 agent loop 和框架绑死了——你没法在不同上下文（CLI/API/test）中复用循环
- 所以：runner 的 spec 模式（AgentRunSpec dataclass 传入所有参数）比依赖注入更适合 agent——因为每次调用的参数都可能不同
- 因此可以：把 mini_symphony 的核心循环提取为类似的 `TaskRunner.run(spec)` 模式，让 CLI 和 programmatic API 共享同一个执行引擎

### 洞见 4：38K stars / 2 个月 = "极简+多平台"是 Agent 框架的杀手组合

nanobot 的爆发增长不是因为技术最先进，而是因为：(1) 代码量小到任何人都能理解，(2) 支持 12 个聊天平台开箱即用，(3) one-click 部署。

- 所以：开源 agent 框架的竞争力不在"功能多"，而在"部署快 + 可理解"
- 所以：Claude Code 的 512K LOC 对开源社区来说是不可理解的（需要专门的分析文档才能消化），而 nanobot 的 1200 LOC 是可读的
- 因此可以：如果我们想让 mini_symphony 有社区影响力，应该追求"最小可用"而非"功能完备"

---

## 隐含假设

- **LLM 足够智能来做记忆合并**：forced tool_choice + save_memory 工具假设 LLM 能正确合并新旧记忆。如果 LLM 质量下降（便宜模型），合并质量也会下降
- **单用户场景**：没有 RBAC、没有权限系统、没有审计日志。`allowFrom` 是白名单而非角色权限
- **Python GIL 不是瓶颈**：asyncio 并发 + Semaphore(3) 对 I/O 密集型场景足够，但 CPU 密集型工具会阻塞
- **OpenAI 兼容 API 是通用标准**：所有 provider 都通过 OpenAI 兼容层适配（Anthropic 除外有原生 SDK）。假设这个标准不会分裂
- **context_window_tokens / 2 是安全水位**：记忆合并在 50% 窗口时触发，留一半给新对话。对长任务链这可能太激进

---

## 反模式与陷阱

- **litellm 供应链中毒**：2026-03-21 发现并紧急移除。教训：抽象层引入的不只是技术债务，还有安全风险 → 正确做法：依赖最小化，优先用原生 SDK
- **子 Agent 无递归保护**：虽然子 Agent 没有 spawn 工具，但如果未来加了 MCP 支持，MCP 工具可能间接触发递归 → 正确做法：加 max_depth 计数器
- **会话锁可能导致死锁**：`_session_locks` 是 per-session 的 asyncio.Lock，如果一个请求处理中触发了子 Agent 的 MessageBus 回调并进入同一 session → 正确做法：使用 reentrant lock 或分离回调队列

---

## 与现有知识库的连接

- **关联 `analysis/claude-code-architecture-patterns.md`**：最直接的对比。nanobot 的 7 个核心组件 vs Claude Code 的 10 个可迁移模式。两者共有：Tool Registry、Agent Loop、Memory、Skills、Hooks。Claude Code 额外的：Permission、Feature Flags、Bridge、Observable Store、Coordinator——都是产品化层
- **关联 `analysis/symphony-orchestration-spec.md`**：Symphony 的 workspace 隔离 vs nanobot 的子 Agent 工具集裁剪——两种隔离哲学：限制能力 vs 限制影响
- **关联 `python/mini_symphony.py`**：mini_symphony 约 500 LOC，nanobot core 约 1200 LOC。mini_symphony 缺少的：Memory system、Skill loader、Hook lifecycle、concurrent tool execution。可以借鉴 nanobot 的 AgentRunner 提取模式
- **关联 `python/session_tracker.py`**：session_tracker 的 FTS5 restore vs nanobot 的 HISTORY.md grep search——两种会话恢复策略的对比。nanobot 更简单（文件 grep），session_tracker 更精确（SQL query）
- **关联 `analysis/pi-context-engineering.md`**：pi 的 7 个 context engineering 决策 vs nanobot 的 ContextBuilder——都在解决"如何在有限 context 中塞入最大信息"
- **关联 `analysis/karpathy-llm-wiki-pattern.md`**：nanobot 的两层记忆（MEMORY.md + HISTORY.md）是 Karpathy wiki 模式在 agent 内部的微缩版——MEMORY.md = 编译型 wiki（LLM 合并维护），HISTORY.md = append-only log。`_fail_or_raw_archive` 降级 = 一种极端的 lint 策略（宁可有噪声也不丢数据）

---

## 衍生项目想法

### 想法 1：mini_symphony AgentRunner 提取

**来源组合**：[nanobot 的 AgentRunner 解耦模式] × [已有 KB 的 mini_symphony.py]
**为什么有意思**：当前 mini_symphony 的执行逻辑和 CLI 入口绑在一起。借鉴 nanobot 的 `AgentRunSpec → AgentRunner.run() → AgentRunResult` 模式，可以让 mini_symphony 在 CLI / Python API / 子任务三个场景中复用同一个执行引擎。
**最小 spike**：把 mini_symphony 的 `_execute_task()` 方法提取为独立的 `TaskRunner` 类，接收 `TaskRunSpec` dataclass。

**验证状态**：
- 原始来源：✅ nanobot 已实现此模式（runner.py 被 3 处复用）
- GitHub：⚠️ LangChain/CrewAI 有类似的 executor 概念，但与框架深度绑定，不如 nanobot 纯净
- 社区：⚠️ "agent runner decoupling" 是已知的好实践，但 Python 生态中干净的 spec-based runner 模式少见
- 增量价值：把 nanobot 的 runner 解耦模式移植到 mini_symphony 的 task queue 上下文

### 想法 2：LLM 降级链模式——所有 LLM 关键路径加 raw-fallback

**来源组合**：[nanobot 的 raw-archive 降级] × [已有 KB 的 insight_agent.py]
**为什么有意思**：insight_agent.py 如果 LLM 调用失败就什么都不保存。借鉴 nanobot 的 `_fail_or_raw_archive` 模式：LLM 失败 N 次后，保存原始数据而非丢弃。对 insight 收集来说，有原始网页内容总比什么都没有好。
**最小 spike**：在 insight_agent.py 加 try/except，LLM 失败时把 web_fetch 的原始内容保存到 `analysis/raw/{url-slug}.md`。

**验证状态**：
- 原始来源：✅ nanobot 已实现（3 次失败后 raw dump）
- GitHub：✅ 未找到 "LLM fallback to raw archive" 的显式模式
- 社区：✅ Circuit breaker + graceful degradation 是微服务常见模式，但在 LLM agent 中显式应用的少见
- 增量价值：把微服务的 graceful degradation 理念引入 LLM agent 的数据路径
