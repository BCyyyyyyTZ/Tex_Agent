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
    tool_name: str
    result: ToolResult
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def success(self) -> bool:
        return bool(self.result.success)

    @property
    def output(self) -> str:
        return self.result.output

    @property
    def error(self) -> Optional[str]:
        return self.result.error


WorkflowMessage = TextMessage | ToolCallMessage | ToolResultMessage

