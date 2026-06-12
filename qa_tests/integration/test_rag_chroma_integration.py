from __future__ import annotations

import pytest


@pytest.mark.integration
def test_chroma_retriever__add_retrieve_and_list_default(tmp_path) -> None:
    try:
        from rag.vector_store import ChromaRetriever
        from rag.store_listing import StoreField
    except ImportError as e:
        pytest.skip(str(e))

    try:
        r = ChromaRetriever(persist_directory=str(tmp_path))
    except Exception as e:  # noqa: BLE001
        pytest.skip(str(e))

    n = r.add_documents(["hello world"], [{"source": "a.txt"}])
    assert n == 1
    docs = r.retrieve("hello", k=1)
    assert docs
    assert "hello" in docs[0].content.lower()

    page = r.list_stored_page(offset=0, limit=1, fetch_fields=StoreField.DEFAULT)
    assert page.total >= 1
    assert page.items

