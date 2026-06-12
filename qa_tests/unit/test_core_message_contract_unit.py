from __future__ import annotations

import pytest

from core.message import NodeOutput, WorkflowMessage, ensure_message


def test_workflow_message__legacy_string_coercion() -> None:
    m = WorkflowMessage.model_validate("hello")
    assert m.role == "user"
    assert m.source_type == "user"
    assert m.content == "hello"


def test_workflow_message__legacy_agent_tool_fields_mapped() -> None:
    m = WorkflowMessage.model_validate(
        {"role": "assistant", "agent_name": "A", "content": None}
    )
    assert m.source_type == "agent"
    assert m.source_id == "A"
    assert m.content == ""

    t = WorkflowMessage.model_validate(
        {"role": "tool", "tool_name": "T", "content": "x"}
    )
    assert t.source_type == "tool"
    assert t.source_id == "T"
    assert t.tool_name == "T"


def test_ensure_message__fills_defaults() -> None:
    m = ensure_message(
        {"content": "x"},
        default_role="assistant",
        default_source_type="system",
        default_source_id="d",
    )
    assert m.role == "user"
    assert m.source_id


def test_node_output__coerces_string_and_defaults() -> None:
    n = NodeOutput.model_validate("hello")
    assert n.result == "hello"
    assert n.summary
    assert n.status == "pass"


def test_node_output__invalid_confidence_coerces_to_zero() -> None:
    n = NodeOutput.model_validate({"result": "x", "confidence": "bad"})
    assert n.confidence == 0.0

