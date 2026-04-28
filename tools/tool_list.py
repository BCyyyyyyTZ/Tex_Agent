"""
已注册工具列表。构造时逐项实例化：缺少可选依赖的工具会被跳过并打日志，
避免某一工具失败导致整个 ``tool_list`` 无法 import（Web 下拉 / 构图均依赖此模块）。
"""
from __future__ import annotations

from typing import Callable, List, Optional, TypeVar

from memory.persona_memory import get_shared_user_persona_memory
from tools.arxiv_tool import ArxivSearchTool
from tools.chapter_index_tool import ChapterIndexTool
from tools.command_running_tool import CommandRunningTool
from tools.docling_search_tool import DoclingSearchTool
from tools.docling_tool import DoclingParseTool
tool_list = {
    "arxiv_search": ArxivSearchTool(),
    "pdf_comment": PdfCommentTool(),
    "file_loading": FileLoadingTool(),
    "command_running": CommandRunningTool(),
    "docling_parse": DoclingParseTool()
}
