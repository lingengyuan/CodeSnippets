# pi 的 Context Engineering：一个 900 Token Coding Agent 的七个设计决策

> 来源: 文章《pi：一个 900 token 的 Coding Agent 到底能走多远》
>       原文: mariozechner.at/posts/2025-11-30-pi-coding-agent/
>       开源仓库: github.com/badlogic/pi-mono
> 日期: 2026-03-05
> 作者: Mario Zechner（libGDX 游戏引擎作者）
> 关联: analysis/symphony-orchestration-spec.md, python/mini_symphony.py

---

## 一句话

pi 用不到 1000 token 的 system prompt + 工具定义，砍掉了主流 coding agent 90% 的功能，
在 Terminal-Bench 2.0 上提交了成绩，并在作者日常工作中使用了数周。
核心论点：**前沿模型经过大量 RL 训练，天然理解 coding agent 是什么，不需要万字 system prompt 来"教"它。**

---

## 完整 System Prompt（原文，约 200 token）

```
You are an expert coding assistant. You help users with coding tasks
by reading files, executing commands, editing code, and writing new files.

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
- When summarizing your actions, output plain text directly
  - do NOT use cat or bash to display what you did
- Be concise in your responses
- Show file paths clearly when working with files

Documentation:
- Your own documentation (including custom model setup and theme
  creation) is at: /path/to/README.md
- Read it when users ask about features, configuration, or setup,
  and especially if the user asks you to add a custom model or
  provider, or create a custom theme.
```

唯一会被追加到末尾的是用户的 AGENTS.md 文件（全局和项目级的）。

---

## 完整工具定义（原文）

```
read
  Read the contents of a file. Supports text files and images (jpg, png,
  gif, webp). Images are sent as attachments. For text files, defaults to
  first 2000 lines. Use offset/limit for large files.
  - path: Path to the file to read (relative or absolute)
  - offset: Line number to start reading from (1-indexed)
  - limit: Maximum number of lines to read

write
  Write content to a file. Creates the file if it doesn't exist, overwrites
  if it does. Automatically creates parent directories.
  - path: Path to the file to write (relative or absolute)
  - content: Content to write to the file

edit
  Edit a file by replacing exact text. The oldText must match exactly
  (including whitespace). Use this for precise, surgical edits.
  - path: Path to the file to edit (relative or absolute)
  - oldText: Exact text to find and replace (must match exactly)
  - newText: New text to replace the old text with

bash
  Execute a bash command in the current working directory. Returns stdout
  and stderr. Optionally provide a timeout in seconds.
  - command: Bash command to execute
  - timeout: Timeout in seconds (optional, no default timeout)
```

此外还有 grep、find、ls 三个只读工具，默认关闭，只在 `pi --tools read,grep,find,ls` 时启用。

---

## 七个设计决策

### 决策 1：极简 System Prompt

**做了什么**: system prompt + 工具定义合计不到 1000 token。

**为什么可行**:
> "All the frontier models have been RL-trained up the wazoo, so they
> inherently understand what a coding agent is. There does not appear to be
> a need for 10,000 tokens of system prompt."

对比参照：
- Claude Code 的 system prompt：~10,000 token
- Codex 的 system prompt：公开在 GitHub，同样很精简（Mario 认为是进一步佐证）
- opencode：被描述为 Claude Code 原始 prompt 的精简版

**注意事项**: 这是基于个人使用和 benchmark 的观察，**不是严格消融实验**。
没有控制变量下对比"同一模型 + 原生 prompt" vs "同一模型 + 极简 prompt"的效果差异。

---

### 决策 2：只给 4 个工具

**做了什么**: read、write、edit、bash。

**核心论点**:
> bash 本身就是万能工具。你需要 grep？`bash: grep -rn "pattern" src/`
> 你需要 git？`bash: git diff HEAD~1`。你需要跑测试？`bash: npm test`

**bash 工具的一个重要细节**: pi 的 bash 是**同步执行**的，没有后台进程管理。
如果需要运行 dev server 同时让 agent 干别的事，Mario 的方案是用 tmux：

```bash
# Agent 在 tmux session 里启动 dev server
bash: tmux new-session -d -s devserver "npm run dev"

# Agent 继续在主 session 工作
bash: curl http://localhost:3000/api/health

# 你可以随时切到 tmux session 观察
tmux attach -t devserver
```

对 Claude Code 后台 bash 的批评："poor observability"，早期版本在 context compaction 后
会丢失对后台进程的追踪。tmux 方案的优势：你能看到一切，还能直接介入。

---

### 决策 3：不用 MCP——渐进式工具发现

**做了什么**: pi 不内置任何外部工具，完全不支持 MCP。

**Mario 给出的具体数据**:

| MCP Server | 工具数 | Token 消耗 |
|-----------|--------|-----------|
| Playwright MCP | 21 个工具 | ~13,700 token |
| Chrome DevTools MCP | 26 个工具 | ~18,000 token |

> "That's 7-9% of your context window gone before you even start working.
> Many of these tools you'll never use in a given session."

**一旦启用 MCP server，这些工具描述在每个 session 的每次 API 调用中都会被发送，无论你是否实际使用。**

**pi 的替代方案: CLI + README（Progressive Disclosure）**

```
MCP 模式:
  Session 开始 → 加载所有工具描述 → 固定消耗 token（无论是否使用）

pi 模式:
  Session 开始 → 0 额外 token
  需要某工具时 → read README.md → bash 调用 → 只在使用时消耗 token
```

Mario 把这叫做 "progressive disclosure"（渐进式披露）。
在软件工程里，这等价于**延迟加载（Lazy Loading）**——token 成本按需支付，不预付。

Mario 维护了一个 CLI 工具集合：github.com/badlogic/agent-tools，每个工具就是一个命令行程序 + 一个 README。

如果确实离不开 MCP，Mario 推荐了 Peter Steinberger 的 mcporter 工具，
它可以把 MCP server 包装成 CLI 工具。

---

### 决策 4：不要子 Agent——可观测性优先

**做了什么**: pi 不在 session 中自动派生子 agent。

**对子 agent 的批评**:
> "When Claude Code needs to do something complex, it often spawns a sub-
> agent to handle part of the task. You have zero visibility into what that
> sub-agent does. It's a black box within a black box."

具体问题：
- 主 agent 决定给子 agent 什么上下文，你无法控制
- 子 agent 出错时，你看不到完整对话，调试困难
- context transfer between agents is poor

**pi 的替代方案**:

**方案一: Artifact 驱动的工作流**
先用一个 session 专门做上下文收集，产出一个 artifact（比如 CONTEXT.md），
然后在新 session 里基于这个 artifact 工作。这样上下文完整、可审查、可复用。

> "Using a sub-agent mid-session for context gathering is a sign you didn't plan ahead."

**方案二: 通过 bash 启动自身**（仅特定场景）
pi 通过 bash 启动自身的新实例做 code review，这是 pi 的自定义 slash command 格式
（markdown 模板 + 参数支持）：

```markdown
---
description: Run a code review sub-agent
---
Spawn yourself as a sub-agent via bash to do a code review: $@

Use `pi --print` with appropriate arguments. If the user specifies
a model, use `--provider` and `--model` accordingly.

Pass a prompt to the sub-agent asking it to review the code for:
- Bugs and logic errors
- Security issues
- Error handling gaps

Do not read the code yourself. Let the sub-agent do that.

Report the sub-agent's findings.
```

使用时，agent 把自己作为 bash 命令执行，子 agent 的完整输出对你可见。

**Mario 也明确说了他不是完全否定子 agent**:
> "I'm not dismissing sub-agents entirely. There are valid use cases."

他最常用的场景是代码 review。他反对的是在 session 中自动派生子 agent 来并行实现
多个功能——他认为这是一个反模式（"anti-pattern"），会导致代码质量下降。

---

### 决策 5：不做 Plan Mode，不做 TODO——一切皆文件

**Plan Mode 的批评**:
> "You can basically not use plan mode without approving a shit ton of
> command invocations, because without that, planning is basically
> impossible."

在 Claude Code 中，planning 通常由子 agent 执行，你看不到 agent 实际查看了哪些文件、遗漏了什么。

**pi 的方案——直接写文件**:

```markdown
# PLAN.md

## Goal
Refactor authentication system to support OAuth

## Approach
1. Research OAuth 2.0 flows
2. Design token storage schema
3. Implement authorization server endpoints
4. Update client-side login flow
5. Add tests

## Current Step
Working on step 3 - authorization endpoints
```

好处：跨 session 可用、可 Git 版本控制、你和 agent 可以协同编辑。
如果想在规划阶段限制 agent 只读不写：`pi --tools read,grep,find,ls`

**TODO 系统同理**:
> "To-do lists generally confuse models more than they help. They add state
> that the model has to track and update, which introduces more
> opportunities for things to go wrong."

替代方案同样是文件，agent 需要时 read，完成后 edit 打勾。
状态是显式的、可审查的、可版本控制的。

---

### 决策 6：跨 Provider Context Handoff

pi-ai 从设计之初就支持在不同 LLM provider 之间传递上下文。
Context 对象是纯粹的消息数组，可序列化，可在 Claude → GPT → Gemini 之间传递。

局限（Mario 坦承）：Context handoff 只能是 best-effort：
> "Since each provider has their own way of tracking tool calls and thinking
> traces, this can only be a best-effort thing."

---

### 决策 7：默认 YOLO——面对安全边界的现实

**做了什么**: pi 默认以完全无限制模式运行：不弹权限确认框，不用小模型预审命令，
完整的文件系统访问，可以执行任何命令。

**Mario 引用 Simon Willison 的分析**:
> "If an LLM has access to tools that can read private data and make network
> requests, you're playing whack-a-mole with attack vectors."

他对现有安全措施的评价是 "security theater"（安全剧场）:
> "As soon as your agent can write code and run code, it's pretty much game over."

他专门提到 Claude Code 用 Haiku 预审查 bash 命令的做法，认为这增加了延迟但无法
真正防止有意的数据外泄。

**务实建议**: 如果担心安全问题，把 pi 跑在容器里（"run pi inside a container"），
而不是依赖 agent 内部的权限控制。

**需要指出的是**: 这是一个有争议的设计选择。安全措施即使不完美也有其价值——
提高攻击门槛、防止意外误操作、满足合规要求。在团队或企业环境中需要更审慎地评估。

---

## Context Engineering 核心问题

文章最后提出的思考框架（高划线段落）：

> **你的 agent 的 context window 里，有多少 token 是花在了真正重要的事情上——**
> **用户的代码、用户的指令、项目的上下文？**
> **又有多少 token 是花在了模型早就知道的东西上？**

如果 900 token 的 system prompt 能让一个 agent 在 benchmark 上提交成绩、在真实工作中表现良好，
那些额外的 9000 token 到底买到了什么？

---

## 对 mini_symphony.py 的启示

参考 `python/mini_symphony.py`，pi 的设计决策对我们的编排器有以下直接影响：

| pi 决策 | mini_symphony 对应做法 |
|--------|----------------------|
| PLAN.md 替代 Plan Mode | TASKS.md 作为任务队列，文件即状态 |
| bash 是万能工具 | agent 通过 bash 调外部工具，不内置 MCP |
| AGENTS.md（全局+项目） | WORKFLOW.md 同时承担配置和 prompt |
| 无后台进程，用 tmux | before_run hook 可以启动 tmux session |
| pi --print 非交互模式 | `command: "pi --print"` 作为子进程执行 |

---

## pi 架构四包（供参考）

```
pi-coding-agent
├── pi-ai       统一 LLM API（Anthropic/OpenAI/Google/xAI/Groq/Cerebras/OpenRouter）
├── pi-agent-core  Agent 循环：工具执行、结果回传、重复直到不再调用工具
├── pi-tui      自研终端 UI：差分渲染 + 同步输出，接近零闪烁
└── pi-coding-agent  最终 CLI 产品
```

设计哲学：**"if I don't need it, it won't be built."**

---

## 相关资源

- pi 开源仓库：github.com/badlogic/pi-mono
- Mario 的 MCP 分析文章：mariozechner.at/posts/2025-11-02-what-if-you-dont-need-mcp/
- Claude Code System Prompt 历史：cchistory.mariozechner.at
- Terminal-Bench 2.0：github.com/laude-institute/terminal-bench
- CLI 工具集：github.com/badlogic/agent-tools
