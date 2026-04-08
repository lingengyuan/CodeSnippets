# Simon Willison Git 工作流 + 子 Agent 模式精读

**来源**:
- [Using Git with coding agents](https://simonwillison.net/guides/agentic-engineering-patterns/git/)
- [Subagents](https://simonwillison.net/guides/agentic-engineering-patterns/subagents/)
**日期**: 2026-04-08
**标签**: agentic-engineering, git-workflow, subagents, parallel-agents, specialist-agents, context-management
**系列**: Agentic Engineering Patterns — Working with Coding Agents 第 2-3 篇

---

## 30秒 TL;DR

> 两篇合并精读。**Git 篇**：Agent 让 Git 的高级功能（bisect、history rewriting、library extraction）变得日常化——以前"太麻烦不用"的操作现在一个 prompt 搞定。最佳实践："Look at the last few commits"是最有效的 session 启动方式。**Subagents 篇**：子 Agent 是"新鲜 context window + 特定任务指令"的组合，解决三个问题：(1) 保护根 context 不被低价值 token 污染，(2) 并行处理独立文件编辑，(3) 用不同 system prompt 实现 specialist 角色（reviewer / test runner / debugger）。核心心智模型：**子 Agent 是 context 管理策略，不只是并发优化。**

---

## Part 1: Git 工作流模式

### 模式 1: "Look at the last few commits" 启动法

```
session 启动 prompt:
"Look at the last few commits to understand what I've been working on"

效果：
→ Agent 执行 git log --oneline -10
→ 自动获得：项目当前方向、近期改动模式、命名惯例、技术栈线索
→ 比手动写 context briefing 更快更准确
```

**为什么有效**：commit history 是**自然产生的 context**——无需维护，永远最新。

### 模式 2: Git bisect 日常化

以前 git bisect 的使用率极低（太繁琐），Agent 改变了这一点：

```
prompt: "Use git bisect to find which commit broke the login page"

Agent 自动：
1. git bisect start
2. 标记 good/bad commit
3. 对每个候选 commit 执行测试
4. 报告引入 bug 的具体 commit
```

**关键判断**：bisect 的"繁琐"部分（手动标记、来回切换）恰好是 Agent 擅长的重复性工作。

### 模式 3: History rewriting 常规化

> "Don't think of Git history as a permanent record — it's a deliberately authored story."

Agent 有"good taste in commit messages"——因为它能看到整个 diff 并用一句话总结。
- Interactive rebase：Agent 可以把 10 个碎片 commit 合并成 3 个有意义的 commit
- Commit message 改写：给 Agent 看 diff 让它写 message，通常比人写的更一致

### 模式 4: Library extraction 保留历史

```
任务：把 utils/ 从主 repo 提取到独立 repo，保留 git history

Agent 使用 git filter-repo / git subtree split：
→ 复杂的 git plumbing 命令不需要人记
→ Agent 知道 edge cases（空 commit、merge commit 处理）
```

---

## Part 2: 子 Agent 模式

### 核心概念

**子 Agent = 新鲜 context window + 受限工具集 + 特定任务 prompt**

```
Root Agent                          Sub-agent
┌─────────────────┐               ┌─────────────────┐
│ 完整 context     │  dispatch →  │ 空 context       │
│ 50K tokens used  │               │ + 任务指令       │
│ 复杂对话历史     │               │ + 必要文件       │
│                  │  ← result    │                  │
│ 继续主线工作     │               │ 结束，释放       │
└─────────────────┘               └─────────────────┘
```

**核心价值不是并发，而是 context 隔离**：
- Root context 不被搜索结果、测试日志等低价值 token 淹没
- 子 Agent 失败不影响 root 的对话状态
- 每个子 Agent 都有"干净的思考空间"

### 子 Agent 的三种角色

#### 1. Explore 子 Agent（搜索专家）

Claude Code 的实际实现：root Agent 用自己的 system prompt 实例化一个新 session，只给搜索工具。

```
Root: "Find all files that import the UserAuth module"
→ 启动 Explore sub-agent
→ Sub-agent: grep, glob, read files, 汇总结果
→ 返回结构化答案
→ Root context 只增加答案的 tokens，不增加搜索过程的 tokens
```

#### 2. Parallel 子 Agent（并行执行器）

```
Root: "Update the copyright header in all 47 template files"
→ 启动 N 个 sub-agents，每个处理一批文件
→ 所有 sub-agents 并行工作
→ Root 汇总结果
```

**关键约束**：只适用于**独立文件编辑**——如果文件间有依赖关系，并行会导致冲突。

#### 3. Specialist 子 Agent（专家角色）

| 角色 | System prompt 要点 | 工具集 |
|------|-------------------|--------|
| Code Reviewer | "只关注 bug 和安全问题，不评论风格" | read-only tools |
| Test Runner | "运行测试，分析失败原因，建议修复" | bash, read |
| Debugger | "用 GDB/debugger 追踪问题" | bash, read, write |

**每个 specialist 都有精炼的 system prompt**——这比一个"全能" Agent 用通用 prompt 的效果更好。

---

## 心智模型

> **"子 Agent 是 context 管理策略，不只是并发优化。"**

理解子 Agent 的关键不是"并行更快"（这是附带好处），而是"context 更干净"：
- 搜索 10 个文件产生 5000 tokens 的噪声 → 子 Agent 处理后只返回 200 tokens 的答案
- 测试日志 2000 行 → 子 Agent 汇总为 5 行"3 tests failed, root cause: X"
- 代码审查评论 50 条 → 子 Agent 筛选为 3 条"真正重要的"

**适用条件**：(1) root context 已经很满；(2) 任务可以独立执行；(3) 结果可以结构化汇总
**失效条件**：(1) 任务需要 root 的完整对话历史；(2) 结果高度不确定需要 root 实时判断；(3) 启动 sub-agent 的开销大于节省

---

## 非显见洞见

### 洞见 1: "Look at the last few commits" 是最便宜的 context seeding

- 所以：commit history 是**零维护成本的 context source**——不需要写 README、ARCHITECTURE.md 就能让 Agent 理解项目方向
- 所以：保持良好的 commit 习惯有了新的激励——不只是给人看，也是给 Agent 读
- 因此可以：在 AGENTS.md 的 session-start 部分加入 "always start by reading recent git log"

### 洞见 2: 子 Agent 的 context 压缩比是衡量其价值的关键指标

- 所以：一个好的子 Agent 应该把 N tokens 的工作压缩为 N/10 的结果报告
- 所以：子 Agent 的 system prompt 中应该明确要求"只返回结论，不返回过程"
- 因此可以：为 mini_symphony 的 subtask 机制设计"结果压缩 prompt"——每个子任务完成后只返回 key findings + file changes

### 洞见 3: Specialist sub-agent 模式证明了"角色 prompt"比"全能 prompt"更有效

- 所以：与其给一个 Agent 一个长 system prompt 涵盖所有能力，不如拆成多个 specialist
- 所以：mini_symphony 的 task 分配不应该只按"文件"分，还可以按"角色"分（reviewer / implementer / tester）
- 因此可以：在 mini_symphony 中实现 specialist worker 机制——不同任务类型路由到不同 system prompt 的 worker

---

## 隐含假设

- **Git 篇假设代码库使用 Git**：对于 monorepo 或非 Git VCS，某些模式不适用
- **Git 篇假设测试存在**：bisect 需要可执行的测试来自动标记 good/bad
- **Subagent 篇假设 API 成本不是瓶颈**：每个子 Agent 都是一次新 API 调用，高频使用成本累积
- **Subagent 篇假设任务可分解**：并非所有任务都能拆成独立子任务

---

## 反模式与陷阱

- **子 Agent 过度拆分**：5 行改动不需要子 Agent → 判断标准：子 Agent 的 context 压缩比是否 > 5x
- **Parallel sub-agents 改有依赖的文件**：两个 sub-agent 都改同一个文件 → 冲突 → 应该串行或用文件锁
- **忽视 git log 作为 context**：很多人手写长段 context briefing → 不如直接让 Agent 读 git log + README

---

## 与现有知识库的连接

- **关联 `analysis/hkuds-nanobot-minimalist-agent.md`**：nanobot 的 SubagentManager 正是 Willison 描述的 specialist sub-agent 模式——`spawned_agents` dict 管理独立 context 的子 Agent 生命周期
- **关联 `analysis/claude-code-architecture-patterns.md`**：Claude Code 的 Worker 进程 = Explore sub-agent 的生产级实现。Worker 的 `abortController` / `kill()` 机制 = sub-agent 的生命周期管理
- **关联 `analysis/simon-willison-red-green-tdd.md`**：git bisect + Agent = TDD 的自然延伸——红绿循环中的"找到哪个 commit 引入了红"变得 trivial
- **关联 `analysis/simon-willison-agentic-patterns.md`**：本文补充了 overview 中缺失的 Working with Coding Agents 章节细节
- **关联 `analysis/pi-context-engineering-prompt-design.md`**：子 Agent 的 system prompt 设计 = context engineering 的子域。Pi 文中的"精确指令"原则直接适用于 specialist sub-agent 的 prompt
- **关联 `python/mini_symphony.py`**：mini_symphony 的 TASKS.md → agent 分发机制 = 原始形态的 sub-agent dispatcher。可以从 Willison 的 specialist 模式获得改进方向

---

## 衍生项目想法

### 想法 1: mini_symphony specialist worker 机制

**来源组合**：[Specialist sub-agent 模式] × [已有 mini_symphony 任务分发]
**为什么有意思**：当前 mini_symphony 所有 worker 使用相同 prompt。如果根据任务类型（实现/测试/审查/文档）路由到不同 specialist prompt，应该能显著提升每类任务的质量。
**最小 spike**：在 mini_symphony 的 worker 启动逻辑中，根据 task type 选择不同的 system prompt template（3 个 template：implementer / tester / reviewer）。

**验证状态**：
- 原始来源：✅ Willison 描述了概念但没有具体 task-queue 实现
- GitHub：⚠️ Claude Code 有 Explore 子 Agent 但没有 specialist router
- 社区：⚠️ 多角色 Agent 概念有讨论，但 task-queue × specialist 组合较少
- 增量价值：把 specialist sub-agent 模式融入 task queue 框架

### 想法 2: "git log as context" session starter

**来源组合**：[Git log 启动法] × [已有 AGENTS.md]
**为什么有意思**：在 AGENTS.md 中加入 session-start hook，让任何新 Agent session 首先读最近 git log——零成本获得最新 context。
**最小 spike**：在 AGENTS.md 的顶部加一行 "Start every session by running: git log --oneline -15"。

**验证状态**：
- 原始来源：✅ Willison 建议了做法，但没有系统化到 AGENTS.md 模板中
- GitHub：✅ 未找到将此模式 codify 到 AGENTS.md 的公开案例
- 社区：✅ 概念已有共识但实现方式各异
- 增量价值：把经验性建议固化为项目级标准
