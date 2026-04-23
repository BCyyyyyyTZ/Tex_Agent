from tools.arxiv_tool import ArxivSearchTool
from tools.pdf_comment_tool import PdfCommentTool
from tools.file_loading_tool import FileLoadingTool
from tools.command_running_tool import CommandRunningTool
from tools.docling_tool import DoclingParseTool
from tools.docling_search_tool import DoclingSearchTool
from tools.markdown_section_tool import MarkdownSectionTool
from tools.pymupdf_parse_tool import PyMuPDFParseTool
from tools.chapter_index_tool import ChapterIndexTool
from tools.ref_checker_tool import RefCheckerTool
from tools.figure_ref_checker_tool import FigureRefCheckerTool
from tools.rag_retrieve_tool import RAGRetrieveTool
from memory.persona_memory import get_shared_user_persona_memory
from tools.user_persona_tools import build_user_persona_tools

_shared_pm = get_shared_user_persona_memory()

_BASE_TOOLS = [
    ArxivSearchTool(),
    PdfCommentTool(),
    FileLoadingTool(),
    CommandRunningTool(),
    DoclingParseTool(),
    DoclingSearchTool(),
    MarkdownSectionTool(),
    PyMuPDFParseTool(),
    ChapterIndexTool(),
    RefCheckerTool(),
    FigureRefCheckerTool(),
    RAGRetrieveTool(),
]

_USER_PERSONA_TOOLS = build_user_persona_tools(_shared_pm)

# 全量列表：独立跑 Agent / 测试时可 import；动态图中由 build_tools_for_graph_node 按节点过滤
tool_list = list(_BASE_TOOLS) + list(_USER_PERSONA_TOOLS)


def build_tools_for_graph_node(*, is_entry_node: bool):
    """
    动态图节点专用：仅入口节点挂载用户画像工具，避免非入口误写画像。
    """
    if is_entry_node:
        return list(_BASE_TOOLS) + list(_USER_PERSONA_TOOLS)
    return list(_BASE_TOOLS)


__all__ = [
    "tool_list",
    "build_tools_for_graph_node",
]
