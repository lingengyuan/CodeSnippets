# Claude Agent SDK Demos 精读

> 来源: https://github.com/anthropics/claude-agent-sdk-demos
> 日期: 2026-03-22
> 类型: Anthropic 官方 SDK demo 仓库（TypeScript 为主，含 Python 多 agent 示例）

---

## 概述

Anthropic 官方发布的 Claude Agent SDK 示例集，展示如何在应用中嵌入 Claude 作为后端 agent。仓库包含 8 个独立 demo，核心 SDK 包为 `@anthropic-ai/claude-agent-sdk`（TS）和 `claude-agent-sdk`（Python）。

**关键认知**：这不是一个"API 调用"SDK——SDK 底层 **spawn Claude CLI 进程**，agent 拥有完整的工具集（Bash、Read、Write、WebSearch 等），与 Claude Code 的能力集几乎一致。这意味着 SDK 应用本质上是在编程化地操控一个 Claude Code 实例。

---

## 9 维度提取

### 🟢 可复用代码

**1. AsyncIterator 消息队列（TS）**

```typescript
// simple-chatapp/server/ai-client.ts
class MessageQueue {
  private messages: UserMessage[] = [];
  private waiting: ((msg: UserMessage) => void) | null = null;
  private closed = false;

  push(content: string) { /* ... */ }

  async *[Symbol.asyncIterator](): AsyncIterableIterator<UserMessage> {
    while (!this.closed) {
      if (this.messages.length > 0) {
        yield this.messages.shift()!;
      } else {
        yield await new Promise<UserMessage>((resolve) => {
          this.waiting = resolve;
        });
      }
    }
  }
}
```

用途：将 push-based 消息源（WebSocket）转为 pull-based AsyncIterator，与 SDK 的 `query()` generator 对接。
模式名称：**Push-to-Pull Adapter via Async Generator**。这是一个通用的 backpressure 解决方案。

**2. V2 Session API 模式（TS）**

```typescript
// hello-world-v2/v2-examples.ts
// 关键 API：
import { unstable_v2_createSession, unstable_v2_resumeSession, unstable_v2_prompt } from '@anthropic-ai/claude-agent-sdk';

// 基本会话
await using session = unstable_v2_createSession({ model: 'sonnet' });
await session.send('...');
for await (const msg of session.stream()) { /* ... */ }

// 会话恢复（跨进程保持 context）
await using session = unstable_v2_resumeSession(sessionId!, { model: 'sonnet' });

// 一次性调用
const result = await unstable_v2_prompt('...', { model: 'sonnet' });
console.log(result.result, result.total_cost_usd);
```

注意 `await using` 语法——利用 TC39 Explicit Resource Management（`Symbol.asyncDispose`）自动清理。

**3. canUseTool 拦截器模式（TS）**

```typescript
// ask-user-question-previews/server.ts
canUseTool: async (toolName, input) => {
  if (toolName === "ToolSearch" || toolName === "ExitPlanMode") {
    return { behavior: "allow", updatedInput: input };
  }
  if (toolName !== "AskUserQuestion") {
    return { behavior: "deny", message: "Use AskUserQuestion instead." };
  }
  // 将 AskUserQuestion 的选项发送给浏览器，等待用户选择后注入回答
  const answers = await waitForBrowserAnswer(input);
  return { behavior: "allow", updatedInput: { questions, answers } };
}
```

模式名称：**Tool Interception + Human-in-the-Loop Bridge**。SDK 在 tool 调用前暂停，应用代码桥接外部交互后注入结果。

### 🏗️ 技术模式

**1. "SDK-as-Agent-Process" 模式**

SDK 不是直接调 API——它 spawn 一个 Claude CLI 子进程。这决定了：
- 每个 session 是一个独立的操作系统进程
- agent 拥有 CLI 的全部工具集，包括文件系统访问
- `cwd` 参数控制 agent 的工作目录（沙箱隔离的基础）
- hooks 是进程级别的拦截器，不是 HTTP middleware

**2. V1 vs V2 API 架构差异**

| 维度 | V1 (`query()`) | V2 (`createSession`) |
|------|-----------------|---------------------|
| 接口 | 单个 async generator | send() + stream() 分离 |
| 多轮 | 通过 MessageQueue 注入用户消息 | 自然的 send→stream→send 循环 |
| 持久化 | 无内建 | `resumeSession(sessionId)` |
| 一次性 | 需自行处理 | `unstable_v2_prompt()` 便捷函数 |
| 成熟度 | 稳定 | unstable_v2_* 前缀 |

**3. 多 Agent 编排模式（Research Agent）**

```
Lead Agent (orchestrator, model=haiku, tool=Task only)
 ├── Researcher-1 (haiku, tools=[WebSearch, Write])
 ├── Researcher-2 (haiku, tools=[WebSearch, Write])
 ├── Researcher-3 (haiku, tools=[WebSearch, Write])
 ├── Data-Analyst (haiku, tools=[Glob, Read, Bash, Write])
 └── Report-Writer (haiku, tools=[Skill, Write, Glob, Read, Bash])
```

关键设计：
- Lead agent 只有 `Task` 工具——通过 `AgentDefinition` 定义子 agent 的类型、工具集和 prompt
- 子 agent 的工具集是**白名单**的（Researcher 只能 WebSearch+Write，不能 Bash）
- 文件系统作为通信总线：研究员写 `files/research_notes/`，分析员读取后写 `files/charts/`
- 全部用 haiku 模型——成本控制的明确意图

**4. WebSocket 双向桥接模式**

两个 demo（simple-chatapp、ask-user-question-previews）都使用 WebSocket 作为 SDK 与浏览器之间的桥梁：

```
Browser ←WebSocket→ Express Server ←SDK spawn→ Claude CLI Process
```

simple-chatapp 的 Session 类管理了 subscriber 模式：多个 WebSocket 客户端可以订阅同一个 agent session。

**5. PreToolUse Hook 沙箱（Hello World）**

```typescript
PreToolUse: [{
  matcher: "Write|Edit|MultiEdit",
  hooks: [async (input) => {
    // 只允许 .js/.ts 文件写入 custom_scripts 目录
    if (!filePath.startsWith(customScriptsPath)) {
      return { decision: 'block', stopReason: '...' };
    }
    return { continue: true };
  }]
}]
```

模式名称：**Hook-based File System Sandbox**。通过 matcher + 路径检查限制 agent 的写入范围。

### 📦 工具与依赖

| 工具 | 版本 | 用途 |
|------|------|------|
| `@anthropic-ai/claude-agent-sdk` | ^0.1.59 | TypeScript SDK |
| `claude-agent-sdk` (Python) | >=0.1.0 | Python SDK |
| Bun / Node.js 18+ | — | 运行时 |
| `ws` | — | WebSocket 服务端 |
| Express | — | REST API |
| React + Vite + Tailwind | — | 前端 |
| reportlab (Python) | — | PDF 生成 |
| matplotlib (Python) | — | 数据图表 |

### 🧠 心智模型

**1. "Agent 即进程"心智模型**

SDK 的核心抽象不是 HTTP 客户端，而是进程管理器。`query()` 启动一个带完整工具集的 Claude 进程，hooks 是进程生命周期的拦截器，`cwd` 是进程的工作目录。这与 Anthropic API 的 `messages.create()` 是完全不同的思维方式。

**2. "文件系统即 IPC"心智模型**

Research Agent 用文件系统作为子 agent 之间的通信渠道（`research_notes/` → `data/` → `charts/` → `reports/`）。这不是 hack，而是有意的设计——文件系统是 agent 天然理解的 IPC 机制，无需额外的消息协议。

**3. "工具白名单即安全边界"心智模型**

安全不靠信任 prompt，靠限制工具集：
- Lead agent 只能 spawn 子 agent（`Task` 工具），不能直接操作
- Researcher 只能搜索和写文件，不能执行代码
- Report-writer 可以执行 Bash（需要 reportlab 生成 PDF），但不能搜索

### ⚖️ 权衡取舍

**1. V1 generator vs V2 session**
- V1：更简单，单个异步迭代器搞定一切。但多轮对话需要自己实现 MessageQueue 这样的适配器
- V2：多轮对话更自然（send/stream 分离），但 `unstable_` 前缀表示 API 可能变

**2. 全部用 haiku vs 混合模型**
- Research Agent 全用 haiku：成本极低，但研究质量可能受限
- Resume Generator 用 sonnet，Hello World 用 opus：不同任务不同模型
- 隐含判断：搜索+综合类任务用小模型足够，创意/推理密集型任务需要大模型

**3. 文件系统 IPC vs 结构化消息传递**
- 文件系统：agent 天然理解、可调试（用 cat 就能看）、但需要约定目录结构
- 结构化消息：类型安全、不依赖文件系统、但需要额外的序列化/反序列化

**4. permissionMode: "bypassPermissions" vs "plan"**
- Research Agent 用 `bypassPermissions`：子 agent 全自动，不等人类确认
- AskUserQuestion demo 用 `plan`：强制 Claude 先问问题再行动
- 隐含判断：内部自动化用 bypass，面向用户的应用用 plan

### ⚠️ 反模式与陷阱

1. **MessageQueue 没有 backpressure**：如果 agent 处理慢而消息来得快，队列会无限增长。生产环境需要限制队列长度或丢弃旧消息
2. **sessions Map 没有清理机制**：simple-chatapp 的 `sessions: Map<string, Session>` 只在 delete 时清理，长时间运行会内存泄漏
3. **SubagentTracker 用 `type(msg).__name__` 做类型检查**：Python SDK 的消息类型可能在版本间变化，这比 `isinstance()` 更脆弱
4. **`permissionMode: "bypassPermissions"` 意味着 agent 可以执行任何 Bash 命令**：Research Agent 的 Data-Analyst 子 agent 有 Bash 工具且 bypass permissions——如果 prompt injection 通过搜索结果注入，可能执行恶意命令
5. **V2 API 标记为 unstable**：`unstable_v2_*` 前缀明确表示 API 会变，不适合生产依赖

### 💡 非显见洞见

**1. SDK 的真正价值不是 API 封装，而是 agent 编排基础设施**

表面看 SDK 是一个 API 客户端库，实际上它提供的是：进程管理、工具权限控制、hooks 拦截、子 agent 定义、会话持久化。这些是构建 agent 应用的基础设施，不是 API 调用的便利封装。

→ 所以：选 SDK vs 直接调 API 不是"方便 vs 灵活"的选择，而是"要不要 agent 运行时"的选择
→ 所以：如果你的应用只需要文本生成，SDK 是过度的；但如果需要 agent 执行任务，SDK 是必需的
→ 因此可以：评估项目时，问"我的应用是对话型还是任务型？"来决定用 API 还是 SDK

**2. `canUseTool` 是构建"Agent-as-Backend"的关键抽象**

`canUseTool` 允许应用代码在每次工具调用前拦截、修改、拒绝、或等待外部输入。这不只是权限检查——它是将 agent 嵌入应用逻辑的连接点：
- 等待用户在浏览器中做选择（AskUserQuestion demo）
- 注入应用状态到工具输入中
- 根据业务规则动态允许/拒绝操作

→ 所以：任何需要 human-in-the-loop 的 agent 应用，关键都在于 `canUseTool` 的实现
→ 所以：`canUseTool` 本质上是一个中间件模式，可以链式组合多个拦截器
→ 因此可以：用 `canUseTool` 实现审计日志、费用控制、A/B 测试等横切关注点

**3. 文件系统是 agent 原生的 IPC 机制**

Research Agent 不用消息队列、不用 RPC、不用共享内存——子 agent 通过文件系统交换数据。这看起来"原始"但实际上是最优选择：
- Agent 天然会用 Read/Write 工具操作文件
- 无需额外的序列化协议
- 中间产物可人类审查（markdown 文件比 protobuf 好读）
- 天然支持"断点续跑"（文件在磁盘上持久化）

→ 所以：设计多 agent 系统时，文件系统应该是默认 IPC，除非有明确的性能需求才考虑其他方案
→ 所以：目录结构就是 agent 间的 API contract
→ 因此可以：定义 `files/{stage_name}/` 目录约定作为多 agent pipeline 的标准接口

**4. "工具白名单 + 小模型"是 agent 安全的实用策略**

Research Agent 的每个子 agent 只获得执行其任务所需的最少工具集，并且全用最小的 haiku 模型。这不仅是成本优化——小模型更难被 prompt injection 操纵（推理能力弱 = 更难"理解"注入指令），工具白名单限制了即使被操纵后的爆炸半径。

→ 所以：agent 安全不是一个"加密"问题，而是一个"最小权限 + 能力缩减"问题
→ 所以：越信任 agent 自主性的场景，越应该缩小工具集和模型能力
→ 因此可以：建立"agent 安全级别"框架——L1（只读）、L2（读写特定目录）、L3（可执行代码）、L4（可网络访问）

### ❓ 开放问题

1. **V2 Session API 何时稳定？** `unstable_v2_*` 前缀暗示 API 正在演进中，是否应该现在就基于 V2 构建？
2. **子 agent 的 prompt injection 防御怎么做？** Research Agent 的 researcher 子 agent 直接消费搜索结果——如果搜索结果包含 prompt injection，researcher 可能被操纵
3. **SDK 进程模型的伸缩性？** 每个 session 一个子进程，在多用户场景下的资源消耗如何？
4. **`AgentDefinition` 能否支持更复杂的编排？** 当前只有扁平的 lead→sub 结构，能否做嵌套编排（sub 里再 spawn sub）？
5. **Python SDK 和 TS SDK 的 feature parity 如何？** Research Agent 用 Python SDK，API 风格与 TS 不同（`ClaudeSDKClient` vs `query()`）

### 🚀 衍生想法种子

见 Step 3D 的组合生成部分。

---

## 深度推理

### 3A：蕴含链

**洞见 1：SDK spawn CLI 进程，agent 拥有完整工具集**

→ 所以：SDK 应用本质上是在编程化操控 Claude Code 实例
→ 所以：任何 Claude Code 能做的事（读写文件、执行代码、搜索网页），SDK 应用都能做
→ 所以：SDK 应用的能力上限 = Claude Code 的能力上限
→ 因此可以：先在 Claude Code 中手动验证 workflow，然后直接用 SDK 自动化

**洞见 2：`canUseTool` 在 tool 调用前暂停等待外部输入**

→ 所以：agent 的执行流可以在任意 tool 调用点"暂停"
→ 所以：这等价于一个协程的 yield 点——agent 是一个在 tool 调用上 yield 的协程
→ 所以：可以在 yield 点注入任何逻辑：审批、计费、限流、路由
→ 因此可以：基于 `canUseTool` 构建一个通用的 "agent middleware" 框架

**洞见 3：Research Agent 用 haiku 做所有子 agent**

→ 所以：子 agent 不需要强推理——搜索+整理+格式化是 haiku 的甜点
→ 所以：lead agent 也用 haiku——编排决策足够简单（分解成 2-4 个子主题）
→ 所以：在成本敏感的 agent 应用中，90% 的工作可以交给最便宜的模型
→ 因此可以：建立"模型预算分配"原则——只在最终输出质量有直接影响的环节用大模型

### 3B：隐含假设挖掘

**假设 1：用户只在本地运行**

README 明确说"NOT be deployed to production"。所有 demo 都假设单用户、本地环境：
- 没有认证/授权
- 内存存储（重启丢数据）
- `bypassPermissions` 绕过所有安全检查
- 如果违反这个假设：安全问题、资源竞争、数据丢失

**假设 2：文件系统可靠且快速**

Research Agent 的 IPC 假设文件写入即时可见。在网络文件系统（NFS/EFS）或高并发场景下，这个假设可能不成立。

**假设 3：子 agent 能遵循目录约定**

Research Agent 的正确性依赖于子 agent 将输出写入约定目录（`files/research_notes/`）。如果 agent 不遵守（写到其他地方、用错文件名），pipeline 就断了。没有任何运行时验证。

**假设 4：搜索结果是安全的**

Researcher 子 agent 直接消费 WebSearch 结果并写入文件。如果搜索结果包含恶意内容（prompt injection），可能影响后续 agent 的行为。Data-Analyst 有 Bash 工具——如果 research_notes 中被注入了恶意指令，可能执行任意代码。

### 3C：反事实分析

**Q：为什么用 CLI 进程 spawn 而不是直接调 API？**

选择 CLI spawn 意味着：每个 agent 是独立进程、有自己的文件系统视图、可以执行真正的 Bash 命令。
如果选 API 直接调用：需要自己实现工具执行（Bash、Read、Write 等），但获得更好的进程效率和更细粒度的控制。
决策逻辑：SDK 的目标是降低门槛——让开发者不需要自己构建 agent 运行时，直接复用 Claude CLI 的全部能力。

**Q：为什么 Research Agent 用 Python 而其他 demo 用 TypeScript？**

可能原因：Python 的 async/await 模型更适合复杂的多 agent 编排（asyncio 比 Node.js 的 event loop 更容易推理嵌套并发）。也可能只是为了展示两个 SDK 都能用。

**Q：为什么 AskUserQuestion demo 不用 V2 Session API？**

`canUseTool` 回调在 V1 `query()` 中就支持——不需要 V2 的多轮能力。选 V1 降低了复杂度，也表明 V1 并非过时。

### 3D：组合生成

**[本次：AgentDefinition 多 agent 编排] × [已有：mini_symphony.py 的 TASKS.md 队列]**

→ 新想法：给 mini_symphony 增加 SDK 子 agent 作为执行器类型——除了 spawn claude/pi CLI 外，可以用 AgentDefinition 定义专用 agent（带工具白名单和自定义 prompt），在同一个 TASKS.md 中混用
→ 价值：比通用 claude 进程更安全（限定工具集）、比纯 CLI spawn 更可编程（hooks 拦截）
→ 最小验证实验：在 mini_symphony 的 worker 层增加一个 `executor: sdk-agent` 类型，用 ClaudeSDKClient 替代 subprocess.Popen，在单个任务上对比效果

**[本次：canUseTool 拦截器模式] × [已有：session_tracker.py 的事件捕获]**

→ 新想法：基于 `canUseTool` 构建一个通用的 agent 审计中间件——每次 tool 调用自动写入 SQLite（像 session_tracker 一样），支持事后查询"agent 做了什么"
→ 价值：canUseTool 在 tool 执行前拦截（比 PostToolUse hook 更早），可以同时做审计和权限控制
→ 最小验证实验：写一个 `auditMiddleware(canUseTool)` 装饰器，包装任意 canUseTool 回调，自动将 tool_name + input 写入 JSONL

**[本次：文件系统 IPC 的 agent 间通信] × [已有：context-mode-session-continuity-pattern 的 snapshot 机制]**

→ 新想法：在多 agent 文件系统 IPC 上叠加一层"snapshot point"——每个阶段完成时生成一个优先级快照（≤2 KB），作为下一个 agent 的 context 引导，而不是让它读全部文件
→ 价值：解决 context 窗口限制——Data-Analyst 不需要读所有 research_notes 的全文，只需要快照中的关键数据点
→ 最小验证实验：在 Research Agent 的 lead_agent.txt 中增加一条规则："研究完成后，让最后一个 researcher 写一个 snapshot.md 总结所有子主题的关键数字"

### 3E：边界与反例

**规模边界**
- 单用户 demo 假设，1-10 并发 session 可能 OK，100+ 并发 session 每个都 spawn 一个 CLI 进程会把服务器打垮
- Research Agent 的 2-4 个子 agent 适合单次查询，但如果需要 20+ 子 agent 的复杂研究，进程开销会很大

**复杂度边界**
- 扁平的 lead→sub 编排适合线性 pipeline（搜索→分析→报告），但不适合需要反馈循环的场景（报告质量不够 → 追加研究 → 重新分析）
- 文件系统 IPC 在 2-3 个阶段间没问题，但 10 个阶段的 pipeline 目录约定会变得混乱

**团队边界**
- 单人开发 demo 级别的代码，没有测试、没有错误恢复、没有监控
- 多人协作需要：类型安全的消息协议（替代文件名约定）、集成测试、agent 执行的可观测性

**反例场景**
1. 高频实时应用（如聊天机器人服务 1000 并发用户）：每用户一个 CLI 进程不可接受
2. 需要事务性保证的应用（如金融操作）：文件系统 IPC 没有事务语义，agent 中途崩溃会留下部分写入的文件

---

## 来源完整性

以上所有代码均从仓库原文提取，未虚构。分析和推理基于代码的实际结构和行为。
