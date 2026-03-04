# MapReduce in Rust — 架构模式分析

**来源**: [https://github.com/Aditya-1304/mapreduce](https://github.com/Aditya-1304/mapreduce)
**日期**: 2026-03-04
**状态**: 💡灵感

---

## 核心内容

用 Rust 实现的单机多线程 MapReduce 框架，灵感来自 Google 2004 年论文。用线程+通道替代分布式节点，核心机制完整还原：

- Master/Worker 架构（mpsc 通道通信）
- Map → Sort → Reduce 三阶段执行流水线
- Speculative Execution（推测执行：备份慢任务）
- 超时重试 + 任务级 Fault Tolerance
- 原子文件写入（tmp → rename）
- K-way 外部归并排序（BinaryHeap 实现）

**只依赖 Rust 标准库，无任何外部 crate。**

---

## 架构图

```
User Program
    │
    ▼
MapReduceEngine::run(job, input_files)
    │
    ├── spawn Master thread (event loop, mpsc::Receiver)
    │       ├── Phase::Map  → 分配 M 个 Map 任务
    │       ├── Phase::Reduce → 分配 R 个 Reduce 任务
    │       └── Phase::Done / Phase::Failed
    │
    └── spawn N Worker threads (each with mpsc::Sender)
            │
            └── loop:
                  1. 发 RequestTask（附带一次性 reply channel）
                  2. 收到 TaskAssignment：Map / Reduce / Wait / Exit
                  3. 执行任务，发 Complete / Failed 回 Master
```

---

## 五个关键模式

### 模式一：mpsc 请求/回复（一次性 channel）

Worker 向 Master 请求任务时，在请求消息里内嵌一个一次性 `Sender<TaskAssignment>`：

```rust
// Worker 端
let (reply_tx, reply_rx) = mpsc::channel();
event_tx.send(MasterEvent::RequestTask {
    worker_id,
    reply: reply_tx,   // 一次性回信通道塞进请求里
}).unwrap();
let assignment = reply_rx.recv().unwrap();

// Master 端
MasterEvent::RequestTask { worker_id, reply } => {
    let assignment = master.next_assignment(worker_id);
    let _ = reply.send(assignment);  // 用一次性通道回复
}
```

**价值**：避免每个 worker 维护独立 channel 的复杂度，Master 只需一个 `Receiver`，扩展性好。

---

### 模式二：原子文件写入（tmp → rename）

防止部分写入污染数据的通用模式：

```rust
fn temp_path(final_path: &Path) -> PathBuf {
    let pid = std::process::id();
    let tid = format!("{:?}", thread::current().id());
    PathBuf::from(format!("{}.tmp-{}-{}", final_path.display(), pid, tid))
}

// 写入流程：
let tmp_path = temp_path(&final_path);
let mut writer = BufWriter::new(File::create(&tmp_path)?);
// ... 写入数据 ...
writer.flush()?;
fs::rename(&tmp_path, &final_path)?;  // 原子替换
```

**价值**：OS 保证 `rename` 是原子操作。即使进程在写入中途崩溃，`final_path` 永远是完整文件。tmp 文件名带 pid+tid 避免多线程/多进程冲突。

---

### 模式三：BinaryHeap 实现 K-way 外部归并排序

将 Rust 的 max-heap 变成 min-heap，只需在 `Ord` 实现里交换 `self` 和 `other`：

```rust
impl Ord for HeapEntry {
    fn cmp(&self, other: &Self) -> Ordering {
        // 注意：other.cmp(self)，反转方向 → BinaryHeap 变成 min-heap
        other.key.cmp(&self.key)
            .then_with(|| other.source_idx.cmp(&self.source_idx))
    }
}
```

K-way 归并循环：

```rust
// 初始化：把每个来源的第一个元素推入堆
for (src_idx, source) in sources.iter_mut().enumerate() {
    if let Some(kv) = source.next_kv()? {
        heap.push(HeapEntry { key: kv.key, value: kv.value, source_idx: src_idx });
    }
}

// 归并：每次弹出最小 key，收集相同 key 的所有值
while let Some(entry) = heap.pop() {
    let key = entry.key;
    let mut values = vec![entry.value];
    refill_source(entry.source_idx, &mut sources, &mut heap)?;

    // 继续 peek，把相同 key 的都收进来
    while heap.peek().map_or(false, |n| n.key == key) {
        let same = heap.pop().unwrap();
        values.push(same.value);
        refill_source(same.source_idx, &mut sources, &mut heap)?;
    }

    let result = reduce_fn(&key, &values);
}
```

**关联**：`snippets/kway-merge-heap.rs` 是这个模式的完整可运行版本。

---

### 模式四：推测执行（Speculative Execution）

`TaskMeta::can_speculate()` 判断是否需要对慢任务发起备份：

```rust
fn can_speculate(&self, worker_id: usize, now: Instant, after: Duration) -> bool {
    // 条件：
    // 1. 任务还没完成
    // 2. 当前只有 1 个 active attempt（防止无限 fork）
    // 3. 请求的 worker 不是已在跑这个任务的 worker
    // 4. 该任务已运行超过 speculation threshold
    if self.completed || self.active.len() != 1 { return false; }
    let active = &self.active[0];
    active.worker_id != worker_id && now.duration_since(active.started_at) >= after
}
```

选择策略：从所有可推测的任务中选**运行时间最长的**（最严重的 straggler）：

```rust
fn pick_speculative_task(&self, tasks: &[TaskMeta], worker_id: usize) -> Option<usize> {
    let threshold = self.speculative_after?;
    let now = Instant::now();
    tasks.iter().enumerate()
        .filter(|(_, t)| t.can_speculate(worker_id, now, threshold))
        .min_by_key(|(_, t)| t.oldest_start())  // 最早开始 = 运行最久
        .map(|(id, _)| id)
}
```

---

### 模式五：Builder Pattern + 验证构造函数

```rust
pub fn new(...) -> Result<Self, String> {
    if num_workers == 0 { return Err("..."); }
    // ...验证...
    Ok(Self { ... })
}

pub fn with_max_retries(mut self, max_retries: u32) -> Self {
    self.max_retries = max_retries;
    self
}

pub fn with_speculative_after(mut self, speculative_after: Option<Duration>) -> Self {
    self.speculative_after = speculative_after;
    self
}

// 调用：
let engine = MapReduceEngine::new(4, 3, PathBuf::from("mr-tmp"), Duration::from_secs(10))?
    .with_max_retries(5)
    .with_speculative_after(Some(Duration::from_secs(5)));
```

---

## 与 Google 论文的七个偏差

| # | 论文设计 | 本实现 |
|---|---------|-------|
| 1 | 分布式集群 + RPC | 单机多线程 + mpsc |
| 2 | GFS 数据本地性 | 普通 OS 文件系统 |
| 3 | 大文件自动分块（16-64MB） | 1:1，每个输入文件一个 Map 任务 |
| 4 | 流式 Iterator 给 Reduce | 全量 Vec 进内存 |
| 5 | Combiner 函数 | 未实现 |
| 6 | Worker 节点宕机 → 重跑已完成 Map | 线程共享磁盘，仅重跑失败任务 |
| 7 | 状态 HTTP 页、计数器、自定义分区 | 未实现 |

---

## 可提取的技术片段

1. **`snippets/kway-merge-heap.rs`** — BinaryHeap min-heap + K-way 归并的完整实现
2. **`snippets/atomic-file-write.rs`** — tmp + rename 原子写入 Rust 版

## 延伸方向

### A. 给 Python/Rust 工具加 K-way merge

我们的 `fts5_fuzzy_search.py` 在聚合多个 SQLite 结果时可以用类似的堆归并替代简单排序，对大结果集更节省内存。

### B. 原子文件写入包装为 Python snippet

Python 也有同样的需求，`tempfile.NamedTemporaryFile` + `os.replace()` 是同等模式，值得作为 `python/atomic_write.py` 收录。

### C. 推测执行思路用于 Agent Task Scheduler

我们的 `tape_context.py` 里有异步 agent 任务编排，可以借鉴 speculative execution：对运行超时的 agent 任务发起备份执行，取最先完成的结果。

### D. 这个框架 + WASM 的思路

用 Rust 实现的 MapReduce 可以编译到 WASM，在浏览器里演示 MapReduce 流程——结合 Simon Willison 的 Interactive Explanations 模式，可以做一个动态可视化 MapReduce 执行过程的工具。

---

## 参考链接

- [仓库 Aditya-1304/mapreduce](https://github.com/Aditya-1304/mapreduce)
- [Google MapReduce Paper (2004)](https://static.googleusercontent.com/media/research.google.com/en//archive/mapreduce-osdi04.pdf)
- [相关：analysis/simon-willison-agentic-patterns.md](../analysis/simon-willison-agentic-patterns.md)（Interactive Explanations 模式）
