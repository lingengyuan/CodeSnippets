// =============================================================================
// 名称: K-way 外部归并排序（BinaryHeap min-heap）
// 用途: 对 K 个已排序的迭代器/文件流进行归并，输出全局有序序列；
//       同时将相同 key 的 values 收集在一起（适用于 MapReduce Reduce 阶段）
// 依赖: stdlib only (std::collections::BinaryHeap, std::cmp::Ordering)
// 适用场景: MapReduce Reduce 阶段 / 多路归并排序 / 日志合并 / 外部排序
// 来源: https://github.com/Aditya-1304/mapreduce
// 日期: 2026-03-04
// =============================================================================
//
// 关键技巧：Rust 的 BinaryHeap 默认是 max-heap。
// 在 Ord 实现里交换 self/other 的比较方向，无需额外包装类型即可变为 min-heap。
//
// 用法示例：
//   let sources = vec![
//       vec![("apple", "1"), ("cat", "1")],
//       vec![("apple", "1"), ("banana", "1")],
//       vec![("cat", "1"), ("dog", "1")],
//   ];
//   kway_merge(sources, |key, values| {
//       println!("{}: {}", key, values.len());  // apple: 2, banana: 1, cat: 2, dog: 1
//   });

use std::cmp::Ordering;
use std::collections::BinaryHeap;

// -----------------------------------------------------------------------------
// 堆条目：携带 key、value 和来源索引
// -----------------------------------------------------------------------------
#[derive(Debug)]
struct HeapEntry {
    key: String,
    value: String,
    source_idx: usize,
}

impl Eq for HeapEntry {}

impl PartialEq for HeapEntry {
    fn eq(&self, other: &Self) -> bool {
        self.key == other.key && self.source_idx == other.source_idx
    }
}

impl Ord for HeapEntry {
    fn cmp(&self, other: &Self) -> Ordering {
        // 反转方向：other.cmp(self) → BinaryHeap 从 max-heap 变为 min-heap
        other
            .key
            .cmp(&self.key)
            .then_with(|| other.source_idx.cmp(&self.source_idx))
    }
}

impl PartialOrd for HeapEntry {
    fn partial_cmp(&self, other: &Self) -> Option<Ordering> {
        Some(self.cmp(other))
    }
}

// -----------------------------------------------------------------------------
// K-way 归并，相同 key 的 values 自动聚合
// reduce_fn: (key, values) → 对聚合结果做处理（打印/写文件/累加等）
// -----------------------------------------------------------------------------
fn kway_merge<F>(mut sources: Vec<Vec<(String, String)>>, mut reduce_fn: F)
where
    F: FnMut(&str, &[String]),
{
    // 将每个 source 转换为迭代器
    let mut iters: Vec<_> = sources.iter_mut().map(|v| v.drain(..)).collect();

    let mut heap = BinaryHeap::<HeapEntry>::new();

    // 初始化：把每个来源的第一个元素推入堆
    for (idx, iter) in iters.iter_mut().enumerate() {
        if let Some((key, value)) = iter.next() {
            heap.push(HeapEntry { key, value, source_idx: idx });
        }
    }

    // 归并主循环
    while let Some(entry) = heap.pop() {
        let key = entry.key.clone();
        let mut values = vec![entry.value.clone()];

        // 补充这个来源的下一个元素
        if let Some((k, v)) = iters[entry.source_idx].next() {
            heap.push(HeapEntry { key: k, value: v, source_idx: entry.source_idx });
        }

        // 继续 peek：收集所有相同 key 的 value
        while heap.peek().map_or(false, |n| n.key == key) {
            let same = heap.pop().unwrap();
            values.push(same.value.clone());
            // 补充这个来源的下一个元素
            if let Some((k, v)) = iters[same.source_idx].next() {
                heap.push(HeapEntry { key: k, value: v, source_idx: same.source_idx });
            }
        }

        reduce_fn(&key, &values);
    }
}

// -----------------------------------------------------------------------------
// 示例：WordCount reduce 阶段
// -----------------------------------------------------------------------------
fn wc_reduce(_key: &str, values: &[String]) -> String {
    values.iter().filter_map(|v| v.parse::<u64>().ok()).sum::<u64>().to_string()
}

fn main() {
    // 三路已排序的中间数据（模拟 Map 阶段的三个输出分区）
    let sources = vec![
        vec![
            ("apple".to_string(), "1".to_string()),
            ("cat".to_string(), "1".to_string()),
        ],
        vec![
            ("apple".to_string(), "1".to_string()),
            ("banana".to_string(), "1".to_string()),
        ],
        vec![
            ("cat".to_string(), "1".to_string()),
            ("dog".to_string(), "1".to_string()),
        ],
    ];

    kway_merge(sources, |key, values| {
        let count = wc_reduce(key, values);
        println!("{}\t{}", key, count);
    });
    // 输出（已全局有序）：
    // apple   2
    // banana  1
    // cat     2
    // dog     1
}
