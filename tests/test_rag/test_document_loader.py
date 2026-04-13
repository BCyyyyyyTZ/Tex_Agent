"""
document_loader 纯函数单元测试（不依赖向量库 / Chroma）。

夹具目录：与本文件同级的 test_document/
运行（在项目根 Tex_Agent/ 下）：
    pytest tests/test_rag/test_document_loader.py -v
    pytest tests/test_rag/test_document_loader.py --cov=rag.document_loader --cov-report=term-missing
"""
from pathlib import Path

import pytest

from rag.document_loader import chunk_text, load_and_chunk, load_text_file

FIXTURE_DIR = Path(__file__).resolve().parent / "test_document"



# chunk_text
def test_chunk_empty_string():
    assert chunk_text("") == []


def test_chunk_whitespace_only():
    assert chunk_text("   \n\t  ") == []


def test_chunk_strips_outer_whitespace():
    text = "  hello  "
    assert chunk_text(text, chunk_size=100) == ["hello"]


def test_chunk_short_returns_single_element():
    assert chunk_text("abc", chunk_size=10) == ["abc"]


def test_chunk_exact_chunk_size_single_block():
    s = "a" * 20
    assert chunk_text(s, chunk_size=20, overlap=0) == [s]


def test_chunk_length_plus_one_yields_two_blocks():
    s = "a" * 21
    chunks = chunk_text(s, chunk_size=20, overlap=5)
    assert len(chunks) == 2
    assert len(chunks[0]) == 20
    assert chunks[1] == "a" * 6


def test_chunk_overlap_semantics_between_adjacent_blocks():
    """相邻块尾部 overlap 与下一块头部应一致。"""
    text = "0123456789" * 10  # 100 字符
    chunk_size, overlap = 25, 5
    chunks = chunk_text(text, chunk_size=chunk_size, overlap=overlap)
    assert len(chunks) >= 2
    for i in range(len(chunks) - 1):
        assert chunks[i][-overlap:] == chunks[i + 1][:overlap]


def test_chunk_when_overlap_geq_chunk_size_uses_fallback_step():
    """step = chunk_size - overlap <= 0 时，step 退化为 max(1, chunk_size//2)。"""
    chunk_size, overlap = 10, 15
    text = "b" * 23
    chunks = chunk_text(text, chunk_size=chunk_size, overlap=overlap)
    assert len(chunks) >= 2
    assert all(len(c) <= chunk_size for c in chunks)
    assert text.startswith(chunks[0])
    assert chunks[-1][-1] == "b"


def test_chunk_unicode_mixed():
    s = "中文ABC" * 15
    chunks = chunk_text(s, chunk_size=10, overlap=2)
    assert chunks
    assert all(len(c) <= 10 for c in chunks)
    assert s.strip().startswith(chunks[0])
    assert s.strip().endswith(chunks[-1])


def test_chunk_uses_long_line_fixture():
    path = FIXTURE_DIR / "long_line.txt"
    assert path.is_file(), f"缺少夹具: {path}"
    raw = path.read_text(encoding="utf-8")
    chunks = chunk_text(raw, chunk_size=80, overlap=10)
    assert len(chunks) >= 2
    assert all(len(c) <= 80 for c in chunks)
    assert "START" in chunks[0]
    assert "END" in chunks[-1]


# load_text_file
def test_load_text_file_not_found():
    missing = FIXTURE_DIR / "does_not_exist_42.txt"
    with pytest.raises(FileNotFoundError) as exc:
        load_text_file(str(missing))
    assert str(missing) in str(exc.value) or "不存在" in str(exc.value)


def test_load_text_file_minimal_md():
    path = FIXTURE_DIR / "minimal.md"
    content = load_text_file(str(path))
    assert "RAG" in content or "测试" in content
    assert len(content) > 0


def test_load_text_file_sample_tex():
    path = FIXTURE_DIR / "sample.tex"
    content = load_text_file(str(path))
    assert "\\documentclass" in content or "Introduction" in content


def test_load_text_file_empty_tmp(tmp_path: Path):
    p = tmp_path / "empty.txt"
    p.write_text("", encoding="utf-8")
    assert load_text_file(str(p)) == ""


def test_load_text_file_non_utf8_raises(tmp_path: Path):
    p = tmp_path / "latin1.txt"
    p.write_bytes(b"caf\xe9")  # é in latin-1, invalid UTF-8
    with pytest.raises(UnicodeDecodeError):
        load_text_file(str(p))


# load_and_chunk
def test_load_and_chunk_not_found():
    missing = FIXTURE_DIR / "missing_file_xyz.md"
    with pytest.raises(FileNotFoundError):
        load_and_chunk(str(missing))


def test_load_and_chunk_unsupported_suffix():
    path = FIXTURE_DIR / "error.cpp"
    assert path.is_file()
    with pytest.raises(ValueError) as exc:
        load_and_chunk(str(path))
    assert ".cpp" in str(exc.value)
    assert "不支持" in str(exc.value)


def test_load_and_chunk_whitespace_file_empty_chunks():
    path = FIXTURE_DIR / "whitespace.txt"
    chunks, metas = load_and_chunk(str(path))
    assert chunks == []
    assert metas == []


def test_load_and_chunk_matches_chunk_text_of_file_content():
    """与先 read_text 再 chunk_text 的结果一致；元数据逐块对应。"""
    for name, chunk_size, overlap in [
        ("minimal.md", 120, 15),
        ("sample.tex", 200, 20),
        ("long_line.txt", 60, 8),
    ]:
        path = FIXTURE_DIR / name
        assert path.is_file(), f"缺少夹具: {path}"
        chunks, metas = load_and_chunk(str(path), chunk_size=chunk_size, overlap=overlap)
        content = path.read_text(encoding="utf-8")
        expected = chunk_text(content, chunk_size=chunk_size, overlap=overlap)
        assert chunks == expected
        assert len(metas) == len(chunks)
        for i, meta in enumerate(metas):
            assert meta == {"source": path.name, "chunk_idx": i}


def test_load_and_chunk_uppercase_suffix(tmp_path: Path):
    src = FIXTURE_DIR / "minimal.md"
    dst = tmp_path / "copy.MD"
    dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    chunks, metas = load_and_chunk(str(dst), chunk_size=500, overlap=50)
    assert isinstance(chunks, list)
    assert len(metas) == len(chunks)
    if chunks:
        assert metas[0]["source"] == "copy.MD"