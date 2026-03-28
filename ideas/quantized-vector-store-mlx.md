# MLX 量化向量存储：百万级本地向量搜索

**来源**: https://github.com/lingengyuan/qjl-mlx + `python/zvec_inprocess_vector.py`
**日期**: 2026-03-28
**状态**: ❌ 已饱和（2026-03-28 验证）

> **验证结论**：Google TurboQuant 论文本身已在 SIFT1M（100万×128d）和 Deep1B（10亿×96d）上做了完整的 Recall vs PQ 对比实验。我们在 10K-100K 规模上重做只是论文已有结果的小规模子集，不产出新 insight。

---

## 核心理念

> 将 TurboQuant 3-bit 量化集成到 in-process 向量库中，让 Apple Silicon Mac 在 ~300 MB 内存内完成百万级向量搜索。

**解决的核心痛点**：本地向量库（zvec、Qdrant local、ChromaDB）在百万级文档时内存占用过高（float32 × 1024 dim × 1M = 4 GB），限制了纯本地 RAG 的规模上限。

**非显见之处**：直觉上"量化后检索质量会大幅下降"，但 TurboQuant 3-bit 在 1000 doc 规模下 Recall@5 仍有 71.6%、Pearson r = 0.971。牺牲 ~30% 的 Recall 换取 10x 的内存压缩，在许多 RAG 场景（先粗筛再 rerank）中是值得的。

---

## 关键技术要点

### 压缩 Pipeline

```
原始嵌入 (float32, 4 bytes/dim)
  → TurboQuant 旋转 + 极坐标量化 (3 bits/dim)
  → 打包存储 (uint8 角度码 + float32 范数)
  → 内存压缩比 ~10.5x
```

### 检索 Pipeline

```
Query (float32)
  → 预旋转 (一次矩阵乘法)
  → 对所有量化向量做非对称 score
    → mse 模式: decode_rotated → dot product
    → 未来: 可用 table-lookup 加速
  → Top-K 选取
  → 可选: 对 Top-K 重新用原始向量精排
```

### 关键参数

| 配置 | bits/dim | 内存/百万向量 | Recall@5 (1K doc) |
|------|----------|-------------|-------------------|
| float32 baseline | 32 | ~4 GB | 100% |
| TURBOQUANTmse 3-bit | 3.03 | ~390 MB | 71.6% |
| PolarQuant 2-bit | 2.03 | ~260 MB | 46.4% |
| QJL 1-bit | 1.0 | ~128 MB | 33.6% |

### 核心代码路径（来自 qjl-mlx）

```python
# 初始化（一次性）
compressor = TurboQuantMLXCompressor(dim=1024, total_bits=3, mode="mse")

# 压缩
compressed = compressor.compress(mx.array(embeddings))

# 检索
rotated_query = compressor.rotate_query(mx.array(query))
scores = compressor.score_rotated_query(rotated_query, compressed)
top_k = mx.argsort(scores)[-k:]
```

---

## 蕴含链

TurboQuant 3-bit 在 d=1024 下实现 10x 内存压缩且保持 Pearson r > 0.97
→ 所以：百万级向量从 4 GB 降到 400 MB，Mac 16 GB 机器上可行
→ 所以：不再需要外部向量数据库（Qdrant、Milvus）来处理中等规模文档库
→ 因此可以：构建一个"文档超过 10 万就自动启用量化"的自适应本地向量库，小规模用 float32 精确搜索，大规模自动降级到 3-bit 近似搜索 + rerank 精排

---

## 可行性分析

- ✅ 已验证可行：TurboQuant MLX 后端代码已存在且通过验证
- ✅ 已验证可行：打包/解包（pack_codes/unpack_codes）实现完整
- ⚠️ 待解决：当前 scoring 是 decode-then-dot（慢），需要 table-lookup 优化
- ⚠️ 待解决：旋转矩阵初始化需要 QR 分解（CPU fallback），但只执行一次
- ⚠️ 待解决：添加新文档时需要重新量化或支持增量插入
- ❌ 潜在阻断：如果检索场景需要 Recall@5 > 90%，3-bit 不够，需要 4-bit（但 4-bit PolarQuant Recall@5 = 100% on toy）

**适用边界**：
- 规模：10 万~1000 万文档时价值最大。< 1 万时 float32 内存不是问题；> 1000 万时可能需要分布式方案。
- 精度：适用于"先粗筛再 rerank"的两阶段检索架构。不适用于需要精确向量重建的场景。
- 硬件：Apple Silicon 必须（MLX 依赖），统一内存是 CPU fallback 无开销的前提。

---

## 与现有知识库的连接

- 关联 `python/zvec_inprocess_vector.py`：zvec 是最直接的集成目标——加一个量化后端选项。
- 关联 `analysis/docflow-local-rag-assistant.md`：DocFlow 当前 2500 chunk 不需要量化（博客草稿已确认），但如果 DocFlow 扩展到扫描整个硬盘的文档，量化就有价值了。
- 关联 `analysis/qjl-mlx-turboquant-apple-silicon.md`：技术细节来源，特别是 MLX 算子回退模式和跨后端验证方法。

---

## 下一步行动

- [ ] 最小 spike：fork zvec，加 `TurboQuantMLXCompressor` 作为可选量化后端，跑 1000-doc benchmark 对比
- [ ] 测量 decode-then-dot 在 10 万 doc 下的 latency，评估是否需要 fused scoring kernel
- [ ] 设计增量插入方案：新文档即时量化追加，不需要全量重建
