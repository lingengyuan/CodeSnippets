# pi 的 Context Engineering：一个 260-Token Coding Agent 的七个设计决策

**来源**: [pi：一个 900 token 的 Coding Agent 到底能走多远](https://mariozechner.at/posts/2025-11-30-pi-coding-agent/)
**开源仓库**: https://github.com/badlogic/pi-mono
**作者**: Mario Zechner（libGDX 游戏引擎作者）
**日期**: 2026-03-08
**标签**: context-engineering, minimal-prompt, coding-agent, cross-provider, terminal-ui

---

## 30秒 TL;DR

> 主流 coding agent 用 10,000+ token 的系统提示，pi 用 260 token——产出质量相当。原因：RL 训练已经把"coding agent 行为"烧进了模型权重，系统提示是用来**定制**的，不是用来**解释基础**的。pi 的七个架构决策每一个都在问同一个问题：这个东西真的需要吗？

---

## 概念总览

| 决策 | 选择 | 被放弃的替代方案 |
|------|------|------|
| 系统提示长度 | 260 token | 10,000+ token（Claude Code、Codex） |
| 工具数量 | 4 个（read/write/edit/bash） | 扩展工具面 |
| MCP 集成 | ❌ 不用 | MCP（7-9% context overhead） |
| 状态管理 | 外部文件（计划/todo） | 内置功能 |
| 子 Agent | 需显式 bash 调用 | 自动派生 |
| 跨 Provider 切换 | `<thinking>` 标签中转 | Provider 锁定 |
| 终端 UI 渲染 | 差分渲染（只重绘变化行） | 全屏重绘 |

---

## 深读

### 决策 1：系统提示极简化

**完整 system prompt**（约 260 token）：
```
You are an expert coding assistant helping with coding tasks by reading files,
executing commands, editing code, and writing new files.

Available tools:
- read: Read file contents
- bash: Execute bash commands
- edit: Make surgical edits to files
- write: Create or overwrite files

Guidelines:
- Use bash for file operations like ls, grep, find
- Use read to examine files before editing
- Use edit for precise changes (old text must match exactly)
- Use write only for new files or complete rewrites
- When summarizing actions, output plain text directly—do NOT use cat or bash
  to display what you did
- Be concise in responses
- Show file paths clearly when working with files
```

**注意缺失的内容**：没有示例、没有防护规则、没有领域特定指令、没有解释"什么是 coding agent"。

### 决策 2：4 工具架构

| 工具 | 参数 | 特殊能力 |
|------|------|------|
| `read` | path, offset, limit | 支持图片（jpg/png/gif/webp）；默认 2000 行 |
| `write` | path, content | 自动创建父目录 |
| `edit` | path, oldText, newText | 要求精确匹配；手术级修改 |
| `bash` | command, timeout | 可选超时；同步执行 |

额外只读工具：`grep`、`find`、`ls`。

### 决策 3：拒绝 MCP

作者的计算：MCP 服务器需要在 context 开头加载完整的工具 schema，约 13,700-18,000 token——即使这些工具从未被调用。相比之下，CLI 工具 + README 是"按需披露"：只有被调用时才占用 context。

**核心洞见**："Progressive disclosure via CLI + README" vs "upfront schema dump via MCP"。

### 决策 4：文件即状态

计划和 todo 存文件，不存在内存/内置功能里：
- 可跨 session 持久化
- 可用 git 版本化
- 可被任意外部工具读写
- 完整可观测（不是 agent 的内部状态）

### 决策 5：子 Agent 默认不存在

子 Agent 只能通过显式 `bash` 调用派生。这避免了"黑箱中的黑箱"——子 Agent 的行为无法从主 session 观测。

### 决策 6：跨 Provider 上下文切换

```typescript
// 从 Claude 切换到 GPT 时，thinking trace 转换为 <thinking> 标签
const claude = getModel('anthropic', 'claude-sonnet-4-5');
const gpt = getModel('openai', 'gpt-5.1-codex');
// context 自动适配（provider 特有格式 → 通用 <thinking> 标签）
```

### 决策 7：差分终端渲染

```
只重绘从第一个变化行开始的内容
+ 同步输出（CSI ?2026h/l）：原子更新，避免闪烁
```

标准终端 UI 框架（Bubble Tea 等）重绘整个屏幕 → 闪烁。pi 只重绘变化行，配合同步输出转义序列实现零闪烁。

---

## 心智模型

> **"RL 训练已经教会模型怎么做 coding agent，系统提示是用来说'和通常情况有什么不同'的。"**

**适用条件**：现代 frontier 模型（Sonnet、GPT-4 及以上），通用 coding 任务。
**失效条件**：高度垂直领域（医疗、法律）或严格安全合规要求——这些确实需要明确的系统提示覆盖。
**在我的工作中如何用**：审计 mini_symphony 的 WORKFLOW.md system prompt，删除所有解释"agent 是什么"的内容，只保留项目特有的约束和上下文。预期可以从当前 N 行压缩到 <10 行核心内容。

---

## 非显见洞见

- **洞见**：系统提示 260 token vs 10,000 token 的质量差距可能比预期小得多
  - 所以：token 成本的大头不在于"解释基础"而在于"项目特有上下文"
  - 所以：system prompt 的 ROI = 差异化内容 / 总 token 数；通用 agent 描述的 ROI ≈ 0
  - 因此可以：为每个项目维护一个**最小化 CLAUDE.md**，只写"这个项目和通常项目有什么不同"，不写"你是一个 coding agent"

- **洞见**：一旦 agent 可以写代码+执行代码，任何 prompt 级别的权限系统都是安全剧场
  - 所以：真正的安全边界是执行环境（Docker + 网络隔离），不是 prompt 里的警告
  - 所以：permission prompt（"是否允许执行此命令？"）在不受信任的环境中没有价值
  - 因此可以：在生产部署 mini_symphony 时，不依赖任何 prompt 级别的限制，而是把 agent 运行在网络受限的 Docker 容器里

- **洞见**：MCP 的"协议税"是每次 session 固定支付的（13.7k-18k token），而不是按工具调用支付
  - 所以：MCP 工具数量越多，固定税越重——即使只用其中 2 个工具
  - 所以：CLI + README 的"零 token 税"在 token 敏感场景有明显优势
  - 因此可以：在 insight_agent 里，把工具描述写得极简（已在 SYSTEM_PROMPT 中这样做），避免工具描述本身成为 context 负担

---

## 隐含假设

- **假设：单用户专家操作者**。"我从没找到需要 max-steps 的场景" → 作者知道什么时候该打断。非专家用户需要明确的步骤上限和中断机制。若不成立：agent 可能无限循环直到 context 耗尽。

- **假设：Token 计费可以是 best-effort**。"我没有多用户计费需求"。若不成立（SaaS 产品）：无法精确归因 token 消耗到具体用户，billing 不准确。

- **假设：单机 session，不需要 context compaction**。"几百条消息都没问题"。若不成立（超长 session）：context window 耗尽，没有内置压缩机制。

---

## 反模式与陷阱

- **MCP upfront 加载陷阱**：启用 MCP 服务器后，每次 session 开始都支付 13.7k-18k token 的 schema 加载成本，无论这些工具是否被用。→ 正确做法：评估工具被调用的频率；低频工具用 CLI bash 调用，不挂 MCP。

- **子 Agent 黑箱陷阱**：在主 agent 内部自动派生子 agent → 主 session 无法观测子 agent 的文件操作和 bash 调用。→ 正确做法：子 agent 只通过 bash 显式调用；子 agent 的 working directory 记录在日志里。

- **Token 追踪精度假设陷阱**：不同 provider 对同一请求报告的 token 数有差异（Cerebras/xAI 拒绝某些字段），best-effort 计费在多 provider 环境下可能严重失真。→ 正确做法：用 provider 原始 token 计数，不做跨 provider 归一化。

- **全文件 `write` 覆盖 vs `edit` 精准修改**：`write` 会丢失文件中未包含在 content 参数里的内容（并发写入时数据丢失）。→ 正确做法：只对新文件或完整重写用 `write`；修改现有文件必须用 `edit`（需要精确的 oldText）。

---

## 与现有知识库的连接

- 关联 `python/mini_symphony.py`：mini_symphony 的 system prompt 可以用 pi 的极简原则重写；同时 mini_symphony 的 `max_rounds=20` 是粗糙的步骤上限，可以补充超时检测（类 Symphony stall detection）
- 关联 `python/tape_context.py`：pi 的"跨 provider 上下文切换"（thinking trace → `<thinking>` 标签）是一个具体的上下文转换需求，tape_context 的锚点机制可以扩展支持这类跨 provider 格式转换
- 关联 `python/sandbox_execute.py`：pi 的"安全边界 = 执行环境而非 prompt 限制"与 sandbox_execute.py 的设计理念完全一致；sandbox_execute 的 stdout-only 隔离可以作为 mini_symphony 任务隔离的基础

---

## 衍生项目想法

### mini_symphony system prompt 极简化实验

**来源组合**：[pi: 260-token system prompt 效果等于 10,000-token] + [mini_symphony: WORKFLOW.md system prompt]
**为什么有意思**：mini_symphony 的 system prompt 包含大量解释性内容，pi 证明这些内容的边际价值接近零；削减 system prompt 可以降低每次任务的 token 成本，同时可能改善模型遵循率（更少的噪音）
**最小 spike**：把 WORKFLOW.md 的 system prompt 压缩到 10 行以内，运行 3 个相同任务对比输出质量和 token 消耗
**潜在难点**：需要建立评估标准——如何衡量"输出质量"？用任务完成率还是人工评分？

### pi 差分渲染移植到 mini_symphony 的进度显示

**来源组合**：[pi: 差分渲染（只重绘变化行）+ 同步输出] + [mini_symphony: 目前用 print() 线性输出]
**为什么有意思**：mini_symphony 在长任务中的实时进度显示是纯 print，看不到当前状态全貌；差分渲染可以做一个"实时任务看板"——每个任务一行，状态实时更新，不滚动
**最小 spike**：用 `rich.Live` 实现固定高度的任务状态面板，替换 mini_symphony 的 print 输出
**潜在难点**：mini_symphony 是 subprocess 调用子进程，子进程的输出需要被捕获并路由到 Live 面板
