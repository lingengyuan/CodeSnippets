# Reading List

待归档的 URL 列表。mini_symphony 自动处理未完成条目，完成后标记为 [x]。

**运行方式**：
```bash
cd /root/projects/CodeSnippets
python3 python/mini_symphony.py -w WORKFLOW.md --once      # 处理一轮
python3 python/mini_symphony.py -w WORKFLOW.md             # 持续监听
python3 python/mini_symphony.py -w WORKFLOW.md --dry-run   # 预览 prompt
python3 python/insight_agent.py <url> [备注]               # 直接归档单条
```

---

## 待归档

<!-- 在下方添加 URL，每行一个，格式：
- [ ] https://example.com/article
      可选备注：关注点或提示
-->

## 已归档

- [x] https://simonwillison.net/2025/May/27/claude-code-tips/
      Simon Willison 的 Claude Code 使用技巧（实际归档：LLM 0.26 工具支持）
- [x] https://simonwillison.net/guides/agentic-engineering-patterns/hoard-things-you-know-how-to-do/
      重点提取：囤积体系的构建方法、与 CodeSnippets 知识库的连接、非显见洞见和蕴含链
- [x] https://simonwillison.net/guides/agentic-engineering-patterns/code-is-cheap/
      Simon Willison Agentic Engineering Patterns 系列，提取非显见洞见+蕴含链+与现有KB的连接
- [x] https://simonwillison.net/guides/agentic-engineering-patterns/red-green-tdd/
      Simon Willison Agentic Engineering Patterns 系列，提取非显见洞见+蕴含链+与现有KB的连接
- [x] https://mksg.lu/blog/context-mode
      同时参考 GitHub 仓库 https://github.com/mksglu/claude-context-mode，提取上下文模式的架构设计和实现
- [x] https://simonwillison.net/guides/agentic-engineering-patterns/first-run-the-tests/
      Testing & QA 系列：三合一信号（能力探测+规模校准+心态注入）、与 Red/Green TDD 的对称关系
- [x] https://simonwillison.net/guides/agentic-engineering-patterns/agentic-manual-testing/
      Testing & QA 系列（与 linear-walkthroughs 合并归档）：Showboat 工具、exec 防作弊、验证即产物
- [x] https://simonwillison.net/guides/agentic-engineering-patterns/linear-walkthroughs/
      Understanding Code 系列（与 agentic-manual-testing 合并归档）：认知债务三级体系、Showboat 代码导读
- [x] https://simonwillison.net/guides/agentic-engineering-patterns/interactive-explanations/
      Understanding Code 系列：认知债务、两阶段还债路径、"只有亲眼看到才能建立"的直觉性理解
- [x] https://simonwillison.net/guides/agentic-engineering-patterns/gif-optimization/
      Annotated Prompts 系列：CLI→WASM→零后端 HTML 完整模式、Emscripten 暴力编译、Rodney 自测闭环
- [x] https://github.com/Aditya-1304/mapreduce
      Rust MapReduce 单机实现：Master/Worker 架构、K-way 归并、推测执行、原子文件写入
- [x] https://simonwillison.net/guides/agentic-engineering-patterns/anti-patterns/
      Principles 系列：未审查 PR 反模式、PR 验证伦理、验证证据原则
- [x] https://simonwillison.net/guides/agentic-engineering-patterns/prompts/
      Appendix：Artifacts/Proofreader/Alt text prompts（页面持续更新，实际 prompt 内容未完全展示）
- [x] https://github.com/astral-sh/ruff
      Python linter+formatter 工具链整合：迁移策略、捉虫规则集、CI 配置
- [x] https://github.com/karpathy/nanochat
      单拨盘 LLM 训练框架：x0 残差、Muon+AdamW 分组、显式精度管理、autoresearch 的父 repo
- [x] https://github.com/0xdesign/design-plugin
      Claude Code UI 设计插件：样式推断、FeedbackOverlay、DESIGN_MEMORY 积累、5轴变体生成
- [x] https://github.com/karpathy/autoresearch
      Git 棘轮自主 ML 实验框架：program.md 两级优化、NEVER STOP、固定时间预算实验比较
