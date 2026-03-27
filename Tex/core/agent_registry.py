# ============================================================
# core/agent_registry.py
# 全局 Agent 注册表与服务发现机制
# ============================================================
# 本文件实现"Agent 注册表"，类似微服务架构中的服务发现。
# 所有 Agent 实例在创建时注册到此表，其他组件（Router、
# Orchestrator 等）可通过此表查找和调用 Agent。
#
# 【需要实现的内容】
#
# 1. AgentRegistration — 注册信息数据类
#    字段:
#    - agent_id: str             # Agent 唯一 ID
#    - agent_name: str           # Agent 名称
#    - agent_type: str           # Agent 类型（simple/react/...）
#    - capabilities: list[str]   # 能力标签（便于能力匹配查找）
#    - status: AgentStatus       # 当前状态
#    - instance: BaseAgent       # Agent 实例引用（弱引用，防止内存泄漏）
#    - registered_at: datetime
#    - last_active_at: datetime
#    - task_count: int           # 已完成任务数（统计用）
#    - metadata: dict
#
# 2. AgentRegistry — 注册表类（单例模式）
#
#    核心方法:
#
#    register(agent: BaseAgent, capabilities: list[str]) -> str:
#    - 将 Agent 注册到表中
#    - 返回 agent_id
#    - 如已存在同名 Agent，抛出 DuplicateAgentError
#
#    unregister(agent_id: str) -> None:
#    - 从注册表移除 Agent
#    - 触发 "agent.unregistered" 事件
#
#    get_agent(agent_id: str) -> BaseAgent:
#    - 通过 ID 获取 Agent 实例
#    - 如不存在抛出 AgentNotFoundError
#
#    get_agent_by_name(name: str) -> BaseAgent:
#    - 通过名称获取 Agent 实例
#
#    find_agents_by_type(agent_type: str) -> list[BaseAgent]:
#    - 按类型查找所有 Agent
#
#    find_agents_by_capability(capability: str) -> list[BaseAgent]:
#    - 按能力标签查找所有可用 Agent
#    - 只返回 status=IDLE 或 RUNNING 的 Agent
#
#    find_best_agent(task_type: str, context: dict) -> BaseAgent:
#    - 根据任务类型和上下文选择最优 Agent
#    - 考虑因素：能力匹配度、当前负载、历史成功率
#
#    list_all_agents() -> list[AgentRegistration]:
#    - 返回所有注册信息（不含实例引用）
#
#    get_agent_stats() -> dict:
#    - 返回各 Agent 的任务统计信息
#
#    update_agent_status(agent_id, status) -> None:
#    - 更新 Agent 状态（由 Agent 自身在执行时调用）
#
#    healthcheck() -> dict:
#    - 对所有注册 Agent 进行健康检查
#    - 返回每个 Agent 的健康状态
#
# 3. 装饰器：@register_agent
#    用于自动注册 Agent 类（类级别装饰器）
#    示例: @register_agent(capabilities=["latex", "writing"])
#          class LaTeXAgent(BaseAgent): ...
#    功能：在类实例化时自动调用 registry.register()
#
# 4. get_registry() — 获取全局单例
# ============================================================

from __future__ import annotations

import weakref
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Type

from pydantic import BaseModel, Field


class AgentRegistration(BaseModel):
    """Agent 注册信息，【实现字段见上方注释】"""

    class Config:
        arbitrary_types_allowed = True

    agent_id: str = ""
    agent_name: str = ""
    agent_type: str = ""
    capabilities: List[str] = Field(default_factory=list)
    status: str = "idle"
    registered_at: datetime = Field(default_factory=datetime.now)
    last_active_at: datetime = Field(default_factory=datetime.now)
    task_count: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AgentRegistry:
    """
    全局 Agent 注册表（单例）。
    【完整实现规范见上方注释】
    """

    _instance: Optional["AgentRegistry"] = None

    def __new__(cls) -> "AgentRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if hasattr(self, "_initialized"):
            return
        # 【需要实现】
        # - _agents: dict[str, AgentRegistration]  # agent_id -> registration
        # - _name_index: dict[str, str]             # agent_name -> agent_id
        # - _type_index: dict[str, list[str]]       # agent_type -> [agent_ids]
        # - _capability_index: dict[str, list[str]] # capability -> [agent_ids]
        # - _agent_refs: dict[str, weakref.ref]     # agent_id -> 弱引用
        self._initialized = True

    def register(
        self, agent: Any, capabilities: Optional[List[str]] = None
    ) -> str:
        """注册 Agent，【需要实现】"""
        pass

    def unregister(self, agent_id: str) -> None:
        """注销 Agent，【需要实现】"""
        pass

    def get_agent(self, agent_id: str) -> Any:
        """通过 ID 获取 Agent 实例，【需要实现】"""
        pass

    def get_agent_by_name(self, name: str) -> Any:
        """通过名称获取 Agent，【需要实现】"""
        pass

    def find_agents_by_type(self, agent_type: str) -> List[Any]:
        """按类型查找 Agent，【需要实现】"""
        pass

    def find_agents_by_capability(self, capability: str) -> List[Any]:
        """按能力标签查找可用 Agent，【需要实现】"""
        pass

    def find_best_agent(self, task_type: str, context: Dict = {}) -> Any:
        """
        根据任务类型选择最优 Agent。
        【需要实现】
        多维度评分算法:
        1. 能力匹配分（能力标签与任务类型的 Jaccard 相似度）
        2. 负载分（IDLE=1.0, RUNNING=0.5, 其他=0）
        3. 历史成功率（task_count 和 error_count 的比例）
        加权求和，返回分数最高的 Agent
        """
        pass

    def list_all_agents(self) -> List[AgentRegistration]:
        """返回所有注册信息，【需要实现】"""
        pass

    def get_agent_stats(self) -> Dict[str, Any]:
        """返回 Agent 统计信息，【需要实现】"""
        pass

    def update_agent_status(self, agent_id: str, status: str) -> None:
        """更新 Agent 状态，【需要实现】"""
        pass

    def healthcheck(self) -> Dict[str, Any]:
        """执行全体 Agent 健康检查，【需要实现】"""
        pass

    def __len__(self) -> int:
        """返回已注册 Agent 数量"""
        pass


def register_agent(capabilities: Optional[List[str]] = None):
    """
    类级别装饰器，自动注册 Agent。
    【需要实现】
    返回一个包装类，在 __init__ 后自动调用 registry.register()
    """
    def decorator(cls: Type) -> Type:
        pass
    return decorator


def get_registry() -> AgentRegistry:
    """获取全局 Agent 注册表单例"""
    return AgentRegistry()
