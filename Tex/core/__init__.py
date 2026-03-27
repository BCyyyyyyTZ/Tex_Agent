# ============================================================
# core/__init__.py
# 核心基础设施模块入口
# ============================================================
# core 模块提供整个 NeuroTeX 系统的基础设施层，包括：
# - BaseAgent: 所有 Agent 的抽象基类
# - AgentRegistry: 全局 Agent 注册与发现
# - MessageBus: Agent 间异步消息通信总线
# - StateMachine: Agent 任务状态机
# - EventSystem: 全局事件发布/订阅系统
# - Exceptions: 统一异常体系
# ============================================================

from core.base_agent import BaseAgent, AgentStatus, AgentMessage
from core.agent_registry import AgentRegistry, get_registry
from core.message_bus import MessageBus, get_message_bus
from core.state_machine import StateMachine, TaskState
from core.event_system import EventSystem, Event, get_event_system
from core.exceptions import (
    NeuroTeXError,
    AgentError,
    ToolError,
    MemoryError,
    RAGError,
    RouterError,
    ConfigError,
)

__all__ = [
    "BaseAgent", "AgentStatus", "AgentMessage",
    "AgentRegistry", "get_registry",
    "MessageBus", "get_message_bus",
    "StateMachine", "TaskState",
    "EventSystem", "Event", "get_event_system",
    "NeuroTeXError", "AgentError", "ToolError",
    "MemoryError", "RAGError", "RouterError", "ConfigError",
]
