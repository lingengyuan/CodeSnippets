# Context Mode：Agent 上下文压缩模式

**来源**: [mksg.lu/blog/context-mode](https://mksg.lu/blog/context-mode) + [GitHub](https://github.com/mksglu/claude-context-mode)
**日期**: 2026-03-01
**状态**: 💡灵感

---

## 核心内容

### 问题

Claude Code 的 200K context window 被工具输出快速耗尽：
- Playwright 快照：56 KB
- 20 个 GitHub issues：59 KB
- 一个 access log：45 KB
- 81+ 工具加载后，143K tokens（72%）在第一条消息前就被消耗

**结果**：有效工作时间约 30 分钟就 context 爆炸。

### 解决方案：沙箱 + 只回传 stdout

核心思路极其简单：**不要把原始数据放进 context，在沙箱里处理完，只把结果（stdout）放进 context。**

```
原始数据 (56 KB) → 沙箱执行脚本 → stdout (299 B) → 进入 context
```

315 KB 变 5.4 KB，压缩率 98%。工作时间从 30 分钟延长到 3 小时。

### 三层架构

**1. 沙箱系统（Sandbox）**
- 每次 `execute` 调用 spawn 一个隔离子进程
- 支持 11 种运行时：JS、TS、Python、Shell、Ruby、Go、Rust、PHP、Perl、R、Elixir
- 认证 CLI 透传：`gh`、`aws`、`gcloud`、`kubectl`、`docker` 的环境变量自动继承
- Bun 自动检测，JS/TS 执行快 3-5x

**2. 知识库系统（Knowledge Base）**
- SQLite FTS5 全文搜索
- BM25 排序 + Porter 词干化
- 按 heading 分 chunk，保持代码块完整
- 三层模糊搜索：Porter 词干 → trigram 子串 → Levenshtein 纠错

**3. Hook 系统**
- PreToolUse hook 自动拦截工具输出，路由到沙箱
- 子 agent 自动升级为 `general-purpose`，获得 MCP 工具访问权

### MCP 工具定义

| 工具 | 功能 | 压缩效果 |
|------|------|---------|
| `batch_execute` | 一次调用运行多命令 + 多搜索 | 986 KB → 62 KB |
| `execute` | 在沙箱中运行代码，只有 stdout 进 context | 56 KB → 299 B |
| `execute_file` | 在沙箱中处理文件，原始内容不出沙箱 | 45 KB → 155 B |
| `index` | Markdown 分块存入 FTS5 | 60 KB → 40 B |
| `search` | 查询索引内容，支持多查询批量 | — |
| `fetch_and_index` | 抓取 URL → 转 markdown → 建索引 | 60 KB → 40 B |

### 渐进式搜索节流

防止搜索本身淹没 context：
- 第 1-3 次调用：正常返回（每查询 2 条）
- 第 4-8 次：减少返回（每查询 1 条）+ 警告
- 第 9 次+：阻止，重定向到 `batch_execute`

---

## 可提取的技术片段

### 1. SQLite FTS5 三层模糊搜索（Python 可复用）

核心模式：精确匹配 → 子串匹配 → 模糊纠错，逐层降级。这个模式不依赖 context-mode，任何需要本地全文搜索的项目都能用。

**关联**：可以给 `python/snippet_manager.py` 加上 FTS5 搜索，替代现在的字符串匹配。

### 2. 沙箱执行 + stdout 过滤模式

思路：spawn 子进程 → 捕获 stdout → 丢弃 stderr 和原始数据。这个模式可以用在任何需要"执行但不想把全部输出放进内存/context"的场景。

### 3. Intent-Driven 过滤

当输出 > 5 KB 且提供了 intent 时：全量输出存入知识库，只检索与 intent 匹配的片段返回。这是一个通用的"大数据 → 小答案"模式。

### 4. PreToolUse Hook 拦截模式

Claude Code 的 hook 系统可以在工具执行前/后注入逻辑。这是一个扩展 agent 行为的通用模式。

---

## 延伸方向

### A. 给我们的 Tape Context 加上压缩层

**关联**: `python/tape_context.py`

Tape 的锚点 summary 本质上就是"压缩"——把一段对话压缩成一句话。Context Mode 的思路可以更系统化：
- 每条 message 入 Tape 前，先过沙箱压缩
- 锚点不只是 summary 文字，而是把完整数据存入 FTS5 知识库
- `assemble_context()` 时从知识库检索，而不是直接拼原始消息

### B. 本地 FTS5 搜索引擎给 CodeSnippets

用 SQLite FTS5 替代 snippet_manager 的字符串搜索：
- 所有片段的名称、描述、代码都建 FTS5 索引
- BM25 排序 + Porter 词干化
- 比 zvec 向量搜索更轻量，不需要 embedding 模型
- 两者可以并存：FTS5 做关键词搜索，zvec 做语义搜索

### C. Agent Context Budget 管理器

把 Context Mode 的渐进式节流思想泛化：
- 给每个工具分配 context budget（字节配额）
- 超配额自动压缩或存入知识库
- session 级别的 context 消耗追踪和预警

### D. 通用 MCP Proxy：任何 MCP 工具输出自动压缩

不绑定 Claude Code，做一个通用的 MCP 中间件：
- 拦截任何 MCP server 的工具响应
- 大于阈值的自动走 FTS5 索引 + 摘要
- 对任何 MCP 客户端透明

---

## 参考链接

- [Blog: Context Mode](https://mksg.lu/blog/context-mode)
- [GitHub: mksglu/claude-context-mode](https://github.com/mksglu/claude-context-mode)
- [SQLite FTS5 文档](https://www.sqlite.org/fts5.html)
- [Claude Code Hooks 文档](https://docs.anthropic.com/en/docs/claude-code/hooks)
