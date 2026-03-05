# Symphony：OpenAI 的 Agent 编排系统规格分析

> 来源: https://github.com/openai/symphony
> 日期: 2026-03-05
> 语言: Elixir（参考实现），SPEC.md 语言无关
> 标签: agent orchestration, issue tracker, state machine, workspace isolation, coding agent

---

## 一句话

Symphony 是一个 daemon，它监听 Linear 看板，把 issue 转化为隔离的 workspace，调起 Coding Agent（Codex）执行，并通过指数退避重试保证最终交付。

---

## 核心架构

```
Linear Issue Board
       ↓  (30s 轮询)
  Orchestrator
  ├── Candidate 筛选（priority → age → identifier 排序）
  ├── Concurrency 控制（全局 + 按状态分槽位）
  ├── Workspace Manager（per-issue 目录，一次创建多次复用）
  └── Agent Runner
        ├── 构建 prompt（Liquid 模板 + issue 变量）
        ├── 启动 codex app-server 子进程
        └── 读 stdout JSON-RPC 流直到 turn/completed
```

六个抽象层：`Policy → Config → Coordination → Execution → Integration → Observability`

---

## 值得复用的设计模式

### 1. 五态状态机（Issue Orchestration States）

```
Unclaimed
   ↓ dispatch
 Claimed    ← 防止重复 dispatch 的"锁"
   ↓ launch
 Running    ← 有 worker task
   ↓ fail
RetryQueued ← 有退避定时器
   ↓ terminal/gone
 Released
```

关键设计：`Claimed` 状态是一个"预留"状态，不是真正在跑。先 claim，再 launch，防止并发 tick 重复 dispatch 同一个 issue。

---

### 2. Run Attempt 生命周期（线性状态机）

```
PreparingWorkspace
→ BuildingPrompt
→ LaunchingAgentProcess
→ InitializingSession
→ StreamingTurn
→ Finishing
→ {Succeeded | Failed | TimedOut | Stalled | CanceledByReconciliation}
```

---

### 3. Workspace 隔离三条安全不变量

```python
# 不变量 1: agent 只能在自己的 workspace 目录里运行
assert cwd == workspace_path

# 不变量 2: workspace 必须在 workspace root 下（防止路径穿越）
assert os.path.abspath(workspace_path).startswith(os.path.abspath(workspace_root))

# 不变量 3: workspace key 只允许 [A-Za-z0-9._-]，其他字符替换为 _
workspace_key = re.sub(r'[^A-Za-z0-9._-]', '_', issue.identifier)
```

---

### 4. WORKFLOW.md 模式：配置 + Prompt 合一

```yaml
---
# YAML front matter = 配置
tracker:
  kind: linear
  api_key: $LINEAR_API_KEY
  project_slug: my-project
  active_states: "Todo, In Progress"

polling:
  interval_ms: 30000

agent:
  max_concurrent_agents: 10

hooks:
  after_create: |
    git clone $REPO_URL .
    npm install
  before_run: |
    git fetch && git checkout main
---

# Markdown body = Prompt Template（Liquid 语法）
你是一个 coding agent，请完成以下 issue：

**标题**: {{ issue.title }}
**描述**: {{ issue.description }}

{% if attempt %}
这是第 {{ attempt }} 次重试。请先查看上次的错误，再开始工作。
{% endif %}
```

**好处**：配置和 prompt 版本控制在同一文件；动态热重载无需重启；prompt 能感知重试次数。

---

### 5. 两种重试策略

```
Continuation retry（正常退出但未完成）:
  delay = 1000 ms (固定)

Failure retry（出错）:
  delay = min(10000 × 2^(attempt-1), max_retry_backoff_ms)
  默认 max = 300000 ms（5 分钟）

例: 1次失败→10s, 2次→20s, 3次→40s, ... 上限5分钟
```

---

### 6. Coding Agent App-Server 通信协议

Agent 作为子进程运行，通过 **stdout 的换行分隔 JSON** 通信（stderr 忽略）：

```
# 启动握手顺序（严格有序）
orchestrator → agent:  initialize request
agent → orchestrator:  initialized notification
orchestrator → agent:  thread/start request
agent → orchestrator:  thread/start result  ← 拿到 thread_id
orchestrator → agent:  turn/start request
agent → orchestrator:  turn/start result    ← 拿到 turn_id

# 运行期
agent → orchestrator:  [各种事件消息流...]
agent → orchestrator:  turn/completed | turn/failed | turn/cancelled

# Session ID
session_id = f"{thread_id}-{turn_id}"

# 续跑（继续用同一 thread）
orchestrator → agent:  turn/start (reuse threadId, new turnId)
```

**Continuation** = 同一 thread 下多个 turn；**Retry** = 全新 thread。

---

### 7. 并发控制（双层槽位）

```python
# 全局槽
available = max_concurrent_agents - len(running)

# 按状态槽（覆盖全局）
if state in max_concurrent_agents_by_state:
    state_available = max_concurrent_agents_by_state[state] - count_running_in_state(state)
    available = min(available, state_available)

# dispatch 优先级排序
candidates.sort(key=lambda i: (i.priority, i.created_at, i.identifier))
```

---

### 8. Reconciliation（主动终止检测）

每次 poll tick 除了 dispatch 新任务，还要做 reconciliation：

```
Part A — Stall 检测:
  elapsed = now - max(last_codex_timestamp, started_at)
  if elapsed > stall_timeout_ms → terminate + retry

Part B — Tracker 状态同步:
  fetch 所有 running issue 的当前状态
  terminal state → terminate + cleanup workspace
  active state   → 更新快照
  其他           → terminate，不清理（可能是状态异常）
```

---

### 9. 生命周期钩子

```bash
# 4 个钩子（均在 workspace 目录下以 bash -lc 执行）
after_create:  初始化 workspace（克隆代码、安装依赖）  失败→中止
before_run:    每次 attempt 前准备（git pull、清理）    失败→中止本次
after_run:     每次 attempt 后清理                      失败→仅记录
before_remove: workspace 删除前                         失败→仅记录
```

---

## 单一可信内存状态（重要设计决策）

Orchestrator 维护一个**单一权威内存状态**，没有外部数据库：

```
{
  poll_interval_ms,
  max_concurrent_agents,
  running: Map<issue_id, LiveSession>,
  claimed: Set<issue_id>,
  retry_attempts: Map<issue_id, RetryEntry>,
  completed: Set<issue_id>,
  codex_totals: { input_tokens, output_tokens, seconds_running },
  codex_rate_limits: ...
}
```

**重启代价**：所有 retry timer 丢失，但 running agents 不受影响（它们是独立子进程）；重启后下次 poll 会重新 dispatch 未完成的 issue。这是**有意的简化**，规格中明确写了 "TODO: Persist retry queue/session metadata across restarts"。

---

## 与现有 snippets 的关联

| Symphony 概念 | CodeSnippets 相关文件 |
|--------------|----------------------|
| 单次 turn 的 Agent 执行 | `python/sandbox_execute.py`（隔离子进程执行） |
| 多轮 context 管理 | `python/tape_context.py`（anchor-based context） |
| Simon Willison 的 agentic 模式 | `analysis/simon-willison-agentic-patterns.md` |

---

## 可以延伸的方向

### 方向 A：Python 迷你 Symphony
用 Python 实现 SPEC 的核心子集：Linear 轮询 + 子进程 Agent + 指数退避。不需要 Elixir，SPEC 是语言无关的。核心只需要：

```python
# 伪代码骨架
while True:
    issues = linear.fetch_candidates()
    for issue in prioritized(issues):
        if slots_available() and not claimed(issue):
            claim(issue)
            spawn_agent(issue)   # 参考 sandbox_execute.py
    reconcile_running()
    sleep(poll_interval)
```

### 方向 B：WORKFLOW.md 模式用于个人任务
把 WORKFLOW.md 的"配置 + prompt 合一 + 热重载"模式用于个人 agent workflow 管理。比如：一个 `WORKFLOW.md` 定义"每天处理 GitHub notifications"的规则和 prompt。

### 方向 C：App-Server 协议的 Mock 实现
写一个 mock codex app-server，用于测试 orchestrator 逻辑，不依赖真实的 Codex/Claude Code。协议是 line-delimited JSON，很容易用 Python subprocess 模拟。

---

## 可选 HTTP API（/api/v1）

```
GET  /api/v1/state                    # 全局状态快照
GET  /api/v1/<issue_identifier>       # 单 issue 详情
POST /api/v1/refresh                  # 立即触发一次 poll（202 Accepted）
```

---

## 关键取舍总结

| 决策 | 选择 | 理由 |
|------|------|------|
| 状态存储 | 纯内存 | 简单；重启后重新 dispatch 即可 |
| 重试 | 指数退避 + cap | 避免无限快重试；continuation 用固定 1s |
| Workspace | 磁盘目录，复用 | Agent 需要持久上下文（git history 等） |
| 配置 | WORKFLOW.md 热重载 | 不重启服务改策略；prompt 也可更新 |
| Ticket 写操作 | 交给 Agent，非 Orchestrator | Orchestrator 职责边界清晰 |
| 安全 | 路径校验 + 容器 | Agent 可信环境；容器是推荐但非强制 |
