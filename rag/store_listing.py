"""
RAG 向量库「列举」的数据结构与纯展示函数。

- 查询/分页：由 ChromaRetriever / RAGPipeline 填充 StoredChunksPage
- 格式化：format_stored_chunks_page（供其它模块先查询再打印）
- 打印：print_stored_chunks_page（命令行或脚本）
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from enum import Flag, auto
from typing import Any, List, Optional, TextIO


DEFAULT_LIST_PAGE_SIZE = 5
MAX_LIST_PAGE_SIZE = 5


class StoreField(Flag):
    """控制从向量库拉取以及打印时包含哪些信息。"""

    ID = auto()
    METADATA = auto()
    DOCUMENT = auto()
    EMBEDDING = auto()

    # 常用组合
    MINIMAL = ID
    DEFAULT = ID | METADATA
    FULL = ID | METADATA | DOCUMENT | EMBEDDING


def store_fields_for_fetch(display: StoreField) -> StoreField:
    """打印需要 DOCUMENT 时，拉取阶段必须包含 DOCUMENT。"""
    return display


@dataclass
class StoredChunkRecord:
    id: str
    metadata: Optional[dict] = None
    document: Optional[str] = None
    embedding: Optional[List[float]] = None


@dataclass
class StoredChunksPage:
    """一页列举结果（最多 10 条由调用方 limit 保证）。"""

    items: List[StoredChunkRecord] = field(default_factory=list)
    total: int = 0
    offset: int = 0
    limit: int = DEFAULT_LIST_PAGE_SIZE
    persist_directory: Optional[str] = None
    collection_name: str = ""

    @property
    def has_next(self) -> bool:
        return self.offset + len(self.items) < self.total


def _truncate(s: str, max_len: int) -> str:
    if max_len <= 0 or len(s) <= max_len:
        return s
    return s[: max_len - 3] + "..."


def format_stored_chunks_page(
    page: StoredChunksPage,
    display: StoreField = StoreField.DEFAULT,
    *,
    document_max_chars: int = 2000,
    embedding_preview_dims: int = 8,
) -> str:
    """将一页结果格式化为多行文本（不写 stdout）。"""
    lines: List[str] = []
    header = (
        f"collection={page.collection_name!r}  "
        f"total={page.total}  offset={page.offset}  limit={page.limit}  "
        f"returned={len(page.items)}  has_next={page.has_next}"
    )
    if page.persist_directory:
        header += f"\npersist_directory={page.persist_directory!r}"
    lines.append(header)
    lines.append("-" * 72)

    for i, rec in enumerate(page.items):
        lines.append(f"[{page.offset + i + 1}/{page.total}] id={rec.id!r}")
        if display & StoreField.METADATA:
            lines.append(f"  metadata: {rec.metadata!r}")
        if display & StoreField.DOCUMENT:
            doc = rec.document
            if doc is None:
                lines.append("  document: <not loaded>")
            else:
                lines.append(f"  document:\n{_truncate(doc, document_max_chars)}")
        if display & StoreField.EMBEDDING:
            emb = rec.embedding
            if emb is None:
                lines.append("  embedding: <not loaded>")
            else:
                prev = emb[:embedding_preview_dims]
                lines.append(
                    f"  embedding: dim={len(emb)} preview={prev!r} ..."
                )
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def print_stored_chunks_page(
    page: StoredChunksPage,
    display: StoreField = StoreField.DEFAULT,
    *,
    document_max_chars: int = 2000,
    embedding_preview_dims: int = 8,
    stream: TextIO = sys.stdout,
) -> None:
    """格式化并打印到 stream（默认 stdout）。"""
    stream.write(
        format_stored_chunks_page(
            page,
            display,
            document_max_chars=document_max_chars,
            embedding_preview_dims=embedding_preview_dims,
        )
    )