"""
IO 类工具的单元测试：
- tools.file_loading_tool.FileLoadingTool
- tools.pdf_comment_tool.PdfCommentTool（依赖 PyMuPDF/fitz）

目标：
1) 覆盖常见输入校验与文件读取路径；
2) 尽量不依赖外部环境：使用 tmp_path 构造临时文件；
3) pdf_comment_tool 若依赖缺失则跳过（importorskip）。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.file_loading_tool import FileLoadingTool


def test_file_loading_tool_rejects_missing_path() -> None:
    """
    文件不存在时应返回 success=False 且 error 可读。
    """
    tool = FileLoadingTool()
    r = tool.run("not_exists_12345.txt")
    assert r.success is False
    assert "文件不存在" in (r.error or "")


def test_file_loading_tool_reads_utf8_text(tmp_path: Path) -> None:
    """
    对常见文本扩展名（.txt/.md/.py 等）应按 UTF-8 读取。
    """
    p = tmp_path / "a.txt"
    p.write_text("hello\n世界", encoding="utf-8")
    tool = FileLoadingTool()
    r = tool.run(str(p))
    assert r.success is True
    assert "hello" in r.output
    assert "世界" in r.output


def test_file_loading_tool_reads_gbk_fallback(tmp_path: Path) -> None:
    """
    当 UTF-8 解码失败时，应尝试 GBK（针对 Windows 常见编码场景）。
    """
    p = tmp_path / "a.txt"
    p.write_bytes("中文".encode("gbk"))
    tool = FileLoadingTool()
    r = tool.run(str(p))
    assert r.success is True
    assert "中文" in r.output


def test_pdf_comment_tool_fuzzy_search_basic(tmp_path: Path) -> None:
    """
    PdfCommentTool.fuzzy_search 的核心是：
    - 从 page.get_text(\"words\") 得到单词序列；
    - 用滑动窗口匹配 target_text 的 token；
    - 合并矩形框，返回候选 Rect 列表。

    本用例使用 PyMuPDF 生成一个最小 PDF 并写入可检索文本，确保测试按照真实运行路径执行。
    """
    fitz = pytest.importorskip("fitz")
    from tools.pdf_comment_tool import PdfCommentTool

    pdf_path = tmp_path / "t.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Hello World")
    doc.save(pdf_path)
    doc.close()

    doc2 = fitz.open(pdf_path)
    page2 = doc2.load_page(0)

    tool = PdfCommentTool()
    rects = tool.fuzzy_search(page2, "Hello World")
    assert isinstance(rects, list)
    assert len(rects) >= 1
    assert all(isinstance(x, fitz.Rect) for x in rects)
    doc2.close()


def test_pdf_comment_tool_run_single_creates_output(tmp_path: Path) -> None:
    """
    run_single 会在指定页搜索文本并添加批注：
    - 成功时应返回 success=True；
    - 输出 PDF 文件应存在且非空。
    """
    fitz = pytest.importorskip("fitz")
    from tools.pdf_comment_tool import PdfCommentTool

    pdf_path = tmp_path / "t2.pdf"
    doc = fitz.open()
    p0 = doc.new_page()
    p0.insert_text((72, 72), "TARGET TEXT")
    doc.save(pdf_path)
    doc.close()

    tool = PdfCommentTool()
    out_path = tmp_path / "out.pdf"
    r = tool.run_single(
        pdf_path=str(pdf_path),
        output_path=str(out_path),
        page_idx=0,
        text="TARGET TEXT",
        comment="COMMENT",
        author=None,
    )
    assert r.success is True
    assert out_path.exists()
    assert out_path.stat().st_size > 0
