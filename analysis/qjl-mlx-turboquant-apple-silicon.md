# QJL-MLX: TurboQuant Apple Silicon 移植精读

**来源**: [github.com/lingengyuan/qjl-mlx](https://github.com/lingengyuan/qjl-mlx)
**日期**: 2026-03-28
**标签**: vector-quantization, MLX, Apple-Silicon, KV-cache, PolarQuant, QJL

---

## 30秒 TL;DR

> Google Research 的 TurboQuant（PolarQuant + QJL）是一种 3-bit KV cache 量化算法。本项目将其从 JAX+CUDA 完整移植到 Apple Silicon MLX，分三阶段逐步验证（QJL → PolarQuant → TurboQuant），PyTorch 参考与 MLX 后端得分差异 < 10⁻⁷。移植过程揭示了三个论文未强调的实践真相：重建质量 ≠ 检索质量、无偏估计器实践中可能更差、坐标空间对齐是不可见的关键。

## 概念总览

| 概念/模式 | 核心思想 | 适用场景 |
|---------|---------|---------|
| **QJL (Quantized JL)** | 随机正交旋转 + 1-bit 符号压缩，无偏内积估计 | 极低精度向量压缩，1 bit/dim |
| **PolarQuant** | 递归极坐标变换 + 固定 codebook 角度量化 | 2-4 bit 向量量化，不需要动态归一化 |
| **TURBOQUANTmse** | 所有 bit 给 PolarQuant，有偏但足够好 | 生产推理推荐模式 |
| **TURBOQUANTprod** | PolarQuant(b-1 bit) + QJL 残差(1 bit)，理论无偏 | 研究/理论验证 |
| **Lloyd-Max 量化** | 对解析角度分布迭代优化分桶边界 | 任何已知概率分布的标量量化 |
| **MLX 算子回退模式** | QR 走 CPU、searchsorted 走广播比较 | MLX 移植中遇到 GPU 缺失算子 |
| **分阶段验证 + Handoff 文档** | 每个阶段独立验证、写交接文档、再进入下一阶段 | Agent 驱动的多阶段工程项目 |

---

## 深读

### 算法三层结构

TurboQuant 不是一个独立算法，而是两个已有算法的组合：

1. **QJL**（arXiv:2406.03482）：用随机正交矩阵 S 旋转向量，只保留旋转后每个维度的符号位（±1）。数学保证：E[⟨q, Q⁻¹(Q(k))⟩] = ⟨q, k⟩（无偏估计）。关键：query 保持高精度，key 压缩为 1-bit，非对称估计内积。

2. **PolarQuant**（arXiv:2502.02617）：共享随机旋转后，递归地将 d 维向量分组为 (d/2) 对坐标，每对转换为 (角度, 半径)，角度用固定 codebook 量化。每层递归将维度减半，直到剩下一个标量（向量范数）。

3. **TurboQuant**（arXiv:2504.19874）：组合上述两者。mse 模式把所有 bit 给 PolarQuant（简单有效），prod 模式把 b-1 bit 给 PolarQuant、1 bit 给 QJL 残差纠错（理论最优但实践噪声大）。

### Lloyd-Max 比等分位更好

PolarQuant 每层递归的角度分布有解析形式：
- Level 1：[0, 2π) 上均匀分布
- Level k > 1：[0, π/2] 上密度正比于 sin(2θ)^(2^(k-1) - 1)

等分位（equal-quantile）切分虽然已经是合理起点，但 Lloyd-Max 迭代（质心 = pdf 加权平均，边界 = 相邻质心中点）能进一步优化 MSE。本项目实现后：
- 2-bit 重建余弦：0.889 → 0.891
- 2-bit Recall@5：84% → 88%（toy benchmark）

### MLX 移植：两个算子缺口

1. **`mx.linalg.qr` 只支持 CPU**：临时切换默认设备到 CPU，算完切回。Apple Silicon 统一内存，无数据拷贝。QR 只在初始化执行一次，不影响推理。

2. **无 `searchsorted`/`bucketize`**：用广播比较替代——将角度与所有边界做 ≥ 比较再求和得到 bucket index。固定 codebook 只有 2-4 个边界，广播开销可忽略。

### 跨后端验证方法

MLX 后端接受可选的 `rotation_matrix` 参数，测试时直接传入 PyTorch 参考实现的旋转矩阵，确保两边用完全相同的随机数。结果：max abs diff = 0.000000178（analytic 配置）。独立初始化路径的正交误差 ~1.67e-6，与 NumPy QR 精度一致。

### AGENTS.md 治理框架

项目使用 AGENTS.md 定义 9 条规则约束 Agent 行为：
- 不能在 handoff 文档未更新时声明阶段完成
- 验证发现的是"limitation"时必须如实记录，不能包装为"已解决"
- 每个阶段必须记录精确命令、输出指标、未解决风险

---

## 心智模型

> **"参考实现先行，正确性验证后再移植"的分层移植策略。**

作者不是直接用 MLX 从零实现 TurboQuant，而是先用 PyTorch 逐个验证每个子算法（QJL → PolarQuant → TurboQuant），确认数学正确后再移植到 MLX，用共享旋转矩阵做跨后端 parity 检查。

**适用条件**：目标框架（MLX）文档不完善、算子覆盖不确定时，先用成熟框架（PyTorch）建立 ground truth 是高效策略。
**失效条件**：如果目标框架的编程模型与参考框架差异极大（例如 eager vs lazy），直接对照移植可能导致性能问题。MLX 的 lazy evaluation 在本项目中已隐含处理（手动 `mx.eval`），但更复杂场景可能需要重新设计数据流。
**在我的工作中如何用**：任何涉及数值算法移植的项目，都应该先在熟悉框架建立验证基准，再移植到目标框架。

---

## 非显见洞见

### 洞见 1：重建质量好 ≠ 检索质量好

- **洞见**：PolarQuant analytic codebook 的重建余弦（0.889）远优于 uniform（0.820），但检索 Recall@5 反而更低（84% vs 88%）。
  - 所以：检索只关心排序一致性，不关心绝对值重建精度。均匀切分在排序上更稳定，虽然每个角度的重建误差更大。
  - 所以：优化量化算法时，MSE 不是唯一指标——需要 end-to-end 指标（Recall、NDCG）来评判。
  - 因此可以：在设计向量量化方案时，始终用检索指标而非重建指标做最终决策；可以同时保留多种 codebook 供下游任务选择。

### 洞见 2：理论无偏在实践中可能是净负贡献

- **洞见**：TURBOQUANTprod（理论无偏）在 1000 文档规模下 Recall@5 只有 48.8%，远低于 TURBOQUANTmse（有偏但 71.6%）。
  - 所以：QJL 残差估计的方差 O(1/d) 在 d=1024 时仍然较大，噪声淹没了纠错收益。
  - 所以：Attention softmax 只需要相对排序正确，绝对无偏反而引入了不必要的方差。
  - 因此可以：在实际系统中，优先选择低方差的有偏估计器（MSE 目标），除非无偏性有明确的理论需求（如统计检验）。

### 洞见 3：坐标空间对齐是不可见的关键

- **洞见**：PolarQuant 在旋转空间量化，残差也必须在旋转空间计算。如果将残差拉回原空间再做 QJL，旋转矩阵的正交性保证断裂，QJL 纠错完全失效（Recall 与不加 QJL 一样）。
  - 所以：两个算法组合时，"在哪个空间操作"是一个容易被忽视但致命的决策点。
  - 所以：论文"一句话带过"的空间约束，在实现中可能是 80% 调试时间的来源。
  - 因此可以：组合多个数值算法时，第一步应明确每个算法的"工作空间"，在代码中用显式的变量命名（如 `_rotated` 后缀）强制标注坐标空间。

### 洞见 4：RoPE 和随机旋转不交换——KV cache 量化的根本限制

- **洞见**：TurboQuant 的"预旋转 query"优化在 LLM KV cache 场景下不可用，因为 TurboQuant 旋转 Π 和 RoPE 位置编码不交换（Π·RoPE ≠ RoPE·Π）。
  - 所以：社区（TheTom/turboquant_plus）已确认放弃"预旋转 query"路径。
  - 所以：在实际 KV cache 应用中，旋转必须在 RoPE 之前应用于 key，而不是应用于 query。这改变了整个推理 pipeline 的集成点。
  - 因此可以：评估任何 KV cache 量化方案时，必须检查它与位置编码的交互——这是被论文和 benchmark 忽略但部署时致命的约束。

---

## 隐含假设

作者默认了但没有说明的前提：

- **假设 1：向量维度足够高（d ≥ 768）**：QJL 的 JL 引理保证和 PolarQuant 的角度分布收敛都依赖高维。若 d < 100，递归极坐标变换层数太少，codebook 质量会急剧下降。
- **假设 2：向量近似各向同性（isotropic）**：随机正交旋转的效果假设数据不存在极端的方向偏好。如果嵌入空间存在强各向异性（如某些维度方差远大于其他），可能需要 PCA 预处理。
- **假设 3：检索场景不需要精确重建**：整个分析框架围绕 Recall 和排序质量。如果下游需要精确向量重建（如生成模型的 conditioning），3-bit 量化的误差可能不可接受。
- **假设 4：Apple Silicon 统一内存消除了 CPU/GPU 数据传输成本**：QR 走 CPU 的回退之所以无开销，依赖 Apple 芯片的统一内存架构。在传统 CPU+GPU 分离的架构上，这个回退会引入数据传输延迟。

---

## 反模式与陷阱

- **"看数字选 codebook" 陷阱**：analytic codebook 的重建指标更好，但检索指标更差。如果只看 MSE/cosine 就做决策，会选错。→ 正确做法：始终用 end-to-end 任务指标做最终判断。

- **"论文说无偏就选无偏" 陷阱**：TURBOQUANTprod 数学上是 Theorem 2 的无偏估计器，但在有限维度下方差太大。→ 正确做法：在目标规模和维度下实测，不要只信理论保证。

- **"组合两个正确的算法自然正确" 陷阱**：QJL 正确 + PolarQuant 正确 ≠ 组合正确。残差空间不对齐时，两个正确算法的组合效果为零。→ 正确做法：组合后必须独立验证，且在变更坐标空间时显式标注。

- **`np.trapz` 在 NumPy 2.x 已移除**：必须用 `np.trapezoid` 替代。这类 API 变更在数值计算代码中特别隐蔽。

---

## 与现有知识库的连接

- 关联 `analysis/docflow-local-rag-assistant.md`：博客草稿中直接讨论了将 TurboQuant 接入 DocFlow 的可行性——2500 chunk / 10MB 的规模下收益为零，瓶颈在 LLM TTFT 而非向量搜索。这为"什么时候值得用向量量化"提供了具体的反例。

- 关联 `python/zvec_inprocess_vector.py`：zvec 演示的是 in-process 向量库 + 混合检索。如果 zvec 场景扩展到百万级文档，TurboQuant 的 3-bit 压缩（10.5x 内存压缩比）可以让更多向量放入内存。组合方向：给 zvec 加一个可选的量化后端。

- 关联 `analysis/karpathy-nanochat.md`：nanochat 中"显式精度管理"的心智模型与本项目一致——torch.float32 → bfloat16 的精度控制类似于这里的 angle_bits 管理。两者共享"精度是需要工程师显式决策的维度"这一认知。

- 关联 `analysis/karpathy-autoresearch.md`：autoresearch 的 git-ratchet 分阶段验证模式与 qjl-mlx 的 Phase 1→2→3 handoff 模式高度相似。区别在于 autoresearch 用 git commit 做不可回退的棘轮，qjl-mlx 用 handoff 文档做阶段交接。

- 关联 `analysis/pegainfer-qwen35-prefill-optimization.md`：pegainfer 处理的是 prefill 阶段的 TTFT 优化，TurboQuant 处理的是 KV cache 内存压缩。两者解决 LLM 推理的不同瓶颈（计算 vs 内存），但可能在同一个推理 pipeline 中共存。

---

## 可复用代码模式

### 1. MLX QR CPU 回退

```python
original_device = mx.default_device()
try:
    mx.set_default_device(mx.cpu)
    q, _ = mx.linalg.qr(mx.array(sample))
    mx.eval(q)
finally:
    mx.set_default_device(original_device)
```

适用于 MLX 中任何 GPU 不支持但 CPU 支持的线性代数算子。Apple Silicon 统一内存保证无数据拷贝。

### 2. 广播比较替代 searchsorted

```python
comparisons = mx.expand_dims(angles, -1) >= boundaries[1:-1]
codes = mx.sum(comparisons, axis=-1).astype(mx.uint8)
```

适用于固定边界数量少（≤ 16）的量化场景。边界数量大时，二分查找更高效。

### 3. 跨后端 Parity 测试——共享随机矩阵注入

```python
# PyTorch 生成参考旋转矩阵
torch.manual_seed(42)
S = torch.randn(dim, dim)
Q, _ = torch.linalg.qr(S)

# MLX 后端接受注入
mlx_compressor = TurboQuantMLXCompressor(
    dim=dim, rotation_matrix=Q.numpy()
)
```

适用于任何涉及随机初始化的跨框架数值验证。

---

## 衍生项目想法

### 想法 1：MLX 向量量化存储后端

**来源组合**：[TurboQuant MLX 3-bit 压缩] + [已有 `python/zvec_inprocess_vector.py` 的 in-process 向量库]
**为什么有意思**：zvec 当前存储 float32 向量，百万级文档需要 ~3 GB 内存。加入 TurboQuant 量化后可降至 ~300 MB，使 Mac 上百万级向量搜索成为可能，同时保持 Recall@5 > 70%。
**最小 spike**：给 zvec 加一个 `quantize=True` 参数，用 TurboQuantMLXCompressor 压缩向量，score 时调用 `score_rotated_query`，对比 float32 baseline 的 Recall 和延迟。
**潜在难点**：TurboQuant 当前的 scoring 是 decode-then-dot（无 fused kernel），规模化后可能比 float32 暴力扫描更慢。

### 想法 2：AGENTS.md 治理模板

**来源组合**：[qjl-mlx 的 AGENTS.md 9 条规则 + 分阶段 handoff 模式] + [已有 `analysis/karpathy-autoresearch.md` 的 git-ratchet 模式]
**为什么有意思**：两个项目各自解决了 Agent 驱动工程的不同失效模式——qjl-mlx 解决"Agent 过早声明完成"，autoresearch 解决"Agent 回退到已验证过的状态"。组合后可以构建一个更完整的 Agent 工程治理框架。
**最小 spike**：提取 AGENTS.md 的 9 条规则 + autoresearch 的 NEVER STOP 设计，合成一个 `templates/AGENTS.md.template`，附带分阶段 handoff 文档模板。
**潜在难点**：规则过多会降低 Agent 的灵活性，需要找到最小有效规则集。

### 想法 3：KV Cache 量化 + Prefill 优化联合推理 Pipeline

**来源组合**：[TurboQuant KV cache 3-bit 压缩] + [已有 `analysis/pegainfer-qwen35-prefill-optimization.md` 的 chunk-wise prefill 优化]
**为什么有意思**：LLM 长上下文推理有两个瓶颈——prefill 阶段的计算延迟（pegainfer 解决）和 decode 阶段的 KV cache 内存（TurboQuant 解决）。两者是互补的，但目前没有人在 MLX 上把两者集成到一个 pipeline 里。
**最小 spike**：在 MLX-LM 推理流程中，prefill 后将 KV cache 用 TurboQuant 压缩，decode 阶段用压缩后的 cache 做 attention，测量 peak memory 和 perplexity 变化。
**潜在难点**：RoPE 与 TurboQuant 旋转不交换（已知限制），需要在 RoPE 之前对 key 做量化旋转，这需要修改模型的 attention 层。

---

## 开放问题

1. **uniform codebook 在大规模下是否仍然优于 analytic？** toy benchmark 的逆转可能是小样本效应，1000-doc 规模未分别测试两种 codebook。
2. **TURBOQUANTprod 的方差在更高维度（d=4096）下是否收敛到可用水平？** 当前结论基于 d=1024，大模型的 head_dim 可能不同。
3. **MLX lazy evaluation 对大规模 batch 量化的影响？** 当前实现手动 `mx.eval`，未探索计算图合并的优化空间。
4. **Phase 4 向量存储集成的具体设计？** README 标记为 Planned，但无设计文档。
