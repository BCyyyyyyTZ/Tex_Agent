"""
RAG（检索增强生成）模块。

提供文档索引、向量检索、检索管道的完整实现，
以及对应的抽象接口，支持未来扩展为多类别知识库（论文库、专家库等）。

可运行组件:
    ChromaRetriever  - 基于 ChromaDB 的本地向量检索器
    RAGPipeline      - 文档索引 + 检索的端到端管道

[扩展] 接口:
    BaseRetriever    - 向量检索器抽象基类
    BaseRAGPipeline  - 检索管道抽象基类
"""
from rag.base_retriever import BaseRetriever, BaseRAGPipeline, RetrievedDocument
from rag.document_parse import DoclingParseResult, parse_document_to_dir, resolve_source_path
from rag.rag_pipeline import RAGPipeline

__all__ = [
    "BaseRetriever",
    "BaseRAGPipeline",
    "RetrievedDocument",
    "RAGPipeline",
    "DoclingParseResult",
    "parse_document_to_dir",
    "resolve_source_path",
]
