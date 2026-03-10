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
| 🟢 code | `python/session_tracker.py` | Agent session continuity: SQLite event capture → priority snapshot (≤2 KB) → FTS5 restore after compaction | stdlib only |
| 🟢 code | `snippets/kway-merge-heap.rs` | K-way external merge sort using BinaryHeap as min-heap; groups identical keys (MapReduce Reduce phase) | stdlib (Rust) |
| 🟢 code | `snippets/atomic-file-write.rs` | Atomic file write via tmp → rename; prevents partial-write corruption | stdlib (Rust) |
| 🟡 template | `templates/WORKFLOW.md.template` | Config + prompt template for mini_symphony.py — copy and customize per project | — |
| 🟡 template | `templates/TASKS.md.example` | Task queue file example for mini_symphony.py — markdown checklist format | — |
| 🔵 reference | `analysis/simon-willison-agentic-patterns.md` | Deep-read of 7 agentic engineering patterns by Simon Willison | — |
| 🔵 reference | `analysis/simon-willison-hoard-things.md` | Deep-read: "Hoard Things You Know How to Do" — recombination prompts, hoarding system design, Agent-era knowledge leverage | — |
| 🔵 reference | `analysis/simon-willison-code-is-cheap.md` | Deep-read: "Writing Code is Cheap Now" — cost model inversion, 4 non-obvious insights + implication chains, 5 anti-patterns, 3 derived ideas | — |
| 🔵 reference | `analysis/simon-willison-red-green-tdd.md` | Deep-read: "Red/Green TDD for Coding Agents" — 4 non-obvious insights + implication chains, test-gate orchestration pattern, prompt compression cheatsheet idea | — |
| 🔵 reference | `analysis/symphony-orchestration-spec.md` | Deep-read of OpenAI Symphony SPEC: orchestration FSM, workspace isolation, app-server protocol | — |
| 🔵 reference | `analysis/pi-context-engineering.md` | Deep-read of pi coding agent: 7 context engineering decisions + verbatim system prompt + tool defs | — |
| 🔵 reference | `analysis/simon-willison-llm-026-tools.md` | Deep-read of Simon Willison's LLM 0.26 tool-use release: CLI flags, plugin system, Python API, ReAct loop, MCP roadmap | — |
| 🔵 reference | `analysis/context-mode-mcp-context-saving.md` | Deep-read of Context Mode: MCP output sandbox (315 KB → 5.4 KB, 98% reduction), session continuity via SQLite+FTS5, dual-layer routing enforcement, 5 non-obvious insights | — |
| 🔵 reference | `ideas/yt-browse-local-first-channel-browser.md` | Local-first channel browser patterns: fetch-cache-search, Bubble Tea Elm TUI | — |
| 🔵 reference | `ideas/frontend-slides-skill-design.md` | frontend-slides skill: progressive disclosure, show-dont-tell style selection, viewport fitting rules, 12 style presets | — |
| 🔵 reference | `ideas/context-mode-session-continuity-pattern.md` | Agent session continuity pattern: PreCompact snapshot + FTS5 restore, 4-hook architecture, priority-tiered XML (≤2 KB), 15-category Session Guide | — |
| 🟢 code | `snippets/css-reveal-animations.css` | CSS entrance animations (fade-slide, scale, blur, stagger), viewport slide rules, bg patterns | none |
| 🟢 code | `python/insight_agent.py` | Standalone URL→CodeSnippets archiving agent — direct Anthropic SDK call, usable as CLI or mini_symphony subcommand | `anthropic`, `requests` |
| 🟢 code | `snippets/emscripten-wasm-build-template.sh` | Emscripten WASM build script template — patch + build script pattern (no source in repo), reusable for any C/C++ CLI → browser tool | `emcc` (emsdk) |
| 🟢 code | `snippets/mapreduce-engine.rs` | Rust MapReduce engine — Master/Worker mpsc scheduling, K-way merge BinaryHeap, speculative execution, atomic writes (stdlib only) | stdlib (Rust) |
| 🟡 template | `snippets/interactive-explanation-prompt.md` | Interactive Explanation prompt template — generates visual HTML animation for hard-to-intuit algorithms; includes Showboat usage | — |
| 🔵 reference | `analysis/simon-willison-anti-patterns.md` | Deep-read: Agentic Engineering Anti-patterns — PR validation ethics, unreviewed code as value-transfer, 3 non-obvious insights + implication chains | — |
| 🔵 reference | `analysis/simon-willison-first-run-tests.md` | Deep-read: "First Run the Tests" — 3-in-1 signal (capability probe + scale calibration + mindset injection), symmetry with Red/Green TDD, test-gate orchestration | — |
| 🔵 reference | `analysis/simon-willison-interactive-explanations.md` | Deep-read: Interactive Explanations & Cognitive Debt — two-phase debt reduction (linear walkthrough → interactive animation), 4 non-obvious insights + implication chains | — |
| 🔵 reference | `analysis/simon-willison-linear-walkthroughs-manual-testing.md` | Deep-read: Linear Walkthroughs + Agentic Manual Testing + Showboat — cognitive debt 3-tier system, exec anti-cheating design, verification-as-artifact pattern | — |
| 🔵 reference | `analysis/simon-willison-wasm-browser-tool-pattern.md` | Deep-read: WASM Browser Tool Pattern (GIF Optimization) — CLI→WASM→zero-backend HTML, agent Emscripten brute-force, Rodney self-test close-loop | — |
| 🔵 reference | `analysis/rust-mapreduce-architecture.md` | Deep-read: Rust MapReduce single-machine impl — Master/Worker FSM, K-way merge, speculative execution, 7 honest deviation statements | — |
| 🔵 reference | `ideas/wasm-cli-tool-wrapper-factory.md` | WASM CLI Tool Wrapper Factory — any C/C++ CLI tool → drag-drop zero-backend HTML tool via agent Emscripten brute-force | — |
| 🔵 reference | `analysis/karpathy-autoresearch.md` | Deep-read: karpathy/autoresearch — git-ratchet autonomous ML experimentation, program.md as two-level optimization, NEVER STOP design, 4 non-obvious insights + implication chains | — |
| 🔵 reference | `analysis/design-plugin-claude-code.md` | Deep-read: 0xdesign/design-plugin — visual style inference from codebase, FeedbackOverlay CSS selector mechanism, DESIGN_MEMORY accumulation pattern, 4 non-obvious insights | — |
| 🔵 reference | `analysis/karpathy-nanochat.md` | Deep-read: karpathy/nanochat — single-dial GPT training ($48 GPT-2), x0 residual, Muon+AdamW param grouping, explicit COMPUTE_DTYPE, SSSL window, softcap logits, parallel data download | — |
| 🔵 reference | `analysis/ruff-python-linter.md` | Ruff linter/formatter reference: migration strategy (--add-noqa), RUF100 debt tracking, B006/B023 bug-catching rules, CI exit code gotcha, monorepo config inheritance | — |
| 🟡 template | `templates/ruff.toml.template` | Production ruff config: E/F/B/I/UP/RUF rules, per-file-ignores, formatter settings, migration & CI commands | — |

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
# 适用场景: <Where to apply it>
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
| 🟢 代码 | `python/session_tracker.py` | Agent 会话持续性：SQLite 事件捕获 → 优先级快照（≤2 KB）→ Compaction 后 FTS5 恢复 | 标准库 |
| 🟢 代码 | `snippets/kway-merge-heap.rs` | K-way 外部归并排序（BinaryHeap min-heap）+ 相同 key 聚合，MapReduce Reduce 阶段模式 | 标准库 (Rust) |
| 🟢 代码 | `snippets/atomic-file-write.rs` | 原子文件写入：先写 tmp 再 rename，防止崩溃或并发导致脏文件 | 标准库 (Rust) |
| 🟡 模板 | `templates/WORKFLOW.md.template` | mini_symphony.py 的配置+Prompt 模板——复制后按项目修改 | — |
| 🟡 模板 | `templates/TASKS.md.example` | mini_symphony.py 的任务队列文件示例——Markdown checklist 格式 | — |
| 🔵 参考 | `analysis/simon-willison-agentic-patterns.md` | Simon Willison 7 个 Agentic Engineering 模式精读 | — |
| 🔵 参考 | `analysis/simon-willison-hoard-things.md` | 精读："囤积你知道如何做的事"——重组 Prompt 模板、囤积体系设计、Agent 时代知识复利的核心论证 | — |
| 🔵 参考 | `analysis/simon-willison-code-is-cheap.md` | 精读："代码现在很便宜"——成本模型反转、4条非显见洞见+蕴含链、5个反模式、隐含假设矩阵、3个衍生想法 | — |
| 🔵 参考 | `analysis/simon-willison-red-green-tdd.md` | 精读："Agent 时代的 Red/Green TDD"——4条非显见洞见+蕴含链、测试门控编排模式、Prompt压缩词典想法 | — |
| 🔵 参考 | `analysis/symphony-orchestration-spec.md` | OpenAI Symphony SPEC 精读：编排状态机、Workspace 隔离、App-Server 协议 | — |
| 🔵 参考 | `analysis/pi-context-engineering.md` | pi coding agent 精读：7 个 Context Engineering 决策 + system prompt + 工具定义原文 | — |
| 🔵 参考 | `analysis/simon-willison-llm-026-tools.md` | Simon Willison LLM 0.26 工具调用发布精读：CLI 用法、插件体系、Python API、ReAct 循环、MCP 路线图 | — |
| 🔵 参考 | `analysis/context-mode-mcp-context-saving.md` | Context Mode 精读：MCP 输出沙箱（315 KB→5.4 KB，98%压缩）、SQLite+FTS5 会话持续性、双层路由强制、5条非显见洞见+蕴含链 | — |
| 🔵 参考 | `ideas/yt-browse-local-first-channel-browser.md` | 本地优先内容浏览器模式：fetch-cache-search、Bubble Tea Elm TUI | — |
| 🔵 参考 | `ideas/frontend-slides-skill-design.md` | frontend-slides skill 架构分析：渐进式披露、Show Don't Tell 风格选择、Viewport 适配规则、12 种风格速查 | — |
| 🔵 参考 | `ideas/context-mode-session-continuity-pattern.md` | Agent 会话持续性模式：PreCompact 快照+FTS5 恢复、四钩架构、优先级 XML（≤2 KB）、15 分类 Session Guide | — |
| 🟢 代码 | `snippets/css-reveal-animations.css` | CSS 入场动画集合（淡入上移、缩放、模糊、错开延迟）+ 幻灯片 Viewport 规则 + 背景效果 | 无 |
| 🟢 代码 | `python/insight_agent.py` | 独立的 URL→CodeSnippets 归档 Agent——直接调用 Anthropic SDK，可作为 CLI 或 mini_symphony 子命令使用 | `anthropic`, `requests` |
| 🟢 代码 | `snippets/emscripten-wasm-build-template.sh` | Emscripten WASM 构建脚本模板——patch+build script 模式（不放源码只放补丁），可复用于任意 C/C++ CLI→浏览器工具 | `emcc` (emsdk) |
| 🟢 代码 | `snippets/mapreduce-engine.rs` | Rust MapReduce 引擎——Master/Worker mpsc 调度、K-way 归并 BinaryHeap、推测执行、原子写入（仅标准库） | 标准库 (Rust) |
| 🟡 模板 | `snippets/interactive-explanation-prompt.md` | 交互式解释 Prompt 模板——为难以直觉理解的算法生成可视化 HTML 动画；含 Showboat 用法 | — |
| 🔵 参考 | `analysis/simon-willison-anti-patterns.md` | 精读："Agentic Engineering 反模式"——PR 验证伦理、未审查代码作为价值转嫁、3条非显见洞见+蕴含链 | — |
| 🔵 参考 | `analysis/simon-willison-first-run-tests.md` | 精读："First Run the Tests"——三合一信号（能力探测+规模校准+心态注入）、与 Red/Green TDD 的测试门控对称、编排应用 | — |
| 🔵 参考 | `analysis/simon-willison-interactive-explanations.md` | 精读：交互式解释 & 认知债务——两阶段还债路径（线性导读→交互动画）、4条非显见洞见+蕴含链 | — |
| 🔵 参考 | `analysis/simon-willison-linear-walkthroughs-manual-testing.md` | 精读：线性导读 + Agent 手动测试 + Showboat——认知债务三级体系、exec 防作弊设计、验证即产物模式 | — |
| 🔵 参考 | `analysis/simon-willison-wasm-browser-tool-pattern.md` | 精读：WASM 浏览器工具模式（GIF 优化）——CLI→WASM→零后端 HTML、Agent Emscripten 暴力编译、Rodney 自测闭环 | — |
| 🔵 参考 | `analysis/rust-mapreduce-architecture.md` | 精读：Rust MapReduce 单机实现——Master/Worker FSM、K-way 归并、推测执行、7条诚实偏差声明 | — |
| 🔵 参考 | `ideas/wasm-cli-tool-wrapper-factory.md` | WASM CLI 工具封装工厂——任意 C/C++ CLI 工具→拖放式零后端 HTML 工具，Agent 暴力 Emscripten 编译 | — |
| 🔵 参考 | `analysis/karpathy-autoresearch.md` | karpathy/autoresearch 精读：Git 棘轮自主 ML 实验、program.md 两级优化解耦、NEVER STOP 设计、4条非显见洞见+蕴含链 | — |
| 🔵 参考 | `analysis/design-plugin-claude-code.md` | design-plugin 精读：从代码库推断视觉语言、FeedbackOverlay CSS selector 坐标系、DESIGN_MEMORY 跨会话积累、4条非显见洞见+蕴含链 | — |
| 🔵 参考 | `analysis/karpathy-nanochat.md` | nanochat 精读：单拨盘 GPT 训练（$48 GPT-2）、x0 残差、Muon+AdamW 参数分组、显式 COMPUTE_DTYPE、SSSL 滑窗、softcap 逻辑值、并行数据下载 | — |
| 🔵 参考 | `analysis/ruff-python-linter.md` | Ruff linter/formatter 精读：--add-noqa 迁移策略、RUF100 技术债追踪、B006/B023 真正捉虫的规则、CI 退出码陷阱、monorepo 配置继承 | — |
| 🟡 模板 | `templates/ruff.toml.template` | 生产级 ruff 配置：E/F/B/I/UP/RUF 规则、per-file-ignores、formatter 设置、迁移命令和 CI 命令 | — |

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
