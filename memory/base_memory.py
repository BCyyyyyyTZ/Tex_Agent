"""
BaseMemory 记忆模块抽象基类。
所有记忆实现（ContextManager、向量库等）均继承此类，保证接口统一。
"""
from abc import ABC, abstractmethod
from typing import List, Optional

from core.message import AgentMessage


class BaseMemory(ABC):
    """
    记忆模块标准接口基类。

    定义了所有记忆实现必须支持的基础操作：
    - save:  存储消息
    - load:  检索消息
    - clear: 清空记忆

    设计原则：
        Agent 和工作流节点仅依赖 BaseMemory 接口，
        便于将来无缝切换记忆后端（内存列表 → 向量库 → 数据库）
        而无需修改 Agent 或节点代码。
    """

    @abstractmethod
    def save(self, message: AgentMessage) -> None:
        """
        存储一条消息到记忆。

        Args:
            message: 需要存储的 AgentMessage 对象。

        Raises:
            MemoryError: 参数类型错误或存储失败时抛出。
        """

    @abstractmethod
    def load(self, limit: Optional[int] = None) -> List[AgentMessage]:
        """
        检索消息历史。

        Args:
            limit: 返回最近的 N 条消息（按时间倒序取后 N 条，正序返回）。
                   None 表示返回全部历史。

        Returns:
            AgentMessage 列表（按时间正序排列，最旧的在前）。

        Raises:
            MemoryError: 检索失败时抛出。
        """

    @abstractmethod
    def clear(self) -> None:
        """清空所有记忆内容。"""

    def __len__(self) -> int:
        """返回当前存储的消息数量（不传 limit 获取全量后计数）。"""
        return len(self.load())
