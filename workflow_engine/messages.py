from __future__ import annotations

"""
工作流消息定义（Workflow Messages）。

工作流节点之间通过结构化消息通信，本模块使用 Pydantic 模型定义消息载体：
- TextMessage: 纯文本消息（通常来自 LLM 或用户输入）
- ToolCallMessage: 工具调用请求（由 LLM 生成或上游节点生成）
- ToolResultMessage: 工具执行结果（由 ToolNode 产生）
- MergedMessage: 多路输入的合并消息（由 Workflow 在节点执行前合并）

WorkflowMessage 是上述类型的联合类型，用于统一类型标注。
"""

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from core.message import ToolResult


class TextMessage(BaseModel):
    """
    文本消息。

    metadata 通常用于携带：
    - node_id: 产生该消息的节点
    - file_to_upload: 需要上传给 LLM 的文件路径列表（由上游节点/调用方写入）
    """
    type: Literal["text"] = "text"
    text: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class ToolCallMessage(BaseModel):
    """
    工具调用消息。

    tool_name 为工具注册名（见 tools/tool_list.py）。
    arguments 为工具 run(**arguments) 的入参字典。
    """
    type: Literal["tool_call"] = "tool_call"
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ToolResultMessage(BaseModel):
    """
    工具结果消息。

    tool_names: 本轮执行的工具名集合
    results: 与 tool_calls 对应的 ToolResult 列表（顺序与执行一致）
    """
    type: Literal["tool_result"] = "tool_result"
    tool_names: set[str]
    results: list[ToolResult]
    metadata: dict[str, Any] = Field(default_factory=dict)


class MergedMessage(BaseModel):
    """
    合并消息。

    Workflow 在节点执行前将多路输入聚合为单条消息，便于节点以统一方式处理：
    - text: 上游文本按段落合并
    - tool_calls: 汇总工具调用请求
    - tool_results: 汇总工具结果（tool_names/results）
    - metadata: 合并后的元数据
    """
    type: Literal["merged"] = "merged"
    text: str = ""
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    tool_results: dict[str, Any] = Field(default_factory=lambda: {"tool_names": set(), "results": []})
    metadata: dict[str, Any] = Field(default_factory=dict)


WorkflowMessage = TextMessage | ToolCallMessage | ToolResultMessage | MergedMessage

