"""
统一通信协议定义。
- WorkflowMessage: 工作流统一消息对象（兼容历史字段）
- NodeOutput: 工作流统一节点结构化输出对象
- ToolResult: 工具层执行返回对象（仅工具层使用）
"""
from typing import Any, Dict, Iterable, Literal, Optional, Union
from datetime import datetime, timezone
from pydantic import BaseModel, Field, model_validator

MESSAGE_SCHEMA_VERSION = "2.0"
NODE_OUTPUT_SCHEMA_VERSION = "1.0"


class WorkflowMessage(BaseModel):
    """
    工作流统一消息对象。

    语义约束：
    - role: 消息在对话中的角色
    - source_type/source_id: 消息来源（agent/tool/user/system）
    - content: 文本主体
    - metadata/payload: 可审计扩展信息
    """

    role: Literal["user", "assistant", "system", "tool"] = "user"
    source_type: Literal["agent", "tool", "user", "system"] = "system"
    source_id: str = "unknown"
    content: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)
    payload: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    schema_version: str = MESSAGE_SCHEMA_VERSION

    model_config = {"frozen": False}

    @model_validator(mode="before")
    @classmethod
    def _compat_legacy_fields(cls, raw: Any) -> Any:
        """
        兼容旧字段：
        - agent_name/tool_name -> source_id/source_type
        - content 允许 None（自动转空串）
        """
        if isinstance(raw, cls):
            return raw
        if isinstance(raw, str):
            return {
                "role": "user",
                "source_type": "user",
                "source_id": "legacy_text",
                "content": raw,
            }
        if not isinstance(raw, dict):
            return {
                "role": "user",
                "source_type": "user",
                "source_id": "legacy_unknown",
                "content": str(raw),
            }

        data = dict(raw)
        role = str(data.get("role", "user"))
        agent_name = data.get("agent_name")
        tool_name = data.get("tool_name")
        source_type = data.get("source_type")
        source_id = data.get("source_id")

        if source_type == "chat":
            source_type = "user" if role == "user" else "agent"

        if not source_type:
            if tool_name or role == "tool":
                source_type = "tool"
            elif role == "user":
                source_type = "user"
            elif role == "assistant":
                source_type = "agent"
            else:
                source_type = "system"
        if not source_id:
            source_id = tool_name or agent_name or "unknown"

        data["source_type"] = source_type
        data["source_id"] = str(source_id)
        data["content"] = "" if data.get("content") is None else str(data.get("content"))
        data["schema_version"] = str(data.get("schema_version") or MESSAGE_SCHEMA_VERSION)
        if not isinstance(data.get("metadata"), dict):
            data["metadata"] = {}
        if not isinstance(data.get("payload"), dict):
            data["payload"] = {}
        return data

    # ---- 历史兼容只读属性（避免旧代码立刻崩溃） ----
    @property
    def agent_name(self) -> str:
        return self.source_id

    @property
    def tool_name(self) -> str:
        if self.source_type == "tool":
            return self.source_id
        return str(self.metadata.get("tool_name", "unknown"))

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump(mode="json")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkflowMessage":
        return cls.model_validate(data)


MessageLike = Union[str, Dict[str, Any], WorkflowMessage]

# 向后兼容：旧代码仍引用 AgentMessage
AgentMessage = WorkflowMessage


def ensure_message(
    raw: MessageLike,
    *,
    default_role: Literal["user", "assistant", "system", "tool"] = "assistant",
    default_source_type: Literal["agent", "tool", "user", "system"] = "system",
    default_source_id: str = "unknown",
) -> WorkflowMessage:
    """将任意输入归一化为统一消息对象。"""
    if isinstance(raw, WorkflowMessage):
        msg = raw
    elif isinstance(raw, dict):
        msg = WorkflowMessage.model_validate(raw)
    elif isinstance(raw, str):
        msg = WorkflowMessage(
            role=default_role,
            source_type=default_source_type,
            source_id=default_source_id,
            content=raw,
        )
    else:
        msg = WorkflowMessage(
            role=default_role,
            source_type=default_source_type,
            source_id=default_source_id,
            content=str(raw),
        )

    if not msg.source_id:
        msg.source_id = default_source_id
    if not msg.source_type:
        msg.source_type = default_source_type
    if not msg.role:
        msg.role = default_role
    return msg


def ensure_message_dict(
    raw: MessageLike,
    *,
    default_role: Literal["user", "assistant", "system", "tool"] = "assistant",
    default_source_type: Literal["agent", "tool", "user", "system"] = "system",
    default_source_id: str = "unknown",
) -> Dict[str, Any]:
    return ensure_message(
        raw,
        default_role=default_role,
        default_source_type=default_source_type,
        default_source_id=default_source_id,
    ).to_dict()


def normalize_message_list(messages: Iterable[MessageLike]) -> list[Dict[str, Any]]:
    """统一 state.messages 的唯一写回格式：list[dict]。"""
    return [ensure_message_dict(msg) for msg in messages]


class NodeOutput(BaseModel):
    """
    工作流节点统一结构化输出协议。
    存储位置：state.metadata[node_id]
    """

    result: str = ""
    summary: str = ""
    confidence: float = 0.0
    status: Literal["pass", "fail", "partial", "needs_user", "invalid"] = "pass"
    metadata: Dict[str, Any] = Field(default_factory=dict)
    schema_version: str = NODE_OUTPUT_SCHEMA_VERSION

    @model_validator(mode="before")
    @classmethod
    def _coerce_fields(cls, raw: Any) -> Any:
        if isinstance(raw, cls):
            return raw
        if isinstance(raw, str):
            return {"result": raw, "summary": raw[:80]}
        if not isinstance(raw, dict):
            return {"result": str(raw), "summary": str(raw)[:80]}
        data = dict(raw)
        data["result"] = "" if data.get("result") is None else str(data.get("result"))
        if data.get("summary") is None:
            data["summary"] = str(data["result"])[:80]
        else:
            data["summary"] = str(data.get("summary"))
        try:
            data["confidence"] = float(data.get("confidence", 0.0))
        except Exception:
            data["confidence"] = 0.0
        if not isinstance(data.get("metadata"), dict):
            data["metadata"] = {}
        data["schema_version"] = str(data.get("schema_version") or NODE_OUTPUT_SCHEMA_VERSION)
        return data

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump(mode="json")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NodeOutput":
        return cls.model_validate(data)


class ToolResult(BaseModel):
    """
    工具执行结果的标准返回格式。

    所有 BaseTool 子类的 run()/arun() 方法均返回此类型，
    保证工具结果格式的一致性，便于 Agent 统一处理。

    Attributes:
        success: 工具是否执行成功。
        output: 工具输出的文本内容（失败时为空字符串）。
        error: 若执行失败，记录错误信息；成功时为 None。
        metadata: 扩展元数据（如结果数量、耗时、数据来源等）。
    """

    success: bool
    output: str
    error: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
