# context/base.py
"""
BaseContext：上下文模块抽象基类。
所有上下文实现（ContextManager、向量库上下文、数据库上下文等）均继承此类，保证接口统一。
"""
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, TYPE_CHECKING

from core.message import WorkflowMessage

if TYPE_CHECKING:
    # 仅用于类型提示，避免循环导入
    from memory.base_memory import BaseMemory


class BaseContext(ABC):
    """
    上下文模块标准接口基类。

    定义了所有上下文实现必须支持的基础操作：
    - save:   存储一条 WorkflowMessage 到上下文
    - load:   检索消息历史
    - clear:  清空上下文
    - build:  (可选) GSSC 上下文构建流水线，用于聚合多源数据生成 LLM Prompt

    设计原则：
        Agent 和工作流节点仅依赖 BaseContext 接口，
        便于将来无缝切换上下文后端（内存列表 → 向量库 → 数据库）
        而无需修改 Agent 或节点代码。
    """

    @abstractmethod
    def save(self, message: WorkflowMessage) -> None:
        """
        存储一条消息到上下文。

        Args:
            message: 需要存储的 WorkflowMessage 对象。

        Raises:
            TypeError: 传入对象类型不正确时抛出。
            MemoryError: 存储失败时抛出。
        """
        pass

    @abstractmethod
    def load(self, limit: Optional[int] = None) -> List[WorkflowMessage]:
        """
        检索消息历史。

        Args:
            limit: 返回最近的 N 条消息（按时间正序返回）。None 表示返回全部。

        Returns:
            WorkflowMessage 列表（按时间正序排列，最旧的在前）。
        """
        pass

    @abstractmethod
    def clear(self) -> None:
        """清空所有上下文内容。"""
        pass

    def __len__(self) -> int:
        """
        返回当前存储的消息数量。
        默认调用 load() 计数，子类可重写为 O(1) 实现（如直接返回内部计数器）。
        """
        return len(self.load())

    # ================= GSSC 扩展接口 =================
    def build(
        self,
        state: Dict[str, Any],
        memory: Optional["BaseMemory"] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        【可选】GSSC 多源上下文构建流水线。
        默认实现：仅返回对话历史的简单拼接。
        子类（如 ContextManager）应重写此方法以支持 RAG/Memory/Token压缩 等高级能力。

        Args:
            state: LangGraph WorkflowState，包含 messages / retrieved_context / input 等字段。
            memory: 长期记忆实例（需实现 search() 接口）。
            config: 配置字典，如 conv_limit, mem_limit, max_tokens, format 等。

        Returns:
            格式化后的上下文字符串，可直接用于 LLM Prompt。
        """
        # 默认降级实现：仅加载对话历史并简单格式化
        messages = self.load(limit=config.get("conv_limit") if config else None)
        if not messages:
            return ""

        parts = []
        for msg in messages:
            role = getattr(msg, "role", "unknown").upper()
            source_type = getattr(msg, "source_type", "system")
            source_id = getattr(msg, "source_id", "sys")
            parts.append(f"[{role} | {source_type}:{source_id}] {msg.content}")
        return "\n".join(parts)