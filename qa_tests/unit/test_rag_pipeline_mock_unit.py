from __future__ import annotations

from dataclasses import dataclass

from rag.base_retriever import BaseRetriever, RetrievedDocument
from rag.rag_pipeline import RAGPipeline


@dataclass
class _Store:
    docs: list[RetrievedDocument]


class MockRetriever(BaseRetriever):
    def __init__(self) -> None:
        self._store = _Store(docs=[])

    def add_documents(self, texts: list[str], metadatas: list[dict] | None = None) -> int:
        metadatas = metadatas or [{} for _ in texts]
        for t, m in zip(texts, metadatas, strict=False):
            src = str(m.get("source") or "")
            self._store.docs.append(RetrievedDocument(content=t, source=src, score=0.5, metadata=m))
        return len(texts)

    def retrieve(self, query: str, k: int = 5) -> list[RetrievedDocument]:
        q = (query or "").strip().lower()
        if not q:
            return []
        hits = [d for d in self._store.docs if q in d.content.lower()]
        return hits[:k]

    def clear(self) -> None:
        self._store.docs.clear()

    def document_count(self) -> int:
        return len(self._store.docs)

    def delete_by_ids(self, ids: list[str]) -> int:
        return 0


def test_rag_pipeline__retrieve_empty_when_not_ready() -> None:
    p = RAGPipeline(retriever=MockRetriever(), chunk_size=50, chunk_overlap=0)
    assert p.is_ready() is False
    assert p.retrieve("anything") == ""


def test_rag_pipeline__index_and_retrieve_formatted() -> None:
    p = RAGPipeline(retriever=MockRetriever(), chunk_size=50, chunk_overlap=0)
    n = p.index_text("Hello attention mechanism", source="intro.txt")
    assert n >= 1
    assert p.is_ready() is True

    out = p.retrieve("attention", k=1)
    assert "【相关片段 1】" in out
    assert "intro.txt" in out
    assert "attention mechanism" in out


def test_rag_pipeline__clear_resets_ready() -> None:
    p = RAGPipeline(retriever=MockRetriever(), chunk_size=50, chunk_overlap=0)
    p.index_text("A B C", source="x.txt")
    assert p.document_count() > 0
    p.clear()
    assert p.document_count() == 0
    assert p.is_ready() is False

