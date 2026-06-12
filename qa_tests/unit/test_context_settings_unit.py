from __future__ import annotations

from config.context_settings import (
    PROFILE_PIPELINE,
    is_persona_confirmation_reply,
    match_intent,
    resolve_graph_context_profile,
    resolve_terminal_delivery_style,
    valid_profiles,
)


def test_valid_profiles__contains_pipeline() -> None:
    assert PROFILE_PIPELINE in valid_profiles()


def test_match_intent__echo_smoke() -> None:
    assert match_intent("echo", "echo hello") is True or match_intent("echo", "echo") is True


def test_resolve_graph_context_profile__explicit_wins() -> None:
    p = resolve_graph_context_profile("any", explicit=PROFILE_PIPELINE, mode="task")
    assert p == PROFILE_PIPELINE


def test_resolve_terminal_delivery_style__non_terminal_is_none() -> None:
    out = resolve_terminal_delivery_style(
        "hi", {}, profile=PROFILE_PIPELINE, is_terminal=False
    )
    assert out == "none"


def test_is_persona_confirmation_reply__short_text_false() -> None:
    assert is_persona_confirmation_reply("ok") is False

