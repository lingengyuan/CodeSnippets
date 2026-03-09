# Red/Green TDD for Coding Agents 精读

**来源**: [Red/green TDD — Agentic Engineering Patterns](https://simonwillison.net/guides/agentic-engineering-patterns/red-green-tdd/)
**扩展来源**:
- [First run the tests](https://simonwillison.net/guides/agentic-engineering-patterns/first-run-the-tests/)
- [Anti-patterns: things to avoid](https://simonwillison.net/guides/agentic-engineering-patterns/anti-patterns/)
**日期**: 2026-03-07
**标签**: tdd, testing, coding-agents, agentic-engineering, ai-assisted-programming

---

## 30秒 TL;DR

> 把"先写失败测试、再实现让它通过"这一纪律应用到 coding agent 身上，是防止 agent 输出"看起来能工作但从未被执行"的代码的最有效手段。四个词 `Use red/green TDD` 已足够触发主流模型的完整 TDD 行为。

---

## 概念总览

| 概念/模式 | 核心思想 | 适用场景 |
|---------|---------|---------|
| Red 阶段 | 先写测试，确认测试**失败** | 每次新功能开始 |
| Green 阶段 | 迭代实现，直到测试**通过** | 红阶段完成后 |
| First Run the Tests | Session 开始先跑全量测试 | 每次新 session 接手已有项目 |
| 测试即上下文 | 测试文件是 Agent 理解项目最高信噪比的信息源 | Agent 接手陌生 codebase |
| 测试即执行证明 | 未被测试的 Agent 代码在统计上是"草稿" | 所有 Agent 输出 |

---

## 深读

### 1. 为什么 TDD 与 Agent 是天然组合

Simon 点出了 coding agent 的两大核心风险：

1. **写了不工作的代码**——agent 自信地交付了一段永远不会报错的代码……因为它从未被执行
2. **写了不被调用的代码**——agent 生成了完整的函数/类，但没有任何代码路径会触发它

TDD 同时解决这两个问题：
- 测试强制要求你先**想清楚接口**，然后**证明实现达到了接口规约**
- 失败的测试证明代码路径真的被执行了（而不是编译通过即正确）

### 2. 红阶段是"测试的测试"——最容易被跳过的一步

Simon 专门强调了这一点：

> "It's important to confirm that the tests fail before implementing the code to make them pass. If you skip that step you risk building a test that passes already, hence failing to exercise and confirm your new implementation."

**这不是仪式，是验证**：

- 如果你跳过红阶段，测试可能因为以下原因已经通过：
  - 测试写的是已有逻辑（不是新需求）
  - 测试断言太宽松（永远为真）
  - 测试覆盖了错误的代码路径

一个"永远绿"的测试是最危险的——它给了你虚假的安全感，而不告诉你任何有用信息。

### 3. 四词提示词的工程效率

```
Use red/green TDD
```

这四个词是**压缩了大量软件工程纪律的短语**。Simon 明确说：

> "Every good model understands 'red/green TDD' as a shorthand for the much longer 'use test driven development, write the tests first, confirm that the tests fail before you implement the change that gets them to pass'."

这是 **Prompt Compression**（提示词压缩）的一个范例：
- 长 prompt：50+ 词的 TDD 指令
- 短 prompt：4 个词，效果相同（甚至更好，因为模型用训练数据里最规范的 TDD 实践来填充）

### 4. First Run the Tests — Session 开场仪式的实质

相邻章节"First Run the Tests"揭示了一个对称模式：

```
Red/Green TDD       → 新功能的测试纪律
First Run the Tests → 接手已有项目的测试纪律
```

这四个词（`Run the tests` / `uv run pytest`）的实际效果远超字面含义：

1. **强制发现测试套件**：让 agent 主动找到如何运行测试，而不是假设测试存在
2. **测试数量 = 复杂度代理**：agent 看到"运行了 247 个测试"会自动校准对项目规模的估计
3. **注入测试心态**：已经运行过测试的 agent，在后续操作中显著更倾向于写新测试
4. **测试文件是最高信噪比的文档**：agent 被隐式引导去阅读测试文件来理解业务逻辑

### 5. Anti-pattern 对比：未审查代码的 PR

Anti-patterns 章节提供了 TDD 的对立面案例：

> "Don't file pull requests with code you haven't reviewed yourself. If you open a PR with hundreds (or thousands) of lines of code that an agent produced for you, and you haven't done the work to ensure that code is functional yourself, you are delegating the actual work to other people."

**关键逻辑**：测试不只是技术工具，也是**职责转移的防护机制**——有测试的 PR 作者证明了"我为这段代码的正确性背书"，没测试的 PR 把验证工作推给了 reviewer。

Simon 建议的好 PR 特征（可用作 Agent PR 的 Checklist）：
- [ ] 代码可工作，且你有自信它可工作
- [ ] 变更足够小，reviewer 能高效审查（多个小 PR 优于一个大 PR）
- [ ] 包含额外上下文（高层目标、关联 issue/spec）
- [ ] PR 描述由你审查过（不能直接用 agent 生成的描述）
- [ ] 包含手动测试记录（截图/视频/日志）

---

## 心智模型

> **测试 = 可执行的规约（Executable Specification）**
> 在 Agent 时代，测试的主要价值从"防回归"扩展到"证明代码曾被执行"和"替代文档成为 Agent 的项目地图"。

**适用条件**：
- 项目有（或能快速建立）测试框架
- 使用主流模型（GPT-4+、Claude 3+），已内化 TDD 知识
- 需要多个 Agent session 迭代的中长期项目

**失效条件**：
- 纯探索性原型（不关心正确性，只关心可行性评估）
- 轻量/领域特化模型，可能不理解"red/green TDD"缩写
- 测试成本极高的领域（如硬件 I/O、外部 API 密集交互）

---

## 非显见洞见

### 洞见 1：Agent 会写"通过语法检查"的代码，而不是"被执行过"的代码

- **洞见**：Agent 的置信度来自"代码在语义上合理"，而不是"代码曾经运行"
  - → 所以：静态代码审查（甚至你自己读代码）不能替代运行测试
  - → 所以：Agent 输出的代码在有测试之前，本质上是"高质量的推测"
  - → 因此可以：**把"测试运行成功"作为 Agent 任务的 Definition of Done，而非"代码看起来正确"**

### 洞见 2：跳过红阶段会使整个 TDD 退化成"validation theater"

- **洞见**：如果让 Agent 先写实现，再写测试（不确认失败），测试只会验证实现路径，而不是需求规约
  - → 所以：这样的测试是"实现的镜子"，而不是"需求的证明"
  - → 所以：未来重构时，这类测试会误报（实现变了 → 测试失败，即使行为是正确的）
  - → 因此可以：**在 Agent 的任务描述中显式要求"输出：失败测试的运行日志"作为红阶段的审计证据**

### 洞见 3：测试文件是 Agent 的"项目地图"，优先级高于 README

- **洞见**：Agent 被问到已有功能时，会主动读测试文件——因为测试密度高、上下文具体、无模糊性
  - → 所以：测试套件的完整度决定了 Agent 对项目的理解上限
  - → 所以：没有测试的遗留代码对 Agent 来说是"暗物质"——可以感知到它的引力（被调用），但无法理解它的结构
  - → 因此可以：**为遗留代码补写测试（即使没有 TDD），优先级高于写文档，因为测试对 Agent 的信息密度远高于 README**

### 洞见 4："Four-word prompt"是 Prompt Compression 的核心工程技术

- **洞见**：`Use red/green TDD` 等四词短语的威力来自模型训练数据中对该概念的密集覆盖
  - → 所以：你不需要在每次 prompt 里重新解释 TDD——模型用"最佳实践版本"填充
  - → 所以：让 Agent 使用自己内化的最佳实践，比你在 prompt 里手动描述效果更好（你的描述可能不如训练数据的样本质量高）
  - → 因此可以：**建立个人的"四词提示词词典"，把常见工程纪律压缩成 3-6 词的标准短语，储存在 `snippets/` 中**

---

## 反模式与陷阱

- **陷阱：跳过红阶段**  
  写完测试直接开始实现，没有确认测试先失败。  
  → 正确做法：强制要求 Agent 在实现前输出测试失败日志（作为 checkpoint）

- **陷阱：测试写在实现之后**（Post-hoc testing）  
  让 Agent 先写实现，再补测试。测试会"拥抱"实现的所有缺陷。  
  → 正确做法：任务描述中明确"先写测试，输出失败日志，再写实现"

- **陷阱：把 Agent PR 的 PR description 当 ground truth**  
  Agent 写的 PR 描述听起来自信而专业，但作者没读过就发出去。  
  → 正确做法：PR 描述必须是你亲自读过、验证过的内容

- **陷阱：测试覆盖太宽松**（Vacuous Tests）  
  断言总是为真（`assert True`、`assert result is not None`），红阶段永远不会出现。  
  → 正确做法：测试断言应该是会因错误实现而失败的具体行为

- **陷阱：只在新功能上用 TDD，不在接手旧项目时用 "First Run the Tests"**  
  Agent 没有运行现有测试，以为项目"无副作用"，结果改坏了已有功能。  
  → 正确做法：每次新 session 第一件事是 `Run the tests`，建立 baseline

---

## 与现有知识库的连接

- 关联 `python/mini_symphony.py`：编排器在分发子任务时可以在 TASK 描述里强制插入 `Use red/green TDD`，将测试纪律系统化注入所有子 agent 任务（而不依赖人工记忆）
- 关联 `python/sandbox_execute.py`：沙盒执行器可以在 Agent 实现完成后自动运行测试，把"测试通过/失败"作为任务状态的判断依据，实现自动化的"绿阶段确认"
- 关联 `analysis/simon-willison-agentic-patterns.md`：本文是该综合文档中 Red/Green TDD 章节的深化版本，补充了蕴含链、反模式细化和交叉想法
- 关联 `analysis/simon-willison-code-is-cheap.md`："代码现在很便宜"的成本模型反转与测试的关系——当实现成本趋零，测试的"价值/成本"比变得极高，测试从"昂贵的可选项"变成"零额外成本的必需品"
- 关联 `templates/WORKFLOW.md.template`：WORKFLOW 模板可以在 Agent 任务描述里默认包含 TDD 指令，让每个任务自动继承测试纪律

---

## 衍生项目想法

### 想法 1：Agent 任务编排的"测试门控"（Test Gate）

**来源组合**：[Red/Green TDD（本次）] + [`python/mini_symphony.py`（已有 KB）]

**为什么有意思**：mini_symphony.py 目前的任务状态只有"成功/失败/重试"，但没有区分"实现完成"和"测试通过"。在编排器里插入一个 Test Gate——Agent 完成实现后自动运行测试，只有全绿才能标记任务为完成，否则自动触发第二轮修复循环——可以在不改变 prompt 的情况下，把测试纪律注入所有 Agent 任务。

**最小 spike**：修改 `mini_symphony.py`，在任务完成判断逻辑里加一步 `subprocess.run(["uv", "run", "pytest"])` ，exit code 非零则将任务状态改为 `test_failed`，并把测试输出重新注入 Agent 上下文触发修复。预计 2-3 小时内可验证。

---

### 想法 2：个人"四词提示词词典" (Prompt Compression Cheatsheet)

**来源组合**：[Prompt Compression 洞见（本次）] + [`python/snippet_manager.py`（已有 KB CLI 搜索）]

**为什么有意思**：Simon 在这篇文章中隐式揭示了一类高价值技巧——把完整的工程纪律压缩成 3-6 个词的标准短语（`red/green TDD`、`run the tests`）。系统地收集这类"压缩提示词"，配合 snippet_manager.py 的自然语言搜索，可以在写 prompt 时快速调出正确的"纪律触发词"，形成个人的 prompt engineering 知识库。

**最小 spike**：在 `snippets/` 目录下创建 `prompt-compression-cheatsheet.md`，收录 10-15 个类似短语（`red/green TDD`、`think step by step`、`rubber duck this`、`YAGNI`、`DRY`……），用 snippet_manager.py 验证自然语言检索效果（如查询"测试驱动开发"能否命中 `red/green TDD`）。1 天内可完成。

---

### 想法 3：遗留代码的"Agent 地图测试"（Legacy Mapping Tests）

**来源组合**：[测试是 Agent 项目地图的洞见（本次）] + [`analysis/pi-context-engineering.md`（已有 KB）]

**为什么有意思**：pi-context-engineering.md 揭示了 coding agent 如何构建项目上下文。本次洞见说测试是 Agent 读取项目最高效的入口。两者结合暗示了一个 Legacy Codebase 的现代化路径：不是先重写代码，而是**先用 Agent 为遗留代码生成覆盖测试**（characterization tests——描述"现在的行为"而非"应该的行为"），把 Agent 对遗留代码的理解固化成可执行规约，再在此基础上安全地重构。

**最小 spike**：选取 CodeSnippets 中一个没有测试的 snippet（如 `python/fts5_fuzzy_search.py`），用 prompt `Generate characterization tests for this code — tests that document its current behavior, not ideal behavior. Use red/green TDD for any new behavior.`，观察 Agent 能否生成有意义的覆盖测试。预计 1-2 小时内可验证。
