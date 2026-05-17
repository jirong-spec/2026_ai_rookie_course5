# 2026 AI Rookie Course 5 — Knowledge Graph RAG

從 Vector RAG 到具備 Guardrails 的 Graph RAG，六個 Lab 循序建構企業級知識圖譜問答系統。

## 系統需求

| 服務 | 啟動指令 | 連線位址 |
|------|---------|---------|
| Neo4j | `docker compose -f docker-compose-neo4j.yaml up -d` | bolt://localhost:7687（帳號 `neo4j` / 密碼 `password123`）|
| vLLM | `docker compose -f docker-compose-vllm.yaml up -d` | http://localhost:8299/v1 |

模型：`Qwen2.5-3B-Instruct`
Embedding：`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`

## Lab 一覽

| Lab | 主題 | 核心技術 | 狀態 |
|-----|------|---------|------|
| [Lab 0](lab0/README.md) | 環境驗證 | vLLM + Neo4j 連線測試 | ✅ 完成 |
| [Lab 1](lab1/README.md) | Vector RAG | SemanticChunker → ChromaDB → RetrievalQA | ✅ 完成 |
| [Lab 2](lab2/README.md) | Graph 建置 | 正則解析三元組 → Neo4j MERGE | ✅ 完成 |
| [Lab 3](lab3/README.md) | Graph 查詢 | LLM 實體抽取 + 2-hop Cypher + 規則回答 | ✅ 完成 |
| [Lab 4](lab4/README.md) | Graph RAG | 向量搜尋候選實體 → 圖譜展開 → LLM 生成 | ✅ 完成 |
| [Lab 5](lab5/README.md) | Hybrid Graph RAG | LLM 抽取三元組 + 多語料向量索引 | ✅ 完成 |
| [Lab 6](lab6/README.md) | Guardrailed RAG | 四道防護：注入偵測、主題過濾、證據充足、事實查核 | ✅ 完成 |

## 架構總覽

```
使用者問題
    │
    ├─ [Lab 6] Input Guard
    │   ├─ #1 注入偵測（正則 10 條）
    │   └─ #2 主題過濾（LLM-as-judge）
    │
    ├─ 向量檢索（ChromaDB）
    │   └─ [Lab 1] SemanticChunker 索引（lab1/chroma_store）
    │
    ├─ 候選實體提取（正則 [A-Z][A-Za-z]+）
    │
    ├─ 圖譜展開（Neo4j）
    │   └─ [Lab 2/5] MERGE 匯入的三元組
    │   └─ Cypher MATCH (n)-[*1..2]-(m) LIMIT 100
    │
    ├─ [Lab 6] Retrieval Guard
    │   └─ #3 證據充足性（三元組數量）
    │
    ├─ LLM 生成答案（Qwen2.5-3B via vLLM）
    │
    └─ [Lab 6] Output Guard
        └─ #4 事實查核（LLM-as-judge）
```

## 快速開始

```bash
# 1. 啟動服務
docker compose -f docker-compose-neo4j.yaml up -d
docker compose -f docker-compose-vllm.yaml up -d

# 2. 驗證環境
cd lab0 && python test.py

# 3. 建立向量索引（其他 Lab 共用）
cd ../lab1 && python vector_rag.py

# 4. 匯入知識圖譜
cd ../lab2 && python ingest_graph.py

# 5. 執行 Guardrailed RAG（最終版本）
cd ../lab6 && python guardrailed_rag.py
```

## Lab 依賴關係

```
Lab 0
 └─ Lab 1（建立 lab1/chroma_store）
     └─ Lab 2（匯入 Neo4j 圖譜）
         ├─ Lab 3（圖譜查詢）
         ├─ Lab 4（Graph RAG，依賴 Lab 1 + Lab 2）
         │   └─ Lab 6（Guardrailed RAG，依賴 Lab 1 + Lab 2）
         └─ Lab 5（Hybrid RAG，建立獨立 lab5/chroma_store）
```

## 知識圖譜關係類型

| 句式 | 關係 | 範例 |
|------|------|------|
| `X works_at Y` | WORKS_AT | Alice works_at Acme. |
| `X produces Y` | PRODUCES | Acme produces RocketSkates. |
| `X partners_with Y` | PARTNERS_WITH | Acme partners_with BoltCorp. |
| `X supplies Y to Z` | SUPPLIES | BoltCorp supplies TurboMotor to Acme. |
| `X leads Y` | LEADS | Carol leads TurboMotor. |
| `X manages Y` | MANAGES | Dave manages Bob. |

## 實作狀態

所有 Lab（0–6）的 TODO 均已完成。
