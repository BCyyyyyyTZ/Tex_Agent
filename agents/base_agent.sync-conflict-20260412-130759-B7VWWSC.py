"""
BaseAgent 抽象基类。
所有 Agent 实现均继承此类，保证接口统一，支持面向接口编程与 Mock 测试。
"""
from abc import ABC, abstractmethod
from typing import List
import asyncio

from core.message import AgentMessage


class BaseAgent(ABC):
    """
    Agent 标准抽象基类。

    所有 Agent（SimpleAgent、ReActAgent 等）必须继承此类并实现以下接口：
    - name: Agent 唯一标识名（property）
    - run: 同步推理执行
    - reset: 重置 Agent 内部状态

    ainvoke 提供默认的异步实现（线程池包装 run），子类可按需重写以实现真正的异步推理。

    设计原则：
        工作流节点（workflow/nodes.py）仅依赖 BaseAgent 接口，不依赖具体实现。
        开发者可通过 Mock BaseAgent 独立测试工作流，无需真实 LLM 调用。

    TODO: 未来在此处增加 emotion_hook(message: AgentMessage) 情感分析钩子接口
    TODO: 未来在此处增加 before_run / after_run 生命周期钩子，用于中间件拦截
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Agent 唯一标识名（英文，PascalCase，如 "DesignAgent"）。"""

    @abstractmethod
    def run(self, message: AgentMessage) -> AgentMessage:
        """
        同步执行推理，接收输入消息并返回 Agent 响应。

        Args:
            message: 输入的 AgentMessage 对象（role 通常为 "user"）。

        Returns:
            Agent 生成的响应 AgentMessage（role="assistant"，agent_name=self.name）。

        Raises:
            AgentError: 推理执行失败时抛出。
        """

    async def ainvoke(self, message: AgentMessage) -> AgentMessage:
        """
        异步执行推理。

        默认实现将同步 run() 包装在线程池中执行，避免阻塞事件循环。
        子类可重写此方法以实现真正的原生异步推理（如使用 httpx 的异步 LLM 调用）。

        Args:
            message: 输入的 AgentMessage 对象。

        Returns:
            Agent 生成的响应 AgentMessage。
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.run, message)

    @abstractmethod
    def reset(self) -> None:
        """
        重置 Agent 内部状态（如清空对话历史、工具调用记录等）。
        在开始处理新任务前调用，防止历史上下文污染新任务。
        """

    def get_history(self) -> List[AgentMessage]:
        """
        获取当前 Agent 的对话历史。

        BaseAgent 默认返回空列表，维护历史的子类应重写此方法。

        Returns:
            AgentMessage 历史列表（按时间正序）。
        """
        return []
