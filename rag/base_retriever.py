"""
RAG 模块抽象接口定义。

包含两层抽象：
  1. BaseRetriever  - 底层向量检索器（面向向量库的增删查接口）
  2. BaseRAGPipeline - 高层检索管道（面向业务的索引+检索接口）

遵循框架"基于接口编程"原则：
  - workflow/nodes.py 的 make_retrieve_node 依赖 BaseRAGPipeline，
    不依赖具体的 RAGPipeline 实现，方便后续 Mock 测试和替换实现。
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional
from rag.store_listing import StoreField, StoredChunksPage


@dataclass
class RetrievedDocument:
    """
    单条检索结果的数据容器。

    Attributes:
        content: 文档片段的文本内容。
        source:  来源文件名或 URL，用于引用标注。
        score:   相关性分数（0~1，越高越相关）。
        metadata: 附加元数据（如 chunk 序号、原文页码等）。
    """

    content: str
    source: str = ""
    score: float = 0.0
    metadata: dict = field(default_factory=dict)


class BaseRetriever(ABC):
    """
    向量检索器抽象基类（低层接口）。

    职责：封装对具体向量数据库（ChromaDB / FAISS / Weaviate 等）的
    增删查操作，屏蔽各向量库的 API 差异。

    [扩展] 实现建议：
        - 继承此类，在 __init__ 中初始化向量库连接和 Embedding 模型。
        - add_documents 负责将文本向量化并写入库。
        - retrieve 负责将查询向量化并执行近邻搜索。

    TODO: 未来增加 delete_documents(ids) 接口，支持文档的单条删除
    TODO: 未来增加 get_document(id) 接口，支持按 ID 精确查询
    """

    @abstractmethod
    def add_documents(
        self,
        texts: List[str],
        metadatas: Optional[List[dict]] = None,
    ) -> int:
        """
        向向量库中批量添加文档。

        Args:
            texts:     文档文本列表（已完成分块）。
            metadatas: 与 texts 一一对应的元数据列表。None 表示无元数据。

        Returns:
            成功添加的文档数量。

        Raises:
            NotImplementedError: 子类必须实现。
        """
        raise NotImplementedError

    @abstractmethod
    def retrieve(self, query: str, k: int = 5) -> List[RetrievedDocument]:
        """
        根据查询文本检索最相关的文档片段。

        Args:
            query: 检索查询文本。
            k:     返回结果数量上限。

        Returns:
            按相关性降序排列的 RetrievedDocument 列表。

        Raises:
            NotImplementedError: 子类必须实现。
        """
        raise NotImplementedError

    @abstractmethod
    def clear(self) -> None:
        """
        清空向量库中的所有文档。

        Raises:
            NotImplementedError: 子类必须实现。
        """
        raise NotImplementedError

    @abstractmethod
    def document_count(self) -> int:
        """
        返回当前向量库中存储的文档片段总数。

        Returns:
            文档片段数量（int）。

        Raises:
            NotImplementedError: 子类必须实现。
        """
        raise NotImplementedError

    def list_stored_page(
        self,
        offset: int = 0,
        limit: int = 10,
        fetch_fields: StoreField = StoreField.DEFAULT,
    ) -> StoredChunksPage:
        """
        分页列举当前向量库中的记录（纯数据，不做打印）。
        默认实现：子类未实现时抛出 NotImplementedError。
        """
        raise NotImplementedError(
            f"{type(self).__name__} 未实现 list_stored_page"
        )

    @abstractmethod
    def delete_by_ids(self, ids: list[str]) -> int:
        """
        按 Chroma 存储 id 删除若干条 chunk（幂等：不存在的 id 忽略）。
        Args:
            ids: 文档片段 id 列表（与 list_stored_page 返回的 StoredChunkRecord.id 一致）。
        Returns:
            实际删除的条数（以底层库返回值或成功删除计数为准）。
        """
        raise NotImplementedError
    def delete_by_source(self, source: str) -> int:
        """
        删除 metadata 中 source 等于给定值的所有 chunk。
        默认未实现；ChromaRetriever 可覆盖。不需要按来源删除时可不实现子类。
        """
        raise NotImplementedError(
            f"{type(self).__name__} 未实现 delete_by_source"
        )

class BaseRAGPipeline(ABC):
    """
    检索管道抽象基类（高层接口）。

    职责：将文档加载、分块、向量化（索引）和检索
    组合为一个面向业务的端到端管道。

    这是 workflow/nodes.py 依赖的接口，而非 BaseRetriever。
    遵循"高层模块依赖抽象"的设计原则，确保：
      - 测试时可以传入 Mock 实现，无需真实向量库
      - 生产时可以无缝切换 ChromaDB / FAISS 等底层实现

    TODO: 未来增加 async_retrieve(query) 接口，支持异步检索
    TODO: 未来增加 batch_retrieve(queries) 接口，支持多查询并发
    TODO: 未来增加 hybrid_retrieve(query, bm25_weight) 接口，支持混合检索
    """

    @abstractmethod
    def index_text(
        self,
        text: str,
        source: str = "",
        metadata: Optional[dict] = None,
    ) -> int:
        """
        对原始文本进行分块并写入向量库。

        Args:
            text:     待索引的原始文本内容。
            source:   文本来源标识（文件名、URL 等），用于引用标注。
            metadata: 附加到所有分块的元数据。

        Returns:
            成功索引的文档片段数量。

        Raises:
            NotImplementedError: 子类必须实现。
        """
        raise NotImplementedError

    @abstractmethod
    def index_file(self, path: str) -> int:
        """
        加载本地文件，分块后写入向量库。

        支持格式：.txt / .md / .tex（PDF 支持为 [扩展] 功能）。

        Args:
            path: 文件绝对路径或相对路径。

        Returns:
            成功索引的文档片段数量。

        Raises:
            FileNotFoundError: 文件不存在时。
            ValueError:        文件格式不受支持时。
            NotImplementedError: 子类必须实现。
        """
        raise NotImplementedError

    @abstractmethod
    def retrieve(self, query: str, k: Optional[int] = None) -> str:
        """
        检索与查询最相关的文档片段，并格式化为可直接注入 Prompt 的字符串。

        Args:
            query: 检索查询文本（通常为用户原始任务描述）。
            k:     返回片段数，None 时使用配置默认值。

        Returns:
            格式化的多段检索结果字符串，已包含来源标注。
            知识库为空或无相关内容时返回空字符串 ""。

        Raises:
            NotImplementedError: 子类必须实现。
        """
        raise NotImplementedError

    @abstractmethod
    def is_ready(self) -> bool:
        """
        检查知识库是否已有索引内容（是否可以进行检索）。

        Returns:
            True 表示已有文档可检索，False 表示知识库为空。

        Raises:
            NotImplementedError: 子类必须实现。
        """
        raise NotImplementedError

    @abstractmethod
    def clear(self) -> None:
        """
        清空知识库中的所有文档索引。

        Raises:
            NotImplementedError: 子类必须实现。
        """
        raise NotImplementedError
    
    @abstractmethod
    def delete_chunks_by_ids(self, ids: list[str]) -> int:
        """按向量库中的 chunk id 删除若干条。"""
        raise NotImplementedError
    @abstractmethod
    def delete_by_source(self, source: str) -> int:
        """删除某一来源（如文件名）下的全部 chunk。"""
        raise NotImplementedError
