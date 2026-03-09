# "Hoard Things You Know How to Do" 精读

**来源**: [Hoard things you know how to do — Agentic Engineering Patterns](https://simonwillison.net/guides/agentic-engineering-patterns/hoard-things-you-know-how-to-do/)
**日期**: 2026-06-12
**标签**: agentic-engineering, knowledge-management, prompt-engineering, html-tools, coding-agents, recombination

---

## 30秒 TL;DR

> 软件工程师的核心资产是"**知道哪些事情可以做、大概怎么做**"——而不只是能写代码。把每一个你弄清楚的技巧（博文、GitHub repo、可运行的代码片段）囤积起来，形成可被 Coding Agent 检索和重组的"活弹药库"。Agent 时代之前，这个库让你比别人看到更多机会；Agent 时代之后，这个库让你的 Agent 只需要把现有方案拼在一起就能完成新任务，彻底消除了"先摸索再实现"的摩擦。

---

## 概念总览

| 概念/模式 | 核心思想 | 适用场景 |
|---------|---------|---------|
| **可能性感知（Possibility Awareness）** | 知道"X 能做到"与"知道怎么做 X"是两个不同层次，后者才是真正的资产 | 判断技术方向、识别机会 |
| **囤积体系（Hoarding System）** | 多层次的个人知识库：博客 TIL + GitHub 千余 repo + 单页 HTML 工具集 | 日常写作、实验记录 |
| **重组提示词（Recombination Prompt）** | 把两个现有可运行示例作为上下文，让 Agent 组合出新工具 | Agent 辅助构建 |
| **一次搞清 / 永久可用** | Agent 时代每个技巧只需弄清一次，存档后 Agent 可永远调取 | 知识复利最大化 |
| **公开即上下文** | 把自己的代码公开到 GitHub，这样就可以直接在 prompt 里引用 URL 或 clone 指令 | Agent 访问代码示例 |

---

## 深读

### 1. 什么是"囤积的东西"

Simon 的囤积体系分三层：

| 层级 | 形式 | 特点 |
|------|------|------|
| **文字记录** | [blog](https://simonwillison.net/) + [TIL blog](https://til.simonwillison.net/) | 带叙事的笔记，可被搜索引擎检索 |
| **代码仓库** | [1000+ GitHub repos](https://github.com/simonw)，大量小型 PoC | 可运行，有 commit 历史作为上下文 |
| **单页工具** | [tools.simonwillison.net](https://tools.simonwillison.net) | HTML+JS+CSS，可直接被 Agent fetch 原始代码 |

**关键观察**：这三层不是"存档"，而是**可消费的上下文输入源**——可以丢进 prompt，可以被 Agent curl，可以被 clone 到 /tmp。

### 2. 重组提示词的完整案例（PDF + OCR → 工具）

这是全文最有操作价值的部分：Simon 用 **两段现有代码 + 一段需求描述** 构建了 PDF OCR 工具。

```
原始资产 A: PDF.js 渲染 PDF 为图片（JS，~60行）
原始资产 B: Tesseract.js OCR 图片（JS，~20行）
需求描述: 拖拽 PDF → 每页转 JPEG 展示 → 每页下方显示 OCR 文本框
```

**Prompt 结构（这个结构可直接复用）**：
```
这段代码展示了如何做 A：
[代码片段 A]

这段代码展示了如何做 B：
[代码片段 B]

用这两个例子构建一个单页 HTML，实现：[具体需求]
```

结果：Claude 3 Opus 一次出结果，经少量迭代后就是生产级工具。

### 3. Agent 时代的升级：从"我记得"到"可检索"

在没有 Agent 之前，囤积的价值在于：**你在脑子里维护了一张可能性地图**，在碰到问题时能意识到"哦，我曾经见过类似的方案"。

有了 Coding Agent 之后，这个价值发生了质的变化：

```
旧：人脑检索 → 人手实现 （记忆 + 编码双成本）
新：Agent 检索 + Agent 实现 （你只需要维护检索入口）
```

Simon 举的三种 Agent 检索方式：

1. **直接提供 URL**（Agent 有 curl/WebFetch 能力）：
   ```
   Use curl to fetch https://tools.simonwillison.net/ocr and https://tools.simonwillison.net/gemini-bbox
   and build a new tool that...
   ```
   > 注：Simon 明确指定用 `curl` 而非 WebFetch，原因是 WebFetch 会摘要页面而非返回原始 HTML。

2. **指向本地路径**（Agent 在你的机器上跑）：
   ```
   Add mocked HTTP tests to ~/dev/ecosystem/datasette-oauth
   inspired by how ~/dev/ecosystem/llm-mistral is doing it.
   ```

3. **指令 clone 到 /tmp**（仓库在 GitHub 上）：
   ```
   Clone simonw/research from GitHub to /tmp and find examples of
   compiling Rust to WebAssembly, then use that to build...
   ```

### 4. "只需搞清一次"原则的深层含义

> *"The key idea here is that coding agents mean we only ever need to figure out a useful trick once."*

这一句话是整篇文章的核心命题，但它的含义比表面更深：

- **不只是"不用重复造轮子"**——那是 Stack Overflow 就已经做到的事
- **关键差异**：你的代码片段是**经过你验证、适配你的编码风格、已经在你的项目中跑通过的**；它不是 Stack Overflow 上一个陌生人说"这应该能用"的代码
- **第二层含义**：Agent 拿到经验证的代码，可以**用类比推理**而非从零重新探索；这让 Agent 的输出质量显著高于从空白开始

---

## 心智模型

> **"知识库 = 杠杆的支点"**：你的囤积体系不是存档，而是可以让 Agent 以 10x 速度落地任何想法的弹射台。代码片段的数量和质量直接决定了 Agent 能以多高的置信度完成你的需求。

**适用条件**：
- 你有定期记录/实验的习惯，且已经积累了一定体量的片段
- 你的片段是**可运行的代码**，而非伪代码或描述性文字
- 你的 Agent 能访问这些片段（URL、本地路径或 GitHub）

**失效条件**：
- 片段被锁在私有笔记/PDF/内网，Agent 无法访问
- 片段是过期代码，依赖已更新（特别是 JS 库版本不兼容）
- 囤积的是"读懂的代码"而非"自己跑通的代码"——前者不能作为可信的重组输入

---

## 非显见洞见

### 洞见 1：curl vs WebFetch——原始内容 vs 摘要的根本差异

- **洞见**：Simon 特别提示用 `curl` 而非 Agent 默认的 WebFetch，因为 WebFetch 会"摘要"而非返回原始 HTML
  - 所以：对于"需要让 Agent 读源码"的场景，所有摘要工具（Firecrawl、内置 browse 工具）都是有损的
  - 所以：你的工具代码放在公开 URL 上时，要保证 Agent 可以直接 curl 到原始内容，而不是被中间层处理
  - 因此可以：**把本知识库的代码片段托管为 raw GitHub URL**，在 prompt 里直接引用 `raw.githubusercontent.com/...`，确保 Agent 拿到的是无损代码

### 洞见 2：囤积体系的"可能性感知"价值不会被 AI 替代

- **洞见**：AI 可以帮你实现任何已知可能的事情，但**识别"这里可以用 X 技术"这个机会的能力**仍然来自人类的积累
  - 所以：会背答案的学生和能从题目描述里判断"这是一道递推题"的学生，AI 替代的是前者，保留的是后者
  - 所以：软件工程师的核心护城河从"写代码能力"迁移到了"技术可能性地图的广度与深度"
  - 因此可以：**刻意扩展自己的"知道能做"清单**，哪怕没有实现，只要有 PoC 代码/TIL 记录就算数

### 洞见 3：公开是一种基础设施

- **洞见**：Simon 把代码公开到 GitHub 不只是为了分享，而是让自己的 Agent 可以 `clone` 它
  - 所以：**私有仓库是对 Agent 不可用的知识**
  - 所以：对于个人工具/PoC，公开到 GitHub 是从"我知道怎么做"到"我的 Agent 也知道怎么做"的开关
  - 因此可以：本 CodeSnippets 库的 `html-tools/`、`snippets/` 如果能公开到 GitHub，就能被 Agent 直接引用，形成正反馈

### 洞见 4：重组 Prompt 的隐含假设——两段代码必须都"运行过"

- **洞见**：Simon 没有说"我看过 Tesseract.js 的文档"，他说"我曾经**用过**这个库，发现它很强"
  - 隐含假设：只有**经过自己运行验证**的代码才能作为重组 Prompt 的可信输入
  - 失效场景：如果你提供的是从 Stack Overflow 复制但未验证的代码，Agent 可能在错误的基础上构建
  - 因此可以：**本知识库的质量标准应是"必须跑通过的代码"，而非"看起来能用的代码"**

---

## 反模式与陷阱

- **陷阱 1："读懂了就等于囤积了"**
  读懂一篇教程 ≠ 拥有一个可用的代码示例。阅读是挥发性的，代码是持久性的。
  → 正确做法：每次学新东西，花 15 分钟跑一个最小可运行的 demo，保存到库里

- **陷阱 2："我的笔记只有我能搜索"**
  私有笔记对 Agent 是黑盒，无法被 prompt 引用。
  → 正确做法：代码类知识放到 Agent 可访问的地方（公开 GitHub、本地路径）；非代码知识可以保持私有

- **陷阱 3：使用 WebFetch（摘要型工具）读取源码**
  LLM 的 browse 工具默认摘要内容，对需要精确重组的源码来说是有损的。
  → 正确做法：明确指定 `curl` 或 `raw.githubusercontent.com` URL

- **陷阱 4："只积累自己熟悉方向的技巧"**
  囤积价值 = 广度 × 深度。只积累舒适区内的技巧，无法在跨领域问题上看到机会。
  → 正确做法：刻意探索自己不熟悉的领域（如：浏览器 API、Rust WASM、iOS Bluetooth），哪怕只是跑一个 PoC

---

## 与现有知识库的连接

- **关联 `html-tools/pdf_ocr.html`**：这正是 Simon 在文中描述的 PDF+OCR 重组工具的实物！本知识库已经有这个工具，说明"两段代码重组"这个模式在本库里已经成功实践过
- **关联 `javascript/pdf_to_images.html`** 和 **`javascript/browser_ocr.html`**：这是两个"原始资产"——正是构成重组 Prompt 的两个输入片段。Simon 案例在本库里有完整的对应关系
- **关联 `python/snippet_manager.py`**：这个 CLI 工具本身就是一个囤积体系的实现——自然语言搜索 + 组合成 LLM prompt，正是 Simon 描述的"把片段变为 Agent 可用上下文"的机制
- **关联 `analysis/simon-willison-agentic-patterns.md`**：原有精读中已有对 "Hoard Things" 的章节交叉引用（见该文 Section 3），本文是对该模式的独立深展
- **关联 `python/fts5_fuzzy_search.py`**：这类 snippet 是"可被搜索的囤积物"——要让它发挥价值，需要确保它在 Agent 可访问的路径下，且有完整的 header 注释

---

## 衍生项目想法

### 想法 1：Raw-URL 优先的 Snippet 检索协议

**来源组合**：[本次"curl vs WebFetch"洞见] + [已有 `python/snippet_manager.py` 的 LLM prompt 组合功能]

**为什么有意思**：
`snippet_manager.py` 目前输出的是文件内容（需要把整个文件贴进 prompt），但 Simon 的案例显示：如果代码托管在公开 URL 上，Agent 可以直接 curl，无需占用 context window。如果本知识库 push 到 GitHub，`snippet_manager.py` 可以输出 `raw.githubusercontent.com` URL 而非文件内容，Agent 可以按需 fetch，实现"懒加载"式的上下文引用——只有 Agent 真正需要的片段才进入 context，而非把所有候选片段一股脑贴进去。

**最小 spike**：
1. 给 `snippet_manager.py` 加一个 `--url-mode` 参数
2. 搜索结果输出 `raw.githubusercontent.com/...` URL（需要配置仓库基础 URL）
3. 构造测试 prompt：把 3 个 URL 交给 Claude，让它 curl 后完成一个组合任务
4. 对比：URL 引用 vs 直接贴内容，哪种方式输出质量更高、token 消耗更少
5. 预计完成时间：4小时

---

### 想法 2：Snippet 重组助手（Recombination Prompt Generator）

**来源组合**：[本次"重组 Prompt 结构模板"] + [已有 `python/snippet_manager.py` 的自然语言搜索功能]

**为什么有意思**：
Simon 的重组 Prompt 有一个固定结构："这段代码展示了 A → 这段代码展示了 B → 用这两段代码构建 C"。目前 `snippet_manager.py` 支持搜索和组合，但没有"针对重组任务生成 prompt 模板"的功能。如果加上这个功能，用户输入"我要把 PDF 渲染和 OCR 结合"，系统自动：①搜索最相关的 2-3 个 snippet，②生成标准化重组 Prompt，③可选地把 prompt 发送给 Agent 直接执行。这把"知道两段代码存在" + "知道如何写重组 prompt"合二为一。

**最小 spike**：
1. 在 `snippet_manager.py` 加 `--recombine "需求描述"` 子命令
2. 搜索 top-2 相关 snippet，用固定模板生成：`这段代码展示了如何做 A:\n[snippet A]\n\n这段代码展示了如何做 B:\n[snippet B]\n\n用这两个例子构建：{需求描述}`
3. 输出到 stdout 或直接调用 Anthropic API
4. 预计完成时间：3小时

---

### 想法 3：TIL 自动归档 Pipeline（本知识库 → TIL 博客格式）

**来源组合**：[本次"博客 TIL 是囤积体系的一层"] + [已有 `analysis/` 目录的精读文档体系]

**为什么有意思**：
Simon 的 TIL 博客和本知识库做的是同一件事，但 Simon 的 TIL 是公开可检索的（搜索引擎 + Agent curl）。本知识库目前是私有的，囤积的知识对 Agent 不可见。一个最小的"公开化 pipeline"可以：在每次归档完成后，把 analysis 文档的 TL;DR + 非显见洞见部分提取为 TIL 格式，push 到一个公开的 `til.yourdomain.com` 或 GitHub Pages。这样就把私有积累转化为公开可检索的 Agent 上下文资源。

**最小 spike**：
1. 写一个脚本：读取任意 analysis/*.md，提取"30秒 TL;DR"和"非显见洞见"部分
2. 生成 TIL 格式 Markdown（标题 + 简短正文 + 原始来源链接）
3. push 到一个 GitHub Pages 仓库（零成本托管）
4. 验证：Agent 能否 curl 到这些 URL 并正确读取内容
5. 预计完成时间：半天
