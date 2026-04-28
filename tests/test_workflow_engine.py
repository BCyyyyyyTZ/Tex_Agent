from __future__ import annotations

from core.message import ToolResult
from tools.base_tool import BaseTool
from workflow_engine.messages import TextMessage, ToolCallMessage, ToolResultMessage
from workflow_engine.nodes import LlmNode, ToolNode
from workflow_engine.workflow import Workflow


class FakeLlmClient:
    def response(self, prompt: str) -> str:
        return f"LLM({prompt})"


class EchoTool(BaseTool):
    def __init__(self):
        super().__init__(name="echo", description="echo", input_schema={"text": "str"})

    def run(self, text: str) -> ToolResult:
        return ToolResult(success=True, output=text, error=None, metadata={})


def test_llm_node_linear_workflow():
    wf = Workflow()
    wf.add_node(LlmNode("llm1", FakeLlmClient()))
    out = wf.run(TextMessage(text="hi"), start_nodes=["llm1"])
    assert isinstance(out, TextMessage)
    assert out.text == "LLM(hi)"


def test_tool_node_linear_workflow():
    wf = Workflow()
    wf.add_node(ToolNode("tool1", tool=EchoTool()))
    out = wf.run(ToolCallMessage(tool_name="echo", arguments={"text": "ok"}), start_nodes=["tool1"])
    assert isinstance(out, ToolResultMessage)
    assert out.success is True
    assert out.output == "ok"


def test_llm_to_tool_workflow_with_parser():
    def parse_to_tool_call(llm_text: str, _ctx) -> ToolCallMessage:
        return ToolCallMessage(tool_name="echo", arguments={"text": llm_text})

    wf = Workflow()
    wf.add_node(LlmNode("llm1", FakeLlmClient(), output_parser=parse_to_tool_call))
    wf.add_node(ToolNode("tool1", tool=EchoTool()))
    wf.add_edge("llm1", "tool1")

    out = wf.run(TextMessage(text="x"), start_nodes=["llm1"])
    assert isinstance(out, ToolResultMessage)
    assert out.output == "LLM(x)"

