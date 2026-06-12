from __future__ import annotations

import pytest

from agents.base_agent import LlmClient


def test_parse_chat_completion__string_passthrough() -> None:
    assert LlmClient._parse_chat_completion_response(" hello ") == "hello"


def test_parse_chat_completion__dict_choices_message_content() -> None:
    raw = {"choices": [{"message": {"content": "hi"}}]}
    assert LlmClient._parse_chat_completion_response(raw) == "hi"


def test_parse_chat_completion__dict_fallback_keys() -> None:
    raw = {"output_text": "x"}
    assert LlmClient._parse_chat_completion_response(raw) == "x"


def test_parse_chat_completion__unknown_dict_raises() -> None:
    with pytest.raises(ValueError):
        LlmClient._parse_chat_completion_response({"a": 1})


def test_parse_chat_completion__none_raises() -> None:
    with pytest.raises(ValueError):
        LlmClient._parse_chat_completion_response(None)

