from __future__ import annotations

from core import state as st


def test_merge_metadata__deep_merge_and_execution_order_dedupes() -> None:
    base = {"a": {"x": 1}, "__execution_order__": ["n1"]}
    upd = {"a": {"y": 2}, "__execution_order__": ["n1", "n2"]}
    out = st._merge_metadata(base, upd)
    assert out["a"] == {"x": 1, "y": 2}
    assert out["__execution_order__"] == ["n1", "n2"]


def test_last_nonempty__keeps_previous_when_empty() -> None:
    assert st._last_nonempty("a", "") == "a"
    assert st._last_nonempty("a", None) == "a"
    assert st._last_nonempty("a", "b") == "b"


def test_first_error__keeps_first() -> None:
    assert st._first_error("e1", None) == "e1"
    assert st._first_error(None, "e2") == "e2"

