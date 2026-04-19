"""
RAG service: index docs/ into ChromaDB, expose search_docs().

Document types (stored in metadata):
  doc_type: "syllabus" | "policy" | "faq"

Indexing strategy:
  - chunk_size=500 tokens, chunk_overlap=50
  - RecursiveCharacterTextSplitter on .md files
  - Run once on app startup; skip if collection already populated
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ── Directory → doc_type mapping ─────────────────────────────────────────────
_DIR_TO_DOCTYPE: dict[str, str] = {
    "syllabus": "syllabus",
    "policies": "policy",
    "faq": "faq",
}

_COLLECTION_NAME = "trinity_docs"
_chroma_store: object | None = None


def _get_store(embeddings: Embeddings, persist_dir: str):
    """Return (or create) the singleton Chroma vector store."""
    global _chroma_store
    if _chroma_store is not None:
        return _chroma_store
    from langchain_chroma import Chroma  # lazy to avoid heavy import
    _chroma_store = Chroma(
        collection_name=_COLLECTION_NAME,
        embedding_function=embeddings,
        persist_directory=persist_dir,
    )
    return _chroma_store


def _load_documents(docs_dir: Path) -> list:
    """Walk docs/ and load all .md files with doc_type metadata."""
    from langchain_core.documents import Document
    docs: list = []
    for subdir, doc_type in _DIR_TO_DOCTYPE.items():
        target = docs_dir / subdir
        if not target.exists():
            logger.warning("Docs directory not found: %s", target)
            continue
        for md_file in sorted(target.glob("*.md")):
            text = md_file.read_text(encoding="utf-8")
            docs.append(
                Document(
                    page_content=text,
                    metadata={
                        "source": md_file.name,
                        "doc_type": doc_type,
                    },
                )
            )
    return docs


def _split_text(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    """Simple character-based splitter — avoids langchain_text_splitters dependency."""
    if len(text) <= chunk_size:
        return [text]
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - chunk_overlap
    return chunks


def _split_documents(docs: list, chunk_size: int, chunk_overlap: int) -> list:
    """Split a list of Documents into smaller chunks, preserving metadata."""
    from langchain_core.documents import Document
    result: list = []
    for doc in docs:
        for chunk_text in _split_text(doc.page_content, chunk_size, chunk_overlap):
            result.append(Document(page_content=chunk_text, metadata=dict(doc.metadata)))
    return result


def index_docs(docs_dir: Path, embeddings, persist_dir: str) -> int:
    """
    Load, split and index docs/. Safe to call multiple times —
    skips indexing if collection is already populated.
    Returns number of chunks indexed (0 if skipped).
    """
    store = _get_store(embeddings, persist_dir)

    # Skip if already populated
    try:
        count = store._collection.count()  # type: ignore[attr-defined]
        if count > 0:
            logger.info("ChromaDB already has %d chunks — skipping re-index.", count)
            return 0
    except Exception:
        pass

    raw_docs = _load_documents(docs_dir)
    if not raw_docs:
        logger.warning("No documents found in %s — RAG will not work.", docs_dir)
        return 0

    chunks = _split_documents(raw_docs, chunk_size=500, chunk_overlap=50)
    store.add_documents(chunks)
    logger.info("Indexed %d chunks from %d documents.", len(chunks), len(raw_docs))
    return len(chunks)


def search_docs(
    query: str,
    embeddings,
    persist_dir: str,
    doc_type: Optional[str] = None,
    k: int = 4,
) -> list[str]:
    """
    Semantic search. Returns list of matching text chunks.
    doc_type filters to "syllabus" | "policy" | "faq" | None (all).
    """
    store = _get_store(embeddings, persist_dir)
    where = {"doc_type": doc_type} if doc_type else None
    try:
        results = store.similarity_search(query, k=k, filter=where)
    except Exception as exc:
        logger.error("ChromaDB search error: %s", exc)
        return []
    return [doc.page_content for doc in results]


def reset_store() -> None:
    """For tests: clear singleton so a fresh store is created."""
    global _chroma_store
    _chroma_store = None
