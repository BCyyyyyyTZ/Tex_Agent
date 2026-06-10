"""
核心协议（core.message）契约测试。

目标：
1) 验证 WorkflowMessage / NodeOutput / ToolResult 等“跨模块共享协议”的默认值、兼容性与序列化行为；
2) 该类协议一旦破坏，会影响 workflow_engine / tools / agents / ui 等多个模块，因此优先使用稳定的契约测试做回归保护。

注意：
- 本文件只做纯单元级测试，不依赖外部服务与网络；
- 断言只关注“协议形态与关键字段语义”，不测试具体业务逻辑。
"""

from __future__ import annotations

import json

import pytest

from core.message import (
    MESSAGE_SCHEMA_VERSION,
    NODE_OUTPUT_SCHEMA_VERSION,
    AgentMessage,
    NodeOutput,
    ToolResult,
    WorkflowMessage,
    ensure_message,
    ensure_message_dict,
    normalize_message_list,
)


def test_workflow_message_accepts_legacy_fields_and_coerces_types() -> None:
    """
    旧代码可能仍传 agent_name/tool_name/content=None 等字段：
    - agent_name/tool_name 应映射到 source_id/source_type；
    - content=None 应被归一化为空字符串；
    - metadata/payload 不为 dict 时应被修正为 dict。
    """
    msg = WorkflowMessage.model_validate(
        {
            "role": "assistant",
            "agent_name": "LegacyAgent",
            "content": None,
            "metadata": None,
            "payload": None,
        }
    )
    assert msg.role == "assistant"
    assert msg.source_type == "agent"
    assert msg.source_id == "LegacyAgent"
    assert msg.content == ""
    assert isinstance(msg.metadata, dict)
    assert isinstance(msg.payload, dict)
    assert msg.schema_version == MESSAGE_SCHEMA_VERSION


def test_workflow_message_string_input_becomes_user_message() -> None:
    """
    WorkflowMessage 允许直接用 str 作为输入（历史兼容），应自动转换为 user 消息。
    """
    msg = WorkflowMessage.model_validate("hello")
    assert msg.role == "user"
    assert msg.source_type == "user"
    assert msg.content == "hello"
    assert msg.schema_version == MESSAGE_SCHEMA_VERSION


@pytest.mark.parametrize(
    ("raw", "role", "source_type", "source_id", "content"),
    [
        ("hi", "assistant", "system", "unknown", "hi"),
        ({"role": "user", "content": "u"}, "user", "user", "unknown", "u"),
        (WorkflowMessage(role="tool", source_type="tool", source_id="t", content="x"), "tool", "tool", "t", "x"),
        (123, "assistant", "system", "unknown", "123"),
    ],
)
def test_ensure_message_normalizes_various_inputs(
    raw, role: str, source_type: str, source_id: str, content: str
) -> None:
    """
    ensure_message 是多个模块写入 state.messages 的统一入口：
    - 支持 str/dict/WorkflowMessage/其他对象；
    - 可补齐默认 role/source_type/source_id；
    - 应保证返回 WorkflowMessage 且字段非空。
    """
    msg = ensure_message(
        raw,
        default_role=role,  # 这里显式传入默认值，确保行为可预测
        default_source_type=source_type,
        default_source_id=source_id,
    )
    assert isinstance(msg, WorkflowMessage)
    assert msg.role == role
    assert msg.source_type == source_type
    assert msg.source_id == source_id
    assert msg.content == content


def test_ensure_message_dict_round_trip() -> None:
    """
    ensure_message_dict 应输出 JSON 友好的 dict；
    该 dict 能再次被 WorkflowMessage.from_dict / model_validate 接受。
    """
    d = ensure_message_dict({"role": "assistant", "content": "ok", "agent_name": "A"})
    assert isinstance(d, dict)
    msg = WorkflowMessage.from_dict(d)
    assert msg.role == "assistant"
    assert msg.source_id == "A"
    assert msg.content == "ok"

    # 额外检查：可被 json 序列化（UI 与日志系统常用）
    json.dumps(d, ensure_ascii=False)


def test_normalize_message_list_is_canonical_dict_list() -> None:
    """
    normalize_message_list 规定 state.messages 的写回格式必须是 list[dict]。
    """
    out = normalize_message_list(
        [
            "s1",
            {"role": "user", "content": "u1"},
            WorkflowMessage(role="assistant", source_type="agent", source_id="X", content="a1"),
        ]
    )
    assert isinstance(out, list)
    assert all(isinstance(x, dict) for x in out)
    assert out[0]["content"] == "s1"
    assert out[1]["role"] == "user"
    assert out[2]["source_id"] == "X"


def test_agent_message_is_alias_of_workflow_message() -> None:
    """
    core.message 中 AgentMessage 是 WorkflowMessage 的向后兼容别名。
    测试目的：避免未来重构误删该别名导致历史代码崩溃。
    """
    msg = AgentMessage(role="assistant", source_type="agent", source_id="a", content="c")
    assert isinstance(msg, WorkflowMessage)


def test_node_output_coerce_and_defaults() -> None:
    """
    NodeOutput 用于 workflow 写回 state.metadata[node_id]：
    - 允许从 str/任意对象/dict 初始化；
    - summary None 时应自动生成；
    - confidence 应可被强制转换为 float；
    - metadata 缺失或类型错误应归一化为 dict。
    """
    n1 = NodeOutput.model_validate("hello")
    assert n1.result == "hello"
    assert n1.summary == "hello"
    assert n1.schema_version == NODE_OUTPUT_SCHEMA_VERSION

    n2 = NodeOutput.model_validate({"result": None, "summary": None, "confidence": "0.7", "metadata": None})
    assert n2.result == ""
    assert isinstance(n2.summary, str) and len(n2.summary) >= 0
    assert n2.confidence == pytest.approx(0.7)
    assert isinstance(n2.metadata, dict)


def test_tool_result_is_json_serializable_and_has_stable_fields() -> None:
    """
    ToolResult 是工具层统一返回结构：
    - success/output/error/metadata 字段应稳定存在；
    - 可序列化为 JSON（便于 UI/日志/测试输出）。
    """
    r = ToolResult(success=True, output="ok", error="", metadata={"k": 1})
    d = r.model_dump(mode="json")
    assert d["success"] is True
    assert d["output"] == "ok"
    assert d["metadata"]["k"] == 1
    json.dumps(d, ensure_ascii=False)

