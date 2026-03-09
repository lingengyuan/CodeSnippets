# Symphony：OpenAI Agent 编排系统规格精读

**来源**: [openai/symphony SPEC.md](https://raw.githubusercontent.com/openai/symphony/refs/heads/main/SPEC.md)
**日期**: 2026-03-08
**标签**: agent-orchestration, FSM, workspace-isolation, linear-tracker, codex, retry-strategy

---

## 30秒 TL;DR

> Symphony 是一个 Issue Tracker → Agent 的调度器：从 Linear 读取 issue，给每个 issue 派发一个 codex 子进程在隔离 workspace 里工作，用 FSM 管理 issue 生命周期。核心架构哲学：**编排器只读 Tracker，Agent 写 Tracker**；所有持久状态在 Tracker + 文件系统里，编排器无数据库，崩溃重启零状态丢失。

---

## 概念总览

| 概念 | 核心思想 | 对应 mini_symphony |
|------|---------|---------|
| Issue Claim FSM | 5 状态防重复派发 | TASKS.md 的 `[ ]`/`[x]` 标记 |
| Run Attempt FSM | 11 阶段追踪每次 agent 尝试 | max_rounds 计数 |
| Workspace 持久化 | 同一 issue 跨次重试复用同一目录 | 每次重新创建（可改进） |
| Hook 扩展点 | 4 个生命周期 shell 脚本 | 无 |
| Blocker 规则 | Todo issue 有未完成依赖则不派发 | 无 |
| 两类重试策略 | continuation（固定 1s）vs failure（指数退避） | 统一 max_rounds |
| Tracker-driven 恢复 | 重启后 poll Tracker 重建状态，无需数据库 | 重启后扫描 TASKS.md |

---

## 深读

### Issue 生命周期 FSM（5 状态）

```
Unclaimed → Claimed → Running → [成功完成]
                   ↘ RetryQueued → [重新 Running]
              Released ← [终态/不符合条件/重试完成]
```

**关键设计**：`Claimed` 状态在 `Running` 之前，用于防止并发编排器重复派发同一 issue。

### Run Attempt 生命周期（11 阶段）

```
PreparingWorkspace → BuildingPrompt → LaunchingAgentProcess
→ InitializingSession → StreamingTurn → Finishing
→ [Succeeded | Failed | TimedOut | Stalled | CanceledByReconciliation]
```

每个终态触发不同的重试逻辑和可观测性日志。

### Workspace 隔离（3 条安全不变式）

1. **执行边界**：agent 只在 per-issue workspace 路径里运行
2. **路径包含**：workspace 路径必须是 workspace root 的绝对路径前缀子集
3. **名称净化**：`[A-Za-z0-9._-]` 以外的字符 → 下划线

**workspace 持久化**：同一 issue 的多次重试复用同一目录。成功完成不自动删除，通过 Tracker 终态触发清理（reconciliation 或启动扫描）。

### 4 个生命周期 Hook

| Hook | 触发时机 | 失败行为 |
|------|---------|---------|
| `after_create` | 新 workspace 创建后 | Fatal：中止创建 |
| `before_run` | 每次 agent 尝试前 | Fatal：中止本次尝试 |
| `after_run` | 每次尝试结束（无论结果） | 记录日志，忽略 |
| `before_remove` | workspace 删除前 | 记录日志，忽略 |

Hook 是 workspace 目录下的 shell 脚本，`timeout_ms` 默认 60 秒。

### codex App-Server 协议（4 步握手）

```
Client → codex app-server (stdio, line-delimited JSON)

1. initialize {clientInfo, capabilities}
   ← response
2. initialized  [notification]
3. thread/start {approvalPolicy, sandbox, cwd}
   ← {thread.id}
4. turn/start {threadId, prompt, title, sandboxPolicy}
   ← stream: turn/completed | turn/failed | turn/cancelled | timeout
```

`session_id = thread_id + "-" + turn_id`

**Continuation turn**：同一 thread_id 复用，只发 guidance，不重发原始 prompt（避免 context 重复）。

### 两类重试策略

```python
# Continuation retry（正常完成，检查是否需要继续）
delay = 1000  # 固定 1 秒

# Failure retry（异常退出）
delay = min(10000 * (2 ** (attempt - 1)), max_retry_backoff_ms)
# 默认 max_retry_backoff_ms = 300000（5 分钟）
```

**关键区分**：continuation = 正常工作流（agent 完成一轮，看看还有没有工作）；failure = 出错（需要等待冷却）。两类混用会过度惩罚正常完成。

### 候选资格规则（所有条件同时满足才派发）

- `id`、`identifier`、`title`、`state` 字段存在
- state 在 `active_states` 且不在 `terminal_states`
- 未在运行、未被 claim
- 全局并发槽位可用
- per-state 并发槽位可用
- **Blocker 规则**：Todo state 的 issue 若有任何非终态 blocker，不派发

### 调度循环（每个 poll tick）

```
1. Reconcile（stall 检测 + Tracker 状态刷新）
2. Preflight 校验（workflow、tracker、codex 命令）
3. Fetch 候选 issue
4. 排序：priority ↑ → creation_time 最老 → identifier 字典序
5. 按并发上限派发
6. 通知可观测性消费者
```

校验失败 → 跳过派发，但 reconcile 继续执行。

---

## 心智模型

> **"编排器 = 调度器 + 读者；Agent = 执行者 + 写者。"** Symphony 永远不写 Tracker，只读。这意味着你可以随时把 Symphony 接到任何已有的 Linear 项目上，它不会污染你的 backlog。

**适用条件**：Linear（或兼容 tracker），单机部署，issue 级别的并发任务。
**失效条件**：多机分布式部署（单编排器权威假设失效，需要分布式锁）；非 Linear tracker（需要实现新的 tracker adapter）。
**在我的工作中如何用**：mini_symphony 已经实现了类似的"编排器只读 TASKS.md，agent 写文件"的模式——这验证了该架构方向的正确性。下一步可以借鉴 Symphony 的 per-task workspace 持久化和 blocker 规则。

---

## 非显见洞见

- **洞见**：编排器不持久化状态——崩溃重启后 poll Tracker + 扫描文件系统即可重建完整状态
  - 所以：Symphony 的"数据库"就是 Linear + 文件系统，两者都在编排器外部
  - 所以：更新 Symphony 二进制无需数据迁移、无需协调正在运行的 agent
  - 因此可以：mini_symphony 可以采用同样模式——把所有状态外化到 TASKS.md + workspace 目录，重启只需重新扫描，不需要 state 序列化

- **洞见**：Continuation retry（1s）和 Failure retry（指数退避）是两种本质不同的事件，不能共用一套策略
  - 所以：把正常完成和失败都用"等待重试"处理会过度惩罚正常工作流
  - 所以：mini_symphony 的 `max_rounds` 无法区分"agent 主动完成一轮"和"agent 崩溃"
  - 因此可以：给 mini_symphony 的退出码赋予语义——exit(0) = continuation，exit(1) = failure，分别触发不同的重试延迟

- **洞见**：Workspace 跨重试持久化让 agent 能从上次失败的地方继续工作
  - 所以：agent 不需要重新做已经完成的文件修改，只需要从断点继续
  - 所以：这对长任务（数小时的代码重构）的成本效益尤其显著
  - 因此可以：mini_symphony 目前每次重试都在新的工作目录里启动——改为复用 per-issue workspace 可以显著减少重复工作

---

## 隐含假设

- **假设：单编排器权威**。用来避免重复派发。若不成立（多实例并行运行）：两个编排器可能同时 claim 同一 issue——需要 distributed lock（Redis SET NX 或数据库行锁）。

- **假设：Linear 作为唯一 Tracker**。GraphQL schema 是 Linear 特有的。若不成立（GitHub Issues、Jira）：需要实现新的 tracker adapter；当前 issue 字段命名强依赖 Linear 的 API 格式。

- **假设：codex app-server 可在本地执行**。stdio 协议假设子进程与编排器在同一机器。若不成立（远程 agent 执行）：需要 WebSocket 或 gRPC 替代 stdio。

---

## 反模式与陷阱

- **Stall detection 被禁用的隐患**：`stall_timeout_ms ≤ 0` 完全禁用 stall 检测 → hung agent 永久占用并发槽位，其他 issue 无法被派发。→ 正确做法：始终设置合理的 stall timeout（默认 5 分钟是合理起点）；在 `after_run` hook 里记录每次 agent 的实际执行时间用于调优。

- **`before_run` hook bug 导致全面停工**：`before_run` 失败是 Fatal，当前 attempt 中止。如果 hook 有 bug 且无法修复，所有 issue 都无法被派发。→ 正确做法：hook 脚本必须有 dry-run 模式；上线前在非生产 workspace 测试；`after_run` 可以用于记录 hook 的输出便于调试。

- **Workspace 名称净化不完整**：若净化逻辑漏掉某个字符类（如 Unicode 字符），issue identifier 中的特殊字符可能产生路径穿越风险（`../` 序列）。→ 正确做法：白名单而非黑名单：只允许 `[A-Za-z0-9._-]`，其余全部替换为下划线；在创建 workspace 前验证最终路径是 root 的子路径。

- **Per-tick reconciliation 的时间窗口盲区**：如果 Tracker 状态在两次 poll 之间变化又恢复（issue 被 close 后立刻 reopen），编排器可能错过这次状态变化。→ 正确做法：在 agent 写入 Tracker 的关键操作前，先验证 issue 当前状态；不依赖编排器的 snapshot 与 Tracker 完全同步。

---

## 与现有知识库的连接

- 关联 `python/mini_symphony.py`：Symphony 的 per-issue workspace 持久化（跨重试复用目录）、blocker 规则、两类重试策略都是 mini_symphony 可以直接借鉴的增强点；Symphony 的 stall detection 对应 mini_symphony 的 `max_rounds` 但更准确（基于时间而非步骤数）
- 关联 `snippets/atomic-file-write.rs`：Symphony 的 workspace 安全不变式（路径包含验证）与原子写入的"防崩溃写入"共享同一类安全思维——在文件系统操作中，防御性检查比事后恢复更便宜
- 关联 `python/sandbox_execute.py`：Symphony 的 codex subprocess + stdio 协议与 sandbox_execute 的 subprocess 隔离模式完全一致；sandbox_execute 可以作为 mini_symphony worker 的执行沙箱

---

## 衍生项目想法

### mini_symphony 退出码语义化（Continuation vs Failure 分离）

**来源组合**：[Symphony: continuation retry 1s fixed vs failure retry exponential backoff] + [mini_symphony: max_rounds 统一处理所有退出]
**为什么有意思**：mini_symphony 目前把"agent 正常完成所有 turns"和"agent 崩溃/超时"用同一套逻辑处理，这错误地惩罚了正常完成的任务；Symphony 的两类重试策略揭示了这是两种本质不同的事件
**最小 spike**：给 mini_symphony 定义退出码语义（exit 0 = 正常完成，exit 1 = 失败），在 orchestrator 层根据退出码分别触发 1s 重检 vs 指数退避重试
**潜在难点**：子进程（pi/claude CLI）的退出码语义不一定由 mini_symphony 控制，需要封装一层

### mini_symphony per-task Workspace 持久化

**来源组合**：[Symphony: workspace 跨重试持久化，agent 从断点继续] + [mini_symphony: 每次任务在新目录启动]
**为什么有意思**：当前 mini_symphony 的任务失败后重试时，agent 看不到上次的工作产物（已修改的文件、已生成的代码），需要从零开始；Symphony 的持久化 workspace 让 agent 的重试成本接近于"继续"而非"重做"
**最小 spike**：在 TASKS.md 格式里加 `workspace: ./workspaces/{task-id}` 字段；mini_symphony 在 `before_run` 时创建/复用该目录；agent 在该目录下工作
**潜在难点**：需要处理 workspace 污染问题——上次失败的中间状态文件可能干扰新的尝试；需要 `before_run` hook 做状态清理或 git stash

### TASKS.md 依赖关系（Blocker 规则）

**来源组合**：[Symphony: Todo issue 有未完成 blocker 则不派发] + [mini_symphony: TASKS.md 任务队列无依赖关系]
**为什么有意思**：当前 TASKS.md 任务是完全平行的，无法表达"任务 B 依赖任务 A 的输出"；加入 blocker 规则后，mini_symphony 可以处理有 DAG 依赖关系的任务图，而不仅仅是独立任务队列
**最小 spike**：扩展 TASKS.md 格式，支持 `blocked_by: [task-1, task-2]`；mini_symphony 在选择下一个任务时跳过有未完成 blocker 的任务
**潜在难点**：TASKS.md 是 Markdown checklist 格式，解析依赖关系需要约定注释格式；需要防止循环依赖
