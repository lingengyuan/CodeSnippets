# Pretext 精读：纯 JS 多行文本测量与布局

**来源**: [chenglou/pretext](https://github.com/chenglou/pretext)
**日期**: 2026-03-30
**标签**: text-layout, canvas-measureText, DOM-reflow, browser-accuracy, agent-documentation

---

## 30秒 TL;DR

> Pretext 是一个纯 JS/TS 库，用 Canvas `measureText()` 绕过 DOM 重排，实现多行文本的高精度测量和布局。核心架构是 **prepare/layout 两阶段分离**：`prepare()` 做一次性的文本分段+测量+缓存，`layout()` 只走纯算术——永远不碰 DOM。支持 CJK、阿拉伯语、泰文、缅甸文、emoji 等复杂文字系统，并在三大浏览器（Chrome/Safari/Firefox）上通过跨脚本、跨字体的精度回归门控。

---

## 概念总览

| 概念/模式 | 核心思想 | 适用场景 |
|---------|---------|---------|
| **prepare/layout 两阶段** | 把昂贵的文本分析和测量从热路径中剥离 | 任何需要反复对同一文本做不同宽度布局的场景（虚拟列表、resize） |
| **Canvas 作为字体引擎代理** | 用 `measureText()` 绕过 DOM，直接获取浏览器字体引擎的宽度数据 | 避免 `getBoundingClientRect` 导致的同步重排 |
| **浏览器作为 ground truth** | 不实现自己的字体渲染引擎，而是用浏览器的 Canvas 输出作为"标准答案"，在其上做纯算术布局 | "AI-friendly iteration"——让验证循环极短 |
| **段求和 + 语义预处理** | 按词/段测量宽度并求和，在预处理阶段合并标点、处理特殊 Unicode 序列 | 多语言文本布局 |
| **8 种内部断行类型** | 普通文本、可折叠空格、保留空格、Tab、不可断胶水、零宽断行点、soft hyphen、硬换行 | 精确模拟 CSS `white-space: normal` 和 `pre-wrap` |
| **浏览器特定容差** | Chrome/Gecko 0.005px，Safari/WebKit 1/64px | 承认平台差异，用最小 shim 而非统一算法 |

---

## 深读

### 架构：两阶段分离是产品层面的核心胜利

Pretext 的整个架构围绕一个不可动摇的约束：**`layout()` 永远不碰 DOM、不调 Canvas、不做字符串操作、不做额外内存分配**。所有"脏活"都在 `prepare()` 里完成。

```
prepare(text, font) → 分段 → 测量 → 缓存 → 返回 opaque handle
layout(prepared, maxWidth, lineHeight) → 纯算术 → { height, lineCount }
```

这个分离的实际效果：
- `prepare()` 对 500 段文本 ≈ 19ms（一次性）
- `layout()` 对同一批 ≈ 0.09ms（每次 resize 都可以调）

### 内部模块划分

| 文件 | 职责 |
|------|------|
| `src/analysis.ts` (27KB) | 文本分析阶段：正规化、分段、胶水规则、Unicode 预处理 |
| `src/measurement.ts` (7KB) | Canvas 测量运行时、段缓存、emoji 修正、浏览器 profile shim |
| `src/line-break.ts` (31KB) | 内部断行核心，被富布局 API 和热路径计数器共享 |
| `src/layout.ts` (24KB) | 公共 API：prepare/layout/prepareWithSegments/layoutWithLines/walkLineRanges/layoutNextLine |
| `src/bidi.ts` (7KB) | 简化的 BiDi 元数据辅助 |

### 多语言挑战的处理策略

RESEARCH.md 记录了每种文字系统的"什么活下来了 / 什么没活下来"，这是整个项目最有价值的部分之一：

| 文字系统 | 关键保留 | 关键淘汰 |
|---------|---------|---------|
| 阿拉伯语 | 无空格标点簇合并、标点+音标簇左粘、预处理层处理 | 配对修正模型、运行级宽度模型、短语级启发式 |
| 日语 | 假名叠字符号 (`ゝ`/`ゞ`) 视为 CJK 行首禁则 | 堆叠窄标点规则 |
| 中文 | 保持为"精度天花板金丝雀"（Chrome 有正残差，Safari 干净） | 后移闭标点、合并重复标点（`——`、`……`） |
| 泰文 | 上下文 ASCII 引号胶水 | — |
| 缅甸文 | `၊`/`။`/`၍`/`၌`/`၏` 左粘 + 中缀胶水 | 广泛的字素断行、引号-跟随词胶水 |
| 高棉 | 保留源文本中的显式零宽分隔符 | — |

### 被拒绝的方案（同样有价值）

- **DOM 元素测量放入 `prepare()`**：重新引入 DOM 读取
- **SVG `getComputedTextLength()`**：比两阶段模型更慢
- **`layout()` 中做全字符串验证**：回归了热路径性能
- **均匀缩放**：不够准确
- **通用的配对级修正模型**：太局部，移不动真正的 miss
- **HarfBuzz 服务端探测**：有研究价值，但不是运行时方向
- **text-shaper 做运行时替代**：Unicode 覆盖好，但分段和断行不适合浏览器对齐场景

### AGENTS.md 作为工程文档的范本

这是我见过最精细的 Agent 工程文档之一（16KB）。关键设计模式：
- **分层信息架构**：README（公共 API）→ DEVELOPMENT.md（命令面）→ STATUS.md（当前快照指针）→ RESEARCH.md（历史探索日志）→ AGENTS.md（内部实现笔记 + 开放问题）
- **"什么活下来了 / 什么没活下来"格式**：每个探索都明确记录保留和淘汰的理由
- **机器可读状态仪表盘**：`status/dashboard.json`、`accuracy/*.json`、`benchmarks/*.json`、`corpora/*.json` 组成回归门控

---

## 心智模型

> **"userland 拿到文本控制权，就能绕过 80% 的 CSS spec"**

chenglou 的核心论点：Web 布局的瓶颈不是实现能力，而是 spec 复杂度本身。CSS 把文本塞进单方向黑洞，想要拿回文本度量就必须付 DOM 重排的代价。如果 userland 能直接测量和布局文本，虚拟化、masonry、JS-driven flexbox 等"高级布局"就变成了纯算术问题。

**适用条件**：文本密集的 Web 应用（聊天、编辑器、虚拟列表、数据仪表盘）
**失效条件**：纯静态内容（博客文章），或者文本极少的 GL 着陆页
**在我的工作中如何用**：DocFlow 的 Web 前端如果有任何自定义文本布局需求（如 chunk 可视化、检索结果高亮），Pretext 是直接可用的底层能力

---

## 非显见洞见

### 洞见 1：语义预处理比运行时修正更有效

作者反复验证了一个模式：**在 `prepare()` 阶段用语义规则清洗文本，比在 `layout()` 阶段做聪明的数值修正效果更好。**

- 所以：数据清洗的"黄金时间"是摄入时，不是查询时
- 所以：这个原则迁移到 RAG 管线 = chunk 预处理（分词、标点合并、空白正规化）比检索时的重排序更值得投入
- 因此可以：DocFlow 的 embedder 预处理管线中，中文分词（jieba）和标点合并的收益可能比优化 reranker 模型更大

### 洞见 2：浏览器差异是物理事实，不是待解决的 bug

Chrome/Gecko 需要 0.005px 容差，Safari/WebKit 需要 1/64px。`system-ui` 在 macOS 上 Canvas 和 DOM 解析到不同字体。这些不是 Pretext 的缺陷，是**浏览器字体引擎的固有分歧**。

- 所以：跨平台精度有物理天花板，超过这个天花板的优化是白费力气
- 所以：正确的策略是"最小 shim + 承认边界"而不是"找到统一解"
- 因此可以：这个思维框架迁移到 MPS/CPU 内存问题 = 承认 PyTorch MPS 的 Metal buffer pool 是当前物理事实，用配置化 shim（我们已经做的 3 个开关）而不是追求"完美修复"

### 洞见 3：两阶段分离的价值超过所有单点优化之和

项目中所有被淘汰的方案（DOM 测量、字符串验证、均匀缩放）都有一个共同点：它们试图让 `layout()` 做更多的事。而所有活下来的改进都是让 `prepare()` 更聪明。

- 所以：架构约束（"layout 永远是纯算术"）比任何具体算法更重要
- 所以：在设计系统时，最有价值的决定是"这个组件永远不做 X"的否定约束
- 因此可以：审视 DocFlow 的架构——是否有类似的"热路径不可违反的约束"需要显式建立？

### 洞见 4：作者把"验证软件的成本趋向零"视为前提

thoughts.md 的最后一句：`The cost of any verifiable software will trend toward 0`。结合 README 中 `(very AI-friendly iteration method)` 的描述——chenglou 显然在大量使用 AI agent 做浏览器精度迭代。

- 所以：AGENTS.md 的工程精细度不是"文档癖"，而是**AI 协作的基础设施**
- 所以：项目的迭代速度不取决于人类编码速度，而取决于"agent 能不能独立完成一个浏览器精度验证循环"
- 因此可以：这是 AGENTS.md / CLAUDE.md 写法的参考标杆——不是给人读的手册，是给 agent 读的操作规程

---

## 隐含假设

- **浏览器 Canvas `measureText()` 的精度等同于 DOM 渲染精度**：这在绝大多数情况下成立，但 emoji 和 `system-ui` 上存在例外（作者已发现并做了 shim）
- **`Intl.Segmenter` 在目标浏览器中可用**：这是 prepare 阶段的核心依赖。如果目标环境不支持（如旧 Firefox），整个方案需要 polyfill
- **字体在 Canvas 和 DOM 中解析一致**：`system-ui` 上已证伪，作者选择标记为 unsafe 而非修复
- **用户会传入与 CSS 一致的 font 参数**：如果 `prepare()` 的 font 和实际 CSS font 不匹配，所有测量都会偏

---

## 反模式与陷阱

- **在热路径中引入 DOM 读取**：Pretext 整个项目的存在就是为了避免这件事。一旦 `layout()` 碰了 DOM，性能收益归零 → 正确做法：把所有测量封闭在 `prepare()` 中
- **用短时基准测试评估精度**：精度问题往往在大量文本、窄宽度、混合脚本时才暴露 → 正确做法：用跨字体 × 跨尺寸 × 跨宽度的网格扫描
- **把"浏览器差异"当 bug 修**：Chrome 和 Safari 的行适配容差本身不同 → 正确做法：最小 shim + 文档化边界
- **过早放弃"探索失败"的记录**：RESEARCH.md 中被拒绝的方案和被保留的方案同样有价值 → 正确做法：用"什么活下来了 / 什么没活下来"格式记录每次探索

---

## 与现有知识库的连接

- 关联 `analysis/docflow-local-rag-assistant.md`：Pretext 的"预处理比运行时修正更有效"原则，直接对应 DocFlow 的 jieba 分词 + 标点合并（坑3）。两个项目独立发现了同一条规律。
- 关联 `analysis/simon-willison-agentic-patterns.md`：AGENTS.md 的"分层信息架构"是 Simon Willison 的 agent 工程模式在实战中的极致实现。
- 关联 `ideas/context-mode-session-continuity-pattern.md`：Pretext 的 `prepare()` 缓存机制 = 一种特化的 context 预计算。SessionTracker 的"优先级快照"和 Pretext 的"opaque handle"在架构上是同一个 pattern：**把昂贵计算封装成轻量句柄，热路径只操作句柄**。
- 关联 `python/mini_symphony.py`：AGENTS.md 的多文件信息分层（README → DEVELOPMENT → STATUS → RESEARCH → AGENTS）可以作为 mini_symphony 项目文档结构的参考。

---

## 衍生项目想法

### 想法 1：AGENTS.md 最佳实践模板

**来源组合**：[Pretext 的 5 层文档架构] + [已有 KB 中的 mini_symphony 编排器]
**为什么有意思**：目前 CLAUDE.md 的写法缺乏公认的最佳实践。chenglou 的 AGENTS.md 是我见过的最精细的 agent 工程文档——从命令面、文件角色、实现约束到开放问题，形成了完整的"agent 操作规程"。提取成模板可以直接提升任何项目的 agent 协作效率。
**最小 spike**：从 Pretext 的 AGENTS.md 中提取结构骨架，做成 `templates/AGENTS.md.template`，然后在 CodeSnippets 或 DocFlow 上试用一次。
**潜在难点**：不同项目的 agent 需求差异很大，模板可能过于僵硬。

**验证状态**：
- 原始论文：✅ 这不是论文项目，无需论文验证
- GitHub：⚠️ 存在零散的 CLAUDE.md 示例（如 anthropics/anthropic-cookbook），但没有从实战项目中提炼的结构化模板
- 社区：⚠️ 搜到一些 "how to write CLAUDE.md" 的文章，但缺乏像 Pretext 这样精细度的实例
- 增量价值：从一个 **实际高强度使用 AI agent 迭代的项目** 中反向提取模板，比从指南文章中归纳更接地气

### 想法 2："预处理优于运行时修正"原则跨域验证

**来源组合**：[Pretext 的 RESEARCH.md 结论] + [已有 KB 中的 DocFlow 坑 3（jieba 分词）]
**为什么有意思**：两个完全不同的领域（Web 文本布局 vs RAG 管线）独立发现了同一条规律："在摄入/准备阶段做语义清洗，比在查询/布局阶段做修正效果更好"。这暗示它可能是一条更普遍的系统设计原则。
**最小 spike**：在 DocFlow 的 LESSONS.md 中增加一条跨项目验证条目，并检查 embedder 预处理管线是否还有可以前移的清洗步骤。
**潜在难点**：DocFlow 的预处理已经做了 jieba 分词，进一步前移的空间可能有限。

**验证状态**：
- 原始论文：✅ 这是从实践中归纳的原则，非论文
- GitHub：✅ 未找到明确把这条原则跨域形式化的项目
- 社区：⚠️ "data cleaning > model tuning" 在 ML 社区是常识，但没有与 Web layout 交叉对照
- 增量价值：把两个独立发现串成显式的跨域验证，对我们自己的项目审计有直接价值
