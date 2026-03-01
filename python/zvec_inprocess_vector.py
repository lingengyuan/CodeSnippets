# =============================================================================
# 名称: zvec In-Process Vector DB
# 用途: in-process 向量库，零服务依赖，支持混合检索（语义+结构化过滤）
# 依赖: pip install zvec sentence-transformers
# 适用场景: 本地 RAG、CLI 工具嵌入搜索、单测 mock 向量库、边缘设备
# 日期: 2026-03-01
#
# 核心卖点：不是"又一个向量数据库"，而是 in-process——像 SQLite 一样直接嵌进进程，
# 没有服务、没有网络、没有 Docker。
# - Dense + Sparse 同时支持，一次 query 调用就能做混合检索
# - 基于阿里巴巴 Proxima，生产级 ANN 引擎，10M 向量毫秒级
#
# 一句话：演示了 zvec 作为零依赖 in-process 向量库，同时做向量相似度检索和结构化字段过滤。
#
# 延伸场景:
#   - CLI 内嵌语义搜索：历史命令/笔记向量化，grep 升级为语义 grep，零服务启动
#   - 单测 mock 向量数据库：测 RAG pipeline 不需要起 Qdrant/Milvus，in-process 即用即毁
#   - 一次性去重：百万级文本去重，脚本跑完数据库随进程消失
#   - Edge 设备本地 RAG：树莓派、工控机，不用联网，向量库跑在本地
#   - Embedding cache：同一 query 的 embedding 做 ANN 找历史近似 query，省掉重复调用
#   - Jupyter Notebook 实验性向量搜索：不需要 restart server，cell 重跑即重建
#   - 当 feature store 用：tabular 数据转向量，进程内做相似样本检索
# =============================================================================

import zvec

# --- 1. 定义 schema，支持 payload 字段用于过滤 ---
schema = zvec.CollectionSchema(
    name="docs",
    vectors=zvec.VectorSchema("emb", zvec.DataType.VECTOR_FP32, 4),
    fields=[
        zvec.FieldSchema("category", zvec.DataType.STRING),
        zvec.FieldSchema("score",    zvec.DataType.INT64),
    ]
)

col = zvec.create_and_open(path="/tmp/zvec_demo", schema=schema)

# --- 2. 插入带 payload 的文档 ---
col.insert([
    zvec.Doc(id="a", vectors={"emb": [0.1, 0.9, 0.1, 0.2]},
             fields={"category": "code",  "score": 90}),
    zvec.Doc(id="b", vectors={"emb": [0.8, 0.1, 0.2, 0.3]},
             fields={"category": "docs",  "score": 70}),
    zvec.Doc(id="c", vectors={"emb": [0.1, 0.8, 0.3, 0.1]},
             fields={"category": "code",  "score": 60}),
    zvec.Doc(id="d", vectors={"emb": [0.5, 0.5, 0.5, 0.5]},
             fields={"category": "docs",  "score": 85}),
])

# --- 3. 纯向量搜索 ---
results = col.query(
    zvec.VectorQuery("emb", vector=[0.1, 0.85, 0.2, 0.15]),
    topk=3
)
print("向量搜索:", results)

# --- 4. 混合搜索：向量 + 结构化过滤（只看 code 类，score > 70）---
results_filtered = col.query(
    zvec.VectorQuery("emb", vector=[0.1, 0.85, 0.2, 0.15]),
    topk=3,
    filter="category = 'code' AND score > 70"
)
print("混合搜索:", results_filtered)
