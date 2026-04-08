# Simon Willison "AI Should Help Us Produce Better Code" 精读：Compound Engineering 复利工程

**来源**: [AI should help us produce better code](https://simonwillison.net/guides/agentic-engineering-patterns/better-code/)
**日期**: 2026-04-08
**标签**: agentic-engineering, compound-engineering, technical-debt, exploratory-prototyping, code-quality, refactoring
**系列**: Agentic Engineering Patterns — Principles 第 4 篇

---

## 30秒 TL;DR

> Agent 时代代码质量下降是一种**选择**，而非必然。Willison 提出三个利用 Agent 提升代码质量的机制：(1) 用异步 Agent 做"简单但耗时"的重构——清除重命名、API 统一、文件拆分等技术债；(2) 用 Agent 做**探索性原型**——验证技术选型的成本从"几天"降到"一个 prompt"；(3) **Compound Engineering**（Dan Shipper/Every 提出）——每次任务结束做回顾，把有效做法沉淀到 Agent 指令中，形成质量复利循环。核心心智模型：**Agent 同时交付新功能和质量提升——二者不再是 tradeoff。**

---

## 概念总览

| 概念/模式 | 核心思想 | 适用场景 |
|---------|---------|---------|
| **零容忍代码异味** | 重构成本趋近零 → 不再有借口容忍小问题 | 任何有轻微技术债的代码库 |
| **异步 Agent 重构** | 用 Gemini Jules/Codex Web/Claude Code Web 后台跑重构任务 | 不打断主工作流的大规模清理 |
| **探索性原型** | 用一个 prompt 生成技术选型的验证原型 | 架构决策前的 spike |
| **Compound Engineering** | 任务结束 → 回顾 → 沉淀到 Agent 指令 → 下次更好 | 任何长期项目 |

---

## 深读

### 1. 技术债的四种"简单但耗时"类型

Willison 列举了最常见的债务：
- **API 不一致**：早期设计缺陷需要改几十处代码，于是加了一个"略有不同的新 API"共存
- **命名混乱**：teams vs groups 选错了，但改名工作量太大只在 UI 层修
- **重复功能**：系统演化出多个功能略有不同的重复模块
- **巨型文件**：一个文件几千行需要拆分

**关键判断**：这些都是"概念上简单"的变更——不需要设计决策，只需要执行。这恰好是 Agent 最强的领域。

### 2. 异步 Agent 重构

```
工作流：
1. 启动异步 Agent（Gemini Jules / Codex Web / Claude Code Web）
2. 给出重构指令，让它在分支/worktree 中工作
3. 继续自己的主线工作
4. 稍后在 PR 中评审结果
5. 好 → merge；差不多 → 再 prompt；差 → 丢弃
```

**关键洞见**：这些是"fire-and-forget"任务——失败成本几乎为零，成功价值却是永久的代码质量提升。

### 3. 探索性原型——技术选型的验证成本趋零

> "Is Redis a good choice for the activity feed on a site which expects thousands of concurrent users? The best way to know for sure is to wire up a simulation and run a load test."

以前这个实验需要一天。现在一个 prompt 搞定。而且可以**并行跑多个实验**——同时测 Redis、PostgreSQL、DynamoDB，选最好的。

### 4. Compound Engineering 复利循环

Dan Shipper / Every 公司的做法：
```
每次 Agent 任务结束后：
1. 回顾：什么有效？什么低效？
2. 沉淀：把有效做法写入 CLAUDE.md / AGENTS.md
3. 下次：Agent 自动遵循改进后的指令
→ 质量复利：每个项目都比上一个更好
```

**这就是 CodeSnippets 知识库在做的事**——但 Compound Engineering 把它具体化到了单个项目的 Agent 指令层面。

---

## 心智模型

> **"Agent 同时交付新功能和质量提升——二者不再是 tradeoff。"**

传统工程中，新功能 vs 技术债是零和博弈。Agent 打破了这个约束：
- 新功能：Agent 写
- 技术债：异步 Agent 同时清理
- 质量保证：每次回顾都让 Agent 更好

**适用条件**：(1) 有自动化测试保证重构不引入 bug；(2) 有 PR review 流程检查 Agent 输出；(3) 技术债是"简单但耗时"类型
**失效条件**：(1) 技术债是设计层面的（需要人决策）；(2) 没有测试覆盖（Agent 重构可能引入 bug）；(3) 代码库太小不值得
**在我的工作中如何用**：mini_symphony 的 WORKFLOW.md 就是 Compound Engineering 的载体——每次任务后更新 WORKFLOW.md 就是"compound step"

---

## 非显见洞见

### 洞见 1：重构成本趋零意味着"代码异味"的容忍阈值应该归零

- 所以：以前"不值得花半天重命名"的判断框架过时了——现在只需要一个 prompt
- 所以：代码审查中发现的任何小问题都应该立即修复，而不是记到 backlog 等死
- 因此可以：在 mini_symphony 的 WORKFLOW.md 中加一条：每次任务结束前，Agent 主动检查并修复一个已知代码异味

### 洞见 2：探索性原型的成本趋零改变了技术决策的方法论

- 所以：以前"选 A 还是 B"是基于经验和推理的——现在应该基于**并行实验**
- 所以：架构讨论会议可以从"辩论哪个方案更好"变成"各跑一个 spike 看数据"
- 因此可以：建立"任何技术选型问题先跑 spike"的工作习惯，用 mini_symphony 并行调度

### 洞见 3：Compound Engineering 是 CodeSnippets 知识库的项目级实例

- 所以：CodeSnippets 是跨项目的 compound step（沉淀可复用知识），而 CLAUDE.md/WORKFLOW.md 是项目内的 compound step（沉淀项目特化知识）
- 所以：两层都需要——全局 KB + 项目级指令
- 因此可以：insight-collector 的 Step 3D（组合生成）就是一种 compound step——把新知识与旧知识交叉连接

---

## 隐含假设

- **假设有 PR review 流程**：Agent 重构后必须有人审查。如果自动 merge 则错误会积累
- **假设测试覆盖足够**：重构安全性依赖于测试。无测试的代码库用 Agent 重构风险极高
- **假设"简单但耗时"是主要技术债类型**：对于设计层面的债务（错误的架构选择），Agent 无法独立判断

---

## 反模式与陷阱

- **"Agent 写的代码质量差"归因错误**：Willison 指出这是一种**选择**而非必然。如果你的 Agent 产出质量差，是你的 prompt/review/workflow 需要改进 → 正确做法：把质量问题当作 process 问题而非 tool 问题
- **"Compound step 太麻烦"**：每次任务后回顾→沉淀确实有开销。但这个开销的复利回报极高 → 正确做法：把 compound step 固化到 workflow 中，而非依靠自律

---

## 与现有知识库的连接

- **关联 `analysis/simon-willison-code-is-cheap.md`**：本文是"代码便宜了"的**下一步推论**——便宜了不是降低质量的理由，而是提高质量的机会
- **关联 `analysis/karpathy-llm-wiki-pattern.md`**：Compound Engineering = Karpathy wiki 的 Lint 操作在项目级的实例。两者都是"持续维护"模式
- **关联 `analysis/simon-willison-red-green-tdd.md`**：TDD 是 Agent 重构的安全网——没有测试的重构是危险的
- **关联 `python/mini_symphony.py`**：mini_symphony 的 WORKFLOW.md = Compound Engineering 的载体。每次任务结束更新 WORKFLOW.md 就是 compound step
- **关联 `analysis/claude-code-architecture-patterns.md`**：Claude Code 的 Worker 后台执行 = Willison 描述的"异步 Agent 重构"模式

---

## 衍生项目想法

### 想法 1：mini_symphony compound-step 自动化

**来源组合**：[Compound Engineering 回顾→沉淀循环] × [已有 mini_symphony WORKFLOW.md]
**为什么有意思**：当前 mini_symphony 任务完成后没有 compound step。如果每次任务结束自动追加"本次学到什么"到 WORKFLOW.md 的 lessons 部分，后续任务自动受益。
**最小 spike**：在 mini_symphony 任务完成后，调 LLM 总结本次任务的 key learning，追加到 WORKFLOW.md 的 `## Lessons Learned` 部分。

**验证状态**：
- 原始来源：✅ Dan Shipper/Every 描述了手动 compound step，但没有自动化
- GitHub：⚠️ 有类似的"session memory"机制（nanobot MEMORY.md），但没有针对 WORKFLOW 的 compound step
- 社区：⚠️ Compound Engineering 是新概念（2026），实现方式仍在探索中
- 增量价值：把手动 compound step 自动化到 task queue workflow 中
