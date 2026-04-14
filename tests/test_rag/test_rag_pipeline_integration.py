"""
真实 ChromaRetriever + RAGPipeline 集成测试（embedding / 索引 / 检索）。

- 标记：pytest.mark.integration
- 跳过：环境变量 SKIP_CHROMA_INTEGRATION=1，或未安装 chromadb
- 隔离：每个用例使用 tmp_path 下独立持久化目录

仅跑本文件集成测试：
    pytest tests/test_rag/test_rag_pipeline_integration.py -v -m integration
排除集成测试：
    pytest -m "not integration"
"""
from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest

from rag.document_loader import chunk_text, load_and_chunk
from rag.rag_pipeline import RAGPipeline

pytestmark = pytest.mark.integration

FIXTURE_DIR = Path(__file__).resolve().parent / "test_document"


def _skip_if_disabled() -> None:
    if os.getenv("SKIP_CHROMA_INTEGRATION", "").strip().lower() in ("1", "true", "yes"):
        pytest.skip("SKIP_CHROMA_INTEGRATION is set")


def _require_chromadb() -> None:
    pytest.importorskip("chromadb")


def _fragment_count(formatted: str) -> int:
    return formatted.count("【相关片段")


def _make_pipeline(
    tmp_path: Path,
    chunk_size: int = 500,
    chunk_overlap: int = 50,
) -> RAGPipeline:
    _skip_if_disabled()
    _require_chromadb()
    db_dir = tmp_path / f"chroma_{uuid.uuid4().hex}"
    db_dir.mkdir(parents=True, exist_ok=True)
    return RAGPipeline(
        persist_directory=str(db_dir),
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )


@pytest.fixture
def isolated_pipeline(tmp_path: Path) -> RAGPipeline:
    return _make_pipeline(tmp_path)


# ----- C-A：生命周期与空库 -----


def test_empty_library_not_ready_and_retrieve_blank(isolated_pipeline: RAGPipeline):
    p = isolated_pipeline
    assert p.is_ready() is False
    assert p.retrieve("anything") == ""
    assert p.document_count() == 0


def test_index_then_ready_and_count(isolated_pipeline: RAGPipeline):
    p = isolated_pipeline
    n = p.index_text("single chunk doc", source="one.txt")
    assert n == 1
    assert p.is_ready() is True
    assert p.document_count() == 1


def test_clear_resets_library(isolated_pipeline: RAGPipeline):
    p = isolated_pipeline
    p.index_text("data", source="d.txt")
    assert p.document_count() >= 1
    p.clear()
    assert p.document_count() == 0
    assert p.is_ready() is False
    assert p.retrieve("data") == ""


# ----- C-B：索引与分块 -----


def test_index_long_text_chunk_count_matches_document_loader(tmp_path: Path):
    p = _make_pipeline(tmp_path, chunk_size=40, chunk_overlap=8)
    text = "w" * 220
    expected_n = len(chunk_text(text, chunk_size=40, overlap=8))
    n = p.index_text(text, source="long.txt")
    assert n == expected_n
    assert p.document_count() == expected_n


def test_index_file_minimal_md(tmp_path: Path):
    path = FIXTURE_DIR / "minimal.md"
    assert path.is_file()
    p = _make_pipeline(tmp_path, chunk_size=100, chunk_overlap=12)
    expected_chunks, _ = load_and_chunk(str(path), chunk_size=100, overlap=12)
    n = p.index_file(str(path))
    assert n == len(expected_chunks)
    assert p.document_count() == len(expected_chunks)
    out = p.retrieve("RAG 向量检索 测试", k=5)
    assert out
    assert "minimal.md" in out or "【相关片段" in out


# ----- C-C：检索、k、弱查询 -----


def test_retrieve_format_and_k_bound(isolated_pipeline: RAGPipeline):
    p = isolated_pipeline
    body = "alpha " * 80
    p.index_text(body, source="bulk.txt", metadata={"kind": "bulk"})
    out = p.retrieve("alpha repeated tokens", k=2)
    assert out
    assert "【相关片段" in out
    assert "来源：" in out
    assert "相关度：" in out
    assert _fragment_count(out) <= 2


def test_retrieve_k_larger_than_collection(tmp_path: Path):
    p = _make_pipeline(tmp_path, chunk_size=30, chunk_overlap=5)
    text = "z" * 120
    p.index_text(text, source="many_chunks.txt")
    total = p.document_count()
    assert total >= 2
    out = p.retrieve("z chunk", k=10)
    if out:
        assert _fragment_count(out) <= min(10, total)


def test_retrieve_unrelated_query_no_crash(isolated_pipeline: RAGPipeline):
    p = isolated_pipeline
    p.index_text("hello small library", source="h.txt")
    q = "xyzqwertyunlikelytoken" * 5 + " quantum gravity string theory formalism"
    out = p.retrieve(q, k=5)
    assert isinstance(out, str)


# ----- C-D：多主题 + 语义区分 -----


def _seed_four_topics(p: RAGPipeline) -> None:
    p.index_text(
        "Basketball NBA courts and scoring games sport league UNIQUE_SPORT_BASKET",
        source="sport.txt",
    )
    p.index_text(
        "Photosynthesis chloroplast sunlight plants glucose energy UNIQUE_BIO_PHOTOSYN",
        source="bio.txt",
    )
    p.index_text(
        "TCP UDP internet protocol packets routing layers UNIQUE_NET_TCP",
        source="net.txt",
    )
    p.index_text(
        "Matrix multiplication linear algebra vectors spaces UNIQUE_MATH_MATMUL",
        source="math.txt",
    )


def test_semantic_retrieve_bio_topic(isolated_pipeline: RAGPipeline):
    p = isolated_pipeline
    _seed_four_topics(p)
    out = p.retrieve(
        "chlorophyll sunlight plant photosynthesis glucose energy",
        k=8,
    )
    assert "UNIQUE_BIO_PHOTOSYN" in out


def test_semantic_retrieve_net_topic(isolated_pipeline: RAGPipeline):
    p = isolated_pipeline
    _seed_four_topics(p)
    out = p.retrieve(
        "IP routing network protocol UDP TCP packets internet",
        k=8,
    )
    assert "UNIQUE_NET_TCP" in out


def test_semantic_retrieve_math_topic(isolated_pipeline: RAGPipeline):
    p = isolated_pipeline
    _seed_four_topics(p)
    out = p.retrieve(
        "linear algebra matrix vector multiplication eigenvalue",
        k=8,
    )
    assert "UNIQUE_MATH_MATMUL" in out


def test_semantic_retrieve_sport_topic(isolated_pipeline: RAGPipeline):
    p = isolated_pipeline
    _seed_four_topics(p)
    out = p.retrieve(
        "NBA basketball court scoring league game sport",
        k=8,
    )
    assert "UNIQUE_SPORT_BASKET" in out


# ----- C-E：持久化 — 新 Pipeline 实例可读同一目录 -----


def test_persistence_second_pipeline_sees_data(tmp_path: Path):
    _skip_if_disabled()
    _require_chromadb()
    db_dir = tmp_path / "persist_shared"
    db_dir.mkdir(parents=True, exist_ok=True)
    path_str = str(db_dir)

    p1 = RAGPipeline(persist_directory=path_str, chunk_size=200, chunk_overlap=20)
    p1.index_text(
        "persistence check hello world UNIQUE_PERSIST_XYZ marker",
        source="persist.txt",
    )
    assert p1.is_ready()

    p2 = RAGPipeline(persist_directory=path_str, chunk_size=200, chunk_overlap=20)
    assert p2.is_ready()
    out = p2.retrieve("persistence hello marker", k=3)
    assert "UNIQUE_PERSIST_XYZ" in out