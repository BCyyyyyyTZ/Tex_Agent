"""
[扩展] 向量知识库接口定义（高层、面向多类别 RAG 场景）。

架构说明
--------
本框架现有两层 RAG 相关接口，职责不同，请勿混淆：

  ┌─ memory/vector_store.py（本文件）─────────────────────────────────────┐
  │  VectorStoreBase：高层、面向"多类别知识库管理"场景的接口。              │
  │  操作单位是 Document 对象（含 doc_id / content / metadata）。           │
  │  适用于：论文资料库、专家经验库、用户自定义库等多库并存的场景。          │
  │  目前仅为 [扩展] 占位，尚无可运行实现。                                 │
  └────────────────────────────────────────────────────────────────────────┘

  ┌─ rag/base_retriever.py ────────────────────────────────────────────────┐
  │  BaseRetriever：低层、面向"向量库增删查"操作的接口。                     │
  │  操作单位是原始文本字符串（List[str]）。                                 │
  │  BaseRAGPipeline：高层检索管道接口，封装分块+索引+检索全流程。           │
  │  RAGPipeline（可运行）：基于 ChromaDB 的具体实现，已在工作流中集成。     │
  └────────────────────────────────────────────────────────────────────────┘

开发者 D 建议
-------------
  - 当前阶段：直接使用 rag/rag_pipeline.py 的 RAGPipeline 实现即可。
  - 若需要多类别知识库（论文库 + 专家库 + 用户库 分库存储、按类别过滤检索），
    则在本文件中实现 VectorStoreBase，并在 rag/rag_pipeline.py 内部使用它。
  - 注意保持接口语义一致：VectorStoreBase.add_documents() 接收 List[Document]，
    BaseRetriever.add_documents() 接收 List[str]，两者互补不冲突。

TODO: 开发者 D 负责实现此类（建议在 RAGPipeline 基础上扩展多库支持）
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Document:
    """
    知识库文档数据结构。

    Attributes:
        doc_id: 文档唯一标识符（建议使用 UUID 或文件名 hash）。
        content: 文档文本内容（通常经过切分处理）。
        metadata: 文档元数据（来源、类别、作者、时间戳等）。
        embedding: 向量嵌入（懒加载，添加到向量库时填充）。
    """

    doc_id: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    embedding: Optional[List[float]] = None


@dataclass
class SearchResult:
    """
    向量检索单条结果。

    Attributes:
        document: 匹配的文档对象。
        score: 相似度分数（0~1，越高越相关）。
    """

    document: Document
    score: float


class VectorStoreBase(ABC):
    """
    [扩展] 向量知识库抽象基类。

    功能规划：
        1. 多类别 RAG 支持：
           - 检索论文资料库（arXiv 下载的论文 PDF 解析后入库）
           - 专家经验知识库（领域专家总结的写作经验）
           - 用户自定义资源库（用户上传的参考文献、笔记等）
        2. 文档向量化存储与高效语义检索
        3. 支持多种向量库后端（Chroma / FAISS / Pinecone）

    TODO: 开发者 D 实现建议：
          - 优先实现基于 Chroma（本地）的版本（pip install chromadb）
          - Embedding 模型推荐：OpenAI text-embedding-3-small 或 BGE-M3
          - 文档切分策略参考 LangChain 的 RecursiveCharacterTextSplitter
    """

    @abstractmethod
    def add_documents(self, documents: List[Document]) -> List[str]:
        """
        向知识库添加文档并完成向量化存储。

        Args:
            documents: 需要添加的文档列表（content 已完成切分）。

        Returns:
            成功添加的文档 ID 列表。

        Raises:
            NotImplementedError: 子类必须实现。
        """
        raise NotImplementedError

    @abstractmethod
    def search(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[SearchResult]:
        """
        语义检索最相关的文档。

        Args:
            query: 检索查询文本（自然语言）。
            top_k: 返回的最大结果数，默认 5。
            filters: 元数据过滤条件（如 {"category": "paper", "year": "2024"}）。

        Returns:
            按相似度降序排列的 SearchResult 列表。

        Raises:
            NotImplementedError: 子类必须实现。
        """
        raise NotImplementedError

    @abstractmethod
    def delete_document(self, doc_id: str) -> bool:
        """
        删除指定文档。

        Args:
            doc_id: 要删除的文档 ID。

        Returns:
            True 表示删除成功，False 表示文档不存在。

        Raises:
            NotImplementedError: 子类必须实现。
        """
        raise NotImplementedError

    @abstractmethod
    def clear(self) -> None:
        """清空知识库所有内容（谨慎使用）。"""
        raise NotImplementedError

    # TODO: 未来增加 update_document(doc_id, new_content) 接口，支持文档更新
    # TODO: 未来增加 add_from_file(file_path, category) 接口，
    #       支持 PDF/LaTeX 文件批量解析并导入
    # TODO: 未来增加 get_stats() 接口，返回知识库规模统计信息
