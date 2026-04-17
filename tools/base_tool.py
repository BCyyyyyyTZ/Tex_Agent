"""
BaseTool 标准工具抽象基类。
所有工具实现均继承此类，保证工具接口统一，支持动态注册与插拔式扩展。
"""
from abc import ABC, abstractmethod
import asyncio

from core.message import ToolResult


class BaseTool(ABC):
    """
    工具标准接口基类。

    所有工具（ArxivSearchTool、LaTeXParserTool 等）必须继承此类并实现：
    - name: 工具唯一标识名（property）
    - description: 工具功能描述（property，供 LLM 理解工具用途）
    - run: 同步执行工具逻辑

    arun 提供默认的异步实现（线程池包装 run），原生支持异步的工具可重写。

    设计原则：
        工具与 Agent 完全解耦，Agent 仅通过 BaseTool 接口调用工具，
        便于开发者 C 独立开发和测试每个工具，无需关心 Agent 实现细节。
    """

    def __init__(self, name: str, description: str, input_schema: dict[str, str]):
        self.name = name
        self.description = description
        self.input_schema = input_schema


    def run(self, input: str) -> ToolResult:
        """
        同步执行工具。

        Args:
            input: 工具输入参数（纯文本，通常为用户查询或指令）。

        Returns:
            ToolResult 对象，包含执行结果（output）和状态（success/error）。

        Raises:
            ToolError: 工具执行失败时抛出（内部应 catch 后封装为 ToolResult 返回）。
        """
        pass

    async def arun(self, input: str) -> ToolResult:
        """
        异步执行工具（默认实现：在线程池中运行同步 run，不阻塞事件循环）。

        若工具本身原生支持异步（如基于 httpx 的 HTTP 调用），
        子类可重写此方法以实现真正的异步执行，获得更好的并发性能。

        Args:
            input: 工具输入参数。

        Returns:
            ToolResult 对象。
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.run, input)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name!r})"
