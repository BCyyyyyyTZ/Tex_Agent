"""
工具注册表（tool_list）。

该文件负责集中实例化并注册所有可供 Agent/Workflow 调用的工具。

约定：
- key 为工具对外暴露的名称（tool_name）
- value 为对应的 BaseTool 实例

新增工具的步骤通常是：
1) 在 tools/ 目录实现 BaseTool 子类
2) 在此处 import 并加入 tool_list 字典
"""

from tools.arxiv_tool import ArxivSearchTool
from tools.pdf_comment_tool import PdfCommentTool
from tools.file_loading_tool import FileLoadingTool
from tools.command_running_tool import CommandRunningTool
from tools.docling_tool import DoclingParseTool
from tools.chart_plot_tool import ChartPlotTool
from tools.concept_diagram_tool import ConceptDiagramTool
from tools.latex_autofix_tool import LatexAutoFixTool
tool_list = {
    "arxiv_search": ArxivSearchTool(),
    "pdf_comment": PdfCommentTool(),
    "file_loading": FileLoadingTool(),
    "command_running": CommandRunningTool(),
    "docling_parse": DoclingParseTool(),
    "chart_plot": ChartPlotTool(),
    "concept_diagram": ConceptDiagramTool(),
    "latex_autofix": LatexAutoFixTool(),
}
