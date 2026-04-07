# ============================================================
# core/state_machine.py
# 任务状态机 —— 管理任务和 Agent 的状态流转
# ============================================================
# 本文件实现有限状态机（FSM），管理 NeuroTeX 中任务和 Agent
# 的合法状态转换。确保状态转换的一致性和可追溯性。
#
# 【为什么需要状态机？】
# 在复杂的多 Agent 系统中，Agent 可能处于多种状态（规划中、
# 执行中、等待用户确认、反思中等）。状态机可以：
# 1. 防止非法状态转换（如 COMPLETED -> RUNNING）
# 2. 在状态变化时触发相应的回调/事件
# 3. 提供清晰的状态转换图，便于调试
# 4. 支持状态持久化（系统重启后恢复）
#
# 【需要实现的内容】
#
# 1. TaskState — 枚举，任务状态
#    - CREATED     # 任务创建，尚未分配
#    - QUEUED      # 已加入队列，等待执行
#    - PLANNING    # 正在由 Planner 分解规划
#    - ROUTING     # 正在由 Router 选择执行者
#    - EXECUTING   # 正在执行
#    - REFLECTING  # 正在自我反思/修正
#    - WAITING     # 等待外部输入（用户/工具/其他 Agent）
#    - COMPLETED   # 成功完成
#    - FAILED      # 执行失败
#    - CANCELLED   # 被用户或系统取消
#    - TIMEOUT     # 超时
#
# 2. StateTransition — 数据类，单次状态转换记录
#    字段:
#    - from_state: TaskState
#    - to_state: TaskState
#    - trigger: str             # 触发转换的事件名
#    - agent_id: str            # 执行转换的 Agent
#    - timestamp: datetime
#    - metadata: dict           # 附加信息（如错误原因）
#
# 3. StateMachine — 状态机主类
#
#    初始化:
#    - entity_id: str           # 被管理对象的 ID（task_id 或 agent_id）
#    - entity_type: str         # "task" 或 "agent"
#    - current_state: TaskState
#    - transition_history: list[StateTransition]
#    - _transition_table: dict  # {from_state: {trigger: to_state}}
#    - _callbacks: dict         # {state: list[Callable]}（状态进入回调）
#    - _exit_callbacks: dict    # {state: list[Callable]}（状态退出回调）
#
#    核心方法:
#
#    transition(trigger: str, agent_id: str = "", metadata: dict = {}) -> bool:
#    - 根据 trigger 执行状态转换
#    - 检查当前状态下该 trigger 是否合法
#    - 执行退出旧状态的回调
#    - 更新 current_state
#    - 执行进入新状态的回调
#    - 记录 StateTransition
#    - 返回是否转换成功
#
#    can_transition(trigger: str) -> bool:
#    - 判断当前状态下是否可以执行该 trigger
#
#    on_enter(state: TaskState, callback: Callable) -> None:
#    - 注册进入某状态时的回调
#
#    on_exit(state: TaskState, callback: Callable) -> None:
#    - 注册离开某状态时的回调
#
#    get_history() -> list[StateTransition]:
#    - 返回完整的状态转换历史
#
#    get_current_state() -> TaskState:
#    - 返回当前状态
#
#    is_terminal() -> bool:
#    - 判断是否处于终止状态（COMPLETED/FAILED/CANCELLED）
#
#    reset(initial_state: TaskState = TaskState.CREATED) -> None:
#    - 重置状态机（清空历史，回到初始状态）
#
# 4. 任务状态机默认转换表（TASK_TRANSITION_TABLE）
#    定义合法的状态转换规则:
#    CREATED + "queue" -> QUEUED
#    QUEUED + "start_planning" -> PLANNING
#    QUEUED + "start_routing" -> ROUTING
#    PLANNING + "plan_complete" -> ROUTING
#    ROUTING + "assign" -> EXECUTING
#    EXECUTING + "need_reflection" -> REFLECTING
#    EXECUTING + "need_input" -> WAITING
#    EXECUTING + "complete" -> COMPLETED
#    EXECUTING + "fail" -> FAILED
#    REFLECTING + "revision_complete" -> EXECUTING
#    WAITING + "input_received" -> EXECUTING
#    任何状态 + "cancel" -> CANCELLED
#    任何状态 + "timeout" -> TIMEOUT
#    ...（完整转换表）
#
# 5. StateMachineFactory
#    create_task_state_machine(task_id) -> StateMachine:
#    - 创建并返回配置好转换规则的任务状态机
#
#    create_agent_state_machine(agent_id) -> StateMachine:
#    - 创建 Agent 状态管理的状态机
# ============================================================

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class TaskState(str, Enum):
    """任务状态枚举，【实现见上方注释】"""
    CREATED = "created"
    QUEUED = "queued"
    PLANNING = "planning"
    ROUTING = "routing"
    EXECUTING = "executing"
    REFLECTING = "reflecting"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class StateTransition:
    """状态转换记录，【实现字段见上方注释】"""

    def __init__(
        self,
        from_state: TaskState,
        to_state: TaskState,
        trigger: str,
        agent_id: str = "",
        metadata: Optional[Dict] = None,
    ) -> None:
        # 【需要实现】赋值所有字段
        pass


class StateMachine:
    """
    有限状态机，管理任务或 Agent 的状态流转。
    【完整实现规范见上方注释】
    """

    def __init__(
        self,
        entity_id: str,
        entity_type: str = "task",
        initial_state: TaskState = TaskState.CREATED,
        transition_table: Optional[Dict] = None,
    ) -> None:
        # 【需要实现】初始化所有属性
        pass

    def transition(
        self,
        trigger: str,
        agent_id: str = "",
        metadata: Optional[Dict] = None,
    ) -> bool:
        """执行状态转换，【需要实现】"""
        pass

    def can_transition(self, trigger: str) -> bool:
        """判断是否可以执行该转换，【需要实现】"""
        pass

    def on_enter(self, state: TaskState, callback: Callable) -> None:
        """注册状态进入回调，【需要实现】"""
        pass

    def on_exit(self, state: TaskState, callback: Callable) -> None:
        """注册状态退出回调，【需要实现】"""
        pass

    def get_history(self) -> List[StateTransition]:
        """返回转换历史，【需要实现】"""
        pass

    def get_current_state(self) -> TaskState:
        """返回当前状态，【需要实现】"""
        pass

    def is_terminal(self) -> bool:
        """判断是否处于终止状态，【需要实现】"""
        pass

    def reset(self, initial_state: TaskState = TaskState.CREATED) -> None:
        """重置状态机，【需要实现】"""
        pass

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典（用于持久化），【需要实现】"""
        pass


# 默认任务状态转换表
TASK_TRANSITION_TABLE: Dict[TaskState, Dict[str, TaskState]] = {
    # 【需要实现】填入完整的状态转换规则（见上方注释）
    TaskState.CREATED: {
        "queue": TaskState.QUEUED,
        "cancel": TaskState.CANCELLED,
    },
    # ...
}


class StateMachineFactory:
    """
    状态机工厂，创建预配置的状态机实例。
    【需要实现的方法见上方注释】
    """

    @staticmethod
    def create_task_state_machine(task_id: str) -> StateMachine:
        """创建任务状态机，【需要实现】"""
        pass

    @staticmethod
    def create_agent_state_machine(agent_id: str) -> StateMachine:
        """创建 Agent 状态机，【需要实现】"""
        pass
