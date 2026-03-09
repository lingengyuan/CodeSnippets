# Simon Willison — LLM 0.26 工具支持精读

**来源**: [Large Language Models can run tools in your terminal with LLM 0.26](https://simonwillison.net/2025/May/27/llm-tools/)
**日期**: 2026-03-08
**标签**: llm-cli, tool-use, plugin-system, ReAcT, MCP

---

## 30秒 TL;DR

> LLM 0.26 把"工具调用"从 API 概念变成了命令行一等公民：任何带类型注解和 docstring 的 Python 函数都自动成为工具，无需写 JSON Schema。插件生态让工具可以 pip 安装和分发。ReAcT 循环由框架自动管理。MCP 集成路线图意味着整个 MCP 服务器生态将变成 `llm -T` 可调用的工具集。

---

## 概念总览

| 概念/模式 | 核心思想 | 适用场景 |
|---------|---------|---------|
| Function-as-Tool | 带类型注解+docstring的Python函数自动转为工具定义 | 快速原型、一次性脚本 |
| Toolbox 模式 | 构造函数传参配置有状态工具（`-T 'Plugin("config")'`） | 需要初始化参数的复杂工具 |
| ReAcT 循环 | model输出→框架执行→结果回注→继续推理 | 所有需要多步推理的任务 |
| 插件生态 | pip 安装即可扩展工具集 | 可复用、可分发的工具包 |
| `--functions` | 内联 Python 定义，无需打包 | 即席工具、测试 |

---

## 深读

### CLI 核心用法

```bash
# 基础：指定工具名
llm -T simple_eval 'Calculate 1234 * 4346 / 32414 and square root it' --td

# Toolbox：带构造参数的有状态工具
llm -T 'Datasette("https://datasette.io/content")' --td "What has the most stars?"

# 内联 Python 函数（即席工具）
llm --functions '
import httpx
def search_blog(q: str) -> str:
    "Search Simon Willison blog"
    return httpx.get("https://simonwillison.net/search/", params={"q": q}).text
' --td 'Three features of sqlite-utils' -s 'use Simon search'
```

`--td` / `--tools-debug` 显示每次工具调用和返回值，对调试至关重要。

### Python API

```python
import llm

def count_char_in_text(char: str, text: str) -> int:
    "How many times does char appear in text?"
    return text.count(char)

model = llm.get_model("gpt-4.1-mini")
chain_response = model.chain(
    "Rs in strawberry?",
    tools=[count_char_in_text],
    after_call=print          # 每次工具调用后的回调
)
for chunk in chain_response:
    print(chunk, end="", flush=True)
```

**关键**：`model.chain()` 自动管理整个 ReAcT 循环，支持 async/await 和 `asyncio.gather()` 并发执行多工具。

### 已发布插件

| 插件 | 功能 | 特点 |
|------|------|------|
| llm-tools-simpleeval | 安全 Python 表达式求值 | 沙箱执行 |
| llm-tools-quickjs | JavaScript 解释器 | 持久化状态 |
| llm-tools-sqlite | 本地 SQLite 只读查询 | 零配置 |
| llm-tools-datasette | 远程 Datasette 实例查询 | 网络访问 |

### 多步推理演示（Datasette 场景）

1. 模型按假设尝试查询 → 报错
2. 调用 `schema()` 查看实际表结构
3. 重新构造正确查询
4. 返回解释结果

这 4 步完全无需显式循环逻辑——框架自动管理。

---

## 心智模型

> **"工具 = 函数，函数 = 工具。"** LLM 0.26 的核心认知模型：不需要先学 JSON Schema，不需要理解 tool_use API，只需要写 Python 函数。

**适用条件**：本地执行环境，可信代码，Python 生态。
**失效条件**：多用户/服务器部署（`--functions` 无沙箱，执行任意 Python）；浏览器端（CORS 只有 Anthropic/xAI 支持）。
**在我的工作中如何用**：把 CodeSnippets 里的 `fts5_fuzzy_search.py` 封装成一个 llm 工具，让 `llm -T snippet_search "向量数据库"` 直接搜索本地知识库。

---

## 非显见洞见

- **洞见**：任何带类型注解的 Python 函数 = 工具，零仪式感，不需要写 JSON Schema
  - 所以：工具编写的摩擦趋近于零（5 分钟写一个工具 vs 过去的 30 分钟）
  - 所以：工具数量的瓶颈从"写工具"转移到"决定给模型哪些工具"
  - 因此可以：专注工具的**选择与组合**，而不是工具的**实现**；在会话开始时像选择上下文一样选择工具集

- **洞见**：MCP 8 天内获得 OpenAI、Anthropic、Mistral 三大厂商支持
  - 所以：MCP 协议标准化已成事实（不是某家厂商私有格式）
  - 所以：LLM CLI 作为 MCP 客户端后，整个 MCP 服务器生态等于免费获得
  - 因此可以：现在投资构建 MCP 服务器是杠杆化的——一次构建，所有 MCP 客户端（Claude Desktop、llm CLI、未来工具）都可用

- **洞见**：`--functions` 执行原始 Python，无任何沙箱
  - 所以：LLM 0.26 的"零摩擦"工具定义是以安全换取的
  - 因此可以：只在信任的本地环境用 `--functions`；分发给他人的工具必须用插件形式（可审查、可版本化）

---

## 隐含假设

- **假设：单用户本地执行**。若不成立（多用户平台），则工具隔离和 token billing 追踪都会失效——LLM 0.26 没有 per-request 的工具沙箱或 audit log。
- **假设：工具是无状态的或状态在工具内部管理**。若工具有副作用（写文件、发邮件），ReAcT 循环的重试行为可能造成重复执行——没有幂等保障。
- **假设：Python 函数签名足以描述工具**。若工具需要复杂的 enum 约束或 nested schema，纯 type hint 表达力不足，需要手写 JSON Schema。

---

## 反模式与陷阱

- **上下文膨胀陷阱**：每轮 ReAcT 把工具结果追加到 context——长工具链会耗尽 context window。`model.chain()` 没有自动截断。→ 正确做法：工具返回值要精简，只返回模型需要的信息，不返回原始 HTML 或完整 JSON。

- **`--functions` 在生产中使用**：无沙箱执行任意 Python，等同于给 LLM root 权限执行代码。→ 正确做法：生产场景用插件形式（经过代码审查、有版本控制）。

- **同步阻塞工具在 async 环境中的性能陷阱**：混用 sync/async 工具时，sync 工具会阻塞事件循环。→ 正确做法：用 async 工具 + `asyncio.gather()` 并发执行多个独立工具调用。

---

## 与现有知识库的连接

- 关联 `python/snippet_manager.py`：snippet_manager 已经有自然语言搜索，可以封装成 llm 工具（`search_snippets(query: str) -> str`），让 `llm -T snippet_search` 直接查询 CodeSnippets 知识库
- 关联 `python/fts5_fuzzy_search.py`：FTS5 三层模糊搜索可以直接作为 llm 工具的实现后端，query → SQLite FTS5 → 返回相关片段
- 关联 `python/insight_agent.py`：insight_agent 手动实现了工具循环（web_fetch, read_file, write_file），可以用 `model.chain()` 重写，减少循环管理代码量约 60 行

---

## 衍生项目想法

### CodeSnippets 作为 llm 本地工具集

**来源组合**：[LLM 0.26 Function-as-Tool 零摩擦] + [snippet_manager.py 自然语言搜索]
**为什么有意思**：snippet_manager 已经有 CLI，但需要单独运行；封装成 llm 工具后，可以在任意 llm 会话中随时搜索本地知识库，而不需要切换终端
**最小 spike**：写一个 `codesnippets_tools.py`，定义 `search_snippets(query: str) -> str` 和 `list_snippets(language: str = "") -> str` 两个函数，用 `llm --functions codesnippets_tools.py` 测试
**潜在难点**：llm 的 `--functions` 不支持从文件直接读取，需要封装成插件（llm-tools-codesnippets）

### 用 `model.chain()` 重写 insight_agent

**来源组合**：[LLM 0.26 model.chain() 自动管理 ReAcT 循环] + [insight_agent.py 手写 20 轮循环]
**为什么有意思**：insight_agent 的 run_agent() 函数有约 70 行用于管理消息列表、检查 stop_reason、分发工具——这些 model.chain() 全部内置
**最小 spike**：用 `llm` Python API 重写 `run_agent()`，保留现有 4 个工具函数，对比输出质量和代码行数
**潜在难点**：llm 库的 `after_call` 回调和 insight_agent 的进度打印风格不同，需要适配
