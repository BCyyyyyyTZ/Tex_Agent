"""
FileLoadingTool：加载指定文件路径的文件内容并返回。
"""
import os
from typing import Optional

from tools.base_tool import BaseTool
from core.message import ToolResult
from utils.logger import get_logger

import PyPDF2
import docx


logger = get_logger(__name__)


class FileLoadingTool(BaseTool):
    """
    文件加载工具。

    加载指定文件路径的文件内容并返回，支持文本文件、PDF、Word等文件的读取。

    Example:
        tool = FileLoadingTool()
        result = tool.run("path/to/file.txt")
        print(result.output)
    """

    def __init__(self):
        super().__init__(
            name="file_loading",
            description="加载指定文件路径的文件内容并返回。输入文件的绝对路径，返回文件的文本内容。支持文本文件、PDF、Word等文件格式。",
            input_schema={
                "file_path": "文件的绝对路径，支持文本文件、PDF、Word等文件格式的读取"
            }
        )

    def run(self, file_path: str) -> ToolResult:
        """
        执行文件加载操作。

        Args:
            file_path: 文件的绝对路径。

        Returns:
            ToolResult，成功时 output 为文件内容，
            失败时 success=False 且 error 字段包含错误信息。
        """
        logger.info(f"文件加载启动 | 路径: {file_path!r}")
        try:
            # 检查文件是否存在
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"文件不存在: {file_path}")
            
            # 检查是否为文件
            if not os.path.isfile(file_path):
                raise IsADirectoryError(f"路径不是文件: {file_path}")
            
            # 获取文件扩展名
            _, ext = os.path.splitext(file_path.lower())
            
            # 根据文件类型读取内容
            if ext in ['.txt', '.md', '.json', '.xml', '.csv', '.html', '.css', '.js', '.py']:
                # 文本文件
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                except UnicodeDecodeError:
                    # 尝试其他编码
                    try:
                        with open(file_path, 'r', encoding='gbk') as f:
                            content = f.read()
                    except Exception:
                        # 尝试其他常见编码
                        try:
                            with open(file_path, 'r', encoding='utf-16') as f:
                                content = f.read()
                        except Exception:
                            raise ValueError(f"无法读取文件，编码格式不支持: {file_path}")
            elif ext == '.pdf':
                # PDF 文件
                try:
                    content = []
                    with open(file_path, 'rb') as f:
                        reader = PyPDF2.PdfReader(f)
                        for page_num in range(len(reader.pages)):
                            page = reader.pages[page_num]
                            text = page.extract_text()
                            # 确保文本编码正确
                            if isinstance(text, str):
                                content.append(text)
                            else:
                                content.append(str(text))
                    content = '\n'.join(content)
                except ImportError:
                    raise ImportError("需要安装 PyPDF2 库来读取 PDF 文件: pip install PyPDF2")
                except Exception as e:
                    raise Exception(f"读取 PDF 文件失败: {e}")
            elif ext in ['.docx']:
                # Word 文件
                try:
                    try:
                        doc = docx.Document(file_path)
                        content = []
                        for para in doc.paragraphs:
                            text = para.text
                            # 确保文本编码正确
                            if isinstance(text, str):
                                content.append(text)
                            else:
                                content.append(str(text))
                        content = '\n'.join(content)
                    except KeyError as e:
                        # 处理书签相关的错误
                        if "There is no item named" in str(e):
                            # 尝试使用 python-docx 的另一种方式读取
                            from zipfile import ZipFile
                            import xml.etree.ElementTree as ET
                            
                            content = []
                            with ZipFile(file_path, 'r') as zf:
                                # 读取文档主体内容
                                if 'word/document.xml' in zf.namelist():
                                    with zf.open('word/document.xml') as f:
                                        tree = ET.parse(f)
                                        root = tree.getroot()
                                        
                                        # 命名空间处理
                                        ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
                                        
                                        # 提取所有段落文本
                                        for para in root.findall('.//w:p', ns):
                                            para_text = []
                                            for run in para.findall('.//w:t', ns):
                                                if run.text:
                                                    text = run.text
                                                    # 确保文本编码正确
                                                    if isinstance(text, str):
                                                        para_text.append(text)
                                                    else:
                                                        para_text.append(str(text))
                                            if para_text:
                                                content.append(''.join(para_text))
                            content = '\n'.join(content)
                        else:
                            raise
                except ImportError:
                    raise ImportError("需要安装 python-docx 库来读取 Word 文件: pip install python-docx")
                except Exception as e:
                    raise Exception(f"读取 Word 文件失败: {e}")
            else:
                # 其他文件类型，尝试作为文本文件读取
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                except UnicodeDecodeError:
                    # 尝试其他编码
                    try:
                        with open(file_path, 'r', encoding='gbk') as f:
                            content = f.read()
                    except Exception:
                        raise ValueError(f"不支持的文件类型或无法以文本格式读取: {file_path}")
            
            # 确保返回的内容是字符串格式，并且编码正确
            if not isinstance(content, str):
                content = str(content)
            
            # 处理可能的编码问题，确保字符串可以直接使用
            #try:
                # 尝试编码和解码，确保字符串是有效的
            #    content.encode('utf-8').decode('utf-8')
            #except Exception:
                # 如果出现编码问题，尝试使用替换模式
            #    content = content.encode('utf-8', errors='replace').decode('utf-8')
            
            # 限制文件大小，避免读取过大的文件
            #max_size = 1024 * 1024  # 1MB
            #if len(content) > max_size:
            #    content = content[:max_size] + f"\n\n[文件内容已截断，原始大小: {len(content)} 字节]"
            
            logger.info(f"文件加载完成 | 路径: {file_path!r} | 大小: {len(content)} 字节")
            return ToolResult(
                success=True,
                output=content,
                metadata={
                    "file_path": file_path,
                    "file_size": len(content),
                },
            )

        except Exception as e:
            logger.error(f"文件加载失败: {e}")
            return ToolResult(
                success=False,
                output="",
                error=f"{e}",
                metadata={"file_path": file_path},
            )

if __name__ == "__main__":
    tool = FileLoadingTool()
    result = tool.run(r"C:\Users\Drago\Downloads\实验报告.docx")
    print("文件加载结果:", "成功" if result.success else "失败")
    print("错误信息:", result.error if not result.success else "无")
    if result.success:
        print("文件大小:", result.metadata.get("file_size", 0), "字节")
        print("\n文件内容预览:")
        # 限制预览长度，避免打印过多内容
        preview = result.output[:500] + ("..." if len(result.output) > 500 else "")
        print(preview)
