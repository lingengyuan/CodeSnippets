# Simon Willison — Linear Walkthroughs & Agentic Manual Testing 精读

**来源**:
- [Linear Walkthroughs](https://simonwillison.net/guides/agentic-engineering-patterns/linear-walkthroughs/) — Agentic Engineering Patterns
- [Agentic Manual Testing](https://simonwillison.net/guides/agentic-engineering-patterns/agentic-manual-testing/) — Agentic Engineering Patterns
- [Interactive Explanations](https://simonwillison.net/guides/agentic-engineering-patterns/interactive-explanations/) — Agentic Engineering Patterns
- [Showboat GitHub](https://github.com/simonw/showboat)

**日期**: 2026-03-10
**标签**: agentic-engineering, showboat, cognitive-debt, linear-walkthrough, manual-testing, playwright, vibe-coding

---

## 30秒 TL;DR

> Vibe coding 产生了大量"黑盒代码"——能跑但你不懂。Simon 提出的解法是一个三级递进体系：先让 agent 生成**线性代码导读**（Linear Walkthrough），对还不直观的算法部分再让 agent 构建**交互式动画解释**（Interactive Explanation）；同时，用 agent **"手动"测试**（Manual Testing）替代单纯依赖自动化测试——用 Showboat 工具将测试过程变成可验证、可提交的文档。这整套体系的底层哲学是：**agent 写代码容易，理解代码和证明代码工作依然是人类（借助 agent）必须主动承担的责任。**

---

## 概念总览

| 概念/模式 | 核心思想 | 适用场景 |
|---------|---------|---------|
| Linear Walkthrough | 让 agent 读源码 + 用真实命令引用代码片段，生成结构化导读文档 | vibe coding 后、接手陌生代码库、遗忘自己写的代码 |
| Showboat | 专为 agent 设计的"可执行文档"工具：命令+输出双记录，防止 agent 捏造结果 | 代码讲解、手动测试记录、展示 agent 工作过程 |
| Agentic Manual Testing | 让 agent 自己测试代码：`python -c`、curl、Playwright/Rodney | 补充自动化测试盲区，尤其是 UI 层 |
| Cognitive Debt | 代码能跑但工程师不理解——类比技术债，会减慢未来决策速度 | 识别何时需要主动"偿还"理解欠债 |
| Interactive Explanation | 用动画 HTML 页面可视化算法执行过程 | 算法级别的"啊哈"理解，文字无法替代视觉直觉 |

---

## 深读

### 一、Vibe Coding 产生的理解欠债

Simon 的触发场景：用 Claude Code + Opus 4.6 **vibe coded** 了一个 SwiftUI 幻灯片演示 App（Showboat），整个过程"没怎么看代码"，事后连自己写（让 agent 写）的代码都不知道怎么工作。

这揭示了 Vibe Coding 的一个结构性问题：

```
Vibe Coding 特性：
  ✅ 产出速度极快
  ✅ 代码能跑
  ❌ 工程师理解程度 ≈ 0
  ❌ 调试/扩展时无从入手
```

Simon 提出的"认知债务（Cognitive Debt）"概念：

> "当我们失去对 agent 写的代码如何工作的认知，我们就积累了认知债务。对于简单的 CRUD 无所谓；对于应用的核心逻辑，这会使我们无法自信地推理，让规划新功能更难，最终和技术债一样减慢进展。"

---

### 二、Linear Walkthrough 模式详解

#### 完整 Prompt 模板

Simon 的实际 Prompt：

```
Read the source and then plan a linear walkthrough of the code
that explains how it all works in detail

Then run "uvx showboat --help" to learn showboat - use showboat
to create a walkthrough.md file in the repo and build the walkthrough
in there, using showboat note for commentary and showboat exec plus
sed or grep or cat or whatever you need to include snippets of code
you are talking about
```

拆解每个设计决策：

| Prompt 片段 | 设计意图 |
|------------|---------|
| `plan a linear walkthrough` | 让 agent 先思考整体结构，而非立即开写（先规划后执行）|
| `run "uvx showboat --help"` | 让 agent 自学工具，不需要预先安装；`--help` 输出专为 agent 教学设计 |
| `showboat note for commentary` | 分离"主观解释"和"客观代码引用"两种内容 |
| `showboat exec plus sed/grep/cat` | **关键设计**：强制 agent 用工具读实际文件，而非"凭记忆"写代码片段 |

#### 为什么必须用 `sed/grep/cat` 而不是手动复制

```
风险：agent 复制代码片段时可能：
  - 引入细微改动（"幻觉"）
  - 复制错误版本
  - 编造不存在的代码

对策：showboat exec + cat/grep/sed 记录的是：
  1. 实际执行的命令（命令本身可读）
  2. 该命令的真实输出（不可伪造）

→ 文档的可信度 = 现场直播，而非事后回忆
```

#### 产出效果

Simon 读了 agent 生成的 SwiftUI walkthrough 后的反馈：

> "我学到了大量关于 SwiftUI app 结构的知识，顺带吸收了一些扎实的 Swift 语言细节——仅仅通过阅读这份文档。"

---

### 三、三级理解递进体系

当 Linear Walkthrough 不够时，还有下一级：

```
Level 1: 对话提问（最快，理解最浅）
    ↓ 当你需要结构化文档时
Level 2: Linear Walkthrough（Showboat 生成 walkthrough.md）
    ↓ 当你仍然无法直觉理解某个算法时
Level 3: Interactive Explanation（动画 HTML 可视化）
```

#### Level 3 实例：Archimedean 螺旋词云

Simon 让 Claude Opus 4.6 构建了一个词云算法的动画解释，核心 Prompt：

```
Fetch https://raw.githubusercontent.com/simonw/research/refs/heads/main/rust-wordcloud/walkthrough.md
to /tmp using curl so you can read the whole thing

Inspired by that, build animated-word-cloud.html - a page that accepts pasted text
(which it persists in the `#fragment` of the URL such that a page loaded with that `#`
populated will use that text as input and auto-submit it) such that when you submit
the text it builds a word cloud using the algorithm described in that document but
does it animated, to make the algorithm as clear to understand.
Include a slider for the animation which can be paused and the speed adjusted or
even stepped through frame by frame while paused.
At any stage the visible in-progress word cloud can be downloaded as a PNG.
```

注意 Prompt 中的几个"隐式工程要求"：
- `#fragment` URL 持久化：不刷新即保留状态（不需要后端）
- "step through frame by frame"：调试友好的交互控件
- "download as PNG"：产出可分享的静态产物

---

### 四、Agentic Manual Testing 详解

#### 核心原则

> **"永远不要假设 LLM 生成的代码能工作，直到代码被实际执行。"**

自动化测试 ≠ 代码工作的证明：
- 测试可能遗漏 UI 层问题
- 服务器可能在启动时就崩溃
- 关键 UI 元素可能根本没渲染
- 测试用例可能没有覆盖真实使用路径

#### 机制一：`python -c`（Python 库）

```bash
# 提示词
Try that new function on some edge cases using `python -c`

# agent 会执行类似
python -c "
from mymodule import process_data
result = process_data(edge_case_input)
print(result)
"
```

优点：
- 不需要创建临时文件
- 直接在当前环境中测试
- agent 天生熟悉这个 trick（有时不提示也会用）

#### 机制二：`curl`（Web API）

```bash
# 提示词
Run a dev server and explore that new JSON API using `curl`

# "explore" 这个词让 agent 主动尝试多种端点和参数组合
```

关键词选择：`explore`（探索）vs `test`（测试）——"explore"更倾向于生成覆盖更广的测试用例。

#### 机制三：Playwright / Rodney（Web UI）

**Playwright**（微软出品，功能最全）：
```bash
# 简单触发
Test that with Playwright
# agent 自行选择语言绑定或使用 playwright-cli
```

**Rodney**（Simon 自建，专为 agent 优化）：
```bash
# Simon 的典型 Prompt
Start a dev server and then use `uvx rodney --help` to test the new homepage,
look at screenshots to confirm the menu is in the right place
```

三个技巧叠加：
1. `uvx rodney --help` → 自动安装 + 自学工具（无需预装）
2. `--help` 专为 agent 设计，包含所有使用方法
3. `look at screenshots` → 提示 agent 用视觉能力评估 UI 正确性

Rodney 能力：JavaScript 执行、滚动、点击、输入、读取 accessibility tree、截图。

#### Showboat 在手动测试中的角色

```bash
# Prompt 模板
Run `uvx showboat --help` and then create a `notes/api-demo.md` showboat
document and use it to test and document that new API.
```

测试 + 文档 = 同一个产出物：

```
[测试结果] ──记录──→ [Showboat 文档]
     ↑                    ↓
  可验证                可提交到 repo
  （exec 捕获）         （作为测试证明）
```

**`exec` 命令是核心**：记录了命令 + 输出，阻止 agent 写它"希望发生"的事而非"实际发生"的事。

---

### 五、Showboat 工具完整解剖

#### 设计哲学

> Showboat 创建"可执行的演示文档"（executable demo documents）——混合解说、可执行代码块和捕获输出。文档本身是可读文档，也是可复现的工作证明。验证者可以重新执行所有代码块确认输出仍然一致。

这是"**可重现文档**"（Reproducible Documentation）的具体实现。

#### 完整命令集

```bash
showboat init <file> <title>          # 创建新文档
showboat note <file> [text]           # 追加说明文字（或 stdin）
showboat exec <file> <lang> [code]    # 执行命令，记录命令+输出（或 stdin）
showboat image <file> <path>          # 插入图片（自动复制文件）
showboat image <file> '![alt](path)' # 带 alt text 的图片
showboat pop <file>                   # 删除最近一条记录（命令失败时回滚）
showboat verify <file>                # 重新执行所有代码块，diff 输出
showboat extract <file>               # 输出重建文档所需的原始命令序列
```

#### 安装方式（为 agent 设计）

```bash
# 无需预装，直接用 uvx 运行
uvx showboat --help

# 或安装
uv tool install showboat
pip install showboat

# Go 原生
go install github.com/simonw/showboat@latest
```

注意：Showboat 是用 **Go** 写的，但通过 **PyPI** 分发（使用 `go-to-wheel` 工具）。这使得 agent 可以在任何 Python 环境中用 uvx 无缝使用，而不需要 Go 工具链。

#### 生成文档格式

````markdown
# Setting Up a Python Project

*2026-02-06T15:30:00Z*

First, let's create a virtual environment.

```bash
python3 -m venv .venv && echo 'Done'
```

```output
Done
```

```python3
print('Hello from Python')
```

```output
Hello from Python
```
````

#### `exec` 的特殊行为

```bash
# exec 将输出打印到 stdout，同时追加到文档
$ showboat exec demo.md bash "echo hello && exit 1"
hello
$ echo $?
1
# → agent 能看到输出，并知道命令失败了（exit code 1）
# → 失败记录仍然追加到文档
# → 用 showboat pop 可以删除这条失败记录
```

#### `verify` 命令（可重现性保证）

```bash
showboat verify demo.md
# 重新执行所有代码块，diff 实际输出 vs 记录输出
# 如果任何输出不同，退出 code 1
# 用 --output <file> 写出更新后的文档而不修改原文件
```

这让 walkthrough 文档成为一种"**活文档**"——可以随时验证其准确性。

#### 远程流式传输（隐藏特性）

```bash
export SHOWBOAT_REMOTE_URL=https://example.com/showboat?token=secret
# 每次 init/note/exec/image/pop 都会 POST 到这个 URL
# 实现：agent 工作进度的实时远程可视化
```

这个特性为构建"**agent 工作过程监控仪表盘**"提供了基础设施。

---

## 心智模型

### 模型一：代码导读的"防伪机制"

> **让 agent 引用代码，而不是复述代码。**

```
复述（高幻觉风险）：
  agent 从记忆中写 → 可能引入改动 → 文档与代码不一致

引用（低幻觉风险）：
  agent 执行 cat/grep/sed → 真实输出 → 文档与代码一致
```

**适用条件**：agent session 有文件系统访问权限（Claude Code、Codex 等）
**失效条件**：纯对话界面（无工具调用）；agent 没有读文件权限

### 模型二："认知债务"需要主动偿还

> 就像技术债一样，认知债务不会自动消失，只会越积越重，直到严重拖慢进展。

对于什么程度的代码"值得"偿还认知债务：
- 简单 CRUD：不值（猜一猜能知道）
- 核心算法：必须（不理解 = 不能合理规划新功能）
- UI 交互逻辑：视情况（是否会频繁修改）

**适用条件**：长期维护的代码库；需要在已有基础上迭代
**失效条件**：纯一次性脚本；对代码后续不关心

### 模型三：`--help` 设计为 agent 教学媒介

> 工具的 `--help` 输出应该包含 agent 使用它所需的一切信息，而不仅仅是面向人类的简短说明。

Simon 的 Rodney 和 Showboat 都遵循这个设计原则：
- help 文本包含完整的命令格式
- help 文本包含使用示例
- help 文本解释了关键的行为细节（如 exec 的 exit code 传递）

**适用条件**：工具的主要用户是 coding agent；工具通过 `uvx` 调用
**失效条件**：人类主要用户对详细 help 有抵触；help 文本太长导致 context 膨胀

---

## 非显见洞见

### 洞见 1：`uvx tool --help` 是自学习 agent 接口的标准范式

- **所以**：Showboat 和 Rodney 都设计成"通过 --help 教会 agent 使用自己"，不需要 agent 预先知道工具的存在
- **所以**：任何面向 agent 的 CLI 工具，`--help` 输出质量 = 工具被 agent 正确使用的概率
- **因此可以**：在自己的项目中，对任何会被 agent 使用的内部工具，将 `--help` 的设计提升到与 API 文档同等重要的地位；考虑专门为 agent 写 `--help-for-agent` 子命令输出更结构化的说明

---

### 洞见 2：Showboat 的 `exec` 命令是"反幻觉原语"

- **所以**：记录"我执行了什么命令、得到了什么输出"比记录"我认为发生了什么"有根本性的可信度差异
- **所以**：任何 agent 生成的文档，如果混合了"agent 的解释"和"实际执行结果"，后者有更高的信任权重
- **因此可以**：在 CI/CD 中引入 `showboat verify` 步骤，定期重新验证 agent 生成的演示文档是否还准确（随代码变更自动失效的活文档）

蕴含链：
```
exec 记录命令+输出
→ 所以：文档是"现场直播"而非"事后回忆"
→ 所以：verify 可以检测文档是否随代码过时
→ 因此可以：把 showboat verify 加入 CI，让导读文档像测试一样自动检验
```

---

### 洞见 3：动画解释 > 文字导读（对算法理解的阈值）

> "Archimedean 螺旋放置"——文字读了 N 遍，看一次动画就懂了。

- **所以**：存在一类理解的"阈值"，文字描述无论多详细都无法越过，但视觉动画可以
- **所以**：Frontier model（Opus 4.6 级别）现在能够构建有"品味"的解释性动画，这是新能力
- **因此可以**：对任何自己写过但记不清原理的算法（如 FTS5 的 trigram 索引、BK-tree 搜索），让 agent 构建一次动画解释 HTML；这比反复读代码更高效

---

### 洞见 4：Vibe Coding 的"结构性理解赤字"不是 bug，是必须主动管理的特性

- **所以**：接受 vibe coding 的速度优势，就意味着接受理解债务——这不是选择，是权衡
- **所以**：Linear Walkthrough 和 Interactive Explanation 是 vibe coding 工作流的**必要补充步骤**，而不是可选的后处理
- **因此可以**：在团队中建立规范："任何 vibe coded 的模块，上线前必须有 walkthrough.md"，将理解债务还清作为 Definition of Done 的一部分

---

### 洞见 5：手动测试 × agent 视觉能力 = 新的 UI 验证范式

> "看截图确认菜单在正确位置"——这句话的底层是：agent 有视觉能力 + Rodney 有截图能力 → agent 能做"眼看"测试

- **所以**：`agent.screenshot() + agent.vision_check()` 是一种全新的 UI 测试机制，不依赖 selector、不依赖 accessibility tree
- **所以**：长期困扰前端测试的"选择器脆弱性"问题，可以用视觉验证规避
- **因此可以**：对 UI 的"视觉正确性"（布局、颜色、相对位置）用 agent 视觉测试，对"功能正确性"（点击是否触发正确逻辑）用传统 Playwright

---

## 反模式与陷阱

- **陷阱：agent 手动复制代码片段到文档**
  → 描述：agent 从"记忆"中写代码片段，而不是从文件中读取，可能引入幻觉
  → 正确做法：明确 prompt 中说"use sed/grep/cat to include snippets"，强制引用

- **陷阱：只信任自动化测试，不做手动测试**
  → 描述：测试通过 ≠ 代码工作。服务可能无法启动，UI 可能无法渲染关键元素
  → 正确做法：让 agent 用 `python -c` / curl / Playwright 做一轮真实执行验证

- **陷阱：Interactive Explanation 跳过 Linear Walkthrough**
  → 描述：直接要求动画解释，agent 可能构建错误的算法可视化（因为没有准确理解代码）
  → 正确做法：先做 walkthrough，将 walkthrough.md 作为上下文传入 Interactive Explanation 的 prompt

- **陷阱：认知债务积累到无法管理**
  → 描述：每个 vibe coded 模块都有理解赤字，不处理会累积成"没人懂这个系统"
  → 正确做法：把 walkthrough.md 的生成纳入 PR 流程，而不是事后补救

- **陷阱：`showboat exec` 失败后不用 `pop` 清理**
  → 描述：失败的命令记录留在文档中，污染 walkthrough，让读者困惑
  → 正确做法：命令失败后立即 `showboat pop demo.md` 删除该记录，再重试正确命令

---

## 与现有知识库的连接

- 关联 `analysis/simon-willison-agentic-patterns.md`：本文是该分析的深度补充，专注于 Linear Walkthroughs + Manual Testing 两个模式的完整实现细节。原文件中 Section 4 已有简要覆盖，本文将其扩展为完整精读。

- 关联 `python/mini_symphony.py`：Symphony 编排器产生的子任务输出天然适合用 Showboat 记录——每个子任务的 `exec` 输出可以流入 Showboat 文档，形成"编排过程的可验证日志"。

- 关联 `python/sandbox_execute.py`：sandbox_execute 的设计原则（只有 stdout 进入 context）与 Showboat 的 `exec` 命令高度互补——前者控制 agent 执行环境，后者记录执行结果。两者组合可以构建"安全执行 + 防伪记录"的双重保障。

- 关联 `analysis/simon-willison-red-green-tdd.md`：Manual Testing 是 TDD 的互补（而非替代）——TDD 证明代码逻辑正确，Manual Testing（含浏览器自动化）证明用户体验正确。两者都可以用 Showboat 记录，形成完整的质量证明链。

---

## 衍生项目想法

### 想法一：Showboat 风格的 mini_symphony 执行日志

**来源组合**：[Showboat `exec` 记录机制] + [已有 `python/mini_symphony.py` 任务编排器]

**为什么有意思**：mini_symphony 目前每个子任务的执行结果只输出到 stdout，没有持久化的"工作证明"。如果在编排器中集成 Showboat 风格的日志——每个子任务的命令+输出双记录——就能得到：
- 整个编排过程的可重现文档
- 每个子任务是否"言行一致"的验证（verify 功能）
- 适合 code review 的"agent 工作报告"

**最小 spike**：修改 `mini_symphony.py`，在每次调用子 agent 前后，用 `showboat note` + `showboat exec` 将 prompt 和输出记录到 `logs/session-YYYYMMDD.md`。一天内可以完成，验证效果：`showboat verify logs/session-YYYYMMDD.md` 是否能复现所有非交互步骤。

---

### 想法二：`--help-for-agent` 标准子命令

**来源组合**：[Simon 的"--help 设计为 agent 教学媒介"原则] + [已有 `python/sandbox_execute.py` 工具体系]

**为什么有意思**：当前 CLI 工具的 `--help` 是为人类设计的（简洁、分组、颜色）。但 agent 需要的 help 信息不同：完整的参数类型说明、所有子命令、使用示例（含 edge case）、exit code 语义。如果建立一个"agent-help"约定，工具可以输出 JSON 或结构化 Markdown，agent 解析效率更高，而且可以根据 agent 的能力动态生成（比如告诉 agent"你可以用 vision 能力处理图片输出"）。

**最小 spike**：给 `sandbox_execute.py` 增加一个 `--help-agent` 标志，输出 JSON 格式的完整 API 说明（包含所有参数的类型、默认值、示例）。测试：将这个 JSON 直接注入 agent prompt，看 agent 使用正确率是否高于普通 `--help` 文本。

---

### 想法三：FTS5 算法动画解释 HTML

**来源组合**：[Interactive Explanation 模式] + [已有 `python/fts5_fuzzy_search.py` 三层模糊搜索]

**为什么有意思**：`fts5_fuzzy_search.py` 实现了三层搜索（Porter 词干 → trigram 子串 → Levenshtein 纠错），这个级联搜索的工作机制对使用者来说是黑盒。一个动画 HTML 可以：
1. 展示同一个查询词如何经过三层过滤逐步缩小候选集
2. 让用户看到 trigram 索引的实际分解过程
3. 可视化 Levenshtein 距离计算的矩阵

对于打算基于此 snippet 构建搜索功能的人，这比读代码更有价值。

**最小 spike**：prompt Claude Opus 4.x：先 fetch `fts5_fuzzy_search.py`，再生成 `fts5-explainer.html`——输入一个查询词，动画展示三层搜索的过滤过程（可以 mock 数据，不需要真实 SQLite 连接）。预计 1-2 小时，结果存入 `html-tools/fts5-explainer.html`。

---

### 想法四：Showboat verify 的 CI 集成模板

**来源组合**：[Showboat `verify` 命令（可重现性验证）] + [已有 `templates/WORKFLOW.md.template`]

**为什么有意思**：`showboat verify` 可以像 `pytest` 一样成为 CI 中的质量门控——如果 agent 生成的 walkthrough 中有任何命令输出变了，CI 失败，强制更新文档。这创造了一种新型"活文档"机制：文档和代码的一致性由机器保证而非人工维护。

**最小 spike**：在 `templates/` 目录下增加 `.github/workflows/verify-walkthroughs.yml` 模板——找到 `analysis/` 目录下所有 `.md` 文件，筛选含 `showboat-id:` 注释的（Showboat 生成的），运行 `uvx showboat verify`，失败则 CI 报红。一天内可以写出并在本 repo 试跑。

---

## 提示词速查

### Linear Walkthrough（基础版）

```
Read the source and then plan a linear walkthrough of the code
that explains how it all works in detail.

Use showboat to create a walkthrough.md file and build the walkthrough
in there, using showboat note for commentary and showboat exec plus
sed or grep or cat or whatever you need to include snippets of code
you are talking about.

Run "uvx showboat --help" first to learn how to use showboat.
```

### Interactive Explanation（动画版）

```
Fetch [walkthrough.md URL] to /tmp using curl so you can read the whole thing.

Build animated-[topic].html - a self-contained page that visualizes
[specific algorithm/mechanism] step by step using canvas animations.
Include controls: play/pause, speed slider, frame-by-frame stepping.
The page should persist its state in the URL #fragment.
```

### Agentic Manual Testing（综合版）

```
Run `uvx showboat --help` and then create a `notes/[feature]-demo.md`
showboat document and use it to test and document [the new feature]:

1. Start a dev server
2. Test the API with curl, exploring different endpoints and edge cases
3. Run `uvx rodney --help` and test the UI visually, looking at screenshots
4. If you find issues, fix them with red/green TDD

Document everything in the showboat file.
```

### `python -c` 边界测试

```
Try that new function on these edge cases using `python -c`:
- [edge case 1]
- [edge case 2]
- [edge case 3]
```

---

## 参考链接

- [Showboat GitHub](https://github.com/simonw/showboat) — 可执行文档工具
- [Rodney GitHub](https://github.com/simonw/rodney) — agent 浏览器测试工具（Chrome DevTools Protocol）
- [agent-browser by Vercel](https://agent-browser.dev/) — Playwright CLI wrapper for agents
- [Animated Word Cloud 演示](https://tools.simonwillison.net/animated-word-cloud) — Interactive Explanation 实例
- [Simon 的 Showboat walkthrough 示例](https://github.com/simonw/present) — Linear Walkthrough 实际产出
- 关联已有文件：
  - [`analysis/simon-willison-agentic-patterns.md`](./simon-willison-agentic-patterns.md) — 该系列总览（含简要版 Linear Walkthrough）
  - [`analysis/simon-willison-red-green-tdd.md`](./simon-willison-red-green-tdd.md) — TDD 模式（与 Manual Testing 互补）
  - [`python/mini_symphony.py`](../python/mini_symphony.py) — 可集成 Showboat 日志的编排器
  - [`python/sandbox_execute.py`](../python/sandbox_execute.py) — 安全执行 + Showboat 记录的互补组合
