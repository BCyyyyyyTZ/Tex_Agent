from __future__ import annotations

from core.message import ToolResult
from tools.base_tool import BaseTool
import sys
import types


class FakeLlmClient:
    def response(self, prompt: str) -> str:
        return f"LLM({prompt})"


class EchoTool(BaseTool):
    def __init__(self):
        super().__init__(name="echo", description="echo", input_schema={"text": "str"})

    def run(self, text: str) -> ToolResult:
        return ToolResult(success=True, output=text, error="", metadata={})


def _install_minimal_tool_list() -> None:
    """
    workflow_engine.nodes.ToolNode 依赖 tools.tool_list（dict: name -> tool instance）。
    为避免测试导入阶段被工具注册表里的可选依赖阻断，这里为测试提供最小注册表。
    """
    m = types.ModuleType("tools.tool_list")
    m.tool_list = {"echo": EchoTool()}
    sys.modules["tools.tool_list"] = m


def test_llm_node_linear_workflow():
    _install_minimal_tool_list()
    from workflow_engine.messages import TextMessage
    from workflow_engine.nodes import LlmNode
    from workflow_engine.workflow import Workflow

    wf = Workflow()
    wf.add_node(LlmNode("llm1", FakeLlmClient()))
    out = wf.run(TextMessage(text="hi"), start_nodes=["llm1"])
    assert isinstance(out, TextMessage)
    assert out.text == "LLM(hi)"


def test_tool_node_linear_workflow():
    _install_minimal_tool_list()
    from workflow_engine.messages import ToolCallMessage, ToolResultMessage
    from workflow_engine.nodes import ToolNode
    from workflow_engine.workflow import Workflow, WorkflowContext

    wf = Workflow()
    wf.add_node(ToolNode("tool1", tool_names=["echo"]))
    ctx = WorkflowContext(metadata={"tool_default_args": {}})
    out = wf.run(ToolCallMessage(tool_name="echo", arguments={"text": "ok"}), start_nodes=["tool1"], context=ctx)
    assert isinstance(out, ToolResultMessage)
    assert "echo" in out.tool_names
    assert len(out.results) == 1
    assert out.results[0].success is True
    assert out.results[0].output == "ok"


def test_llm_to_tool_workflow_with_parser():
    _install_minimal_tool_list()
    from workflow_engine.messages import TextMessage, ToolCallMessage, ToolResultMessage
    from workflow_engine.nodes import LlmNode, ToolNode
    from workflow_engine.workflow import Workflow, WorkflowContext

    def parse_to_tool_call(llm_text: str, _ctx) -> ToolCallMessage:
        return ToolCallMessage(tool_name="echo", arguments={"text": llm_text})

    wf = Workflow()
    wf.add_node(LlmNode("llm1", FakeLlmClient(), output_parser=parse_to_tool_call))
    wf.add_node(ToolNode("tool1", tool_names=["echo"]))
    wf.add_edge("llm1", "tool1")

    ctx = WorkflowContext(metadata={"tool_default_args": {}})
    out = wf.run(TextMessage(text="x"), start_nodes=["llm1"], context=ctx)
    assert isinstance(out, ToolResultMessage)
    assert out.results[0].output == "LLM(x)"

