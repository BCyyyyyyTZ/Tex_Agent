"""
DoclingParseTool：使用 Docling 将文档（PDF/DOCX 等）解析为 Markdown + JSON。

支持缓存：若 redo=False（默认），会先在 PARSED_DOC_DIR 下查找已存在的解析结果（按文件名 stem 匹配），
存在有效结果则直接复用，避免重复解析。
"""

import re
import time
from pathlib import Path
from typing import Optional

from tools.base_tool import BaseTool
from core.message import ToolResult
from rag.docling_parse import parse_document_to_dir, DoclingParseResult
from config.settings import settings
from utils.logger import get_logger

logger = get_logger(__name__)


def _sanitize_stem(stem: str) -> str:
    """与 docling_parse.py 保持一致的 stem 清理逻辑。"""
    s = stem.strip() or "document"
    s = re.sub(r"[^\w\-]+", "_", s, flags=re.UNICODE)
    return (s[:120] if len(s) > 120 else s) or "document"


def _find_existing_parse(root: Path, source_stem: str) -> Optional[Path]:
    """
    在 parsed_doc_dir 下查找与输入文件名 stem 匹配的最新解析目录。
    目录命名格式为 {sanitized_stem}_{timestamp}。
    返回第一个包含有效 document.md 和 document.json 的目录（优先最新）。
    """
    if not root.exists():
        return None

    safe_stem = _sanitize_stem(source_stem)
    candidates = []

    for item in root.iterdir():
        if item.is_dir() and item.name.startswith(f"{safe_stem}_"):
            md_path = item / "document.md"
            json_path = item / "document.json"
            if md_path.exists() and json_path.exists() and md_path.stat().st_size > 100:  # 非空检查
                candidates.append(item)

    if not candidates:
        return None

    # 按修改时间倒序，取最新的
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0]


class DoclingParseTool(BaseTool):
    """
    Docling 文档解析工具。

    将 PDF、DOCX、MD 等文档解析为结构化 Markdown 和 JSON。
    支持缓存机制（默认开启），避免重复解析相同文档。
    """

    def __init__(self):
        """初始化 Docling 解析工具，并声明输入 schema（doc_path/redo）。"""
        super().__init__(
            name="docling_parse",
            description="使用 Docling 解析文档（PDF/DOCX/MD 等），返回解析后的 Markdown 和 JSON 文件路径。支持缓存复用已解析结果（默认开启）。",
            input_schema={
                "doc_path": "必填，要解析的文档绝对或相对路径（支持 PDF、DOCX、MD、TXT 等）",
                "redo": "可选，是否强制重新解析（true/false，默认为 false）。若为 false 则优先复用缓存结果。"
            }
        )

    def run(self, doc_path: str, redo: bool = False) -> ToolResult:
        """
        执行文档解析。

        Args:
            doc_path: 文档路径
            redo: 是否强制重新解析，默认为 False（使用缓存）

        Returns:
            ToolResult，output 中包含解析结果路径和摘要信息
        """
        logger.info(f"DoclingParseTool 执行 | doc_path={doc_path!r}, redo={redo}")

        try:
            parsed_root = Path(settings.parsed_doc_dir)
            source_path = Path(doc_path)
            stem = source_path.stem

            # 1. 检查缓存（redo=False 时）
            existing_dir = None
            if not redo:
                existing_dir = _find_existing_parse(parsed_root, stem)
                if existing_dir:
                    md_path = existing_dir / "document.md"
                    json_path = existing_dir / "document.json"
                    artifacts_dir = existing_dir / "artifacts"

                    logger.info(f"找到缓存解析结果: {existing_dir.name}")
                    return ToolResult(
                        success=True,
                        output=f"""已从缓存加载解析结果（无需重新解析）：

文档: {doc_path}
输出目录: {existing_dir}
Markdown: {md_path}
JSON: {json_path}
Artifacts: {artifacts_dir}

提示：如需强制重新解析，请设置 redo=true。
""",
                        metadata={
                            "success": True,
                            "source_path": str(source_path),
                            "output_dir": str(existing_dir),
                            "markdown_path": str(md_path),
                            "json_path": str(json_path),
                            "artifacts_dir": str(artifacts_dir),
                            "from_cache": True,
                            "redo": redo,
                        }
                    )

            # 2. 执行解析
            logger.info(f"开始 Docling 解析: {doc_path} (redo={redo})")
            result: DoclingParseResult = parse_document_to_dir(
                source=doc_path,
                output_root=str(parsed_root)
            )

            if not result.success:
                return ToolResult(
                    success=False,
                    output="文档解析失败",
                    error=result.error or "未知错误",
                    metadata={"source_path": str(source_path), "from_cache": False}
                )

            output_msg = f"""文档解析成功！

源文件: {result.source_path}
输出目录: {result.output_dir}
Markdown 文件: {result.markdown_path}
JSON 文件: {result.json_path}
资源目录: {result.artifacts_dir}
解析路由: {result.route}
页数: {result.page_count or 'N/A'}
"""

            if result.bypass_stage:
                output_msg += f"旁路阶段: {result.bypass_stage}\n"

            return ToolResult(
                success=True,
                output=output_msg,
                metadata={
                    "success": True,
                    "source_path": result.source_path,
                    "output_dir": result.output_dir,
                    "markdown_path": result.markdown_path,
                    "json_path": result.json_path,
                    "artifacts_dir": result.artifacts_dir,
                    "page_count": result.page_count,
                    "route": result.route,
                    "from_cache": False,
                    "redo": redo,
                }
            )

        except Exception as e:
            logger.exception(f"DoclingParseTool 执行异常: {e}")
            return ToolResult(
                success=False,
                output="文档解析工具执行失败",
                error=str(e),
                metadata={"doc_path": doc_path, "redo": redo}
            )

    def __repr__(self) -> str:
        """返回工具的稳定字符串表示（便于日志与调试）。"""
        return "DoclingParseTool(name='docling_parse')"


# 测试入口
if __name__ == "__main__":
    # 注意：测试需要安装所有依赖（arxiv, docling 等）
    # 可直接在代码中调用：tool = DoclingParseTool(); result = tool.run("your_doc.pdf", redo=False)
    print("DoclingParseTool 已定义。使用示例：")
    print("  from tools.docling_tool import DoclingParseTool")
    print("  tool = DoclingParseTool()")
    print('  result = tool.run("path/to/document.pdf", redo=False)')
    print("  print(result.output)")
    print("\n工具名称: docling_parse")
    print("输入参数: doc_path (必填), redo=False (可选)")
