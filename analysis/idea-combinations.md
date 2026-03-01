# 现有素材交叉组合分析

**日期**: 2026-03-01

## 当前库存盘点

| 编号 | 素材 | 核心能力 |
|------|------|---------|
| A | snippet_manager | 片段存储 + 自然语言搜索 + prompt 组合 |
| B | tape_context | 锚点上下文管理，按需装配，不继承历史 |
| C | zvec | in-process 向量库，混合检索，零服务 |
| D | PDF.js + Tesseract.js | 纯前端 PDF 渲染 + OCR |
| E | Agentic Hoarding 模式 | agent 读已有代码 → 组合出新工具 |

---

## 组合一：A + C → 语义 Snippet Manager

**把 snippet_manager 的搜索从字符串匹配升级为向量检索。**

现在 `search()` 只做 `query.lower() in name`，本质是 grep。接上 zvec 之后：

- 每个 snippet 入库时自动 embed（代码 + 描述），存入 zvec
- 搜索 `"怎么做并发"` 能命中 `asyncio_pool.py`，即使名字和描述里没有"并发"二字
- 结构化过滤：`search("并发", tags=["python"], score>80)`
- `combine_prompt()` 变成：描述目标 → 语义检索最相关的 N 个片段 → 自动组合 prompt

**一句话**：CodeSnippets 本身就变成一个语义可检索的 agent 工具库。

**实现量**：约 50 行，把 zvec 嵌进 snippet_manager 的 `load/save/search`。

---

## 组合二：B + C → 有记忆的 Agent 框架

**Tape 管理对话流，zvec 管理长期记忆。**

Tape 的锚点解决了"当前任务上下文"，但锚点之前的历史就丢了。加上 zvec：

- 每个锚点的 summary 自动 embed，存入 zvec
- 新任务开始时，用任务描述在 zvec 里检索相关的历史锚点
- 装配上下文 = 最近锚点 + 语义相关的远期锚点 + 当前消息

**效果**：Agent 不仅记得"刚才在做什么"，还能想起"三个月前做过类似的事"。

**场景**：
- 代码助手：你让它改 auth 模块，它自动想起上次改 auth 时踩的坑
- 客服 Agent：新工单进来，自动关联这个用户历史上相似的问题
- 游戏 NPC："你上次来的时候帮我打了狼"——从向量库捞出来的

**实现量**：在 Tape 类里加一个 `zvec_store`，`anchor()` 时同步写入，`assemble_context()` 时多查一步。

---

## 组合三：D + C → 扫描件全文检索

**PDF OCR 提取文字 → zvec 向量化 → 语义搜索扫描件内容。**

现在 pdf_ocr.html 只是提取文字然后显示。加上 zvec 后端：

- 前端：PDF → OCR → 文字（已有）
- 后端（Python）：接收 OCR 文字 → chunk → embed → 存入 zvec
- 查询：`"2023年Q3的营收数据"` → 直接命中某份扫描版财报的第 7 页

**场景**：律师事务所的合同库、会计事务所的历史报表、医院的病历档案。

**变体**：纯离线版——Python 脚本用 `pymupdf` 替代 PDF.js，Tesseract CLI 替代 Tesseract.js，全程不需要浏览器。

---

## 组合四：E + A → 自进化 Snippet 库

**用 Simon 的 Agentic Hoarding 模式，让 agent 自动给你的片段库添加新片段。**

流程：
1. 你解决了一个问题（写了一段代码、调通了一个 API）
2. Git hook 或 CI 触发 agent
3. Agent 读你的 diff，判断是否值得沉淀为 snippet
4. 值得 → 自动提取、补上标准头部注释、归入对应目录、更新 README 目录表

**更进一步**：agent 定期扫描你的所有 GitHub 仓库，把散落在各处的有价值代码片段自动收割回 CodeSnippets。

**一句话**：不是你维护片段库，是片段库自己生长。

---

## 组合五：B + D + E → Agent 驱动的文档处理管线

**Tape 管理多步任务流，OCR 做输入，Agent 模式做编排。**

场景：批量处理一堆扫描件合同

```
Tape 纸带:
  [anchor] 已 OCR 完 20 份合同，提取了关键条款
  [message] 用户：帮我找所有违约金超过 100 万的合同
  [message] agent：在 zvec 中检索到 3 份，分别是...
  [anchor] 完成违约金筛选，3 份命中
  [message] 用户：把这 3 份的关键条款做个对比表
```

每一步都有锚点，崩溃了从锚点续跑，不需要重新 OCR。

---

## 组合六：全部 → CodeSnippets 变成 MCP Server

**把整个 CodeSnippets 仓库暴露为一个 MCP (Model Context Protocol) server。**

Agent（Claude Code / Cursor / 任何 MCP 客户端）可以直接调用：

| MCP Tool | 功能 | 用到的素材 |
|----------|------|-----------|
| `search_snippets` | 语义搜索片段 | A + C |
| `get_snippet` | 获取完整代码 | A |
| `combine_for_task` | 描述任务 → 自动组合最相关片段为 prompt | A + C + E |
| `ocr_pdf` | 传入 PDF → 返回 OCR 文字 | D |
| `recall_context` | 传入任务描述 → 返回历史相关锚点 | B + C |

**一句话**：你的代码片段库变成 agent 的工具箱，任何 agent 都能在需要时翻你的"经验"。

这是所有组合的终极形态——CodeSnippets 不再是被动的笔记本，而是 agent 生态中的一个主动参与者。

---

## 优先级排序

| 组合 | 投入 | 杠杆 | 建议 |
|------|------|------|------|
| A+C 语义 Snippet Manager | ~50 行 | 立刻提升搜索体验 | **先做** |
| E+A 自进化片段库 | Git hook + agent prompt | 一劳永逸 | **第二** |
| B+C 有记忆的 Agent | ~100 行 | 通用框架，复用性最高 | 第三 |
| 全部 → MCP Server | 中等 | 终极形态 | 积累够了再做 |
| D+C 扫描件检索 | 需要后端 | 垂直场景 | 按需 |
| B+D+E 文档管线 | 较大 | 太重，等场景驱动 | 最后 |
