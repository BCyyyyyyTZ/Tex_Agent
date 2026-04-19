"""
RAG 端到端管道实现（可运行）。

RAGPipeline 是 BaseRAGPipeline 的具体实现，整合了：
  1. 文档加载与分块（document_loader.py）
  2. 向量存储与检索（vector_store.py）

面向外部（workflow/nodes.py）暴露两类接口：
  - 索引接口：index_text() / index_file()
  - 检索接口：retrieve()  →  返回可直接注入 Prompt 的格式化字符串

设计原则：
  - 对 nodes.py 依赖 BaseRAGPipeline 而非 RAGPipeline，保证可 Mock
  - 配置通过 config/settings.py 统一管理，不硬编码在此文件
  - retriever 通过构造函数注入，方便单元测试时替换为 MockRetriever
"""
from typing import Optional

from rag.base_retriever import BaseRAGPipeline, BaseRetriever
from rag.document_loader import chunk_text, load_and_chunk
from config.settings import settings
from utils.logger import get_logger

from rag.store_listing import StoreField, StoredChunksPage

logger = get_logger(__name__)


class RAGPipeline(BaseRAGPipeline):
    """
    RAG 检索管道（可运行）。

    Args:
        retriever:    底层向量检索器实例（BaseRetriever 接口）。
                      None 时自动创建 ChromaRetriever（内存模式）。
        chunk_size:   文本分块大小（字符数）。None 时读取 settings.rag_chunk_size。
        chunk_overlap: 分块重叠字符数。None 时读取 settings.rag_chunk_overlap。
        persist_directory: 向量库持久化路径（仅当 retriever=None 时生效）。

    Example:
        # 快速使用（内存模式）
        pipeline = RAGPipeline()
        pipeline.index_text("Transformer 使用多头注意力机制...", source="intro.txt")
        result = pipeline.retrieve("attention mechanism")
        print(result)

        # 持久化模式
        pipeline = RAGPipeline(persist_directory="./knowledge_base")
        pipeline.index_file("papers/survey.md")
        result = pipeline.retrieve("大语言模型综述")
    """

    def __init__(
        self,
        retriever: Optional[BaseRetriever] = None,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
        persist_directory: Optional[str] = None,
    ) -> None:
        if retriever is not None:
            self._retriever = retriever
        else:
            # 延迟导入，避免未安装 chromadb 时在模块加载阶段就崩溃
            from rag.vector_store import ChromaRetriever
            persist_dir = persist_directory or (
                settings.rag_persist_directory if settings.rag_persist_directory else None
            )
            self._retriever = ChromaRetriever(persist_directory=persist_dir)

        self._chunk_size = chunk_size if chunk_size is not None else settings.rag_chunk_size
        self._chunk_overlap = chunk_overlap if chunk_overlap is not None else settings.rag_chunk_overlap

    # ------------------------------------------------------------------ #
    # 索引接口
    # ------------------------------------------------------------------ #

    def index_text(
        self,
        text: str,
        source: str = "",
        metadata: Optional[dict] = None,
    ) -> int:
        """
        对原始文本分块后写入向量库。

        Args:
            text:     待索引的原始文本。
            source:   文本来源标识（文件名、URL 等）。
            metadata: 附加到所有分块的元数据。

        Returns:
            成功索引的文档片段数量。
        """
        chunks = chunk_text(text, chunk_size=self._chunk_size, overlap=self._chunk_overlap)
        if not chunks:
            logger.warning("index_text: 输入文本为空，跳过索引。")
            return 0

        metas = [
            {"source": source, "chunk_idx": i, **(metadata or {})}
            for i in range(len(chunks))
        ]
        count = self._retriever.add_documents(chunks, metas)
        logger.info(f"RAG 索引完成: source={source!r}，共 {count} 个片段")
        return count

    def index_file(self, path: str) -> int:
        """
        加载本地文件，分块后写入向量库。

        Args:
            path: 文件路径（支持 .txt / .md / .tex）。

        Returns:
            成功索引的文档片段数量。

        Raises:
            FileNotFoundError: 文件不存在时。
            ValueError:        文件格式不受支持时。
        """
        chunks, metadatas = load_and_chunk(
            path,
            chunk_size=self._chunk_size,
            overlap=self._chunk_overlap,
        )
        if not chunks:
            logger.warning(f"index_file: 文件内容为空，跳过索引。path={path!r}")
            return 0

        count = self._retriever.add_documents(chunks, metadatas)
        logger.info(f"RAG 文件索引完成: path={path!r}，共 {count} 个片段")
        return count

    # ------------------------------------------------------------------ #
    # 检索接口
    # ------------------------------------------------------------------ #

    def retrieve(self, query: str, k: Optional[int] = None) -> str:
        """
        检索与查询相关的文档片段，返回格式化后的字符串。

        返回的字符串格式设计为可直接嵌入 LLM Prompt 的参考资料段落：
            【相关片段 1】（来源：paper.md）
            ...片段内容...

            ---

            【相关片段 2】（来源：survey.txt）
            ...片段内容...

        Args:
            query: 检索查询文本（通常为用户原始任务描述）。
            k:     返回片段数，None 时使用 settings.rag_top_k。

        Returns:
            格式化检索结果字符串。知识库为空或无相关内容时返回 ""。
        """
        if not self.is_ready():
            return ""

        actual_k = k if k is not None else settings.rag_top_k
        docs = self._retriever.retrieve(query, k=actual_k)

        if not docs:
            return ""

        parts = [
            f"【相关片段 {i + 1}】（来源：{d.source or '未知'}，相关度：{d.score:.2f}）\n{d.content}"
            for i, d in enumerate(docs)
        ]
        return "\n\n---\n\n".join(parts)

    def is_ready(self) -> bool:
        """知识库中有索引内容时返回 True。"""
        return self._retriever.document_count() > 0

    def clear(self) -> None:
        """清空知识库中的所有文档。"""
        self._retriever.clear()
        logger.info("RAG 知识库已清空")

    # ------------------------------------------------------------------ #
    # 工具方法
    # ------------------------------------------------------------------ #

    def document_count(self) -> int:
        """返回当前知识库中的文档片段总数。"""
        return self._retriever.document_count()

    def list_stored_page(
        self,
        offset: int = 0,
        limit: int = 10,
        fetch_fields: StoreField = StoreField.DEFAULT,
    ) -> StoredChunksPage:
        getter = getattr(self._retriever, "list_stored_page", None)
        if getter is None:
            raise NotImplementedError("当前 retriever 不支持 list_stored_page")
        return getter(offset=offset, limit=limit, fetch_fields=fetch_fields)

    def delete_chunks_by_ids(self, ids: list[str]) -> int:
        n = self._retriever.delete_by_ids(ids)
        logger.info(f"RAG 按 id 删除: 请求 {len(ids)} 条, 实际删除 {n} 条")
        return n
    def delete_by_source(self, source: str) -> int:
        getter = getattr(self._retriever, "delete_by_source", None)
        if getter is None:
            raise NotImplementedError("当前 retriever 不支持 delete_by_source")
        n = getter(source)
        logger.info(f"RAG 按来源删除: source={source!r}, 删除 {n} 条")
        return n
