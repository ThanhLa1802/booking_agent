"""
Tests for the RAG service: document indexing and semantic search.

Uses FakeEmbeddings (returns deterministic vectors) so no Ollama is needed.
Uses chromadb.EphemeralClient for an in-memory store.
"""
import pytest
from pathlib import Path
from langchain_core.embeddings import Embeddings


class FakeEmbeddings(Embeddings):
    """Deterministic fake embeddings: each word is its ordinal sum."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vec(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vec(text)

    def _vec(self, text: str) -> list[float]:
        total = sum(ord(c) for c in text[:50])
        return [float(total % 256) / 255.0] * 384


@pytest.fixture(autouse=True)
def reset_chroma_store():
    """Ensure singleton is cleared between tests."""
    from fast_api_services.agent.rag import reset_store
    reset_store()
    yield
    reset_store()


@pytest.fixture
def tmp_docs(tmp_path: Path) -> Path:
    """Create a minimal docs/ structure for testing."""
    (tmp_path / "syllabus").mkdir()
    (tmp_path / "policies").mkdir()
    (tmp_path / "faq").mkdir()

    (tmp_path / "syllabus" / "grades.md").write_text(
        "# Syllabus\nGrade 1 Piano Classical exam lasts 10 minutes.\n"
        "Grade 5 Theory is required for higher grades.", encoding="utf-8"
    )
    (tmp_path / "policies" / "cancellation.md").write_text(
        "# Cancellation Policy\nCancel 30+ days before: 90% refund.\n"
        "Cancel 1-7 days before: 0% refund.", encoding="utf-8"
    )
    (tmp_path / "faq" / "candidate.md").write_text(
        "# FAQ\nWhat should I bring on exam day?\nBring your candidate ID and instrument.", encoding="utf-8"
    )
    return tmp_path


def test_index_docs_returns_chunk_count(tmp_docs, tmp_path):
    """index_docs should return > 0 chunks on first run."""
    import chromadb
    from langchain_chroma import Chroma
    from fast_api_services.agent import rag

    embeddings = FakeEmbeddings()
    persist_dir = str(tmp_path / "chroma")

    # Patch to use ephemeral (in-memory) Chroma
    ephemeral_client = chromadb.EphemeralClient()

    original_get_store = rag._get_store

    def fake_get_store(emb, pdir):
        store = Chroma(
            client=ephemeral_client,
            collection_name="trinity_docs_test",
            embedding_function=emb,
        )
        rag._chroma_store = store
        return store

    rag._get_store = fake_get_store
    try:
        count = rag.index_docs(tmp_docs, embeddings, persist_dir)
        assert count > 0
    finally:
        rag._get_store = original_get_store


def test_index_docs_skips_on_second_call(tmp_docs, tmp_path):
    """index_docs should return 0 if collection already has documents."""
    import chromadb
    from langchain_chroma import Chroma
    from fast_api_services.agent import rag

    embeddings = FakeEmbeddings()
    persist_dir = str(tmp_path / "chroma2")
    ephemeral_client = chromadb.EphemeralClient()

    def fake_get_store(emb, pdir):
        store = Chroma(
            client=ephemeral_client,
            collection_name="trinity_docs_skip",
            embedding_function=emb,
        )
        rag._chroma_store = store
        return store

    rag._get_store = fake_get_store
    try:
        first = rag.index_docs(tmp_docs, embeddings, persist_dir)
        second = rag.index_docs(tmp_docs, embeddings, persist_dir)
        assert first > 0
        assert second == 0
    finally:
        rag._get_store = fake_get_store  # restore to same since reset_store will clear


def test_search_docs_returns_results(tmp_docs, tmp_path):
    """search_docs should return non-empty list for relevant query."""
    import chromadb
    from langchain_chroma import Chroma
    from fast_api_services.agent import rag

    embeddings = FakeEmbeddings()
    persist_dir = str(tmp_path / "chroma3")
    ephemeral_client = chromadb.EphemeralClient()

    def fake_get_store(emb, pdir):
        store = Chroma(
            client=ephemeral_client,
            collection_name="trinity_docs_search",
            embedding_function=emb,
        )
        rag._chroma_store = store
        return store

    rag._get_store = fake_get_store
    try:
        rag.index_docs(tmp_docs, embeddings, persist_dir)
        results = rag.search_docs("Grade 1 Piano", embeddings, persist_dir, k=2)
        assert isinstance(results, list)
        assert len(results) >= 1
    finally:
        rag._get_store = fake_get_store


def test_search_docs_returns_empty_on_empty_store(tmp_path):
    """search_docs on empty collection should return [] not raise."""
    import chromadb
    from langchain_chroma import Chroma
    from fast_api_services.agent import rag

    embeddings = FakeEmbeddings()
    persist_dir = str(tmp_path / "chroma4")
    ephemeral_client = chromadb.EphemeralClient()

    def fake_get_store(emb, pdir):
        store = Chroma(
            client=ephemeral_client,
            collection_name="trinity_docs_empty",
            embedding_function=emb,
        )
        rag._chroma_store = store
        return store

    rag._get_store = fake_get_store
    try:
        results = rag.search_docs("anything", embeddings, persist_dir)
        assert results == []
    finally:
        rag._get_store = fake_get_store


def test_load_documents_missing_dir_is_skipped(tmp_path):
    """_load_documents should skip missing subdirs without raising."""
    from fast_api_services.agent.rag import _load_documents

    empty = tmp_path / "nodocs"
    empty.mkdir()
    docs = _load_documents(empty)
    assert docs == []


def test_load_documents_sets_doc_type_metadata(tmp_docs):
    """Loaded documents must carry doc_type metadata."""
    from fast_api_services.agent.rag import _load_documents

    docs = _load_documents(tmp_docs)
    types = {d.metadata["doc_type"] for d in docs}
    assert "syllabus" in types
    assert "policy" in types
    assert "faq" in types
