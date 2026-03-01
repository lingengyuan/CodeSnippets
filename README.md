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

### Project Structure

```
CodeSnippets/
├── python/          # Python snippets
├── javascript/      # JavaScript / Node.js snippets
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

### 项目结构

```
CodeSnippets/
├── python/          # Python 相关片段
├── javascript/      # JavaScript / Node.js 相关片段
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
