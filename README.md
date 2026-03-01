# CodeSnippets

> A personal knowledge base for project ideas, code snippets, and implementation patterns.
>
> 记录项目灵感、代码片段和实现技巧的个人知识库。

---

## English

### Features

- Organized by language and topic — drop in a file and it's indexed
- Each snippet is self-documented with purpose, dependencies, and use cases
- `ideas/` directory for capturing raw inspiration with a structured template

### Snippet Catalog

| File | What it does | Dependencies |
|------|-------------|--------------|
| `python/snippet_manager.py` | CLI snippet manager with natural-language search; combines snippets into LLM prompts | `anthropic`, `rich` |
| `python/tape_context.py` | Anchor-based context assembly for multi-turn conversations (replaces history inheritance) | stdlib only |
| `python/zvec_inprocess_vector.py` | In-process vector DB demo — hybrid search (semantic + structured filtering) with zero services | `zvec`, `sentence-transformers` |
| `javascript/pdf_to_images.html` | Pure frontend PDF page renderer — converts each page to JPEG via PDF.js | PDF.js (CDN) |
| `javascript/browser_ocr.html` | Pure frontend OCR — Tesseract WebAssembly, supports English + Chinese | Tesseract.js (CDN) |
| `html-tools/pdf_ocr.html` | Complete browser-based PDF OCR tool — PDF rendering + text extraction, zero backend | PDF.js + Tesseract.js (CDN) |
| `python/fts5_fuzzy_search.py` | SQLite FTS5 three-layer fuzzy search: Porter stemming → trigram substring → Levenshtein correction | stdlib (sqlite3) |
| `python/sandbox_execute.py` | Isolated subprocess execution — only stdout enters context, with budget control | stdlib (subprocess) |

### Project Structure

```
CodeSnippets/
├── python/          # Python snippets
├── javascript/      # JavaScript / Node.js snippets
├── html-tools/      # Standalone single-page HTML tools
├── shell/           # Shell scripts & CLI tricks
├── snippets/        # Cross-language / general snippets
├── ideas/           # Raw project ideas (markdown)
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

### 功能特性

- 按语言和主题分目录管理，放入文件即归档
- 每个片段自带用途、依赖、适用场景等结构化注释
- `ideas/` 目录用于捕捉灵感，提供标准化模板

### 片段目录

| 文件 | 功能 | 依赖 |
|------|------|------|
| `python/snippet_manager.py` | CLI 片段管理器，支持自然语言搜索，可组合片段生成 LLM prompt | `anthropic`, `rich` |
| `python/tape_context.py` | 基于锚点的上下文装配，替代历史继承，适合群聊/多任务 Agent | 标准库 |
| `python/zvec_inprocess_vector.py` | in-process 向量库演示——混合检索（语义+结构化过滤），零服务依赖 | `zvec`, `sentence-transformers` |
| `javascript/pdf_to_images.html` | 纯前端 PDF 页面渲染——通过 PDF.js 将每页转为 JPEG | PDF.js (CDN) |
| `javascript/browser_ocr.html` | 纯前端 OCR——Tesseract WebAssembly，支持中英文 | Tesseract.js (CDN) |
| `html-tools/pdf_ocr.html` | 完整的浏览器端 PDF OCR 工具——PDF 渲染 + 文字提取，零后端 | PDF.js + Tesseract.js (CDN) |
| `python/fts5_fuzzy_search.py` | SQLite FTS5 三层模糊搜索：Porter 词干 → trigram 子串 → Levenshtein 纠错 | 标准库 (sqlite3) |
| `python/sandbox_execute.py` | 隔离子进程执行——只有 stdout 进入 context，带 budget 控制 | 标准库 (subprocess) |

### 项目结构

```
CodeSnippets/
├── python/          # Python 相关片段
├── javascript/      # JavaScript / Node.js 相关片段
├── html-tools/      # 独立单页 HTML 工具
├── shell/           # Shell 脚本与命令行技巧
├── snippets/        # 通用 / 跨语言片段
├── ideas/           # 项目灵感与构思
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
