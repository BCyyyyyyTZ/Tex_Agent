# ============================================================
# memory/long_term/vector_store.py
# VectorStore —— 长期记忆向量数据库接口
# ============================================================
# VectorStore 是 NeuroTeX 长期记忆系统的核心存储层，
# 提供统一的向量存储和语义检索接口，屏蔽底层实现差异
# （ChromaDB / FAISS / Weaviate 可互换）。
#
# 【需要实现的内容】
#
# 1. VectorDocument — 存储的文档单元
#    字段:
#    - doc_id: str
#    - content: str              # 原始文本内容
#    - embedding: list[float]    # 向量表示（由 EmbeddingGenerator 生成）
#    - metadata: dict            # 附加元数据（来源、时间、类型等）
#    - collection_name: str      # 所属集合名
#    - created_at: datetime
#
# 2. SearchResult — 检索结果
#    字段:
#    - doc: VectorDocument
#    - score: float              # 相似度分数（越高越相关）
#    - rank: int                 # 排名
#
# 3. VectorStore — 抽象基类（定义统一接口）
#    抽象方法（子类必须实现）:
#    - async add(docs: list[VectorDocument], collection: str) -> list[str]
#    - async search(query_embedding: list[float], collection: str, k: int, filter: dict) -> list[SearchResult]
#    - async delete(doc_ids: list[str], collection: str) -> None
#    - async update(doc_id: str, new_content: str, collection: str) -> None
#    - async create_collection(name: str, metadata: dict) -> None
#    - async delete_collection(name: str) -> None
#    - async count(collection: str) -> int
#
# 4. ChromaVectorStore — ChromaDB 实现
#    - 使用 chromadb.Client() 连接本地持久化存储
#    - 支持 metadata 过滤查询
#    - 使用 "cosine" 相似度度量
#
# 5. FAISSVectorStore — FAISS 实现
#    - 使用 faiss.IndexFlatIP（内积，等效于余弦相似度）
#    - 本地内存/文件存储
#    - 支持 save_index(path) / load_index(path)
#
# 6. VectorStoreFactory — 工厂函数
#    create_vector_store(store_type: str, config: dict) -> VectorStore:
#    - 根据配置返回对应的向量存储实例
#    - 支持 "chroma" / "faiss" / "weaviate"
# ============================================================

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class VectorDocument:
    """向量存储文档单元，【实现字段见上方注释】"""
    doc_id: str = ""
    content: str = ""
    embedding: List[float] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    collection_name: str = "default"
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class SearchResult:
    """向量检索结果，【实现字段见上方注释】"""
    doc: Optional[VectorDocument] = None
    score: float = 0.0
    rank: int = 0


class VectorStore(ABC):
    """
    向量存储抽象基类，定义统一接口。
    所有具体实现（ChromaDB/FAISS/Weaviate）继承此类。
    【完整实现规范见上方注释】
    """

    @abstractmethod
    async def add(
        self,
        docs: List[VectorDocument],
        collection: str = "default",
    ) -> List[str]:
        """添加文档，返回 doc_id 列表，【子类实现】"""
        pass

    @abstractmethod
    async def search(
        self,
        query_embedding: List[float],
        collection: str = "default",
        k: int = 10,
        filter: Optional[Dict[str, Any]] = None,
    ) -> List[SearchResult]:
        """语义检索，【子类实现】"""
        pass

    @abstractmethod
    async def delete(
        self, doc_ids: List[str], collection: str = "default"
    ) -> None:
        """删除文档，【子类实现】"""
        pass

    @abstractmethod
    async def update(
        self, doc_id: str, new_content: str, collection: str = "default"
    ) -> None:
        """更新文档，【子类实现】"""
        pass

    @abstractmethod
    async def create_collection(
        self, name: str, metadata: Optional[Dict] = None
    ) -> None:
        """创建集合，【子类实现】"""
        pass

    @abstractmethod
    async def delete_collection(self, name: str) -> None:
        """删除集合，【子类实现】"""
        pass

    @abstractmethod
    async def count(self, collection: str = "default") -> int:
        """统计文档数量，【子类实现】"""
        pass


class ChromaVectorStore(VectorStore):
    """
    ChromaDB 向量存储实现。
    【需要实现所有抽象方法】
    使用 chromadb 库连接本地持久化存储。
    """

    def __init__(self, persist_dir: str = "./data/chroma_db") -> None:
        # 【需要实现】
        # import chromadb
        # self._client = chromadb.PersistentClient(path=persist_dir)
        # self._collections: dict[str, Any] = {}
        self.persist_dir = persist_dir

    async def add(self, docs, collection="default") -> List[str]:
        """【需要实现】使用 collection.add() 添加文档"""
        pass

    async def search(self, query_embedding, collection="default", k=10, filter=None) -> List[SearchResult]:
        """【需要实现】使用 collection.query() 执行向量检索"""
        pass

    async def delete(self, doc_ids, collection="default") -> None:
        """【需要实现】"""
        pass

    async def update(self, doc_id, new_content, collection="default") -> None:
        """【需要实现】"""
        pass

    async def create_collection(self, name, metadata=None) -> None:
        """【需要实现】"""
        pass

    async def delete_collection(self, name) -> None:
        """【需要实现】"""
        pass

    async def count(self, collection="default") -> int:
        """【需要实现】"""
        pass


class FAISSVectorStore(VectorStore):
    """
    FAISS 向量存储实现（高性能本地检索）。
    【需要实现所有抽象方法】
    使用 faiss.IndexFlatIP 实现内积相似度检索。

    额外方法:
    - save_index(path: str): 将索引保存到文件
    - load_index(path: str): 从文件加载索引
    """

    def __init__(self, embedding_dim: int = 1536) -> None:
        # 【需要实现】
        # import faiss
        # self._index = faiss.IndexFlatIP(embedding_dim)
        # self._doc_store: dict[int, VectorDocument] = {}  # faiss_id -> doc
        # self._id_map: dict[str, int] = {}  # doc_id -> faiss_id
        self.embedding_dim = embedding_dim

    async def add(self, docs, collection="default") -> List[str]:
        """【需要实现】"""
        pass

    async def search(self, query_embedding, collection="default", k=10, filter=None) -> List[SearchResult]:
        """【需要实现】使用 self._index.search() 检索"""
        pass

    async def delete(self, doc_ids, collection="default") -> None:
        """【需要实现】注意 FAISS 不直接支持删除，需要重建索引"""
        pass

    async def update(self, doc_id, new_content, collection="default") -> None:
        """【需要实现】"""
        pass

    async def create_collection(self, name, metadata=None) -> None:
        """【需要实现】FAISS 用独立索引文件模拟集合"""
        pass

    async def delete_collection(self, name) -> None:
        """【需要实现】"""
        pass

    async def count(self, collection="default") -> int:
        """【需要实现】"""
        pass

    def save_index(self, path: str) -> None:
        """保存 FAISS 索引到文件，【需要实现】"""
        pass

    def load_index(self, path: str) -> None:
        """从文件加载 FAISS 索引，【需要实现】"""
        pass


def create_vector_store(store_type: str = "chroma", config: Optional[Dict] = None) -> VectorStore:
    """
    向量存储工厂函数。
    【需要实现】根据 store_type 返回对应实例
    支持 "chroma" / "faiss" / "weaviate"
    """
    pass
