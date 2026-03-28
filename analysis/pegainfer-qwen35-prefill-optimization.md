# pegainfer Qwen3.5-4B Prefill 优化 精读

**来源**: [xiaguan/pegainfer PR #27 — perf(qwen35): Qwen3.5-4B prefill TTFT 16.8s → 235ms](https://github.com/xiaguan/pegainfer/pull/27)
**日期**: 2026-03-22
**标签**: cuda, triton, rust, llm-inference, linear-attention, gated-delta-rule, prefill-optimization, kernel-launch

---

## 30秒 TL;DR

> 纯 Rust + CUDA 推理引擎 pegainfer 在 Qwen3.5-4B（24 层线性注意力 + 8 层全注意力混合架构）上，将 prefill TTFT 从 16.8s 压缩到 235ms（vLLM 222ms，差距 +6%）。核心手段：把每 token 顺序启动的数万个小 CUDA kernel 替换为少量 Triton 批处理 kernel。根本原因不是 GPU 计算能力不足，而是**CPU kernel launch overhead 占了 wall clock 的 67%**。

---

## 概念总览

| 概念/模式 | 核心思想 | 适用场景 |
|---------|---------|---------|
| Batched RMSNorm | 把 seq_len 次独立 norm kernel 合并为一个 2D batch kernel | 任何 per-token 的逐点 op |
| Triton FA2 prefill (HD256) | FlashAttention-2 的 Triton 实现，HEAD_DIM=256 拆为 4×64 块控制寄存器压力 | 全注意力层 prefill |
| Fused-recurrent GDR prefill | 把 per-token GDR 循环内化进一个 Triton kernel，消除 host-side token 循环 | 线性注意力 prefill 第一阶段 |
| Chunk-wise GDR prefill (FLA) | 把 seq 切成 chunk=64，用矩阵操作替代循环，7 阶段流水线 | 线性注意力 prefill 最终形态 |
| Triton AOT + Rust 调用 | Python Triton 编写 kernel，提前编译为 cubin，Rust 通过 cudarc FFI 调用 | 无 Python 运行时开销的 GPU 编程 |

---

## 深读

### 优化时间线与数字

| 步骤 | 改动 | TTFT (2048,1) | kernel launch 数量 |
|------|------|--------------|-------------------|
| 基线 | per-token 所有 op | 16.8s | ~160,000 |
| #1 Batched RMSNorm | 8,193 → 1 launch | 14.5s (−14%) | 减少 8,192 |
| #2–3 Triton FA2 prefill | 16,384 → 8 launch | 3.89s | 减少 ~16,376 |
| #6 Fused-recurrent GDR | 49K → 24 launch | 378ms | 295K → 278 |
| #7 Chunk-wise GDR | FLA 风格 7 阶段 | 222ms (in-process) / 235ms (HTTP) | 同数量级 |
| vLLM 基准 | torch.compile + CUDA Graph | 222ms | — |

### Qwen3.5-4B 混合架构

**关键设计**：32 层中 24 层是线性注意力（GDR），8 层是全注意力（GQA）。

- 线性注意力：recurrent state `[32 × 128 × 128]` f32/层，conv1d prefilter
- 全注意力：16 q_heads, 4 kv_heads, head_dim=256，partial RoPE rotary_dim=64 (25%)
- 总层数 32，全注意力 indices: 3, 7, 11, 15, 19, 23, 27, 31（每 4 层一次）

### 根本原因诊断

```
baseline nsys: wall clock 669ms, GPU kernel time 222ms
                                  ^^ CPU overhead 447ms (67%)
```

2048 token，每层每 token 一个 GDR kernel → 2048 × 24 = 49,152 launches  
每个 cudaLaunchKernel 约 5μs → 49K × 5μs ≈ **245ms 纯 CPU launch 开销**  
全注意力同理：2048 × 8 = 16,384 single-token attention launches

GPU 在等 CPU 排队，不是 GPU 算力不足。

### Triton FA2 HD256 实现细节

HEAD_DIM=256 在 Triton 中需要特殊处理：
```python
# 把 256-wide head 拆为 4×64，控制寄存器压力
QTR_HD: tl.constexpr = HEAD_DIM // 4  # = 64
# 计算 QK，4 路点积累加
qk += tl.dot(q_q0.to(tl.bfloat16), tl.trans(k_q0.to(tl.bfloat16)), out_dtype=tl.float32)
qk += tl.dot(q_q1.to(tl.bfloat16), tl.trans(k_q1.to(tl.bfloat16)), out_dtype=tl.float32)
# ... (4 路)
# 数值稳定：用 log2(e) trick，exp2 代替 exp
scale = 1.44269504 / tl.sqrt(float(HEAD_DIM))  # log2(e) / sqrt(HEAD_DIM)
m_new = tl.maximum(m_i, block_max)
p = tl.math.exp2(qk - m_new[:, None])
```

### Chunk-wise GDR 7 阶段流水线

从 FLA（Flash Linear Attention）移植，针对 Qwen3.5 固定 shape（batch=1, H=32, K=128, V=128, chunk=64）特化：

```
1. gdr_prepare_qkv_gbeta    ← Q/K L2 norm，expand heads，计算 softplus gate g，sigmoid beta
2. gdr_chunk_local_cumsum   ← chunk 内 g 的 prefix sum（因果掩码所需）
3. gdr_chunk_scaled_dot_kkt ← 构建 chunk-local 严格下三角 A = beta * exp(g_i - g_j) * K^T K
4. gdr_solve_tril_64        ← 求解 (I + A)^{-1}，固定 BT=64，4×16 分块迭代
5. gdr_recompute_w_u        ← 计算 W = (I+A)^{-1} K，U = (I+A)^{-1} V（WY-fast 核心）
6. gdr_chunk_state          ← 跨 chunk 传播 recurrent state h，每 chunk 末尾写 snapshot
7. gdr_chunk_o              ← 计算最终输出 O = Q·h_prev + intra-chunk attention（Q W^T U）
```

### 关键 Bug：GDR chunk_state 中 v_new 的 gating 语义

```python
# ❌ 错误：把 v_new 乘以 exp(g_last - g_t) 后写回 memory
v_new = v * exp(g_last - g_t)  # ← gated 后写出

# ✅ 正确（FLA 语义）：
# - v_new 必须以 ungated 形式写入 memory（供后续 WY-fast 更新矩阵用）
# - gated 形式只用于 recurrent state 累加：h += k ⊗ v_new_gated
v_new = v                      # ← ungated 写出
h += k ⊗ (v_new * exp(g))     # ← gated 只用于 h 更新
```

修复后 v_new stage 误差从严重错误降到 max ~1.95e-3，chunk_o 误差 max ~1.22e-4。

---

## 心智模型

> **kernel launch 是跨越 CPU-GPU 边界的函数调用，每次成本约 5μs。per-token 的 sequential 循环在 seq_len=2048 时等价于在热路径上串行调用 5万次函数。**

**适用条件**：任何"对每个 token/位置 单独启动一个小 kernel"的推理 loop  
**失效条件**：当每个 kernel 本身已经是大型 GEMM（cuBLAS 自己管理 batch），或 decode（seq_len=1，无法 batch）  
**在我的工作中如何用**：构建推理引擎时，prefill 路径必须从设计上避免 per-token kernel dispatch

---

## 非显见洞见

- **洞见 1：GPU utilization 低不代表算法差——可能只是 CPU launch 在排队**
  - 所以：profiler 里看 "GPU kernel time vs wall clock" 的比值才是诊断起点，不是 GPU 占用率
  - 所以：nsys `cuda_api_sum` 中 `cudaLaunchKernel` 的 total calls 是隐藏的瓶颈指标
  - 因此可以：对任何 seq_len > 128 的 prefill，先数 kernel launches，再考虑 kernel 优化

- **洞见 2：chunk-wise 算法是 recurrent 模型达到 attention-parity prefill 的结构性必要条件**
  - 所以：fused-recurrent（把 token 循环内化进一个 kernel）只是过渡态，TTFT 还是受限于 kernel 内部的 seq 串行依赖
  - 所以：真正的并行化需要打破 token 内的顺序依赖——chunk-wise 把 64-token 块内转化为矩阵运算（solve_tril + GEMM）
  - 因此可以：所有 recurrent / linear attention 模型（Mamba, RWKV, GLA, GDR）prefill 优化的终点都是 chunk-wise 路径

- **洞见 3：Triton + Rust AOT = 比 FlashAttention C++ 更快迭代，但保持零 Python 运行时**
  - 所以：kernel 用 Python Triton 写（高层语义，易实验），编译为 AOT cubin，Rust cudarc 调用
  - 所以：和 PyTorch/vLLM 的区别是：没有 Python GIL，没有 eager tensor dispatch 开销，有完整 Rust 内存安全
  - 因此可以：这是一个可复制的"高生产力 GPU 内核"模板，不需要写 C++

---

## 隐含假设

- **假设 1：单 GPU，单请求，batch=1**：若不成立（multi-request batching），则 chunk-wise 的跨 chunk state 顺序依赖会变为 per-sequence 独立，并行度大幅提升，效果更好
- **假设 2：chunk_size=64 固定**：若 seq_len 不整除 64，需要 padding 处理（当前用 `boundary_check`）；若 chunk_size 成为可调参数，则 solve_tril 的 block 分解方案需要泛化
- **假设 3：RoPE rotary_dim=64（仅 25% head_dim）**：全注意力 RoPE 只旋转 head_dim 的前 64 维，这减少了 rope cache 体积和 QK preprocessing 成本

---

## 反模式与陷阱

- **反模式：复用 decode kernel 做 prefill**
  - 描述：早期 pegainfer 用 `fused_attention_hd256_single_token`（为 decode=1 设计）处理 prefill 的每个 token → 正确但有 16,384 launches 开销
  - 正确做法：prefill 和 decode 路径必须分开实现，各自针对 "batch matrix" vs "single vector" 优化

- **陷阱：WY-fast 中 v_new 的 gating 位置**
  - 描述：WY-fast 分解中，v_new 的 ungated 版本用于更新矩阵 W/U，gated 版本只用于 recurrent state；混淆两者会导致 chunk_o 输出静默偏差（e2e 测试失败，但不 crash）
  - 正确做法：始终参考 FLA 原始实现的变量命名约定，`v_new` = ungated，`v_new_gated` = 用于 h 更新

- **陷阱：Triton HD256 寄存器溢出**
  - 描述：直接把 256-wide vector 载入一个 Triton block → 寄存器压力过大，spill 到 DRAM
  - 正确做法：拆为 4×64，用 `QTR_HD: tl.constexpr = HEAD_DIM // 4` 分块加载和计算

---

## 与现有知识库的连接

- 关联 `analysis/rust-mapreduce-architecture.md`：MapReduce 的 Map → Shuffle → Reduce 三阶段结构与 chunk-wise GDR 的 prepare → local-compute → state-propagate 高度同构。chunk-wise 算法本质是 MapReduce 在 GPU 上的一次实例化。

- 关联 `snippets/kway-merge-heap.rs`：kway merge 处理有顺序依赖的多路归并；chunk-wise GDR 的 `gdr_chunk_state` 阶段也是有顺序依赖的跨 chunk 归并（每个 chunk 的终态 h 是下一个 chunk 的初态）。两者都是"依赖链不可并行，但链上每个节点内部可并行"的模式。

- 关联 `python/mini_symphony.py`：mini_symphony 的 per-task subprocess spawn 与 per-token kernel launch 是同一类问题——频繁跨越进程/设备边界的开销。解法也相同：batch 化，减少边界穿越次数。

- 关联 `analysis/karpathy-nanochat.md`：nanochat 关注训练的 per-token cost；这里关注推理的 prefill 路径。两者合起来揭示了 seq_len 对 GPU 工作负载特征的影响：prefill 是 compute-bound GEMM + kernel launch overhead，decode 是 memory-bandwidth-bound GEMV。

---

## 衍生项目想法

### 想法 1：chunk-wise 线性注意力 prefill 通用模板库（Triton + Rust）

**来源组合**：[pegainfer chunk-wise GDR 7 阶段实现] + [snippets/emscripten-wasm-build-template.sh 的"build 脚本即 API 约定"思路]
**为什么有意思**：目前 pegainfer 的 chunk-wise GDR 是硬编码 Qwen3.5 的 shape（H=32, K=128, V=128, chunk=64）。但任何基于 GDR/GLA/Delta Rule 的线性注意力模型都需要完全相同的 7 阶段 pipeline，只是 shape 不同。把形状参数化，抽象为 `ChunkwiseLinearAttnPrefill<HEAD, KEY_DIM, VALUE_DIM, CHUNK_SIZE>` Triton kernel 族，同时保持 AOT 编译（用 constexpr shape 换性能）。
**最小 spike**：把 Qwen3.5 的 `gdr_chunk_scaled_dot_kkt` 中的 BLOCK_T / KEY_DIM 从 constexpr 改为运行时参数，测量 Triton autotuner 能否在不同 shape 下自动找到最优配置
**潜在难点**：Triton AOT 模式和运行时 autotune 模式互斥——要 AOT 性能就必须固定 constexpr，要泛用性就必须放弃最优编译时展开

### 想法 2：kernel launch budget 诊断工具

**来源组合**：[pegainfer nsys 诊断方法：`cuda_api_sum` launch count] + [python/session_tracker.py 的 event capture 思路]
**为什么有意思**：pegainfer 靠手动 nsys profiling 发现 "295K launches 是瓶颈"，这个诊断流程可以自动化。写一个轻量工具：给定任意 CUDA 程序，在 dry-run 时拦截 `cudaLaunchKernel` 调用，统计 launch count 和 size distribution，自动标注"这里每个 token 一个 launch"的 hotspot。
**最小 spike**：用 LD_PRELOAD 拦截 libcuda.so 的 `cuLaunchKernel`，打印 (grid_x, block_x, timestamp) 到 SQLite，用 session_tracker.py 的 priority snapshot 方法压缩输出
**潜在难点**：CUDA Graph 会把 launch 提前录制，拦截 replay 阶段得到的 call count 不等于实际 kernel 执行次数

---

## 结构性收获

**prefill vs decode 的优化方向完全不同**：
- decode: seq=1，memory-bandwidth-bound，CUDA Graph 消除 CPU overhead，目标是减少 VRAM 读写
- prefill: seq=N，初期 CPU-launch-bound（kernel 太小太多），消除后变为 compute-bound（GEMM + recurrent kernel），目标是最大化矩阵并行度

对于 recurrent 模型，prefill 优化的三个层次（从低到高）：
1. **消除 per-token kernel dispatch**：把 N 个 decode kernel 合并为 1 个 batch kernel（TTFT 数十倍改善）
2. **消除 per-token host-side 循环**：把 token 循环内化进 kernel（fused-recurrent）
3. **把 token 顺序依赖转化为 chunk 内矩阵并行**：chunk-wise WY-fast（最终性能上限）
