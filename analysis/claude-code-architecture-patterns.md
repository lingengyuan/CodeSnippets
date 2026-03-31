# Claude Code 架构精读：生产级 Agent CLI 的 10 个可迁移模式

**来源**: `/Users/hughlin/Projects/claude-code`（2026-03-31 泄露的 TypeScript 源码，~1900 文件，512K+ LOC）
**日期**: 2026-03-31
**标签**: agent-architecture, tool-system, permission-model, startup-optimization, context-compression, multi-agent, feature-flags

---

## 30秒 TL;DR

> Claude Code 是 Anthropic 的 CLI Agent 工具，基于 Bun + React/Ink 构建。从 512K LOC 中提取了 10 个可迁移到我们自己 Agent 项目的工程模式：(1) buildTool() 工厂 + 并发安全标记，(2) async generator 流式 QueryEngine 循环，(3) 5 阶段启动优化（pre-import 副作用→并行 prefetch→lazy loading→deferred prefetch→条件性 prefetch），(4) 规则+分类器+拒绝追踪三层权限，(5) Worker 状态隔离（setAppState no-op），(6) 4 层 Skill 加载（bundled/project/user/plugin），(7) 索引+按需注入的 MEMORY.md 模式，(8) bun:bundle 编译时 DCE + GrowthBook 运行时双层 feature flag，(9) 35 行 Observable Store，(10) UUID 环形缓冲去重的 Bridge 协议。

---

## 概念总览

| 模式 | 核心思想 | 适用场景 |
|------|---------|---------|
| **buildTool() 工厂** | 工具 = schema + permission + call 的标准化注册 | 任何需要可扩展工具系统的 Agent |
| **Async Generator QueryEngine** | LLM 交互 = async generator yield 流式事件 | Agent 主循环设计 |
| **5 阶段启动优化** | 不同阶段用不同策略：pre-import / parallel / lazy / deferred / conditional | CLI 工具启动加速 |
| **三层权限模型** | 规则匹配 → 分类器自动审批 → 拒绝追踪升级 | Agent 安全控制 |
| **Worker 状态隔离** | 子 Agent 的 setState = no-op，只保留任务注册通道 | 多 Agent 编排 |
| **4 层 Skill 加载** | bundled → project → user → plugin，token 预算控制 | 可扩展的 Skill/Plugin 系统 |
| **MEMORY.md 索引 + 按需注入** | 只注入索引，topic 按关键词匹配按需加载 | Agent 长期记忆 |
| **双层 Feature Flag** | 编译时 DCE（bun:bundle）+ 运行时门控（GrowthBook） | 渐进式功能发布 |
| **35 行 Observable Store** | getState / setState / subscribe，Object.is 比较 | 最小化状态管理 |
| **UUID 环形缓冲去重** | BoundedUUIDSet 有限容量 FIFO 去重 | 消息传输幂等性 |

---

## 深读

### 模式 1：buildTool() 工厂——工具即声明

每个工具（~40 个）通过 `buildTool()` 工厂注册，声明 5 个维度：

| 维度 | 作用 | 为什么重要 |
|------|------|-----------|
| `inputSchema`（Zod） | 输入验证 | LLM 生成的参数自动校验 |
| `checkPermissions()` | 权限检查 | 返回 allow/deny/ask 三态 |
| `isConcurrencySafe()` | 并发安全标记 | 决定能否并行执行 |
| `isReadOnly()` | 只读标记 | Plan 模式下只允许只读工具 |
| `call()` | 执行逻辑 | 实际工具功能 |

**关键设计决策**：并发安全由工具自己声明（不是框架推断）。BashTool 声明非安全（shell 状态共享），GrepTool 声明安全（无状态）。StreamingToolExecutor 根据标记决定并行/串行。

**对我们的启示**：mini_symphony 的任务目前是串行的。如果给每个任务加 `concurrency_safe` 标记，就可以安全地并行执行独立任务。

### 模式 2：Async Generator 流式主循环

QueryEngine 的核心是 `async *submitMessage()` 生成器：

```
用户输入 → processUserInput() → 推入 mutableMessages
         → yield 系统初始化消息
         → for await (msg of query()) { yield msg }  // 流式
         → return {duration, usage, denials}
```

**query()** 内部循环处理：
- 流式 API 响应 → yield StreamEvent
- 工具调用 → StreamingToolExecutor 并发执行 → yield 工具结果
- prompt-too-long → 触发 reactive compact → 压缩后重试
- 输出限额不足 → 自动从 8K 升到 64K → 重试
- 回退模型 → FallbackTriggeredError → 换模型重试

**对我们的启示**：insight_agent.py 当前是同步请求-响应。改成 async generator 模式可以支持流式输出和中途取消。

### 模式 3：5 阶段启动优化

| 阶段 | 策略 | 时机 | 节省 |
|------|------|------|------|
| **Phase 1** | Pre-import 副作用 | 模块加载前 | ~65ms（macOS keychain + MDM 并行） |
| **Phase 2** | Lazy require | 需要时加载 | 避免循环依赖 + 减小初始包 |
| **Phase 3** | Promise.all 并行 | 初始化时 | commands + agents + MCP 并发加载 |
| **Phase 4** | Deferred prefetch | UI 渲染后 | fire-and-forget 不阻塞首帧 |
| **Phase 5** | 条件性 prefetch | 距上次 >15min 才触发 | 避免冗余网络请求 |

**关键洞察**：Phase 1 的"pre-import 副作用"最有价值——在 ES module 评估之前就发起异步操作，利用模块加载时间做有用的事。

### 模式 4：三层权限模型

```
工具调用请求
  → 1. validateInput()：硬门控（文件大小、路径合法性）
  → 2. 规则匹配（alwaysAllow / alwaysDeny / alwaysAsk）
  → 3. 分类器自动审批（auto 模式）
  → 4. Hook 执行（pre-sampling hooks 可以自动批准）
  → 5. 用户提示（如果以上都未决定）
  → 6. 拒绝追踪：连续拒绝 ≥3 次 → 升级为"阻断"
```

**拒绝追踪升级**是最精妙的设计——防止模型反复请求已被拒绝的权限（无限循环），自动升级为硬阻断。每个子 Agent 有独立的追踪状态。

### 模式 5：Worker 状态隔离

子 Agent（Worker）的上下文创建：
- `setAppState` → **no-op**（Worker 不能修改父 UI 状态）
- `setAppStateForTasks` → **始终透传到 root**（可以注册后台任务）
- `abortController` → 子控制器（父可以杀子，子不影响父）
- MCP servers → 追加模式（子可以加新的 MCP，不能删父的）

**核心原则**：子 Agent 可以做 work（工具调用、文件操作），但不能影响 UX（UI 状态、权限设置）。唯一的向上通道是 `<task-notification>` XML。

**对我们的启示**：mini_symphony 的子任务目前共享状态。应该引入类似的隔离——子任务只能通过"结果文件"向父通信，不能修改全局状态。

### 模式 6：4 层 Skill 加载

| 层级 | 来源 | 加载时机 |
|------|------|---------|
| Bundled | 编译到二进制 | 启动时注册 |
| Project | `.claude/skills/*.md` | 按项目加载 |
| User | `~/.claude/skills/*.md` | 全局加载 |
| Plugin | 插件提供 | 插件激活时 |

**Token 预算控制**：`estimateSkillFrontmatterTokens()` 只计算 frontmatter 的 token 数（内容按需加载），防止大量 skill 撑爆 system prompt。

**去重**：通过 `realpath()` 解析符号链接检测重复 skill。

### 模式 7：MEMORY.md 索引 + 按需注入

```
~/.claude/projects/<slug>/memory/
  ├── MEMORY.md          ← 始终注入（索引，≤200行/25KB）
  ├── topic1.md          ← 按需注入
  └── topic2.md          ← 按需注入
```

模型输出中出现 `<[topic_name]>` 标签时触发 `findRelevantMemories()`，扫描 memory 文件并注入匹配内容。**只有索引进入初始 context，topic 按需加载**。

**对我们的启示**：CodeSnippets 的 README.md 就是一个 MEMORY.md 的角色——索引。当前 insight-collector 的 Step 0 读取整个 README 做扫描。如果 KB 继续增长，可能需要类似的"索引+按需"策略。

### 模式 8：双层 Feature Flag

**编译时**（bun:bundle DCE）：
```typescript
const mod = feature('VOICE_MODE') ? require('./voice') : null
// false 分支在构建时完全消除（包括字符串字面量）
```

**运行时**（GrowthBook 远程门控）：
```typescript
if (isVoiceGrowthBookEnabled()) { /* 远程 kill-switch */ }
```

**正向三元组模式**：必须用 `feature('X') ? doWork() : null`，不能用 `if (!feature('X')) return` —— 后者在 false 分支时 `doWork()` 仍然会被内联，导致敏感字符串泄露。

### 模式 9：35 行 Observable Store

整个状态管理层只有 35 行：`createStore<T>` 提供 `getState()` / `setState(updater)` / `subscribe(listener)`。

- 不用 Immer、不用 Redux、不用 Zustand
- 变更检测用 `Object.is`（引用比较）
- 可选 `onChange` 回调接收 `{newState, oldState}`
- React 接入用 `useAppState(selector)` + memoized selector

**对我们的启示**：Agent 项目的状态管理不需要复杂框架。一个 subscribe/publish 模式就够了。

### 模式 10：Context 压缩（Compact）策略

触发条件四种：auto（token 超阈值）、manual（/compact）、session-start（resume 时）、reactive（prompt-too-long 时）。

压缩算法：
1. 按 API 轮次分组消息
2. 用 Claude（最小 system context）生成摘要
3. 保留 thinking blocks + tool-use 结构骨架，替换文本为摘要
4. 压缩后恢复 5 个关键文件（带预算上限）
5. 重新注入被引用的 Skill（5KB/skill，~25KB 总预算）

---

## 心智模型

> **"Agent 是工具调用的状态机，不是对话的延续"**

Claude Code 的核心循环是 `while(有工具调用) { 执行工具 → 把结果喂回 LLM → 拿到下一步 }`。这不是"对话"——是"工具驱动的状态机"。每轮的输入不是"用户说了什么"，而是"工具返回了什么"。

**适用条件**：需要执行多步操作的 Agent（编辑文件、运行命令、搜索代码）
**失效条件**：纯对话场景（无工具调用），或单轮问答
**在我的工作中如何用**：mini_symphony 和 insight_agent 都应该以"工具调用循环"为核心设计，而非"prompt-response"线性流程

---

## 非显见洞见

### 洞见 1：并发安全是工具自声明的，不是框架推断的

框架不尝试分析工具是否有副作用——由每个工具自己声明 `isConcurrencySafe()`。BashTool = false（shell 有状态），GrepTool = true（无状态）。

- 所以：这是"知道自己有多安全的是组件本身，不是上层调度器"
- 所以：在 mini_symphony 中，任务本身应该声明"是否可以与其他任务并行"
- 因此可以：给 TASKS.md 的任务格式加一个 `parallel: true/false` 标记

### 洞见 2：拒绝追踪升级 = 防止 Agent 死循环的安全阀

如果用户连续 3 次拒绝同一权限，系统自动从"ask"升级到"block"。这解决了一个 Agent 的经典问题：模型不理解"不"的意思，反复请求同一操作。

- 所以：任何 Agent 的重试机制都需要"升级阈值"——连续失败 N 次后改变策略，而不是无限重试
- 所以：这与 autoresearch 的"NEVER STOP"哲学形成有趣的张力——"永不放弃"需要搭配"改变策略"
- 因此可以：mini_symphony 的两级重试（prompt retry → model escalation）可以加第三级：连续失败后标记任务为 blocked 而非无限重试

### 洞见 3：pre-import 副作用是启动优化的最大杠杆

在 ES module 评估（import 链）之前就发起 keychain 读取和 MDM 查询——利用模块加载的"死时间"做有用的 I/O。这比所有 lazy loading 加起来的效果都大。

- 所以：启动优化的关键不是"少加载什么"，而是"在不可避免的等待期间做什么"
- 所以：Python 的 import 也有类似的"死时间"——可以在 `__init__.py` 中发起 async I/O
- 因此可以：insight_agent.py 启动时可以在 import anthropic 的同时 prefetch README.md 内容

### 洞见 4：子 Agent 的 setState 是 no-op——隔离的精髓

Worker 可以调用所有工具（bash、edit、read），但 `setAppState` 被替换为 no-op。**工作能力完整，状态影响为零**。唯一的向上通道是结构化的 `<task-notification>` XML。

- 所以：多 Agent 系统的关键不是"子 Agent 能做什么"，而是"子 Agent 能改变什么"
- 所以：mini_symphony 的子任务如果能修改全局状态（如 README、WORKFLOW.md），就有潜在的干扰风险
- 因此可以：mini_symphony 加 `--isolate` 模式——子任务在 git worktree 中工作，只通过结果文件通信

---

## 隐含假设

- **单用户模型**：权限系统假设只有一个人在操作——没有 RBAC（角色权限控制）
- **LLM 能力足够**：分类器自动审批（auto 模式）依赖 LLM 的判断力——如果 LLM 犯错，安全性下降
- **Bun 运行时可用**：整个架构深度绑定 Bun（bun:bundle DCE、native NAPI 加载），不可移植到 Node.js
- **网络可用**：GrowthBook feature flags 需要网络；离线时回退到缓存（stale-friendly）
- **Context window 足够大**：200K context window 是许多设计的前提；在更小的 window 下需要更激进的压缩

---

## 反模式与陷阱

- **用 `if (!feature('X')) return` 而不是三元组**：false 分支的代码仍然会被内联，导致敏感字符串泄露到 bundle 中 → 正确做法：`feature('X') ? require('./module') : null`
- **子 Agent 共享父状态**：导致子 Agent 的操作污染父 Agent 的 UI 和权限 → 正确做法：setState no-op + 结构化通知通道
- **无限重试相同的失败操作**：Agent 不理解"不"，反复请求同一权限 → 正确做法：拒绝追踪 + 升级阈值
- **启动时全量加载所有模块**：重型模块（OpenTelemetry ~400KB, gRPC ~700KB）拖慢启动 → 正确做法：lazy import() 到首次使用时

---

## 与现有知识库的连接

- 关联 `analysis/symphony-orchestration-spec.md`：Symphony 的 workspace 隔离 = Claude Code 的 Worker setState no-op。两者都隔离子任务的状态影响，只通过结构化消息通信。
- 关联 `analysis/pi-context-engineering.md`：pi 的 7 个 context engineering 决策 vs Claude Code 的 5 阶段启动优化——都在回答"如何最大化利用有限的 context 和启动时间"
- 关联 `analysis/karpathy-autoresearch.md`：autoresearch 的"NEVER STOP"vs Claude Code 的"拒绝追踪升级"——"永不放弃"必须搭配"改变策略"
- 关联 `analysis/context-mode-mcp-context-saving.md`：Context Mode 的 98% 压缩 vs Claude Code 的 Compact 服务——两种 context 压缩策略的对比（输出沙箱 vs 摘要+骨架保留）
- 关联 `ideas/progress-as-code-manifest.md`：Claude Code 的 buildTool() 注册模式可以启发 manifest 脚本的"声明式文件描述"设计
- 关联 `analysis/claude-code-ai-reimplementation-ethics.md`：本分析只提取架构模式（ideas, not expression），与前篇伦理分析的"规格级知识 > 实现级代码"结论一致

---

## 衍生项目想法

### 想法 1：mini_symphony 并发执行 + 隔离模式

**来源组合**：[Claude Code 的 isConcurrencySafe + Worker 隔离] × [已有 KB 的 mini_symphony 任务队列]
**为什么有意思**：当前 mini_symphony 是串行执行。借鉴 Claude Code 的模式：(1) 任务自声明 `parallel: true/false`，(2) 并行任务在 git worktree 中隔离执行，(3) 通过结果文件通信。这能显著加速多任务场景。
**最小 spike**：给 TASKS.md 格式加 `parallel` 标记，mini_symphony 读取后对 parallel=true 的任务用 `subprocess.Popen` 并发启动。
**潜在难点**：git worktree 创建有开销；任务间可能有隐式依赖。

**验证状态**：
- 原始来源：✅ Claude Code 实现了完整的 Worker 隔离，但绑定 Bun 生态
- GitHub：⚠️ 有 git worktree 用于 CI 并行的案例，但没有 Agent 任务队列 + worktree 隔离的组合
- 社区：⚠️ OmX 的 $team 模式做了类似的事（并行 worktree），但 OmX 绑定 Codex 生态
- 增量价值：把 Claude Code 的 Worker 隔离模式移植到轻量级 Python Agent 编排器

### 想法 2：拒绝追踪 + 策略升级模式

**来源组合**：[Claude Code 的拒绝追踪升级] × [已有 KB 的 mini_symphony 两级重试]
**为什么有意思**：mini_symphony 当前的重试是"prompt retry → model escalation"两级。加入"拒绝追踪"后变成三级：retry → escalate → block。这解决了 Agent 死循环问题——连续失败不是"再试一次"，而是"标记为 blocked 等待人工干预"。
**最小 spike**：在 mini_symphony 的任务执行中加一个失败计数器，连续 3 次失败后标记 `status: blocked`。
**潜在难点**：阈值设置——太低误阻断，太高浪费时间。

**验证状态**：
- 原始来源：✅ Claude Code 实现了连续拒绝 ≥3 次自动升级的机制
- GitHub：✅ 没有找到 Agent 编排器中显式的"拒绝追踪升级"模式
- 社区：⚠️ 通用的 circuit breaker 模式在微服务中常见，但在 Agent 编排中是新应用
- 增量价值：把 circuit breaker 思维引入 Agent 任务编排——"Agent 的断路器"
