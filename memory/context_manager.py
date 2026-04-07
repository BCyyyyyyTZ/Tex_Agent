"""
ContextManager：基础上下文管理器（可运行）。
在单次运行周期内，以有界双端队列（deque）的形式维护所有 AgentMessage 记录。
程序重启后记忆清空（非持久化），适合 MVP 阶段使用。
"""
from collections import deque
from typing import List, Optional

from memory.base_memory import BaseMemory
from core.message import AgentMessage
from core.exceptions import MemoryError as TexMemoryError
from utils.logger import get_logger

logger = get_logger(__name__)


class ContextManager(BaseMemory):
    """
    内存上下文管理器（单次运行周期内有效）。

    使用 collections.deque 存储所有 AgentMessage，支持：
    - 消息追加与按数量检索（O(1) FIFO 淘汰）
    - 按 Agent 名称过滤
    - 可配置的最大消息数（超出时自动淘汰最旧消息）
    - 上下文窗口提取（用于 LLM 调用）

    Args:
        max_messages: 最大保留消息数（None 表示不限制；0 表示禁止存储）。

    Example:
        ctx = ContextManager(max_messages=100)
        ctx.save(AgentMessage(role="user", content="你好", agent_name="user"))
        history = ctx.load(limit=10)
        window = ctx.get_context_window(max_messages=20)
    """

    def __init__(self, max_messages: Optional[int] = None):
        self.max_messages = max_messages
        # 使用 deque(maxlen) 让 Python 自动完成 O(1) FIFO 淘汰；
        # max_messages=None 时 maxlen=None，即不限制。
        self._messages: deque = deque(maxlen=max_messages)

    def save(self, message: AgentMessage) -> None:
        """
        追加一条消息到上下文。

        超出 max_messages 限制时，deque 自动移除最旧的消息（FIFO 策略，O(1)）。

        Args:
            message: 需要保存的 AgentMessage 对象。

        Raises:
            TexMemoryError: 传入对象类型不正确时抛出。
        """
        if not isinstance(message, AgentMessage):
            raise TexMemoryError(
                f"save() 需要 AgentMessage 类型，收到 {type(message).__name__}"
            )

        if self.max_messages is not None and self.max_messages == 0:
            logger.debug("max_messages=0，本条消息不会被存储")
            return

        # deque(maxlen=N) 追加时若已满会自动从左侧弹出最旧元素
        overflowed = (
            self.max_messages is not None
            and len(self._messages) >= self.max_messages
        )
        self._messages.append(message)

        if overflowed:
            logger.debug(
                f"上下文已满，已自动淘汰最旧消息，当前共 {len(self._messages)} 条"
            )

        logger.debug(
            f"上下文已保存（共 {len(self._messages)} 条）: "
            f"[{message.agent_name}/{message.role}] {message.content[:50]}..."
        )

    def load(self, limit: Optional[int] = None) -> List[AgentMessage]:
        """
        获取消息历史。

        Args:
            limit: 返回最近的 N 条消息，None 返回全部。

        Returns:
            AgentMessage 列表（时间正序，最旧在前）。
        """
        if limit is None:
            return list(self._messages)
        return list(self._messages)[-limit:]

    def clear(self) -> None:
        """清空所有上下文消息。"""
        count = len(self._messages)
        self._messages.clear()
        logger.debug(f"上下文已清空，共清除 {count} 条消息")

    def get_context_window(self, max_messages: int = 20) -> List[AgentMessage]:
        """
        获取用于 LLM 调用的上下文窗口（最近 N 条消息）。

        Args:
            max_messages: 上下文窗口最大消息数，默认 20。

        Returns:
            最近 max_messages 条的 AgentMessage 列表。

        Notes:
            TODO: 未来在此处接入基于 token 计数的智能上下文窗口管理策略，
                  避免超出 LLM 的上下文长度限制。
        """
        return self.load(limit=max_messages)

    def get_messages_by_agent(self, agent_name: str) -> List[AgentMessage]:
        """
        按 Agent 名称筛选消息记录。

        Args:
            agent_name: 目标 Agent 的名称（精确匹配）。

        Returns:
            该 Agent 发出的所有消息列表（时间正序）。
        """
        return [m for m in self._messages if m.agent_name == agent_name]

    def __len__(self) -> int:
        return len(self._messages)

    def __repr__(self) -> str:
        return f"ContextManager(messages={len(self._messages)}, max={self.max_messages})"
