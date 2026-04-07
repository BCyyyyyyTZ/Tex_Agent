"""
Agent 间通信协议定义。
AgentMessage 是所有 Agent、节点之间传递信息的标准载体。
ToolResult 是所有工具执行结果的标准返回格式。
"""
from typing import Literal, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field


class AgentMessage(BaseModel):
    """
    Agent 间标准消息对象。

    作为工作流中所有节点之间、Agent 之间通信的统一载体，
    确保消息格式的一致性，并预留 metadata 字段用于未来扩展
    （如情感标注、路由标签、分支 ID 等）。

    Attributes:
        role: 消息角色。"user" 表示用户/上游节点输入，
              "assistant" 表示 Agent 响应，"system" 表示系统提示，
              "tool" 表示工具执行结果。
        content: 消息的文本内容。
        agent_name: 消息发送方的 Agent 名称，"user" 表示来自用户/节点构造。
        timestamp: 消息创建的 UTC 时间戳（自动填充）。
        metadata: 扩展元数据字典，预留给路由标签、情感标注、分支 ID 等未来功能。
    """

    role: Literal["user", "assistant", "system", "tool"] = "user"
    content: str
    agent_name: str = "unknown"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict = Field(default_factory=dict)

    model_config = {"frozen": False}

    def to_dict(self) -> dict:
        """序列化为字典，用于存入 WorkflowState.messages(JSON 兼容格式）。"""
        return self.model_dump(mode="json")

    @classmethod
    def from_dict(cls, data: dict) -> "AgentMessage":
        """从字典反序列化为 AgentMessage 对象。"""
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
    metadata: dict = Field(default_factory=dict)
