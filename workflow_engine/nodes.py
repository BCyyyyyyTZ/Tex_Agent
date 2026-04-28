from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any, Callable, Optional, Protocol, TYPE_CHECKING

from core.message import ToolResult
from tools.base_tool import BaseTool
from workflow_engine.messages import TextMessage, ToolCallMessage, ToolResultMessage, MergedMessage, WorkflowMessage
from tools.tool_list import tool_list
if TYPE_CHECKING:
    from workflow_engine.workflow import WorkflowContext

from workflow_engine.config import MODE

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
        print(f"Run FunctionNode({self.node_id})")
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

    def run(self, message: Optional[WorkflowMessage], context: "WorkflowContext") -> Optional[WorkflowMessage]:
        
        print(f"Run LlmNode({self.node_id})")
        if self.prompt is None and not isinstance(message, (TextMessage, MergedMessage)):
            raise TypeError(f"LlmNode({self.node_id}) expects TextMessage when prompt is not set, got {type(message).__name__}")
        if callable(self.prompt):
            prompt_text = self.prompt(message, context)
        elif isinstance(self.prompt, str):
            prompt_text = self.prompt
        else:
            if not message or not message.text:
                raise ValueError(f"LlmNode({self.node_id}) got empty prompt text")
            prompt_text = message.text
        kwargs = {}
        file_paths = []
        if message:
            file_paths_from_msg = message.metadata.get("file_to_upload", [])
            file_paths.extend(file_paths_from_msg)
        file_paths_from_ctx = context.metadata.get("file_to_upload", [])
        file_paths.extend(file_paths_from_ctx)
        if file_paths:
            kwargs["file_paths"] = file_paths
        try:
            if MODE == "debug":
                print(f"prompt_text: {prompt_text}\n\n")
                print(f"kwargs: {kwargs}\n\n")
            llm_text = self.llm_client.response(prompt=prompt_text, **kwargs)
        except TypeError:
            llm_text = self.llm_client.response(prompt_text)

        if self.output_parser is not None:
            out = self.output_parser(llm_text, context)
        else:
            raw = llm_text.strip()
            if MODE == "debug":
                print(f"llm_response: {raw}\n\n")

            if raw.startswith("TOOL_CALL"):
                parts = raw.split(maxsplit=2)
                if len(parts) < 3:
                    raise ValueError("TOOL_CALL 格式错误")

                tool_name = parts[1].strip()
                arg_dict_str = parts[2].strip()

                if tool_name == "none":
                    return None

                try:
                    arg_dict = json.loads(arg_dict_str)
                except json.JSONDecodeError as e:
                    raise ValueError(f"TOOL_CALL 参数不是合法 JSON：{e}") from e

                out = ToolCallMessage(
                    tool_name=tool_name,
                    arguments=arg_dict,
                    metadata={"node_id": self.node_id},
                )
            else:
                out = TextMessage(text=llm_text, metadata={"node_id": self.node_id})

        return out


class ToolNode(BaseNode):
    def __init__(self, node_id: str, *, tool_names: Optional[list[str]] = None):
        super().__init__(node_id=node_id)
        if tool_names is None:
            self.tools = tool_list
        else:
            self.tools = {}
            for tool in tool_names:
                self.tools[tool] = tool_list[tool]
        self.tool_names = self.tools.keys()

    def run(self, message: WorkflowMessage, context: "WorkflowContext") -> Optional[WorkflowMessage]:
        print(f"Run ToolNode({self.node_id})")
        if not message.tool_calls:
            return None

        tool_calls = [c for c in message.tool_calls if c["tool_name"] in self.tool_names]
        
        tool_results = []
        tool_names = set()

        for tool_call in tool_calls:
            tool_name = tool_call["tool_name"]
            args = tool_call["arguments"]
            if context.metadata["tool_default_args"].get(tool_name, None):
                args.update(context.metadata["tool_default_args"][tool_name])
            tool = self.tools.get(tool_name, None)
            if tool is None:
                raise RuntimeError(f"ToolNode({self.node_id}) requires tool instance")

            try:
                if MODE == "debug":
                    print(f"tool_call: {tool_name}\n\n")
                    print(f"args: {args}\n\n")
                result = tool.run(**args)
                tool_results.append(result)
                tool_names.add(tool_name)
            except Exception as e:
                result = ToolResult(success=False, output="", error=str(e), metadata={})

        return ToolResultMessage(
            tool_names=tool_names,
            results=tool_results,
            metadata={"node_id": self.node_id},
        )

