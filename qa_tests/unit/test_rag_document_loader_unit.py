from __future__ import annotations

from pathlib import Path

import pytest

from rag.document_loader import chunk_text, load_and_chunk, load_text_file


def test_chunk_text__empty_returns_empty() -> None:
    assert chunk_text("") == []
    assert chunk_text("   ") == []


def test_chunk_text__overlap_step_guard() -> None:
    txt = "x" * 50
    chunks = chunk_text(txt, chunk_size=10, overlap=20)
    assert chunks
    assert all(1 <= len(c) <= 10 for c in chunks)


def test_load_text_file__reads_utf8(tmp_path: Path) -> None:
    p = tmp_path / "a.txt"
    p.write_text("hello", encoding="utf-8")
    assert load_text_file(str(p)) == "hello"


def test_load_and_chunk__unsupported_suffix_rejected(tmp_path: Path) -> None:
    p = tmp_path / "a.pdf"
    p.write_bytes(b"%PDF-1.4")
    with pytest.raises(ValueError):
        load_and_chunk(str(p))


def test_load_and_chunk__returns_chunks_and_metadatas(tmp_path: Path) -> None:
    p = tmp_path / "a.md"
    p.write_text("A" * 30, encoding="utf-8")
    chunks, metas = load_and_chunk(str(p), chunk_size=10, overlap=0)
    assert len(chunks) == 3
    assert len(metas) == 3
    assert metas[0]["source"] == "a.md"
    assert metas[0]["chunk_idx"] == 0

