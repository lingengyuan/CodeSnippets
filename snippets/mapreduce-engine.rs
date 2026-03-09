// =============================================================================
// 名称: Rust MapReduce Engine — Master/Worker + K-way Merge + Speculative Execution
// 来源: https://github.com/Aditya-1304/mapreduce
// 用途: 单机多线程 MapReduce 框架；提供可复用的三大核心模式：
//       1. Master/Worker mpsc 任务调度（无共享内存）
//       2. K-way 外部归并排序（BinaryHeap min-heap + peek-drain 聚合）
//       3. 原子文件写入 + 推测执行 straggler 缓解
// 依赖: stdlib only (std::thread, std::sync::mpsc, std::collections::BinaryHeap, std::fs)
// 适用场景:
//   - 批量并行数据处理（word count / 日志聚合 / 数据转换）
//   - 需要"协调者 + 执行者"架构的任务调度系统
//   - 多路有序文件合并（外部排序 / ETL 管道）
// 日期: 2025-01-14
// =============================================================================
//
// ┌─────────────────────────────────────────────────────────────┐
// │               MapReduce 执行流水线                           │
// │                                                             │
// │  main() ──→ MapReduceEngine::run()                          │
// │                 ├── prepare_work_dir()  清理 mr-tmp/         │
// │                 ├── Master 线程         状态机 + 任务分配     │
// │                 ├── [×N] Worker 线程   轮询 + 执行          │
// │                 │      ├── run_map_task()                   │
// │                 │      │    hash分桶→排序→原子写R个tmp文件   │
// │                 │      └── run_reduce_task()                │
// │                 │           K-way merge→reduce_fn→原子写    │
// │                 └── merge_outputs()    R个文件→mr-out-final  │
// └─────────────────────────────────────────────────────────────┘
//
// 关键设计决策：
// [1] mpsc 双向通道：Worker→Master 用主 channel，Master→Worker 用 per-request reply channel
//     避免 Master 持有所有 Worker 的回写句柄（无需 Arc<Mutex<_>>）
// [2] attempt 令牌：TaskToken{task_id, attempt} 唯一标识每次执行尝试，实现 exactly-once 完成语义
// [3] BinaryHeap min-heap：在 Ord 实现中交换 self/other 方向，无需 Reverse<T> 包装
// [4] peek-drain 聚合：先 peek 判断 key 是否相同，再 pop，避免浪费堆操作
// [5] tmp → rename 原子写入：PID+TID 命名防止多线程临时文件冲突

//! src/engine.rs（完整源码）

use std::cmp::Ordering;
use std::collections::BinaryHeap;
use std::fs::{self, File};
use std::io::{BufRead, BufReader, BufWriter, Write};
use std::path::{Path, PathBuf};
use std::sync::mpsc::{self, Receiver, Sender};
use std::thread;
use std::time::{Duration, Instant};

// =============================================================================
// 公开 API 类型
// =============================================================================

/// 中间/输出数据的 key-value 对
#[derive(Debug, Clone)]
pub struct KeyValue {
    pub key: String,
    pub value: String,
}

/// Map 函数类型：(文件名, 文件内容) → 中间 KV 列表
pub type MapFn = fn(filename: &str, contents: &str) -> Vec<KeyValue>;
/// Reduce 函数类型：(key, values列表) → 聚合结果
pub type ReduceFn = fn(key: &str, values: &[String]) -> String;

/// 用户提供的 Map/Reduce 函数对（Copy，可安全跨线程传递）
#[derive(Clone, Copy)]
pub struct MapReduceJob {
    pub map: MapFn,
    pub reduce: ReduceFn,
}

/// 引擎配置（Builder 模式）
pub struct MapReduceEngine {
    pub num_workers: usize,          // 并行 Worker 线程数
    pub num_reducers: usize,         // R：输出分区数（论文中的 R）
    pub work_dir: PathBuf,           // 中间/输出文件目录
    pub task_timeout: Duration,      // 任务超时时间（超时→重试）
    pub max_retries: u32,            // 最大重试次数
    pub speculative_after: Option<Duration>, // 推测执行触发时间（None = 禁用）
}

impl MapReduceEngine {
    /// 创建引擎，验证参数合法性
    pub fn new(
        num_workers: usize,
        num_reducers: usize,
        work_dir: PathBuf,
        task_timeout: Duration,
    ) -> Result<Self, String> {
        if num_workers == 0 { return Err("num_workers must be > 0".to_string()); }
        if num_reducers == 0 { return Err("num_reducers must be > 0".to_string()); }
        if task_timeout.is_zero() { return Err("task_timeout must be > 0".to_string()); }

        // 默认推测执行阈值 = timeout / 2
        let half_ms = (task_timeout.as_millis() / 2).max(1).min(u64::MAX as u128) as u64;
        Ok(Self {
            num_workers,
            num_reducers,
            work_dir,
            task_timeout,
            max_retries: 5,
            speculative_after: Some(Duration::from_millis(half_ms)),
        })
    }

    pub fn with_max_retries(mut self, max_retries: u32) -> Self {
        self.max_retries = max_retries;
        self
    }

    pub fn with_speculative_after(mut self, speculative_after: Option<Duration>) -> Self {
        self.speculative_after = speculative_after;
        self
    }

    /// 执行 MapReduce 作业，返回 (key, value) 对列表
    pub fn run(
        &self,
        job: MapReduceJob,
        input_files: Vec<String>,
    ) -> Result<Vec<(String, String)>, String> {
        if input_files.is_empty() {
            return Err("at least one input file is required".to_string());
        }

        prepare_work_dir(&self.work_dir)?;

        let master = Master::new(
            input_files,
            self.num_reducers,
            self.task_timeout,
            self.max_retries,
            self.speculative_after,
        );

        // Worker→Master 主通道
        let (event_tx, event_rx) = mpsc::channel::<MasterEvent>();

        // Master 在独立线程运行状态机
        let master_handle = thread::spawn(move || master_loop(master, event_rx));

        // 启动 N 个 Worker 线程
        let mut worker_handles = Vec::with_capacity(self.num_workers);
        for worker_id in 0..self.num_workers {
            let tx = event_tx.clone();
            let work_dir = self.work_dir.clone();
            let n_reduce = self.num_reducers;
            worker_handles.push(thread::spawn(move || {
                worker_loop(worker_id, tx, work_dir, n_reduce, job)
            }));
        }

        // 丢弃主线程的 tx，确保 Worker 全退出后 channel 关闭，Master 能退出 recv 循环
        drop(event_tx);

        for handle in worker_handles {
            handle.join().map_err(|_| "worker thread panicked".to_string())??;
        }

        let master_result = master_handle
            .join()
            .map_err(|_| "master thread panicked".to_string())?;

        if let Some(err) = master_result.fatal_error {
            return Err(err);
        }
        if !master_result.completed {
            return Err("job ended without reaching completed state".to_string());
        }

        merge_outputs(&self.work_dir, self.num_reducers)
    }
}

// =============================================================================
// Master 状态机内部类型
// =============================================================================

/// 作业全局 Phase，严格单向流转：Map → Reduce → Done（或任意时刻 → Failed）
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum Phase { Map, Reduce, Done, Failed }

/// 任务类型
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum TaskKind { Map, Reduce }

/// 唯一标识一次任务执行尝试（支持推测执行去重）
/// attempt 序号区分"原始任务"和"备份任务"
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
struct TaskToken {
    kind: TaskKind,
    task_id: usize,
    attempt: u32,
}

/// 一次正在运行的 attempt 记录
#[derive(Debug, Clone)]
struct RunningAttempt {
    attempt: u32,
    worker_id: usize,
    started_at: Instant,
}

/// 单个 Map/Reduce 任务的状态
#[derive(Debug, Clone)]
struct TaskMeta {
    completed: bool,         // 任何 attempt 成功即为 true
    retries: u32,            // 累计失败/超时次数
    next_attempt: u32,       // 单调递增 attempt ID 序号
    active: Vec<RunningAttempt>, // 当前运行中的 attempt（推测执行时可能有 2 个）
}

impl TaskMeta {
    fn new() -> Self {
        Self { completed: false, retries: 0, next_attempt: 1, active: Vec::new() }
    }

    fn is_completed(&self) -> bool { self.completed }

    /// 空闲：未完成且没有正在运行的 attempt
    fn is_idle(&self) -> bool { !self.completed && self.active.is_empty() }

    /// 分配给 Worker，返回 attempt ID
    fn assign(&mut self, worker_id: usize) -> u32 {
        let attempt = self.next_attempt;
        self.next_attempt = self.next_attempt.saturating_add(1);
        self.active.push(RunningAttempt { attempt, worker_id, started_at: Instant::now() });
        attempt
    }

    /// 标记完成；只接受 active 列表中存在的 attempt，防止"幽灵完成"
    fn mark_complete(&mut self, attempt: u32, worker_id: usize) -> bool {
        if self.completed { return false; }
        let found = self.active.iter().position(|a| a.attempt == attempt && a.worker_id == worker_id);
        if found.is_some() {
            self.completed = true;
            self.active.clear();
            return true;
        }
        false
    }

    /// 标记失败，超出重试次数则返回 Err
    fn mark_failed(&mut self, attempt: u32, worker_id: usize, max_retries: u32) -> Result<(), String> {
        if self.completed { return Ok(()); }
        if let Some(pos) = self.active.iter().position(|a| a.attempt == attempt && a.worker_id == worker_id) {
            self.active.swap_remove(pos);
            self.retries = self.retries.saturating_add(1);
            if self.retries > max_retries {
                return Err(format!("retry limit exceeded ({} retries)", self.retries));
            }
        }
        Ok(())
    }

    /// 清除已超时的 attempt，超出重试次数则返回 Err
    fn reap_timeouts(&mut self, now: Instant, timeout: Duration, max_retries: u32) -> Result<(), String> {
        if self.completed || self.active.is_empty() { return Ok(()); }
        let mut timed_out = 0_u32;
        self.active.retain(|a| {
            if now.duration_since(a.started_at) > timeout { timed_out += 1; false } else { true }
        });
        if timed_out > 0 {
            self.retries = self.retries.saturating_add(timed_out);
            if self.retries > max_retries {
                return Err(format!("retry limit exceeded after timeouts ({} retries)", self.retries));
            }
        }
        Ok(())
    }

    /// 是否可以投机执行（关键约束：active.len() == 1，防止投机爆炸）
    fn can_speculate(&self, worker_id: usize, now: Instant, after: Duration) -> bool {
        if self.completed || self.active.len() != 1 { return false; }
        let a = &self.active[0];
        // 不能对自己投机；且运行时间必须超过阈值
        a.worker_id != worker_id && now.duration_since(a.started_at) >= after
    }

    fn oldest_start(&self) -> Option<Instant> {
        self.active.iter().map(|a| a.started_at).min()
    }
}

// =============================================================================
// Master/Worker 消息协议
// =============================================================================

/// Master → Worker（通过 per-request reply channel 发送）
#[derive(Debug)]
enum TaskAssignment {
    Map { token: TaskToken, filename: String },
    Reduce { token: TaskToken, map_count: usize },
    Wait,   // 暂无任务，稍后重试
    Exit,   // 作业完成，线程退出
}

/// Worker → Master（通过主 event channel 发送）
enum MasterEvent {
    RequestTask {
        worker_id: usize,
        reply: Sender<TaskAssignment>,  // 一次性 reply channel
    },
    Complete { worker_id: usize, token: TaskToken },
    Failed { worker_id: usize, token: TaskToken, error: String },
}

// =============================================================================
// Master 实现
// =============================================================================

struct Master {
    phase: Phase,
    map_tasks: Vec<TaskMeta>,
    reduce_tasks: Vec<TaskMeta>,
    input_files: Vec<String>,
    timeout: Duration,
    max_retries: u32,
    speculative_after: Option<Duration>,
    fatal_error: Option<String>,
}

struct MasterLoopResult {
    completed: bool,
    fatal_error: Option<String>,
}

impl Master {
    fn new(
        input_files: Vec<String>,
        num_reducers: usize,
        timeout: Duration,
        max_retries: u32,
        speculative_after: Option<Duration>,
    ) -> Self {
        let map_tasks = (0..input_files.len()).map(|_| TaskMeta::new()).collect();
        let reduce_tasks = (0..num_reducers).map(|_| TaskMeta::new()).collect();
        Self { phase: Phase::Map, map_tasks, reduce_tasks, input_files,
               timeout, max_retries, speculative_after, fatal_error: None }
    }

    fn next_assignment(&mut self, worker_id: usize) -> TaskAssignment {
        self.maintenance();
        match self.phase {
            Phase::Failed | Phase::Done => TaskAssignment::Exit,
            Phase::Map => {
                // 优先分配空闲任务，其次推测执行
                if let Some(id) = self.first_idle_map_task() {
                    let attempt = self.map_tasks[id].assign(worker_id);
                    return TaskAssignment::Map {
                        token: TaskToken { kind: TaskKind::Map, task_id: id, attempt },
                        filename: self.input_files[id].clone(),
                    };
                }
                if let Some(id) = self.pick_speculative_task(&self.map_tasks.clone(), worker_id) {
                    let attempt = self.map_tasks[id].assign(worker_id);
                    return TaskAssignment::Map {
                        token: TaskToken { kind: TaskKind::Map, task_id: id, attempt },
                        filename: self.input_files[id].clone(),
                    };
                }
                TaskAssignment::Wait
            }
            Phase::Reduce => {
                if let Some(id) = self.first_idle_reduce_task() {
                    let attempt = self.reduce_tasks[id].assign(worker_id);
                    return TaskAssignment::Reduce {
                        token: TaskToken { kind: TaskKind::Reduce, task_id: id, attempt },
                        map_count: self.input_files.len(),
                    };
                }
                if let Some(id) = self.pick_speculative_task(&self.reduce_tasks.clone(), worker_id) {
                    let attempt = self.reduce_tasks[id].assign(worker_id);
                    return TaskAssignment::Reduce {
                        token: TaskToken { kind: TaskKind::Reduce, task_id: id, attempt },
                        map_count: self.input_files.len(),
                    };
                }
                TaskAssignment::Wait
            }
        }
    }

    fn on_complete(&mut self, worker_id: usize, token: TaskToken) {
        match token.kind {
            TaskKind::Map => { self.map_tasks[token.task_id].mark_complete(token.attempt, worker_id); }
            TaskKind::Reduce => { self.reduce_tasks[token.task_id].mark_complete(token.attempt, worker_id); }
        }
        self.update_phase();
    }

    fn on_failed(&mut self, worker_id: usize, token: TaskToken, error: String) {
        let result = match token.kind {
            TaskKind::Map => self.map_tasks[token.task_id].mark_failed(token.attempt, worker_id, self.max_retries),
            TaskKind::Reduce => self.reduce_tasks[token.task_id].mark_failed(token.attempt, worker_id, self.max_retries),
        };
        if let Err(e) = result {
            self.fail_job(format!("task {:?}-{} permanently failed: {} | {}", token.kind, token.task_id, e, error));
            return;
        }
        self.update_phase();
    }

    fn maintenance(&mut self) {
        if matches!(self.phase, Phase::Done | Phase::Failed) { return; }
        let now = Instant::now();
        let timeout = self.timeout;
        let max_retries = self.max_retries;
        let tasks = match self.phase {
            Phase::Map => &mut self.map_tasks,
            Phase::Reduce => &mut self.reduce_tasks,
            _ => return,
        };
        for (id, task) in tasks.iter_mut().enumerate() {
            if let Err(e) = task.reap_timeouts(now, timeout, max_retries) {
                self.fatal_error = Some(format!("task {} permanently timed out: {}", id, e));
                self.phase = Phase::Failed;
                return;
            }
        }
        self.update_phase();
    }

    fn update_phase(&mut self) {
        // Phase 严格单向：必须全部完成才能推进
        if self.phase == Phase::Map && self.map_tasks.iter().all(TaskMeta::is_completed) {
            self.phase = Phase::Reduce;
        }
        if self.phase == Phase::Reduce && self.reduce_tasks.iter().all(TaskMeta::is_completed) {
            self.phase = Phase::Done;
        }
    }

    fn fail_job(&mut self, err: String) {
        if self.fatal_error.is_none() { self.fatal_error = Some(err); }
        self.phase = Phase::Failed;
    }

    fn first_idle_map_task(&self) -> Option<usize> {
        self.map_tasks.iter().position(TaskMeta::is_idle)
    }

    fn first_idle_reduce_task(&self) -> Option<usize> {
        self.reduce_tasks.iter().position(TaskMeta::is_idle)
    }

    /// 选择运行时间最长、超过阈值、且只有 1 个 attempt 的任务进行推测执行
    fn pick_speculative_task(&self, tasks: Vec<TaskMeta>, worker_id: usize) -> Option<usize> {
        let threshold = self.speculative_after?;
        let now = Instant::now();
        let mut best: Option<(usize, Instant)> = None;
        for (id, task) in tasks.iter().enumerate() {
            if !task.can_speculate(worker_id, now, threshold) { continue; }
            if let Some(started) = task.oldest_start() {
                match best {
                    None => best = Some((id, started)),
                    Some((_, current)) if started < current => best = Some((id, started)),
                    _ => {}
                }
            }
        }
        best.map(|(id, _)| id)
    }
}

fn master_loop(mut master: Master, event_rx: Receiver<MasterEvent>) -> MasterLoopResult {
    while let Ok(event) = event_rx.recv() {
        match event {
            MasterEvent::RequestTask { worker_id, reply } => {
                let assignment = master.next_assignment(worker_id);
                let _ = reply.send(assignment);
            }
            MasterEvent::Complete { worker_id, token } => master.on_complete(worker_id, token),
            MasterEvent::Failed { worker_id, token, error } => master.on_failed(worker_id, token, error),
        }
    }
    MasterLoopResult { completed: master.phase == Phase::Done, fatal_error: master.fatal_error }
}

// =============================================================================
// Worker 实现
// =============================================================================

fn worker_loop(
    worker_id: usize,
    event_tx: Sender<MasterEvent>,
    work_dir: PathBuf,
    n_reduce: usize,
    job: MapReduceJob,
) -> Result<(), String> {
    loop {
        // 创建一次性 reply channel，发送请求
        let (reply_tx, reply_rx) = mpsc::channel();
        event_tx.send(MasterEvent::RequestTask { worker_id, reply: reply_tx })
            .map_err(|_| "master channel closed".to_string())?;
        let assignment = reply_rx.recv()
            .map_err(|_| "reply channel closed".to_string())?;

        match assignment {
            TaskAssignment::Map { token, filename } => {
                match run_map_task(&filename, token.task_id, n_reduce, &work_dir, job.map) {
                    Ok(()) => event_tx.send(MasterEvent::Complete { worker_id, token })
                        .map_err(|_| "master channel closed".to_string())?,
                    Err(e) => event_tx.send(MasterEvent::Failed { worker_id, token, error: e })
                        .map_err(|_| "master channel closed".to_string())?,
                }
            }
            TaskAssignment::Reduce { token, map_count } => {
                match run_reduce_task(token.task_id, map_count, &work_dir, job.reduce) {
                    Ok(()) => event_tx.send(MasterEvent::Complete { worker_id, token })
                        .map_err(|_| "master channel closed".to_string())?,
                    Err(e) => event_tx.send(MasterEvent::Failed { worker_id, token, error: e })
                        .map_err(|_| "master channel closed".to_string())?,
                }
            }
            TaskAssignment::Wait => thread::sleep(Duration::from_millis(50)),
            TaskAssignment::Exit => break,
        }
    }
    Ok(())
}

// =============================================================================
// Map 任务执行
// =============================================================================

fn run_map_task(
    filename: &str,
    map_id: usize,
    n_reduce: usize,
    work_dir: &Path,
    map_fn: MapFn,
) -> Result<(), String> {
    // 注意：这里全量读取，生产环境应改用 BufReader 流式处理
    let contents = fs::read_to_string(filename)
        .map_err(|e| format!("failed to read {}: {}", filename, e))?;

    let emitted = map_fn(filename, &contents);

    // 创建 R 个桶并哈希分区
    let mut buckets: Vec<Vec<KeyValue>> = (0..n_reduce).map(|_| Vec::new()).collect();
    for kv in emitted {
        let bucket_id = ihash(&kv.key) % n_reduce;
        buckets[bucket_id].push(kv);
    }

    // 每个桶内局部排序（为 K-way merge 做准备）
    for bucket in &mut buckets {
        bucket.sort_unstable_by(|a, b| a.key.cmp(&b.key));
    }

    // 原子写入每个中间文件：先写 tmp，再 rename
    for (reduce_id, bucket) in buckets.into_iter().enumerate() {
        let final_path = intermediate_path(work_dir, map_id, reduce_id);
        let tmp_path = temp_path(&final_path);

        let mut writer = BufWriter::new(
            File::create(&tmp_path).map_err(|e| format!("create tmp {}: {}", tmp_path.display(), e))?
        );
        for kv in bucket {
            write_kv_line(&mut writer, &kv.key, &kv.value)?;
        }
        writer.flush().map_err(|e| format!("flush {}: {}", tmp_path.display(), e))?;
        fs::rename(&tmp_path, &final_path)
            .map_err(|e| format!("rename {} → {}: {}", tmp_path.display(), final_path.display(), e))?;
    }
    Ok(())
}

// =============================================================================
// Reduce 任务执行（K-way 外部归并排序 + peek-drain 聚合）
// =============================================================================

fn run_reduce_task(
    reduce_id: usize,
    map_count: usize,
    work_dir: &Path,
    reduce_fn: ReduceFn,
) -> Result<(), String> {
    let final_out = reduce_out_path(work_dir, reduce_id);
    let tmp_out = temp_path(&final_out);
    let mut writer = BufWriter::new(
        File::create(&tmp_out).map_err(|e| format!("create tmp reduce output: {}", e))?
    );

    // 打开 M 个中间文件的流式读取器
    let mut sources: Vec<SourceReader> = (0..map_count)
        .map(|map_id| SourceReader::open(intermediate_path(work_dir, map_id, reduce_id)))
        .collect::<Result<_, _>>()?;

    // ── K-way 归并核心 ────────────────────────────────────────────────────────
    // min-heap：Ord 实现已反转方向（other.cmp(self)），弹出最小 key
    let mut heap = BinaryHeap::<HeapEntry>::new();

    // 初始化：每个来源推入第一个元素
    for (idx, src) in sources.iter_mut().enumerate() {
        if let Some(kv) = src.next_kv()? {
            heap.push(HeapEntry { key: kv.key, value: kv.value, source_idx: idx });
        }
    }

    while let Some(entry) = heap.pop() {
        let key = entry.key;
        let mut values = vec![entry.value];

        // 补充弹出来源的下一个元素
        refill_source(entry.source_idx, &mut sources, &mut heap)?;

        // peek-drain 聚合：收集所有相同 key 的 value（不浪费堆操作）
        while let Some(next) = heap.peek() {
            if next.key != key { break; }
            let same = heap.pop().unwrap();
            values.push(same.value);
            refill_source(same.source_idx, &mut sources, &mut heap)?;
        }

        let result = reduce_fn(&key, &values);
        write_kv_line(&mut writer, &key, &result)?;
    }
    // ─────────────────────────────────────────────────────────────────────────

    writer.flush().map_err(|e| format!("flush reduce output: {}", e))?;
    fs::rename(&tmp_out, &final_out)
        .map_err(|e| format!("rename {} → {}: {}", tmp_out.display(), final_out.display(), e))?;
    Ok(())
}

fn refill_source(
    source_idx: usize,
    sources: &mut [SourceReader],
    heap: &mut BinaryHeap<HeapEntry>,
) -> Result<(), String> {
    if let Some(kv) = sources[source_idx].next_kv()? {
        heap.push(HeapEntry { key: kv.key, value: kv.value, source_idx });
    }
    Ok(())
}

// =============================================================================
// 输出合并
// =============================================================================

fn merge_outputs(work_dir: &Path, n_reduce: usize) -> Result<Vec<(String, String)>, String> {
    let mut merged: Vec<(String, String)> = Vec::new();
    for reduce_id in 0..n_reduce {
        let out_path = reduce_out_path(work_dir, reduce_id);
        let reader = BufReader::new(
            File::open(&out_path).map_err(|e| format!("open reduce output {}: {}", out_path.display(), e))?
        );
        for line in reader.lines() {
            let line = line.map_err(|e| format!("read {}: {}", out_path.display(), e))?;
            if line.trim().is_empty() { continue; }
            let kv = parse_kv_line(&line)?;
            merged.push((kv.key, kv.value));
        }
    }
    // 注意：这里全量排序，生产环境可用 K-way merge 替换以节省内存
    merged.sort_unstable_by(|a, b| a.0.cmp(&b.0));

    let final_path = work_dir.join("mr-out-final");
    let tmp_path = temp_path(&final_path);
    let mut writer = BufWriter::new(
        File::create(&tmp_path).map_err(|e| format!("create final output: {}", e))?
    );
    for (k, v) in &merged {
        write_kv_line(&mut writer, k, v)?;
    }
    writer.flush().map_err(|e| format!("flush final output: {}", e))?;
    fs::rename(&tmp_path, &final_path)
        .map_err(|e| format!("rename final output: {}", e))?;
    Ok(merged)
}

// =============================================================================
// 工具函数
// =============================================================================

fn prepare_work_dir(work_dir: &Path) -> Result<(), String> {
    fs::create_dir_all(work_dir).map_err(|e| format!("create work_dir: {}", e))?;
    for entry in fs::read_dir(work_dir).map_err(|e| format!("read work_dir: {}", e))? {
        let path = entry.map_err(|e| format!("read entry: {}", e))?.path();
        let is_mr = path.file_name().and_then(|s| s.to_str())
            .map(|n| n.starts_with("mr-")).unwrap_or(false);
        if is_mr { fs::remove_file(&path).map_err(|e| format!("remove stale {}: {}", path.display(), e))?; }
    }
    Ok(())
}

fn intermediate_path(work_dir: &Path, map_id: usize, reduce_id: usize) -> PathBuf {
    work_dir.join(format!("mr-{}-{}", map_id, reduce_id))
}

fn reduce_out_path(work_dir: &Path, reduce_id: usize) -> PathBuf {
    work_dir.join(format!("mr-out-{}", reduce_id))
}

/// PID + ThreadId 组合，保证多线程临时文件不冲突
fn temp_path(final_path: &Path) -> PathBuf {
    let pid = std::process::id();
    let tid = format!("{:?}", thread::current().id());
    PathBuf::from(format!("{}.tmp-{}-{}", final_path.display(), pid, tid))
}

/// 简单哈希函数（保证正数）
fn ihash(key: &str) -> usize {
    use std::hash::{Hash, Hasher};
    let mut hasher = std::collections::hash_map::DefaultHasher::new();
    key.hash(&mut hasher);
    (hasher.finish() as usize) & 0x7fff_ffff
}

/// 序列化 KV 对为 tab 分隔行（含转义）
fn write_kv_line(writer: &mut BufWriter<File>, key: &str, value: &str) -> Result<(), String> {
    writeln!(writer, "{}\t{}", escape_field(key), escape_field(value))
        .map_err(|e| format!("write kv line: {}", e))
}

fn parse_kv_line(line: &str) -> Result<KeyValue, String> {
    let (raw_key, raw_value) = line.split_once('\t')
        .ok_or_else(|| "missing tab separator".to_string())?;
    Ok(KeyValue { key: unescape_field(raw_key)?, value: unescape_field(raw_value)? })
}

fn escape_field(input: &str) -> String {
    let mut out = String::with_capacity(input.len());
    for c in input.chars() {
        match c {
            '\\' => out.push_str("\\\\"),
            '\t' => out.push_str("\\t"),
            '\n' => out.push_str("\\n"),
            _ => out.push(c),
        }
    }
    out
}

fn unescape_field(input: &str) -> Result<String, String> {
    let mut out = String::with_capacity(input.len());
    let mut chars = input.chars();
    while let Some(c) = chars.next() {
        if c != '\\' { out.push(c); continue; }
        match chars.next().ok_or("dangling escape")? {
            '\\' => out.push('\\'),
            't' => out.push('\t'),
            'n' => out.push('\n'),
            other => return Err(format!("unsupported escape: \\{}", other)),
        }
    }
    Ok(out)
}

// =============================================================================
// 流式文件读取器（K-way merge 的数据源）
// =============================================================================

struct SourceReader {
    path: PathBuf,
    reader: BufReader<File>,
    scratch: String,
}

impl SourceReader {
    fn open(path: PathBuf) -> Result<Self, String> {
        let file = File::open(&path)
            .map_err(|e| format!("open intermediate {}: {}", path.display(), e))?;
        Ok(Self { path, reader: BufReader::new(file), scratch: String::new() })
    }

    fn next_kv(&mut self) -> Result<Option<KeyValue>, String> {
        loop {
            self.scratch.clear();
            let bytes = self.reader.read_line(&mut self.scratch)
                .map_err(|e| format!("read {}: {}", self.path.display(), e))?;
            if bytes == 0 { return Ok(None); }  // EOF
            while self.scratch.ends_with('\n') || self.scratch.ends_with('\r') { self.scratch.pop(); }
            if self.scratch.is_empty() { continue; }
            return Ok(Some(parse_kv_line(&self.scratch)?));
        }
    }
}

// =============================================================================
// min-heap 条目（Ord 实现反转 → 变 max-heap 为 min-heap）
// =============================================================================

#[derive(Debug)]
struct HeapEntry {
    key: String,
    value: String,
    source_idx: usize,
}

impl Eq for HeapEntry {}

impl PartialEq for HeapEntry {
    fn eq(&self, other: &Self) -> bool {
        self.key == other.key && self.source_idx == other.source_idx && self.value == other.value
    }
}

impl Ord for HeapEntry {
    fn cmp(&self, other: &Self) -> Ordering {
        // 关键：other 在前 → 反转方向 → BinaryHeap 表现为 min-heap
        other.key.cmp(&self.key)
            .then_with(|| other.source_idx.cmp(&self.source_idx))
    }
}

impl PartialOrd for HeapEntry {
    fn partial_cmp(&self, other: &Self) -> Option<Ordering> {
        Some(self.cmp(other))
    }
}

// =============================================================================
// 用法示例（Word Count）
// =============================================================================

/// 用户自定义 Map 函数：文档 → (单词, "1") 列表
fn wc_map(_filename: &str, contents: &str) -> Vec<KeyValue> {
    contents.split_whitespace()
        .filter_map(|token| {
            let cleaned: String = token.chars()
                .filter(|c| c.is_alphanumeric())
                .collect::<String>()
                .to_lowercase();
            if cleaned.is_empty() { None }
            else { Some(KeyValue { key: cleaned, value: "1".to_string() }) }
        })
        .collect()
}

/// 用户自定义 Reduce 函数：累加所有 "1" → 总计数
fn wc_reduce(_key: &str, values: &[String]) -> String {
    values.iter().filter_map(|v| v.parse::<u64>().ok()).sum::<u64>().to_string()
}

fn main() -> Result<(), String> {
    let engine = MapReduceEngine::new(
        4,                           // 4 个 Worker 线程
        3,                           // 3 个输出分区
        PathBuf::from("mr-tmp"),
        Duration::from_secs(10),
    )?
    .with_max_retries(5)
    .with_speculative_after(Some(Duration::from_secs(5)));

    let job = MapReduceJob { map: wc_map, reduce: wc_reduce };

    let merged = engine.run(job, vec!["input.txt".to_string()])?;
    println!("Done. {} unique keys", merged.len());
    Ok(())
}
