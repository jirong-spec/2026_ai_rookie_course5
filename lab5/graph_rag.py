"""Lab 5：混合式 Graph RAG（語料為多檔 corpus + 擴充後的 Neo4j）。"""
import os, re
from pathlib import Path

from langchain_openai import ChatOpenAI
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from neo4j import GraphDatabase

os.environ["OPENAI_API_KEY"] = "EMPTY"
os.environ["OPENAI_API_BASE"] = "http://localhost:8299/v1"
LLM_MODEL = "Qwen2.5-3B-Instruct"
llm = ChatOpenAI(model=LLM_MODEL, temperature=0.2)

LAB5 = Path(__file__).resolve().parent
emb = HuggingFaceEmbeddings(
    model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)
vectordb = Chroma(
    persist_directory=str(LAB5 / "chroma_store"),
    embedding_function=emb,
)

driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "password123"))


def candidate_entities(question: str, k: int = 6):
    docs = vectordb.similarity_search(question, k=k)
    ent = set()
    for d in docs:
        for tok in re.findall(r'[A-Z][A-Za-z]+', d.page_content):
            ent.add(tok)
    return list(ent)[:8]


def graph_expand(ents, hop=2):
    if not ents:
        return []
    query = f"""
    MATCH p=(n)-[*1..{hop}]-(m)
    WHERE n.name IN $ents
    RETURN p LIMIT 120
    """
    with driver.session() as s:
        recs = s.run(query, ents=ents)
        triples = set()
        for r in recs:
            for rel in r["p"].relationships:
                triples.add(f"({rel.start_node['name']})-[:{rel.type}]->({rel.end_node['name']})")
    return list(triples)


def answer_with_graph(question: str):
    ents = candidate_entities(question)
    triples = graph_expand(ents)
    context = "\n".join(triples) if triples else "（圖譜中找不到相關關係）"
    prompt = f"""
你是一位企業知識專家，只能根據下列圖譜關係回答問題，若資訊不足請回答「無足夠資訊」。
圖譜：
{context}

問題：{question}
答案（繁體中文）：
"""
    return llm.invoke(prompt).content.strip(), triples, ents


if __name__ == "__main__":
    while True:
        q = input("提問 (Enter 離開)：")
        if not q:
            break
        ans, triples, ents = answer_with_graph(q)
        print("候選實體：", ents)
        print("Evidence triples:", triples)
        print("Answer:", ans, "\n")
