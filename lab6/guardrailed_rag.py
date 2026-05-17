"""Lab 6：為混合式 Graph RAG 加入 Guardrails（防護機制）。

基於 Lab 4 的 hybrid Graph RAG pipeline，在 Input / Retrieval / Output
三個階段加入四道防護：

  1. 注入偵測（rule-based）
  2. 主題過濾（LLM-as-judge）
  3. 證據充足性（rule-based）
  4. 事實查核（LLM-as-judge）
"""
import argparse
import json
import os
import re
from pathlib import Path

from langchain_openai import ChatOpenAI
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from neo4j import GraphDatabase

# ------- env & clients -------
os.environ["OPENAI_API_KEY"] = "EMPTY"
os.environ["OPENAI_API_BASE"] = "http://localhost:8299/v1"
LLM_MODEL = "Qwen2.5-3B-Instruct"
llm = ChatOpenAI(model=LLM_MODEL, temperature=0)

emb = HuggingFaceEmbeddings(
    model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)
_chroma_dir = Path(__file__).resolve().parent.parent / "lab1" / "chroma_store"
vectordb = Chroma(persist_directory=str(_chroma_dir), embedding_function=emb)

driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "password123"))

# ============================================================
# Guardrails
# ============================================================

INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|above|prior)",
    r"forget\s+(all\s+)?(previous|above|prior|your|instructions)",
    r"disregard\s+(all\s+)?(previous|above|prior|instructions)",
    r"system\s*prompt",
    r"jailbreak",
    r"\bDAN\s+mode\b",
    r"假裝(你是|你現在是|自己是)",
    r"扮演.{0,10}(角色|助手|AI|機器人)",
    r"你是一個.{0,20}(不受限|沒有限制|無限制)",
    r"(新的|以下是).{0,10}(指令|系統提示|system prompt)",
]


def guard_injection(question: str) -> dict:
    """Input guardrail #1：規則比對偵測 prompt injection。"""
    for pat in INJECTION_PATTERNS:
        if re.search(pat, question, re.IGNORECASE):
            return {"pass": False, "reason": "偵測到可能的提示注入（prompt injection）"}
    return {"pass": True, "reason": "安全"}


def guard_topic(question: str) -> dict:
    """Input guardrail #2：LLM 判斷問題是否與企業知識相關。"""
    prompt = f"""你是一個問題分類器，負責判斷使用者的問題是否與企業知識相關。
企業知識的範疇包括：人員任職關係、公司資訊、產品、供應鏈、合作夥伴、業務往來等。

使用者問題：{question}

請判斷此問題是否與企業知識相關，僅回傳 JSON，不要輸出任何其他文字：
{{"relevant": true 或 false, "reason": "簡短理由"}}"""
    try:
        resp = llm.invoke(prompt).content.strip()
        match = re.search(r"\{.*?\}", resp, re.DOTALL)
        if match:
            data = json.loads(match.group())
            if data.get("relevant", False):
                return {"pass": True, "reason": data.get("reason", "相關")}
            return {"pass": False, "reason": data.get("reason", "與企業知識無關")}
    except Exception:
        pass
    return {"pass": True, "reason": "（無法判斷，預設放行）"}


def guard_evidence(triples: list, min_count: int = 1) -> dict:
    """Retrieval guardrail：證據不足時拒答，避免憑空生成。"""
    n = len(triples)
    if n < min_count:
        return {"pass": False, "reason": f"僅檢索到 {n} 筆三元組，證據不足"}
    return {"pass": True, "reason": f"檢索到 {n} 筆三元組"}


def guard_grounding(answer: str, triples: list) -> dict:
    """Output guardrail：LLM 查核答案是否有圖譜證據支持。"""
    context = "\n".join(triples)
    prompt = f"""你是一個事實查核助手，負責驗證 AI 回答是否完全有圖譜依據。

圖譜證據：
{context}

AI 生成的回答：
{answer}

請判斷回答中的每項陳述是否都能從圖譜證據中找到依據。
僅回傳 JSON，不要輸出任何其他文字：
{{"grounded": true 或 false, "reason": "說明哪些陳述有或沒有依據"}}"""
    try:
        resp = llm.invoke(prompt).content.strip()
        match = re.search(r"\{.*?\}", resp, re.DOTALL)
        if match:
            data = json.loads(match.group())
            if data.get("grounded", False):
                return {"pass": True, "reason": data.get("reason", "有根據")}
            return {"pass": False, "reason": data.get("reason", "答案可能包含幻覺")}
    except Exception:
        pass
    return {"pass": True, "reason": "（無法判斷，預設放行）"}


# ============================================================
# RAG Pipeline（與 Lab 4 相同邏輯）
# ============================================================

def candidate_entities(question: str, k: int = 4):
    docs = vectordb.similarity_search(question, k=k)
    ent = set()
    for d in docs:
        for tok in re.findall(r"[A-Z][A-Za-z]+", d.page_content):
            ent.add(tok)
    return list(ent)[:5]


def graph_expand(ents, hop=2):
    if not ents:
        return []
    query = f"""
    MATCH p=(n)-[*1..{hop}]-(m)
    WHERE n.name IN $ents
    RETURN p LIMIT 100
    """
    with driver.session() as s:
        recs = s.run(query, ents=ents)
        triples = set()
        for r in recs:
            for rel in r["p"].relationships:
                triples.add(
                    f"({rel.start_node['name']})-[:{rel.type}]->({rel.end_node['name']})"
                )
        return list(triples)


def generate_answer(question: str, triples: list) -> str:
    context = "\n".join(triples) if triples else "（圖譜中找不到相關關係）"
    prompt = (
        "你是一位企業知識專家，只能根據下列圖譜關係回答問題，"
        "若資訊不足請回答「無足夠資訊」。\n"
        f"圖譜：\n{context}\n\n"
        f"問題：{question}\n"
        "答案（繁體中文）："
    )
    return llm.invoke(prompt).content.strip()


# ============================================================
# Guardrailed Pipeline
# ============================================================

def _icon(passed: bool) -> str:
    return "v" if passed else "x"


def guardrailed_rag(question: str, enable_guards: bool = True):
    """完整 pipeline：Input → Retrieval → Generation → Output，每階段可加 guardrail。"""

    print(f"\n{'=' * 55}")
    print(f"  提問：{question}")
    print("=" * 55)

    # ---- Input Guards ----
    if enable_guards:
        print("── Input Guard ──")

        inj = guard_injection(question)
        print(f"  [{_icon(inj['pass'])}] 注入偵測：{inj['reason']}")
        if not inj["pass"]:
            print("── 最終回答 ──")
            print(f"  [已攔截] {inj['reason']}\n")
            return

        topic = guard_topic(question)
        print(f"  [{_icon(topic['pass'])}] 主題過濾：{topic['reason']}")
        if not topic["pass"]:
            print("── 最終回答 ──")
            print(f"  [已攔截] 此問題與企業知識無關，請換個問題。\n")
            return

    # ---- Retrieval ----
    print("── Retrieval ──")
    ents = candidate_entities(question)
    print(f"  候選實體：{ents}")
    triples = graph_expand(ents)
    print(f"  圖譜三元組：{len(triples)} 筆")
    if triples:
        for t in triples[:5]:
            print(f"    {t}")
        if len(triples) > 5:
            print(f"    ... 另有 {len(triples) - 5} 筆")

    # ---- Retrieval Guard ----
    if enable_guards:
        print("── Retrieval Guard ──")
        ev = guard_evidence(triples)
        print(f"  [{_icon(ev['pass'])}] 證據充足：{ev['reason']}")
        if not ev["pass"]:
            print("── 最終回答 ──")
            print("  無足夠證據回答此問題。\n")
            return

    # ---- Generation ----
    print("── LLM 回答 ──")
    answer = generate_answer(question, triples)
    print(f"  {answer}")

    # ---- Output Guard ----
    if enable_guards:
        print("── Output Guard ──")
        gr = guard_grounding(answer, triples)
        print(f"  [{_icon(gr['pass'])}] 事實查核：{gr['reason']}")
        if not gr["pass"]:
            print("── 最終回答 ──")
            print(f"  {answer}")
            print(f"  ⚠ 警告：{gr['reason']}\n")
            return

    print("── 最終回答 ──")
    print(f"  {answer}\n")


# ============================================================
# Main
# ============================================================

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Lab 6：Guardrailed Graph RAG")
    ap.add_argument(
        "--no-guard",
        action="store_true",
        help="停用所有 guardrails，直接執行 RAG pipeline（方便對比）",
    )
    args = ap.parse_args()

    guards_on = not args.no_guard
    mode = "ON" if guards_on else "OFF"
    print(f"Guardrails: {mode}")
    print("輸入問題開始問答，按 Enter 離開。\n")

    while True:
        q = input("提問：")
        if not q:
            break
        guardrailed_rag(q, enable_guards=guards_on)

    driver.close()
