## CodeSnippets

Internal notes for contributors and agents.
Use `README.md` as the public source of truth for the catalog and usage.
See `references/project-conventions.md` and `references/doc-templates.md` for formatting rules.

### Commands

```sh
# 单条 URL 归档（独立 CLI）
python3 python/insight_agent.py <url> [备注]

# 批量任务队列处理
python3 python/mini_symphony.py -w WORKFLOW.md --once      # 处理一轮
python3 python/mini_symphony.py -w WORKFLOW.md             # 持续监听
python3 python/mini_symphony.py -w WORKFLOW.md --dry-run   # 预览 prompt
```

### Important files

**入口与编排**
- `python/mini_symphony.py` — 轻量 Agent 编排器：TASKS.md 队列 → per-task workspace → 子进程执行 → 两级重试
- `python/insight_agent.py` — 独立 URL→归档 Agent：fetch → 分析 → 路由 → 写文件 → 更新索引
- `WORKFLOW.md` — mini_symphony 的运行时配置（任务源、prompt 模板、hook 脚本）
- `READING_LIST.md` — 任务队列：`- [ ]` 待归档、`- [x]` 已归档

**索引与元数据**
- `README.md` — 项目主目录表，中英文双表，**每次新增文件必须同步更新两张表**
- `references/project-conventions.md` — 目录路由规则、命名规范、Header 格式
- `references/doc-templates.md` — analysis/ 和 ideas/ 的完整文档模板

**可复用代码**
- `python/tape_context.py` — 锚点上下文装配（多轮对话）
- `python/session_tracker.py` — SQLite 事件 → 优先级快照 → FTS5 恢复
- `python/fts5_fuzzy_search.py` — 三层模糊搜索（Porter → trigram → Levenshtein）
- `python/sandbox_execute.py` — 隔离子进程执行，只有 stdout 进入 context
- `snippets/mapreduce-engine.rs` — Rust MapReduce 单机实现（Master/Worker + K-way 归并）

**模板**
- `templates/WORKFLOW.md.template` — mini_symphony 配置模板
- `templates/agents-md-template.md` — 5 层 Agent 文档架构模板（本文件就是用这个模板创建的）
- `templates/ruff.toml.template` — 生产级 Python linter 配置

### Implementation notes

- **README 双表同步是强制约束**：每次新增文件，必须同时更新 README.md 的英文表和中文表。遗漏任何一张表都算未完成。
- **READING_LIST 闭环**：归档完成后，必须在 READING_LIST.md 中把对应 URL 从 `- [ ]` 改为 `- [x]`。如果 URL 不在列表中，在"已归档"末尾追加 `- [x] {url}`。
- **代码文件 Header 不可省略**：所有 `python/`、`javascript/`、`snippets/` 下的代码文件必须以标准 Header 开头（名称、来源、用途、依赖、适用场景、日期）。Header 用中文。
- **代码用英文，文档用中文**：代码变量名、注释用英文；analysis/、ideas/ 文档用中文撰写。
- **目录路由规则**：可运行代码 → `python/`/`javascript/`/`snippets/`；项目灵感 → `ideas/`；外部精读 → `analysis/`；HTML 单页工具 → `html-tools/`；模板 → `templates/`。
- **文件命名**：小写、连字符（analysis 和 ideas）或下划线（python 代码）、描述性。不允许空格。
- **ideas 文件必须包含来源组合和最小 spike**：没有这两项的想法视为无效。
- **analysis 文件必须包含"与现有知识库的连接"**：孤立的精读没有复利价值。
- **不要虚构代码**：只提取实际存在于原材料的内容。如果原材料没有代码，就不要创建 snippets/ 文件。
- **一个来源可以产出多个文件**：一篇博文可以同时产出代码片段 + idea 文档 + analysis 精读。
- **Emoji 分类**：🟢 代码（可运行/导入）、🟡 模板（复制后修改）、🔵 参考（设计决策时查阅）。
- **insight-collector skill 是主归档工作流**：它实现了 6 步收录流程（KB 扫描 → 获取 → 9维提取 → 深度推理 → 写文件 → 更新索引）。所有行动建议必须经过 Step 3F 实时验证。
- **搜索优先原则**：当判断"这个值不值得做"或"有没有人做过"时，第一步永远是搜索（web_search / GitHub search），不是推理。推理建立在搜索结果之上。

### Open questions

- `insight_agent.py` 是否应该支持批量 URL 处理（READING_LIST 中多条待归档一次性处理）？
- analysis 文档是否应该自动扫描 snippets/ 生成代码链接？
- 是否需要一个 `status/` 目录放机器可读的知识库统计快照（文件数、覆盖领域、最近更新时间）？
- ideas/ 的状态标记（💡/⚠️/❌）是否应该有更结构化的验证流程？

### Related

- `~/.claude/skills/insight-collector/` — 主归档 skill，定义了 6 步收录工作流
- `~/.claude/skills/readme-maintainer/` — README 同步 skill
- `~/Projects/DocFlow/` — 本地 PDF RAG 助手，与 CodeSnippets 的 analysis/ 互为参考
