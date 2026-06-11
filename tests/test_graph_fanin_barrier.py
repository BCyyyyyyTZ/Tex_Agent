"""多入边自动 join 汇聚（graph_builder fan-in join）单元测试。"""
from __future__ import annotations

from workflow.graph_builder import (
    _collect_fanin_join_targets,
    _edges_excluding_fanin_joins,
)
from workflow.workflow_parser import EdgeConfig, NodeConfig


def _node(node_id: str, node_type: str = "agent") -> NodeConfig:
    return NodeConfig(node_id=node_id, node_type=node_type)


def test_collect_fanin_join_targets_detects_fork_pattern() -> None:
    nodes = [
        _node("checklist_prepare", "tool"),
        _node("chapter_routing", "tool"),
        _node("fork_checkers", "parallel_fork"),
        _node("join_checkers", "parallel_join"),
    ]
    edges = [
        EdgeConfig("checklist_prepare", "fork_checkers"),
        EdgeConfig("chapter_routing", "fork_checkers"),
        EdgeConfig("abstract_checker", "join_checkers"),
        EdgeConfig("method_checker", "join_checkers"),
    ]
    targets = _collect_fanin_join_targets(nodes, edges)
    assert targets == {
        "fork_checkers": ["checklist_prepare", "chapter_routing"],
    }


def test_collect_fanin_join_skips_parallel_join() -> None:
    nodes = [
        _node("a"),
        _node("b"),
        _node("join_checkers", "parallel_join"),
    ]
    edges = [
        EdgeConfig("a", "join_checkers"),
        EdgeConfig("b", "join_checkers"),
    ]
    assert _collect_fanin_join_targets(nodes, edges) == {}


def test_edges_excluding_fanin_joins_removes_merged_edges() -> None:
    edges = [
        EdgeConfig("checklist_prepare", "fork_checkers"),
        EdgeConfig("chapter_routing", "fork_checkers"),
        EdgeConfig("fork_checkers", "extract_abstract"),
    ]
    targets = {"fork_checkers": ["checklist_prepare", "chapter_routing"]}
    remaining = _edges_excluding_fanin_joins(edges, targets)

    assert EdgeConfig("fork_checkers", "extract_abstract") in remaining
    assert not any(
        e.to_node == "fork_checkers" for e in remaining
    )


def test_edges_excluding_fanin_joins_empty_when_no_targets() -> None:
    edges = [EdgeConfig("a", "b")]
    assert _edges_excluding_fanin_joins(edges, {}) == edges
