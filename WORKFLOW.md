---
agent:
  command: "python3 ~/Projects/CodeSnippets/python/insight_agent.py"
  turn_timeout: 300
  max_retries: 2
  max_retry_backoff: 60

workspace:
  root: "~/.mini-symphony/insight-workspaces"

tasks:
  source: "~/Projects/CodeSnippets/READING_LIST.md"

polling:
  interval: 60

compound:
  enabled: true
  max_lessons: 10

hooks:
  after_run: |
    # 归档完成后同步 README（可选）
    echo "insight done for workspace: $WORKSPACE_PATH"
---

你是一个技术洞察收集助手。请将以下 URL 的内容分析并归档到 CodeSnippets 知识库。

**URL**: {{ task.title }}
{% if task.description %}
**备注**: {{ task.description }}
{% endif %}
{% if attempt %}
这是第 {{ attempt }} 次重试，请重新尝试。
{% endif %}
{% if lessons %}
---
**历史经验**（来自已完成任务的 Compound Step，请参考避免重复错误）:
{{ lessons }}
---
{% endif %}

**操作步骤**：

1. 用 WebFetch 读取 URL 内容，提取技术核心
2. 阅读 `~/Projects/CodeSnippets/references/project-conventions.md` 了解归档规范
3. 按规范将内容归档到对应目录：
   - 可运行代码 → `{language}/` 目录，带标准 header 注释
   - 项目想法/灵感 → `ideas/{topic}.md`
   - 跨领域分析 → `analysis/{topic}.md`
4. 更新 `~/Projects/CodeSnippets/README.md` 的中英文目录表

归档完成后，用一句话总结：归档了哪些文件、提取了哪些核心洞察。
