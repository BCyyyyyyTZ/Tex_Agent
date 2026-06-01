"""上下文配置加载与行为解析（不调用 LLM）。"""
from __future__ import annotations

from config.context_settings import (
    PROFILE_AUTO_SINGLE,
    PROFILE_DIALOGUE,
    PROFILE_LEGACY,
    PROFILE_PIPELINE,
    build_agent_prompt,
    filter_messages_for_memory,
    load_context_config,
    match_intent,
    memory_search_enabled,
    reload_context_config,
    resolve_graph_context_profile,
    resolve_node_context_behavior,
    resolve_terminal_delivery_style,
    should_save_assistant_to_dialogue_context,
    is_persona_confirmation_reply,
)
from core.message import WorkflowMessage
from workflow.graph_builder import build_dynamic_graph
from workflow.workflow_parser import NodeConfig


def test_config_loads():
    cfg = load_context_config()
    assert cfg.get("version") == 1
    assert "profiles" in cfg
    assert "intent_patterns" in cfg


def test_legacy_profile_unchanged_for_checklist():
    assert resolve_graph_context_profile("checklist_multi_v4", mode="task") == PROFILE_LEGACY
    assert resolve_graph_context_profile("latex_diagnose_v0", mode="task") == PROFILE_LEGACY
    assert resolve_graph_context_profile("thesis_checklist_task", mode="task") == PROFILE_LEGACY


def test_mode_routing_from_config():
    assert resolve_graph_context_profile("anything", mode="auto") == PROFILE_AUTO_SINGLE
    assert resolve_graph_context_profile("anything", mode="plan") == "dialogue"
    assert resolve_graph_context_profile("default", mode="task") == PROFILE_PIPELINE


def test_intent_from_config_json():
    reload_context_config()
    assert match_intent("echo", "请原封不动输出")
    assert match_intent("persona_write", "请记住我是张三")


def test_filter_system_chat_source_id_maps_to_agent():
    """source_id=chat 是对话通道；勿把 source_type 写成 chat（会触发 WorkflowMessage 校验失败）。"""
    raw = [
        WorkflowMessage(
            role="assistant",
            source_type="system",
            source_id="chat",
            content="上一轮助手回复摘要",
        ),
    ]
    filtered = filter_messages_for_memory(raw, PROFILE_DIALOGUE)
    assert len(filtered) == 1
    assert filtered[0].source_type == "agent"
    assert filtered[0].source_id == "chat"


def test_filter_skips_prompt_builder():
    raw = [
        WorkflowMessage(
            role="user",
            source_type="system",
            source_id="n_prompt_builder",
            content="[你的具体任务]\nxxx\n[原始任务背景]\nyyy",
        ),
        WorkflowMessage(
            role="user",
            source_type="user",
            source_id="chat",
            content="讲 agent 记忆",
        ),
    ]
    filtered = filter_messages_for_memory(raw, PROFILE_PIPELINE)
    assert len(filtered) == 1
    assert "agent" in filtered[0].content


def test_behavior_auto_memory_off():
    b = resolve_node_context_behavior(
        {}, graph_profile=PROFILE_AUTO_SINGLE, user_input="你好", is_terminal=True
    )
    assert b.memory_search_enabled is False
    assert b.mem_limit == 0


def test_persona_skip_from_config_markers():
    reload_context_config()
    text = "已记录。已写入用户画像。用户画像更新完成。"
    assert is_persona_confirmation_reply(text)
    b = resolve_node_context_behavior(
        {}, graph_profile=PROFILE_AUTO_SINGLE, user_input="", is_terminal=True
    )
    assert not should_save_assistant_to_dialogue_context(text, b)


def test_auto_long_form_uses_full_delivery():
    style = resolve_terminal_delivery_style(
        "请写一篇3000字的影评",
        {},
        profile=PROFILE_AUTO_SINGLE,
        is_terminal=True,
    )
    assert style == "full"


def test_auto_graph_compiles():
    cfg = load_context_config()["profiles"]["auto_single"]["agent"]
    nodes = [
        NodeConfig(
            node_id=cfg["node_id"],
            node_type="agent",
            agent_name=cfg.get("agent_name", "SimpleAgent"),
            config={"context_profile": PROFILE_AUTO_SINGLE},
        )
    ]
    app = build_dynamic_graph(
        nodes,
        [],
        default_workflow_name="auto_single",
        default_context_profile=PROFILE_AUTO_SINGLE,
    )
    assert app is not None
