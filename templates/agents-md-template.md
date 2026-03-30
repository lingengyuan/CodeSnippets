# AGENTS.md 模板

> 从 [chenglou/pretext](https://github.com/chenglou/pretext) 的 5 层文档架构中提炼。
> 用于需要 AI Agent 深度参与开发的项目。

---

## 设计原则

Pretext 项目的文档分 5 层，每层有明确的**读者**和**职责**：

| 文件 | 读者 | 职责 | 更新频率 |
|------|------|------|---------|
| `README.md` | 用户、外部开发者 | 公共 API、用法示例、已知限制 | 发版时 |
| `DEVELOPMENT.md` | 贡献者、CI | 命令面、环境搭建、profiling 流程 | 命令变更时 |
| `STATUS.md` | 贡献者、Agent | 当前状态指针（指向机器可读快照） | 快照刷新时 |
| `RESEARCH.md` | 贡献者、Agent、未来自己 | 探索日志：什么活下来了/什么没有/为什么 | 每次重大探索后 |
| `AGENTS.md` | AI Agent（主要）、贡献者 | 内部实现约束、文件角色、开放问题 | 代码变更时 |

**关键洞见**：AGENTS.md 不是给人读的手册，是给 Agent 读的**操作规程**。它的精细度决定了 Agent 能否独立完成一个完整的验证循环。

---

## 模板：AGENTS.md

```markdown
## {项目名}

<!-- 一句话：这个文件的定位 -->
Internal notes for contributors and agents.
Use `README.md` as the public source of truth for API and user-facing docs.
See `DEVELOPMENT.md` for the command surface.

### Commands

<!-- 不要复制 DEVELOPMENT.md 的完整命令列表，只放工作流级别的注释 -->
See `DEVELOPMENT.md` for the current command surface.
Keep the higher-level workflow notes below in sync with that command list.

### Important files

<!-- 列出每个关键文件 + 一句话职责。Agent 靠这个表决定"改哪个文件" -->
- `src/core.{ext}` — {核心模块，一句话描述其不可违反的约束}
- `src/analysis.{ext}` — {分析/预处理模块}
- `src/measurement.{ext}` — {外部系统交互层}
- `tests/` — {测试策略：小型持久不变量测试 vs 一次性探测脚本}
- `status/` — {机器可读状态快照，回归门控用}
- `config.{ext}` — {配置文件，标注哪些字段会影响热路径}

### Implementation notes

<!-- 这是最核心的部分。写法规则：
     1. 每条都是一个可执行的约束或决策记录
     2. 用"Keep X"/"Do not Y"的祈使句
     3. 标注约束的理由（"because..."或"That keeps..."）
     4. 如果某个约束来自一次失败的尝试，链接到 RESEARCH.md 的对应段落 -->

- {核心架构约束}：`{热路径函数}()` is the hot path: no {禁止操作1}, no {禁止操作2}, avoid {不鼓励操作}.
- {预处理策略}：Keep {特定类型}fixes in preprocessing, not `{热路径函数}()`.
- {缓存策略}：{缓存结构描述}; shared across {共享范围} and resettable via `{清除函数}()`.
- {测试策略}：Keep `{测试文件}` small and durable. For narrow hypothesis work, prefer throwaway probes.
- {浏览器/平台策略}：{平台名} is unsafe for {原因}. <!-- 如适用 -->
- {刷新规则}：Refresh `{快照文件}` when a diff changes {触发条件}.
- {性能约束}：For deep perf work, prefer {推荐工具} over {不推荐工具}. {理由}.
- {并发约束}：Do not run {操作A} and {操作B} in parallel. {理由}.

### Open questions

<!-- 未解决的设计决策。每条都应该是一个可以独立研究的问题。
     Agent 看到这里会知道"这个方向还没定论，不要自作主张" -->

- {架构级未决}：Decide whether {X} should stay as {当前方案} or move to {候选方案}.
- {性能级未决}：{优化方向} could skip some {开销}, but needs benchmarking.
- {覆盖级未决}：Additional {配置/场景} are still untested: {列表}.

### Related

<!-- 相关项目、上游依赖、参考实现 -->
- {相关项目/原型} — {一句话关系描述}
```

---

## 模板：STATUS.md

```markdown
# Current Status

<!-- 这个文件只做一件事：告诉你"现在去哪里看数据" -->
Machine-readable snapshot data lives in JSON.

Use this file for "where do I look right now?".
Use `RESEARCH.md` for why the numbers changed.

## {维度1：如 Accuracy / Test Coverage}

Dashboard: `{path/to/dashboard.json}`
Raw data: `{path/to/raw-data.json}`

Notes:
- {当前状态一句话}
- {刷新条件}

## {维度2：如 Benchmarks / Performance}

Dashboard: `{path/to/dashboard.json}`
Raw data: `{path/to/snapshots.json}`

Notes:
- {当前状态一句话}
- {哪个环境是主基线}

## Pointers

<!-- 所有机器可读文件的快速索引 -->
- {文件}: {一句话描述}
```

---

## 模板：RESEARCH.md

```markdown
# Research Log

<!-- 历史探索日志。写法规则：
     1. 每个段落都用"什么活下来了 / 什么没活下来"格式
     2. 被拒绝的方案和理由跟保留的方案同样重要
     3. 按时间/主题组织，最新的在最前面 -->

Everything we tried, measured, and learned.
For the current snapshot, see `STATUS.md`.

## Current steering summary

<!-- 一段话：当前各个方向的状态总览 -->

## {探索主题 1}

### The problem
{问题描述}

### What survived
- {保留的方案 + 理由}

### What did NOT survive
- {被拒绝的方案 + 为什么失败}

### Broad lesson
{可迁移的一般性结论}

## {探索主题 2}
...
```

---

## 使用指南

### 何时需要全套 5 层？

- ✅ AI Agent 深度参与开发（每天多次 agent 交互）
- ✅ 有持续的精度/性能回归门控需求
- ✅ 探索性强的项目（大量"试了 X，不行，换 Y"）
- ❌ 简单的 CRUD 应用
- ❌ 一次性脚本

### 最小起步

如果项目还小，先只写 AGENTS.md（Important files + Implementation notes + Open questions）。
等项目积累了 3 次以上"试了不行又换"的经历后，开 RESEARCH.md。
等有了机器可读的质量快照后，开 STATUS.md。

### 写作心法

> **AGENTS.md 的每一条都应该能回答一个 Agent 的具体问题：**
> "我要改 X，会不会破坏 Y？" → Implementation notes
> "这个文件是干什么的？" → Important files
> "这个方向有人试过吗？" → Open questions + RESEARCH.md 链接
