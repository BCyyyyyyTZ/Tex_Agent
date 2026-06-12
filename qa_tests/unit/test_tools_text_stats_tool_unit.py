from __future__ import annotations

from tools.text_stats_tool import TextStatsTool


def test_text_stats_tool__empty_text_fails() -> None:
    tool = TextStatsTool()
    r = tool.run("")
    assert r.success is False
    assert "不能为空" in (r.error or "")


def test_text_stats_tool__basic_stats_present() -> None:
    tool = TextStatsTool()
    r = tool.run("hello world.\n你好。")
    assert r.success is True
    assert "基础统计" in (r.output or "")
    assert isinstance(r.metadata.get("chars"), int)

