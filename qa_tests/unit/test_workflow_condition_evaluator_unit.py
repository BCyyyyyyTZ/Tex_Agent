from __future__ import annotations

from dataclasses import dataclass

import pytest

from workflow.condition_evaluator import ConditionExpr, evaluate_condition, route_by_conditions


def test_condition_expr__invalid_op_rejected() -> None:
    with pytest.raises(ValueError):
        ConditionExpr(field="a", op="bad")


def test_condition_expr_from_dict__missing_field_rejected() -> None:
    with pytest.raises(ValueError):
        ConditionExpr.from_dict({"op": "eq", "value": 1})


def test_evaluate_condition__exists_and_not_exists() -> None:
    state = {"a": {"b": 1}}
    ok, _ = evaluate_condition(state, ConditionExpr(field="a.b", op="exists"))
    assert ok is True
    ok, _ = evaluate_condition(state, ConditionExpr(field="a.c", op="exists"))
    assert ok is False
    ok, _ = evaluate_condition(state, ConditionExpr(field="a.c", op="not_exists"))
    assert ok is True


def test_evaluate_condition__numeric_comparisons() -> None:
    state = {"x": 10, "y": "2"}
    ok, _ = evaluate_condition(state, ConditionExpr(field="x", op="gt", value=3))
    assert ok is True
    ok, _ = evaluate_condition(state, ConditionExpr(field="y", op="gte", value=2))
    assert ok is True


def test_evaluate_condition__contains_and_in_ops() -> None:
    state = {"s": "hello world", "v": "b"}
    ok, _ = evaluate_condition(state, ConditionExpr(field="s", op="contains", value="world"))
    assert ok is True
    ok, _ = evaluate_condition(state, ConditionExpr(field="v", op="in", value=["a", "b"]))
    assert ok is True
    ok, _ = evaluate_condition(state, ConditionExpr(field="v", op="not_in", value=["a", "c"]))
    assert ok is True


def test_evaluate_condition__missing_field_short_circuit() -> None:
    ok, diag = evaluate_condition({"a": 1}, ConditionExpr(field="b", op="eq", value=1))
    assert ok is False
    assert "not found" in diag


def test_evaluate_condition__type_error_returns_false() -> None:
    ok, diag = evaluate_condition({"x": "abc"}, ConditionExpr(field="x", op="gt", value=1))
    assert ok is False
    assert "comparison error" in diag


@dataclass
class _Edge:
    from_node: str
    to_node: str
    condition: ConditionExpr | None = None
    priority: int = 0


def test_route_by_conditions__priority_first_match() -> None:
    state = {"m": {"score": 0.4}}
    edges = [
        _Edge("a", "low", ConditionExpr(field="m.score", op="lt", value=0.5), priority=10),
        _Edge("a", "high", ConditionExpr(field="m.score", op="gte", value=0.5), priority=1),
    ]
    assert route_by_conditions(state, edges, fallback="fallback") == "low"


def test_route_by_conditions__fallback_when_no_condition_matches() -> None:
    state = {"m": {"score": 0.4}}
    edges = [
        _Edge("a", "high", ConditionExpr(field="m.score", op="gt", value=0.9), priority=10),
    ]
    assert route_by_conditions(state, edges, fallback="fallback") == "fallback"

