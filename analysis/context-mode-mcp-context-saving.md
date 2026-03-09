# Context Mode：MCP 上下文压缩与会话持续性架构精读

**来源**: [Stop Burning Your Context Window — We Built Context Mode](https://mksg.lu/blog/context-mode) · [GitHub: mksglu/context-mode](https://github.com/mksglu/context-mode)
**日期**: 2025-07-13
**标签**: MCP, context-engineering, LLM, Claude Code, SQLite, FTS5, BM25, agent, session-continuity

---

## 30秒 TL;DR

> MCP 工具调用每次都向 context window 倾倒原始数据（Playwright 快照 56 KB，GitHub Issues 59 KB），30分钟后 40% context 消耗殆尽。Context Mode 是一个 MCP 中间层，通过两个机制解决问题：① **沙箱执行**——子进程运行代码/命令，只有 stdout 的摘要进 context（315 KB → 5.4 KB，减少 98%）；② **会话持续性**——每次工具调用的结构化事件写入 SQLite，context 被压缩前生成快照，压缩后通过 FTS5+BM25 检索重建工作状态，Agent 能从上次结束的位置继续，无需用户重新解释。

---

## 概念总览

| 概念/模式 | 核心思想 | 适用场景 |
|---------|---------|---------|
| MCP 沙箱执行 | 子进程隔离，仅 stdout 进 context | 任何会产生大量输出的工具调用 |
| Intent-driven filtering | 输出 >5 KB 时，先全量索引再按 intent 检索 | 不确定输出大小的外部工具 |
| 三层模糊搜索 | Porter 词干 → Trigram 子串 → Levenshtein 纠错 | 拼写不稳定的代码/命令查询 |
| 优先级快照 | P1-P4 四级事件，压缩时先丢低优先级 | ≤2 KB 预算下的状态保全 |
| 双层强制路由 | Hook（拦截）+ 指令文件（引导），缺一实际只有 60% 遵从率 | 需要强制保证 AI 走沙箱路径 |
| Smart Truncation | Head 60% + Tail 40%，保留错误信息 | 长输出的尾部往往有关键报错 |

---

## 深读

### 问题的两个半边

作者将 context 问题精确切成**两半**：

1. **输入侧**：81+ 工具定义本身消耗 143K tokens（72%），Cloudflare Code Mode 通过压缩定义解决了这一半。
2. **输出侧**：工具返回原始数据，每次调用累积损耗。Context Mode 解决的是这另一半。

这是一个重要的**问题分割**：之前所有人都看到了"context 不够"，但作者将其拆成定义侧和输出侧两个独立问题，分别有对应的解法。

### 沙箱架构

```
Claude Code
    │
    ▼ PreToolUse Hook（拦截）
Context Mode MCP Server
    │
    ▼ ctx_execute / ctx_execute_file / ctx_batch_execute
Isolated Subprocess
    │  ← 11种语言 runtime（JS/TS/Python/Shell/Ruby/Go/Rust/PHP/Perl/R/Elixir）
    │  ← Bun 自动检测，JS/TS 快 3-5x
    │  ← 凭证透传（继承环境变量，不暴露给 conversation）
    ▼
stdout only → context
raw data    → stays in sandbox
```

**关键设计决策**：子进程边界隔离意味着脚本之间不共享内存/状态。这既是安全边界也是性能隔离——一个脚本崩溃不影响其他。

**Intent-driven filtering（意图驱动过滤）**：当输出 >5 KB 且提供了 `intent` 参数时，切换到另一个模式：

```
大输出 > 5 KB + intent 参数
    │
    ▼
全量输出 → 索引进知识库（FTS5）
         → 按 intent 搜索匹配段落
         → 返回相关内容 + 可搜索词汇表
```

这避免了"要么全要，要么全丢"的两难，变成了按需检索。

### 知识库架构（SQLite FTS5 + BM25）

```
ctx_index
    │
    ▼ 按 heading 分块，保留 code block 完整性
SQLite FTS5 virtual table
    │  ← Porter stemming（索引时）
    │  ← BM25 ranking（TF-IDF + 文档长度归一化）
    ▼
ctx_search → 智能提取（关键词周围窗口，非头部截断）
```

**三层模糊搜索回退**：

| 层级 | 机制 | 示例 |
|-----|-----|-----|
| Layer 1 | Porter 词干 + FTS5 MATCH | "caching" → "cached/caches/cach" |
| Layer 2 | Trigram 子串匹配 | "useEff" → "useEffect" |
| Layer 3 | Levenshtein 距离纠错 | "kuberntes" → "kubernetes" |

**Smart Truncation（60/40 分割）**：
```
[head: 前 60% 行] → 初始化上下文
[tail: 后 40% 行] → 关键错误信息（日志末尾的 FATAL/stack trace）
```
旧方法盲目截断头部 N 字节，会丢失最关键的末尾报错。

**Progressive Throttling（渐进节流）**：

- 调用 1-3 次：正常结果（每查询 2 条）
- 调用 4-8 次：减少结果（每查询 1 条）+ 警告
- 调用 9+ 次：**阻断**，强制使用 `ctx_batch_execute`

这是一个显式的"反滥用"机制，防止 Agent 陷入搜索循环。

### 工具决策矩阵

| 数据类型 | 最佳工具 | 原因 |
|---------|---------|-----|
| 文档、API 参考 | `ctx_index + ctx_search` | 需要精确代码示例，不能摘要 |
| 日志、测试输出 | `ctx_execute_file` | 需要聚合统计，不需要原始行 |
| CSV 数据、分析 | `ctx_execute_file` | 需要计算指标 |
| 浏览器快照 | `ctx_execute_file` | 需要页面结构摘要 |
| 多命令批量 | `ctx_batch_execute` | 合并多次调用开销 |

**核心区别**：`ctx_execute_file` 返回摘要（适合日志），`ctx_search` 返回原始代码块（适合文档）。用错会导致要么返回无用摘要，要么返回过多冗余。

### 会话持续性架构

这是比沙箱更精妙的设计。Context 压缩（compaction）是 Agent 在长任务中最大的"失忆"来源：

```
正常工作中
    │  PostToolUse Hook → SQLite 写入结构化事件
    │  UserPromptSubmit Hook → 捕获用户决策（"用 X 不用 Y"）
    ▼
Context 接近满了 → 自动压缩触发
    │
    ▼ PreCompact Hook
从 SQLite 读所有事件
→ 按 P1-P4 优先级构建 XML 快照（≤2 KB）
→ 存入 session_resume 表
    │
    ▼ SessionStart Hook (source: "compact")
取出快照
→ 写结构化事件文件 → 自动索引进 FTS5
→ 生成 15 分类 Session Guide
→ 注入 <session_knowledge> 指令进 context
→ 模型从上次 prompt 继续，无需重新解释
```

**优先级快照（≤2 KB）**：

| 优先级 | 内容 | 说明 |
|------|-----|-----|
| P1（关键） | 活跃文件、任务、规则、最后一条用户 prompt | 永不丢弃 |
| P2（高） | 用户决策、Git 操作、错误、环境变量 | 空间够时保留 |
| P3（正常） | MCP 工具调用计数、子 Agent 任务、Skill 调用 | 压缩时先丢 |
| P4（低） | 会话意图分类、大量粘贴的数据引用 | 最先丢弃 |

### 双层路由强制机制

| 强制层 | 工作方式 | 遵从率 |
|------|---------|------|
| Hook 拦截 | 在工具执行前编程阻断 `curl`/`wget`/大文件读取，重定向到沙箱 | ~98% |
| 指令文件（CLAUDE.md/AGENTS.md） | 告诉模型"优先用沙箱工具"，但无法阻止 | ~60% |

**关键洞见**：单靠提示词指令无法可靠改变 Agent 行为，必须有程序化拦截。这不是 AI 问题，而是软件工程问题——"告诉"不等于"强制"。

### 跨平台支持差异

| 平台 | Hook 类型 | 会话完整性 | 备注 |
|-----|---------|---------|-----|
| Claude Code | Shell hooks | **完整** | 全部 5 种 hook 类型 |
| Gemini CLI | Shell hooks | 高 | 缺 UserPromptSubmit |
| VS Code Copilot | JSON hooks | 高 | 缺 UserPromptSubmit |
| OpenCode | TS 插件 | 高 | SessionStart 暂不支持 |
| Codex CLI | 无 hook | **无** | 只靠 AGENTS.md 约 60% 遵从 |

---

## 心智模型

> **"MCP 工具输出是未经过滤的数据流，context window 是珍贵的有限资源——这两者之间需要一个虚拟化层，就像 OS 在进程和内存之间的作用。"**

**适用条件**：
- Agent 需要频繁调用会产生大量输出的工具（Web 抓取、日志分析、代码运行）
- 会话持续时间超过 20-30 分钟，需要跨 compaction 保持状态
- 有多个工具平行运行，需要合并输出

**失效条件**：
- 工具输出本身就很小（<1 KB），沙箱带来的开销大于收益
- 任务是一次性短对话，不需要 session continuity
- 环境没有 hook 支持（如 Codex CLI），只有 60% 效果

---

## 非显见洞见

### 洞见 1：Context 压缩（Compaction）是真正的"失忆"——不是 context 满了，而是被强制遗忘

- **所以**：仅仅节省 context 使用不够，还必须解决压缩后的状态恢复
- **所以**：必须在压缩发生**之前**构建状态快照，而不是压缩**之后**再重建
- **因此可以**：任何长任务 Agent 都应该有 PreCompact hook，把工作状态序列化到持久存储，而不依赖 context 本身作为"记忆"

### 洞见 2："指令文件"和"Hook 拦截"是两个独立的可靠性维度

- **所以**：告诉模型"要这样做"的提示词只能达到 60% 合规率，哪怕写得再好
- **所以**：对于不能容忍 40% 失败率的行为（如"不要把日志倒进 context"），必须有程序化拦截
- **因此可以**：在所有 Agent 系统中，区分"希望模型做的事"（提示词）和"必须做的事"（hook/guard），前者用提示优化，后者用代码强制

### 洞见 3：`ctx_execute_file` vs `ctx_search` 的选择标准是"摘要 vs 精确"，不是数据大小

- **所以**：文档/代码需要 `ctx_search` 返回精确原文，日志/CSV 需要 `ctx_execute_file` 返回摘要
- **所以**：用 `ctx_execute_file` 处理文档会返回"有 5 个代码块"这样无用的描述
- **因此可以**：在任何检索系统设计中，先问"下游需要精确原文还是统计摘要"，再选择压缩策略

### 洞见 4：60/40 Smart Truncation 比简单的"头部 N 字节"更好，原因是错误信息几乎总在末尾

- **所以**：传统截断方式会丢掉最关键的 stack trace 和 FATAL 错误
- **所以**：日志分析的效果下限由截断策略决定
- **因此可以**：在任何需要截断长输出的系统中，默认保留 tail（最后 30-40%），因为错误信息、总结行、退出码都在末尾

### 洞见 5：优先级快照的大小约束（≤2 KB）不是技术限制，而是防止"快照膨胀"导致 session restore 时本身消耗大量 context

- **所以**：快照越小，恢复时注入 context 的成本越低
- **所以**：2 KB 快照大约等于 500 tokens，对 200K context 窗口影响可忽略
- **因此可以**：设计任何 Agent 状态持久化时，显式设置大小预算，并用优先级决定裁剪顺序

---

## 反模式与陷阱

- **陷阱：只用 MCP-only 安装（无 hook）**：只有 60% 的工具调用会走沙箱，剩下 40% 直接倾倒原始数据。一次 56 KB 的 Playwright 快照就能抹掉整个会话的压缩收益。→ 正确做法：始终启用 hook，hook + 指令双层覆盖。

- **陷阱：对文档用 `ctx_execute_file`**：会返回"有 5 个代码块，3 个关于 cleanup 的章节"这样的无用摘要——Agent 无法基于此编写正确代码。→ 正确做法：文档/API 参考用 `ctx_index + ctx_search`，保留精确原文。

- **陷阱：不设置 `--continue` 直接重启会话**：Context Mode 在没有 `--continue` 的情况下，**立即删除**上一个会话的 SQLite 数据——"新会话=干净石板"。→ 正确做法：需要继续上次任务时，用 `claude --continue` 启动。

- **陷阱：依赖 Codex CLI 的 session continuity**：Codex CLI 没有 hook 支持（PR 被关闭），每次压缩都完全失忆。→ 正确做法：长任务选择有完整 hook 支持的平台（Claude Code/Gemini CLI/VS Code Copilot）。

- **陷阱：过度调用 `ctx_search`（9次+被阻断）**：Progressive throttling 在第 9 次调用时直接阻断 search，强制用 `ctx_batch_execute`。→ 正确做法：多个查询合并为一次 `ctx_batch_execute`，一个调用中完成。

- **陷阱：忽略 `intent` 参数**：大输出（>5 KB）不带 intent 时，无法触发 intent-driven filtering，退化为全量截断输出。→ 正确做法：对可能产生大量输出的工具调用，始终提供 `intent` 描述。

---

## 与现有知识库的连接

- 关联 `python/tape_context.py`：Tape 的"锚点（Anchor）+ 按需装配"思想与 Context Mode 的"Session Event + FTS5 检索恢复"是同一心智模型的不同实现层级——前者是 Python 库级别的轻量实现，后者是 SQLite 持久化 + 跨进程 hook 的生产级实现。两者共同验证了"不靠历史继承，靠结构化事件 + 检索重建"这一上下文管理范式。
- 关联 `python/fts5_fuzzy_search.py`：Context Mode 的三层模糊搜索（Porter→Trigram→Levenshtein）与知识库中的 FTS5 三层搜索实现完全同构，是同一设计在不同项目中的独立验证，且 Context Mode 增加了 BM25 ranking 层。
- 关联 `analysis/pi-context-engineering.md`：pi agent 的 7 个 context engineering 决策与 Context Mode 互补——pi 侧重于 system prompt 设计和工具定义压缩，Context Mode 侧重于工具输出压缩和跨 compaction 状态持久化。
- 关联 `python/mini_symphony.py`：mini_symphony 的 per-task workspace 隔离与 Context Mode 的子进程隔离沙箱有相似的隔离哲学——任务状态不应污染全局上下文。

---

## 衍生项目想法

### 想法 1：Session Event Exporter — 将 Context Mode 的 SQLite 事件导出为复盘报告

**来源组合**：[Context Mode 的结构化事件捕获系统] + [知识库 `python/mini_symphony.py` 的任务队列]

**为什么有意思**：Context Mode 的 SQLite 里存着整个工作会话的完整事件流（文件读写、git 操作、错误、用户决策），但目前只用于会话恢复。这些数据天然是一份"工作日志"——能自动生成 PR 描述、复盘报告、任务交接文档。与 mini_symphony 的任务队列结合，可以在任务完成时自动从 SQLite 提取事件，生成结构化的"我做了什么"报告，送入下一个 Agent 任务。

**最小 spike**：
1. 找到 Context Mode 的 SQLite db 文件（`~/.context-mode/sessions.db` 或项目目录）
2. 写一个 Python 脚本，读取 session_events 表，按优先级分组输出 Markdown
3. 验证输出是否足够作为 PR description 或 CHANGELOG 条目

---

### 想法 2：Hook Compliance Monitor — 测量 AI Agent 对指令的实际遵从率

**来源组合**：[Context Mode 的"指令文件 60% vs Hook 98%"量化数据] + [知识库 `analysis/simon-willison-agentic-patterns.md` 的可观测性模式]

**为什么有意思**：Context Mode 发现了一个非显见事实：即使有明确的指令文件，Agent 有 40% 的时间会忽略指令。这意味着所有基于"系统提示词"的行为约束都有 40% 失效率，且这个失效率目前是**不可见的**。如果能有一个通用的"遵从率监测器"——在 PostToolUse 检查实际工具调用是否符合指令——就能量化任何 Agent 系统的可靠性上下限，而不是靠感觉。

**最小 spike**：
1. 在 Claude Code 项目里设置两条互斥指令（如"优先用 ripgrep 不用 grep"）
2. 运行 10 个典型任务，用 PostToolUse hook 记录实际调用的工具
3. 统计遵从率，验证是否接近 60%
4. 加上 hook 拦截后重测，验证是否升至 98%

---

### 想法 3：Intent-Aware Output Compressor — 通用 MCP 输出压缩中间件

**来源组合**：[Context Mode 的 intent-driven filtering 架构] + [知识库 `python/fts5_fuzzy_search.py` 的 SQLite FTS5 实现]

**为什么有意思**：Context Mode 的 intent-driven filtering 目前只对 `ctx_execute` 内的输出生效。但实际上任何 MCP 工具的输出都可以被这个模式处理——将工具返回的原始 JSON/文本先索引到 FTS5，再按调用者的意图检索精华部分，而不是全量注入 context。这可以做成一个通用的"MCP 输出拦截层"，不需要修改现有 MCP 工具，只在返回路径上加一层压缩。

**最小 spike**：
1. 用 `python/fts5_fuzzy_search.py` 作为基础，添加 `compress(raw_output, intent)` 函数
2. 接入一个现有 MCP 工具（如 GitHub Issues），在 PostToolUse hook 里调用 `compress`
3. 测量前后 context 大小，验证与 Context Mode 的 benchmark 是否可比
