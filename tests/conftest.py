"""
pytest 公共 fixtures。
提供 Mock Agent、Mock Tool、初始化 WorkflowState 等通用测试夹具，
供所有子测试模块复用，避免重复代码。
"""
import pytest
from unittest.mock import MagicMock

from core.message import AgentMessage, ToolResult
from core.state import WorkflowState
from context.context_manager import ContextManager


@pytest.fixture
def sample_user_message() -> AgentMessage:
    """创建标准用户消息（用于 Agent / 工具测试）。"""
    return AgentMessage(
        role="user",
        content="请帮我检索关于 transformer 的最新论文",
        agent_name="user",
    )


@pytest.fixture
def sample_assistant_message() -> AgentMessage:
    """创建标准 Agent 响应消息（用于工作流测试）。"""
    return AgentMessage(
        role="assistant",
        content="好的，我将为您检索 transformer 相关论文，并提供写作建议...",
        agent_name="MockAgent",
    )


@pytest.fixture
def initial_state() -> WorkflowState:
    """创建标准初始工作流状态（用于工作流集成测试）。"""
    return {
        "messages": [],
        "current_node": "",
        "input": "帮我检索 transformer 相关论文并给出写作建议",
        "output": "",
        "error": None,
        "metadata": {},
        "retrieved_context": "",  # RAG 检索结果，未启用 RAG 时始终为 ""
    }


@pytest.fixture
def mock_agent(sample_assistant_message: AgentMessage) -> MagicMock:
    """
    创建 Mock BaseAgent。

    run() 返回预定义的 assistant 消息。
    用于隔离工作流测试，无需真实 LLM 调用。
    """
    agent = MagicMock()
    agent.name = "MockAgent"
    agent.run.return_value = sample_assistant_message
    return agent


@pytest.fixture
def mock_tool() -> MagicMock:
    """
    创建 Mock BaseTool。

    run() 返回成功的 ToolResult。
    用于隔离 Agent 测试，无需真实工具执行。
    """
    tool = MagicMock()
    tool.name = "mock_tool"
    tool.description = "A mock tool for testing"
    tool.run.return_value = ToolResult(
        success=True,
        output="Mock tool output: found 3 results",
        metadata={"source": "mock", "count": 3},
    )
    return tool


@pytest.fixture
def context_manager() -> ContextManager:
    """创建空的 ContextManager 实例（max_messages=100）。"""
    return ContextManager(max_messages=100)
