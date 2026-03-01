# =============================================================================
# 名称: SQLite FTS5 Three-Layer Fuzzy Search
# 用途: 本地全文搜索，三层降级：精确匹配 → 子串匹配 → 模糊纠错
# 依赖: 标准库 (sqlite3)
# 适用场景: 本地知识库搜索、snippet 管理器、离线文档检索
# 来源: https://github.com/mksglu/claude-context-mode (FTS5 知识库实现思路)
# 日期: 2026-03-01
#
# 从 context-mode 提取的核心搜索模式，不依赖原项目，纯 Python 可独立使用。
# 三层搜索：
#   Layer 1: FTS5 MATCH + Porter 词干 — 精确语义匹配
#   Layer 2: FTS5 trigram 子串匹配 — "useEff" 命中 "useEffect"
#   Layer 3: Levenshtein 模糊纠错 — 拼写错误容忍
# =============================================================================

import sqlite3
import os
from pathlib import Path


class FTS5Search:
    def __init__(self, db_path: str = ":memory:"):
        self.conn = sqlite3.connect(db_path)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self._init_tables()

    def _init_tables(self):
        # Layer 1: Porter stemming FTS5 table
        self.conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS docs USING fts5(
                title, content, tags,
                tokenize='porter unicode61'
            )
        """)
        # Layer 2: Trigram FTS5 table for substring matching
        self.conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS docs_trigram USING fts5(
                title, content,
                tokenize='trigram'
            )
        """)
        # Metadata table for extra fields
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS docs_meta(
                rowid INTEGER PRIMARY KEY,
                source TEXT,
                added TEXT
            )
        """)
        self.conn.commit()

    def index(self, title: str, content: str, tags: str = "",
              source: str = "", added: str = ""):
        """Index a document into both FTS5 tables."""
        cur = self.conn.execute(
            "INSERT INTO docs(title, content, tags) VALUES (?, ?, ?)",
            (title, content, tags)
        )
        rowid = cur.lastrowid
        self.conn.execute(
            "INSERT INTO docs_trigram(rowid, title, content) VALUES (?, ?, ?)",
            (rowid, title, content)
        )
        self.conn.execute(
            "INSERT INTO docs_meta(rowid, source, added) VALUES (?, ?, ?)",
            (rowid, source, added)
        )
        self.conn.commit()
        return rowid

    def search(self, query: str, limit: int = 5) -> list[dict]:
        """Three-layer search with automatic fallback."""
        # Layer 1: Porter stemming match
        results = self._search_porter(query, limit)
        if results:
            return [dict(r, match_layer="porter") for r in results]

        # Layer 2: Trigram substring match
        results = self._search_trigram(query, limit)
        if results:
            return [dict(r, match_layer="trigram") for r in results]

        # Layer 3: Levenshtein fuzzy correction
        results = self._search_fuzzy(query, limit)
        return [dict(r, match_layer="fuzzy") for r in results]

    def _search_porter(self, query: str, limit: int) -> list[dict]:
        rows = self.conn.execute("""
            SELECT rowid, title, snippet(docs, 1, '>>>', '<<<', '...', 32) as snippet,
                   rank
            FROM docs WHERE docs MATCH ?
            ORDER BY rank LIMIT ?
        """, (query, limit)).fetchall()
        return [{"rowid": r[0], "title": r[1], "snippet": r[2], "score": r[3]}
                for r in rows]

    def _search_trigram(self, query: str, limit: int) -> list[dict]:
        rows = self.conn.execute("""
            SELECT rowid, title, snippet(docs_trigram, 1, '>>>', '<<<', '...', 32) as snippet,
                   rank
            FROM docs_trigram WHERE docs_trigram MATCH ?
            ORDER BY rank LIMIT ?
        """, (query, limit)).fetchall()
        return [{"rowid": r[0], "title": r[1], "snippet": r[2], "score": r[3]}
                for r in rows]

    def _search_fuzzy(self, query: str, limit: int) -> list[dict]:
        """Correct query terms via Levenshtein distance, then re-search."""
        # Get all indexed terms for comparison
        words = query.split()
        corrected = []
        for word in words:
            best = self._find_closest_term(word)
            corrected.append(best if best else word)
        corrected_query = " ".join(corrected)
        if corrected_query != query:
            return self._search_porter(corrected_query, limit)
        return []

    def _find_closest_term(self, word: str, max_distance: int = 2) -> str | None:
        """Find the closest indexed term using Levenshtein distance."""
        rows = self.conn.execute(
            "SELECT DISTINCT term FROM docs_trigram WHERE term MATCH ?",
            (word[:3],)  # Use first 3 chars as trigram seed
        ).fetchall()
        best_term, best_dist = None, max_distance + 1
        for (term,) in rows:
            d = _levenshtein(word.lower(), term.lower())
            if d < best_dist:
                best_term, best_dist = term, d
        return best_term if best_dist <= max_distance else None


def _levenshtein(s: str, t: str) -> int:
    """Compute Levenshtein edit distance."""
    if len(s) < len(t):
        return _levenshtein(t, s)
    if len(t) == 0:
        return len(s)
    prev = list(range(len(t) + 1))
    for i, sc in enumerate(s):
        curr = [i + 1]
        for j, tc in enumerate(t):
            curr.append(min(
                prev[j + 1] + 1, curr[j] + 1,
                prev[j] + (0 if sc == tc else 1)
            ))
        prev = curr
    return prev[-1]


# --- Demo ---
if __name__ == "__main__":
    db = FTS5Search()

    # Index some documents
    db.index("Quicksort Implementation", "def quicksort(arr): partition and recurse", "algorithm,python")
    db.index("Async HTTP Client", "aiohttp session for concurrent requests", "python,async,http")
    db.index("useEffect Hook", "React useEffect for side effects in components", "react,javascript,hooks")
    db.index("Docker Compose Setup", "multi-container orchestration with docker-compose.yml", "docker,devops")

    # Layer 1: exact match via porter stemming
    print("=== 搜索 'sorting algorithm' ===")
    for r in db.search("sorting algorithm"):
        print(f"  [{r['match_layer']}] {r['title']}: {r['snippet']}")

    # Layer 2: trigram substring match
    print("\n=== 搜索 'useEff' (子串) ===")
    for r in db.search("useEff"):
        print(f"  [{r['match_layer']}] {r['title']}: {r['snippet']}")

    # Layer 3: fuzzy match (typo)
    print("\n=== 搜索 'asynch http' (拼写错误) ===")
    for r in db.search("asynch http"):
        print(f"  [{r['match_layer']}] {r['title']}: {r['snippet']}")
