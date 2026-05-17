# Lab 3：圖譜檢索問答（Graph Retrieval QA）

## 目標

利用 LLM 從使用者問題中**抽取實體**，再到 Neo4j 圖譜中擴展出相關的子圖（subgraph），最後將子圖作為上下文讓 LLM 生成答案。

## 核心概念

```
使用者問題："Carol 和 Acme 有什麼關係？"
      ↓ LLM 實體抽取
實體列表：["Carol", "Acme"]
      ↓ Cypher 子圖查詢 (max_hop=2)
子圖三元組：
  (Carol)-[:WORKS_AT]->(BoltCorp)
  (BoltCorp)-[:PARTNERS_WITH]->(Acme)
  (Carol)-[:LEADS]->(TurboMotor)
      ↓ 組成 Prompt
LLM 根據子圖回答問題
```

## 程式說明 — `graph_retrieval.py`

| 步驟 | 函式 | 說明 |
|------|------|------|
| 1 | `extract_entities()` | 送出 prompt 請 LLM 從問題中找出人名、公司名或產品名，回傳 JSON 格式（已提供完整實作） |
| 2 | `fetch_subgraph()` | 以抽取到的實體為起點，在圖譜中做 1~2 hop 的擴展查詢 **(TODO 1)** |
| 3 | `qa_graph()` | 將子圖三元組組成上下文，交由 LLM 回答問題 **(TODO 2)** |

---

## Cypher 查詢語言入門

Cypher 是 Neo4j 的查詢語言，語法以**圖形化的 ASCII art** 表示節點與關係，直覺且易讀。以下從基礎到本 Lab 所需的進階用法循序介紹。

### 1. 節點（Node）

用小括號 `()` 表示節點，可加上**變數名**、**標籤**和**屬性**：

```cypher
()                          -- 匿名節點（任意節點）
(n)                         -- 綁定到變數 n
(n:Person)                  -- 標籤為 Person 的節點
(n:Person {name: 'Alice'})  -- 標籤 Person 且 name 為 Alice
```

### 2. 關係（Relationship）

用方括號 `[]` 搭配箭頭 `-->` 或 `<--` 表示有方向的關係；用 `--` 表示不限方向：

```cypher
(a)-[r]->(b)                -- a 到 b 的有向關係（綁定到變數 r）
(a)<-[r]-(b)                -- b 到 a 的有向關係
(a)-[r]-(b)                 -- 不限方向（雙向匹配）
(a)-[r:WORKS_AT]->(b)       -- 關係類型為 WORKS_AT
(a)-[:SUPPLIES]->(b)        -- 不綁定變數，只指定類型
```

### 3. MATCH — 模式匹配

`MATCH` 是 Cypher 的核心，用來**在圖譜中尋找符合模式的路徑**：

```cypher
-- 找出所有 Person 節點
MATCH (p:Person)
RETURN p.name

-- 找出 Alice 工作的公司
MATCH (p:Person {name: 'Alice'})-[:WORKS_AT]->(c:Company)
RETURN c.name

-- 找出 Acme 的所有關係（不限方向、不限類型）
MATCH (a:Company {name: 'Acme'})-[r]-(other)
RETURN type(r), other.name
```

### 4. WHERE — 條件過濾

用 `WHERE` 對匹配結果做進一步篩選：

```cypher
-- name 等於特定值
MATCH (n)
WHERE n.name = 'Alice'
RETURN n

-- name 在某個列表中（本 Lab 的關鍵用法！）
MATCH (n)
WHERE n.name IN ['Alice', 'Carol']
RETURN n

-- 在 Python 中用 $ents 作為參數傳入
MATCH (n)
WHERE n.name IN $ents
RETURN n
```

### 5. Variable-Length Path — 可變長度路徑（本 Lab 核心）

用 `[*min..max]` 表示沿著關係走 **min 到 max 步**，這是實現**多跳推理**的關鍵：

```cypher
-- 走 1 步（直接鄰居）
MATCH p=(n)-[*1..1]-(m)
WHERE n.name = 'Carol'
RETURN p

-- 走 1~2 步（直接 + 間接鄰居）
MATCH p=(n)-[*1..2]-(m)
WHERE n.name = 'Carol'
RETURN p

-- 走 1~3 步
MATCH p=(n)-[*1..3]-(m)
WHERE n.name IN $ents
RETURN p LIMIT 50
```

> **重要**：`p=` 是把整條路徑（含沿途所有節點和關係）綁定到變數 `p`，後續可從 `p` 中取出每段關係。

#### hop 數的直覺理解

以 Lab 2 建立的圖譜為例，從 Carol 出發：

```
hop=1：Carol → BoltCorp          （直接關係：WORKS_AT）
       Carol → TurboMotor        （直接關係：LEADS）

hop=2：Carol → BoltCorp → Acme   （經 BoltCorp 到 Acme：PARTNERS_WITH / SUPPLIES）
       Carol → TurboMotor → ???  （看有無更多連結）
```

hop 愈大，能探索的範圍愈廣，但結果量也愈大，因此通常會加 `LIMIT`。

### 6. RETURN 與 LIMIT

```cypher
RETURN p              -- 回傳整條路徑
RETURN n.name, r.item -- 回傳特定屬性
RETURN p LIMIT 50     -- 最多回傳 50 筆結果
```

### 7. 參數化查詢（在 Python 中使用）

Cypher 支援用 `$` 前綴傳入參數，避免字串拼接的安全風險：

```python
query = """
MATCH p=(n)-[*1..2]-(m)
WHERE n.name IN $ents
RETURN p LIMIT 50
"""
# 在 neo4j Python driver 中傳入參數
session.run(query, ents=["Alice", "Acme"])
```

> **注意**：`$ents` 是參數化變數，由 `session.run()` 的 `ents=...` 傳入。但 `*1..2` 中的數字**不能**用 `$` 參數化（Cypher 限制），需要用 Python 的 `.format()` 或 f-string 嵌入。

### 8. 組合範例 — 本 Lab 的查詢模式

將以上概念組合，就能寫出本 Lab `fetch_subgraph()` 所需的查詢：

```cypher
MATCH p=(n)-[*1..{hop}]-(m)
WHERE n.name IN $ents
RETURN p LIMIT 50
```

這條查詢做的事：
1. 從 `$ents` 列表中的任一節點 `n` 出發
2. 沿任意方向走 1 到 `{hop}` 步
3. 把走過的完整路徑 `p`（含所有節點和關係）回傳
4. 最多 50 筆結果

在 Python 中需要用 `.format(hop=max_hop)` 將 hop 數嵌入字串（因為 Cypher 不支援路徑長度參數化）。

## 前置條件

- 已完成 **Lab 2** 的圖譜匯入（Neo4j 中有資料）

## 執行方式

```bash
cd lab3
python graph_retrieval.py
```

## 可嘗試的問題

| 問題 | 預期能檢索到的關係 |
|------|-------------------|
| Alice 在哪裡工作？ | (Alice)-[:WORKS_AT]->(Acme) |
| Acme 的合作夥伴是誰？ | (Acme)-[:PARTNERS_WITH]->(BoltCorp) |
| Carol 和 Acme 有什麼關係？ | 需要 2-hop：Carol → BoltCorp → Acme |
| 誰負責 TurboMotor？ | (Carol)-[:LEADS]->(TurboMotor) |

## 實作狀態

`graph_retrieval.py` 已完整實作，無待填空：

| 項目 | 說明 | 狀態 |
|------|------|------|
| `extract_entities()` | LLM 實體抽取 + fallback 正則 | ✅ 完成 |
| `fetch_subgraph()` | Cypher `[*1..2]` 子圖查詢，LIMIT 50 | ✅ 完成 |
| `answer_relation_question()` | 規則式直接／間接關係偵測 | ✅ 完成 |
| `qa_graph()` | 組合上下文，LLM 生成繁體中文回答 | ✅ 完成 |

## 作業

完成上述 TODO 並確認程式可執行後，請繼續以下練習：

1. **調整 hop 數**：修改 `max_hop` 參數為 1，重新問「Carol 和 Acme 有什麼關係？」，觀察結果有何不同。對照上方「hop 數的直覺理解」，解釋為什麼 hop 數會影響回答能力。
2. **觀察實體抽取**：觀察 `extract_entities()` 的輸出，嘗試問一個不包含明確實體名稱的問題（例如「這家公司有什麼產品？」），看看 LLM 能否正確抽取實體。記錄失敗的案例。
3. **改進實體抽取**：在 `extract_entities()` 的 prompt 中加入 few-shot 範例，看看能否提升實體抽取的準確率。
4. **比較題**：用同一個問題分別在 **Lab 1（向量 RAG）** 和 **Lab 3（圖譜 QA）** 中測試，比較兩者的回答。哪種方式在處理「多跳推理」問題時表現更好？為什麼？
