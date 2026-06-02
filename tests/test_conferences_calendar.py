"""顶会日历静态数据与 API 逻辑（不请求网络）。"""
from datetime import date

from ui.web.conferences_data import list_deadlines


def test_list_deadlines_cv_filter():
    data = list_deadlines(fields=["cv"], today=date(2026, 6, 1))
    assert data["count"] >= 1
    for it in data["deadlines"]:
        assert "cv" in it["fields"]


def test_list_deadlines_sorted_by_days():
    data = list_deadlines(today=date(2026, 6, 1))
    days = [it["days_left"] for it in data["deadlines"] if it.get("days_left") is not None and it["days_left"] >= 0]
    assert days == sorted(days)
