# ============================================================
# rag/processors/embedding_generator.py
# EmbeddingGenerator —— 文本嵌入向量生成器
# ============================================================
# EmbeddingGenerator 将文本块转换为稠密向量表示，
# 支持多种嵌入模型，并提供批量处理和缓存优化。
#
# 【需要实现的内容】
#
# 1. EmbeddingModel — 枚举，支持的嵌入模型
#    - OPENAI_SMALL   # text-embedding-3-small（1536维）
#    - OPENAI_LARGE   # text-embedding-3-large（3072维）
#    - SENTENCE_BERT  # sentence-transformers/all-MiniLM-L6-v2（本地）
#    - BGE_BASE       # BAAI/bge-base-en-v1.5（本地，学术优化）
#
# 2. EmbeddingGenerator 类
#
#    初始化:
#    - model: EmbeddingModel
#    - batch_size: int = 32         # 批量生成时每批大小
#    - cache_enabled: bool = True   # 是否缓存嵌入向量
#    - _cache: dict                 # text_hash -> embedding
#
#    核心方法:
#
#    async embed(text: str) -> list[float]:
#    - 生成单条文本的嵌入向量
#    - 先查缓存，缓存未命中再调用模型
#
#    async embed_batch(
#        texts: list[str], show_progress: bool = False
#    ) -> list[list[float]]:
#    - 批量生成嵌入向量（按 batch_size 分批调用）
#    - 支持进度条显示
#
#    async embed_chunks(
#        chunks: list[Chunk]
#    ) -> list[VectorDocument]:
#    - 为 Chunk 列表生成嵌入，返回 VectorDocument 列表
#    - 直接用于存入向量存储
#
#    get_dimension() -> int:
#    - 返回当前模型的向量维度
#
#    _get_cache_key(text: str) -> str:
#    - 生成文本的 MD5 哈希作为缓存键
#
#    _call_openai_api(texts: list[str]) -> list[list[float]]:
#    - 调用 OpenAI Embedding API
#
#    _call_local_model(texts: list[str]) -> list[list[float]]:
#    - 调用本地 sentence-transformers 模型
# ============================================================

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional


class EmbeddingModel(str, Enum):
    """支持的嵌入模型，【实现见上方注释】"""
    OPENAI_SMALL = "text-embedding-3-small"
    OPENAI_LARGE = "text-embedding-3-large"
    SENTENCE_BERT = "sentence-transformers/all-MiniLM-L6-v2"
    BGE_BASE = "BAAI/bge-base-en-v1.5"


class EmbeddingGenerator:
    """
    文本嵌入向量生成器。
    支持多模型切换，内置缓存和批量处理优化。
    【完整实现规范见上方注释】
    """

    MODEL_DIMENSIONS: Dict[str, int] = {
        "text-embedding-3-small": 1536,
        "text-embedding-3-large": 3072,
        "sentence-transformers/all-MiniLM-L6-v2": 384,
        "BAAI/bge-base-en-v1.5": 768,
    }

    def __init__(
        self,
        model: EmbeddingModel = EmbeddingModel.OPENAI_SMALL,
        batch_size: int = 32,
        cache_enabled: bool = True,
    ) -> None:
        self.model = model
        self.batch_size = batch_size
        self.cache_enabled = cache_enabled
        self._cache: Dict[str, List[float]] = {}

    async def embed(self, text: str) -> List[float]:
        """生成单条文本嵌入，【需要实现】"""
        pass

    async def embed_batch(
        self, texts: List[str], show_progress: bool = False
    ) -> List[List[float]]:
        """批量生成嵌入向量，【需要实现】"""
        pass

    async def embed_chunks(self, chunks: List[Any]) -> List[Any]:
        """为 Chunk 列表生成嵌入，返回 VectorDocument 列表，【需要实现】"""
        pass

    def get_dimension(self) -> int:
        """返回当前模型的向量维度，【需要实现】"""
        pass

    def _get_cache_key(self, text: str) -> str:
        """生成缓存键，【需要实现】"""
        pass

    async def _call_openai_api(
        self, texts: List[str]
    ) -> List[List[float]]:
        """调用 OpenAI Embedding API，【需要实现】"""
        pass

    def _call_local_model(
        self, texts: List[str]
    ) -> List[List[float]]:
        """调用本地 sentence-transformers 模型，【需要实现】"""
        pass
