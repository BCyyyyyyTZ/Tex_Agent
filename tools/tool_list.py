from tools.arxiv_tool import ArxivSearchTool
from tools.pdf_comment_tool import PdfCommentTool
from tools.file_loading_tool import FileLoadingTool
from tools.command_running_tool import CommandRunningTool
from tools.docling_tool import DoclingParseTool
tool_list = {
    "arxiv_search": ArxivSearchTool(),
    "pdf_comment": PdfCommentTool(),
    "file_loading": FileLoadingTool(),
    "command_running": CommandRunningTool(),
    "docling_parse": DoclingParseTool()
}
