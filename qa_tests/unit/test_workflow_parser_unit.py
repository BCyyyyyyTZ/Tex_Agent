from __future__ import annotations

import pytest

from workflow.workflow_parser import YAMLWorkflowParser, apply_depends_on_from_edges


def test_parse_nodes__tool_without_tool_name_rejected() -> None:
    p = YAMLWorkflowParser()
    cfg = {"nodes": [{"node_id": "t1", "node_type": "tool", "tool_name": ""}]}
    with pytest.raises(ValueError):
        p.parse_nodes(cfg)


def test_parse_nodes__user_requires_prompt_template() -> None:
    p = YAMLWorkflowParser()
    cfg = {"nodes": [{"node_id": "u1", "node_type": "user", "config": {"input_schema": {"type": "text"}}}]}
    with pytest.raises(ValueError):
        p.parse_nodes(cfg)


def test_parse_nodes__parallel_fork_requires_branches() -> None:
    p = YAMLWorkflowParser()
    cfg = {"nodes": [{"node_id": "pf", "node_type": "parallel_fork", "parallel_branches": []}]}
    with pytest.raises(ValueError):
        p.parse_nodes(cfg)


def test_parse_nodes__parallel_join_requires_sources() -> None:
    p = YAMLWorkflowParser()
    cfg = {"nodes": [{"node_id": "pj", "node_type": "parallel_join", "source_branches": []}]}
    with pytest.raises(ValueError):
        p.parse_nodes(cfg)


def test_parse_edges__string_condition_is_ignored() -> None:
    p = YAMLWorkflowParser()
    edges = p.parse_edges(
        {
            "edges": [
                {"from_node": "a", "to_node": "b", "condition": "x > 0"},
                {"from_node": "a", "to_node": "c"},
            ]
        }
    )
    assert edges[0].condition is None
    assert edges[1].condition is None


def test_parse_edges__dict_condition_parsed() -> None:
    p = YAMLWorkflowParser()
    edges = p.parse_edges(
        {
            "edges": [
                {
                    "from_node": "a",
                    "to_node": "b",
                    "condition": {"field": "m.score", "op": "gte", "value": 0.5},
                    "priority": 2,
                }
            ]
        }
    )
    assert edges[0].condition is not None
    assert edges[0].condition.field == "m.score"
    assert edges[0].priority == 2


def test_apply_depends_on_from_edges__writes_depends_on_ordered_deduped() -> None:
    cfg = {
        "nodes": [{"node_id": "a", "config": {}}, {"node_id": "b", "config": {}}, {"node_id": "c"}],
        "edges": [
            {"from_node": "a", "to_node": "c"},
            {"from_node": "b", "to_node": "c"},
            {"from_node": "a", "to_node": "c"},
        ],
    }
    apply_depends_on_from_edges(cfg)
    c = next(n for n in cfg["nodes"] if n["node_id"] == "c")
    assert c["config"]["depends_on"] == ["a", "b"]

