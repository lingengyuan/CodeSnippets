# 全局方向综合分析 v2

**日期**: 2026-03-05
**在 v1 基础上新增素材**:
- `analysis/pi-context-engineering.md` — 900 token Coding Agent 的七个设计决策
- `analysis/symphony-orchestration-spec.md` → 已落地为 `python/mini_symphony.py`
- `ideas/yt-browse-local-first-channel-browser.md` — Fetch-Cache-Search 本地优先模式
- `ideas/mapreduce-rust-patterns.md` → 已落地为 `snippets/kway-merge-heap.rs`, `snippets/atomic-file-write.rs`

---

## 当前库存（完整）

| 编号 | 素材 | 核心能力 | 状态 |
|------|------|---------|------|
| A | `snippet_manager.py` | 片段存储 + 自然语言搜索 + prompt 组合 | 可运行 |
| B | `tape_context.py` | 锚点上下文管理，按需装配，不继承历史 | 可运行 |
| C | `zvec_inprocess_vector.py` | in-process 向量库，混合检索，零服务 | 可运行 |
| D | `fts5_fuzzy_search.py` | SQLite FTS5 三层模糊搜索（精确→子串→Levenshtein）| 可运行 |
| E | `sandbox_execute.py` | 沙箱子进程执行 + stdout 压缩 | 可运行 |
| F | `mini_symphony.py` | 任务队列编排 + workspace 隔离 + 指数退避重试 | 可运行 |
| G | `snippets/kway-merge-heap.rs` | BinaryHeap min-heap + K-way 归并 | 可运行 |
| H | `snippets/atomic-file-write.rs` | tmp + rename 原子写入 | 可运行 |

**新增设计模式（尚未落地为代码）：**

| 模式 | 来源 | 核心价值 |
|------|------|---------|
| P1 | pi — Progressive Disclosure | 工具定义按需加载，不预占 context |
| P2 | pi — PLAN.md as state | 跨 session 的任务状态持久化到文件 |
| P3 | pi — 4-tool minimalism | bash 是万能工具，减少工具定义 token |
| P4 | yt-browse — Fetch-Cache-Search | 外部 API → 本地缓存 → 零 API 成本搜索 |
| P5 | yt-browse — Two-step cheap fetch | 先拿 ID 列表，再批量拿详情 |
| P6 | yt-browse — 统一三模式搜索接口 | word / regex / fuzzy 统一返回 rune index |
| P7 | MapReduce — 推测执行 | 超时任务发起备份执行，取先完成的 |

---

## 新增组合方向

### 组合七：P4 + D + insight-collector → 自动读物归档管线

**一句话**：把 insight-collector 从"人工触发"变成"持续运行的后台守护进程"。

**现状**：
```
手动：用户 drop URL → 触发 insight-collector → 分析 → 写入 CodeSnippets
```

**目标**：
```
READING_LIST.md（Markdown checklist）
      ↓  mini_symphony 轮询（F）
  per-URL workspace
      ↓  before_run: curl/WebFetch 缓存到本地（P4）
  insight-collector 分析（已有 skill）
      ↓  after_run: 标记为已完成 [ ]→[x]
  CodeSnippets 自动更新
```

**关键决策**：
- 缓存用 `~/.codesnippets/cache/<url-hash>/content.md`，24h TTL（yt-browse 模式）
- 搜索用 D（FTS5），不需要 API
- 去重：URL hash 作为 workspace key，已处理的不重复归档

**实现量**：READING_LIST.md 模板 + mini_symphony 的 WORKFLOW.md 配置 ≈ 30 行配置，零新代码

---

### 组合八：P1 + A + C → snippet_manager 的懒加载语义化升级

**一句话**：让 agent 能"按需"找到并加载 snippet，而不是一次把所有片段塞进 context。

**pi 的核心洞见**：MCP 把所有工具定义都预加载进 context（Playwright MCP = 13,700 token）。
正确的方式是 **Progressive Disclosure**：需要时才读，用 bash 调用。

**对应到 CodeSnippets**：

| 现在（被动笔记本） | 升级后（懒加载工具库） |
|------------------|---------------------|
| agent 要用某个模式 → 不知道去哪找 | agent 执行 `python snippet_manager.py search "并发"` → 得到文件路径 |
| 全部 snippets 塞进 prompt（贵） | 按需 `read` 单个文件（便宜）|
| 无向量检索 | 接入 zvec，"语义搜索 parallel patterns" → 命中 asyncio_pool.py |

**实现量**：
1. `snippet_manager.py` 加 `search` 子命令，输出 `path: 相关度` 列表（~20 行）
2. `snippet_manager.py` 加 `combine --task "描述"` → 语义检索 top-3 + 合并 prompt（~30 行）
3. 接入 zvec（参考 `idea-combinations.md` 组合一，约 50 行）

**使用方式**：
```bash
# agent 在 bash 里调用，而不是把所有 snippets 预加载进 context
python snippet_manager.py search "原子文件写入"
# → snippets/atomic-file-write.rs (score: 94)

python snippet_manager.py combine --task "实现一个有重试的任务调度器"
# → 合并 mini_symphony.py + tape_context.py 的相关片段为 prompt
```

---

### 组合九：P2 + B → tape_context 跨 session 持久化（PLAN.md 模式）

**一句话**：tape 的锚点加一层文件持久化，实现跨 session 的"断点续跑"。

**pi 的 PLAN.md 是什么**：一个文件，记录"正在做什么 + 到哪步了 + 下一步是什么"。
它的优势是：可 Git 版本控制、跨 session 可读、agent 和人都能编辑。

**tape 的现状**：锚点只活在内存里，session 结束即消失。

**融合方案**：
```python
# tape_context.py 新增两个方法：
def save_to_plan(self, path="PLAN.md"):
    """把最新锚点写入 PLAN.md，作为跨 session 的检查点"""

def resume_from_plan(self, path="PLAN.md"):
    """新 session 开始时，从 PLAN.md 恢复最后锚点"""
```

PLAN.md 格式（pi 风格）：
```markdown
---
tape_version: 1
last_anchor_at: 2026-03-05T14:23:00
---
## 当前任务
实现 snippet_manager 的语义搜索升级

## 已完成
- [x] 分析 zvec API
- [x] 设计 search 子命令接口

## 当前步骤
实现 embed + store 逻辑（`load_snippet` 时自动 embed）

## 下一步
集成测试：用 zvec 搜索 10 个 snippets，验证相关度排序
```

**实现量**：tape_context.py 加约 40 行，PLAN.md 模板 1 个文件

---

### 组合十：F + E + P7 → mini_symphony 加推测执行

**一句话**：mini_symphony 已有重试，加上"慢任务备份执行"，让编排器更像 Symphony 原版。

**MapReduce 推测执行的本质**：
- 如果一个任务运行超过阈值，不等它完成，立刻启动另一个 worker 做同样的任务
- 取先完成的结果，kill 另一个

**在 mini_symphony 中的应用**：
```python
# mini_symphony.py 新增：
# 如果某 task 运行超过 stall_timeout（当前只是 kill），
# 改为：fork 一个新 workspace 跑同一 task，两个并行，取先完成的
```

**实现量**：mini_symphony.py 加约 60 行（参考 mapreduce 的 `can_speculate` 逻辑）

---

## 优先级矩阵（更新版）

| 组合 | 投入 | 独立价值 | 协同价值 | 建议时序 |
|------|------|---------|---------|---------|
| **八：snippet_manager 语义化** | ~100 行 | ⭐⭐⭐⭐⭐ | 是所有组合的工具基础 | **立刻** |
| **七：自动读物归档管线** | ~30 行配置 | ⭐⭐⭐⭐⭐ | 直接利用现有 skill + mini_symphony | **立刻** |
| **九：tape + PLAN.md** | ~40 行 | ⭐⭐⭐⭐ | 解决跨 session 断点问题 | 第二批 |
| 轨道一 Step 3-4：MCP Server | 中等 | ⭐⭐⭐⭐⭐ | 需要组合八完成 | 组合八之后 |
| **十：推测执行** | ~60 行 | ⭐⭐⭐ | 增强 mini_symphony | 按兴趣 |
| 轨道四：交互式可视化 HTML | ~1小时/个 | ⭐⭐⭐⭐ | 独立，随时可加 | 穿插 |
| 轨道二：完整 Agent 记忆框架 | 较大 | ⭐⭐⭐⭐⭐ | 需要组合八+九 | 积累后 |

---

## 最小可行第一步

**现在最值得动手的是组合七**，因为：

1. **零新代码**：只需要写一个 `WORKFLOW.md` + `READING_LIST.md`，利用已有的 mini_symphony + insight-collector
2. **立竿见影**：马上有一个"URL 丢进去，自动归档"的工作流
3. **验证假设**：如果用起来顺，再优化；如果不顺，说明需要先做组合八（更好的搜索）

**需要创建的两个文件**：
```
CodeSnippets/
├── READING_LIST.md      # [ ] URL1 \n [ ] URL2 → mini_symphony 的任务源
└── WORKFLOW.md          # mini_symphony 配置 + insight-collector 的 prompt 模板
```

---

## 参考文件索引（完整）

| 文件 | 关键内容 |
|------|---------|
| `ideas/agentic-hoarding-patterns.md` | agent 读已有代码组合新工具 |
| `ideas/context-mode-patterns.md` | 沙箱 + stdout 过滤的 context 压缩架构 |
| `ideas/zvec-directions.md` | sgrep / embedding cache / 单脚本 RAG 六个方向 |
| `ideas/yt-browse-local-first-channel-browser.md` | Fetch-Cache-Search + 统一搜索接口 |
| `ideas/mapreduce-rust-patterns.md` | 推测执行 + K-way 归并 + 原子写入 |
| `analysis/idea-combinations.md` | 旧版五组组合（A+C/B+C/E+A/MCP Server）|
| `analysis/directions-synthesis.md` | 旧版四条轨道 + 优先级矩阵 |
| `analysis/simon-willison-agentic-patterns.md` | TDD / WASM封装 / 交互式解释 |
| `analysis/pi-context-engineering.md` | 极简 prompt / 4 工具 / PLAN.md / 渐进式披露 |
| `analysis/symphony-orchestration-spec.md` | 状态机 / WORKFLOW.md / 推测执行 / workspace |
