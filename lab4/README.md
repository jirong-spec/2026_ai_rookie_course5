# Lab 4：混合式 Graph RAG（Hybrid Graph RAG）

## 目標

結合**向量檢索**與**圖譜擴展**的優勢，建立一個混合式 RAG 系統。先用向量相似度找出候選實體，再到知識圖譜中擴展相關子圖，最後由 LLM 根據圖譜上下文回答問題。

## 向量索引與 Lab 1 一致

向量檢索使用 **Lab 1** 以 **`SemanticChunker`** 建立的 **`lab1/chroma_store/`**（與 `vector_rag.py` 相同 embedding 與切分策略）。請先至少在 Lab 1 執行過一次 `python vector_rag.py` 以產生索引；若修改 `lab1/docs/data.txt` 或切分參數，請在 Lab 1 重新執行以重建索引。

## 核心概念

```
使用者問題："Acme 的供應鏈是怎樣的？"
      ↓
① 向量檢索 (Chroma)
   → 找出語意相關的文件片段
   → 從中提取候選實體：["Acme", "BoltCorp", "RocketSkates"]
      ↓
② 圖譜擴展 (Neo4j)
   → 以候選實體為起點，擴展 1~2 hop 子圖
   → 取得三元組：
     (Acme)-[:PRODUCES]->(RocketSkates)
     (BoltCorp)-[:SUPPLIES]->(Acme)
     (Acme)-[:PARTNERS_WITH]->(BoltCorp)
      ↓
③ LLM 生成答案
   → 根據圖譜三元組，以繁體中文回答
```

## 與前幾個 Lab 的關係

| Lab | 檢索方式 | 限制 |
|-----|---------|------|
| Lab 1 | 純向量檢索（SemanticChunker + Chroma） | 難以處理多跳推理 |
| Lab 3 | LLM 實體抽取 → 圖譜查詢 | 依賴 LLM 抽取品質 |
| **Lab 4** | **向量檢索 → 圖譜擴展** | **結合兩者優勢，更穩健** |

## 程式說明 — `graph_rag.py`

| 步驟 | 函式 | 說明 |
|------|------|------|
| 0 | （啟動時） | 自 `../lab1/chroma_store` 載入與 Lab 1 相同的向量索引 |
| 1 | `candidate_entities()` | 用 Chroma 向量搜尋找出與問題相關的文件片段，以正則從中提取大寫英文詞作為候選實體 |
| 2 | `graph_expand()` | 以候選實體為起點，在 Neo4j 中做 1~2 hop 子圖擴展 |
| 3 | `answer_with_graph()` | 組合子圖三元組為上下文，請 LLM 根據圖譜資訊回答問題 |

## 前置條件

- 已完成 **Lab 1**（已執行 `vector_rag.py`，`lab1/chroma_store/` 存在且為 SemanticChunker 索引）
- 已完成 **Lab 2**（Neo4j 圖譜已匯入）

## 執行方式

```bash
cd lab4
python graph_rag.py
```

## 可嘗試的問題

| 問題 | 預期行為 |
|------|---------|
| Acme 生產什麼？ | 向量檢索找到 Acme → 圖譜確認 PRODUCES 關係 |
| 誰在 BoltCorp 工作？ | 向量檢索找到 BoltCorp → 圖譜找出 WORKS_AT 關係 |
| TurboMotor 的負責人在哪間公司？ | 需要多跳：TurboMotor → Carol → BoltCorp |
| Acme 的供應鏈是怎樣的？ | 向量找到相關實體 → 圖譜擴展出完整供應鏈 |

## 實作狀態

`graph_rag.py` 的 3 個 TODO 已全數完成：

| TODO | 完成內容 | 狀態 |
|------|---------|------|
| TODO 1 | `candidate_entities()`：`similarity_search(k=4)` → 正則 `[A-Z][A-Za-z]+` → `set` 去重 → 前 5 個 | ✅ 完成 |
| TODO 2 | `graph_expand()`：Cypher `MATCH p=(n)-[*1..{hop}]-(m) WHERE n.name IN $ents RETURN p LIMIT 100`，提取三元組字串集合 | ✅ 完成 |
| TODO 3 | `answer_with_graph()` prompt：角色設定為企業知識專家，只依圖譜回答，資訊不足回覆「無足夠資訊」，繁體中文 | ✅ 完成 |

## 作業

完成上述 TODO 並確認程式可執行後，請繼續以下練習：

1. **觀察候選實體**：程式會印出「候選實體」，觀察不同問題產生的候選實體是否合理。目前使用正則抓取「大寫英文詞」作為實體辨識的方式有什麼缺陷？提出至少一種改進方案。
2. **調整參數**：
   - 修改 `candidate_entities()` 中的 `k` 值（向量搜尋回傳數量），觀察對結果的影響。
   - 修改 `graph_expand()` 中的 `hop` 值，觀察子圖大小的變化。
3. **端到端比較**：準備 3 個測試問題，分別在 Lab 1、Lab 3、Lab 4 中執行，製作一張比較表格，包含：
   - 問題內容
   - 各 Lab 的回答
   - 回答是否正確
   - 你的分析（為什麼某個方法表現較好或較差）
4. **進階挑戰**：目前 `candidate_entities()` 使用非常簡易的啟發式方法（大寫開頭）提取實體。嘗試改用 LLM 來抽取實體（參考 Lab 3 的 `extract_entities()`），比較兩種方式的效果差異。
5. **思考題**：在真實的企業場景中，知識圖譜的資料通常遠比 `data.txt` 複雜。你認為這套混合式 Graph RAG 架構在擴展到大規模圖譜時，會遇到哪些挑戰？可以如何應對？

## 延伸

完成本 Lab 後，可繼續：

- **[Lab 5](../lab5/README.md)**：使用多份非結構化企業風格語料與擴充三元組，在較貼近實務的設定下練習同一套混合式流程（獨立的 `lab5/chroma_store`，且匯入圖譜會覆寫 Neo4j 全圖，詳見 Lab 5 說明）。
- **[Lab 6](../lab6/README.md)**：為本 Lab 的混合式 Graph RAG 加入 Guardrails（注入偵測、主題過濾、證據充足性、事實查核），讓系統更貼近生產環境。
