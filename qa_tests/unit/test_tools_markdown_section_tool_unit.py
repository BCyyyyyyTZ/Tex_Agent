from __future__ import annotations

from pathlib import Path

from tools.markdown_section_tool import MarkdownSectionTool


def test_markdown_section_tool__missing_file_fails(tmp_path: Path) -> None:
    tool = MarkdownSectionTool()
    r = tool.run(md_path=str(tmp_path / "missing.md"), section_keywords=["a"])
    assert r.success is False
    assert "文件不存在" in (r.error or "")


def test_markdown_section_tool__outline_mode(tmp_path: Path) -> None:
    p = tmp_path / "a.md"
    p.write_text("# A\n\nx\n\n## B\n\ny\n", encoding="utf-8")
    tool = MarkdownSectionTool()
    r = tool.run(md_path=str(p), mode="outline")
    assert r.success is True
    assert "[文档大纲" in (r.output or "")
    assert "# A" in r.output

