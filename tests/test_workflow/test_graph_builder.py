"""
工作流图构建与执行集成测试。
使用 Mock Agent 完全隔离 LLM 调用，验证图的完整执行链路与状态更新正确性。
"""
import pytest
from unittest.mock import MagicMock, patch

from workflow.graph_builder import build_graph
from core.message import AgentMessage
from context.context_manager import ContextManager


def _make_mock_agent(name: str, response_content: str) -> MagicMock:
    """
    创建指定名称和响应内容的 Mock Agent 实例。

    Args:
        name: Mock Agent 的名称。
        response_content: run() 方法返回的响应内容。
    """
    agent = MagicMock()
    agent.name = name
    agent.run.return_value = AgentMessage(
        role="assistant",
        content=response_content,
        agent_name=name,
    )
    return agent


class TestGraphBuilder:
    """工作流图构建与执行测试套件。"""

    def test_build_graph_returns_compiled_app(self):
        """验证 build_graph() 返回可调用的编译图对象。"""
        ctx = ContextManager()
        app = build_graph(context_manager=ctx)
        assert app is not None
        assert hasattr(app, "invoke")

    def test_workflow_executes_in_correct_order(self):
        """
        验证工作流按 Design → Think → Execute 顺序执行，
        最终 current_node 为 "execute"。
        """
        ctx = ContextManager()
        design_mock = _make_mock_agent("DesignAgent", "设计方案：分析任务结构...")
        think_mock = _make_mock_agent("ThinkAgent", "深度思考：关键技术点是...")
        execute_mock = _make_mock_agent("ExecuteAgent", "最终执行结果：完整答案...")

        with patch("workflow.graph_builder.SimpleAgent") as MockSimpleAgent:
            MockSimpleAgent.side_effect = [design_mock, think_mock, execute_mock]
            app = build_graph(context_manager=ctx)
            result = app.invoke({
                "messages": [],
                "current_node": "",
                "input": "帮我检索 transformer 论文",
                "output": "",
                "error": None,
                "metadata": {},
                "retrieved_context": "",
            })

        assert result is not None
        assert result["current_node"] == "execute"

    def test_workflow_sets_output_to_execute_response(self):
        """验证工作流执行完成后，output 字段被正确设置为 Execute 节点的响应内容。"""
        ctx = ContextManager()
        expected_output = "这是最终的执行结果，包含完整的论文写作建议。"

        design_mock = _make_mock_agent("DesignAgent", "设计内容")
        think_mock = _make_mock_agent("ThinkAgent", "思考内容")
        execute_mock = _make_mock_agent("ExecuteAgent", expected_output)

        with patch("workflow.graph_builder.SimpleAgent") as MockSimpleAgent:
            MockSimpleAgent.side_effect = [design_mock, think_mock, execute_mock]
            app = build_graph(context_manager=ctx)
            result = app.invoke({
                "messages": [],
                "current_node": "",
                "input": "测试任务",
                "output": "",
                "error": None,
                "metadata": {},
                "retrieved_context": "",
            })

        assert result["output"] == expected_output

    def test_workflow_accumulates_six_messages(self):
        """
        验证工作流执行完成后消息列表正确累积。
        每个节点产生 2 条消息（user + assistant），3 个节点共 6 条。
        """
        ctx = ContextManager()
        design_mock = _make_mock_agent("DesignAgent", "设计内容")
        think_mock = _make_mock_agent("ThinkAgent", "思考内容")
        execute_mock = _make_mock_agent("ExecuteAgent", "执行内容")

        with patch("workflow.graph_builder.SimpleAgent") as MockSimpleAgent:
            MockSimpleAgent.side_effect = [design_mock, think_mock, execute_mock]
            app = build_graph(context_manager=ctx)
            result = app.invoke({
                "messages": [],
                "current_node": "",
                "input": "测试任务",
                "output": "",
                "error": None,
                "metadata": {},
                "retrieved_context": "",
            })

        assert len(result["messages"]) == 6

    def test_workflow_messages_contain_correct_roles(self):
        """验证工作流完成后消息列表中 role 字段分布正确（user/assistant 交替）。"""
        ctx = ContextManager()
        design_mock = _make_mock_agent("DesignAgent", "设计内容")
        think_mock = _make_mock_agent("ThinkAgent", "思考内容")
        execute_mock = _make_mock_agent("ExecuteAgent", "执行内容")

        with patch("workflow.graph_builder.SimpleAgent") as MockSimpleAgent:
            MockSimpleAgent.side_effect = [design_mock, think_mock, execute_mock]
            app = build_graph(context_manager=ctx)
            result = app.invoke({
                "messages": [],
                "current_node": "",
                "input": "测试任务",
                "output": "",
                "error": None,
                "metadata": {},
                "retrieved_context": "",
            })

        roles = [msg["role"] for msg in result["messages"]]
        # 期望格式：[user, assistant, user, assistant, user, assistant]
        assert roles == ["user", "assistant", "user", "assistant", "user", "assistant"]

    def test_workflow_no_error_on_success(self):
        """验证工作流正常执行完成后 error 字段为 None。"""
        ctx = ContextManager()
        design_mock = _make_mock_agent("DesignAgent", "设计内容")
        think_mock = _make_mock_agent("ThinkAgent", "思考内容")
        execute_mock = _make_mock_agent("ExecuteAgent", "执行内容")

        with patch("workflow.graph_builder.SimpleAgent") as MockSimpleAgent:
            MockSimpleAgent.side_effect = [design_mock, think_mock, execute_mock]
            app = build_graph(context_manager=ctx)
            result = app.invoke({
                "messages": [],
                "current_node": "",
                "input": "测试任务",
                "output": "",
                "error": None,
                "metadata": {},
                "retrieved_context": "",
            })

        assert result["error"] is None

    def test_context_manager_receives_all_messages(self):
        """验证工作流执行后 ContextManager 记录了所有节点产生的消息。"""
        ctx = ContextManager()
        design_mock = _make_mock_agent("DesignAgent", "设计内容")
        think_mock = _make_mock_agent("ThinkAgent", "思考内容")
        execute_mock = _make_mock_agent("ExecuteAgent", "执行内容")

        with patch("workflow.graph_builder.SimpleAgent") as MockSimpleAgent:
            MockSimpleAgent.side_effect = [design_mock, think_mock, execute_mock]
            app = build_graph(context_manager=ctx)
            app.invoke({
                "messages": [],
                "current_node": "",
                "input": "测试任务",
                "output": "",
                "error": None,
                "metadata": {},
                "retrieved_context": "",
            })

        # ContextManager 中也应记录 6 条消息
        assert len(ctx) == 6
