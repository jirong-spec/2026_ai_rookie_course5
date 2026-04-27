import json
from typing import List
from neo4j import GraphDatabase
import requests

driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j","password123"))

def call_llm(messages):
    data = {
        "model": "Qwen2.5-3B-Instruct",
        "messages": messages,
        "temperature": 0.8,
        "top_p": 0.6,
        "stream": False,
        "max_tokens": 1024
    }
    
    response = requests.post("http://127.0.0.1:8299/v1/chat/completions", json=data)
    response = response.json()
    response_text = response["choices"][0]["message"]["content"]
    return response_text

def extract_entities(question:str)->List[str]:
    system_prompt = "你是一位助手，請從使用者問題中找出人名、公司名或產品名，列成 Python list，不要包含重複或其他文字。回傳 JSON，例如：{\"entities\":[\"Alice\",\"Acme\"]}"
    user_prompt = f"問題：{question}"
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    response = call_llm(messages)
    try:
        data = json.loads(response.strip())
        return data.get("entities",[])
    except Exception:
        return []

def fetch_subgraph(entities:List[str], max_hop:int=1):
    if not entities: return []
    # TODO 1: 撰寫 Cypher 查詢，以 entities 為起點擴展 1~max_hop 步的子圖
    # 要求：
    #   - MATCH p=(n)-[*1..max_hop]-(m)   ← 用 .format(k=max_hop) 嵌入 hop 數
    #   - WHERE n.name IN $ents
    #   - RETURN p LIMIT 50
    query = f"""
    MATCH p=(n)-[*1..{max_hop}]-(m)
    WHERE n.name IN $ents
    RETURN p
    LIMIT 50
    """

    with driver.session() as s:
        records=s.run(query,ents=entities)
        triples=[]
        for r in records:
            for rel in r["p"].relationships:
                triples.append(f"({rel.start_node['name']})-[:{rel.type}]->({rel.end_node['name']})")
        return list(set(triples))

def qa_graph(question:str):
    entities=extract_entities(question)
    triples=fetch_subgraph(entities)
    context="\n".join(triples) if triples else "（查無相關圖譜）"
    # TODO 2: 撰寫 prompt，將圖譜三元組（context）當作上下文，讓 LLM 根據這些關係回答問題
    # 提示：prompt 應包含：(1) 已知的圖譜關係 (2) 使用者的問題 (3) 要求 LLM 根據上下文回答
    prompt = f"""
你是一個根據知識圖譜回答問題的助手。

以下是已知的圖譜關係：
{context}

使用者問題：
{question}

請根據上面的圖譜關係回答問題。
要求：
1. 只能根據提供的圖譜關係作答，不要使用外部知識。
2. 如果圖譜關係不足以回答，就回答：「我不知道」。
3. 回答要簡潔、清楚。
"""

    messages = [
        {"role": "user", "content": prompt}
    ]
    response = call_llm(messages)
    answer = response.strip()
    return answer, triples

if __name__=="__main__":
    while True:
        q=input("提問(Enter 離開)：")
        if not q: break
        ans,ev=qa_graph(q)
        print("Answer:",ans)
        print("Evidence triples:",ev)
