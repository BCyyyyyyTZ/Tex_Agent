from __future__ import annotations

from core.state import normalize_messages_for_state, normalize_node_output


def test_normalize_messages_for_state__produces_list_of_dicts() -> None:
    out = normalize_messages_for_state(["hello", {"role": "user", "content": "x"}])
    assert isinstance(out, list)
    assert all(isinstance(x, dict) for x in out)
    assert out[0]["content"] == "hello"


def test_normalize_node_output__coerces_to_nodeoutput_dict() -> None:
    d = normalize_node_output("hello")
    assert d["result"] == "hello"
    assert d["status"] == "pass"
    assert isinstance(d.get("metadata"), dict)

