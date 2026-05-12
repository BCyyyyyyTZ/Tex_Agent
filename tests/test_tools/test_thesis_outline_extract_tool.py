from __future__ import annotations

import json
from pathlib import Path

from tools.thesis_outline_extract_tool import ThesisOutlineExtractTool
from utils import thesis_pdf_extract
from utils.thesis_pdf_extract import ChapterNode


def _build_mock_tree() -> list[ChapterNode]:
    ch1 = ChapterNode("第1章 绪论", page=0, depth=0)
    ch11 = ChapterNode("1.1 研究背景", page=1, depth=1)
    ch12 = ChapterNode("1.2 研究意义", page=2, depth=1)
    ch1.children = [ch11, ch12]

    ch2 = ChapterNode("第2章 方法", page=4, depth=0)
    ch21 = ChapterNode("2.1 数据", page=5, depth=1)
    ch2.children = [ch21]
    return [ch1, ch2]


def test_outline_mode_writes_outline_json(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"%PDF-1.1\n%\xe2\xe3\xcf\xd3\n")
    tool = ThesisOutlineExtractTool()

    monkeypatch.setattr("tools.thesis_outline_extract_tool.settings.parsed_doc_dir", str(tmp_path), raising=False)
    monkeypatch.setattr(
        "tools.thesis_outline_extract_tool._load_outline",
        lambda *_args, **_kwargs: (_build_mock_tree(), 10, "pypdf"),
    )

    result = tool.run(pdf_path=str(pdf), mode="outline", redo=True)
    assert result.success is True, result.error
    meta = result.metadata or {}
    outline_path = Path(meta["outline_path"])
    assert outline_path.is_file()
    obj = json.loads(outline_path.read_text(encoding="utf-8"))
    assert obj["total_pages"] == 10
    assert obj["outline_source"] == "pypdf"


def test_extract_mode_requires_chapters(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"%PDF-1.1\n%\xe2\xe3\xcf\xd3\n")
    tool = ThesisOutlineExtractTool()
    monkeypatch.setattr("tools.thesis_outline_extract_tool.settings.parsed_doc_dir", str(tmp_path), raising=False)
    result = tool.run(pdf_path=str(pdf), mode="extract", chapters="")
    assert result.success is False
    assert "必须提供 chapters" in str(result.error or "")


def test_extract_mode_outputs_selected_sections(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"%PDF-1.1\n%\xe2\xe3\xcf\xd3\n")
    tool = ThesisOutlineExtractTool()

    monkeypatch.setattr("tools.thesis_outline_extract_tool.settings.parsed_doc_dir", str(tmp_path), raising=False)
    monkeypatch.setattr(
        "tools.thesis_outline_extract_tool._load_outline",
        lambda *_args, **_kwargs: (_build_mock_tree(), 10, "pymupdf"),
    )

    def _fake_process(node, inherited_text="", pdf_path=""):  # type: ignore[no-untyped-def]
        node.text = f"{node.title}\n这是{node.title}的正文。"
        for child in node.children:
            _fake_process(child, inherited_text="", pdf_path=pdf_path)

    monkeypatch.setattr("tools.thesis_outline_extract_tool.process_chapter", _fake_process)

    result = tool.run(
        pdf_path=str(pdf),
        mode="extract",
        chapters="第1章;2.1;不存在章节",
        strict_chapters=False,
        redo=True,
    )
    assert result.success is True, result.error
    meta = result.metadata or {}
    assert meta.get("selected_chapters")
    assert "不存在章节" in (meta.get("unresolved_chapter_tokens") or [])

    md_path = Path(meta["markdown_path"])
    assert md_path.is_file()
    md_text = md_path.read_text(encoding="utf-8")
    assert "# 第1章 绪论" in md_text
    assert "## 2.1 数据" in md_text


def test_select_nodes_supports_title_alias_and_without_number() -> None:
    tree = _build_mock_tree()
    selected, unresolved = thesis_pdf_extract.select_nodes_by_chapters(
        tree,
        "研究背景这一小节;1.1小节",
    )
    assert not unresolved
    titles = [n.title for n in selected]
    assert "1.1 研究背景" in titles


def test_process_chapter_fallback_when_inherited_text_only_title(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    node = ChapterNode("3.2 研究背景", page=10, depth=1)
    node.end_page = 11
    calls = {"count": 0}

    def _fake_extract(_pdf_path: str, _start: int, _end: int) -> str:
        calls["count"] += 1
        return "3.2 研究背景\n这是本节正文。"

    monkeypatch.setattr(thesis_pdf_extract, "extract_pages_text", _fake_extract)
    thesis_pdf_extract.process_chapter(node, inherited_text="3.2 研究背景", pdf_path="dummy.pdf")
    body = thesis_pdf_extract.strip_title_from_text(node.text, node.title)
    assert "这是本节正文" in body
    assert calls["count"] >= 1
