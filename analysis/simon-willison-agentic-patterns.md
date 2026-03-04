# Simon Willison — Agentic Engineering Patterns 精读

**来源**:
- [Code is Cheap](https://simonwillison.net/guides/agentic-engineering-patterns/code-is-cheap/)
- [Red/Green TDD](https://simonwillison.net/guides/agentic-engineering-patterns/red-green-tdd/)
- [First Run the Tests](https://simonwillison.net/guides/agentic-engineering-patterns/first-run-the-tests/)
- [Linear Walkthroughs](https://simonwillison.net/guides/agentic-engineering-patterns/linear-walkthroughs/)
- [Interactive Explanations](https://simonwillison.net/guides/agentic-engineering-patterns/interactive-explanations/)
- [GIF Optimization](https://simonwillison.net/guides/agentic-engineering-patterns/gif-optimization/)
- [Prompts](https://simonwillison.net/guides/agentic-engineering-patterns/prompts/)

**日期**: 2026-03-04
**系列**: Simon Willison's Agentic Engineering Patterns Guide

---

## 模式总览

| 模式 | 核心思想 | 适用场景 |
|------|---------|---------|
| Code is Cheap | 编码成本已接近零，但"好代码"仍然有代价 | 工程文化、决策框架 |
| Red/Green TDD | 先写失败测试再实现，agent 遵循同样规则 | 新功能开发 |
| First Run the Tests | 每个 session 开始先跑测试，建立上下文 | 已有项目 / 维护工作 |
| Linear Walkthroughs | 让 agent 生成结构化代码讲解文档 | 读懂陌生/遗忘的代码库 |
| Interactive Explanations | 用动态可视化解释算法原理 | 理解复杂算法 / 消除认知债务 |
| GIF Optimization | 把 CLI 工具编译到 WASM，包成 Web 界面 | 构建无后端工具 |
| Prompts | 无 React Artifact 指令、校对 Prompt | 日常提示词工程 |

---

## 1. Code is Cheap — 编码便宜了，但好代码没有

### 核心论点

AI agent 把"打字写代码"的成本降低到接近零，但这摧毁的是**过去那套建立在"时间稀缺"上的工程直觉**：

- **宏观层面**：以前项目规划精细、功能评估谨慎，因为代码时间昂贵。现在异步 agent 可以并行实现 + 重构 + 测试 + 写文档，决策框架需要重建。
- **微观层面**：以前"重构这个函数值不值一小时？"、"写这个边界测试值不值？"——这些都是成本权衡问题。现在代价趋近于零，任何想法都值得 prompt 一下。

### 什么是"好代码"（依然昂贵）

> 好代码 = 能运行 + **我们知道它能运行**（有测试证明）+ 解决了正确问题 + 优雅处理错误 + 简单可维护 + 有回归测试 + 文档与代码同步 + 为未来变更留有余地 + 满足各种 "-ility"（可访问性、可测试性、可靠性、安全性……）

**关键洞察**：agent 可以帮助实现以上大部分，但驾驭 agent 的工程师仍然要承担确保"好代码"的责任。

### 新习惯框架

> 任何时候你的直觉说"别做那个，不值这时间"，就异步跑一个 agent——最坏情况是十分钟后回来发现真的不值那些 token。

---

## 2. Red/Green TDD — 红绿测试驱动开发

### 核心模式

TDD（测试驱动开发）与 agent 天然契合：
- **红（Red）阶段**：先写测试，确认测试失败
- **绿（Green）阶段**：迭代实现，直到测试通过

### 为什么 TDD + Agent 特别有效

1. **防止 agent 写了不被调用的代码**（测试强制验证代码路径）
2. **防止 agent 写出不工作的代码**（测试即时发现）
3. **建立回归测试套件**（随项目增长保护已有功能）
4. **跳过红阶段的风险**：测试可能已经通过，导致你以为实现了新功能，其实测试根本没覆盖到

### 四字提示词

```
Use red/green TDD
```

这四个词对任何主流模型来说都够用——它们已经知道这意味着"先写测试，确认失败，再实现，确认通过"。

---

## 3. First Run the Tests — 先跑一遍测试

### 核心做法

每次新开 agent session 时，第一件事就是让 agent 跑测试：

```
Run the tests
```

或者对于用 `uv` 管理的 Python 项目：

```
Run the tests using uv run pytest
```

### 为什么这四个字值那么多

1. **让 agent 主动发现测试套件**，而不是假设测试存在
2. **测试数量 ≈ 项目规模代理指标**，帮助 agent 评估复杂度
3. **建立测试心态**——跑过测试的 agent 后续更倾向于补充测试
4. **鼓励 agent 读测试文件来理解项目**，而不仅靠源码

与 [Hoard Things You Know How to Do](https://simonwillison.net/guides/agentic-engineering-patterns/hoard-things-you-know-how-to-do/) 模式结合：有测试套件的项目比没有的项目更容易被 agent 接手。

---

## 4. Linear Walkthroughs — 线性代码导读

### 使用场景

- 需要理解陌生代码库
- 自己写的代码忘了细节
- vibe coding 之后想搞清楚 agent 到底写了什么

### 核心工具：Showboat

[Showboat](https://github.com/simonw/showboat) 是专为 agent 设计的文档生成工具：
- `showboat note <markdown>` — 向文档追加 Markdown 内容
- `showboat exec <shell command>` — 执行命令，并把**命令 + 输出**都追加到文档

关键设计：让 agent 用 `sed`/`grep`/`cat` 来引用真实代码片段，而不是手动复制，**防止幻觉**。

### 提示词模板

```
Give me a linear walkthrough of how this codebase works.
Use showboat to document your walkthrough.
Use sed or grep or cat or whatever you need to include
snippets of code you are talking about.
```

### 效果

- 生成的文档是 Markdown，可以提交到 repo
- 结合代码片段，理解比单纯对话更扎实
- 借此机会学习陌生技术栈（Swift、Rust 等）

---

## 5. Interactive Explanations — 交互式解释

### 核心场景：消除"认知债务"

**认知债务（Cognitive Debt）**：agent 写了代码、代码可以工作，但你不懂它是怎么工作的。对于简单的 CRUD 这无所谓；对于核心算法，这会让你无法合理规划下一步。

### 解决路径

1. 先做 [Linear Walkthrough](#4-linear-walkthroughs----线性代码导读) 理解代码结构
2. 对仍然不直观的算法部分，让 agent 构建**动态可视化**

### 示例：Archimedean 螺旋放置算法

Simon 让 Claude Opus 4.6 构建了一个[词云动画解释](https://tools.simonwillison.net/animated-word-cloud)，通过动画展示词云的 Archimedean 螺旋放置算法：每个词尝试在螺旋路径上找位置，与已放置词不重叠则定位。

### 提示词模板

```
Build an animated explanation of [algorithm/mechanism] as a self-contained HTML page.
Reference [walkthrough.md or code file] for the implementation details.
Use canvas animations to show [specific step you want visualized].
```

**关键点**：
- Claude Opus 4.6 在构建解释性动画方面"品味不错"
- 把已有的 walkthrough.md 链接传入作为上下文，避免让 agent 重新读代码

---

## 6. GIF Optimization — GIF 优化工具（WASM 封装模式）

### 核心技术模式：CLI → WASM → Web UI

**工具**：[Gifsicle](https://github.com/kohler/gifsicle)（C 语言，30年历史）→ 用 [Emscripten](https://emscripten.org/) 编译到 WebAssembly → 包装成单页 HTML 工具

这是一个通用的模式：**把任何 CLI 工具编译到 WASM，配上 drag-drop web UI，变成零后端的浏览器工具。**

### 关键提示词结构分析

```
gif-optimizer.html
Compile gifsicle to WASM, then build a web page that lets you open or drag-drop
an animated GIF onto it and it then shows you that GIF compressed using gifsicle
with a number of different settings, each preview with the size and a download button
Also include controls for the gifsicle options for manual use - each preview has a
"tweak these settings" link which sets those manual settings to the ones used for
that preview so the user can customize them further
Run "uvx rodney --help" and use that tool to test your work - use this GIF for
testing https://static.simonwillison.net/static/2026/animated-word-cloud-demo.gif
```

拆解：
| 提示词片段 | 作用 |
|-----------|------|
| `gif-optimizer.html`（第一行文件名）| 告诉 agent 输出文件位置，它会自动扫描 repo 理解上下文 |
| `Compile gifsicle to WASM` | 隐式包含了 Emscripten 工具链的全部复杂度 |
| `drag-drop` | agent 知道这意味着 drag-and-drop JS 事件 + CSS dropzone |
| `download button` | agent 知道用 `<a download>` + blob URL 实现文件保存对话框 |
| `Run "uvx rodney --help"` | 给 agent 一个自测工具，指向它 --help，让它自学如何使用 |
| 提供测试 GIF URL | 确保 agent 用真实文件测试，而不只是静态代码审查 |

### Agent 自测的重要性

> 让 agent 能测试自己写的代码，是让它工作得更好的最重要手段之一。

工具选项：
- [Playwright](https://playwright.dev/) — 全功能浏览器自动化
- [Selenium](https://www.selenium.dev/) — 传统方案
- [agent-browser](https://agent-browser.dev/) — 专为 agent 设计
- [Rodney](https://github.com/simonw/rodney) — Simon 自建，`--help` 输出专为教会 agent 使用设计

### WASM 构建技巧

- Emscripten 编译复杂，需要大量 trial-and-error——agent 天生擅长暴力破解这类问题
- patch 文件 + build script 要一起提交到 repo（build script 克隆到 /tmp 再 apply patch）
- WASM 文件本身也要提交（如果通过静态托管部署）
- 开源软件要在页面上标注来源和许可证

---

## 7. Prompts — 可复用提示词

### Artifact 无 React 指令

Simon 不喜欢 React Artifacts（因为需要构建步骤，无法直接复制粘贴到静态托管），所以用 Claude Project 自定义指令强制使用纯 HTML + JS。

**关键思路**：在 Claude Project 的 custom instructions 里写一条"不要用 React，用原生 HTML + Vanilla JS"，所有后续对话自动遵守。

### 校对 Prompt

Simon 的硬性原则：表达观点或用"我"的文本必须是他亲自写的，不让 LLM 代写博客。但他用 LLM 做校对。

具体做法：在 Claude Project 的 custom instructions 里放校对 Prompt，形成固定的"人写 + AI 校对"工作流。

---

## 对 CodeSnippets 项目的应用建议

| 模式 | 可以立刻做的事 |
|------|--------------|
| Code is Cheap | 凡是"感觉不值得实现"的小工具，直接 prompt 一个 agent，成本几乎为零 |
| Red/Green TDD | 在 `snippets/` 里加一个 `agent-tdd-starter.md`，记录 TDD 提示词 |
| First Run the Tests | 每个 Python snippet 都加 `if __name__ == "__main__"` 的简单测试，方便 agent 感知项目 |
| Linear Walkthroughs | 用 showboat 给复杂 snippet 生成 walkthrough，存 `analysis/` |
| Interactive Explanations | 对 `python/fts5_fuzzy_search.py` 等算法 snippet，考虑做一个动态可视化 HTML |
| GIF Optimization / WASM 封装 | `html-tools/` 目录可以收录 WASM 包装类工具模板 |
| Prompts | 把常用 Project instructions（无 React / 校对）存 `snippets/claude-project-instructions.md` |

---

## 参考链接

- [Showboat](https://github.com/simonw/showboat) — agent 文档生成工具
- [Rodney](https://github.com/simonw/rodney) — agent 浏览器自测工具
- [Gifsicle](https://github.com/kohler/gifsicle) — GIF 优化 CLI
- [Emscripten](https://emscripten.org/) — C/C++ → WASM 工具链
- [tools.simonwillison.net](https://tools.simonwillison.net) — Simon 的单页工具集
- [Animated Word Cloud Demo](https://tools.simonwillison.net/animated-word-cloud) — 交互式算法解释示例
- [GIF Optimizer Tool](https://tools.simonwillison.net/gif-optimizer) — Gifsicle WASM 工具示例
- 相关已有文件：[ideas/agentic-hoarding-patterns.md](../ideas/agentic-hoarding-patterns.md)
