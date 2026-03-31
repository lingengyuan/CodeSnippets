# CodeSnippets

> A personal knowledge base for project ideas, code snippets, and implementation patterns.
>
> 记录项目灵感、代码片段和实现技巧的个人知识库。

---

## English

### Features

- **17 runnable code snippets** — Python, Rust, TypeScript, HTML/JS tools, ready to import or execute
- **29 deep-read analyses** — distilled insights from expert articles, open-source projects, and papers
- **11 idea documents** — project directions with real-time market verification status
- **5 reusable templates** — orchestrator configs, prompt templates, linter presets, agent doc architecture

### Catalog

#### 🟢 Code — run or import directly

| File | What it does | Dependencies |
|------|-------------|--------------|
| `python/snippet_manager.py` | CLI snippet manager with natural-language search; combines snippets into LLM prompts | `anthropic`, `rich` |
| `python/tape_context.py` | Anchor-based context assembly for multi-turn conversations (replaces history inheritance) | stdlib only |
| `python/zvec_inprocess_vector.py` | In-process vector DB demo — hybrid search (semantic + structured filtering) with zero services | `zvec`, `sentence-transformers` |
| `python/fts5_fuzzy_search.py` | SQLite FTS5 three-layer fuzzy search: Porter stemming → trigram substring → Levenshtein correction | stdlib (sqlite3) |
| `python/sandbox_execute.py` | Isolated subprocess execution — only stdout enters context, with budget control | stdlib (subprocess) |
| `python/mini_symphony.py` | Lightweight agent orchestrator: TASKS.md task queue → per-task workspace → pi/claude subprocess → two-tier retry | `pyyaml` |
| `python/session_tracker.py` | Agent session continuity: SQLite event capture → priority snapshot (≤2 KB) → FTS5 restore after compaction | stdlib only |
| `python/insight_agent.py` | Standalone URL→CodeSnippets archiving agent — direct Anthropic SDK call, usable as CLI or mini_symphony subcommand | `anthropic`, `requests` |
| `javascript/pdf_to_images.html` | Pure frontend PDF page renderer — converts each page to JPEG via PDF.js | PDF.js (CDN) |
| `javascript/browser_ocr.html` | Pure frontend OCR — Tesseract WebAssembly, supports English + Chinese | Tesseract.js (CDN) |
| `html-tools/pdf_ocr.html` | Complete browser-based PDF OCR tool — PDF rendering + text extraction, zero backend | PDF.js + Tesseract.js (CDN) |
| `snippets/kway-merge-heap.rs` | K-way external merge sort using BinaryHeap as min-heap; groups identical keys (MapReduce Reduce phase) | stdlib (Rust) |
| `snippets/atomic-file-write.rs` | Atomic file write via tmp → rename; prevents partial-write corruption | stdlib (Rust) |
| `snippets/mapreduce-engine.rs` | Rust MapReduce engine — Master/Worker mpsc scheduling, K-way merge BinaryHeap, speculative execution, atomic writes | stdlib (Rust) |
| `snippets/async-message-queue.ts` | TypeScript async message queue — push-to-pull adapter for WebSocket/SDK streaming via AsyncIterator | TypeScript stdlib |
| `snippets/css-reveal-animations.css` | CSS entrance animations (fade-slide, scale, blur, stagger), viewport slide rules, bg patterns | none |
| `snippets/emscripten-wasm-build-template.sh` | Emscripten WASM build script template — patch + build script pattern, reusable for any C/C++ CLI → browser tool | `emcc` (emsdk) |

#### 🟡 Templates — copy and customize

| File | What it does | Dependencies |
|------|-------------|--------------|
| `templates/WORKFLOW.md.template` | Config + prompt template for mini_symphony.py — copy and customize per project | — |
| `templates/TASKS.md.example` | Task queue file example for mini_symphony.py — markdown checklist format | — |
| `templates/ruff.toml.template` | Production ruff config: E/F/B/I/UP/RUF rules, per-file-ignores, formatter settings, migration & CI commands | — |
| `snippets/interactive-explanation-prompt.md` | Interactive Explanation prompt template — generates visual HTML animation for hard-to-intuit algorithms | — |
| `templates/agents-md-template.md` | 5-layer agent doc architecture template (README→DEVELOPMENT→STATUS→RESEARCH→AGENTS), extracted from chenglou/pretext | — |

#### 🔵 Reference — read when making design decisions

**Deep-reads (analysis/)**

| File | What it covers |
|------|---------------|
| `analysis/simon-willison-agentic-patterns.md` | 7 agentic engineering patterns by Simon Willison |
| `analysis/simon-willison-hoard-things.md` | "Hoard Things You Know How to Do" — recombination prompts, hoarding system design, Agent-era knowledge leverage |
| `analysis/simon-willison-code-is-cheap.md` | "Writing Code is Cheap Now" — cost model inversion, 4 non-obvious insights, 5 anti-patterns, 3 derived ideas |
| `analysis/simon-willison-red-green-tdd.md` | "Red/Green TDD for Coding Agents" — 4 non-obvious insights, test-gate orchestration pattern |
| `analysis/simon-willison-anti-patterns.md` | "Agentic Engineering Anti-patterns" — PR validation ethics, unreviewed code as value-transfer |
| `analysis/simon-willison-first-run-tests.md` | "First Run the Tests" — 3-in-1 signal (capability probe + scale calibration + mindset injection) |
| `analysis/simon-willison-interactive-explanations.md` | Interactive Explanations and Cognitive Debt — two-phase debt reduction (linear walkthrough → interactive animation) |
| `analysis/simon-willison-linear-walkthroughs-manual-testing.md` | Linear Walkthroughs + Agentic Manual Testing + Showboat — cognitive debt 3-tier system |
| `analysis/simon-willison-wasm-browser-tool-pattern.md` | WASM Browser Tool Pattern (GIF Optimization) — CLI→WASM→zero-backend HTML, agent Emscripten brute-force |
| `analysis/simon-willison-llm-026-tools.md` | LLM 0.26 tool-use release: CLI flags, plugin system, Python API, ReAct loop, MCP roadmap |
| `analysis/symphony-orchestration-spec.md` | OpenAI Symphony SPEC: orchestration FSM, workspace isolation, app-server protocol |
| `analysis/pi-context-engineering.md` | pi coding agent: 7 context engineering decisions + verbatim system prompt + tool defs |
| `analysis/context-mode-mcp-context-saving.md` | Context Mode: MCP output sandbox (315 KB → 5.4 KB, 98% reduction), session continuity via SQLite+FTS5 |
| `analysis/rust-mapreduce-architecture.md` | Rust MapReduce single-machine impl — Master/Worker FSM, K-way merge, speculative execution |
| `analysis/karpathy-autoresearch.md` | karpathy/autoresearch — git-ratchet autonomous ML experimentation, program.md two-level optimization |
| `analysis/karpathy-nanochat.md` | nanochat — single-dial GPT training, x0 residual, Muon+AdamW param grouping |
| `analysis/design-plugin-claude-code.md` | 0xdesign/design-plugin — visual style inference from codebase, FeedbackOverlay CSS selector mechanism |
| `analysis/ruff-python-linter.md` | Ruff linter/formatter: migration strategy (--add-noqa), RUF100 debt tracking, B006/B023 rules |
| `analysis/claude-agent-sdk-demos.md` | Claude Agent SDK Demos: AgentDefinition patterns, tool routing, multi-agent TypeScript/Python examples |
| `analysis/docflow-local-rag-assistant.md` | DocFlow local PDF RAG assistant: Phase 6 architecture, Qdrant+Ollama pipeline, PDF chunking |
| `analysis/pegainfer-qwen35-prefill-optimization.md` | pegainfer Qwen3.5-4B prefill: TTFT 16.8s→235ms, CUDA/Triton kernel analysis, gated-delta-rule |
| `analysis/qjl-mlx-turboquant-apple-silicon.md` | QJL-MLX TurboQuant: PolarQuant+QJL on Apple Silicon MLX, KV-cache quantization |
| `analysis/idea-combinations.md` | Cross-idea combination analysis: 5 idea pairs priority-ranked from existing KB entries |
| `analysis/directions-synthesis.md` | Global direction synthesis v1: consolidated priorities from all ideas and analyses |
| `analysis/directions-synthesis-v2.md` | Global direction synthesis v2: updated with pi-context, symphony, yt-browse, MapReduce inputs |
| `analysis/chenglou-pretext-text-layout.md` | Pretext: pure JS multiline text measurement & layout — two-phase prepare/layout, canvas-based, multi-script |
| `analysis/microsoft-vibevoice-voice-ai.md` | VibeVoice: Microsoft's open-source Voice AI family — 7.5Hz tokenizer (3200× compression), next-token diffusion, ASR/TTS/Realtime |
| `analysis/claude-code-ai-reimplementation-ethics.md` | AI reimplementation & copyleft erosion: "legal ≠ legitimate" direction vector, chardet case, specification copyleft, ethical porting |
| `analysis/claude-code-architecture-patterns.md` | Claude Code architecture: 10 transferable patterns from 512K LOC — buildTool() factory, async generator loop, 5-phase startup, 3-layer permissions, Worker isolation |

**Ideas and directions (ideas/)**

| File | What it covers | Status |
|------|---------------|--------|
| `ideas/agentic-hoarding-patterns.md` | Agentic hoarding patterns: agent reads existing code to compose new tools | 💡 |
| `ideas/context-mode-patterns.md` | Context Mode compression: sandbox + stdout filtering for agent context | 💡 |
| `ideas/context-mode-session-continuity-pattern.md` | Agent session continuity: PreCompact snapshot + FTS5 restore, 4-hook architecture | 💡 |
| `ideas/frontend-slides-skill-design.md` | frontend-slides skill: progressive disclosure, show-dont-tell style, 12 style presets | 💡 |
| `ideas/mapreduce-rust-patterns.md` | MapReduce Rust architecture patterns: Master/Worker FSM, speculative execution | 💡 |
| `ideas/wasm-cli-tool-wrapper-factory.md` | WASM CLI Tool Wrapper Factory — any C/C++ CLI → drag-drop zero-backend HTML tool | ⚠️ 缝隙 |
| `ideas/yt-browse-local-first-channel-browser.md` | Local-first channel browser: fetch-cache-search, Bubble Tea Elm TUI | ❌ 已饱和 |
| `ideas/zvec-directions.md` | 6 zvec project directions (hybrid search, RAG, edge KB, etc.) | ❌ 大部分已饱和 |
| `ideas/quantized-vector-store-mlx.md` | MLX quantized vector store: million-scale local vector search | ❌ 已饱和 |
| `ideas/sdk-agent-mini-symphony-integration.md` | SDK Agent as mini_symphony executor (Claude SDK + task queue) | ❌ 已被取代 |
| `ideas/progress-as-code-manifest.md` | Progress-as-Code: self-scanning project dashboard, auto-generate README catalog from file system | 💡 |

### Project Structure

```
CodeSnippets/
├── python/          # Python snippets
├── javascript/      # JavaScript / Node.js snippets
├── html-tools/      # Standalone single-page HTML tools
├── shell/           # Shell scripts and CLI tricks
├── snippets/        # Cross-language / general snippets
├── templates/       # Copy-paste config and file templates
├── ideas/           # Project ideas with verification status
├── analysis/        # External research and deep-read docs
├── references/      # Internal conventions and doc templates
├── READING_LIST.md  # Source URL tracking (pending / archived)
├── WORKFLOW.md      # Insight collection workflow config
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
# Name: <Snippet Name>
# Purpose: <What problem it solves>
# Deps: <pip install ...>
# Use cases: <Where to apply it>
# Date: YYYY-MM-DD
# =============================================================================
```

### License

[MIT](LICENSE) — Copyright (c) 2026 Hugh Lin

---

## 简体中文

### 功能特性

- **17 个可运行代码片段** — Python、Rust、TypeScript、HTML/JS 工具，可直接导入或执行
- **29 篇深度精读** — 从专家文章、开源项目、论文中萃取的核心洞见
- **11 个灵感文档** — 项目方向，含实时市场验证状态
- **5 个可复用模板** — 编排器配置、Prompt 模板、Linter 预设、Agent 文档架构

### 目录

#### 🟢 代码——可直接运行或导入

| 文件 | 功能 | 依赖 |
|------|------|------|
| `python/snippet_manager.py` | CLI 片段管理器，支持自然语言搜索，可组合片段生成 LLM prompt | `anthropic`, `rich` |
| `python/tape_context.py` | 基于锚点的上下文装配，替代历史继承，适合群聊/多任务 Agent | 标准库 |
| `python/zvec_inprocess_vector.py` | in-process 向量库演示——混合检索（语义+结构化过滤），零服务依赖 | `zvec`, `sentence-transformers` |
| `python/fts5_fuzzy_search.py` | SQLite FTS5 三层模糊搜索：Porter 词干 → trigram 子串 → Levenshtein 纠错 | 标准库 (sqlite3) |
| `python/sandbox_execute.py` | 隔离子进程执行——只有 stdout 进入 context，带 budget 控制 | 标准库 (subprocess) |
| `python/mini_symphony.py` | 轻量 Agent 编排器：TASKS.md 任务队列 → per-task workspace → pi/claude 子进程 → 两种重试 | `pyyaml` |
| `python/session_tracker.py` | Agent 会话持续性：SQLite 事件捕获 → 优先级快照（≤2 KB）→ Compaction 后 FTS5 恢复 | 标准库 |
| `python/insight_agent.py` | 独立的 URL→CodeSnippets 归档 Agent——直接调用 Anthropic SDK，可作为 CLI 或 mini_symphony 子命令 | `anthropic`, `requests` |
| `javascript/pdf_to_images.html` | 纯前端 PDF 页面渲染——通过 PDF.js 将每页转为 JPEG | PDF.js (CDN) |
| `javascript/browser_ocr.html` | 纯前端 OCR——Tesseract WebAssembly，支持中英文 | Tesseract.js (CDN) |
| `html-tools/pdf_ocr.html` | 完整的浏览器端 PDF OCR 工具——PDF 渲染 + 文字提取，零后端 | PDF.js + Tesseract.js (CDN) |
| `snippets/kway-merge-heap.rs` | K-way 外部归并排序（BinaryHeap min-heap）+ 相同 key 聚合，MapReduce Reduce 阶段 | 标准库 (Rust) |
| `snippets/atomic-file-write.rs` | 原子文件写入：先写 tmp 再 rename，防止崩溃或并发导致脏文件 | 标准库 (Rust) |
| `snippets/mapreduce-engine.rs` | Rust MapReduce 引擎——Master/Worker mpsc 调度、K-way 归并、推测执行、原子写入 | 标准库 (Rust) |
| `snippets/async-message-queue.ts` | TypeScript 异步消息队列——push-to-pull 适配器，WebSocket/SDK 流式消费用 AsyncIterator | TypeScript 标准 |
| `snippets/css-reveal-animations.css` | CSS 入场动画集合（淡入上移、缩放、模糊、错开延迟）+ Viewport 规则 + 背景效果 | 无 |
| `snippets/emscripten-wasm-build-template.sh` | Emscripten WASM 构建脚本模板——patch+build 模式，可复用于任意 C/C++ CLI→浏览器工具 | `emcc` (emsdk) |

#### 🟡 模板——复制后按需修改

| 文件 | 功能 | 依赖 |
|------|------|------|
| `templates/WORKFLOW.md.template` | mini_symphony.py 的配置+Prompt 模板——复制后按项目修改 | — |
| `templates/TASKS.md.example` | mini_symphony.py 的任务队列文件示例——Markdown checklist 格式 | — |
| `templates/ruff.toml.template` | 生产级 ruff 配置：E/F/B/I/UP/RUF 规则、per-file-ignores、formatter 设置 | — |
| `snippets/interactive-explanation-prompt.md` | 交互式解释 Prompt 模板——为难以直觉理解的算法生成可视化 HTML 动画 | — |
| `templates/agents-md-template.md` | 5 层 Agent 文档架构模板（README→DEVELOPMENT→STATUS→RESEARCH→AGENTS），从 chenglou/pretext 提炼 | — |

#### 🔵 参考——做设计决策时查阅

**精读文档 (analysis/)**

| 文件 | 内容 |
|------|------|
| `analysis/simon-willison-agentic-patterns.md` | Simon Willison 7 个 Agentic Engineering 模式精读 |
| `analysis/simon-willison-hoard-things.md` | 精读："囤积你知道如何做的事"——重组 Prompt、囤积体系、Agent 时代知识复利 |
| `analysis/simon-willison-code-is-cheap.md` | 精读："代码现在很便宜"——成本模型反转、4条洞见+蕴含链、5个反模式、3个衍生想法 |
| `analysis/simon-willison-red-green-tdd.md` | 精读："Agent 时代的 Red/Green TDD"——4条洞见+蕴含链、测试门控编排模式 |
| `analysis/simon-willison-anti-patterns.md` | 精读："Agentic Engineering 反模式"——PR 验证伦理、未审查代码作为价值转嫁 |
| `analysis/simon-willison-first-run-tests.md` | 精读："First Run the Tests"——三合一信号（能力探测+规模校准+心态注入） |
| `analysis/simon-willison-interactive-explanations.md` | 精读：交互式解释 & 认知债务——两阶段还债路径（线性导读→交互动画） |
| `analysis/simon-willison-linear-walkthroughs-manual-testing.md` | 精读：线性导读 + Agent 手动测试 + Showboat——认知债务三级体系、防作弊设计 |
| `analysis/simon-willison-wasm-browser-tool-pattern.md` | 精读：WASM 浏览器工具模式——CLI→WASM→零后端 HTML、Emscripten 暴力编译 |
| `analysis/simon-willison-llm-026-tools.md` | LLM 0.26 工具调用发布精读：CLI、插件、Python API、ReAct 循环、MCP 路线图 |
| `analysis/symphony-orchestration-spec.md` | OpenAI Symphony SPEC 精读：编排状态机、Workspace 隔离、App-Server 协议 |
| `analysis/pi-context-engineering.md` | pi coding agent 精读：7 个 Context Engineering 决策 + system prompt + 工具定义 |
| `analysis/context-mode-mcp-context-saving.md` | Context Mode 精读：MCP 输出沙箱（98%压缩）、SQLite+FTS5 会话持续性 |
| `analysis/rust-mapreduce-architecture.md` | Rust MapReduce 单机实现——Master/Worker FSM、K-way 归并、推测执行 |
| `analysis/karpathy-autoresearch.md` | karpathy/autoresearch 精读：Git 棘轮自主 ML 实验、program.md 两级优化 |
| `analysis/karpathy-nanochat.md` | nanochat 精读：单拨盘 GPT 训练、x0 残差、Muon+AdamW 参数分组 |
| `analysis/design-plugin-claude-code.md` | design-plugin 精读：代码库推断视觉语言、CSS selector 坐标系、DESIGN_MEMORY 积累 |
| `analysis/ruff-python-linter.md` | Ruff 精读：--add-noqa 迁移策略、RUF100 技术债追踪、B006/B023 捉虫规则 |
| `analysis/claude-agent-sdk-demos.md` | Claude Agent SDK Demos 精读：AgentDefinition 模式、工具路由、多 Agent 示例 |
| `analysis/docflow-local-rag-assistant.md` | DocFlow 本地 PDF 知识助手精读：Phase 6 架构、Qdrant+Ollama 管线 |
| `analysis/pegainfer-qwen35-prefill-optimization.md` | pegainfer Qwen3.5 Prefill 优化精读：TTFT 16.8s→235ms、CUDA/Triton 内核 |
| `analysis/qjl-mlx-turboquant-apple-silicon.md` | QJL-MLX TurboQuant 精读：PolarQuant+QJL Apple Silicon MLX KV-cache 量化 |
| `analysis/idea-combinations.md` | 现有素材交叉组合分析：5 组想法配对、优先级排序 |
| `analysis/directions-synthesis.md` | 全局方向综合分析 v1：从所有想法和精读中提炼统一优先级 |
| `analysis/directions-synthesis-v2.md` | 全局方向综合分析 v2：新增 pi-context、symphony、yt-browse、MapReduce 后更新 |
| `analysis/chenglou-pretext-text-layout.md` | Pretext 精读：纯 JS 多行文本测量布局——prepare/layout 两阶段、Canvas 代理测量、多文字系统 |
| `analysis/microsoft-vibevoice-voice-ai.md` | VibeVoice 精读：微软开源语音 AI 全家桶——7.5Hz tokenizer（3200× 压缩）、next-token diffusion、ASR/TTS/Realtime |
| `analysis/claude-code-ai-reimplementation-ethics.md` | AI 重实现与 copyleft 侵蚀精读：合法≠正当方向向量、chardet 案例、规格 copyleft、伦理 porting |
| `analysis/claude-code-architecture-patterns.md` | Claude Code 架构精读：512K LOC 中提取的 10 个可迁移模式——buildTool() 工厂、async generator 循环、5 阶段启动、三层权限、Worker 隔离 |

**灵感与方向 (ideas/)**

| 文件 | 内容 | 状态 |
|------|------|------|
| `ideas/agentic-hoarding-patterns.md` | Agentic 囤积模式：Agent 读已有代码组合新工具 | 💡 |
| `ideas/context-mode-patterns.md` | Context Mode 压缩模式：沙箱 + stdout 过滤 | 💡 |
| `ideas/context-mode-session-continuity-pattern.md` | Agent 会话持续性：PreCompact 快照+FTS5 恢复、四钩架构 | 💡 |
| `ideas/frontend-slides-skill-design.md` | frontend-slides skill 架构：渐进式披露、12 种风格速查 | 💡 |
| `ideas/mapreduce-rust-patterns.md` | MapReduce Rust 架构模式：Master/Worker FSM、推测执行 | 💡 |
| `ideas/wasm-cli-tool-wrapper-factory.md` | WASM CLI 工具封装工厂——任意 C/C++ CLI→拖放式零后端 HTML 工具 | ⚠️ 缝隙 |
| `ideas/yt-browse-local-first-channel-browser.md` | 本地优先频道浏览器：fetch-cache-search、Bubble Tea Elm TUI | ❌ 已饱和 |
| `ideas/zvec-directions.md` | 6 个 zvec 项目方向（混合检索、RAG、边缘 KB 等） | ❌ 大部分已饱和 |
| `ideas/quantized-vector-store-mlx.md` | MLX 量化向量存储：百万级本地向量搜索 | ❌ 已饱和 |
| `ideas/sdk-agent-mini-symphony-integration.md` | SDK Agent 作为 mini_symphony 执行器 | ❌ 已被取代 |
| `ideas/progress-as-code-manifest.md` | Progress-as-Code：自扫描式项目仪表盘，从文件系统自动生成 README 目录表 | 💡 |

### 项目结构

```
CodeSnippets/
├── python/          # Python 相关片段
├── javascript/      # JavaScript / Node.js 相关片段
├── html-tools/      # 独立单页 HTML 工具
├── shell/           # Shell 脚本与命令行技巧
├── snippets/        # 通用 / 跨语言片段
├── templates/       # 配置文件与项目模板（复制即用）
├── ideas/           # 项目灵感与构思（含验证状态）
├── analysis/        # 外部资料精读与参考文档
├── references/      # 内部规范与文档模板
├── READING_LIST.md  # 来源 URL 追踪（待归档 / 已归档）
├── WORKFLOW.md      # Insight 收录工作流配置
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
