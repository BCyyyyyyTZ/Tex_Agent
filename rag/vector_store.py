"""
基于 ChromaDB 的本地向量检索器实现（可运行）。

ChromaDB 是一个轻量级嵌入式向量数据库，无需独立服务进程，
所有数据可存储在内存中（EphemeralClient）或本地磁盘（PersistentClient）。

默认 Embedding 模型：
    ChromaDB 内置的 DefaultEmbeddingFunction，基于 all-MiniLM-L6-v2（ONNX Runtime）。
    首次运行时会自动下载约 40MB 的 ONNX 模型文件到本地缓存，需要联网。
    模型下载完成后完全离线运行，无需 API Key。

[扩展] 替换 Embedding 的方式：
    在初始化时传入自定义 embedding_fn，例如：
    from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
    custom_fn = OpenAIEmbeddingFunction(api_key="...", model_name="text-embedding-ada-002")
    retriever = ChromaRetriever(embedding_fn=custom_fn)

依赖：
    pip install chromadb>=0.5.0

TODO: 未来增加对 FAISS / Qdrant / Weaviate 的适配实现
TODO: 未来增加批量删除接口 delete_by_source(source_name)
"""
import uuid
from typing import List, Optional

try:
    import chromadb
    from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
    _CHROMA_AVAILABLE = True
except ImportError:
    _CHROMA_AVAILABLE = False

from rag.base_retriever import BaseRetriever, RetrievedDocument

from rag.store_listing import StoreField, StoredChunkRecord, StoredChunksPage, DEFAULT_LIST_PAGE_SIZE, MAX_LIST_PAGE_SIZE


def _chroma_sequence(raw: dict, key: str) -> list:
    v = raw.get(key)
    if v is None:
        return []
    try:
        return list(v)
    except TypeError:
        return []
def _embedding_to_list(emb):
    if emb is None:
        return None
    if hasattr(emb, "tolist"):
        return [float(x) for x in emb.tolist()]
    return [float(x) for x in list(emb)]

def _check_chromadb() -> None:
    """检查 chromadb 是否已安装，未安装时给出清晰的错误提示。"""
    if not _CHROMA_AVAILABLE:
        raise ImportError(
            "RAG 功能需要安装 chromadb：\n"
            "    pip install chromadb>=0.5.0\n"
            "安装完成后重新运行即可。"
        )


class ChromaRetriever(BaseRetriever):
    """
    基于 ChromaDB 的本地向量检索器（可运行）。

    Args:
        collection_name:   ChromaDB 集合名称（相当于向量库中的"表"）。
        persist_directory: 持久化存储路径。None 表示使用内存模式（进程退出后数据丢失）。
        embedding_fn:      自定义 Embedding 函数。None 时使用 ChromaDB 默认 Embedding。

    Example:
        # 内存模式（测试用）
        retriever = ChromaRetriever()
        retriever.add_documents(["关于 Transformer 的研究..."], [{"source": "paper.txt"}])
        docs = retriever.retrieve("注意力机制", k=3)

        # 持久化模式（生产用）
        retriever = ChromaRetriever(persist_directory="./chroma_data")
    """

    def __init__(
        self,
        collection_name: str = "tex_agent",
        persist_directory: Optional[str] = None,
        embedding_fn=None,
    ) -> None:
        _check_chromadb()

        if persist_directory:
            self._client = chromadb.PersistentClient(path=persist_directory)
        else:
            self._client = chromadb.EphemeralClient()

        self._embedding_fn = embedding_fn or DefaultEmbeddingFunction()
        self._collection_name = collection_name
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            embedding_function=self._embedding_fn,
        )
        self._persist_directory = persist_directory  # Optional[str]，内存模式为 None

    def add_documents(
        self,
        texts: List[str],
        metadatas: Optional[List[dict]] = None,
    ) -> int:
        """
        批量向 ChromaDB 集合添加文档，每条文档自动生成唯一 UUID 作为 ID。

        ChromaDB 会自动调用 embedding_fn 对文本向量化并存储。
        """
        if not texts:
            return 0

        ids = [str(uuid.uuid4()) for _ in texts]
        metas = metadatas if metadatas is not None else [{} for _ in texts]

        self._collection.add(
            documents=texts,
            ids=ids,
            metadatas=metas,
        )
        return len(texts)

    def retrieve(self, query: str, k: int = 5) -> List[RetrievedDocument]:
        """
        向 ChromaDB 执行近邻搜索，返回最相关的文档片段列表。

        ChromaDB 默认使用 L2 距离，距离越小越相关。
        这里将距离转换为相似度分数：score = 1 / (1 + distance)。
        """
        total = self.document_count()
        if total == 0:
            return []

        actual_k = min(k, total)
        results = self._collection.query(
            query_texts=[query],
            n_results=actual_k,
            include=["documents", "metadatas", "distances"],
        )

        documents: List[RetrievedDocument] = []
        for i, doc_text in enumerate(results["documents"][0]):
            raw_meta = results["metadatas"][0][i] if results.get("metadatas") else {}
            meta = dict(raw_meta) if isinstance(raw_meta, dict) else {}
            rid = ""
            try:
                rid = str((results.get("ids") or [[]])[0][i] or "")
            except Exception:
                rid = ""
            if rid:
                meta["_id"] = rid
            distance = results["distances"][0][i] if results.get("distances") else 1.0
            score = 1.0 / (1.0 + distance)

            documents.append(
                RetrievedDocument(
                    content=doc_text,
                    source=meta.get("source", ""),
                    score=round(score, 4),
                    metadata=meta,
                )
            )

        documents.sort(key=lambda d: d.score, reverse=True)
        return documents

    def clear(self) -> None:
        """删除并重新创建集合，实现清空所有文档的效果。"""
        self._client.delete_collection(self._collection_name)
        self._collection = self._client.get_or_create_collection(
            name=self._collection_name,
            embedding_function=self._embedding_fn,
        )

    def document_count(self) -> int:
        """返回当前集合中存储的文档片段数量。"""
        return self._collection.count()

    def delete_by_ids(self, ids: list[str]) -> int:
        """按 id 批量删除；空列表返回 0。"""
        if not ids:
            return 0
        # 去重且去掉空串
        uniq = list({str(i).strip() for i in ids if str(i).strip()})
        if not uniq:
            return 0
        # Chroma: delete 不存在的 id 通常不报错
        self._collection.delete(ids=uniq)
        return len(uniq)
    def delete_by_source(self, source: str) -> int:
        """删除 metadata.source == source 的所有记录。"""
        if not source:
            return 0
        raw = self._collection.get(
            where={"source": source},
            include=[],
        )
        id_list = list(raw.get("ids") or [])
        if not id_list:
            return 0
        self._collection.delete(ids=id_list)
        return len(id_list)

    def list_stored_page(
        self,
        offset: int = 0,
        limit: int = 10,
        fetch_fields: StoreField = StoreField.DEFAULT,
    ) -> StoredChunksPage:
        _check_chromadb()
        total = self.document_count()
        cap = max(1, min(int(limit), MAX_LIST_PAGE_SIZE))
        off = max(0, int(offset))
        include: List[str] = []
        if fetch_fields & StoreField.METADATA:
            include.append("metadatas")
        if fetch_fields & StoreField.DOCUMENT:
            include.append("documents")
        if fetch_fields & StoreField.EMBEDDING:
            include.append("embeddings")
        if not include:
            include = ["metadatas"]  # Chroma 通常至少要 metadatas 或 documents
        raw = self._collection.get(
            include=include,
            limit=cap,
            offset=off,
        )
        ids = _chroma_sequence(raw, "ids")
        metas = _chroma_sequence(raw, "metadatas")
        docs = _chroma_sequence(raw, "documents")
        embs = _chroma_sequence(raw, "embeddings")
        items: List[StoredChunkRecord] = []
        for i, rid in enumerate(ids):
            meta = metas[i] if i < len(metas) else None
            doc = docs[i] if i < len(docs) and (fetch_fields & StoreField.DOCUMENT) else None
            _embedding_to_list(embs[i]) if i < len(embs) and (fetch_fields & StoreField.EMBEDDING) else None
            if not (fetch_fields & StoreField.DOCUMENT):
                doc = None
            if not (fetch_fields & StoreField.EMBEDDING):
                emb = None
            items.append(
                StoredChunkRecord(id=str(rid), metadata=meta, document=doc, embedding=emb)
            )
        return StoredChunksPage(
            items=items,
            total=total,
            offset=off,
            limit=cap,
            persist_directory=self._persist_directory,
            collection_name=self._collection_name,
        )
