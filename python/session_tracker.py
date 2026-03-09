# =============================================================================
# 名称: Session Tracker — Agent 会话持续性跟踪器
# 来源: https://github.com/mksglu/context-mode （架构参考，本实现为原创移植）
# 用途: 在 AI Agent 会话中持久化结构化事件，在 context 压缩前后重建工作状态
#       核心思路：PreCompact 时构建优先级快照（≤2 KB），SessionStart 时通过 FTS5 恢复
# 依赖: stdlib only (sqlite3, json, time, pathlib)
# 适用场景:
#   - Claude Code / Gemini CLI 的 PreCompact + SessionStart hook 脚本
#   - 任何需要跨 context compaction 保持状态的长任务 Agent
#   - 多 Agent 协作时的共享会话状态存储
# 日期: 2025-07-13
# =============================================================================
#
# 架构说明:
#   PostToolUse  → tracker.capture(category, content, priority)
#   PreCompact   → snapshot = tracker.build_snapshot(budget_chars=2000)
#   SessionStart → tracker.restore_from_snapshot(snapshot) + context injection
#
# 优先级分类（P1 永不丢弃，P4 最先丢弃）:
#   P1: files/tasks/rules/last_prompt          ← 关键工作状态
#   P2: decisions/git/errors/environment       ← 高价值上下文
#   P3: mcp_tools/subagents/skills             ← 参考信息
#   P4: intent/data_references                 ← 可重建信息
#
# 三层模糊搜索（FTS5）:
#   Layer 1: Porter stemming — "caching" → "cached/caches"
#   Layer 2: Trigram substring — "useEff" → "useEffect"
#   Layer 3: Levenshtein correction — "kuberntes" → "kubernetes"
# =============================================================================

import sqlite3
import json
import time
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Literal, Optional


# ---------------------------------------------------------------------------
# 事件优先级常量
# ---------------------------------------------------------------------------
PRIORITY = {
    "critical": 1,  # files, tasks, rules, last_prompt
    "high":     2,  # decisions, git, errors, environment
    "normal":   3,  # mcp_tools, subagents, skills
    "low":      4,  # intent, data_references
}

CATEGORY_PRIORITY = {
    "files":       PRIORITY["critical"],
    "tasks":       PRIORITY["critical"],
    "rules":       PRIORITY["critical"],
    "last_prompt": PRIORITY["critical"],
    "decisions":   PRIORITY["high"],
    "git":         PRIORITY["high"],
    "errors":      PRIORITY["high"],
    "environment": PRIORITY["high"],
    "mcp_tools":   PRIORITY["normal"],
    "subagents":   PRIORITY["normal"],
    "skills":      PRIORITY["normal"],
    "intent":      PRIORITY["low"],
    "data":        PRIORITY["low"],
}


# ---------------------------------------------------------------------------
# 主体类
# ---------------------------------------------------------------------------
class SessionTracker:
    """
    Agent 会话状态跟踪器——基于 SQLite FTS5 实现跨 compaction 的状态持久化。

    用法示例（Claude Code hook 脚本中）:
        # PostToolUse hook
        tracker = SessionTracker("/path/to/project")
        tracker.capture("files", "read: src/app.ts")
        tracker.capture("git", "commit: feat: add auth endpoint")

        # PreCompact hook
        snapshot = tracker.build_snapshot()
        tracker.save_snapshot(snapshot)

        # SessionStart hook (source="compact")
        snapshot = tracker.load_snapshot()
        guide = tracker.build_session_guide(snapshot)
        print(guide)  # 注入到 context
    """

    def __init__(self, project_root: str, db_name: str = ".context-mode.db"):
        self.project_root = Path(project_root)
        db_path = self.project_root / db_name
        self.conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    # ------------------------------------------------------------------
    # Schema 初始化
    # ------------------------------------------------------------------
    def _init_schema(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS events (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                ts       REAL    NOT NULL,
                priority INTEGER NOT NULL DEFAULT 2,
                category TEXT    NOT NULL,
                content  TEXT    NOT NULL,
                metadata TEXT    DEFAULT '{}'
            );

            CREATE INDEX IF NOT EXISTS idx_events_priority_ts
                ON events(priority ASC, ts DESC);

            CREATE TABLE IF NOT EXISTS session_resume (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                ts       REAL    NOT NULL,
                snapshot TEXT    NOT NULL
            );
        """)
        # FTS5 表（Porter stemming）
        self.conn.executescript("""
            CREATE VIRTUAL TABLE IF NOT EXISTS events_fts
            USING fts5(content, category UNINDEXED, tokenize='porter');
        """)
        self.conn.commit()

    # ------------------------------------------------------------------
    # 事件捕获
    # ------------------------------------------------------------------
    def capture(
        self,
        category: str,
        content: str,
        priority: Optional[int] = None,
        metadata: Optional[dict] = None,
    ) -> int:
        """
        捕获一个会话事件。

        Args:
            category:  事件类别（见 CATEGORY_PRIORITY）
            content:   事件描述（自然语言，会被索引进 FTS5）
            priority:  覆盖默认优先级（1=关键，4=低）
            metadata:  任意额外数据（JSON 序列化）

        Returns:
            新插入事件的 rowid
        """
        if priority is None:
            priority = CATEGORY_PRIORITY.get(category, PRIORITY["normal"])
        meta_str = json.dumps(metadata or {})
        ts = time.time()

        cur = self.conn.execute(
            "INSERT INTO events(ts, priority, category, content, metadata) VALUES(?,?,?,?,?)",
            (ts, priority, category, content, meta_str),
        )
        self.conn.execute(
            "INSERT INTO events_fts(content, category) VALUES(?,?)",
            (content, category),
        )
        self.conn.commit()
        return cur.lastrowid

    def capture_batch(self, events: list[dict]) -> int:
        """批量捕获事件，events 格式: [{"category": str, "content": str, ...}]"""
        count = 0
        for ev in events:
            self.capture(
                category=ev["category"],
                content=ev["content"],
                priority=ev.get("priority"),
                metadata=ev.get("metadata"),
            )
            count += 1
        return count

    # ------------------------------------------------------------------
    # 优先级快照构建（PreCompact）
    # ------------------------------------------------------------------
    def build_snapshot(self, budget_chars: int = 2000) -> str:
        """
        按优先级构建 XML 快照，不超过 budget_chars。
        P1 事件永不丢弃；P4 事件最先被裁剪。

        Returns:
            XML 字符串（注入 context 的格式）
        """
        events = self.conn.execute(
            """
            SELECT category, content, priority
            FROM events
            ORDER BY priority ASC, ts DESC
            """
        ).fetchall()

        # 按 category 分组
        groups: dict[str, list[str]] = {}
        for ev in events:
            groups.setdefault(ev["category"], []).append(ev["content"])

        # 按优先级排序分组
        sorted_cats = sorted(
            groups.keys(),
            key=lambda c: CATEGORY_PRIORITY.get(c, PRIORITY["normal"]),
        )

        lines = ["<session_knowledge>"]
        total = len("<session_knowledge></session_knowledge>")
        critical_done = False

        for cat in sorted_cats:
            cat_lines = [f"  <{cat}>"]
            for content in groups[cat][:10]:  # 每类最多 10 条
                entry = f"    <item>{_escape_xml(content)}</item>"
                cat_lines.append(entry)
            cat_lines.append(f"  </{cat}>")
            block = "\n".join(cat_lines)

            priority = CATEGORY_PRIORITY.get(cat, PRIORITY["normal"])
            if priority <= PRIORITY["critical"]:
                # P1 强制保留
                lines.append(block)
                total += len(block)
            elif total + len(block) <= budget_chars:
                lines.append(block)
                total += len(block)
            # 否则跳过（预算不足）

        lines.append("</session_knowledge>")
        return "\n".join(lines)

    def save_snapshot(self, snapshot: str):
        """将快照保存到 session_resume 表"""
        self.conn.execute(
            "INSERT INTO session_resume(ts, snapshot) VALUES(?,?)",
            (time.time(), snapshot),
        )
        self.conn.commit()

    def load_snapshot(self) -> Optional[str]:
        """加载最新快照"""
        row = self.conn.execute(
            "SELECT snapshot FROM session_resume ORDER BY ts DESC LIMIT 1"
        ).fetchone()
        return row["snapshot"] if row else None

    # ------------------------------------------------------------------
    # Session Guide 构建（SessionStart 后注入 context）
    # ------------------------------------------------------------------
    def build_session_guide(self, snapshot: Optional[str] = None) -> str:
        """
        构建人类可读的 Session Guide，用于 SessionStart 时注入 context。
        包含 14 个分类，让模型无需重新解释就能继续工作。
        """
        if snapshot is None:
            snapshot = self.load_snapshot()
        if not snapshot:
            return ""

        lines = [
            "## Session Continuity Guide",
            "",
            "> You are resuming a session. Below is your working state.",
            "",
        ]

        # 解析快照中的分类
        categories = re.findall(r"<(\w+)>(.*?)</\1>", snapshot, re.DOTALL)
        for cat, content in categories:
            items = re.findall(r"<item>(.*?)</item>", content, re.DOTALL)
            if not items:
                continue
            lines.append(f"### {cat.replace('_', ' ').title()}")
            for item in items:
                lines.append(f"- {item.strip()}")
            lines.append("")

        lines.append("---")
        lines.append("*Continue from your last request above without asking for re-explanation.*")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # FTS5 三层模糊搜索
    # ------------------------------------------------------------------
    def search(self, query: str, limit: int = 5) -> list[dict]:
        """
        三层模糊搜索：
          Layer 1: Porter stemming FTS5 MATCH
          Layer 2: Trigram substring（如未返回结果）
          Layer 3: Levenshtein 纠错（如仍无结果）

        Returns:
            [{content: str, category: str, score: float}, ...]
        """
        # Layer 1: Porter stemming
        results = self._fts_search(query, limit)
        if results:
            return results

        # Layer 2: Trigram substring（每3字符拆分后搜索）
        if len(query) >= 3:
            trigram_query = " OR ".join(
                f'"{query[i:i+3]}"' for i in range(len(query) - 2)
            )
            results = self._fts_search(trigram_query, limit)
            if results:
                return results

        # Layer 3: Levenshtein 纠错（简化版：查全表 + 字符串相似度）
        results = self._fuzzy_fallback(query, limit)
        return results

    def _fts_search(self, query: str, limit: int) -> list[dict]:
        try:
            rows = self.conn.execute(
                """
                SELECT content, category, rank as score
                FROM events_fts
                WHERE events_fts MATCH ?
                ORDER BY rank
                LIMIT ?
                """,
                (query, limit),
            ).fetchall()
            return [dict(r) for r in rows]
        except sqlite3.OperationalError:
            return []

    def _fuzzy_fallback(self, query: str, limit: int) -> list[dict]:
        """Levenshtein 距离回退（简化版，只对单词匹配）"""
        rows = self.conn.execute(
            "SELECT content, category FROM events ORDER BY ts DESC LIMIT 500"
        ).fetchall()
        scored = []
        for row in rows:
            score = _max_word_similarity(query.lower(), row["content"].lower())
            if score > 0.6:
                scored.append({"content": row["content"], "category": row["category"], "score": score})
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:limit]

    # ------------------------------------------------------------------
    # 会话清理
    # ------------------------------------------------------------------
    def clear(self):
        """清空当前会话数据（新会话时调用）"""
        self.conn.executescript("""
            DELETE FROM events;
            DELETE FROM events_fts;
            DELETE FROM session_resume;
        """)
        self.conn.commit()

    def stats(self) -> dict:
        """返回当前会话统计"""
        total = self.conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        by_cat = self.conn.execute(
            "SELECT category, COUNT(*) as cnt FROM events GROUP BY category"
        ).fetchall()
        return {
            "total_events": total,
            "by_category": {r["category"]: r["cnt"] for r in by_cat},
        }


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------
def _escape_xml(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _levenshtein(s1: str, s2: str) -> int:
    """计算两个字符串的编辑距离"""
    if len(s1) < len(s2):
        return _levenshtein(s2, s1)
    if len(s2) == 0:
        return len(s1)
    prev = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        curr = [i + 1]
        for j, c2 in enumerate(s2):
            curr.append(min(prev[j + 1] + 1, curr[-1] + 1, prev[j] + (c1 != c2)))
        prev = curr
    return prev[-1]


def _max_word_similarity(query: str, text: str) -> float:
    """返回 query 与 text 中每个词的最大相似度"""
    words = text.split()
    if not words:
        return 0.0
    best = 0.0
    for word in words:
        max_len = max(len(query), len(word))
        if max_len == 0:
            continue
        dist = _levenshtein(query, word)
        sim = 1.0 - dist / max_len
        best = max(best, sim)
    return best


# ---------------------------------------------------------------------------
# 演示用法
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import tempfile
    import os

    with tempfile.TemporaryDirectory() as tmpdir:
        tracker = SessionTracker(tmpdir)

        # 模拟 PostToolUse 捕获事件
        tracker.capture("files", "read: src/routes/users.ts")
        tracker.capture("files", "edit: src/routes/users.ts — added POST /users")
        tracker.capture("tasks", "create: Implement user authentication")
        tracker.capture("tasks", "complete: Add POST /users route")
        tracker.capture("git", "commit: feat: add POST /users endpoint")
        tracker.capture("errors", "TS2345: Argument of type string is not assignable to number")
        tracker.capture("decisions", "use Zod for validation instead of Joi")
        tracker.capture("last_prompt", "Now add error handling middleware")
        tracker.capture("intent", "implement: REST API with auth and error handling", priority=4)

        # 模拟 PreCompact
        print("=== PreCompact: 构建优先级快照 ===")
        snapshot = tracker.build_snapshot(budget_chars=800)
        tracker.save_snapshot(snapshot)
        print(snapshot)
        print()

        # 模拟 SessionStart
        print("=== SessionStart: 构建 Session Guide ===")
        guide = tracker.build_session_guide()
        print(guide)
        print()

        # 模拟 FTS5 搜索
        print("=== FTS5 搜索: 'authentication' ===")
        results = tracker.search("authentication")
        for r in results:
            print(f"  [{r['category']}] {r['content']}")
        print()

        # 统计
        print("=== 会话统计 ===")
        print(json.dumps(tracker.stats(), indent=2))
