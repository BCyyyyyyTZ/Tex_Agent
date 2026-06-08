from __future__ import annotations

"""
工作流节点（Nodes）。

该模块定义工作流执行单元的统一接口（BaseNode），并提供三类常用节点：
- FunctionNode: 用普通 Python 函数封装节点逻辑
- LlmNode: 调用 LLM，将输入消息转换为文本/工具调用消息
- ToolNode: 执行工具调用，将 ToolCallMessage 转换为 ToolResultMessage

节点之间通过 workflow_engine.messages 中的结构化消息进行通信。
"""

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
    """
    LLM 客户端的最小能力约束。

    只要求实现 response(prompt, ...) -> str，以便 LlmNode 可以在不同 LLM 实现间切换。
    """
    def response(self, prompt: str, *args: Any, **kwargs: Any) -> str:
        """根据 prompt 生成模型回复文本（可选携带文件、工具参数等扩展能力）。"""
        ...


class BaseNode(ABC):
    """
    工作流节点抽象基类。

    约定：
    - node_id: 节点唯一标识（用于连接边、记录上下文输出）
    - run: 输入 WorkflowMessage（可能为 None 或合并消息），输出 WorkflowMessage 或 None
    """
    def __init__(self, node_id: str):
        """
        Args:
            node_id: 节点 id（在同一个 Workflow 内必须唯一）
        """
        self.node_id = node_id

    @abstractmethod
    def run(self, message: WorkflowMessage, context: Any) -> Optional[WorkflowMessage]:
        """
        执行节点逻辑。

        Args:
            message: 上游传入的结构化消息（可能是文本、工具调用、工具结果或合并消息）
            context: WorkflowContext（或兼容对象），用于跨节点共享状态与默认参数
        """
        raise NotImplementedError


class FunctionNode(BaseNode):
    """
    以函数形式实现节点逻辑的适配器。

    适用场景：
    - 快速把一段纯 Python 处理逻辑插入工作流
    - 对 message 做轻量转换或路由标记
    """
    def __init__(self, node_id: str, fn: Callable[[WorkflowMessage, Any], WorkflowMessage]):
        """
        Args:
            node_id: 节点 id
            fn: 处理函数，签名为 (message, context) -> WorkflowMessage
        """
        super().__init__(node_id=node_id)
        self.fn = fn

    def run(self, message: WorkflowMessage, context: Any) -> Optional[WorkflowMessage]:
        """
        调用封装的处理函数并返回其输出。
        """
        print(f"Run FunctionNode({self.node_id})")
        return self.fn(message, context)


class LlmNode(BaseNode):
    """
    LLM 节点。

    行为：
    - 从 message 或 prompt 构造最终 prompt_text
    - 可从 message/context.metadata 中收集 file_to_upload，传给 LLM 客户端
    - 默认输出解析规则：
        * 以 "TOOL_CALL <tool_name> <json_args>" 开头 -> ToolCallMessage
        * 否则 -> TextMessage

    output_parser 可用于替换默认解析逻辑，直接把 LLM 文本解析为任意 WorkflowMessage。
    """
    def __init__(
        self,
        node_id: str,
        llm_client: LlmClientLike,
        *,
        prompt: str | Callable[[WorkflowMessage, Any], str] | None = None,
        output_parser: Optional[Callable[[str, Any], WorkflowMessage]] = None,
    ):
        """
        Args:
            node_id: 节点 id
            llm_client: LLM 客户端（实现 LlmClientLike）
            prompt: 固定字符串 prompt 或动态 prompt 函数；为 None 时使用 message.text
            output_parser: 可选自定义解析器，把 LLM 输出文本解析为 WorkflowMessage
        """
        super().__init__(node_id=node_id)
        self.llm_client = llm_client
        self.prompt = prompt
        self.output_parser = output_parser

    def run(self, message: Optional[WorkflowMessage], context: "WorkflowContext") -> Optional[WorkflowMessage]:
        """
        调用 LLM 并将其输出转换为结构化消息。

        约定的 TOOL_CALL 格式用于让 LLM 触发 ToolNode：
            TOOL_CALL <tool_name> <json_dict>
        tool_name 为 "none" 时视为不调用工具并返回 None。
        """
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
    """
    工具调用节点。

    输入：ToolCallMessage / MergedMessage（包含 tool_calls 列表）
    输出：ToolResultMessage（聚合本轮执行的工具结果）

    tool_names 可用于限制可调用的工具子集；不传则默认使用全量 tool_list。
    """
    def __init__(self, node_id: str, *, tool_names: Optional[list[str]] = None):
        """
        Args:
            node_id: 节点 id
            tool_names: 允许调用的工具名白名单；为 None 时允许调用全部已注册工具
        """
        super().__init__(node_id=node_id)
        if tool_names is None:
            self.tools = tool_list
        else:
            self.tools = {}
            for tool in tool_names:
                self.tools[tool] = tool_list[tool]
        self.tool_names = self.tools.keys()

    def run(self, message: WorkflowMessage, context: "WorkflowContext") -> Optional[WorkflowMessage]:
        """
        执行消息中包含的工具调用，并返回聚合后的工具结果消息。

        context.metadata["tool_default_args"] 可提供工具默认参数（按工具名索引），会与消息内 args 合并。
        """
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

