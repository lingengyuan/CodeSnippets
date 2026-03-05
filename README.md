# CodeSnippets

> A personal knowledge base for project ideas, code snippets, and implementation patterns.
>
> 记录项目灵感、代码片段和实现技巧的个人知识库。

---

## English

### Catalog

| Type | File | What it does | Dependencies |
|------|------|-------------|--------------|
| 🟢 code | `python/snippet_manager.py` | CLI snippet manager with natural-language search; combines snippets into LLM prompts | `anthropic`, `rich` |
| 🟢 code | `python/tape_context.py` | Anchor-based context assembly for multi-turn conversations (replaces history inheritance) | stdlib only |
| 🟢 code | `python/zvec_inprocess_vector.py` | In-process vector DB demo — hybrid search (semantic + structured filtering) with zero services | `zvec`, `sentence-transformers` |
| 🟢 code | `javascript/pdf_to_images.html` | Pure frontend PDF page renderer — converts each page to JPEG via PDF.js | PDF.js (CDN) |
| 🟢 code | `javascript/browser_ocr.html` | Pure frontend OCR — Tesseract WebAssembly, supports English + Chinese | Tesseract.js (CDN) |
| 🟢 code | `html-tools/pdf_ocr.html` | Complete browser-based PDF OCR tool — PDF rendering + text extraction, zero backend | PDF.js + Tesseract.js (CDN) |
| 🟢 code | `python/fts5_fuzzy_search.py` | SQLite FTS5 three-layer fuzzy search: Porter stemming → trigram substring → Levenshtein correction | stdlib (sqlite3) |
| 🟢 code | `python/sandbox_execute.py` | Isolated subprocess execution — only stdout enters context, with budget control | stdlib (subprocess) |
| 🟢 code | `python/mini_symphony.py` | Lightweight agent orchestrator: TASKS.md task queue → per-task workspace → pi/claude subprocess → two-tier retry | `pyyaml` |
| 🟢 code | `snippets/kway-merge-heap.rs` | K-way external merge sort using BinaryHeap as min-heap; groups identical keys (MapReduce Reduce phase) | stdlib (Rust) |
| 🟢 code | `snippets/atomic-file-write.rs` | Atomic file write via tmp → rename; prevents partial-write corruption | stdlib (Rust) |
| 🟡 template | `templates/WORKFLOW.md.template` | Config + prompt template for mini_symphony.py — copy and customize per project | — |
| 🟡 template | `templates/TASKS.md.example` | Task queue file example for mini_symphony.py — markdown checklist format | — |
| 🔵 reference | `analysis/simon-willison-agentic-patterns.md` | Deep-read of 7 agentic engineering patterns by Simon Willison | — |
| 🔵 reference | `analysis/symphony-orchestration-spec.md` | Deep-read of OpenAI Symphony SPEC: orchestration FSM, workspace isolation, app-server protocol | — |
| 🔵 reference | `analysis/pi-context-engineering.md` | Deep-read of pi coding agent: 7 context engineering decisions + verbatim system prompt + tool defs | — |
| 🔵 reference | `ideas/yt-browse-local-first-channel-browser.md` | Local-first channel browser patterns: fetch-cache-search, Bubble Tea Elm TUI | — |

**Type legend**: 🟢 code — run or import directly · 🟡 template — copy and customize · 🔵 reference — read when making design decisions

### Project Structure

```
CodeSnippets/
├── python/          # Python snippets
├── javascript/      # JavaScript / Node.js snippets
├── html-tools/      # Standalone single-page HTML tools
├── shell/           # Shell scripts & CLI tricks
├── snippets/        # Cross-language / general snippets
├── templates/       # Copy-paste config & file templates
├── ideas/           # Raw project ideas (markdown)
├── analysis/        # External research & reference docs
├── LICENSE          # MIT
└── README.md
```

### Usage

Each snippet is a standalone file. The header comment block describes:

- **Purpose** — what problem it solves
- **Dependencies** — what to `pip install`
- **Use cases** — where to apply it

```python
# =============================================================================
# 名称: <Snippet Name>
# 用途: <What problem it solves>
# 依赖: <pip install ...>
# 适用场景: <Where to use it>
# 日期: YYYY-MM-DD
# =============================================================================
```

### License

[MIT](LICENSE) — Copyright (c) 2026 Hugh Lin

---

## 简体中文

### 目录

| 类型 | 文件 | 功能 | 依赖 |
|------|------|------|------|
| 🟢 代码 | `python/snippet_manager.py` | CLI 片段管理器，支持自然语言搜索，可组合片段生成 LLM prompt | `anthropic`, `rich` |
| 🟢 代码 | `python/tape_context.py` | 基于锚点的上下文装配，替代历史继承，适合群聊/多任务 Agent | 标准库 |
| 🟢 代码 | `python/zvec_inprocess_vector.py` | in-process 向量库演示——混合检索（语义+结构化过滤），零服务依赖 | `zvec`, `sentence-transformers` |
| 🟢 代码 | `javascript/pdf_to_images.html` | 纯前端 PDF 页面渲染——通过 PDF.js 将每页转为 JPEG | PDF.js (CDN) |
| 🟢 代码 | `javascript/browser_ocr.html` | 纯前端 OCR——Tesseract WebAssembly，支持中英文 | Tesseract.js (CDN) |
| 🟢 代码 | `html-tools/pdf_ocr.html` | 完整的浏览器端 PDF OCR 工具——PDF 渲染 + 文字提取，零后端 | PDF.js + Tesseract.js (CDN) |
| 🟢 代码 | `python/fts5_fuzzy_search.py` | SQLite FTS5 三层模糊搜索：Porter 词干 → trigram 子串 → Levenshtein 纠错 | 标准库 (sqlite3) |
| 🟢 代码 | `python/sandbox_execute.py` | 隔离子进程执行——只有 stdout 进入 context，带 budget 控制 | 标准库 (subprocess) |
| 🟢 代码 | `python/mini_symphony.py` | 轻量 Agent 编排器：TASKS.md 任务队列 → per-task workspace → pi/claude 子进程 → 两种重试 | `pyyaml` |
| 🟢 代码 | `snippets/kway-merge-heap.rs` | K-way 外部归并排序（BinaryHeap min-heap）+ 相同 key 聚合，MapReduce Reduce 阶段模式 | 标准库 (Rust) |
| 🟢 代码 | `snippets/atomic-file-write.rs` | 原子文件写入：先写 tmp 再 rename，防止崩溃或并发导致脏文件 | 标准库 (Rust) |
| 🟡 模板 | `templates/WORKFLOW.md.template` | mini_symphony.py 的配置+Prompt 模板——复制后按项目修改 | — |
| 🟡 模板 | `templates/TASKS.md.example` | mini_symphony.py 的任务队列文件示例——Markdown checklist 格式 | — |
| 🔵 参考 | `analysis/simon-willison-agentic-patterns.md` | Simon Willison 7 个 Agentic Engineering 模式精读 | — |
| 🔵 参考 | `analysis/symphony-orchestration-spec.md` | OpenAI Symphony SPEC 精读：编排状态机、Workspace 隔离、App-Server 协议 | — |
| 🔵 参考 | `analysis/pi-context-engineering.md` | pi coding agent 精读：7 个 Context Engineering 决策 + system prompt + 工具定义原文 | — |
| 🔵 参考 | `ideas/yt-browse-local-first-channel-browser.md` | 本地优先内容浏览器模式：fetch-cache-search、Bubble Tea Elm TUI | — |

**类型说明**: 🟢 代码——可直接运行或导入 · 🟡 模板——复制后按需修改 · 🔵 参考——做设计决策时查阅

### 项目结构

```
CodeSnippets/
├── python/          # Python 相关片段
├── javascript/      # JavaScript / Node.js 相关片段
├── html-tools/      # 独立单页 HTML 工具
├── shell/           # Shell 脚本与命令行技巧
├── snippets/        # 通用 / 跨语言片段
├── templates/       # 配置文件与项目模板（复制即用）
├── ideas/           # 项目灵感与构思
├── analysis/        # 外部资料精读与参考文档
├── LICENSE          # MIT 许可证
└── README.md
```

### 使用方式

每个片段是独立文件，文件开头的注释块说明：

- **名称 / 用途**：解决什么问题
- **依赖**：需要安装什么
- **适用场景**：在哪些地方可以用
- **日期**：记录日期

```python
# =============================================================================
# 名称: <片段名称>
# 用途: <解决什么问题>
# 依赖: <pip install ...>
# 适用场景: <适用于什么场景>
# 日期: YYYY-MM-DD
# =============================================================================
```

### 许可证

[MIT](LICENSE) — Copyright (c) 2026 Hugh Lin
