# Rust MapReduce 单机实现 精读

**来源**: [Aditya-1304/mapreduce](https://github.com/Aditya-1304/mapreduce)
**日期**: 2025-01-14
**标签**: rust, mapreduce, parallel-processing, k-way-merge, fault-tolerance, concurrency, systems-programming

---

## 30秒 TL;DR

> 这是一个纯 Rust 标准库实现的单机多线程 MapReduce 引擎，忠实还原了 Google 2004 论文的核心机制（Master/Worker 架构、R 分区哈希、K-way 外部归并排序、推测执行、原子文件重命名），
> 同时以明确的 7 条偏差声明诚实地标注了"我做了什么妥协、为什么"。
> 最大的价值在于：**将分布式系统的容错模式映射到本地线程可以直接运行的 Rust 代码**。

---

## 概念总览

| 概念/模式 | 核心思想 | 适用场景 |
|---------|---------|---------|
| Master/Worker 架构 | Master 持有全部状态机，Worker 轮询任务——无共享内存 | 任何需要"协调者+执行者"分离的并行任务调度 |
| R 桶哈希分区 | Map 输出按 `ihash(key) % R` 分桶，保证同一 key 必落入同一 Reducer | 需要按 key 聚合的流水线处理 |
| K-way 外部归并 | BinaryHeap min-heap 同时持有 K 个文件游标，peek 比较+整组聚合 | 内存受限时合并多个已排序文件 |
| 推测执行（Speculative Execution） | 慢任务超过阈值后，同时启动备份任务，先完成者获胜 | 长尾延迟缓解（straggler mitigation） |
| 原子文件重命名 | 先写 `.tmp-PID-TID`，再 `fs::rename` → 操作系统原子保证 | 防止崩溃/并发写入产生脏文件 |
| mpsc 双向通道协议 | Worker→Master：event channel；Master→Worker：per-request reply channel | 无锁状态协调，Rust 所有权天然隔离 |
| TaskToken + attempt 计数 | 每次任务分配携带唯一 attempt ID，区分原始任务与备份任务 | 去重完成信号，防止重复计数 |

---

## 深读

### 1. 执行流水线全景

```
run()
├── prepare_work_dir()          清理 mr-tmp/ 下的所有 mr-* 文件
├── Master::new()               初始化 M 个 MapTask + R 个 ReduceTask 状态机
├── mpsc::channel()             创建 Worker→Master 的 event 通道
├── thread::spawn(master_loop)  Master 在独立线程中 recv 事件
├── [×N] thread::spawn(worker_loop)
│        ↓ RequestTask → reply channel
│        ↓ 收到 Map/Reduce/Wait/Exit
│        ├── run_map_task()
│        │     ├── fs::read_to_string()
│        │     ├── map_fn()
│        │     ├── 哈希分桶 → bucket.sort_unstable_by_key
│        │     └── [×R] tmp 写入 → fs::rename (原子)
│        └── run_reduce_task()
│              ├── 开 M 个 SourceReader（BufReader + scratch）
│              ├── K-way min-heap 归并 + 同 key 聚合
│              ├── reduce_fn()
│              └── tmp 写入 → fs::rename (原子)
└── merge_outputs()             读 R 个 mr-out-N → 排序 → mr-out-final (原子)
```

### 2. Master 状态机

Phase 枚举严格单向流转：`Map → Reduce → Done`（或任意时刻 `→ Failed`）。

```rust
fn update_phase(&mut self) {
    if self.phase == Phase::Map && self.map_tasks.iter().all(TaskMeta::is_completed) {
        self.phase = Phase::Reduce;    // 必须所有 Map 完成才进入 Reduce
    }
    if self.phase == Phase::Reduce && self.reduce_tasks.iter().all(TaskMeta::is_completed) {
        self.phase = Phase::Done;
    }
}
```

**关键约束**：Map 和 Reduce 不能并发——这是正确性保证（Reducer 需要读取所有 Map 的输出）。

### 3. TaskMeta：单任务的细粒度状态

```
TaskMeta {
  completed: bool        // 任何 attempt 成功 → true，后续 Complete 事件被丢弃
  retries: u32           // 累计失败/超时次数（含投机分支）
  next_attempt: u32      // 单调递增的 attempt 序号
  active: Vec<RunningAttempt>  // 通常 1 个，推测执行时 2 个
}
```

`mark_complete` 只接受存在于 `active` 列表中的 attempt，防止"幽灵完成"（过期的 attempt 迟到报告）。

### 4. K-way 外部归并的实现细节

```rust
// 核心循环：弹出最小 key，收集同 key 的所有 value
while let Some(entry) = heap.pop() {
    let key = entry.key;
    let mut values = vec![entry.value];
    refill_source(entry.source_idx, &mut sources, &mut heap)?;

    // peek 收集同 key 条目（不先 pop，避免浪费）
    while let Some(next) = heap.peek() {
        if next.key != key { break; }
        let same = heap.pop().unwrap();
        values.push(same.value);
        refill_source(same.source_idx, &mut sources, &mut heap)?;
    }
    let reduced = reduce_fn(&key, &values);
    write_kv_line(&mut writer, &key, &reduced)?;
}
```

**min-heap 技巧**：Rust `BinaryHeap` 默认 max-heap，在 `Ord` 实现中交换 `self/other`：
```rust
impl Ord for HeapEntry {
    fn cmp(&self, other: &Self) -> Ordering {
        other.key.cmp(&self.key)          // ← 反转：other 在前 = min-heap
            .then_with(|| other.source_idx.cmp(&self.source_idx))
    }
}
```

### 5. 原子文件写入的 TID 命名方案

```rust
fn temp_path(final_path: &Path) -> PathBuf {
    let pid = std::process::id();
    let tid = format!("{:?}", thread::current().id());
    PathBuf::from(format!("{}.tmp-{}-{}", final_path.display(), pid, tid))
}
```

`PID + ThreadId` 组合保证同一台机器上不同进程、不同线程的临时文件不冲突。

### 6. 推测执行的选择逻辑

```rust
fn pick_speculative_task(&self, tasks: &[TaskMeta], worker_id: usize) -> Option<usize> {
    let threshold = self.speculative_after?;
    let now = Instant::now();
    // 选择：运行时间最长（oldest_start 最早）且超过阈值的唯一在运行任务
    // 条件：active.len() == 1（已有备份任务的不再投机）
    //       worker_id 不是当前执行者（避免自我投机）
}
```

**设计约束**：`active.len() == 1` 防止无限制投机扩散（最多同时 2 个 attempt）。

### 7. mpsc 双向通道协议

```
Worker                          Master
  │──── RequestTask{reply_tx} ───→│
  │←─── TaskAssignment ──────────│  (reply_tx 是临时的一次性 channel)
  │──── Complete{token} ─────────→│
  │──── Failed{token, err} ───────→│
```

主通道单向（Worker→Master），reply 通道是按需创建的一次性 Sender，避免 Master 持有所有 Worker 的回写句柄。

---

## 与论文的 7 条偏差（逐条分析）

| 偏差 | 论文做法 | 本实现做法 | 影响 |
|------|---------|---------|------|
| 分布 vs 线程 | 跨机器 RPC | `std::thread` + `mpsc` | 无网络延迟，但不能水平扩展 |
| GFS + 数据局部性 | 计算迁移到数据所在节点 | 标准 OS 文件系统 | 无局部性优化，但实现大幅简化 |
| 输入分割 | 16-64 MB 自动分片 | 1 文件 = 1 Map 任务 | 不支持单文件并行，需外部预分片 |
| 内存模型 | 流式迭代器 | 全量 heap 分配 + Vec | 受内存限制，大文件会 OOM |
| Combiner | Map 本地预聚合 | 未实现 | Word count 等场景效率损失 |
| 容错语义 | Map 节点宕机需重跑（数据不可达） | 共享磁盘，Worker 宕机不需重跑 Map | 简化正确但掩盖了分布式的真实复杂性 |
| 运维细节 | 坏记录跳过、HTTP 状态页、计数器、自定义分区 | 均未实现 | 学习用途无影响，生产用途需补充 |

---

## 心智模型

> **"将分布式系统的正确性约束，映射为本地环境的最小实现"**：
> 不是简化问题，而是在更受控的环境里保留所有关键的 *协议不变量*（原子性、幂等完成、单向 Phase 流转、attempt 追踪），
> 从而让读者可以在 `cargo run` 的环境里验证分布式算法的核心逻辑。

**适用条件**：
- 理解分布式系统的正确性模型（Hadoop/Spark 设计）
- 单机多核并行数据处理
- 教学/学习目的的系统实现

**失效条件**：
- 输入数据超过单机内存（全量 heap 分配）
- 需要跨机器水平扩展
- 需要 Combiner 优化（网络密集型 word count 场景）

---

## 非显见洞见

### 洞见 1：mpsc + per-request reply channel 是 Rust 中无锁状态管理的通用模式

- **洞见**：Master 从不需要 `Arc<Mutex<State>>`——所有状态访问都通过消息序列化
- 所以：Master 线程是天然的"单写者"，TaskMeta 的所有修改都无竞态
- 所以：这个 `MasterEvent` + `TaskAssignment` 协议可以直接提取为一个通用的"任务调度器"模式
- **因此可以**：用同样的模式构建任意需要"中央协调 + 分布执行"的系统（爬虫调度、批量 LLM 调用、文件处理流水线）

### 洞见 2：attempt token 是分布式系统中"幂等完成"的通用解法

- **洞见**：`TaskToken { kind, task_id, attempt }` 三元组唯一标识一次执行尝试
- 所以：即使推测执行产生两个 attempt 都报告 Complete，`mark_complete` 只接受第一个，第二个静默丢弃
- 所以：这个模式可以推广到任何"at-least-once 投递 + exactly-once 语义"场景
- **因此可以**：在消息队列消费、HTTP 重试、Agent 任务调度中用相同的 attempt-id 机制去重

### 洞见 3：`peek` + 整组 drain 是 K-way 聚合的关键效率点

- **洞见**：不是先 pop 再判断，而是先 peek 再有条件 pop
- 所以：对于同一 key 的连续条目，heap 操作次数 = K（来源数），而非 N（总条目数）
- 所以：这个 peek-drain 模式在 values 集合很大时节省 O(N log K) 的堆操作
- **因此可以**：在日志聚合、时序数据合并等场景直接复用这个 peek-drain 循环

### 洞见 4：`active.len() == 1` 约束是防止"投机爆炸"的安全阀

- **洞见**：推测执行只在恰好一个 attempt 运行时触发，有多个 attempt 在跑则不再投机
- 所以：最坏情况下一个任务只有 2 个并发 attempt，资源使用是可预测的 O(2N)
- **因此可以**：这个"最多 N 个并发副本"的约束可以直接应用于任何备份任务系统的限速设计

---

## 反模式与陷阱

- **在 Reduce 前对每个桶局部排序但忽略 Combiner**：
  Map 阶段已经对每个 bucket 调用了 `sort_unstable_by`，但没有合并相同 key。
  对于 word count 这类场景，这意味着每个中间文件里同一个 "the" 出现 1000 次就写 1000 行 `"the\t1"`。
  → 正确做法：在 sort 之后增加 combiner 步骤，局部聚合为 `"the\t1000"`。

- **`merge_outputs` 再次全量排序**：最终合并阶段把 R 个已排序文件读入内存后 `sort_unstable_by`，
  而非再次使用 K-way 归并。对于大 R 值（输出分区多）会造成不必要的内存压力。
  → 正确做法：对 R 个输出文件再做一次 K-way merge，保持 O(N log R) 内存消耗。

- **临时文件命名用 `{:?}` 格式化 ThreadId**：`ThreadId` 的 `Debug` 输出格式（如 `ThreadId(3)`）
  在不同平台可能含括号，路径在 Windows 下可能不合法。
  → 正确做法：提取 `.as_u64()` 或用 UUID。

- **输入文件全量读入内存** (`fs::read_to_string`)：1 GB 的输入文件会直接 OOM。
  → 正确做法：改用 `BufReader` + 行迭代器流式处理。

- **Phase 转换缺少超时/死锁保护**：如果所有 Worker 都因网络/磁盘问题卡住，Master 会永久等待
  `event_rx.recv()`（此时 Workers 还活着但不发消息）。
  → 正确做法：使用 `recv_timeout` + 主动心跳机制。

---

## 与现有知识库的连接

- 关联 `snippets/kway-merge-heap.rs`：知识库已有独立的 K-way merge 实现，本分析提供了其在完整 MapReduce 管道中的上下文——`run_reduce_task` 是那个代码片段的完整生产版本，包含 `SourceReader`（流式文件读取）和 `refill_source`（堆补充）两个配套函数
- 关联 `snippets/atomic-file-write.rs`：知识库已有原子写入片段；本实现使用了相同的 `tmp → rename` 模式，但增加了 `PID+TID` 命名方案防止多线程冲突，是该片段的多线程增强版
- 关联 `python/mini_symphony.py`：Master/Worker + mpsc 任务调度模式与 mini_symphony 的 Agent 编排模式高度同构——两者都是"中央状态机 + 执行者轮询 + 失败重试"架构，只是一个用 Rust 线程、一个用 Python 子进程

---

## 衍生项目想法

### 想法 1：Rust MapReduce 引擎作为通用批处理后端

**来源组合**：[本次 MapReduceEngine] + [已有 `python/mini_symphony.py`]
**为什么有意思**：mini_symphony 目前用 Python 子进程串行执行 Agent 任务；MapReduce 引擎的 Master/Worker 架构可以为其提供并行批处理后端——将 TASKS.md 中的独立任务映射为 Map 任务，最后的结果聚合映射为 Reduce，天然支持任务超时重试和推测执行。Python 子进程调用 Rust 二进制，性能 + 容错双收益。
**最小 spike**：将 `MapReduceEngine` 的 `map_fn/reduce_fn` 接口改为调用外部命令（`std::process::Command`），输入/输出用 JSON Lines，然后用 mini_symphony 的 TASKS.md 格式生成输入文件跑一次端到端测试。估时：4-6 小时。

### 想法 2：Attempt Token 模式用于 LLM Agent 任务去重

**来源组合**：[本次 TaskToken + attempt 计数] + [已有 `python/session_tracker.py`]
**为什么有意思**：session_tracker 目前用 SQLite 记录事件，但没有处理"同一个 Agent 任务被多次触发"的幂等性问题（如网络重试、用户重复提交）。将 `TaskToken { task_id, attempt }` 模式引入 session_tracker，每次任务生成一个 `attempt_id` 写入 SQLite；Complete 事件检查 `attempt_id` 是否已存在，实现 exactly-once 语义。
**最小 spike**：在 `session_tracker.py` 的 `SQLiteEventStore` 中增加 `task_attempts` 表，`attempt_id = uuid4()`，`on_complete` 时先查表再插入。写一个测试：同一 attempt_id 提交两次，验证第二次被静默忽略。估时：2-3 小时。

### 想法 3：K-way Merge 用于多 Agent 上下文流合并

**来源组合**：[本次 K-way 外部归并 + peek-drain 聚合] + [已有 `python/tape_context.py`]
**为什么有意思**：tape_context 用锚点组装多个上下文片段，但当多个 Agent 并行输出结构化 key-value 事件时（如多个工具调用结果），需要将它们按 key（工具名/topic）聚合后送给下游。K-way merge 的 `peek-drain` 模式可以高效地将多个按时间戳排序的事件流合并 + 按 topic 聚合，避免全量排序。
**最小 spike**：用 Python 实现同样的 K-way merge（heapq.merge + groupby），输入为多个 Agent 输出的 JSONL 文件（每行 `{timestamp, topic, content}`），输出为按 topic 聚合的上下文块。验证比 `sorted(all_events)` 的内存使用少 80%+。估时：3-4 小时。
