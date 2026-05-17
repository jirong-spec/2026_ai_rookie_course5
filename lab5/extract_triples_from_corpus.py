"""
讀取 docs/corpus 下所有 .txt，呼叫 LLM 抽取事實，寫入 docs/kg_triples.txt。
僅保留「與 Lab 2 ingest 相同文法」且可通過 triples_parse.parse() 的句子。
"""
import argparse
import os
import re
from pathlib import Path

from langchain_openai import ChatOpenAI

from triples_parse import parse

LAB5 = Path(__file__).resolve().parent
CORPUS_DIR = LAB5 / "docs" / "corpus"
DEFAULT_OUT = LAB5 / "docs" / "kg_triples.txt"

os.environ["OPENAI_API_KEY"] = "EMPTY"
os.environ["OPENAI_API_BASE"] = "http://localhost:8299/v1"
LLM_MODEL = "Qwen2.5-3B-Instruct"

EXTRACTION_PROMPT = """你是一個知識圖譜抽取助手。請從以下語料中抽取所有可識別的事實，並以下列五種英文句式輸出，每行一句、句尾加英文句點。

合法句式（嚴格遵守，不得使用其他格式）：
  Person works_at Company.
  Company produces Product.
  Company partners_with Company.
  Company supplies Product to Company.
  Person leads Product.

中文關鍵詞對應提示：
  「任職」「擔任」「在...工作」 → works_at
  「生產」「製造」「推出」「開發」 → produces
  「策略聯盟」「合作夥伴」「合作」→ partners_with
  「供應」「提供...給」 → supplies...to
  「負責」「主導」「領導」 → leads

規則：
1. 只輸出純英文句子，不要輸出中文、說明文字、編號或 markdown。
2. 實體名稱保留語料中的英文原文（大小寫一致）。
3. 只抽取語料中明確陳述的事實，不推測或補充。
4. 每行只輸出一句，句尾必須是英文句點。

以下是語料：
__CORPUS__

請直接輸出三元組句子，不要有任何前言或說明："""


def load_corpus() -> str:
    if not CORPUS_DIR.is_dir():
        raise FileNotFoundError(f"找不到語料目錄：{CORPUS_DIR}")
    parts = []
    for p in sorted(CORPUS_DIR.glob("**/*.txt")):
        body = p.read_text(encoding="utf-8").strip()
        if body:
            parts.append(f"=== 檔案: {p.name} ===\n{body}")
    if not parts:
        raise RuntimeError(f"{CORPUS_DIR} 內沒有任何 .txt")
    return "\n\n".join(parts)


def normalize_line(line: str) -> str:
    s = line.strip()
    s = re.sub(r"^[\-\*]\s+", "", s)
    s = re.sub(r"^\d+[\.\)、]\s*", "", s)
    s = s.strip("`").strip()
    return s


def extract_raw_lines(llm_text: str) -> list[str]:
    text = llm_text.strip()
    if "```" in text:
        m = re.search(r"```(?:\w*\n)?(.*?)```", text, re.DOTALL)
        if m:
            text = m.group(1).strip()
    out = []
    for line in text.splitlines():
        n = normalize_line(line)
        if n and not n.startswith("#"):
            out.append(n)
    return out


def filter_parsable(lines: list[str]) -> tuple[list[str], list[str]]:
    good, bad = [], []
    seen = set()
    for line in lines:
        if parse(line) is not None:
            if line not in seen:
                seen.add(line)
                good.append(line)
        else:
            bad.append(line)
    return good, bad


def main() -> None:
    ap = argparse.ArgumentParser(description="從 corpus 經 LLM 產生 kg_triples.txt")
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="只印出結果，不寫入檔案",
    )
    ap.add_argument(
        "-o",
        "--output",
        type=Path,
        default=DEFAULT_OUT,
        help=f"輸出路徑（預設：{DEFAULT_OUT}）",
    )
    args = ap.parse_args()

    corpus = load_corpus()
    llm = ChatOpenAI(model=LLM_MODEL, temperature=0)
    prompt = EXTRACTION_PROMPT.replace("__CORPUS__", corpus)
    resp = llm.invoke(prompt).content
    raw = extract_raw_lines(resp)
    good, bad = filter_parsable(raw)

    if bad:
        print("以下行無法通過 ingest 文法，已捨棄：")
        for b in bad[:20]:
            print("  ", repr(b)[:120])
        if len(bad) > 20:
            print(f"  ... 另有 {len(bad) - 20} 行")

    header = (
        "# 本檔由 extract_triples_from_corpus.py 產生；可人工增刪後再執行 ingest_graph.py\n"
        f"# 模型：{LLM_MODEL}，temperature=0\n"
        "\n"
    )
    body = "\n".join(good) + ("\n" if good else "")

    if args.dry_run:
        print(header)
        print(body)
        print(f"# （共 {len(good)} 行可匯入）")
        return

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(header + body, encoding="utf-8")
    print(f"已寫入 {args.output} ，可匯入行數：{len(good)}")


if __name__ == "__main__":
    main()
