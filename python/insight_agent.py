#!/usr/bin/env python3
"""
# =============================================================================
# 名称: insight_agent.py
# 用途: 从 URL/文本提取技术洞察并归档到 CodeSnippets，直接调用 Anthropic SDK
# 依赖: pip install anthropic requests
# 适用场景: mini_symphony agent command，或命令行独立调用
# 日期: 2026-03-05
# =============================================================================

用法:
  python insight_agent.py <url> [description]
  python insight_agent.py "https://example.com/article" "关注其中的缓存设计"

mini_symphony WORKFLOW.md 中的 agent command:
  python3 /root/projects/CodeSnippets/python/insight_agent.py
"""

import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path

import anthropic

# ─────────────────────────────────────────────
# 配置
# ─────────────────────────────────────────────

CODESNIPPETS_ROOT = Path("/root/projects/CodeSnippets")
CONVENTIONS_PATH = CODESNIPPETS_ROOT / "references" / "project-conventions.md"
MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 16384

SYSTEM_PROMPT = f"""\
你是一个技术洞察收集助手，负责将技术文章/代码仓库的核心内容深度归档到 CodeSnippets 知识库。

知识库根目录: {CODESNIPPETS_ROOT}

## 工具

- web_fetch: 抓取 URL 内容（返回纯文本）
- read_file: 读取本地文件
- write_file: 写入文件（覆盖），自动创建父目录
- append_file: 追加内容到文件末尾

---

## 工作流程

### Step 0：读取规范与现有知识库

先并行完成两件事，再开始分析：
1. read_file("{CONVENTIONS_PATH}") — 了解归档格式、目录路由、Header 模板
2. read_file("{CODESNIPPETS_ROOT}/README.md") — 了解知识库已有条目，为后续交叉引用做准备

### Step 1：抓取内容

web_fetch 目标 URL。若页面引用了重要的链出页面（如规范文档、源码），也一并 fetch。

### Step 2：9 维度提取

从材料中提取所有适用维度，重点挖掘 🧠⚖️⚠️💡（信息密度最高、最容易被忽视）：

| 维度 | 内容 |
|------|------|
| 🟢 可复用代码 | 可直接运行/导入的代码，标注语言 |
| 🏗️ 技术模式 | 架构思路、API 用法、设计模式（命名） |
| 📦 工具与依赖 | 值得关注的库/工具/服务，记录版本 |
| 🧠 心智模型 | 作者使用的思维框架（往往最有价值） |
| ⚖️ 权衡取舍 | 明确陈述的 tradeoff：X vs Y 何时选哪个 |
| ⚠️ 反模式与陷阱 | Gotcha、常见错误、边界情况 |
| 💡 非显见洞见 | 不经提示不会想到的"啊哈"结论 |
| ❓ 开放问题 | 材料提出或暗示的悬而未决问题 |
| 🚀 衍生想法种子 | 能从这里出发构建的方向（下一步深化） |

### Step 3：深度推理（核心步骤，不可跳过）

对 Step 2 中每个高价值提取物，运行以下推理后再动笔：

**A. 蕴含链**——追问 3 层"所以……"：
```
洞见：X
→ 所以：Y（直接推论）
→ 所以：Z（Y 的推论）
→ 因此可以：[具体行动]
```

**B. 隐含假设**——作者默认了什么但没说出来？
- 这个方案在什么条件下成立？
- 哪个假设不成立时结论会失效？

**C. 反事实**——为什么选 X 不选 Y？
- 被放弃的替代方案是什么？
- 放弃的理由揭示了什么约束或价值观？

**D. 组合生成**——交叉现有知识库条目（Step 0 读到的）：
```
[本次概念 A] × [已有 KB 条目 B] → [新想法 C]
为什么有意思：A+B 的组合比各自单独更有价值在于……
最小验证实验：能在 1 天内完成的最小 spike
```

**E. 边界分析**——在哪里会失效？规模/复杂度/团队的边界在哪？

### Step 4：写出文件

按 project-conventions.md 的目录路由和模板格式写出。一个来源可产出多个文件。

### Step 5：更新索引

1. read_file README.md 当前内容，write_file 整体更新（中英文两张表各加一行）
2. read_file READING_LIST.md，将来源 URL 标记为 [x]（在"待归档"改，或追加到"已归档"）

---

## 质量标准

- **不虚构内容**——只提取原材料中实际存在的信息
- **衍生想法必须有**：来源组合 + 为什么有意思 + 最小 spike（缺任何一项视为无效）
- **非显见洞见必须有蕴含链**——不能只写"这个模式很重要"
- 宁可少写一个章节，也不要用空话填满模板字段
- 最终检验：读完产出文档，能否做出比读原文更好的设计决策？
"""

# ─────────────────────────────────────────────
# 工具实现
# ─────────────────────────────────────────────

def web_fetch(url: str, max_chars: int = 20000) -> str:
    """抓取 URL 内容，返回文本"""
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (compatible; InsightAgent/1.0)"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            content = resp.read()
            # 尝试解码
            charset = resp.headers.get_content_charset() or "utf-8"
            text = content.decode(charset, errors="replace")
            # 简单去除 HTML 标签
            import re
            text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL)
            text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL)
            text = re.sub(r"<[^>]+>", " ", text)
            text = re.sub(r"\s{3,}", "\n\n", text)
            return text[:max_chars]
    except urllib.error.URLError as e:
        return f"[ERROR] 无法抓取 {url}: {e}"


def read_file(path: str) -> str:
    """读取本地文件"""
    p = Path(path)
    if not p.exists():
        return f"[ERROR] 文件不存在: {path}"
    try:
        return p.read_text(encoding="utf-8")
    except Exception as e:
        return f"[ERROR] 读取失败: {e}"


def write_file(path: str, content: str) -> str:
    """写入文件（覆盖），自动创建父目录"""
    p = Path(path)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"[OK] 已写入: {path} ({len(content)} 字符)"
    except Exception as e:
        return f"[ERROR] 写入失败: {e}"


def append_file(path: str, content: str) -> str:
    """追加内容到文件末尾"""
    p = Path(path)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as f:
            f.write(content)
        return f"[OK] 已追加到: {path}"
    except Exception as e:
        return f"[ERROR] 追加失败: {e}"


# ─────────────────────────────────────────────
# 工具定义（传给 Anthropic API）
# ─────────────────────────────────────────────

TOOLS = [
    {
        "name": "web_fetch",
        "description": "抓取指定 URL 的网页内容，返回纯文本（去除 HTML 标签）",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "要抓取的 URL"},
                "max_chars": {"type": "integer", "description": "返回的最大字符数，默认 20000"},
            },
            "required": ["url"],
        },
    },
    {
        "name": "read_file",
        "description": "读取本地文件内容",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件的绝对路径"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "写入文件（覆盖），自动创建父目录",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件的绝对路径"},
                "content": {"type": "string", "description": "写入的内容"},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "append_file",
        "description": "追加内容到文件末尾（用于更新 README.md 目录表时建议用 write_file 整体更新）",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件的绝对路径"},
                "content": {"type": "string", "description": "要追加的内容"},
            },
            "required": ["path", "content"],
        },
    },
]

# ─────────────────────────────────────────────
# 工具分发
# ─────────────────────────────────────────────

def dispatch_tool(name: str, inputs: dict) -> str:
    if name == "web_fetch":
        return web_fetch(inputs["url"], inputs.get("max_chars", 20000))
    elif name == "read_file":
        return read_file(inputs["path"])
    elif name == "write_file":
        return write_file(inputs["path"], inputs["content"])
    elif name == "append_file":
        return append_file(inputs["path"], inputs["content"])
    else:
        return f"[ERROR] 未知工具: {name}"


# ─────────────────────────────────────────────
# Agent 主循环
# ─────────────────────────────────────────────

def run_agent(url: str, description: str = "") -> bool:
    """
    运行 agent，处理一个 URL 的归档任务。
    返回 True=成功。
    """
    # 读取 API key
    creds_path = Path.home() / ".claude" / ".credentials.json"
    if creds_path.exists():
        creds = json.loads(creds_path.read_text())
        api_key = creds.get("claudeAiOauth", {}).get("accessToken", "")
    else:
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")

    if not api_key:
        print("[ERROR] 找不到 API key", file=sys.stderr)
        return False

    client = anthropic.Anthropic(api_key=api_key)

    user_content = f"请将以下 URL 的内容分析并归档到 CodeSnippets 知识库：\n\nURL: {url}"
    if description:
        user_content += f"\n备注: {description}"

    messages = [{"role": "user", "content": user_content}]

    print(f"[insight_agent] 开始处理: {url}")

    max_rounds = 20
    for round_num in range(max_rounds):
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )

        # 收集本轮 assistant 内容
        assistant_content = response.content
        messages.append({"role": "assistant", "content": assistant_content})

        # 检查停止原因
        if response.stop_reason == "end_turn":
            # 打印最终文字输出
            for block in assistant_content:
                if hasattr(block, "text"):
                    print(f"[insight_agent] 完成: {block.text[:300]}")
            return True

        if response.stop_reason != "tool_use":
            print(f"[insight_agent] 意外停止: {response.stop_reason}", file=sys.stderr)
            return False

        # 执行工具调用
        tool_results = []
        for block in assistant_content:
            if block.type != "tool_use":
                continue
            tool_name = block.name
            tool_input = block.input
            print(f"  → {tool_name}({list(tool_input.keys())})")
            result = dispatch_tool(tool_name, tool_input)
            print(f"    {result[:120]}")
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": result,
            })

        messages.append({"role": "user", "content": tool_results})

    print("[insight_agent] 达到最大轮次，退出", file=sys.stderr)
    return False


# ─────────────────────────────────────────────
# CLI 入口
# ─────────────────────────────────────────────

def main():
    # mini_symphony 调用方式：
    #   command: "python3 /root/projects/CodeSnippets/python/insight_agent.py"
    #   prompt 通过 .symphony_prompt.txt 传入，格式如下：
    #     URL: https://...
    #     备注: ...（可选）
    #
    # 也支持直接命令行调用：
    #   python3 insight_agent.py <url> [description]

    if len(sys.argv) >= 2:
        # 直接命令行调用
        url = sys.argv[1]
        description = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else ""
    else:
        # 从 stdin 或 .symphony_prompt.txt 读取（mini_symphony 模式）
        prompt_file = Path(".symphony_prompt.txt")
        if prompt_file.exists():
            text = prompt_file.read_text(encoding="utf-8")
        else:
            text = sys.stdin.read()

        # 解析 "URL: ..." 和 "备注: ..." 格式
        url = ""
        description = ""
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("**URL**:") or line.startswith("URL:"):
                url = line.split(":", 1)[1].strip()
            elif line.startswith("**备注**:") or line.startswith("备注:"):
                description = line.split(":", 1)[1].strip()

        if not url:
            # fallback: 尝试直接把 prompt 内容的第一个 https:// 开头的词作为 URL
            import re
            m = re.search(r"https?://\S+", text)
            if m:
                url = m.group(0).rstrip(".,\"')")

        if not url:
            print("[ERROR] 无法从 prompt 中提取 URL", file=sys.stderr)
            print("prompt 内容：", text[:200], file=sys.stderr)
            sys.exit(1)

    success = run_agent(url, description)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
