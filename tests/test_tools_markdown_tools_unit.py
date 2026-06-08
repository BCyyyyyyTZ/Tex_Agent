"""
Markdown 相关工具的单元测试：
- ChapterIndexTool（tools.chapter_index_tool）
- MarkdownSectionTool（tools.markdown_section_tool）
- FigureRefCheckerTool（tools.figure_ref_checker_tool）

目的：
1) 这些工具是 thesis-checklist 工作流的“本地文本分析”核心组件；
2) 多数逻辑为纯文本/正则/结构解析，适合用稳定的单元测试做回归保护；
3) 不依赖网络、不依赖外部服务。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.chapter_index_tool import ChapterIndexTool, _annotate_structure, _build_stats, _parse_sections as _parse_md_sections
from tools.figure_ref_checker_tool import (
    _check_numbering_gaps,
    _extract_cited,
    _extract_defined,
)
from tools.markdown_section_tool import MarkdownSectionTool, _parse_sections as _parse_sections2


def test_chapter_index_parse_and_annotate_structure() -> None:
    """
    ChapterIndexTool 的章节解析与结构标注：
    - 能识别 H1/H2/H3；
    - 能计算 sub_count；
    - 当父节只有一个直接子节时，该子节标注 is_isolated=True。
    """
    md = "\n".join(
        [
            "# 1 Introduction",
            "intro text",
            "## 1.1 Background",
            "bg text",
            "# 2 Method",
            "m text",
            "## 2.1 OnlyChild",
            "x",
            "### 2.1.1 Sub",
            "y",
        ]
    )
    sections = _parse_md_sections(md)
    assert [s["level"] for s in sections] == [1, 2, 1, 2, 3]

    sections = _annotate_structure(sections)
    # Introduction 下面只有一个 H2
    assert sections[1]["is_isolated"] is True
    # Method 下面只有一个 H2（OnlyChild）
    assert sections[3]["is_isolated"] is True
    # Method 的 sub_count=1
    assert sections[2]["sub_count"] == 1


def test_chapter_index_stats_counts_only_filtered_sections() -> None:
    """
    统计应基于输入的 sections 列表（工具里会先按 max_level 过滤）。
    """
    sections = [
        {"level": 1, "title": "A", "char_count": 10, "sub_count": 1, "is_isolated": False},
        {"level": 2, "title": "B", "char_count": 5, "sub_count": 0, "is_isolated": True},
    ]
    stats = _build_stats(sections)
    assert stats["total_sections"] == 2
    assert stats["total_chars"] == 15
    assert stats["h1_count"] == 1
    assert stats["h2_count"] == 1
    assert stats["isolated_sections"] == 1


def test_chapter_index_tool_run_tree_json_stats(tmp_path: Path) -> None:
    """
    ChapterIndexTool.run 三种 mode：
    - tree：返回缩进树状结构（文本）
    - json：返回可解析的 JSON（前缀说明文字之后）
    - stats：返回摘要 + metadata 统计字段
    """
    md_path = tmp_path / "doc.md"
    md_path.write_text("# A\nx\n## B\ny\n", encoding="utf-8")

    tool = ChapterIndexTool()

    r_tree = tool.run(md_path=str(md_path), mode="tree", max_level=3)
    assert r_tree.success is True
    assert "# A" in r_tree.output

    r_json = tool.run(md_path=str(md_path), mode="json", max_level=3)
    assert r_json.success is True
    # output 前缀含说明，找到最后一段 JSON 并解析
    raw = r_json.output.splitlines()
    start = next(i for i, ln in enumerate(raw) if ln.strip() == "[")
    payload = json.loads("\n".join(raw[start:]))
    assert isinstance(payload, list) and payload[0]["title"] == "A"

    r_stats = tool.run(md_path=str(md_path), mode="stats", max_level=3)
    assert r_stats.success is True
    assert "章节统计" in r_stats.output
    assert r_stats.metadata["total_sections"] == 2


def test_markdown_section_tool_outline_and_fallback(tmp_path: Path) -> None:
    """
    MarkdownSectionTool：
    - outline 模式输出标题大纲；
    - content 模式关键词无匹配时应 fallback 返回全文并标记 metadata.fallback=True。
    """
    md_path = tmp_path / "paper.md"
    md_path.write_text("# Abstract\nA\n# Intro\nI\n", encoding="utf-8")
    tool = MarkdownSectionTool()

    r_outline = tool.run(md_path=str(md_path), mode="outline")
    assert r_outline.success is True
    assert "[文档大纲" in r_outline.output
    assert "# Abstract" in r_outline.output

    r_fb = tool.run(md_path=str(md_path), section_keywords=["method"], mode="content", max_chars=100)
    assert r_fb.success is True
    assert "无匹配" in r_fb.output
    assert r_fb.metadata.get("fallback") is True


def test_markdown_section_tool_content_includes_subsections_behavior(tmp_path: Path) -> None:
    """
    include_subsections 的当前实现属于“简化策略”：
    - 一旦匹配到某章节，后续章节（含子节）会被连续追加到输出中（直到文件结束）；
    - 该行为虽不完美，但属于当前版本的“既定行为”，测试用例用于锁定语义，避免未来无意改变。
    """
    md_path = tmp_path / "paper.md"
    md_path.write_text(
        "\n".join(
            [
                "# Intro",
                "intro",
                "## Background",
                "bg",
                "# Method",
                "method",
                "## Detail",
                "detail",
                "# End",
                "end",
            ]
        ),
        encoding="utf-8",
    )
    tool = MarkdownSectionTool()

    r = tool.run(md_path=str(md_path), section_keywords=["method"], mode="content", include_subsections=True, max_chars=0)
    assert r.success is True
    # 从 Method 开始应包含 Detail 与 End（当前实现是连续追加）
    assert "# Method" in r.output
    assert "## Detail" in r.output
    assert "# End" in r.output


def test_figure_ref_checker_defined_and_cited_extraction_and_gaps() -> None:
    """
    FigureRefCheckerTool 的核心是：
    - 提取 caption 定义的编号；
    - 提取正文引用的编号；
    - 检查编号跳号。
    """
    md = "\n".join(
        [
            "# Intro",
            "如图 1 所示 ... 见表2。",
            "图 1: caption text",
            "表 1: caption text",
            "Algorithm 1: caption",
            "Equation (1): caption",
            "图 3: skipped",
        ]
    )
    defined = _extract_defined(md)
    assert "1" in defined["fig"]
    assert "1" in defined["tab"]
    assert "1" in defined["alg"]
    assert "1" in defined["eq"]

    cited = _extract_cited(md)
    assert "1" in cited["fig"]
    assert "2" in cited["tab"]  # 正文引用了表2，但定义只有表1

    gaps = _check_numbering_gaps(defined["fig"], "图")
    # 定义了图1与图3，应报告跳号
    assert any("跳号" in g for g in gaps)


def test_markdown_section_internal_parse_sections_basic() -> None:
    """
    额外回归：_parse_sections（markdown_section_tool）能稳定输出 level/title/content。
    """
    md = "# A\n1\n## B\n2\n"
    secs = _parse_sections2(md)
    assert len(secs) == 2
    assert secs[0]["title"] == "A"
    assert secs[1]["title"] == "B"
    assert secs[0]["content"] == "1"
