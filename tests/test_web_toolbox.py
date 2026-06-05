"""Web 工具箱独立工具冒烟测试（不依赖 LLM）。"""
from tools.latex_table_tool import LatexTableTool
from tools.palette_tool import PaletteTool
from tools.paper_title_tool import PaperTitleTool
from tools.qrcode_tool import QrcodeTool
from tools.text_stats_tool import TextStatsTool


def test_latex_table_highlight_best():
    r = LatexTableTool().run(
        headers="Method,Acc",
        rows=[["A", "0.90"], ["B", "0.95"]],
        highlight_best=True,
    )
    assert r.success, r.error
    assert "\\textbf{0.95}" in r.output


def test_palette_ieee():
    r = PaletteTool().run(theme="ieee", count=5)
    assert r.success, r.error
    assert len(r.metadata["colors"]) == 5


def test_text_stats():
    r = TextStatsTool().run(text="Hello. 这是一段测试。")
    assert r.success, r.error
    assert r.metadata["cn_chars"] >= 4


def test_paper_title_template():
    r = PaperTitleTool().run(
        keywords="graph neural networks",
        style="serious",
        count=5,
        seed=42,
        use_llm=False,
    )
    assert r.success, r.error
    assert r.metadata["mode"] == "template-only"
    assert len(r.metadata["titles"]) == 3


def test_qrcode_optional():
    r = QrcodeTool().run(content="https://example.com")
    if not r.success:
        assert "qrcode" in (r.error or "").lower()
    else:
        assert r.output.endswith(".png")
