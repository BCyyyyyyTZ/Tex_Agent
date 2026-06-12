from __future__ import annotations

import importlib

import pytest

def _validate(node_ids, edge_pairs) -> None:
    try:
        m = importlib.import_module("ui.web.server")
    except RuntimeError as e:
        if "python-multipart" in str(e):
            pytest.skip(str(e))
        raise
    m._validate_workflow_dag_and_flow(node_ids, edge_pairs)


def test_validate_workflow_dag_and_flow__single_node_ok() -> None:
    _validate({"a"}, [])


def test_validate_workflow_dag_and_flow__simple_chain_ok() -> None:
    _validate({"a", "b", "c"}, [("a", "b"), ("b", "c")])


def test_validate_workflow_dag_and_flow__self_loop_rejected() -> None:
    with pytest.raises(ValueError) as e:
        _validate({"a"}, [("a", "a")])
    assert "自环" in str(e.value)


def test_validate_workflow_dag_and_flow__cycle_rejected() -> None:
    with pytest.raises(ValueError) as e:
        _validate({"a", "b"}, [("a", "b"), ("b", "a")])
    assert "有向环" in str(e.value)


def test_validate_workflow_dag_and_flow__multiple_sources_rejected() -> None:
    with pytest.raises(ValueError) as e:
        _validate({"a", "b", "c"}, [("a", "c"), ("b", "c")])
    assert "入口节点" in str(e.value)


def test_validate_workflow_dag_and_flow__unreachable_node_rejected() -> None:
    with pytest.raises(ValueError) as e:
        _validate({"a", "b", "c"}, [("a", "b")])
    assert "无法到达" in str(e.value) or "不连通" in str(e.value)

