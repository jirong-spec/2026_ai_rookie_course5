# Lab 1：向量 RAG（Vector RAG）

## 目標

建立一個基礎的 **Retrieval-Augmented Generation (RAG)** 系統，透過向量檢索從文件中找出與問題相關的段落，再交由 LLM 生成答案。

## 核心概念

```
使用者問題
    ↓
Embedding 模型 → 向量化
    ↓
向量資料庫 (Chroma) → 相似度搜尋 → 取出相關文件片段
    ↓
LLM 根據檢索到的片段生成答案
```

## 語意切分（SemanticChunker）

本課程系列統一使用 **`SemanticChunker`**（`langchain_experimental`）：以與向量索引相同的 embedding 模型，比對相鄰片段的語意差異，在語意轉折處切分，讓每個 chunk 較接近完整敘述，後續 Lab 4 的向量→圖譜流程也沿用同一套 `lab1/chroma_store` 索引。

請先安裝：`pip install langchain-experimental`（並具備與 `HuggingFaceEmbeddings` 相關的依賴，例如 `sentence-transformers`）。

### SemanticChunker 參數說明

```python
from langchain_experimental.text_splitter import SemanticChunker

splitter = SemanticChunker(
    embeddings,                        # Embeddings 物件（例如 HuggingFaceEmbeddings 實例）
    breakpoint_threshold_type="...",   # 斷點判斷方式（見下表）
    breakpoint_threshold_amount=90,    # 門檻值（搭配 type 使用）
)
```

| 參數 | 型別 | 說明 |
|------|------|------|
| `embeddings` | `Embeddings` | 用來計算語意相似度的 embedding 模型實例 |
| `breakpoint_threshold_type` | `str` | 斷點策略：`"percentile"`（百分位數）、`"standard_deviation"`（標準差）、`"interquartile"`（四分位距）、`"gradient"`（梯度） |
| `breakpoint_threshold_amount` | `float` | 門檻值。以 `"percentile"` 為例，`90` 表示只在語意差異超過第 90 百分位的位置切分 |

### 使用範例

```python
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_experimental.text_splitter import SemanticChunker

emb = HuggingFaceEmbeddings(model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")

splitter = SemanticChunker(
    emb,
    breakpoint_threshold_type="percentile",
    breakpoint_threshold_amount=90,
)

# docs 是由 TextLoader 載入的 Document 列表
splits = splitter.split_documents(docs)
print(f"切成 {len(splits)} 個 chunk")
```

> **提示**：`breakpoint_threshold_amount` 數值愈高，切分門檻愈嚴格 → 每塊愈長、chunk 數愈少。可嘗試 80～95 觀察差異。

## 資料檔案 — `docs/data.txt`

包含一段以自然語言撰寫的企業知識描述，涵蓋人員任職、公司產品、合作關係與供應鏈等資訊。這些非結構化文字正是向量 RAG 最典型的處理對象。

## 程式說明 — `vector_rag.py`

| 步驟 | 程式碼區段 | 說明 |
|------|-----------|------|
| 1 | `TextLoader` + `SemanticChunker` | 載入 `docs/data.txt`，依語意斷點切分 |
| 2 | `HuggingFaceEmbeddings` + `Chroma` | 使用多語言模型將文字轉為向量，存入 `chroma_store/` |
| 3 | `RetrievalQA.from_chain_type` | 建立 RAG Chain：檢索器取出前 4 筆相關片段，LLM 根據這些片段回答問題 |
| 4 | `while True` 互動迴圈 | 使用者可持續提問，直到按 Enter 離開 |

## 執行方式

```bash
cd lab1
python vector_rag.py
```

## 預期行為

程式啟動後會建立向量索引（首次較慢），之後進入互動問答模式。可嘗試的問題：

- `Alice 在哪裡工作？`
- `Acme 生產什麼？`
- `誰負責 TurboMotor？`

## 實作狀態

`vector_rag.py` 的 3 個 TODO 已全數完成：

| TODO | 完成內容 | 狀態 |
|------|---------|------|
| TODO 1 | 建立 `SemanticChunker(emb, breakpoint_threshold_type="percentile", breakpoint_threshold_amount=90)` 並呼叫 `split_documents(docs)` | ✅ 完成 |
| TODO 2 | `Chroma.from_documents(splits, emb, persist_directory="chroma_store")` | ✅ 完成 |
| TODO 3 | `RetrievalQA.from_chain_type(llm, retriever=vectordb.as_retriever(k=4), chain_type="stuff")` | ✅ 完成 |

## 作業

完成上述 TODO 並確認程式可執行後，請繼續以下練習：

1. **調參實驗**：修改你在 TODO 1 填入的 `breakpoint_threshold_amount`（嘗試 80、90、95），觀察印出的 chunk 數量與回答品質變化。思考：語意切分與「固定字元長度」切分各適合什麼情境？
2. **新增資料**：在 `docs/data.txt` 新增一段描述（例如「Dave 任職於 BoltCorp，負責品管部門。」），重新執行程式，確認新資料能被正確檢索。
3. **觀察限制**：嘗試問一個**需要跨多筆資料推理**的問題（例如「Acme 的合作夥伴供應什麼零件？」），觀察純向量 RAG 是否能正確回答。記錄你的觀察，這將與後續 Graph RAG 做比較。
4. **思考題**：向量 RAG 的檢索方式是基於「語意相似度」，這在什麼情境下可能會失敗？
