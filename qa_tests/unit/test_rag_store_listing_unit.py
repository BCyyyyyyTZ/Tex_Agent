from __future__ import annotations

from rag.store_listing import (
    StoreField,
    StoredChunkRecord,
    StoredChunksPage,
    format_stored_chunks_page,
)


def test_format_stored_chunks_page__includes_metadata_and_has_next() -> None:
    page = StoredChunksPage(
        items=[StoredChunkRecord(id="1", metadata={"source": "a.txt"})],
        total=10,
        offset=0,
        limit=1,
        collection_name="c",
        persist_directory=None,
    )
    out = format_stored_chunks_page(page, display=StoreField.DEFAULT)
    assert "collection=" in out
    assert "has_next=True" in out
    assert "metadata" in out

