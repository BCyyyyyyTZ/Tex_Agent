"""
RAGPipeline 单元测试：注入 Mock BaseRetriever，不启动 Chroma / embedding。

复用夹具：tests/test_rag/test_document/ 下与 document_loader 测试相同的文件。

运行（项目根 Tex_Agent/）：
    pytest tests/test_rag/test_rag_pipeline_mock.py -v
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, List, Optional

import pytest

from rag.base_retriever import BaseRetriever, RetrievedDocument
from rag.document_loader import load_and_chunk
from rag.rag_pipeline import RAGPipeline

from rag.store_listing import (
    StoreField,
    StoredChunkRecord,
    StoredChunksPage,
    format_stored_chunks_page,
)

FIXTURE_DIR = Path(__file__).resolve().parent / "test_document"


class MockRetriever(BaseRetriever):
    """记录 add/retrieve/clear 调用，检索结果可预设。"""

    def __init__(self) -> None:
        self._doc_count = 0
        self.add_calls: List[dict[str, Any]] = []
        self.retrieve_calls: List[tuple[str, int]] = []
        self._retrieve_results: List[RetrievedDocument] = []

    def set_retrieve_results(self, docs: List[RetrievedDocument]) -> None:
        self._retrieve_results = list(docs)

    def add_documents(
        self,
        texts: List[str],
        metadatas: Optional[List[dict]] = None,
    ) -> int:
        self.add_calls.append(
            {
                "texts": list(texts),
                "metadatas": [dict(m) for m in metadatas] if metadatas else None,
            }
        )
        n = len(texts)
        self._doc_count += n
        return n

    def retrieve(self, query: str, k: int = 5) -> List[RetrievedDocument]:
        self.retrieve_calls.append((query, k))
        return list(self._retrieve_results[:k])

    def clear(self) -> None:
        self._doc_count = 0
        self.add_calls.clear()
        self.retrieve_calls.clear()

    def document_count(self) -> int:
        return self._doc_count

    def delete_by_ids(self, ids: list[str]) -> int:
        if not ids:
            return 0
        # 若 Mock 没有真实 id 存储，可仅用于满足接口：
        self._doc_count = max(0, self._doc_count - len(set(ids)))
        return len(set(ids))
    def delete_by_source(self, source: str) -> int:
        # 占位：与 delete_by_ids 类似，或 return 0
        return 0

    def list_stored_page(
        self,
        offset: int = 0,
        limit: int = 10,
        fetch_fields: StoreField = StoreField.DEFAULT,
    ) -> StoredChunksPage:
        cap = max(1, min(int(limit), 10))
        off = max(0, int(offset))
        total = self._doc_count
        items: list[StoredChunkRecord] = []
        for i in range(off, min(off + cap, total)):
            meta = (
                {"source": "mock.txt", "chunk_idx": i}
                if fetch_fields & StoreField.METADATA
                else None
            )
            doc = f"chunk-body-{i}" if fetch_fields & StoreField.DOCUMENT else None
            emb = [float(i), 0.5] if fetch_fields & StoreField.EMBEDDING else None
            items.append(
                StoredChunkRecord(id=f"mock-id-{i}", metadata=meta, document=doc, embedding=emb)
            )
        return StoredChunksPage(
            items=items,
            total=total,
            offset=off,
            limit=cap,
            persist_directory=None,
            collection_name="mock",
        )

@pytest.fixture
def mock_retriever() -> MockRetriever:
    return MockRetriever()


# ----- index_text -----


def test_index_text_empty_skips_add(mock_retriever: MockRetriever):
    pipe = RAGPipeline(retriever=mock_retriever, chunk_size=100, chunk_overlap=10)
    assert pipe.index_text("   \n  ", source="x.txt") == 0
    assert mock_retriever.add_calls == []
    assert mock_retriever.document_count() == 0


def test_index_text_short_single_chunk_and_metadata(mock_retriever: MockRetriever):
    pipe = RAGPipeline(retriever=mock_retriever, chunk_size=500, chunk_overlap=50)
    n = pipe.index_text("hello rag", source="note.md", metadata={"year": 2024})
    assert n == 1
    assert len(mock_retriever.add_calls) == 1
    call = mock_retriever.add_calls[0]
    assert call["texts"] == ["hello rag"]
    assert call["metadatas"] == [
        {"source": "note.md", "chunk_idx": 0, "year": 2024},
    ]
    assert pipe.document_count() == 1


def test_index_text_splits_chunks(mock_retriever: MockRetriever):
    pipe = RAGPipeline(retriever=mock_retriever, chunk_size=10, chunk_overlap=2)
    text = "a" * 25
    n = pipe.index_text(text, source="paper.txt")
    assert n > 1
    assert len(mock_retriever.add_calls) == 1
    texts = mock_retriever.add_calls[0]["texts"]
    assert all(len(t) <= 10 for t in texts)
    metas = mock_retriever.add_calls[0]["metadatas"]
    assert len(metas) == len(texts)
    for i, m in enumerate(metas):
        assert m["source"] == "paper.txt"
        assert m["chunk_idx"] == i


# ----- index_file（复用 test_document） -----


def test_index_file_minimal_md_matches_load_and_chunk(mock_retriever: MockRetriever):
    path = FIXTURE_DIR / "minimal.md"
    assert path.is_file()
    chunk_size, overlap = 100, 12
    pipe = RAGPipeline(
        retriever=mock_retriever, chunk_size=chunk_size, chunk_overlap=overlap
    )
    expected_chunks, expected_metas = load_and_chunk(
        str(path), chunk_size=chunk_size, overlap=overlap
    )
    n = pipe.index_file(str(path))
    assert n == len(expected_chunks)
    assert len(mock_retriever.add_calls) == 1
    assert mock_retriever.add_calls[0]["texts"] == expected_chunks
    assert mock_retriever.add_calls[0]["metadatas"] == expected_metas


def test_index_file_sample_tex(mock_retriever: MockRetriever):
    path = FIXTURE_DIR / "sample.tex"
    assert path.is_file()
    pipe = RAGPipeline(retriever=mock_retriever, chunk_size=200, chunk_overlap=20)
    n = pipe.index_file(str(path))
    assert n >= 1
    assert mock_retriever.add_calls[0]["metadatas"][0]["source"] == "sample.tex"


def test_index_file_whitespace_no_add(mock_retriever: MockRetriever):
    path = FIXTURE_DIR / "whitespace.txt"
    assert path.is_file()
    pipe = RAGPipeline(retriever=mock_retriever, chunk_size=50, chunk_overlap=5)
    assert pipe.index_file(str(path)) == 0
    assert mock_retriever.add_calls == []


def test_index_file_unsupported_suffix_raises(mock_retriever: MockRetriever):
    path = FIXTURE_DIR / "error.cpp"
    assert path.is_file()
    pipe = RAGPipeline(retriever=mock_retriever)
    with pytest.raises(ValueError):
        pipe.index_file(str(path))


# ----- retrieve / is_ready / clear -----


def test_retrieve_when_not_ready_returns_empty(mock_retriever: MockRetriever):
    pipe = RAGPipeline(retriever=mock_retriever)
    assert pipe.is_ready() is False
    assert pipe.retrieve("anything") == ""


def test_retrieve_formats_documents(mock_retriever: MockRetriever):
    pipe = RAGPipeline(retriever=mock_retriever, chunk_size=500, chunk_overlap=50)
    pipe.index_text("seed", source="seed.txt")
    mock_retriever.set_retrieve_results(
        [
            RetrievedDocument(content="片段甲", source="a.md", score=0.8123),
            RetrievedDocument(content="片段乙", source="b.txt", score=0.5),
        ]
    )
    out = pipe.retrieve("query 关键词")
    assert "【相关片段 1】" in out
    assert "【相关片段 2】" in out
    assert "来源：a.md" in out
    assert "来源：b.txt" in out
    assert "相关度：0.81" in out
    assert "相关度：0.50" in out
    assert "片段甲" in out
    assert "片段乙" in out
    assert "\n\n---\n\n" in out


def test_retrieve_passes_k_to_retriever(mock_retriever: MockRetriever):
    mock_retriever.set_retrieve_results(
        [RetrievedDocument(content="only", source="s", score=1.0)]
    )
    pipe = RAGPipeline(retriever=mock_retriever, chunk_size=100, chunk_overlap=10)
    pipe.index_text("seed", source="s.txt")
    pipe.retrieve("q", k=7)
    assert mock_retriever.retrieve_calls[-1] == ("q", 7)


def test_retrieve_empty_docs_returns_empty_string(mock_retriever: MockRetriever):
    mock_retriever.set_retrieve_results([])
    pipe = RAGPipeline(retriever=mock_retriever, chunk_size=100, chunk_overlap=10)
    pipe.index_text("seed", source="s.txt")
    assert pipe.retrieve("q") == ""


def test_clear_resets_and_pipeline_document_count(mock_retriever: MockRetriever):
    pipe = RAGPipeline(retriever=mock_retriever, chunk_size=100, chunk_overlap=10)
    pipe.index_text("abc", source="t.txt")
    assert pipe.document_count() == 1
    pipe.clear()
    assert pipe.document_count() == 0
    assert mock_retriever.add_calls == []


def test_list_stored_page_delegates_to_retriever(mock_retriever: MockRetriever):
    pipe = RAGPipeline(retriever=mock_retriever, chunk_size=10, chunk_overlap=2)
    pipe.index_text("abcdefghijklm", source="s.txt")  # 多 chunk
    assert pipe.document_count() >= 2
    page = pipe.list_stored_page(offset=0, limit=10, fetch_fields=StoreField.FULL)
    assert page.total == pipe.document_count()
    assert len(page.items) <= 10
    assert page.items[0].document is not None
    assert "chunk-body-0" in page.items[0].document
def test_list_stored_page_offset_and_has_next(mock_retriever: MockRetriever):
    pipe = RAGPipeline(retriever=mock_retriever, chunk_size=5, chunk_overlap=0)
    pipe.index_text("0123456789", source="ten.txt")  # 2 chunks of 5
    page0 = pipe.list_stored_page(offset=0, limit=1, fetch_fields=StoreField.DEFAULT)
    assert len(page0.items) == 1
    assert page0.has_next is True
    page1 = pipe.list_stored_page(offset=1, limit=10, fetch_fields=StoreField.DEFAULT)
    assert len(page1.items) == 1
    assert page1.has_next is False
def test_format_stored_chunks_page_contains_header_and_id(mock_retriever: MockRetriever):
    pipe = RAGPipeline(retriever=mock_retriever, chunk_size=500, chunk_overlap=50)
    pipe.index_text("only", source="one.txt")
    page = pipe.list_stored_page(offset=0, limit=10, fetch_fields=StoreField.DEFAULT)
    text = format_stored_chunks_page(page, StoreField.DEFAULT)
    assert "collection='mock'" in text
    assert "total=1" in text
    assert "mock-id-0" in text
    assert "metadata:" in text