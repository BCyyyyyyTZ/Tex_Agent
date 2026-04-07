"""
ArxivSearchTool 单元测试。
使用 Mock 隔离 arXiv API 网络调用，验证工具的基础行为与错误处理。
"""
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime

from tools.arxiv_tool import ArxivSearchTool
from core.message import ToolResult


def _make_mock_paper(title: str, author_count: int = 2) -> MagicMock:
    """
    创建 Mock arXiv 论文对象，模拟 arxiv.Result 的结构。

    Args:
        title: 论文标题。
        author_count: 作者数量。
    """
    paper = MagicMock()
    paper.title = title
    paper.authors = [
        MagicMock(name=f"Author{i}") for i in range(author_count)
    ]
    for i, author in enumerate(paper.authors):
        author.name = f"Author {i + 1}"
    paper.published = datetime(2024, 3, 15)
    paper.entry_id = f"https://arxiv.org/abs/2403.{hash(title) % 100000:05d}"
    paper.summary = f"This paper presents research on {title}. " * 10
    return paper


class TestArxivSearchTool:
    """ArxivSearchTool 基础行为测试套件。"""

    def setup_method(self):
        """每个测试方法前，创建工具实例（max_results=3）。"""
        self.tool = ArxivSearchTool(max_results=3)

    def test_tool_name(self):
        """验证工具名称符合规范。"""
        assert self.tool.name == "arxiv_search"

    def test_tool_description_not_empty(self):
        """验证工具描述为非空字符串。"""
        assert isinstance(self.tool.description, str)
        assert len(self.tool.description) > 10

    def test_run_returns_tool_result_on_success(self):
        """验证检索成功时返回正确的 ToolResult。"""
        mock_papers = [
            _make_mock_paper("Attention Is All You Need"),
            _make_mock_paper("BERT: Pre-training of Deep Bidirectional Transformers"),
        ]
        with patch.object(self.tool._client, "results", return_value=iter(mock_papers)):
            result = self.tool.run("transformer attention mechanism")

        assert isinstance(result, ToolResult)
        assert result.success is True
        assert result.error is None
        assert "Attention Is All You Need" in result.output
        assert result.metadata["count"] == 2
        assert result.metadata["query"] == "transformer attention mechanism"

    def test_run_formats_output_correctly(self):
        """验证输出格式包含预期的关键信息字段。"""
        mock_papers = [_make_mock_paper("Test Paper Title")]
        with patch.object(self.tool._client, "results", return_value=iter(mock_papers)):
            result = self.tool.run("test query")

        assert "Test Paper Title" in result.output
        assert "Author 1" in result.output
        assert "2024-03-15" in result.output
        assert "arxiv.org" in result.output

    def test_run_handles_empty_results(self):
        """验证无检索结果时返回 success=True 且包含提示信息。"""
        with patch.object(self.tool._client, "results", return_value=iter([])):
            result = self.tool.run("xyzabc_nonexistent_topic_99999")

        assert isinstance(result, ToolResult)
        assert result.success is True
        assert "未找到" in result.output
        assert result.metadata["count"] == 0

    def test_run_returns_failure_on_exception(self):
        """验证网络或 API 异常时返回 success=False 的 ToolResult。"""
        with patch.object(
            self.tool._client, "results", side_effect=Exception("Connection timeout")
        ):
            result = self.tool.run("transformer")

        assert isinstance(result, ToolResult)
        assert result.success is False
        assert result.output == ""
        assert result.error is not None
        assert "Connection timeout" in result.error

    def test_run_truncates_long_abstracts(self):
        """验证超长摘要会被截断处理。"""
        paper = _make_mock_paper("Paper With Long Abstract")
        paper.summary = "A" * 1000  # 超长摘要

        with patch.object(self.tool._client, "results", return_value=iter([paper])):
            result = self.tool.run("test")

        assert result.success is True
        # 截断后不应在输出中出现完整的 1000 个 A
        assert result.output.count("A") < 1000

    def test_run_handles_many_authors(self):
        """验证超过 3 位作者时正确显示简略格式。"""
        paper = _make_mock_paper("Multi-Author Paper", author_count=8)
        with patch.object(self.tool._client, "results", return_value=iter([paper])):
            result = self.tool.run("test")

        assert result.success is True
        assert "等 8 位作者" in result.output

    @pytest.mark.asyncio
    async def test_arun_works_correctly(self):
        """验证异步接口 arun() 正常工作。"""
        mock_papers = [_make_mock_paper("Async Test Paper")]
        with patch.object(self.tool._client, "results", return_value=iter(mock_papers)):
            result = await self.tool.arun("async test")

        assert isinstance(result, ToolResult)
        assert result.success is True
