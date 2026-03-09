# Agent 会话持续性模式：PreCompact 快照 + FTS5 恢复

**来源**: [Context Mode GitHub](https://github.com/mksglu/context-mode) · [博客](https://mksg.lu/blog/context-mode)
**日期**: 2025-07-13
**状态**: 💡灵感

---

## 核心理念

> **Agent 的"失忆"不是在 context 满时发生，而是在 context 被压缩（compact）时发生**——解法是在压缩前把工作状态序列化到 SQLite，压缩后通过 FTS5+BM25 按需重建，而不是把完整历史重新注入。

Context Mode 证明了这个架构的可行性：一个 3 小时的工作会话，在多次 compaction 后，模型仍能从上次 prompt 的位置继续，无需用户重新解释上下文。

---

## 关键技术要点

### 四钩架构

```
PostToolUse    ← 每次工具调用后捕获结构化事件 → SQLite
UserPromptSubmit ← 捕获用户决策/偏好 → SQLite
PreCompact     ← 压缩前：读所有事件 → 构建优先级快照（≤2 KB）
SessionStart   ← 压缩后：取快照 → 索引 FTS5 → 注入 <session_knowledge>
```

### 优先级快照结构（XML，≤2 KB）

```xml
<session_knowledge>
  <last_request>用户最后一条 prompt</last_request>
  <tasks>
    <task status="pending">实现 REST API 的错误处理</task>
    <task status="done">添加 /users 路由</task>
  </tasks>
  <key_decisions>
    <decision>用 Zod 验证，不用 Joi</decision>
    <decision>错误格式：{ error: string, code: number }</decision>
  </key_decisions>
  <files_modified>
    <file>src/routes/users.ts</file>
    <file>src/middleware/error.ts</file>
  </files_modified>
  <unresolved_errors>
    <error>TS2345: Argument of type 'string' is not assignable</error>
  </unresolved_errors>
  <environment>
    <cwd>/projects/my-api</cwd>
    <venv>node v20.11.0</venv>
  </environment>
</session_knowledge>
```

### 事件优先级（预算 ≤2 KB，先丢低优先级）

| 级别 | 内容 | 是否可丢弃 |
|-----|-----|----------|
| P1（关键） | 最后 prompt、活跃文件、未完成任务、项目规则 | 永不丢弃 |
| P2（高） | 用户决策、Git 操作、工具报错 | 空间紧时考虑丢弃 |
| P3（正常） | MCP 工具调用计数、子 Agent 任务 | 优先丢弃 |
| P4（低） | 会话意图分类、大数据引用 | 最先丢弃 |

### Session Guide 的 15 个分类（恢复后注入）

1. Last Request（最重要，让模型不用问"我们做到哪了"）
2. Tasks（带 checkbox 状态）
3. Key Decisions（用户的明确偏好）
4. Files Modified
5. Unresolved Errors
6. Git Operations
7. Project Rules（CLAUDE.md 等）
8. MCP Tools Used（调用计数）
9. Subagent Tasks
10. Skills Used
11. Environment（cwd、venv 等）
12. Data References
13. Session Intent（实现/调试/审查）
14. User Role（"以高级工程师身份行事"）
15. FTS5 索引（详细事件的按需检索入口）

---

## 可行性与挑战

- ✅ 已验证可行：Context Mode 在 Claude Code、Gemini CLI、VS Code Copilot 上完整运行
- ✅ 已验证有效：会话从 ~30 分钟延长到 ~3 小时
- ✅ 已验证 SQLite FTS5 能在 1 秒内索引和检索数千个事件
- ⚠️ 待解决：不同 AI 平台的 hook API 不统一——Claude Code 有 5 种 hook，Codex CLI 完全没有
- ⚠️ 待解决：UserPromptSubmit hook 只有 Claude Code 支持，Gemini CLI/VS Code 丢失"用户决策"这个关键事件类别
- ⚠️ 待解决：OpenCode 的 SessionStart hook 尚未实现（GitHub Issue #14808），启动时无法自动恢复

---

## 最小可实现版本（不依赖 Context Mode）

用 Python 手写一个简化版会话持续性系统：

```python
# mini_session_tracker.py
import sqlite3
import json
from pathlib import Path

class SessionTracker:
    def __init__(self, project_root: str):
        db_path = Path(project_root) / ".session.db"
        self.conn = sqlite3.connect(db_path)
        self._init_schema()
    
    def _init_schema(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY,
                ts REAL,
                priority INTEGER,  -- 1=critical, 2=high, 3=normal, 4=low
                category TEXT,     -- files/tasks/decisions/git/errors
                content TEXT
            )
        """)
        self.conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS events_fts 
            USING fts5(content, tokenize='porter')
        """)
    
    def capture(self, category: str, content: str, priority: int = 2):
        import time
        self.conn.execute(
            "INSERT INTO events(ts, priority, category, content) VALUES(?,?,?,?)",
            (time.time(), priority, category, content)
        )
        self.conn.execute(
            "INSERT INTO events_fts(content) VALUES(?)", (content,)
        )
        self.conn.commit()
    
    def build_snapshot(self, budget_chars: int = 2000) -> str:
        """按优先级构建快照，不超过 budget"""
        events = self.conn.execute(
            "SELECT category, content FROM events ORDER BY priority ASC, ts DESC"
        ).fetchall()
        
        lines = []
        total = 0
        for cat, content in events:
            line = f"[{cat}] {content}"
            if total + len(line) > budget_chars:
                break
            lines.append(line)
            total += len(line)
        
        return "\n".join(lines)
    
    def search(self, query: str, limit: int = 3) -> list[str]:
        """FTS5 检索相关事件"""
        rows = self.conn.execute(
            "SELECT content FROM events_fts WHERE events_fts MATCH ? LIMIT ?",
            (query, limit)
        ).fetchall()
        return [r[0] for r in rows]
```

---

## 与现有知识库的连接

- 关联 `python/tape_context.py`：Tape 的"锚点 + 按需装配"是同一思想的轻量级内存版；Session Tracker 是持久化版本，跨进程重启
- 关联 `python/fts5_fuzzy_search.py`：直接复用三层模糊搜索实现，作为事件检索的底层
- 关联 `python/mini_symphony.py`：mini_symphony 的任务队列可以作为 Session Tracker 的"Tasks"事件来源

---

## 下一步行动

- [ ] 写 `python/session_tracker.py`——实现 SQLite 事件捕获 + 优先级快照 + FTS5 检索
- [ ] 与 Claude Code 的 hooks 系统集成（先读 `.claude/hooks/` 文档）
- [ ] 测试 compact 前后的状态恢复准确率（目标：无需重新解释上下文就能继续工作）
- [ ] 对比 tape_context.py（内存锚点）vs session_tracker.py（SQLite 持久化）的适用场景
