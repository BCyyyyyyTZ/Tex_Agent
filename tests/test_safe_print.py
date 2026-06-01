"""safe_print 在 GBK 控制台下不抛错。"""
import io
import sys

from utils.display import safe_print


def test_safe_print_survives_gbk_console(monkeypatch):
    buf = io.BytesIO()
    fake_stdout = io.TextIOWrapper(buf, encoding="gbk", errors="strict")
    monkeypatch.setattr(sys, "stdout", fake_stdout)
    safe_print("\n🧠 [1/4] 初始化规划器...")
    assert buf.getvalue()
