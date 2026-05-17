import json
import re
from typing import List
from neo4j import GraphDatabase
import requests

driver = GraphDatabase.driver(
    "bolt://localhost:7687",
    auth=("neo4j", "password123")
)

LLM_API_URL = "http://127.0.0.1:8299/v1/chat/completions"
LLM_MODEL = "Qwen2.5-3B-Instruct"


def call_llm(messages, temperature=0.2, max_tokens=1024):
    data = {
        "model": LLM_MODEL,
        "messages": messages,
        "temperature": temperature,
        "top_p": 0.8,
        "stream": False,
        "max_tokens": max_tokens
    }

    try:
        response = requests.post(LLM_API_URL, json=data, timeout=30)
        response.raise_for_status()
        payload = response.json()
        return payload["choices"][0]["message"]["content"].strip()
    except requests.RequestException as e:
        print(f"[LLM HTTP error] {e}")
        return ""
    except (KeyError, ValueError, TypeError) as e:
        print(f"[LLM response parse error] {e}")
        return ""


def extract_json_block(text: str):
    if not text:
        return None

    text = text.strip()

    try:
        return json.loads(text)
    except Exception:
        pass

    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None

    try:
        return json.loads(m.group(0))
    except Exception:
        return None



def fallback_extract_entities(question: str) -> List[str]:
    cands = re.findall(r"\b[A-Z][A-Za-z0-9_]+\b", question)
    seen = set()
    out = []
    for x in cands:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out



def extract_entities(question: str) -> List[str]:
    system_prompt = """
你是一個實體抽取器。
請從使用者問題中找出所有明確出現的人名、公司名、產品名。

規則：
1. 必須保留原文中的實體字串，不能翻譯、不能改寫、不能猜測。
2. 英文大小寫必須與原問題完全一致。
3. 只抽取問題中真的有出現的專有名詞，不要加入推測實體。
4. 若沒有實體，回傳空陣列。
5. 只能輸出合法 JSON，不要輸出任何解釋或 markdown。

範例：
問題：Alice 在哪裡工作？
輸出：{"entities":["Alice"]}
""".strip()

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"問題：{question}"}
    ]

    response = call_llm(messages, temperature=0.0, max_tokens=128)
    data = extract_json_block(response)

    if not isinstance(data, dict):
        return []

    entities = data.get("entities", [])
    if not isinstance(entities, list):
        return []
    
    QUESTION_WORDS = {
    "誰", "哪裡", "哪里", "哪個", "哪一個", "哪間", "哪家",
    "什麼", "甚麼", "多少", "幾個", "幾位", "如何"
}
    cleaned = []
    seen = set()
    for x in entities:
        if isinstance(x, str):
            x = x.strip()
            if (
                x
                and x in question
                and x not in QUESTION_WORDS
                and x not in seen
            ):   
                seen.add(x)
                cleaned.append(x)
    if cleaned:
        return cleaned
    return fallback_extract_entities(question)


def fetch_subgraph(entities: List[str], max_hop: int = 2, directed: bool = False):
    if not entities:
        return []

    rel_pat = "->" if directed else "-"
    query = """
    MATCH p=(n)-[*1..{k}]{rel}(m)
    WHERE n.name IN $ents
      AND ALL(x IN nodes(p) WHERE SINGLE(y IN nodes(p) WHERE y = x))
    RETURN p
    LIMIT 50
    """.format(k=max_hop, rel=rel_pat)

    triples = []
    seen = set()

    with driver.session() as s:
        records = s.run(query, ents=entities)
        for r in records:
            path = r["p"]
            for rel in path.relationships:
                triple = f"({rel.start_node['name']})-[:{rel.type}]->({rel.end_node['name']})"
                if triple not in seen:
                    seen.add(triple)
                    triples.append(triple)

    return triples


import re
from collections import defaultdict

def parse_triple(triple: str):
    m = re.match(r"\((.*?)\)-\[:(.*?)\]->\((.*?)\)", triple)
    if not m:
        return None
    return m.group(1), m.group(2), m.group(3)

def answer_relation_question(question: str, entities: List[str], triples: List[str]):
    if len(entities) != 2:
        return None

    a, b = entities[0], entities[1]
    parsed = [parse_triple(t) for t in triples]
    parsed = [x for x in parsed if x]

    # 1-hop direct relation
    for h, r, t in parsed:
        if h == a and t == b:
            return f"{a} 和 {b} 的直接關係是 {r}。"
        if h == b and t == a:
            return f"{a} 和 {b} 的直接關係是 {r}。"

    # 2-hop relation: a -> x -> b, a <- x -> b, a -> x <- b, a <- x <- b
    neighbors = defaultdict(list)
    for h, r, t in parsed:
        neighbors[h].append((r, t, "out"))
        neighbors[t].append((r, h, "in"))

    for mid_info in neighbors[a]:
        _, mid, _ = mid_info
        if mid == b:
            continue
        for _, target, _ in neighbors[mid]:
            if target == b:
                return f"{a} 和 {b} 沒有直接關係，但可透過 {mid} 形成間接關聯。"

    return None



def qa_graph(question: str):
    entities = extract_entities(question)
    triples = fetch_subgraph(entities, max_hop=2, directed=False)

    print("entities =", entities)
    print("triples =", triples)

    rule_answer = answer_relation_question(question, entities, triples)
    if rule_answer:
        return rule_answer, triples

    context = "\n".join(triples) if triples else "（查無相關圖譜）"

    prompt = f"""你是一個根據知識圖譜回答問題的助手。

以下是已知的圖譜關係：
{context}

使用者問題：
{question}

請根據上面的圖譜關係回答問題。

要求：
1. 只能根據提供的圖譜關係作答，不要使用外部知識。
2. 如果圖譜關係不足以回答，就回答「我不知道」。
3. 如果答案需要多跳推理，必須明確指出中間節點與推理鏈。
4. 不要把間接關係說成直接關係。
5. 若圖譜中沒有 A-[:REL]->B，就不能回答 A 和 B 有直接 REL 關係。
6. 回答要簡潔、清楚。
"""

    messages = [
        {"role": "user", "content": prompt}
    ]
    answer = call_llm(messages, temperature=0.2, max_tokens=256)
    return answer, triples


if __name__ == "__main__":
    try:
        while True:
            q = input("提問(Enter 離開)：").strip()
            if not q:
                break

            ans, ev = qa_graph(q)
            print("Answer:", ans if ans else "（LLM 無回應）")
            print("Evidence triples:", ev)
    finally:
        driver.close()
