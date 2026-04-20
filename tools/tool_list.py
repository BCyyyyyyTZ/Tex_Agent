from tools.arxiv_tool import ArxivSearchTool
from tools.pdf_comment_tool import PdfCommentTool
from tools.file_loading_tool import FileLoadingTool
from tools.command_running_tool import CommandRunningTool
from tools.docling_tool import DoclingParseTool
from tools.rag_retrieve_tool import RAGRetrieveTool


tool_list = [
    ArxivSearchTool(), 
    PdfCommentTool(), 
    FileLoadingTool(), 
    CommandRunningTool(), 
    DoclingParseTool(),
    RAGRetrieveTool(),
]   
