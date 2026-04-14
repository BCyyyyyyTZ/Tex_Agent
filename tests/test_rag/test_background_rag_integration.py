"""
Background.tex 的 RAG 集成测试：索引 → 检索 → 清空。

默认::

    pytest tests/test_rag/test_background_rag_integration.py -v -m integration

真实 knowledge_base（会 clear 整库）::

    pytest tests/test_rag/test_background_rag_integration.py -v -m integration --rag-db-mode=real
"""
from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest

from rag.document_loader import load_and_chunk
from rag.rag_pipeline import RAGPipeline

pytestmark = pytest.mark.integration

FIXTURE_DIR = Path(__file__).resolve().parent / "test_document"
BACKGROUND_TEX = FIXTURE_DIR / "Background.tex"
# tests/test_rag -> tests -> 包根（含 config、rag、knowledge_base）
_PACKAGE_ROOT = Path(__file__).resolve().parents[2]
KNOWLEDGE_BASE_DIR = _PACKAGE_ROOT / "knowledge_base"

CHUNK_SIZE = 500
CHUNK_OVERLAP = 50


def _skip_if_disabled() -> None:
    if os.getenv("SKIP_CHROMA_INTEGRATION", "").strip().lower() in ("1", "true", "yes"):
        pytest.skip("SKIP_CHROMA_INTEGRATION is set")


def _require_chromadb() -> None:
    pytest.importorskip("chromadb")


def _queries_and_expected_substrings() -> list[tuple[str, str]]:
    """(query, 期望出现在 retrieve 结果中的子串) — 均来自 Background.tex 正文。"""
    return [
        (
            "What is LoRA low rank adaptation in large models?",
            "Low-rank adaptation (LoRA)",
        ),
        (
            "vision language models multimodal visual encoder",
            "Vision language models (VLMs)",
        ),
        (
            "Punica S-LoRA batch heterogeneous adapters GPU",
            "Punica",
        ),
    ]


def _assert_background_retrieval(p: RAGPipeline) -> None:
    assert p.is_ready() is True
    assert p.document_count() > 0
    out = ""
    for query, needle in _queries_and_expected_substrings():
        out = p.retrieve(query, k=8)
        assert out, f"retrieve 不应为空: query={query!r}"
        assert needle in out, f"期望命中正文片段 {needle!r}，query={query!r}"
    assert "Background.tex" in out


def test_background_tex_index_retrieve_clear_tmp_path(tmp_path: Path) -> None:
    """默认：临时 Chroma 目录，写入 Background.tex → 检索 → clear。"""
    _skip_if_disabled()
    _require_chromadb()
    assert BACKGROUND_TEX.is_file(), f"夹具缺失: {BACKGROUND_TEX}"

    db_dir = tmp_path / f"chroma_bg_{uuid.uuid4().hex}"
    db_dir.mkdir(parents=True, exist_ok=True)
    p = RAGPipeline(
        persist_directory=str(db_dir),
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )

    expected_chunks, _ = load_and_chunk(
        str(BACKGROUND_TEX),
        chunk_size=CHUNK_SIZE,
        overlap=CHUNK_OVERLAP,
    )
    n = p.index_file(str(BACKGROUND_TEX))
    assert n == len(expected_chunks)
    assert p.document_count() == len(expected_chunks)

    _assert_background_retrieval(p)

    p.clear()
    assert p.document_count() == 0
    assert p.is_ready() is False
    assert p.retrieve("LoRA adaptation edge server", k=5) == ""


def test_background_tex_real_knowledge_base(pytestconfig: pytest.Config) -> None:
    """
    仅 ``--rag-db-mode=real``：使用包根下 ``knowledge_base``，不自动 index；最后 clear 整库。
    """
    if pytestconfig.getoption("--rag-db-mode") != "real":
        pytest.skip("使用 --rag-db-mode=real 时再跑本用例")

    _skip_if_disabled()
    _require_chromadb()

    persist = str(KNOWLEDGE_BASE_DIR.resolve())
    if not KNOWLEDGE_BASE_DIR.is_dir():
        pytest.skip(f"目录不存在: {persist}")

    p = RAGPipeline(
        persist_directory=persist,
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )
    if not p.is_ready() or p.document_count() == 0:
        pytest.skip(
            "knowledge_base 为空；请先索引 test_document/Background.tex 后再跑 --rag-db-mode=real"
        )

    try:
        _assert_background_retrieval(p)
    finally:
        p.clear()

    assert p.document_count() == 0
    assert p.is_ready() is False
    assert p.retrieve("LoRA vision edge", k=5) == ""