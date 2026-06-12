from __future__ import annotations

from datetime import date

from ui.web.conferences_data import list_deadlines


def test_list_deadlines__shape_and_sorting_is_stable_for_fixed_today() -> None:
    out = list_deadlines(fields=None, include_past=True, today=date(2026, 1, 1))
    assert isinstance(out, dict)
    assert out.get("today") == "2026-01-01"
    assert isinstance(out.get("deadlines"), list)
    assert out.get("count") == len(out["deadlines"])

    dls = out["deadlines"]
    if len(dls) >= 2:
        a, b = dls[0], dls[1]
        da = a.get("days_left")
        db = b.get("days_left")
        if isinstance(da, int) and isinstance(db, int) and da >= 0 and db >= 0:
            assert da <= db


def test_list_deadlines__field_filter_reduces_or_equals_total() -> None:
    all_out = list_deadlines(fields=None, include_past=True, today=date(2026, 1, 1))
    cv_out = list_deadlines(fields=["cv"], include_past=True, today=date(2026, 1, 1))
    assert cv_out["count"] <= all_out["count"]
    for it in cv_out["deadlines"]:
        assert "cv" in (it.get("fields") or [])

