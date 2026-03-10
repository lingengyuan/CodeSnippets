# karpathy/autoresearch 精读

**来源**: [karpathy/autoresearch](https://github.com/karpathy/autoresearch)
**日期**: 2026-03-09
**标签**: autonomous-agent, ml-research, git-ratchet, self-modification, program.md

---

## 30秒 TL;DR

> 把 AI agent 关进一个只有一个可编辑文件（`train.py`）的仓库，让它在固定 5 分钟时间预算内做实验、看指标、保留或回滚，无限循环。你睡一觉，醒来有 100 个实验结果。核心洞见：**人类编程的是 `program.md`（元级指令），agent 编程的是 `train.py`（目标级代码）**——两级优化解耦。

## 概念总览

| 概念/模式 | 核心思想 | 适用场景 |
|---------|---------|---------|
| Git 棘轮 (Git Ratchet) | branch 只向前走：改进 → advance，退步 → git reset | 任何需要自动 A/B 实验的场景 |
| 固定时间预算 | 每次实验 5 分钟 wall clock，不管架构变化多大 | 使实验之间可直接比较 |
| 单文件修改域 | agent 只能编辑 `train.py`，diff 可审查 | 防止 agent scope 失控 |
| val_bpb 公平指标 | bits per byte，与 vocab size 无关 | 允许探索不同 tokenizer/架构 |
| program.md 即代码 | 人类迭代 program.md 就像迭代软件 | 元级研究组织优化 |
| NEVER STOP | 显式禁止 agent 询问是否继续 | 自主研究场景（人类睡着了） |
| 简洁性标准 | 等效果时删代码 > 加代码；明确写进 program.md | 对抗 ML 研究的复杂性偏见 |

---

## 深读

### 三文件架构

```
prepare.py  — 固定：数据准备、dataloader、eval。agent 不得修改
train.py    — 可变：模型、优化器、训练循环。agent 唯一编辑目标
program.md  — 元级：agent 行为指令。人类迭代优化
```

这种三层分离不是偶然设计，它对应了三种不同的时间尺度：
- `prepare.py`：实验跨运行不变的"物理定律"
- `train.py`：每次实验变化的"假设"
- `program.md`：人类跨多轮 autoresearch 运行积累的"研究方法论"

### 实验循环核心

```bash
# 每次迭代（~5分钟）：
git checkout -b autoresearch/<tag>  # 新运行用新 branch
# 修改 train.py
git commit
uv run train.py > run.log 2>&1      # 重定向防止 context 爆炸
grep "^val_bpb:\|^peak_vram_mb:" run.log  # 提取指标
# 如果改善 → advance；如果退步 → git reset HEAD~1
# 更新 results.tsv（不提交，untracked）
```

### train.py 技术栈（目前基线）

- GPT 架构：RMSNorm + RoPE + GQA（grouped query attention）
- Value Embedding（ResFormer 风格）：每隔一层，input-dependent gate 混合 value embedding
- `WINDOW_PATTERN = "SSSL"`：3 层滑窗注意力 + 1 层全注意力
- Flash Attention 3（Hopper GPU 用 varunneal/flash-attention-3，其他用 kernels-community/flash-attn3）
- Squared ReLU（`F.relu(x).square()`）
- 优化器：Muon + AdamW 混合
- 固定 5 分钟 wall clock，指标 val_bpb（越低越好）

---

## 心智模型

> **"你在为研究组织编程，agent 在为模型编程。"**

两级优化：
- Level 1（人类）：优化 `program.md`，决定 agent 用什么策略实验
- Level 2（agent）：优化 `train.py`，在当前 program 约束下找最优模型

**适用条件**：目标函数可以在固定时间预算内自动测量；实验空间是离散的代码修改

**失效条件**：实验运行时间差异极大（有的 1 分钟有的 1 小时）；评估本身昂贵到无法每轮运行；实验之间有依赖关系（例如需要共享 cache）

**在我的工作中如何用**：任何"修改代码→测量指标→保留或回滚"的场景都可以套用这个模式——不局限于 ML

---

## 非显见洞见

### 洞见 1：固定时间预算反转了 ML 研究的优化目标

- **洞见**：val_bpb in 5 minutes ≠ val_bpb with N training steps。固定 wall clock 让 agent 优化的其实是"哪种配置在你的硬件上学得最快"
  - 所以：agent 会自然发现与该平台硬件最匹配的架构（batch size、sequence length、模型宽深比）
  - 所以：在 H100 上跑出的最优 `train.py` 不一定在 A100 上是最优的——结果是平台绑定的
  - 因此可以：专门为自己的 GPU 用 autoresearch 跑一次，得到该平台专属的最优超参配置，比任何通用调参指南都更准确

### 洞见 2：简洁性标准是逆 ML 研究激励的

- **洞见**：program.md 明确写着"删代码得到相同结果 = 胜利"，"0.001 bpb 改善加 20 行丑代码 = 不值得"
  - 所以：agent 被激励去做 ablation（删除组件验证是否必要），而不是堆砌复杂性
  - 所以：实验历史中的 "discard" 记录本身有价值——它们证明了哪些复杂性是不必要的
  - 因此可以：把 autoresearch 跑出的 results.tsv 中的 "discard" 条目作为简洁性证据，用于论文的 ablation table

### 洞见 3：results.tsv 不提交是防冲突的工程决策

- **洞见**：results.tsv 故意设为 untracked（不进 git），而每次代码修改都进 git
  - 所以：git log 变成纯实验历史，每个 commit = 一次假设，可以 `git diff` 看具体改了什么
  - 所以：branch 的 git 历史可以重放整个研究过程；results.tsv 是元数据，不是实验本身
  - 因此可以：用 `git log --oneline` 快速 review 所有实验思路；用 `git show <hash>` 看某次实验的具体修改

### 洞见 4：NEVER STOP 是 program.md 最重要的一行

- **洞见**：agent 如果每次完成一组实验就问"要继续吗？"，人类睡觉期间就会卡住。NEVER STOP 不是鼓励冒险，是工程上保证连续性
  - 所以：agent 的自主性在夜间有实际价值——100 个实验的信息量 > 人类花同等时间能手动跑的量
  - 所以：agent 需要内置的"坚持"机制，把"用完思路就停"的默认行为显式覆盖
  - 因此可以：在任何自主 agent 的 program.md/system prompt 里，明确禁止它问"是否继续"的习惯性确认

---

## 隐含假设

- **假设 1：agent 的上下文不会在 100 次实验中崩溃**。若上下文在实验中途被压缩，agent 可能丢失实验历史。→ 若不成立：需要 session_tracker.py 类的机制，把实验 log 写到磁盘并定期 compact
- **假设 2：每次实验的代码修改足够小，不会让训练超时**。若 agent 做了一个 OOM 改动，需要有能力识别并回滚。→ program.md 有 10 分钟 timeout 设计，部分缓解
- **假设 3：val_bpb 是真正意义上的通用目标**。但它测的是语言建模能力，不是 instruction-following 或 reasoning。

---

## 反模式与陷阱

- **陷阱：让 agent 在实验循环中输出到 stdout**。
  `uv run train.py` 不加 `> run.log 2>&1` → 训练 log 直接进 agent context → context 迅速爆炸
  正确做法：永远重定向，只用 `grep` 提取关键行

- **陷阱：results.tsv 加进 git**。
  多个 branch 并行运行会产生冲突，autonomous loop 无法处理 merge conflict
  正确做法：gitignore 或明确 untracked

- **陷阱：让 agent 自由安装依赖**。
  一旦允许 `pip install`，实验空间爆炸且不可复现。固定 `pyproject.toml` 是边界设计

- **陷阱：时间预算设置太短（< 3 分钟）**。
  Flash Attention 等编译时间可能占据 startup overhead，导致实际训练时间不稳定

---

## 与现有知识库的连接

- 关联 `python/mini_symphony.py`：mini_symphony 是"任务队列 → agent 子进程"的通用编排器；autoresearch 是"实验循环 → git ratchet"的研究专用版本。两者可以融合：mini_symphony 管理多个 autoresearch branch 并行跑，最后 cherry-pick 最优 commit
- 关联 `python/session_tracker.py`：100 次实验 = context 必然多次压缩。session_tracker 的 PreCompact 快照机制可以保存 results.tsv 的关键摘要（top-5 experiments）让 agent 在恢复后继续
- 关联 `analysis/simon-willison-red-green-tdd.md`：autoresearch 的"val_bpb 改善 → keep"本质上是一个测试门。两者都是"测试门控编排"，只是 autoresearch 的测试是 ML 指标而不是单元测试
- 关联 `analysis/simon-willison-code-is-cheap.md`："代码现在很便宜"的论点在 autoresearch 里走到极端：agent 每 5 分钟写一个版本的 train.py，边际成本接近零，所以可以探索人类不会手动尝试的奇怪想法

---

## 衍生项目想法

### 想法 1：autoresearch 通用化——任意 Python 项目的自主优化循环

**来源组合**：[autoresearch 的 git ratchet + program.md 模式] + [mini_symphony.py 的任务编排]

**为什么有意思**：autoresearch 的模式是通用的——"修改 X 文件 → 跑指标 → 保留或回滚"不依赖 ML。可以用于：优化 web server 的 latency、跑 benchmark suite 优化算法实现、A/B test 不同 prompt 策略的胜率

**最小 spike**：把 autoresearch 的 `program.md` 改成针对一个 Python 排序算法的基准测试（`time python sort.py`），让 agent 尝试不同实现，5 分钟 → 胜出版本

**潜在难点**：指标测量的噪声（5 分钟 ML 训练的 val_bpb 相对稳定，但 latency benchmark 可能噪声大）

---

### 想法 2：program.md 版本控制 + 两级结果追踪

**来源组合**：[autoresearch 的两级优化（program.md vs train.py）] + [analysis/simon-willison-hoard-things.md 的囤积体系]

**为什么有意思**：目前 program.md 的迭代历史没有被系统追踪。把 program.md 的每次修改和对应那轮 autoresearch 的最终 results.tsv 汇总关联，就得到了一个"研究方法论"的演化史——哪条 program.md 指令带来了最大的 val_bpb 提升

**最小 spike**：在 autoresearch 结束时，把当前 program.md 的 hash + 本轮最佳 val_bpb 追加到 `program_results.log`，形成 `(program_version, best_val_bpb)` 时间序列

**潜在难点**：单次 autoresearch run 的结果受随机种子和 GPU 状态影响，需要多次跑才能统计显著

---

### 想法 3：session_tracker + autoresearch 融合——上下文崩溃后继续实验

**来源组合**：[autoresearch 的长时间自主运行需求] + [python/session_tracker.py 的 PreCompact 快照]

**为什么有意思**：100 次实验 ≈ 500 分钟训练 log + 代码修改 log，context 必然压缩多次。目前 autoresearch 没有任何机制在 context reset 后恢复状态。加入 session_tracker，在每次实验后写入结构化快照，agent 恢复时能知道"我已经跑了 47 个实验，当前最优 0.9321，最近 3 次方向是增大 batch size"

**最小 spike**：在 autoresearch 的 `program.md` 里加一条：每次实验后把 results.tsv 的 top-3 行 + 当前 val_bpb + 实验方向写入 `session.md`；在 CLAUDE.md 里加 PostCompact hook 读取 session.md

**潜在难点**：需要 agent 在实验循环内额外维护 session.md，增加了 program.md 的复杂度
