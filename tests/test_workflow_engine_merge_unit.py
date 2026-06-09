"""
workflow_engine.workflow 的单元测试（聚焦消息合并与调度边界）。

现有 tests/test_workflow_engine.py 已覆盖最小线性执行链；
本文件补充：
1) _merge_message 的合并规则（文本/工具调用/工具结果/metadata）；
2) Workflow 的拓扑排序与异常分支（例如重复 node_id、缺失 start node）。

注意：
- 本文件不修改任何生产代码；
- 若发现已知缺陷，可使用 xfail 标注为“已知问题”，以免阻断测试收集与运行。
"""

from __future__ import annotations

import sys
import types
import pytest

from core.message import ToolResult
from tools.base_tool import BaseTool


class _EchoTool(BaseTool):
    def __init__(self) -> None:
        super().__init__(name="echo", description="echo", input_schema={"text": "str"})

    def run(self, text: str) -> ToolResult:
        return ToolResult(success=True, output=text, error="", metadata={})

def _install_minimal_tool_list() -> None:
    m = types.ModuleType("tools.tool_list")
    m.tool_list = {"echo": _EchoTool()}
    sys.modules["tools.tool_list"] = m


def test_merge_message_merges_texts_and_tool_calls_and_results() -> None:
    from workflow_engine.messages import TextMessage, ToolCallMessage, ToolResultMessage
    from workflow_engine.workflow import _merge_message

    """
    合并规则：
    - TextMessage.text 以空行拼接；
    - ToolCallMessage 收集为 tool_calls 列表；
    - ToolResultMessage 的 tool_names/results 合并到 tool_results；
    - metadata 做浅合并（后者覆盖同名键）。
    """
    m = _merge_message(
        [
            TextMessage(text="A", metadata={"k": 1}),
            TextMessage(text="B", metadata={"k": 2}),
            ToolCallMessage(tool_name="t", arguments={"x": 1}),
            ToolResultMessage(tool_names={"t"}, results=[ToolResult(success=True, output="ok", error="", metadata={})]),
        ]
    )
    assert m is not None
    assert m.text == "A\n\nB"
    assert m.tool_calls == [{"tool_name": "t", "arguments": {"x": 1}}]
    assert "t" in m.tool_results["tool_names"]
    assert len(m.tool_results["results"]) == 1
    assert m.metadata["k"] == 2


def test_workflow_rejects_duplicate_node_id() -> None:
    _install_minimal_tool_list()
    from workflow_engine.nodes import ToolNode
    from workflow_engine.workflow import Workflow

    wf = Workflow()
    wf.add_node(ToolNode("n1", tool_names=["echo"]))
    with pytest.raises(KeyError, match="duplicate"):
        wf.add_node(ToolNode("n1", tool_names=["echo"]))


def test_workflow_infer_start_nodes_requires_at_least_one_start() -> None:
    """
    若图中每个节点都有 incoming 边，则无法推断 start_nodes，应报错。
    """
    _install_minimal_tool_list()
    from workflow_engine.nodes import ToolNode
    from workflow_engine.workflow import Workflow

    wf = Workflow()
    wf.add_node(ToolNode("a", tool_names=["echo"]))
    wf.add_node(ToolNode("b", tool_names=["echo"]))
    wf.add_edge("a", "b")
    wf.add_edge("b", "a")
    with pytest.raises(ValueError, match="no start node found"):
        from workflow_engine.messages import ToolCallMessage
        wf.run(ToolCallMessage(tool_name="echo", arguments={"text": "x"}))


def test_workflow_run_rejects_unknown_start_node() -> None:
    _install_minimal_tool_list()
    from workflow_engine.nodes import ToolNode
    from workflow_engine.workflow import Workflow

    wf = Workflow()
    wf.add_node(ToolNode("a", tool_names=["echo"]))
    with pytest.raises(KeyError, match="start node not found"):
        from workflow_engine.messages import ToolCallMessage
        wf.run(ToolCallMessage(tool_name="echo", arguments={"text": "x"}), start_nodes=["missing"])
