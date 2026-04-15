"""store_listing 纯函数单元测试。"""
from rag.store_listing import (
    StoreField,
    StoredChunkRecord,
    StoredChunksPage,
    format_stored_chunks_page,
)


def test_format_truncates_long_document():
    page = StoredChunksPage(
        items=[
            StoredChunkRecord(
                id="x",
                metadata={"source": "a.txt"},
                document="A" * 100,
                embedding=None,
            )
        ],
        total=1,
        offset=0,
        limit=10,
        persist_directory="/tmp/kb",
        collection_name="tex_agent",
    )
    out = format_stored_chunks_page(
        page, StoreField.DOCUMENT, document_max_chars=20
    )
    assert "..." in out


def test_has_next_false_when_last_page():
    page = StoredChunksPage(
        items=[StoredChunkRecord(id="a", metadata={})],
        total=1,
        offset=0,
        limit=10,
        collection_name="c",
    )
    assert page.has_next is False