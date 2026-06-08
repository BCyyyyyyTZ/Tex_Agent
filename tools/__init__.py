"""
tools 包的公开 API 导出。

该包聚合了项目中可供 Agent/Workflow 调用的工具实现（BaseTool 子类）。
工具的统一返回结构是 core.message.ToolResult。
"""

from tools.base_tool import BaseTool
from tools.arxiv_tool import ArxivSearchTool
from tools.docling_tool import DoclingParseTool
from tools.chart_plot_tool import ChartPlotTool
from core.message import ToolResult

__all__ = ["BaseTool", "ToolResult", "ArxivSearchTool", "PdfCommentTool", "FileLoadingTool", "CommandRunningTool", "DoclingParseTool", "ChartPlotTool"]
