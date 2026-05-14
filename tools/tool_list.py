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
from tools.checklist_prepare_tool import ChecklistPrepareTool
from tools.docling_search_tool import DoclingSearchTool
from tools.docling_tool import DoclingParseTool
from tools.figure_ref_checker_tool import FigureRefCheckerTool
from tools.file_loading_tool import FileLoadingTool
from tools.markdown_section_tool import MarkdownSectionTool
from tools.pdf_comment_tool import PdfCommentTool
from tools.pymupdf_parse_tool import PyMuPDFParseTool
from tools.thesis_outline_extract_tool import ThesisOutlineExtractTool
from tools.rag_retrieve_tool import RAGRetrieveTool
from tools.ref_checker_tool import RefCheckerTool
from tools.references_slice_and_docling_tool import ReferencesSliceAndDoclingTool
from tools.user_persona_tools import build_user_persona_tools
from utils.logger import get_logger
from tools.gemini_upload_pdf_tool import GeminiUploadPdfTool
from tools.register_inputs_tool import RegisterInputsTool
from tools.offer_artifact_download_tool import OfferArtifactDownloadTool
from tools.preflight_inputs_tool import PreflightInputsTool
from tools.thesis_chapter_route_tool import ThesisChapterRouteTool

logger = get_logger(__name__)
_shared_pm = get_shared_user_persona_memory()

T = TypeVar("T")


def _safe_instantiate(label: str, factory: Callable[[], T]) -> Optional[T]:
    try:
        return factory()
    except Exception as e:  # noqa: BLE001 — 故意吞掉单工具失败
        logger.warning("[tool_list] 跳过工具 %s：%s", label, e)
        return None


def _build_base_tools() -> List:
    specs = [
        ("arxiv_search", lambda: ArxivSearchTool()),
        ("pdf_comment", lambda: PdfCommentTool()),
        ("file_loading", lambda: FileLoadingTool()),
        ("command_running", lambda: CommandRunningTool()),
        ("docling_parse", lambda: DoclingParseTool()),
        ("docling_search", lambda: DoclingSearchTool()),
        ("markdown_section", lambda: MarkdownSectionTool()),
        ("pymupdf_parse", lambda: PyMuPDFParseTool()),
        ("thesis_outline_extract", lambda: ThesisOutlineExtractTool()),
        ("thesis_chapter_route", lambda: ThesisChapterRouteTool()),
        ("checklist_prepare", lambda: ChecklistPrepareTool()),
        ("chapter_index", lambda: ChapterIndexTool()),
        ("ref_checker", lambda: RefCheckerTool()),
        ("references_slice_and_docling", lambda: ReferencesSliceAndDoclingTool()),
        ("figure_ref_checker", lambda: FigureRefCheckerTool()),
        ("rag_retrieve", lambda: RAGRetrieveTool()),
        ("register_inputs", lambda: RegisterInputsTool()),
        ("preflight_inputs", lambda: PreflightInputsTool()),
        ("gemini_upload_pdf", lambda: GeminiUploadPdfTool()),
        ("offer_artifact_download", lambda: OfferArtifactDownloadTool()),
    ]
    out = []
    for label, factory in specs:
        t = _safe_instantiate(label, factory)
        if t is not None:
            out.append(t)
    return out


_BASE_TOOLS = _build_base_tools()

try:
    _USER_PERSONA_TOOLS = build_user_persona_tools(_shared_pm)
except Exception as e:  # noqa: BLE001
    logger.warning("[tool_list] 用户画像工具组不可用：%s", e)
    _USER_PERSONA_TOOLS = []

# 全量列表：动态图中由 build_tools_for_graph_node 按节点过滤
tool_list: List = list(_BASE_TOOLS) + list(_USER_PERSONA_TOOLS)


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
