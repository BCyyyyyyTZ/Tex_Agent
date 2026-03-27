# ============================================================
# core/event_system.py
# 全局事件发布/订阅系统（Event Bus）
# ============================================================
# 本文件实现 NeuroTeX 的事件系统，支持异步事件的发布与订阅。
# 与 MessageBus 的区别：
# - MessageBus: Agent 之间定向/广播的任务消息
# - EventSystem: 系统级别的事件通知，解耦模块间依赖
#
# 例如：
# - Agent 完成任务后发布 "agent.task.completed" 事件
# - 监控模块订阅此事件来更新统计数据
# - UI 模块订阅此事件来更新进度显示
# 这样 Agent 不需要直接引用监控模块或 UI 模块
#
# 【需要实现的内容】
#
# 1. EventType — 枚举，系统预定义的事件类型
#    - AGENT_STARTED          # Agent 开始执行
#    - AGENT_COMPLETED        # Agent 完成任务
#    - AGENT_FAILED           # Agent 任务失败
#    - AGENT_PAUSED           # Agent 暂停
#    - TASK_CREATED           # 新任务创建
#    - TASK_ROUTED            # 任务完成路由
#    - TASK_COMPLETED         # 任务完成
#    - TASK_FAILED            # 任务失败
#    - MEMORY_UPDATED         # 记忆系统更新
#    - BRANCH_CREATED         # 创建新上下文分支
#    - BRANCH_MERGED          # 分支合并
#    - RAG_RETRIEVED          # RAG 检索完成
#    - USER_EMOTION_DETECTED  # 检测到用户情绪变化
#    - SYSTEM_ERROR           # 系统级错误
#    - SESSION_STARTED        # 用户会话开始
#    - SESSION_ENDED          # 用户会话结束
#    - COST_THRESHOLD_REACHED # 费用达到警告阈值
#
# 2. Event — 事件数据类
#    字段:
#    - event_id: str        # UUID
#    - event_type: str      # EventType 值或自定义字符串
#    - source: str          # 事件来源（模块名/Agent ID）
#    - payload: dict        # 事件携带的数据
#    - timestamp: datetime
#    - session_id: str      # 关联的会话 ID
#    - correlation_id: str  # 用于关联相关事件的 ID
#
# 3. EventSystem — 事件系统主类（单例）
#
#    初始化:
#    - _handlers: dict[str, list[Callable]]  # event_type -> [handlers]
#    - _async_handlers: dict[str, list[Callable]]  # 异步 handlers
#    - _event_history: deque                 # 最近 N 个事件历史
#    - _middleware: list[Callable]           # 事件处理中间件
#
#    核心方法:
#
#    subscribe(event_type: str, handler: Callable, async_handler: bool) -> str:
#    - 订阅事件，返回 subscription_id（用于取消订阅）
#    - handler 签名: def handler(event: Event) -> None
#    - async_handler 标志决定是否以协程方式调用
#
#    unsubscribe(subscription_id: str) -> None:
#    - 按 subscription_id 取消订阅
#
#    async publish(event: Event) -> None:
#    - 发布事件，调用所有订阅了该事件类型的 handler
#    - 同时调用订阅了 "*"（通配符）的 handler
#    - 保存到事件历史
#
#    async publish_event(
#        event_type, source, payload, session_id=""
#    ) -> None:
#    - 快捷发布方法，自动构建 Event 对象
#
#    get_event_history(
#        event_type=None, source=None, limit=100
#    ) -> list[Event]:
#    - 查询事件历史，支持过滤
#
#    clear_handlers(event_type: str = None) -> None:
#    - 清除指定类型（或所有）的 handlers（测试用）
#
# 4. 事件处理器装饰器
#    @on_event("agent.task.completed")
#    async def handle_task_completed(event: Event):
#        ...
#    装饰器将函数自动注册为事件处理器
#
# 5. 内置事件处理器（在对应模块中注册）
#    - 成本追踪器：监听所有 Agent 完成事件，累计 token 用量
#    - 会话记录器：监听 SESSION_STARTED/ENDED，记录会话数据
#    - 情绪响应器：监听 USER_EMOTION_DETECTED，触发陪伴响应
# ============================================================

from __future__ import annotations

import asyncio
import uuid
from collections import deque
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class EventType(str, Enum):
    """系统预定义事件类型，【实现见上方注释】"""
    AGENT_STARTED = "agent.started"
    AGENT_COMPLETED = "agent.completed"
    AGENT_FAILED = "agent.failed"
    AGENT_PAUSED = "agent.paused"
    TASK_CREATED = "task.created"
    TASK_ROUTED = "task.routed"
    TASK_COMPLETED = "task.completed"
    TASK_FAILED = "task.failed"
    MEMORY_UPDATED = "memory.updated"
    BRANCH_CREATED = "context.branch.created"
    BRANCH_MERGED = "context.branch.merged"
    RAG_RETRIEVED = "rag.retrieved"
    USER_EMOTION_DETECTED = "companion.emotion.detected"
    SYSTEM_ERROR = "system.error"
    SESSION_STARTED = "session.started"
    SESSION_ENDED = "session.ended"
    COST_THRESHOLD_REACHED = "cost.threshold.reached"


class Event:
    """系统事件，【实现字段见上方注释】"""

    def __init__(
        self,
        event_type: str,
        source: str,
        payload: Optional[Dict[str, Any]] = None,
        session_id: str = "",
        correlation_id: str = "",
    ) -> None:
        self.event_id: str = str(uuid.uuid4())
        self.event_type: str = event_type
        self.source: str = source
        self.payload: Dict[str, Any] = payload or {}
        self.timestamp: datetime = datetime.now()
        self.session_id: str = session_id
        self.correlation_id: str = correlation_id or self.event_id


class EventSystem:
    """
    全局事件发布/订阅系统（单例）。
    【完整实现规范见上方注释】
    """

    _instance: Optional["EventSystem"] = None

    def __new__(cls) -> "EventSystem":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if hasattr(self, "_initialized"):
            return
        # 【需要实现】初始化所有属性
        self._initialized = True

    def subscribe(
        self,
        event_type: str,
        handler: Callable,
        is_async: bool = True,
    ) -> str:
        """订阅事件，返回 subscription_id，【需要实现】"""
        pass

    def unsubscribe(self, subscription_id: str) -> None:
        """取消订阅，【需要实现】"""
        pass

    async def publish(self, event: Event) -> None:
        """发布事件，调用所有注册的处理器，【需要实现】"""
        pass

    async def publish_event(
        self,
        event_type: str,
        source: str,
        payload: Optional[Dict[str, Any]] = None,
        session_id: str = "",
    ) -> None:
        """快捷发布方法，【需要实现】"""
        pass

    def get_event_history(
        self,
        event_type: Optional[str] = None,
        source: Optional[str] = None,
        limit: int = 100,
    ) -> List[Event]:
        """查询事件历史，【需要实现】"""
        pass

    def clear_handlers(self, event_type: Optional[str] = None) -> None:
        """清除事件处理器（测试用），【需要实现】"""
        pass


def on_event(event_type: str):
    """
    事件处理器注册装饰器。
    【需要实现】自动将函数注册到全局 EventSystem
    """
    def decorator(func: Callable) -> Callable:
        pass
    return decorator


def get_event_system() -> EventSystem:
    """获取全局事件系统单例"""
    return EventSystem()
