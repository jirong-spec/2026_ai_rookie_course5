"""將 docs/corpus 內多份非結構化文件以 SemanticChunker 切分後寫入 lab5/chroma_store。"""
from pathlib import Path

from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_experimental.text_splitter import SemanticChunker

LAB5 = Path(__file__).resolve().parent
CORPUS_DIR = LAB5 / "docs" / "corpus"
CHROMA_DIR = LAB5 / "chroma_store"
EMBED_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


def main() -> None:
    if not CORPUS_DIR.is_dir():
        raise FileNotFoundError(f"找不到語料目錄：{CORPUS_DIR}")

    loader = DirectoryLoader(
        str(CORPUS_DIR),
        glob="**/*.txt",
        loader_cls=TextLoader,
        loader_kwargs={"encoding": "utf-8"},
    )
    docs = loader.load()
    if not docs:
        raise RuntimeError(f"{CORPUS_DIR} 內沒有任何 .txt 文件")

    emb = HuggingFaceEmbeddings(model_name=EMBED_MODEL)
    splitter = SemanticChunker(
        emb,
        breakpoint_threshold_type="percentile",
        breakpoint_threshold_amount=90,
    )
    splits = splitter.split_documents(docs)
    print(f"載入 {len(docs)} 個檔案 → SemanticChunker 產生 {len(splits)} 個 chunk")
    Chroma.from_documents(splits, emb, persist_directory=str(CHROMA_DIR))
    print(f"已寫入：{CHROMA_DIR}")


if __name__ == "__main__":
    main()
