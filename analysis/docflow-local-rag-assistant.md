# DocFlow：本地 PDF 知识助手深度分析

> 来源: ~/Projects/docflow/ (private, https://github.com/lingengyuan/docflow)
> 日期: 2026-03-22
> 类型: 个人项目 Phase 6 完成

---

## 项目概况

DocFlow 是一套完全本地运行的多格式文档知识库系统（RAG），支持 PDF（扫描件 OCR）、Markdown、TXT、DOCX、图片（VLM 描述），数据不出机器。目标平台：M5 Mac 32GB，技术路线刻意选择"小而快"的组合以控制内存。

**核心技术栈**：
- Embedding: Qwen3-Embedding-0.6B（CPU，sentence-transformers）
- Reranker: Qwen3-Reranker-0.6B（MLX，~26x 提速）
- LLM: mlx-community/Qwen3-4B-4bit（MLX in-process，~2.3GB Metal）
- VLM: mlx-community/Qwen2.5-VL-7B-Instruct-4bit（按需加载，~4GB Metal）
- 向量库: Qdrant（Docker 服务，1024 维 COSINE）
- 全文检索: SQLite FTS5（jieba 预分词，取代 BM25 pickle）
- 多格式解析: ParserRegistry Protocol（PDF/MD/TXT/DOCX/图片）
- 检索路由: QueryRouter（规则驱动，~35 行）
- OCR: glm-ocr via Ollama

---

## 9 维度提取

### 🟢 可复用代码

**QueryRouter（~35 行规则引擎）**：
```python
class QueryRouter:
    _KEYWORD_PATTERNS = [
        re.compile(r'"[^"]+"'),        # 引号短语
        re.compile(r'\b\d{4}[-/]\d{1,2}'),  # 日期格式
        re.compile(r'\.\w{2,4}\b'),    # 文件扩展名
        re.compile(r'[A-Z]{2,}\d+'),   # 编号模式
    ]
    @classmethod
    def classify(cls, query):
        signals = sum(1 for p in cls._KEYWORD_PATTERNS if p.search(query))
        if signals >= 2:
            return {"bm25_weight": 2.0, "vec_weight": 0.5}
        elif len(query) > 20 and signals == 0:
            return {"bm25_weight": 0.5, "vec_weight": 2.0}
        else:
            return {"bm25_weight": 1.0, "vec_weight": 1.0}
```

**FTS5 中文检索模式（jieba 预分词 + OR 查询）**：
```python
def _fts_tokenize(text):
    import jieba
    return " ".join(t for t in jieba.cut(text.lower()) if t.strip())

# 检索时
tokens = [t for t in jieba.cut(query.lower()) if t.strip()]
fts_query = " OR ".join(f'"{t}"' for t in tokens)
store.search_fts(fts_query, limit=top_k)
```

**FTS5 subquery 稳定排名**：
```python
# 直接 JOIN 时 FTS5 rank 不稳定，用 subquery 固定
sql = """
    SELECT c.qdrant_id, fi.file_name, fts.score
    FROM (
        SELECT rowid, -rank AS score
        FROM chunks_fts
        WHERE chunks_fts MATCH ?
        ORDER BY rank LIMIT ?
    ) fts
    JOIN chunks c ON c.id = fts.rowid
    JOIN files fi ON fi.id = c.file_id
"""
```

**MLX 单线程约束（共享 Executor）**：
```python
# 所有 MLX 推理必须通过 ml_executor 串行
ml_executor = ThreadPoolExecutor(max_workers=1)

# Embedding 用 CPU 避免 PyTorch MPS + MLX 双 Metal 运行时内存爆炸
pipeline.embedder._model = retriever._embed_model  # 共享实例
```

---

### 🏗️ 技术模式

**模式 1：预索引分词 + 查询时重分词 = 中文 FTS5**
标准 FTS5 不支持中文（无空格分词）。解决：ingest 时 jieba 切词存 `tokenized_text`；检索时同样 jieba 切词构造 `"tok1" OR "tok2"` 查询。rowid == chunks.id 设计使 O(1) 删除成为可能。

**模式 2：FileParser Protocol + ParserRegistry**
```python
class FileParser(Protocol):
    def parse(self, path: Path) -> ParsedDocument: ...

class ParserRegistry:
    @classmethod
    def from_config(cls, cfg) -> "ParserRegistry": ...
    def supports(self, path: Path) -> bool: ...
    def resolve(self, path: Path) -> FileParser: ...
```
新增格式只需实现 Protocol，无需改核心流程。典型 OCP。

**模式 3：RRF 加权融合（Reciprocal Rank Fusion + 动态权重）**
两路检索（向量 + FTS5）独立排名 → RRF 融合，QueryRouter 决定各路权重。向量路捕捉语义，FTS5 路捕捉精确关键词，两路互补。

**模式 4：FTS5 backfill 自动迁移**
旧 DB 无 FTS5 数据时，启动时自动 backfill：从 Qdrant 取 text payload 分批处理，jieba 分词后写入。老数据无缝升级，不需要手动 re-ingest。

---

### 📦 工具与依赖

| 工具 | 版本/说明 | 用途 |
|-----|----------|------|
| mlx-lm | Apple MLX | Reranker / LLM 推理，比 PyTorch MPS 快 ~26x |
| mlx-vlm | Apple MLX | VLM（图片描述），与 LLM 共用 ml_executor |
| sentence-transformers | — | CPU Embedding，避免 Metal 内存冲突 |
| jieba | — | 中文分词，用于 FTS5 预索引 |
| Qdrant | Docker | 向量库，COSINE，1024 维 |
| SQLite FTS5 | stdlib | 全文检索，取代 BM25 pickle |
| pillow-heif | — | HEIC → PNG 转换，送 VLM |
| python-docx | — | DOCX 解析 |
| watchdog | — | 文件系统监控，多目录 + 扩展名过滤 |

---

### 🧠 心智模型

**"小模型 + 快推理 + 本地优先"三角框架**
每个组件都在"参数量最小化，推理速度最大化，数据不出机器"三个约束下选型：Qwen3-0.6B 系列而非 7B，MLX 而非 PyTorch，SQLite 而非 Elasticsearch，CPU Embedding 而非 GPU。

**"分词是数据，查询是视图"**
中文检索的本质问题：FTS5 按空格分词，但中文无空格。解决方案是把"分词结果"作为一种数据（`tokenized_text` 字段）在 ingest 时存储，而不是在查询时即时处理。这把分词成本从 O(每次查询 × 文档数) 降到 O(ingest 一次)。

**"信号驱动的路由而非模型驱动"**
QueryRouter 用 4 个正则表达式判断 query 类型，~35 行，零额外推理成本。与其训练一个路由分类器，不如提炼出关键信号（引号=精确查找，日期=时序查找，长语句无信号=语义查找）。

---

### ⚖️ 权衡取舍

| 决策 | 选择 | 放弃 | 理由 |
|-----|------|------|------|
| 向量库 | Qdrant (Docker) | zvec / ChromaDB | 生产级 ANN，支持 payload 过滤 |
| Embedding 设备 | CPU | MPS | 避免 PyTorch MPS + MLX 双 Metal 内存爆炸 |
| 全文索引 | SQLite FTS5 | Elasticsearch / Whoosh | 零服务依赖，rowid 设计简洁 |
| LLM 推理 | MLX in-process | Ollama | 无 IPC 开销，Metal 共享内存快 |
| VLM | Qwen2.5-VL-7B-4bit | Qwen2.5-VL-3B-4bit | 3B 对复杂图表描述不够，7B 仍在 32GB 内 |
| 分词策略 | jieba 预分词存 DB | 查询时实时分词 + 全表扫描 | 惰性计算 vs 摊销成本 |

---

### ⚠️ 反模式与陷阱

1. **FTS5 rank 在 JOIN 中不稳定**：直接 `JOIN chunks_fts ON ...` 后 ORDER BY rank 结果不可预测。必须用 subquery 先固定排名再 JOIN。

2. **PyTorch MPS + MLX 双 Metal 运行时**：同时加载会导致统一内存爆炸（实测 32GB 机器 OOM）。Embedding 必须强制 `device="cpu"`，并共享单一模型实例。

3. **lazy-load 绕过时忘记 `_ensure_collection()`**：直接访问 `embedder._model` 跳过了懒加载逻辑，Qdrant collection 未初始化会报错。

4. **FTS5 backfill 依赖 Qdrant 的 text payload**：如果 Phase 8 实现"Qdrant payload 瘦身（移除 text 字段）"，backfill 逻辑必须同步改为从 SQLite chunks 表取 text，否则迁移脚本失效。

5. **MLX ThreadPoolExecutor max_workers=1 是硬约束**：VLM、LLM、Reranker 三者不能并发，必须全走同一个 Executor。如果新增推理路径忘记走 Executor 会导致 Metal 内存竞争。

---

### 💡 非显见洞见

1. **FTS5 tokenize 策略是中文 RAG 的关键分叉点**：英文 RAG 直接用 FTS5 `porter` tokenizer 就能工作；中文必须在 ingest 时 jieba 预分词，否则查询命中率接近零。这个差异在英文 RAG 教程中完全不可见。

2. **QueryRouter 的实质是"查询意图的显式编码"**：大多数 RAG 系统隐式假设"所有查询都是语义查询"。DocFlow 把查询意图显式建模（精确/语义/混合），用规则而非神经网络，几乎零成本但显著提升精确查询的准确率。

3. **VLM 的"安全开关"设计**：`vlm.enabled: false` 允许在模型未下载时正常运行，这个设计解耦了"功能配置"和"模型存在性"。很多本地 AI 应用把两者耦合，导致模型文件不完整时整个应用崩溃。

---

### ❓ 开放问题

1. **Phase 8（Qdrant payload 瘦身）**：移除 text 字段后，FTS5 backfill 从哪里取 text？SQLite chunks 表此时还没有 text 字段（只有 tokenized_text）。需要提前规划数据迁移路径。

2. **中文 FTS5 的模糊搜索**：当前实现只支持精确 jieba token 匹配（`"tok1" OR "tok2"`）。用户拼音输入、简繁混用、OCR 错字等场景怎么处理？

3. **Qdrant vs 零服务向量库**：目前需要 Docker 运行 Qdrant。对于轻量部署场景（如共享给家人使用），能否换成 in-process 方案？

4. **多用户 / 多设备同步**：目前是单机单用户，如果需要在 Mac + iPad 间同步知识库，iCloud Drive + SQLite WAL 是否足够？还是需要引入同步层？

---

### 🚀 衍生想法种子（待 Step 3 深化）

1. FTS5 三层模糊搜索移植（来自 `fts5_fuzzy_search.py`）
2. Qdrant → zvec 替换（来自 `zvec_inprocess_vector.py`）
3. 查询历史 + 会话持续性（来自 `session_tracker.py`）

---

## Step 3：深度推理

### 3A：蕴含链

**洞见 1：QueryRouter 用规则代替分类模型**
→ 所以：规则的边界条件是可解释的（"包含引号就是精确查询"），用户可以预测并利用系统行为
→ 所以：用户可以主动在 query 中加引号来强制精确模式，这是隐性的"查询语法"
→ 因此可以：在 UI 提示用户"加引号可以精确匹配"，把规则暴露为功能而不是内部实现

**洞见 2：jieba 预分词存 DB = 把计算摊销到 ingest**
→ 所以：查询延迟与文档数量无关（只取决于 FTS5 索引大小，而非实时分词成本）
→ 所以：即使知识库增长到 10 万个 chunks，查询速度也不会因分词变慢
→ 因此可以：这个模式可以推广到任何需要"昂贵预处理 + 快速查询"的场景（如实体识别结果缓存）

**洞见 3：MLX max_workers=1 的串行约束**
→ 所以：Reranker、LLM、VLM 三者无法并发，这是硬件架构决定的，不是设计缺陷
→ 所以：优化方向只能是"减少每次推理的时间"（量化、更小的模型），而非"并发多路推理"
→ 因此可以：未来如果 Apple 开放多 GPU 上下文，可以解除这个约束，但短期内不值得设计为并发

---

### 3B：隐含假设

- **假设：Qdrant 始终可达**。FTS5 backfill 依赖 Qdrant 的 text payload，如果 Qdrant 服务挂了，backfill 静默失败，旧 chunks 永远进不了 FTS5 索引。这在单机场景基本不发生，但在容器化部署时是真实风险。

- **假设：jieba 分词对领域词汇足够准确**。专业文档（法律、医疗、技术手册）中的领域术语可能被 jieba 错误切分（如"布隆过滤器"被切成"布隆 / 过滤 / 器"），导致精确查询失败。

- **假设：用户查询语言和文档语言一致**。当前没有跨语言检索支持（英文 query 找中文文档）。Qwen3-Embedding 支持多语言，但 FTS5 层的 jieba 分词是纯中文的。

---

### 3C：反事实分析

**为什么选 Qdrant 而不是 zvec（in-process）？**

决策逻辑：Qdrant 提供生产级 ANN（基于 HNSW），支持 payload 过滤，有成熟的 Python client。zvec 基于 Proxima，同样生产级，但 Python binding 还不够成熟。

**zvec 在什么场景反而更优**：
- 不想依赖 Docker 的场景（嵌入式部署、给非技术用户使用）
- 知识库较小（< 5 万 chunks）且不需要 payload 过滤
- 测试/开发阶段（in-process，即用即毁，无状态残留）

**为什么选 MLX 而不是 llama.cpp？**
MLX 与 Apple Silicon 的统一内存架构深度整合，可以与 Qdrant 的 Metal 加速共用内存带宽而不互相抢占。llama.cpp 的 Metal 后端虽然快，但与 Python 生态集成不如 mlx-lm 顺畅。

---

### 3D：组合生成

**组合 1：`fts5_fuzzy_search.py` × DocFlow FTS5**

现状：DocFlow FTS5 只支持精确 jieba token 匹配。用户打错字、OCR 错误字符、简繁混用都会导致 FTS5 层零结果。

组合：在 `retriever._fts_search()` 的 FTS5 query 构建阶段，引入三层降级：
1. 精确 jieba tokens（当前实现）
2. 针对每个 token 用 trigram FTS5 子表做子串匹配
3. Levenshtein 纠错后重查

价值：OCR 文档质量参差不齐，扫描件 OCR 错字率可能高达 5%。精确匹配会完全错过这些 chunks；trigram + Levenshtein 可以显著提升召回率。

最小 spike：在 `DocStore._init_db()` 中添加 `chunks_fts_trigram` trigram 子表，在 `_fts_search()` 中实现两层降级（先精确，再 trigram），跳过 Levenshtein（对中文效果有限）。预计 ~80 行。

---

**组合 2：`zvec_inprocess_vector.py` × DocFlow Qdrant**

现状：DocFlow 依赖 Docker 运行 Qdrant，增加了部署复杂度（需要 `docker compose up`）。

组合：增加 `vector_backend: qdrant | zvec` 配置项，zvec 模式下直接 in-process，无需 Docker。`Embedder` 抽象为 `VectorBackend` Protocol，实现 `QdrantBackend` 和 `ZvecBackend`。

价值：把 DocFlow 从"需要 Docker 才能运行"变成"双击即用"。对于想把 DocFlow 分享给家人/同事的场景，消除 Docker 依赖是关键门槛。

最小 spike：实现 `ZvecBackend`，只需 `upsert(ids, vectors, payloads)`、`search(query_vec, top_k)` 两个接口，约 60 行。在 config.yaml 加 `vector_backend: zvec`，测试 end-to-end ingest + retrieve。

---

**组合 3：`session_tracker.py` × DocFlow 查询历史**

现状：DocFlow 没有查询历史。每次启动是全新状态，用户无法回顾之前的对话、找到之前问过的文档段落。

组合：在 `app.py` 的每次 `/api/query` 后，用 `SessionTracker.capture("queries", query_text)` + `capture("responses", answer_text[:200])` 记录。在前端增加"历史记录"面板，通过 `SessionTracker.search()` 实现查询历史的模糊搜索。

价值：把 DocFlow 从"无状态问答工具"变成"有记忆的知识助手"。用户可以找回上次的问答，避免重复提问。

最小 spike：在 `app.py` 初始化 `SessionTracker(project_root)`，在 `/api/query` 后异步 capture。前端新增 `GET /api/history?q=` 端点，返回匹配历史记录。预计 ~50 行。

---

### 3E：边界与反例

**FTS5 + jieba 方案的边界**：
- **规模**：100 万 chunks 时，jieba 分词后的 FTS5 索引可能超过 1GB，查询速度下降。需要评估是否引入 Rust BM25（DuckDB 或自定义）。
- **语言**：纯英文文档 jieba 分词效果差（会把英文单词切碎），当前 supported_extensions 包含 .md/.txt，这些文件可能是英文内容。需要语言检测 + 分词策略路由。
- **OCR 质量**：低质量扫描件（倾斜、模糊、低分辨率）OCR 错误率高，jieba 精确匹配完全失效。需要 trigram 降级兜底。

**反例场景**：
- 用户上传全英文技术论文（PDF）→ jieba 把英文词切碎 → FTS5 层几乎无效 → 只剩向量检索 → QueryRouter 应检测 query 语言动态调整权重（当前没有）
- 用户问"上次你说的那篇关于 XX 的文章"→ DocFlow 没有对话历史 → 无法回答

---

## 对现有 DocFlow 的优化建议（优先级排序）

### P1：FTS5 Trigram 降级（OCR 容错）

**问题**：扫描件 OCR 错字导致 FTS5 精确匹配失败
**方案**：在 `store.py` 中添加 `chunks_fts_trigram` FTS5 trigram 子表，`_fts_search()` 精确层失败时自动降级到 trigram 子串匹配
**成本**：~80 行，不影响现有接口
**收益**：显著提升扫描件召回率，尤其是技术名词、专有名词

### P2：语言检测 + 分词路由

**问题**：英文文档用 jieba 分词效果差
**方案**：ingest 时用 `langdetect` 检测文档语言；英文文档用 FTS5 porter tokenizer，中文用 jieba 预分词
**成本**：~40 行（新增语言检测 + 条件分词路由），`tokenized_text` 字段语义扩展
**收益**：中英文混合知识库检索质量提升

### P3：查询历史（session_tracker 移植）

**问题**：无查询历史，用户体验割裂
**方案**：移植 `session_tracker.py` 的 SQLite FTS5 事件追踪机制，在 docflow.db 中新增 `query_history` 表 + FTS5 索引
**成本**：~60 行（历史记录 + FTS5 搜索 + API 端点）
**收益**：把 DocFlow 从问答工具变成知识助手

### P4：zvec 向量后端（消除 Docker 依赖）

**问题**：Qdrant 需要 Docker，提升了部署门槛
**方案**：实现 `VectorBackend` Protocol + `ZvecBackend`，config.yaml 新增 `vector_backend` 选项
**成本**：~120 行（后端抽象 + zvec 实现 + 配置路由）
**收益**：Docker-free 模式，降低推广门槛

---

## 总结

DocFlow 的核心设计价值在于：**用最小的服务依赖，实现生产级 RAG**。SQLite FTS5 + Qdrant + MLX 的组合在 M-series Mac 上已经跑通了完整的混合检索闭环。

最值得提炼推广的模式：
1. **jieba 预分词 + FTS5 OR 查询** = 中文 RAG 的标准配件
2. **规则驱动 QueryRouter** = 零成本的检索意图识别
3. **FTS5 rowid == chunks.id** = O(1) 删除的设计技巧

最值得投入的下一步优化：**FTS5 trigram 降级**（P1，最高收益/成本比，直接解决 OCR 文档的核心痛点）。
