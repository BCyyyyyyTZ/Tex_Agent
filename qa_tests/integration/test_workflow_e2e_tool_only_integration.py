from __future__ import annotations

from pathlib import Path

from context.context_manager import ContextManager
from workflow.graph_builder import build_dynamic_graph
from workflow.workflow_parser import EdgeConfig, NodeConfig


def test_workflow_e2e__single_tool_node_markdown_section(tmp_path: Path) -> None:
    md = tmp_path / "doc.md"
    md.write_text("# A\n\nhello\n\n## B\n\nworld\n", encoding="utf-8")

    nodes = [
        NodeConfig(
            node_id="extract",
            node_type="tool",
            tool_name="markdown_section",
            config={
                "tool_input": {
                    "md_path": str(md),
                    "section_keywords": ["A"],
                    "mode": "content",
                    "max_chars": 2000,
                },
                "history_mode": "minimal",
            },
        )
    ]
    edges: list[EdgeConfig] = []
    app = build_dynamic_graph(
        nodes=nodes,
        edges=edges,
        context_manager=ContextManager(default_limit=10),
        default_workflow_name="qa_e2e",
    )
    state = {
        "messages": [],
        "current_node": "",
        "input": "ignored",
        "output": "",
        "error": None,
        "metadata": {"__run_output_dir__": str(tmp_path)},
        "retrieved_context": "",
    }
    out = app.invoke(state)
    assert out.get("error") is None
    assert "hello" in (out.get("output") or "")
    meta = out.get("metadata") or {}
    assert "extract" in meta
    assert "__execution_order__" in meta

