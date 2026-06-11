from __future__ import annotations

from workflow.workflow_parser import apply_depends_on_from_edges


def test_apply_depends_on_from_edges_linear_chain():
    cfg = {
        "nodes": [
            {"node_id": "arxiv", "node_type": "tool", "config": {"depends_on": []}},
            {"node_id": "summarize", "node_type": "agent", "config": {"depends_on": []}},
        ],
        "edges": [{"from_node": "arxiv", "to_node": "summarize"}],
    }
    apply_depends_on_from_edges(cfg)
    assert cfg["nodes"][0]["config"]["depends_on"] == []
    assert cfg["nodes"][1]["config"]["depends_on"] == ["arxiv"]


def test_apply_depends_on_from_edges_multi_upstream():
    cfg = {
        "nodes": [
            {"node_id": "a", "node_type": "agent"},
            {"node_id": "b", "node_type": "agent"},
            {"node_id": "c", "node_type": "agent", "config": {}},
        ],
        "edges": [
            {"from": "a", "to": "c"},
            {"from_node": "b", "to_node": "c"},
        ],
    }
    apply_depends_on_from_edges(cfg)
    assert cfg["nodes"][2]["config"]["depends_on"] == ["a", "b"]


def test_apply_depends_on_clears_stale_depends_on():
    cfg = {
        "nodes": [
            {"node_id": "x", "node_type": "agent", "config": {"depends_on": ["old_node"]}},
        ],
        "edges": [],
    }
    apply_depends_on_from_edges(cfg)
    assert cfg["nodes"][0]["config"]["depends_on"] == []
