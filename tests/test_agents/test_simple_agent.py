"""
SimpleAgent 单元测试。
使用 Mock 隔离 LLM 调用，验证 Agent 基础行为的正确性。
"""
import pytest
from unittest.mock import MagicMock, patch

from agents.simple_agent import SimpleAgent
from core.message import AgentMessage
from core.exceptions import AgentError


class TestSimpleAgent:
    """SimpleAgent 基础行为测试套件。"""

    def setup_method(self):
        """每个测试方法执行前，创建一个 SimpleAgent 实例。"""
        self.agent = SimpleAgent(
            name="TestAgent",
            system_prompt="你是一个有用的学术写作助手。",
        )

    def test_agent_name_property(self):
        """验证 name 属性返回正确的 Agent 名称。"""
        assert self.agent.name == "TestAgent"

    def test_run_returns_agent_message(self):
        """验证 run() 返回正确类型和内容的 AgentMessage。"""
        mock_lc_response = MagicMock()
        mock_lc_response.content = "这是来自 LLM 的测试响应内容。"

        mock_llm = MagicMock()
        mock_llm.invoke.return_value = mock_lc_response

        with patch.object(self.agent, "_get_llm", return_value=mock_llm):
            msg = AgentMessage(role="user", content="你好", agent_name="user")
            result = self.agent.run(msg)

        assert isinstance(result, AgentMessage)
        assert result.role == "assistant"
        assert result.content == "这是来自 LLM 的测试响应内容。"
        assert result.agent_name == "TestAgent"

    def test_run_updates_history(self):
        """验证 run() 正确将用户消息和 Agent 响应追加到对话历史。"""
        mock_lc_response = MagicMock()
        mock_lc_response.content = "助手响应内容"

        mock_llm = MagicMock()
        mock_llm.invoke.return_value = mock_lc_response

        with patch.object(self.agent, "_get_llm", return_value=mock_llm):
            msg = AgentMessage(role="user", content="用户问题", agent_name="user")
            self.agent.run(msg)

        history = self.agent.get_history()
        assert len(history) == 2
        assert history[0].role == "user"
        assert history[0].content == "用户问题"
        assert history[1].role == "assistant"
        assert history[1].content == "助手响应内容"

    def test_run_multiple_times_accumulates_history(self):
        """验证多次 run() 调用后历史记录正确累积。"""
        mock_lc_response = MagicMock()
        mock_lc_response.content = "响应"

        mock_llm = MagicMock()
        mock_llm.invoke.return_value = mock_lc_response

        with patch.object(self.agent, "_get_llm", return_value=mock_llm):
            for i in range(3):
                msg = AgentMessage(role="user", content=f"问题{i}", agent_name="user")
                self.agent.run(msg)

        # 3 次调用，每次产生 2 条记录（用户 + 助手）
        assert len(self.agent.get_history()) == 6

    def test_reset_clears_history(self):
        """验证 reset() 完全清空对话历史。"""
        # 预设一些历史
        self.agent._history = [
            AgentMessage(role="user", content="旧消息", agent_name="user")
        ]
        self.agent.reset()
        assert self.agent.get_history() == []

    def test_run_raises_agent_error_on_llm_failure(self):
        """验证 LLM 调用异常时 run() 正确抛出 AgentError。"""
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = Exception("Network connection failed")

        with patch.object(self.agent, "_get_llm", return_value=mock_llm):
            msg = AgentMessage(role="user", content="问题", agent_name="user")
            with pytest.raises(AgentError) as exc_info:
                self.agent.run(msg)
        assert "TestAgent" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_ainvoke_returns_agent_message(self):
        """验证 ainvoke() 异步调用正确返回 AgentMessage。"""
        mock_lc_response = MagicMock()
        mock_lc_response.content = "异步响应内容"

        mock_llm = MagicMock()
        mock_llm.invoke.return_value = mock_lc_response

        with patch.object(self.agent, "_get_llm", return_value=mock_llm):
            msg = AgentMessage(role="user", content="异步问题", agent_name="user")
            result = await self.agent.ainvoke(msg)

        assert isinstance(result, AgentMessage)
        assert result.role == "assistant"
        assert result.content == "异步响应内容"

    def test_get_history_returns_copy(self):
        """验证 get_history() 返回的是列表副本，不影响内部状态。"""
        mock_lc_response = MagicMock()
        mock_lc_response.content = "响应"
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = mock_lc_response

        with patch.object(self.agent, "_get_llm", return_value=mock_llm):
            msg = AgentMessage(role="user", content="问题", agent_name="user")
            self.agent.run(msg)

        history = self.agent.get_history()
        history.clear()  # 修改返回的副本
        # 内部历史不应受影响
        assert len(self.agent.get_history()) == 2
