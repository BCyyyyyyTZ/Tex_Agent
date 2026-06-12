from __future__ import annotations

from utils.reply_format import normalize_reply_display, strip_citation_artifacts


def test_strip_citation_artifacts__removes_ascii_cite_turn() -> None:
    out = strip_citation_artifacts("hello cite turn0search0 world")
    assert "turn0search0" not in out
    assert "cite" not in out.lower()


def test_normalize_reply_display__merges_short_lines_but_keeps_headers() -> None:
    raw = "一句\n两句\n\n# Title\n\n- a\n- b\n\n短\n句\n"
    out = normalize_reply_display(raw, short_para_chars=10)
    assert "# Title" in out
    assert "- a" in out
    assert "- b" in out
    assert "一句 两句" in out

