"""
ArxivSearchTool：调用 arXiv API 进行学术文献检索（可运行）。
这是框架中第一个完整实现的工具，验证 BaseTool 接口的正确性与可用性。
"""
from typing import List, Optional

import arxiv

from tools.base_tool import BaseTool
from core.message import ToolResult
from config.settings import settings
from utils.logger import get_logger

logger = get_logger(__name__)


class ArxivSearchTool(BaseTool):
    """
    arXiv 学术文献检索工具。

    调用 arXiv 官方 Python SDK 进行基于关键词的文献检索，
    返回格式化的论文列表（标题、作者、摘要、发表时间、链接）。

    Args:
        max_results: 最大检索结果数，默认使用 settings.arxiv_max_results 的配置值。

    Example:
        tool = ArxivSearchTool(max_results=5)
        result = tool.run("large language model survey")
        print(result.output)
    """

    def __init__(self, max_results: Optional[int] = None):
        super().__init__(
            name="arxiv_search",
            description="在 arXiv 平台检索论文。输入关键词或论文主题（英文效果最佳），返回相关论文的标题、作者、摘要和链接。",
            input_schema={
                "query": "用户输入的关键词或论文主题（英文效果最佳）"
            }
        )
        self._max_results = max_results if max_results is not None else settings.arxiv_max_results
        self._client = arxiv.Client()


    def _format_results(self, results: List[arxiv.Result]) -> str:
        """将 arXiv 检索结果格式化为可读的文本字符串。"""
        if not results:
            raise RuntimeError("未找到相关论文。")

        lines = [f"共检索到 {len(results)} 篇相关论文：\n"]
        for i, paper in enumerate(results, 1):
            # 处理作者列表（超过3位显示"等N位作者"）
            authors = ", ".join(a.name for a in paper.authors[:3])
            if len(paper.authors) > 3:
                authors += f" 等 {len(paper.authors)} 位作者"

            # 截断过长摘要
            abstract = paper.summary.replace("\n", " ").strip()
            if len(abstract) > 250:
                abstract = abstract[:250] + "..."

            lines.append(f"【{i}】{paper.title}")
            lines.append(f"   作者：{authors}")
            lines.append(f"   发表：{paper.published.strftime('%Y-%m-%d')}")
            lines.append(f"   链接：{paper.entry_id}")
            lines.append(f"   摘要：{abstract}")
            lines.append("")

        return "\n".join(lines)

    def run(self, query: str) -> ToolResult:
        """
        执行 arXiv 文献检索。

        Args:
            query: 检索关键词或论文主题描述（建议使用英文以获得最佳结果）。

        Returns:
            ToolResult，成功时 output 为格式化的论文列表文本，
            失败时 success=False 且 error 字段包含错误信息。
        """
        logger.info(f"arXiv 检索启动 | 查询: {query!r} | 最大结果数: {self._max_results}")
        try:
            search = arxiv.Search(
                query=query,
                max_results=self._max_results,
                sort_by=arxiv.SortCriterion.Relevance,
            )
            results = list(self._client.results(search))
            formatted = self._format_results(results)

            logger.info(f"arXiv 检索完成，返回 {len(results)} 篇论文")
            return ToolResult(
                success=True,
                output=formatted,
                metadata={
                    "query": query,
                    "result_num": len(results),
                },
            )

        except Exception as e:
            logger.error(f"arXiv 检索失败: {e}")
            return ToolResult(
                success=False,
                output=None,
                error=f"{e}",
                metadata={"query": query},
            )
