"""
ContextManager 单元测试。
验证上下文管理器的基础存储、检索、清空、窗口提取等功能的正确性。
"""
import pytest

from memory.context_manager import ContextManager
from core.message import AgentMessage
from core.exceptions import MemoryError as TexMemoryError


def _make_msg(
    content: str,
    role: str = "user",
    agent_name: str = "user",
) -> AgentMessage:
    """辅助函数：快速创建 AgentMessage 对象。"""
    return AgentMessage(role=role, content=content, agent_name=agent_name)


class TestContextManager:
    """ContextManager 功能测试套件。"""

    def setup_method(self):
        """每个测试方法前，创建新的 ContextManager 实例。"""
        self.ctx = ContextManager(max_messages=10)

    def test_save_and_load_single_message(self):
        """验证 save() 后 load() 能正确返回该消息。"""
        msg = _make_msg("你好，请帮我检索论文")
        self.ctx.save(msg)

        history = self.ctx.load()
        assert len(history) == 1
        assert history[0].content == "你好，请帮我检索论文"
        assert history[0].role == "user"

    def test_load_returns_messages_in_order(self):
        """验证 load() 按时间正序（最旧在前）返回消息。"""
        for i in range(5):
            self.ctx.save(_make_msg(f"消息{i}"))

        history = self.ctx.load()
        assert len(history) == 5
        for i, msg in enumerate(history):
            assert msg.content == f"消息{i}"

    def test_load_with_limit_returns_most_recent(self):
        """验证 load(limit=N) 返回最近的 N 条消息（正序）。"""
        for i in range(5):
            self.ctx.save(_make_msg(f"消息{i}"))

        recent = self.ctx.load(limit=3)
        assert len(recent) == 3
        assert recent[0].content == "消息2"  # 第 3 条
        assert recent[1].content == "消息3"
        assert recent[2].content == "消息4"  # 最新

    def test_clear_removes_all_messages(self):
        """验证 clear() 清空所有消息，len() 归零。"""
        for i in range(3):
            self.ctx.save(_make_msg(f"消息{i}"))

        self.ctx.clear()
        assert len(self.ctx.load()) == 0
        assert len(self.ctx) == 0

    def test_max_messages_evicts_oldest(self):
        """验证超出 max_messages 时，自动移除最旧的消息（FIFO）。"""
        ctx = ContextManager(max_messages=3)
        for i in range(5):
            ctx.save(_make_msg(f"消息{i}"))

        history = ctx.load()
        assert len(history) == 3
        # 消息 0 和 1 应被淘汰
        assert history[0].content == "消息2"
        assert history[1].content == "消息3"
        assert history[2].content == "消息4"

    def test_len_tracks_message_count(self):
        """验证 __len__() 随消息增删正确变化。"""
        assert len(self.ctx) == 0

        self.ctx.save(_make_msg("消息1"))
        assert len(self.ctx) == 1

        self.ctx.save(_make_msg("消息2"))
        assert len(self.ctx) == 2

        self.ctx.clear()
        assert len(self.ctx) == 0

    def test_save_invalid_type_raises_memory_error(self):
        """验证传入非 AgentMessage 对象时抛出 TexMemoryError。"""
        with pytest.raises(TexMemoryError):
            self.ctx.save("这是一个字符串，不是 AgentMessage")

        with pytest.raises(TexMemoryError):
            self.ctx.save({"role": "user", "content": "字典不行"})

    def test_get_context_window_returns_last_n(self):
        """验证 get_context_window() 返回最近 N 条消息。"""
        for i in range(30):
            self.ctx.save(_make_msg(f"消息{i}"))  # max_messages=10，只保留最后10条

        window = self.ctx.get_context_window(max_messages=5)
        assert len(window) == 5

    def test_get_messages_by_agent_filters_correctly(self):
        """验证 get_messages_by_agent() 按名称精确筛选。"""
        self.ctx.save(_make_msg("用户消息1", agent_name="user"))
        self.ctx.save(_make_msg("Agent响应", role="assistant", agent_name="DesignAgent"))
        self.ctx.save(_make_msg("用户消息2", agent_name="user"))
        self.ctx.save(_make_msg("另一Agent响应", role="assistant", agent_name="ThinkAgent"))

        user_msgs = self.ctx.get_messages_by_agent("user")
        design_msgs = self.ctx.get_messages_by_agent("DesignAgent")
        think_msgs = self.ctx.get_messages_by_agent("ThinkAgent")
        nonexistent = self.ctx.get_messages_by_agent("NonExistentAgent")

        assert len(user_msgs) == 2
        assert len(design_msgs) == 1
        assert len(think_msgs) == 1
        assert len(nonexistent) == 0

    def test_load_limit_none_returns_all(self):
        """验证 load(limit=None) 返回全部消息。"""
        for i in range(7):
            self.ctx.save(_make_msg(f"消息{i}"))

        all_msgs = self.ctx.load(limit=None)
        assert len(all_msgs) == 7

    def test_load_limit_larger_than_count_returns_all(self):
        """验证 limit 大于实际消息数时返回全部消息，不报错。"""
        for i in range(3):
            self.ctx.save(_make_msg(f"消息{i}"))

        result = self.ctx.load(limit=100)
        assert len(result) == 3
