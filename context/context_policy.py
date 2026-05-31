"""
上下文策略对外接口（实现已迁至 config/context_settings.py + context_config.json）。
保留本模块以兼容现有 import 路径。
"""
from typing import Optional

from config.context_settings import (  # noqa: F401
    PROFILE_AUTO_SINGLE,
    PROFILE_DIALOGUE,
    PROFILE_LEGACY,
    PROFILE_PIPELINE,
    NodeContextBehavior,
    build_agent_prompt,
    filter_messages_for_memory,
    format_dialogue_history,
    get_profile_agent_spec,
    get_profile_node_defaults,
    load_context_config,
    make_dialogue_save_messages,
    match_intent,
    reload_context_config,
    resolve_graph_context_profile,
    resolve_node_context_behavior,
    resolve_node_context_profile,
    resolve_terminal_delivery_style,
    should_save_assistant_to_dialogue_context,
    valid_profiles,
)
from config.context_settings import (  # noqa: F401
    is_persona_confirmation_reply as is_persona_confirmation_reply,
)
from config.context_settings import match_intent as _match_intent


def should_persona_file_write(user_input: str, profile: str) -> bool:
    from config.context_settings import resolve_node_context_behavior

    b = resolve_node_context_behavior(
        {}, graph_profile=profile, user_input=user_input, is_terminal=False
    )
    return b.persona_file_write


def should_persona_prompt_read(
    user_input: str, profile: str, node_config: Optional[dict] = None,
) -> bool:
    from config.context_settings import resolve_node_context_behavior

    b = resolve_node_context_behavior(
        node_config or {},
        graph_profile=profile,
        user_input=user_input,
        is_terminal=False,
    )
    return b.persona_prompt_read


def should_persona_writeback(user_input: str, profile: str) -> bool:
    return should_persona_file_write(user_input, profile)


def is_echo_task(text: str) -> bool:
    return _match_intent("echo", text)


def memory_search_enabled(node_config: dict, profile: str) -> bool:
    from config.context_settings import resolve_node_context_behavior

    b = resolve_node_context_behavior(
        node_config,
        graph_profile=profile,
        user_input="",
        is_terminal=False,
    )
    return b.memory_search_enabled


def default_include_metadata_chain(
    profile: str, *, is_terminal: bool, node_config: dict
) -> bool:
    if "include_metadata_chain" in node_config:
        return bool(node_config.get("include_metadata_chain"))
    from config.context_settings import _profile_spec

    spec = _profile_spec(profile)
    if "include_metadata_chain" in spec:
        return bool(spec.get("include_metadata_chain"))
    if is_terminal:
        return bool(spec.get("include_metadata_chain_terminal", False))
    return bool(spec.get("include_metadata_chain_non_terminal", False))


def dialogue_max_turns(profile: str) -> int:
    from config.context_settings import _profile_spec

    return int(_profile_spec(profile).get("dialogue_max_turns", 4) or 4)


def build_auto_chat_prompt(**kwargs):
    """已废弃：请使用 build_agent_prompt(..., behavior=...)。"""
    from config.context_settings import NodeContextBehavior, resolve_node_context_behavior

    behavior = resolve_node_context_behavior(
        {"context_profile": PROFILE_AUTO_SINGLE},
        graph_profile=PROFILE_AUTO_SINGLE,
        user_input=kwargs.get("user_input", ""),
        is_terminal=True,
    )
    return build_agent_prompt(
        user_input=kwargs["user_input"],
        subtask="",
        upstream_ctx="",
        built_context=kwargs.get("built_context", ""),
        inline_contracts=kwargs.get("inline_contracts", ""),
        behavior=behavior,
    )
