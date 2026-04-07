"""
文档加载与文本分块工具（可运行）。

提供从本地文件读取文本并切割为固定大小 Chunk 的纯函数集合，
不依赖任何向量库，便于独立测试。

支持格式：.txt / .md / .tex
[扩展] 待支持：.pdf（需安装 PyMuPDF 或 pdfminer）

TODO: 未来增加 load_pdf(path) 函数，支持 PDF 文档解析
TODO: 未来增加 load_url(url) 函数，支持网页内容抓取
TODO: 未来增加 smart_chunk(text) 函数，按段落/章节语义切块
"""
from pathlib import Path
from typing import List, Tuple


_SUPPORTED_SUFFIXES = {".txt", ".md", ".tex"}


def chunk_text(
    text: str,
    chunk_size: int = 500,
    overlap: int = 50,
) -> List[str]:
    """
    将长文本切割为固定大小、带重叠的文本块。

    使用滑动窗口策略保证上下文连续性：
    每个 chunk 的末尾 overlap 个字符与下一个 chunk 的开头重叠，
    避免在 chunk 边界处切断关键语义信息。

    Args:
        text:       待分块的原始文本。
        chunk_size: 每块的最大字符数（默认 500）。
        overlap:    相邻块之间的重叠字符数（默认 50）。

    Returns:
        文本块列表，每块长度 ≤ chunk_size。
        输入文本长度 ≤ chunk_size 时返回包含整段文本的单元素列表。

    Notes:
        - 以字符数为单位切分（非 Token），跨语言均适用。
        - 建议 overlap < chunk_size / 5，避免冗余内容过多。
    """
    text = text.strip()
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]

    chunks: List[str] = []
    step = chunk_size - overlap
    if step <= 0:
        step = max(1, chunk_size // 2)

    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += step

    return chunks


def load_text_file(path: str) -> str:
    """
    读取文本文件内容（UTF-8 编码）。

    Args:
        path: 文件路径（绝对路径或相对路径）。

    Returns:
        文件的完整文本内容字符串。

    Raises:
        FileNotFoundError: 文件不存在时。
        UnicodeDecodeError: 文件编码不是 UTF-8 时。
    """
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"文件不存在: {path}")
    return file_path.read_text(encoding="utf-8")


def load_and_chunk(
    path: str,
    chunk_size: int = 500,
    overlap: int = 50,
) -> Tuple[List[str], List[dict]]:
    """
    加载文件并切块，返回（文本块列表，元数据列表）。

    元数据包含文件名（source）和块序号（chunk_idx），
    这些信息会随文档一起写入向量库，检索结果中可展示来源。

    Args:
        path:       文件路径（支持 .txt / .md / .tex）。
        chunk_size: 每块最大字符数。
        overlap:    相邻块重叠字符数。

    Returns:
        (chunks, metadatas) 元组：
        - chunks:    文本块列表。
        - metadatas: 与 chunks 一一对应的元数据字典列表，
                     包含 "source"（文件名）和 "chunk_idx"（块序号）。

    Raises:
        FileNotFoundError: 文件不存在时。
        ValueError:        文件格式不受支持时（不在 .txt/.md/.tex 中）。
    """
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"文件不存在: {path}")

    suffix = file_path.suffix.lower()
    if suffix not in _SUPPORTED_SUFFIXES:
        raise ValueError(
            f"不支持的文件格式: {suffix!r}。"
            f"当前支持：{sorted(_SUPPORTED_SUFFIXES)}"
        )

    content = load_text_file(path)
    chunks = chunk_text(content, chunk_size=chunk_size, overlap=overlap)
    metadatas = [
        {"source": file_path.name, "chunk_idx": i}
        for i in range(len(chunks))
    ]
    return chunks, metadatas
