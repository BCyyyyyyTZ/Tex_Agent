"""
RAG 模块单元测试。

使用 MockRetriever 替代真实 ChromaDB，实现：
  1. 不依赖 chromadb 安装即可运行
  2. 测试执行速度极快（无 I/O 操作）
  3. 验证 RAGPipeline 的业务逻辑正确性

测试覆盖：
  - RAGPipeline 基础功能（索引、检索、清空）
  - 知识库空时的边界处理
  - 文档分块逻辑（chunk_text）
  - 检索结果格式化输出
  - make_retrieve_node 节点函数的状态更新正确性
"""
import pytest

from rag.base_retriever import BaseRetriever, RetrievedDocument, BaseRAGPipeline
from rag.document_loader import chunk_text, load_and_chunk
from rag.rag_pipeline import RAGPipeline
from workflow.nodes import make_retrieve_node
from memory.context_manager import ContextManager


# ------------------------------------------------------------------ #
# Mock 实现（不依赖 chromadb）
# ------------------------------------------------------------------ #

class MockRetriever(BaseRetriever):
    """用于测试的内存 Mock 检索器，不依赖任何外部库。"""

    def __init__(self):
        self._docs: list = []

    def add_documents(self, texts, metadatas=None):
        metas = metadatas or [{} for _ in texts]
        for text, meta in zip(texts, metas):
            self._docs.append({"text": text, "meta": meta})
        return len(texts)

    def retrieve(self, query: str, k: int = 5):
        results = self._docs[:k]
        return [
            RetrievedDocument(
                content=d["text"],
                source=d["meta"].get("source", ""),
                score=0.85,
                metadata=d["meta"],
            )
            for d in results
        ]

    def clear(self):
        self._docs.clear()

    def document_count(self) -> int:
        return len(self._docs)


# ------------------------------------------------------------------ #
# chunk_text 测试
# ------------------------------------------------------------------ #

class TestChunkText:
    """文本分块逻辑测试。"""

    def test_short_text_returns_single_chunk(self):
        """短文本（≤ chunk_size）应直接作为单个 chunk 返回。"""
        text = "这是一段短文本。"
        chunks = chunk_text(text, chunk_size=500)
        assert chunks == [text]

    def test_empty_text_returns_empty_list(self):
        """空字符串应返回空列表，不产生无效 chunk。"""
        assert chunk_text("") == []
        assert chunk_text("   ") == []

    def test_long_text_produces_multiple_chunks(self):
        """长文本应切割为多个 chunk。"""
        text = "A" * 1200
        chunks = chunk_text(text, chunk_size=500, overlap=50)
        assert len(chunks) > 1

    def test_chunk_size_respected(self):
        """每个 chunk 的长度不应超过 chunk_size。"""
        text = "X" * 2000
        chunks = chunk_text(text, chunk_size=300, overlap=30)
        for chunk in chunks:
            assert len(chunk) <= 300

    def test_overlap_creates_continuity(self):
        """相邻 chunk 之间应有重叠内容，确保上下文连续。"""
        text = "ABCDE" * 100  # 500 个字符
        chunks = chunk_text(text, chunk_size=200, overlap=50)
        if len(chunks) >= 2:
            # chunk[0] 末尾 50 字符应出现在 chunk[1] 开头区域
            end_of_first = chunks[0][-50:]
            assert end_of_first in chunks[1]


# ------------------------------------------------------------------ #
# RAGPipeline 测试
# ------------------------------------------------------------------ #

class TestRAGPipeline:
    """RAGPipeline 端到端业务逻辑测试。"""

    def setup_method(self):
        """每个测试前创建新的 pipeline 实例（使用 MockRetriever）。"""
        self.retriever = MockRetriever()
        self.pipeline = RAGPipeline(retriever=self.retriever)

    def test_is_ready_false_when_empty(self):
        """知识库为空时 is_ready() 应返回 False。"""
        assert self.pipeline.is_ready() is False

    def test_is_ready_true_after_indexing(self):
        """索引文档后 is_ready() 应返回 True。"""
        self.pipeline.index_text("关于 Transformer 注意力机制的研究。")
        assert self.pipeline.is_ready() is True

    def test_index_text_returns_chunk_count(self):
        """index_text 应返回实际写入的片段数量（≥ 1）。"""
        count = self.pipeline.index_text("一段关于论文写作的文本内容，用于测试索引功能是否正常工作。")
        assert count >= 1

    def test_index_empty_text_returns_zero(self):
        """索引空字符串时不应写入任何片段，返回 0。"""
        count = self.pipeline.index_text("")
        assert count == 0

    def test_retrieve_returns_empty_when_not_ready(self):
        """知识库为空时 retrieve() 应返回空字符串。"""
        result = self.pipeline.retrieve("transformer 架构")
        assert result == ""

    def test_retrieve_returns_formatted_string(self):
        """索引后 retrieve() 应返回带格式标注的字符串。"""
        self.pipeline.index_text(
            "Transformer 使用多头自注意力机制处理序列数据。",
            source="paper.txt",
        )
        result = self.pipeline.retrieve("注意力机制")
        assert "相关片段" in result
        assert "paper.txt" in result

    def test_retrieve_contains_indexed_content(self):
        """检索结果应包含被索引的文本内容。"""
        self.pipeline.index_text("BERT 是双向 Transformer 编码器的预训练模型。")
        result = self.pipeline.retrieve("BERT")
        assert "BERT" in result

    def test_clear_resets_knowledge_base(self):
        """clear() 后知识库应回到空状态，is_ready() 返回 False。"""
        self.pipeline.index_text("一些测试内容。")
        assert self.pipeline.is_ready() is True
        self.pipeline.clear()
        assert self.pipeline.is_ready() is False

    def test_document_count_increments_after_indexing(self):
        """多次索引后 document_count() 应正确累加。"""
        before = self.pipeline.document_count()
        self.pipeline.index_text("第一段文本内容。")
        self.pipeline.index_text("第二段文本内容。")
        after = self.pipeline.document_count()
        assert after > before

    def test_index_text_with_long_content_creates_multiple_chunks(self):
        """超出 chunk_size 的长文本应被切割为多个片段分别写入。"""
        long_text = "这是一段非常长的文本内容。" * 50  # 远超 500 字符
        count = self.pipeline.index_text(long_text, source="long_doc.txt")
        assert count > 1


# ------------------------------------------------------------------ #
# make_retrieve_node 测试
# ------------------------------------------------------------------ #

class TestRetrieveNode:
    """retrieve_node 节点函数的状态更新测试。"""

    def _make_state(self, query: str = "测试查询") -> dict:
        """构建最小化的 WorkflowState 字典。"""
        return {
            "messages": [],
            "current_node": "",
            "input": query,
            "output": "",
            "error": None,
            "metadata": {},
            "retrieved_context": "",
        }

    def test_retrieve_node_skips_when_empty(self):
        """知识库为空时，节点应跳过检索并返回空 retrieved_context。"""
        retriever = MockRetriever()
        pipeline = RAGPipeline(retriever=retriever)
        ctx = ContextManager()
        node_fn = make_retrieve_node(pipeline, ctx)

        result = node_fn(self._make_state())

        assert result["retrieved_context"] == ""
        assert result["current_node"] == "retrieve"
        assert result["error"] is None

    def test_retrieve_node_returns_content_when_ready(self):
        """知识库有内容时，节点应返回非空 retrieved_context。"""
        retriever = MockRetriever()
        pipeline = RAGPipeline(retriever=retriever)
        pipeline.index_text("Transformer 注意力机制是深度学习的重要突破。")
        ctx = ContextManager()
        node_fn = make_retrieve_node(pipeline, ctx)

        result = node_fn(self._make_state("注意力机制"))

        assert result["retrieved_context"] != ""
        assert result["current_node"] == "retrieve"
        assert result["error"] is None

    def test_retrieve_node_error_handling(self):
        """检索异常时，节点应捕获错误，返回空 context 并记录 error，不抛出异常。"""
        class BrokenRetriever(MockRetriever):
            def retrieve(self, query, k=5):
                raise RuntimeError("模拟向量库连接失败")

        retriever = BrokenRetriever()
        retriever.add_documents(["占位文档"])  # 使 is_ready() 为 True
        pipeline = RAGPipeline(retriever=retriever)
        ctx = ContextManager()
        node_fn = make_retrieve_node(pipeline, ctx)

        result = node_fn(self._make_state())

        assert result["retrieved_context"] == ""
        assert result["current_node"] == "retrieve"
        assert result["error"] is not None
        assert "模拟向量库连接失败" in result["error"]


# ------------------------------------------------------------------ #
# load_and_chunk 测试（文件 I/O，需要临时文件）
# ------------------------------------------------------------------ #

class TestLoadAndChunk:
    """文档加载与分块功能测试。"""

    def test_load_txt_file(self, tmp_path):
        """应能正确加载 .txt 文件并分块。"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("这是测试文本内容。" * 20, encoding="utf-8")

        chunks, metadatas = load_and_chunk(str(test_file), chunk_size=50, overlap=5)

        assert len(chunks) > 0
        assert all(m["source"] == "test.txt" for m in metadatas)
        assert all("chunk_idx" in m for m in metadatas)

    def test_load_md_file(self, tmp_path):
        """应能正确加载 .md 文件。"""
        test_file = tmp_path / "readme.md"
        test_file.write_text("# 标题\n\n这是一段 Markdown 文本。", encoding="utf-8")

        chunks, metadatas = load_and_chunk(str(test_file))

        assert len(chunks) >= 1

    def test_unsupported_format_raises_error(self, tmp_path):
        """不支持的文件格式应抛出 ValueError。"""
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"fake pdf content")

        with pytest.raises(ValueError, match="不支持的文件格式"):
            load_and_chunk(str(test_file))

    def test_nonexistent_file_raises_error(self):
        """不存在的文件应抛出 FileNotFoundError。"""
        with pytest.raises(FileNotFoundError):
            load_and_chunk("/nonexistent/path/file.txt")

    def test_chunk_metadatas_have_sequential_indices(self, tmp_path):
        """每个 chunk 的 chunk_idx 元数据应从 0 开始连续递增。"""
        test_file = tmp_path / "long.txt"
        test_file.write_text("内容" * 200, encoding="utf-8")  # 400 字符

        chunks, metadatas = load_and_chunk(str(test_file), chunk_size=100, overlap=10)

        indices = [m["chunk_idx"] for m in metadatas]
        assert indices == list(range(len(chunks)))
