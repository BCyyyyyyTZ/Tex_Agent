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

tool_list = [
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
