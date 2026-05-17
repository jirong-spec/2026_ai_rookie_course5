# Lab 5：貼近實務的語料與混合式 Graph RAG

## 三元組通常從哪裡來？

在實務上，**結構化三元組（或圖邊）常見來源包括**：

1. **從非結構化文本抽取**：規則、模板、資訊抽取模型或 LLM，從文件、郵件、網頁等產出 `(頭實體, 關係, 尾實體)`，再經人工校對或品質管線寫入圖譜。  
2. **從已結構化系統匯入**：ERP、CRM、主資料（MDM）、資料庫表轉換。  
3. **人工編修**：知識工程師或領域專家直接維護。

因此「**語料（corpus）→ 三元組**」是**常見路徑之一**，但不是唯一路徑。本 Lab 以 **`extract_triples_from_corpus.py`** 示範用 **LLM 從 corpus 自動抽取**（再經 `parse()` 過濾），並保留**人工校對**與與參考答案比對的練習。

## 目標

1. 以程式 **`extract_triples_from_corpus.py`** 讀取 **`docs/corpus/`**（會議、wiki、郵件、工單、簡報摘錄），透過 **LLM** 抽取事實，產生與 **Lab 2 相同文法**的 **`docs/kg_triples.txt`**；腳本會用與 `ingest_graph` 相同的規則**過濾**無法解析的行。  
2. （選做）人工校對或手改 `kg_triples.txt`，再 **`ingest_graph.py`** 匯入 Neo4j、**`build_vector_index.py`** 建索引、**`graph_rag.py`** 做混合式問答，觀察抽取漏／錯時對答案的影響。

## 資料結構

| 路徑 | 用途 |
|------|------|
| `docs/corpus/*.txt` | **原始敘事資料**（繁中為主，專有名詞英文拼法與參考答案一致） |
| `extract_triples_from_corpus.py` | 讀取 corpus → 呼叫本機 LLM（與其他 Lab 相同 vLLM 設定）→ 寫入 `kg_triples.txt` |
| `triples_parse.py` | 與 Lab 2 相同的五種句式之 `parse()`，供 ingest 與抽取腳本共用（抽取腳本**不**需連 Neo4j） |
| `docs/kg_triples.txt` | **抽取結果**（可人工增刪）；以 `#` 開頭的行匯入時會略過 |
| `docs/kg_triples.template.txt` | 五種合法句式說明（對照 Lab 2 正則） |
| `docs/reference/kg_triples.answer.txt` | **參考答案**（教師／自評用；可不發給學員） |

## 與前序 Lab 的關係

- **Lab 1～4** 仍建議用 `lab1/docs/data.txt` 對照；本 Lab **不覆寫** `lab1/chroma_store`。  
- **`ingest_graph.py` 會清空整個 Neo4j**。還原 Lab 2 小圖：在 **lab2** 重新執行該 Lab 的 `ingest_graph.py`（需有 `lab2/docs/data.txt`）。

## 前置條件

- 已完成 Lab 2（懂三元組文法與 Neo4j 匯入概念）與 Lab 4（混合 RAG 流程）
- Neo4j、vLLM 已啟動；已安裝 `langchain-experimental`、`sentence-transformers` 等依賴

## 建議操作順序（學員）

```bash
cd lab5
# 0) 確認本機 vLLM 已啟動（與 Lab 0／1 相同 OPENAI_API_BASE）
# 1) 從語料自動產生三元組（會覆寫 docs/kg_triples.txt）
python extract_triples_from_corpus.py
# 僅預覽、不寫檔：python extract_triples_from_corpus.py --dry-run
# 2) 匯入 Neo4j
python ingest_graph.py
# 3) 向量索引（僅讀 corpus）
python build_vector_index.py
# 4) 混合式問答
python graph_rag.py
```

若略過步驟 1 直接執行 `ingest_graph.py`，且 `kg_triples.txt` 僅有註解，程式會**清空圖**並警告——可用來討論「空圖譜時 RAG 行為」。

## 可嘗試的問題（範例）

| 問題方向 | 說明 |
|----------|------|
| 供應鏈 | 誰供應 SmartBatteryPack 給 ZenithAuto？（考驗你是否從語料抽出正確 supplies） |
| 人事與負責人 | Eva 在哪間公司？誰負責 NanoSensor？ |
| 聯盟關係 | Acme 與哪些公司是 partners_with？ |
| 自我檢核 | 與 `reference/kg_triples.answer.txt` 比對你漏寫或寫錯的邊 |

## 實作狀態

Lab 5 共 5 個 TODO，目前進度：

### `extract_triples_from_corpus.py`

| TODO | 完成內容 | 狀態 |
|------|---------|------|
| TODO 1 | `EXTRACTION_PROMPT`：角色設定為知識圖譜抽取助手，列出五種句式與中文關鍵詞對應，要求只輸出純英文句子 | ✅ 完成 |
| TODO 2 | `filter_parsable()`：呼叫 `parse()` 判斷合法性，去重後回傳 `(good, bad)` | ✅ 完成 |

### `build_vector_index.py`

| TODO | 完成內容 | 狀態 |
|------|---------|------|
| TODO 3 | `SemanticChunker(emb, percentile, 90)` → `split_documents()` → `Chroma.from_documents(persist_directory=chroma_store)` | ✅ 完成 |

### `graph_rag.py`

| TODO | 完成內容 | 狀態 |
|------|---------|------|
| TODO 4 | `candidate_entities(k=6)`：向量搜尋 + 正則抽實體，回傳前 8 個 | ✅ 完成 |
| TODO 5 | `graph_expand()`：Cypher `MATCH p=(n)-[*1..{hop}]-(m) WHERE n.name IN $ents RETURN p LIMIT 120` | ✅ 完成 |

## 作業建議

1. **對齊參考答案**：將 `extract_triples_from_corpus.py` 產生的 `kg_triples.txt` 與 `reference/kg_triples.answer.txt` 比對（可用 diff）；列出**漏抽**與**多抽**各至少一則，並說明可能原因（提示詞、模型、語意模糊）。  
2. **改 prompt**：調整腳本中的抽取提示詞後重新執行，觀察漏抽／多抽是否改善。  
3. **錯誤注入（選做）**：手動刪改一條 `supplies` 後匯入，用 `graph_rag.py` 提問，觀察錯誤如何影響答案。  
4. **盤點語料雜訊**：舉三種不利自動抽取的寫法，並提出一種前處理或後處理（例如僅保留通過 `parse()` 的行——本腳本已示範）。  
5. **思考題**：若要把抽取結果寫入**正式**圖譜，除了 `parse()` 過濾外，你還會加哪些**人審或規則驗證**？

## 延伸（選做）

- 改為**分段**呼叫 LLM（依檔案或依 chunk），再合併去重，與「一次餵全文」比較品質與成本。  
- 在 **corpus** 新增段落後重跑 `extract_triples_from_corpus.py`，檢查圖譜與 RAG 是否跟著更新。
