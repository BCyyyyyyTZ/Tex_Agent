from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from core.message import ToolResult


class TextMessage(BaseModel):
    type: Literal["text"] = "text"
    text: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class ToolCallMessage(BaseModel):
    type: Literal["tool_call"] = "tool_call"
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ToolResultMessage(BaseModel):
    type: Literal["tool_result"] = "tool_result"
    tool_names: set[str]
    results: list[ToolResult]
    metadata: dict[str, Any] = Field(default_factory=dict)


class MergedMessage(BaseModel):
    type: Literal["merged"] = "merged"
    text: str = ""
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    tool_results: dict[str, Any] = Field(default_factory=lambda: {"tool_names": set(), "results": []})
    metadata: dict[str, Any] = Field(default_factory=dict)


WorkflowMessage = TextMessage | ToolCallMessage | ToolResultMessage | MergedMessage

