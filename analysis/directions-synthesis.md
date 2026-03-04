# 全局方向综合分析

**日期**: 2026-03-04
**素材来源**:
- `ideas/agentic-hoarding-patterns.md` — 囤积模式（agent 读已有代码组合新工具）
- `ideas/context-mode-patterns.md` — Context 压缩（沙箱 + stdout 过滤）
- `ideas/zvec-directions.md` — in-process 向量库六个方向
- `analysis/idea-combinations.md` — 五组交叉组合（已有优先级排序）
- `analysis/simon-willison-agentic-patterns.md` — 7 个 Agentic Engineering 模式

---

## 全局素材地图

```
┌─────────────────────────────────────────────────────────────────┐
│  已有实现（代码可运行）                                           │
│  snippet_manager.py  tape_context.py  zvec_inprocess_vector.py  │
│  pdf_to_images.html  browser_ocr.html  pdf_ocr.html             │
│  fts5_fuzzy_search.py  sandbox_execute.py                       │
└────────────────────────┬────────────────────────────────────────┘
                         │ 已有灵感文档指出的缺口
         ┌───────────────┼───────────────────────┐
         ▼               ▼                       ▼
   向量搜索缺失    Context 压缩缺失        浏览器工具可扩展
   (zvec-directions) (context-mode)       (hoarding-patterns)
                         │
                         │ Simon Willison 新增的杠杆点
                         ▼
     TDD 测试规范 / Interactive Explanations / WASM 封装模式
     Linear Walkthroughs / "Code is Cheap"（成本门槛归零）
```

---

## 四条发展轨道

### 轨道一：工具库语义化 → MCP Server
**现状 → 目标**：字符串搜索的笔记本 → 语义可检索的 agent 工具箱

| 步骤 | 具体动作 | 涉及素材 |
|------|---------|---------|
| 1 | snippet_manager 接入 zvec，搜索从字符串升级为向量 | A + C |
| 2 | 每个 snippet 自动 embed（代码 + 头注释），增量更新 | zvec 方向一 |
| 3 | `combine_for_task()` 改为：描述任务 → 语义检索最相关片段 → 组合 prompt | A + C |
| 4 | 包装成 MCP server，暴露 `search_snippets` / `combine_for_task` 工具 | 组合六 |

**新增 Simon 杠杆**：
- "Code is Cheap" → 不要纠结要不要做，直接 prompt 一个 agent 跑出来
- "First Run the Tests" → snippet_manager 现在零测试，先补测试再扩展

**一句话价值**：CodeSnippets 从被动的笔记本变成 Claude Code/Cursor 可以直接调用的工具箱。

---

### 轨道二：Agent 基础设施套件
**现状 → 目标**：三个独立的 Python 片段 → 一套完整的 agent 基础设施

```
tape_context.py    → 上下文装配（当前任务记忆）
    +
zvec               → 长期记忆（历史锚点向量化）
    +
sandbox_execute.py → Context 压缩（大输出不进 context）
    +
fts5_fuzzy_search  → 知识库检索（结构化文档索引）
```

**把四个片段变成一个协作的框架**：

- Tape 的 `anchor()` 写入时同步 embed → zvec（历史可检索）
- 新任务 `assemble_context()` = 最近锚点 + 语义相关历史锚点 + 当前消息
- 大工具输出走 `sandbox_execute` → 只有 stdout 进 tape
- FTS5 知识库存文档，zvec 存对话锚点，两路并行检索

**新增 Simon 杠杆**：
- "Red/Green TDD" → 框架级代码必须有测试，先写失败测试再集成
- "Interactive Explanations" → 为 tape_context 的锚点机制做一个动态可视化，帮助理解和推广

**一句话价值**：解决"agent 记忆"这个最核心的工程问题，可复用于任何对话式 agent 项目。

---

### 轨道三：零后端浏览器工具集扩展
**现状 → 目标**：3 个浏览器工具（PDF 渲染、OCR、PDF OCR）→ 系统化的 WASM 工具集

**已验证的模式**（来自 Simon）：
```
任意 CLI 工具（C/C++/Rust）
    → Emscripten / wasm-pack 编译
    → drag-drop Web UI + 下载按钮
    → 存入 html-tools/
```

**可以继续做的工具**（按难度排序）：

| 工具 | 来源 CLI | WASM 工作量 | 价值 |
|------|---------|-----------|------|
| GIF 优化器 | Gifsicle | 中（已有 Simon 示例） | ⭐⭐⭐⭐ |
| 图片压缩器 | MozJPEG / OxiPNG | 中 | ⭐⭐⭐⭐ |
| 视频截图 / GIF 转换 | FFmpeg（轻量子集） | 高 | ⭐⭐⭐⭐⭐ |
| 文本 diff 可视化 | diff-so-fancy | 低 | ⭐⭐⭐ |
| SQLite 浏览器 | SQLite WASM（官方提供） | 低 | ⭐⭐⭐⭐ |

**新增 Simon 杠杆**：
- 每个 WASM 工具都需要测试工具（Rodney / Playwright）；把测试脚本也存到 snippets/
- "Code is Cheap" → 以前一个 WASM 工具要花几天，现在 prompt + agent 可以几小时出来

**一句话价值**：html-tools/ 变成一个系统化的"把 CLI 搬到浏览器"工具集，每个工具互相参考代码风格。

---

### 轨道四：知识自我解释层
**现状 → 目标**：代码片段是静态文件 → 每个核心片段都有可互动的"可视化解释"

**应用"Interactive Explanations"模式到我们自己的代码上**：

| 片段 | 值得可视化的核心算法 | 输出形式 |
|------|-------------------|---------|
| `fts5_fuzzy_search.py` | 三层搜索降级流程（精确→子串→Levenshtein） | 动态 HTML：输入关键词，看命中路径 |
| `tape_context.py` | 锚点装配过程（哪些消息被选中、权重如何） | 动态 HTML：可视化 context 组装过程 |
| `zvec_inprocess_vector.py` | 混合检索打分（dense + sparse 权重叠加） | 动态 HTML：两路分数可视化 |
| `sandbox_execute.py` | Context 压缩效果（56KB → 299B 的全过程） | 静态图表或 walkthrough.md |

**应用"Linear Walkthroughs"模式**：
- 用 showboat 为复杂片段生成 walkthrough.md，存入 analysis/
- 目标：任何人（或 agent）读 walkthrough 即可理解片段，不需要逐行读代码

**一句话价值**：片段不只是"能用的代码"，还是"能教会人的文档"，大幅降低复用门槛。

---

## 优先级矩阵（综合所有素材）

| 方向 | 投入 | 独立价值 | 与其他方向协同 | 建议时序 |
|------|------|---------|-------------|---------|
| 轨道一 Step 1-2：A+C 语义搜索 | ~50 行 | ⭐⭐⭐⭐⭐ | 是轨道一/四的基础 | **立刻** |
| 轨道四：fts5 可视化 HTML | ~1小时 | ⭐⭐⭐⭐ | 验证 Interactive Explanations 模式 | **立刻**（成本接近零）|
| 轨道二 Step 1：Tape + zvec 集成 | ~100 行 | ⭐⭐⭐⭐⭐ | 输出可复用框架 | 第二批 |
| 轨道三：WASM 工具集 | 每个几小时 | ⭐⭐⭐⭐ | 独立，随时可加 | 按兴趣穿插 |
| 轨道一 Step 3-4：MCP Server | 中等 | ⭐⭐⭐⭐⭐ | 需要 Step 1-2 完成 | 积累后做 |
| 自进化片段库（E+A Git Hook）| 中等 | ⭐⭐⭐⭐ | 依赖语义搜索 | 轨道一完成后 |
| 轨道二 完整框架 | 较大 | ⭐⭐⭐⭐⭐ | 最高复用价值 | 第三批 |

---

## "Code is Cheap"后的行动原则

Simon 的核心论点用在这里：**以前这个库的增长速度受限于"手写代码的时间成本"，现在这个约束已经解除了。**

实践规则：
1. **任何想法，先 prompt 一个 async agent session**，最坏浪费几个 token
2. **每个新片段用 Red/Green TDD 开发**：先写一个能失败的测试，再让 agent 实现
3. **每个复杂片段配一个 Interactive Explanation HTML**，30分钟以内，不再是奢侈品
4. **WASM 工具**：遇到好用的 CLI，直接 prompt"编译成 WASM + 做个 drag-drop 页面"

---

## 参考文件索引

| 文件 | 关键内容 |
|------|---------|
| `ideas/agentic-hoarding-patterns.md` | agent 读已有代码组合新工具的 prompt 模式 |
| `ideas/context-mode-patterns.md` | 沙箱 + stdout 过滤的 context 压缩架构 |
| `ideas/zvec-directions.md` | sgrep / embedding cache / 单脚本 RAG 等六个方向 |
| `analysis/idea-combinations.md` | A+C / B+C / E+A / MCP Server 交叉组合分析 |
| `analysis/simon-willison-agentic-patterns.md` | TDD / WASM封装 / 交互式解释 / walkthroughs |
