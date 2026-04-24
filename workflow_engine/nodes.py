from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable, Optional, Protocol

from core.message import ToolResult
from tools.base_tool import BaseTool
from workflow_engine.messages import TextMessage, ToolCallMessage, ToolResultMessage, WorkflowMessage


class LlmClientLike(Protocol):
    def response(self, prompt: str, *args: Any, **kwargs: Any) -> str: ...


class BaseNode(ABC):
    def __init__(self, node_id: str):
        self.node_id = node_id

    @abstractmethod
    def run(self, message: WorkflowMessage, context: Any) -> Optional[WorkflowMessage]:
        raise NotImplementedError


class FunctionNode(BaseNode):
    def __init__(self, node_id: str, fn: Callable[[WorkflowMessage, Any], WorkflowMessage]):
        super().__init__(node_id=node_id)
        self.fn = fn

    def run(self, message: WorkflowMessage, context: Any) -> Optional[WorkflowMessage]:
        return self.fn(message, context)


class LlmNode(BaseNode):
    def __init__(
        self,
        node_id: str,
        llm_client: LlmClientLike,
        *,
        prompt: str | Callable[[WorkflowMessage, Any], str] | None = None,
        output_parser: Optional[Callable[[str, Any], WorkflowMessage]] = None,
    ):
        super().__init__(node_id=node_id)
        self.llm_client = llm_client
        self.prompt = prompt
        self.output_parser = output_parser

    def run(self, message: WorkflowMessage, context: Any) -> Optional[WorkflowMessage]:
        in_meta = dict(getattr(message, "metadata", {}) or {})
        if self.prompt is None and not isinstance(message, TextMessage):
            raise TypeError(f"LlmNode({self.node_id}) expects TextMessage when prompt is not set, got {type(message).__name__}")

        if callable(self.prompt):
            prompt_text = self.prompt(message, context)
        elif isinstance(self.prompt, str):
            prompt_text = self.prompt
        else:
            prompt_text = message.text

        kwargs = {}
        file_paths = message.metadata.get("file_paths")
        if file_paths is not None:
            kwargs["file_paths"] = file_paths

        try:
            llm_text = self.llm_client.response(prompt=prompt_text, **kwargs)
        except TypeError:
            llm_text = self.llm_client.response(prompt_text)

        if self.output_parser is not None:
            out = self.output_parser(llm_text, context)
        else:
            out = TextMessage(text=llm_text, metadata={"node_id": self.node_id})

        return out


class ToolNode(BaseNode):
    def __init__(self, node_id: str, *, tool: Optional[BaseTool] = None, tool_name: Optional[str] = None):
        super().__init__(node_id=node_id)
        self.tool = tool
        self.fixed_tool_name = tool_name

    def run(self, message: WorkflowMessage, context: Any) -> Optional[WorkflowMessage]:
        if not isinstance(message, ToolCallMessage):
            raise TypeError(f"ToolNode({self.node_id}) expects ToolCallMessage, got {type(message).__name__}")

        tool_name = self.fixed_tool_name or message.tool_name
        tool = self.tool
        if tool is None:
            raise RuntimeError(f"ToolNode({self.node_id}) requires tool instance")

        try:
            result = tool.run(**message.arguments)
        except Exception as e:
            result = ToolResult(success=False, output="", error=str(e), metadata={})

        return ToolResultMessage(
            tool_name=tool_name,
            result=result,
            metadata={**dict(message.metadata), "node_id": self.node_id},
        )

