# karpathy/nanochat 精读

**来源**: [karpathy/nanochat](https://github.com/karpathy/nanochat)
**日期**: 2026-03-09
**标签**: llm-training, gpt, muon-optimizer, single-gpu, precision-management, kv-cache, autoresearch-parent

---

## 30秒 TL;DR

> nanochat 是一个"单拨盘"LLM 训练框架：用户只需设置 `--depth`（Transformer 层数），宽度/头数/LR/训练时长/权重衰减全部自动推导出计算最优值。$48 可训出 GPT-2 级别模型（2019年需 $43,000）。核心技术组合：Muon+AdamW 混合优化器、x0 残差、Value Embedding、QK Norm、SSSL 滑窗注意力、softcap 逻辑值、显式精度管理（无 autocast）。

## 概念总览

| 概念/模式 | 核心思想 | 适用场景 |
|---------|---------|---------|
| 单拨盘设计（Single Dial）| `--depth` 唯一超参，其余全部自动推导 | 快速实验、autoresearch 循环 |
| x0 残差 | 每层都混回初始 token embedding：`x = λ·x + λ0·x0` | 深模型梯度流、表示学习 |
| Muon + AdamW 混合优化器 | 矩阵参数用 Muon（正交梯度更新），embedding 用 AdamW | 高效矩阵权重优化 |
| 显式 COMPUTE_DTYPE | 无 autocast，自定义 Linear 在 forward 中显式 cast | 精度可审查、可 grep |
| Value Embedding（ResFormer）| 交替层混入 token embedding 的 value 分支，input-dependent gate | 减少 attention sink，改善长序列 |
| softcap 逻辑值 | `20 * tanh(logits/20)`，平滑限制到 [-20, 20] | 训练稳定性，防止极端 logit |
| SSSL 滑窗模式 | 3 层半窗口 + 1 层全窗口，循环平铺到所有层 | 长序列效率与全局依赖的权衡 |
| 后台数据下载并行 | 开 tokenizer 训练时同步后台下载更多 shard | speedrun 的关键 wall clock 节省 |
| LR ∝ 1/√(d_model/768) | embedding/lm_head LR 随模型宽度缩放 | μP 思想的局部实现 |

---

## 深读

### GPT 模型架构（gpt.py）

```python
# 架构摘要（GPTConfig defaults）：
sequence_len = 2048
vocab_size   = 32768
n_layer      = 12          # --depth 控制这里
n_head       = 6           # 自动从 depth 推导
n_kv_head    = 6           # GQA：可设为 n_head 的因数
n_embd       = 768         # 自动从 depth 推导
window_pattern = "SSSL"   # 3层滑窗 + 1层全注意力
```

**完整 Forward 路径**：

```python
x = wte(idx)          # token embedding
x = x.to(COMPUTE_DTYPE)
x = norm(x)           # RMSNorm（无可学习参数）
x0 = x                # ← 保存初始 normalized embedding

for i, block in enumerate(transformer.h):
    x = resid_lambdas[i] * x + x0_lambdas[i] * x0  # ← x0 残差注入
    ve = value_embeds[i](idx) if has_ve(i) else None
    x = block(x, ve, cos_sin, window_sizes[i], kv_cache)

x = norm(x)
logits = lm_head(x)
logits = logits[..., :vocab_size]
logits = logits.float()
logits = 20 * torch.tanh(logits / 20)  # softcap
```

**注意力路径**：
```python
q = c_q(x).view(B, T, n_head, head_dim)
k = c_k(x).view(B, T, n_kv_head, head_dim)
v = c_v(x).view(B, T, n_kv_head, head_dim)

# Value Embedding 混入（ResFormer）
if ve is not None:
    gate = 2 * sigmoid(ve_gate(x[..., :32]))  # 用 x 的前 32 维生成 gate
    v = v + gate.unsqueeze(-1) * ve            # 混入 token embedding 的 value

# RoPE + QK Norm
q, k = apply_rotary_emb(q, cos, sin), apply_rotary_emb(k, cos, sin)
q, k = norm(q), norm(k)

# FA3（Hopper+ SM90）或 SDPA fallback
y = flash_attn(q, k, v, causal=True, window_size=window_size)
```

**MLP**：
```python
x = c_fc(x)           # 线性扩展 4×
x = F.relu(x).square()  # Squared ReLU（不是 GELU/SiLU）
x = c_proj(x)
```

### 精度管理：无 autocast 的显式控制

```python
# common.py
COMPUTE_DTYPE = bfloat16  # SM80+, 否则 float32

# gpt.py
class Linear(nn.Linear):
    def forward(self, x):
        return F.linear(x, self.weight.to(dtype=x.dtype))
        # 主权重始终 fp32（优化器精度），forward 时 cast 到激活 dtype
```

对比 `torch.amp.autocast`：
- autocast 是隐式的，难以知道哪个 op 用了哪个精度
- COMPUTE_DTYPE 是全局显式，所有精度变化都能 grep
- 主权重保持 fp32，embedding 直接存 COMPUTE_DTYPE（省显存）

### Muon + AdamW 混合优化器（optim.py）

**参数分组策略**：
```python
# AdamW 组：查找表类参数
- lm_head        lr=0.004 * dmodel_lr_scale
- wte (embedding) lr=0.2 * dmodel_lr_scale
- value_embeds   lr=0.2 * dmodel_lr_scale
- resid_lambdas  lr=0.005
- x0_lambdas     lr=0.5 (beta1=0.96, 更高动量)

# Muon 组：所有 Transformer 矩阵权重（按 shape 分组堆叠）
- 所有 attention 权重 (c_q, c_k, c_v, c_proj)
- 所有 MLP 权重 (c_fc, c_proj)
lr=0.02, momentum=0.95, ns_steps=5, beta2=0.95
```

**LR 宽度缩放**：
```python
dmodel_lr_scale = (model_dim / 768) ** -0.5
# 模型变宽，embedding LR 按 1/√(width) 降低
# 768 dim → scale=1.0; 1536 dim → scale=0.707
```

**Muon 核心**：用 Polar Express（取代 Newton-Schulz）正交化梯度：
```python
# 5步迭代正交化 stacked gradient tensors
# 结果类似 UV^T（SVD 的正交分量），不是普通动量
# NorMuon：正交化后按每个神经元/列的尺度做自适应 LR
```

**融合内核**：
```python
@torch.compile(dynamic=False, fullgraph=True)
def adamw_step_fused(p, grad, exp_avg, exp_avg_sq, step_t, lr_t, ...):
    # 0-D CPU tensor 作为超参数 → LR 变化不触发重新编译
```

### 推理引擎（engine.py）

KV Cache 推理路径（在 `flash_attn_with_kvcache` 中处理）：
```python
# 每个 token 增量推理
y = flash_attn_with_kvcache(q, k_cache, v_cache, k=k, v=v,
    cache_seqlens=kv_cache.cache_seqlens, causal=True, ...)
# 最后一层处理完后推进位置计数器
if self.layer_idx == kv_cache.n_layers - 1:
    kv_cache.advance(T)
```

Calculator 工具（允许模型调用 Python eval）：
```python
# 支持：纯数学表达式、字符串 .count() 操作
# 禁止：__, import, exec, eval, compile, open, **（幂运算）
# 超时：signal.SIGALRM 3秒
```

### Speedrun 的并行数据策略

```bash
python -m nanochat.dataset -n 8         # 下载 8 个 shard 给 tokenizer
python -m nanochat.dataset -n 170 &    # 后台下载 170 个 shard 给 pretrain
DATASET_DOWNLOAD_PID=$!

python -m scripts.tok_train              # 前台训练 tokenizer（约 2 分钟）

wait $DATASET_DOWNLOAD_PID              # 等后台下载完

torchrun ... -m scripts.base_train      # 开始 pretrain
```

tokenizer 训练与数据下载完全并行，节省了约 20 分钟 wall clock。

### 完整 Pipeline（speedrun.sh）

```
1. BPE tokenizer 训练（vocab_size=32768）
2. Pretrain: depth=24, FP8, target-param-data-ratio=9.5（略低于计算最优比）
3. SFT: SmolTalk + 合成身份数据（教对话格式、工具使用）
4. RL（可选）
5. 部署 Web UI（chat_web.py）
```

---

## 心智模型

> **"复杂度应该表达为一个整数，然后所有细节自动推导。"**

nanochat 的哲学：给定计算预算（等价于 depth），存在唯一的"计算最优"超参配置。与其让用户搜索这个配置，不如把它固化进代码。用户只决定"我要多大的模型"，不决定"我要多大的学习率"。

**适用条件**：目标是通用预训练（language modeling），单 GPU 节点，固定数据集

**失效条件**：
- 需要微调已有的大模型（depth 是输入，不是自由变量）
- 数据集结构非常特殊（代码、数学），计算最优比可能完全不同
- 多节点训练（DistMuon 存在但未在主流程中使用）

---

## 非显见洞见

### 洞见 1：x0 残差是"所有层都能直接看到输入"的架构选择

- **洞见**：`x = resid_lambdas[i] * x + x0_lambdas[i] * x0` 在每一层都把初始 normalized embedding `x0` 混回去。这不是 skip connection（那是相邻层），而是从第 0 层直接连到所有层
  - 所以：梯度可以从 loss 直接流到 embedding 层，不需要穿过所有 Transformer block（解决深模型的梯度消失）
  - 所以：每层都有"提醒自己原始 token 是什么"的机制，防止深层表示过度偏离输入
  - 因此可以：在任何深 Transformer 实现中，加一个可学习的 x0 混合系数（`lambda * x + lambda0 * x0`），这是一行代码，但可能显著改善深模型训练稳定性

### 洞见 2：无 autocast = 精度管理从隐式变为可审查

- **洞见**：`torch.amp.autocast` 是隐式的——你不知道哪个 op 在 fp16 跑，哪个在 fp32 跑（PyTorch 有内部规则）。nanochat 的 `Linear.forward()` 显式 cast 意味着精度决策都在代码里
  - 所以：可以 `grep COMPUTE_DTYPE` 找到所有精度 boundary
  - 所以：FP8 训练（`--fp8` flag）可以精确控制在哪里应用 FP8，而不是让 autocast 决定
  - 因此可以：任何需要混合精度调试的项目，都可以用这个"自定义 Linear cast"模式替代 autocast，换取精度可审查性

### 洞见 3：Muon 只用于矩阵参数，AdamW 用于"查找表"参数，这是有理论依据的分组

- **洞见**：Muon 的正交化梯度对矩阵权重有意义（矩阵有行/列结构），但 embedding 是一个查找表，正交化没有明确含义
  - 所以：盲目把所有参数放入 Muon 会降低 embedding 的学习质量
  - 所以：正确的参数分组策略是"理解每类参数的数学性质，而不是统一对待"
  - 因此可以：在任何使用 Muon 的项目中，把 embedding、lm_head、bias、scale 参数显式排除到 AdamW 组

### 洞见 4：Speedrun 的并行数据下载是 wall clock 优化的典型思维

- **洞见**：tokenizer 训练需要 8 个 shard，pretrain 需要 170 个。传统做法是顺序下载全部再开始。speedrun 的做法是"下 8 个 → 启动 tokenizer → 后台继续下剩余 162 个 → 等待 → pretrain"
  - 所以：tokenizer 训练（几分钟）完全掩盖了数据下载的等待时间
  - 所以：在任何"数据准备时间 > 第一个计算步骤时间"的场景，后台下载 + wait 都是免费的时间节省
  - 因此可以：把这个模式用于 mini_symphony 的大任务分解——先 spawn 后台数据准备进程，让 agent 先处理不需要该数据的前置任务

---

## 隐含假设

- **假设 1：compute-optimal 的超参关系随深度单调变化**。若不成立（例如某些 depth 存在奇点），自动推导的 HP 会失效
- **假设 2：单 H100 节点是目标硬件**。Value Embedding、SSSL 窗口模式、FA3 集成都针对 H100 特性优化
- **假设 3：目标任务是通用语言建模（FineWeb 数据）**。pretrain 数据比和 LR 对代码/数学/多语言分布可能需要不同配置
- **假设 4：8192 vocab_size 的 BPE tokenizer 适合当前规模**。若模型变大，更大的 vocab 可能更优（参考 autoresearch 的 `vocab_size=32768`）

---

## 反模式与陷阱

- **陷阱：混淆 val_bpb 和 perplexity**
  `val_bpb` = val_loss / ln(2)，单位是 bits per byte（与 vocab size 无关）。perplexity = exp(loss)（与 vocab size 绑定）。在 vocab size 不同的模型间比较时，只有 bpb 是公平的

- **陷阱：FP8 不等于总是更快**
  FP8 在 H100（SM90）上有硬件支持，在 A100 上不一定更快或可用。`--fp8` flag 在非 Hopper 硬件上要额外处理

- **陷阱：SSSL 窗口模式在短序列上效率低**
  `S`（滑窗）是"半上下文"，对短于上下文的序列退化为全注意力，但有额外 overhead。autoresearch 的 program.md 建议小硬件用 `"L"` 替代 `"SSSL"`

- **陷阱：忘记 `target-param-data-ratio` 的含义**
  默认 10.5 是"计算最优"，GPT-2 speedrun 用 9.5 表示"略欠训"（以较少数据换更快 wall clock）。不是所有任务都想用默认值

---

## 与现有知识库的连接

- 关联 `analysis/karpathy-autoresearch.md`：autoresearch 的 `train.py` 直接从 nanochat 的 `gpt.py` 简化而来——相同的 SSSL、Value Embedding、Muon+AdamW、QK Norm、FA3 集成。autoresearch 是"nanochat 的 train.py + 实验循环包装"。现在读完两个文档，可以理解 autoresearch 的默认模型到底是什么

- 关联 `python/mini_symphony.py`：nanochat speedrun.sh 的"后台数据下载 + wait"是 mini_symphony 可以采用的并行子任务模式——agent 可以 spawn 后台数据准备任务（`TaskCreate`），继续处理前置步骤，然后等待数据准备完成再触发主任务

- 关联 `python/sandbox_execute.py`：nanochat 的 calculator 工具（`use_calculator()`）是一个更窄的沙箱——禁止 `__`、`import`、`exec`，只允许数学和 `.count()` 字符串操作。与 sandbox_execute.py 的"隔离子进程"相比，这是"同进程 eval + whitelist 过滤"，适合简单计算工具，但攻击面更大

---

## 衍生项目想法

### 想法 1：把 nanochat 的"单拨盘"设计模式提取为 HP 自动推导模板

**来源组合**：[nanochat 的 depth → 所有 HP 自动推导] + [autoresearch 的 program.md 循环]

**为什么有意思**：nanochat 把 compute-optimal 超参关系硬编码进了框架（width = f(depth), lr = g(depth), horizon = h(depth)）。这个"一个整数确定所有 HP"的模式是可以移植的——任何 ML 任务都有类似的 scale 参数（CNN 的 base_channels，ViT 的 patch_size × depth 组合）

→ 所以：autoresearch 可以利用 nanochat 已经建立的这些关系，不需要搜索 `n_embd`、`n_head` 等，只搜索 `depth`
→ 因此可以：写一个 Python 函数 `get_optimal_config(depth) -> GPTConfig`，用于任何需要"depth → full config"的实验脚本

**最小 spike**：从 nanochat codebase 中提取 `depth → (n_embd, n_head, vocab_size, lr_scale, training_horizon)` 的映射关系，写成独立的 `hp_scale.py` 供 autoresearch 使用

**潜在难点**：这些关系是针对 FineWeb 数据和 H100 hardware 拟合的，不一定能泛化到其他场景

---

### 想法 2：x0 残差作为独立的 PyTorch 模块

**来源组合**：[nanochat 的 x0 残差机制] + [snippets/mapreduce-engine.rs 的"读完实现再写抽象"方法论]

**为什么有意思**：x0 残差（每层都混回初始 embedding）目前只在 nanochat 和 autoresearch 里见到，但这个想法是通用的。对任何深 Transformer（10+ 层）来说，它是一行代码的改进，但需要两个可学习的 lambda 参数。把它封装成可插入的 PyTorch 模块，就能在任何 Transformer 实现里试验

**最小 spike**：
```python
class X0ResidualBlock(nn.Module):
    def __init__(self, block):
        super().__init__()
        self.block = block
        self.resid_lambda = nn.Parameter(torch.ones(1))
        self.x0_lambda = nn.Parameter(torch.zeros(1))
    def forward(self, x, x0, *args, **kwargs):
        return self.resid_lambda * self.block(x, *args, **kwargs) + self.x0_lambda * x0
```
包装现有 Transformer block，对比有无 x0 残差的 val_bpb

**潜在难点**：x0_lambdas 和 resid_lambdas 的初始化和 LR 对结果有很大影响（nanochat 里 x0 用 beta1=0.96）

---

### 想法 3：nanochat calculator 工具的 allowlist 沙箱模式

**来源组合**：[nanochat 的 `use_calculator()` 同进程 eval + whitelist] + [python/sandbox_execute.py 的隔离子进程]

**为什么有意思**：nanochat 的 calculator 工具展示了一个轻量沙箱：不 fork 子进程，用 whitelist 限制字符集 + 禁止 dunder + 超时信号。代价是攻击面存在（eval 在主进程中），但适合受信任环境的快速工具调用。与 sandbox_execute.py 的重量级隔离形成对比，两种方案各有适用场景

→ 所以：当工具调用的频率极高（每次推理都调用）时，fork 子进程的 overhead 不可接受，应用 allowlist 同进程 eval
→ 因此可以：把这两种模式的 tradeoff 文档化成"工具调用安全性等级指南"：轻量（同进程 whitelist）→ 中等（subprocess + timeout）→ 重量（docker/gvisor 沙箱）

**最小 spike**：把 `use_calculator()` 的 whitelist 逻辑扩展为支持更多 Python builtins（`len`, `sum`, `sorted`），但保持字符集白名单，测试攻击向量
