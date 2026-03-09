# "First Run the Tests" 精读 — Agentic Engineering Patterns

**来源**: [First run the tests — Agentic Engineering Patterns](https://simonwillison.net/guides/agentic-engineering-patterns/first-run-the-tests/)
**扩展来源**:
- [Red/green TDD](https://simonwillison.net/guides/agentic-engineering-patterns/red-green-tdd/)
- [Agentic manual testing](https://simonwillison.net/guides/agentic-engineering-patterns/agentic-manual-testing/)
**日期**: 2026-07-15
**标签**: testing, coding-agents, agentic-engineering, ai-assisted-programming, context-engineering, prompt-engineering

---

## 30秒 TL;DR

> "First Run the Tests" 是一个四词提示词，在每次新的 Agent session 开始时执行测试套件。它实际上是三个信号的组合：**能力探测**（迫使 agent 定位测试套件）、**规模校准**（测试数量 ≈ 项目复杂度代理指标）、**心态注入**（运行过测试的 agent 后续行为显著不同）。与 Red/Green TDD 构成互补对称：一个解决"新功能开发"，一个解决"接手已有项目"。

---

## 概念总览

| 概念/模式 | 核心思想 | 适用场景 |
|---------|---------|---------|
| First Run the Tests | Session 开始先运行测试套件 | 每次新 session 接手已有项目 |
| 能力探测 (Capability Discovery) | 迫使 agent 主动找到"如何运行测试"而非假设 | 任何 agent 接手已有代码库 |
| 测试数量即复杂度代理 | 测试数量给 agent 校准项目规模的粗粒度信号 | 大型/遗留项目 |
| 心态注入 (Mindset Injection) | 四词短语触发 agent 后续行为改变 | 任何 agent 工作流 |
| Agentic Manual Testing | 自动化测试之外的额外手动探索验证 | 有 UI/API/边界用例的项目 |
| python -c 探索模式 | 用 REPL 字符串快速探索函数边界用例 | Python 库开发 |
| Showboat exec 防作弊 | 记录命令+真实输出，防止 agent 伪造结果 | 需要记录测试证据的项目 |

---

## 深读

### 1. "First Run the Tests" 的三层信号

Simon 列出了这个四词提示词的多重用途，但值得把它们拆开来看：

**信号一：能力探测（Capability Discovery）**

> "It tells the agent that there is a test suite and forces it to figure out how to run the tests."

这里有个微妙的区别：不是"帮助 agent 找到测试"，而是**迫使** agent 主动找到测试。"让 agent 自己找"和"告诉 agent 测试在哪"在行为上导致截然不同的后续表现——自己找到的测试路径，agent 更可能在后续操作中自发使用它。

**信号二：规模校准（Scale Calibration）**

> "Most test harnesses will give the agent a rough indication of how many tests they are. This can act as a proxy for how large and complex the project is."

这是一个间接信号——`247 tests passed` 和 `3 tests passed` 会让 agent 对项目复杂度建立完全不同的估计，进而影响它在后续工作中采取的谨慎程度和覆盖范围。

**信号三：心态注入（Mindset Injection）**

> "It puts the agent in a testing mindset. Having run the tests it's natural for it to then expand them with its own tests later on."

这是最不直觉的一层：运行过测试的 agent，和没运行过的 agent，在后续添加新代码时有显著不同的行为——前者会自发地在修改后再次运行测试，并主动为新代码添加覆盖。

### 2. "旧借口不再成立"——成本模型的根本性反转

文章开篇直接反驳了不写测试的传统理由：

> "The old excuses for not writing them - that they're time consuming and expensive to constantly rewrite while a codebase is rapidly evolving - no longer hold when an agent can knock them into shape in just a few minutes."

这是"Code is Cheap" 成本模型反转在测试领域的具体体现：
- 以前：写测试有显著的时间成本，快速演进的代码库维护测试代价高
- 现在：agent 维护测试的成本趋零，测试的成本结构变了，"没时间写测试"这个理由失效

但同时文章明确测试对 Agent 代码来说是**必需品**，不是可选项：

> "They're also vital for ensuring AI-generated code does what it claims to do. If the code has never been executed it's pure luck if it actually works when deployed to production."

### 3. Agentic Manual Testing——自动化测试之上的第二层验证

相邻章节"Agentic Manual Testing"揭示了一个常被忽视的认识论问题：

> "Just because code passes tests doesn't mean it works as intended. Anyone who's worked with automated tests will have seen cases where the tests all pass but the code itself fails in some obvious way."

失败模式举例：
- 服务器启动时崩溃（但测试覆盖的是已启动状态的接口）
- 关键 UI 元素无法显示（但测试只覆盖了后端逻辑）
- 边界用例（tests 写的是快乐路径）

**三种手动测试机制：**

| 场景 | 工具 | 示例 prompt |
|------|------|------------|
| Python 库边界用例 | `python -c "..."` | `Try that new function on some edge cases using python -c` |
| Web API 探索 | `curl` | `Run a dev server and explore that new JSON API using curl` |
| Web UI 浏览器级验证 | Playwright / agent-browser / Rodney | `Start a dev server and then use uvx rodney --help to test the new homepage` |

### 4. Showboat 的防作弊设计意图

Showboat 的 `exec` 命令的存在是为了解决一个特定问题：

> "The exec command is the most important of these, because it captures a command along with the resulting output. This shows you what the agent did and what the result was, and is designed to discourage the agent from cheating and writing what it hoped had happened into the document."

这里揭示了一个 agent 行为的深层风险：agent 可以在文档中**写它预期会发生的事**，而不是真实记录了什么发生了。`exec` 的设计通过"运行命令并捕获真实输出"来防止这种"结果伪造"。

### 5. 测试套件作为 Agent 的"项目地图"

文章中的这句话密度极高：

> "Watch what happens when you ask Claude Code or similar about an existing feature - the chances are high that they'll find and read the relevant tests."

这意味着测试文件是 agent 理解项目行为的**首选信息源**，优先于 README、注释、甚至源码本身——因为测试同时包含了：接口形状、期望行为、边界用例、真实的调用示例。

---

## 心智模型

> **"运行测试"不仅是验证手段，更是向 Agent 传递信息的仪式**——它向 agent 传递了项目的规模信号、测试文化信号，并激活 agent 内置的"测试纪律"行为模式。

**适用条件**：
- 项目有任何形式的自动化测试套件（哪怕只有几个）
- 使用主流 Coding Agent（Claude Code、Cursor、Copilot 等）
- 需要多个 session 迭代的项目（一次性脚本不适用）

**失效条件**：
- 全新项目，测试套件尚不存在（此时应先用 Red/Green TDD 建立）
- 测试套件极慢（运行一次需要数分钟），session 开始时的代价过高
- 纯探索性原型，不关心正确性证明

---

## 非显见洞见

### 洞见 1：Agent 的"测试心态"是可以被四词短语激活的行为状态

- **洞见**：`Run the tests` 不只是一条指令，它会激活 agent 内部的一套与测试相关的行为模式——后续操作中更可能自发运行测试、主动覆盖新代码
  - → 所以：Agent 在 session 中的行为不完全由 prompt 决定，还受 session 内的**历史操作序列**影响
  - → 所以：通过精心设计 session 的开场序列，可以系统性地"预装"期望的 agent 行为模式
  - → 因此可以：**把高价值操作（`Run the tests`、`Check git log`、`Read WORKFLOW.md`）标准化为每次 session 的固定开场仪式，像"热机"一样激活 agent 的正确工作姿态**

**蕴含链延伸**：
```
激活行为模式 → 意味着 session 的前 5-10 个操作极不成比例地影响整个 session 质量
→ 所以：设计"session 开场仪式"是 agentic 工程中被严重低估的杠杆点
→ 因此可以：为不同类型任务（新功能开发 / 接手旧项目 / debug / 重构）设计对应的开场仪式模板
```

### 洞见 2：测试数量是项目复杂度的低成本信号——但它告诉 agent 的不只是数量

- **洞见**：`247 tests passed in 3.2s` 这一行输出包含多个维度的信息：测试数量（规模）、运行时间（是否有大量 I/O 或等待）、通过率（是否有已知问题）
  - → 所以：Agent 看到的测试输出摘要是项目健康状态的压缩快照
  - → 所以：刻意保持测试套件绿色（而不是带着 skip/xfail 凑合）对 agent 的项目理解有直接影响
  - → 因此可以：**把"测试套件全绿"作为 agent session 开始的先决条件，带着失败测试开始 session 会让 agent 的基线状态紊乱**

**隐含假设**：测试套件运行足够快（< 30s），否则 session 开始成本过高。

### 洞见 3：自动化测试通过 ≠ 功能正确运行——这是结构性的认识论盲区

- **洞见**：测试覆盖的是测试作者**想到的**场景，不是真实世界**会发生**的场景
  - → 所以：通过所有测试的代码依然可能在启动、UI 渲染、并发、真实网络等层面崩溃
  - → 所以：测试套件是"已知场景验证器"，而非"正确性证明"
  - → 因此可以：**手动测试（Agentic Manual Testing）是自动化测试的必要补充，不是竞争替代——两者覆盖不同的失效空间**

**蕴含链延伸**：
```
自动化测试覆盖"已知场景" + 手动测试覆盖"真实使用路径"
→ 两者合并才构成较完整的验证覆盖
→ 对 coding agent 来说，"agentic manual testing"让 agent 自行执行手动测试，
  把人工手动测试的成本也降低到接近零
→ 因此可以：在 agent 任务的 Definition of Done 中同时要求：① 自动化测试全绿 ② agent 自行完成手动探索（python -c / curl / Playwright），不能只满足其中之一
```

### 洞见 4："Bias toward testing" 是 Agent 的固有倾向，可以被强化但也可能被稀释

- **洞见**：Simon 指出 "Agents are already biased towards testing, but the presence of an existing test suite will almost certainly push the agent into testing new changes"
  - → 所以：这个倾向是概率性的，不是确定性的——没有测试套件的项目，这个倾向会被稀释
  - → 所以：测试套件的存在形成正反馈：有测试 → agent 更可能写新测试 → 测试套件更健康 → 下个 session 的 agent 更可能写测试
  - → 因此可以：**对于全新项目，尽早用 Red/Green TDD 建立哪怕几个基础测试，可以"引导"后续所有 session 的 agent 延续测试文化，比在有大量代码后才补测试成本低得多**

---

## 反模式与陷阱

- **陷阱：带着失败测试开始 session**
  测试套件有未修复的失败项，直接开新 session。Agent 会把失败状态当作 baseline，无法区分"原有失败"和"我引入的失败"。
  → 正确做法：session 前先确保测试全绿，或明确告知 agent "以下测试已知失败，忽略它们"

- **陷阱：只做自动化测试，跳过手动探索**
  自动化测试全部通过后认为功能完成，没有让 agent 做手动探索（或自己做手动测试）。
  → 正确做法：在 Definition of Done 中同时包含"自动化测试通过 + 手动探索验证"，可以用 `python -c` / `curl` / Playwright 等工具

- **陷阱：Showboat 文档中 agent 描述而非执行**
  让 agent 写测试记录但使用 `note` 命令（自由描述）而非 `exec` 命令（真实运行+捕获输出），导致文档是 agent 预期的结果而非实际结果。
  → 正确做法：对所有"我验证了 X"的声明，要求 agent 用 `showboat exec` 提供真实输出作为证据

- **陷阱：测试套件太慢，放弃 "First Run the Tests"**
  测试运行需要数分钟，认为 session 开始不值得运行全量测试，转而跳过。
  → 正确做法：把测试套件按速度分层（快速 smoke tests + 完整 test suite），session 开始时只跑 smoke tests

- **陷阱：只在新功能 session 中使用测试纪律，debug session 中跳过**
  Debug 任务觉得"只是找问题"不需要测试，结果 fix 了问题但没有固化为回归测试。
  → 正确做法：发现并 fix 的 bug，让 agent 先把 bug 场景写成失败测试（Red），再 fix（Green），确保不会回归

---

## 与现有知识库的连接

- **关联 `analysis/simon-willison-red-green-tdd.md`**：本文是对 Red/Green TDD 精读的深化——Red/Green TDD 解决"新功能开发的测试纪律"，First Run the Tests 解决"接手已有项目的测试基线"，两者是测试纪律体系的互补对称。已有文档中对 "First Run the Tests" 有提及但未深度展开"三层信号"模型和 Agentic Manual Testing 的认识论分析。

- **关联 `analysis/simon-willison-agentic-patterns.md`**：本文所属的 Agentic Engineering Patterns 系列综合文档，其中 "First Run the Tests" 章节已有概要，本文提供了更深层的非显见洞见分析，可作为查询时的详细版本补充。

- **关联 `python/mini_symphony.py`**：编排器目前的任务完成判断缺少测试门控。可以在 session 初始化阶段加入 "First Run the Tests" 步骤，把测试运行的基线状态（通过数、失败数）记录到任务上下文，让后续 agent 在完成任务后能对比变化，自动识别是否引入了回归。

- **关联 `python/sandbox_execute.py`**：沙盒执行器在执行 agent 代码时，可以组合"自动化测试"和"python -c 边界探索"两种验证，分别在 stdout 中捕获两类证据，构成更完整的验证管道。

- **关联 `analysis/simon-willison-code-is-cheap.md`**：成本模型反转的直接推论——当代码成本趋零，"维护测试太贵"的借口同时失效。两篇文章构成互锁论证：代码便宜了 → 测试现在可以无处不在 → 没有测试的 agent 代码是不可接受的"草稿"。

- **关联 `analysis/pi-context-engineering.md`**：pi agent 的 context engineering 决策中包含了如何让 agent 高效获取项目上下文。"First Run the Tests"是一个零成本的 context injection 手段——测试输出天然携带了项目规模、健康状态、功能覆盖等信息，是 context 效率极高的信息源。

---

## 衍生项目想法

### 想法 1：Session 开场仪式生成器（Session Bootstrap Templates）

**来源组合**：[First Run the Tests 的"心态注入"洞见（本次）] + [`templates/WORKFLOW.md.template`（已有 KB）]

**为什么有意思**：不同类型的 agent 任务需要不同的"热机序列"来激活正确的工作姿态——接手旧项目的 session 需要 `Run the tests`，debug session 需要 `Show me the recent git log`，新功能 session 需要 `Use red/green TDD`。把这些序列模板化，嵌入 WORKFLOW.md，可以让每个任务自动携带正确的开场仪式，而不依赖工程师的记忆。

**最小 spike**：在 `templates/` 目录下创建 `session-bootstrap.md`，为 4 种 session 类型（新功能 / 接手项目 / debug / 重构）各设计一个 5-7 步的开场序列 prompt，测试是否能显著改善 agent 在对应任务类型中的行为质量。1 天内可完成。

---

### 想法 2：双层验证管道（Two-tier Verification Pipeline）

**来源组合**：[自动化测试 + Agentic Manual Testing 双层验证的洞见（本次）] + [`python/sandbox_execute.py`（已有 KB）]

**为什么有意思**：sandbox_execute.py 目前只提供了代码执行的隔离容器，没有区分"自动化测试运行"和"手动探索执行"。在 mini_symphony.py 的任务完成判断中加入一个两阶段验证步骤：阶段一运行 `pytest`（结构化验证），阶段二运行 agent 自选的 `python -c` 探索（非结构化探索），两阶段都通过才能标记任务完成——这个模式把 Simon 的手动测试建议系统化了，而不依赖工程师在每个任务里手动提示。

**最小 spike**：在 `mini_symphony.py` 的任务完成 hook 中增加 `agentic_manual_test` 步骤，prompt 内容为 `Try the new code on 3 edge cases using python -c and report results`，让 agent 自主选择测试什么。运行后观察 agent 是否能发现自动化测试未覆盖的问题。预计半天实验。

---

### 想法 3：遗留代码的 Showboat 验证报告生成器

**来源组合**：[Showboat exec 防作弊设计（本次）] + [`analysis/pi-context-engineering.md`（已有 KB）的 context 构建决策]

**为什么有意思**：pi-context-engineering.md 揭示了 coding agent 如何压缩和选择上下文。Showboat `exec` 的防作弊设计意图（强制真实输出）和 pi 的 context 高效性要求结合，暗示了一个用途：为遗留代码自动生成"行为快照文档"——让 agent 对遗留代码的每个公共接口执行 `showboat exec python -c "<示例调用>"`，捕获真实的输入输出对，形成一份行为规约文档。这份文档比 README 对未来 agent session 更有价值（高信噪比、可执行）。

**最小 spike**：选择 `python/fts5_fuzzy_search.py`（无测试的现有 snippet），prompt `Use showboat to create a behavioral snapshot of this module: for each public function, use showboat exec to run 2-3 example calls with python -c and capture the real output`，观察生成文档是否可以作为后续 agent session 的有效上下文。预计 1-2 小时。
