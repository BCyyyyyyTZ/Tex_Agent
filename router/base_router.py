"""
[扩展] BaseRouter 自适应路由模块接口定义。
预留根据任务复杂度和类型动态分配最合适 Agent 的路由策略接口。

TODO: 开发者 D 负责实现此类（第二阶段任务）
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Optional, Any, TYPE_CHECKING

from core.message import AgentMessage

if TYPE_CHECKING:
    from agents.base_agent import BaseAgent


@dataclass
class RouteDecision:
    """
    路由决策结果。

    Attributes:
        agent_name: 被选中的 Agent 名称。
        agent: 对应的 Agent 实例引用。
        confidence: 路由置信度（0.0~1.0，越高表示越确定）。
        reason: 选择该 Agent 的决策原因说明（用于调试和日志）。
    """ 

    agent_name: str
    agent: "BaseAgent"
    confidence: float
    reason: str


class BaseRouter(ABC):
    """
    [扩展] 自适应路由器抽象基类。

    功能规划：
        1. 任务类型路由：根据任务类型（文献检索/LaTeX 解析/写作建议等）
           选择最合适的 Agent 架构
        2. 复杂度路由：根据任务复杂度（simple/medium/complex）
           动态选择 SimpleAgent / ReActAgent / PlanAndSolveAgent
        3. 负载均衡：在多个同类 Agent 中选择负载最低的实例
        4. 历史优化：基于历史执行效果持续优化路由策略

    TODO: 开发者 D 实现建议：
          - evaluate_complexity() 可先用规则（任务长度、关键词）实现，
            后续升级为 LLM 评估
          - route() 可维护一个优先级规则表，逐条匹配
          - 考虑接入 metrics 收集，为后续路由优化提供数据支撑
    """

    def __init__(self, available_agents: List["BaseAgent"]):
        """
        Args:
            available_agents: 路由器可分配的所有 Agent 实例列表。
        """
        self.available_agents: Dict[str, "BaseAgent"] = {
            agent.name: agent for agent in available_agents
        }

    @abstractmethod
    def route(
        self,
        message: AgentMessage,
        context: Optional[Dict[str, Any]] = None,
    ) -> RouteDecision:
        """
        根据输入消息和上下文做出路由决策。

        Args:
            message: 用户输入消息。
            context: 额外上下文信息（如任务历史、用户偏好、当前分支等）。

        Returns:
            RouteDecision 路由决策结果。

        Raises:
            RouterError: 路由失败时（无合适 Agent 或策略异常）。
            NotImplementedError: 子类必须实现。
        """
        raise NotImplementedError

    @abstractmethod
    def evaluate_complexity(self, message: AgentMessage) -> str:
        """
        评估任务复杂度级别。

        Args:
            message: 用户输入消息。

        Returns:
            复杂度标签字符串：
            - "simple":  简单任务，适合 SimpleAgent（如"帮我查一篇论文"）
            - "medium":  中等任务，适合 ReActAgent（如"检索并分析比较3篇论文"）
            - "complex": 复杂任务，适合 PlanAndSolveAgent（如"帮我完整规划 Related Work"）

        Raises:
            NotImplementedError: 子类必须实现。
        """
        raise NotImplementedError

    def register_agent(self, agent: "BaseAgent") -> None:
        """
        动态注册新 Agent 到路由器可用池。

        Args:
            agent: 需要注册的 Agent 实例。
        """
        self.available_agents[agent.name] = agent

    def unregister_agent(self, agent_name: str) -> bool:
        """
        从路由器可用池中移除 Agent。

        Args:
            agent_name: 要移除的 Agent 名称。

        Returns:
            True 表示成功移除，False 表示 Agent 不存在。
        """
        if agent_name in self.available_agents:
            del self.available_agents[agent_name]
            return True
        return False

    # TODO: 未来增加 route_async() 异步路由接口
    # TODO: 未来增加 feedback(decision, success, latency) 接口，
    #       基于执行结果持续优化路由策略（强化学习/规则更新）
