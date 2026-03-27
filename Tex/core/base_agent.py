# ============================================================
# core/base_agent.py
# 所有 Agent 的抽象基类（Abstract Base Class）
# ============================================================
# 本文件定义 NeuroTeX 中所有 Agent 必须实现的接口规范。
# 采用 ABC（抽象基类）模式，强制所有子类实现核心方法。
#
# 【架构地位】
# BaseAgent 是整个系统中最核心的抽象层。
# 所有具体 Agent（SimpleAgent、ReActAgent 等）都继承自此类。
# 它统一了 Agent 的生命周期管理、工具调用接口、记忆访问、
# 消息收发等核心行为。
#
# 【需要实现的内容】
#
# 1. AgentStatus — 枚举，Agent 运行状态
#    - IDLE       # 空闲，等待任务
#    - RUNNING    # 正在执行任务
#    - PAUSED     # 暂停（等待用户输入或外部事件）
#    - COMPLETED  # 任务完成
#    - ERROR      # 发生错误
#    - TERMINATED # 被终止
#
# 2. AgentMessage — 数据类，Agent 间传递的消息格式
#    字段:
#    - message_id: str           # 唯一消息 ID（UUID）
#    - sender_id: str            # 发送者 Agent ID
#    - receiver_id: str          # 接收者 Agent ID（"broadcast" 表示广播）
#    - message_type: str         # 消息类型（task/result/error/status）
#    - content: Any              # 消息内容
#    - metadata: dict            # 附加元数据（时间戳、优先级等）
#    - parent_message_id: str    # 父消息 ID（用于追踪对话链）
#    - timestamp: datetime
#
# 3. TaskContext — 数据类，任务执行上下文
#    字段:
#    - task_id: str              # 任务唯一 ID
#    - task_description: str     # 任务描述
#    - input_data: Any           # 输入数据
#    - session_id: str           # 所属会话 ID
#    - branch_id: str            # 所属上下文分支 ID
#    - user_id: str              # 发起任务的用户 ID
#    - priority: int             # 优先级（0-10，10最高）
#    - deadline: Optional[datetime]  # 任务截止时间
#    - parent_task_id: str       # 父任务 ID（用于子任务）
#    - metadata: dict            # 任务元数据
#
# 4. AgentResult — 数据类，Agent 执行结果
#    字段:
#    - task_id: str
#    - agent_id: str
#    - status: str               # success / partial / failed
#    - output: Any               # 主要输出内容
#    - artifacts: list[dict]     # 产出物（文件、图表等的引用）
#    - token_usage: dict         # Token 用量统计
#    - duration_ms: int          # 执行耗时
#    - reasoning_trace: list     # 推理轨迹（供调试）
#    - error: Optional[str]      # 错误信息（如有）
#    - metadata: dict
#
# 5. BaseAgent — 抽象基类
#    类属性:
#    - agent_type: str           # Agent 类型标识（子类必须定义）
#    - version: str              # Agent 版本号
#
#    实例属性（__init__ 中初始化）:
#    - agent_id: str             # 唯一 ID（UUID）
#    - name: str                 # 可读名称
#    - config: BaseAgentConfig   # Agent 配置
#    - status: AgentStatus       # 当前状态
#    - _tools: dict[str, Tool]   # 可用工具字典
#    - _memory: Optional[Memory] # 记忆系统引用
#    - _rag: Optional[RAGSystem] # RAG 系统引用
#    - _llm: LLM                 # LLM 客户端
#    - _message_bus: MessageBus  # 消息总线引用
#    - _trace_logger: AgentTraceLogger  # 追踪日志器
#
#    抽象方法（子类必须实现）:
#
#    async run(context: TaskContext) -> AgentResult:
#    - 执行核心任务的主入口
#    - 子类在此实现具体的推理逻辑（单次/循环/反思等）
#
#    async _think(context, history) -> str:
#    - 调用 LLM 进行一次推理，返回模型输出文本
#
#    非抽象方法（BaseAgent 提供默认实现，子类可 override）:
#
#    async execute(context: TaskContext) -> AgentResult:
#    - run() 的包装器，负责：
#      a. 更新 status 为 RUNNING
#      b. 记录开始日志
#      c. 调用 run()
#      d. 记录结束日志
#      e. 更新 status
#      f. 发布任务完成事件
#
#    async call_tool(tool_name, **kwargs) -> Any:
#    - 工具调用统一入口
#    - 校验工具是否在 available_tools 列表中
#    - 记录工具调用日志
#    - 捕获工具异常并封装为 ToolError
#
#    async get_memory_context(query, k=5) -> list:
#    - 从记忆系统检索相关上下文
#
#    async add_to_memory(content, metadata) -> None:
#    - 将重要信息存入记忆系统
#
#    async retrieve_knowledge(query, kb_name=None) -> list:
#    - 从 RAG 知识库检索相关知识
#
#    register_tool(tool: Tool) -> None:
#    - 动态注册工具到该 Agent
#
#    get_status() -> dict:
#    - 返回 Agent 当前状态的完整快照（用于监控）
#
#    async send_message(receiver_id, content, msg_type) -> None:
#    - 通过消息总线发送消息给其他 Agent
#
#    async receive_message() -> AgentMessage:
#    - 从消息总线接收消息
#
#    async pause() / async resume() / async terminate():
#    - Agent 生命周期控制
#
#    _build_system_prompt() -> str:
#    - 根据 config 中的模板名和当前 Agent 状态构建系统提示词
#
#    _count_tokens(text) -> int:
#    - 估算文本 token 数量（使用 tiktoken）
# ============================================================

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AgentStatus(str, Enum):
    """Agent 运行状态枚举，【实现见上方注释】"""
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    ERROR = "error"
    TERMINATED = "terminated"


class AgentMessage(BaseModel):
    """Agent 间通信消息格式，【实现字段见上方注释】"""
    message_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    sender_id: str = ""
    receiver_id: str = ""
    message_type: str = "task"
    content: Any = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    parent_message_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)


class TaskContext(BaseModel):
    """任务执行上下文，【实现字段见上方注释】"""
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task_description: str = ""
    input_data: Any = None
    session_id: str = ""
    branch_id: str = "main"
    user_id: str = ""
    priority: int = 5
    deadline: Optional[datetime] = None
    parent_task_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AgentResult(BaseModel):
    """Agent 执行结果，【实现字段见上方注释】"""
    task_id: str = ""
    agent_id: str = ""
    status: str = "success"
    output: Any = None
    artifacts: List[Dict[str, Any]] = Field(default_factory=list)
    token_usage: Dict[str, int] = Field(default_factory=dict)
    duration_ms: int = 0
    reasoning_trace: List[Any] = Field(default_factory=list)
    error: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class BaseAgent(ABC):
    """
    NeuroTeX 所有 Agent 的抽象基类。
    【完整实现规范见上方注释】

    子类实现示例:
        class SimpleAgent(BaseAgent):
            agent_type = "simple"
            version = "1.0.0"

            async def run(self, context: TaskContext) -> AgentResult:
                # 单次调用 LLM 直接返回结果
                response = await self._think(context, [])
                return AgentResult(output=response, ...)

            async def _think(self, context, history) -> str:
                # 调用 LLM API
                ...
    """

    agent_type: str = "base"
    version: str = "1.0.0"

    def __init__(
        self,
        name: str,
        config: Any = None,
    ) -> None:
        # 【需要实现】初始化所有实例属性（见上方注释）
        self.agent_id: str = str(uuid.uuid4())
        self.name: str = name
        self.config = config
        self.status: AgentStatus = AgentStatus.IDLE
        self._tools: Dict[str, Any] = {}
        self._memory: Optional[Any] = None
        self._rag: Optional[Any] = None
        self._llm: Optional[Any] = None
        self._message_bus: Optional[Any] = None

    @abstractmethod
    async def run(self, context: TaskContext) -> AgentResult:
        """
        执行核心任务。子类必须实现此方法。
        【需要实现】具体的推理/执行逻辑
        """
        pass

    @abstractmethod
    async def _think(self, context: TaskContext, history: List[Any]) -> str:
        """
        调用 LLM 进行一次推理。子类必须实现此方法。
        【需要实现】构建消息列表并调用 LLM API
        """
        pass

    async def execute(self, context: TaskContext) -> AgentResult:
        """
        run() 的包装器，统一处理生命周期管理。
        【需要实现】见上方注释中的执行流程
        """
        pass

    async def call_tool(self, tool_name: str, **kwargs) -> Any:
        """
        工具调用统一入口。
        【需要实现】见上方注释
        """
        pass

    async def get_memory_context(self, query: str, k: int = 5) -> List[Any]:
        """从记忆系统检索相关上下文，【需要实现】"""
        pass

    async def add_to_memory(self, content: Any, metadata: Dict = {}) -> None:
        """将重要信息存入记忆系统，【需要实现】"""
        pass

    async def retrieve_knowledge(
        self, query: str, kb_name: Optional[str] = None
    ) -> List[Any]:
        """从 RAG 知识库检索，【需要实现】"""
        pass

    def register_tool(self, tool: Any) -> None:
        """动态注册工具，【需要实现】"""
        pass

    def get_status(self) -> Dict[str, Any]:
        """返回 Agent 当前状态快照，【需要实现】"""
        pass

    async def send_message(
        self,
        receiver_id: str,
        content: Any,
        msg_type: str = "task",
    ) -> None:
        """通过消息总线发送消息，【需要实现】"""
        pass

    async def receive_message(self) -> Optional[AgentMessage]:
        """从消息总线接收消息，【需要实现】"""
        pass

    async def pause(self) -> None:
        """暂停 Agent，【需要实现】"""
        pass

    async def resume(self) -> None:
        """恢复 Agent，【需要实现】"""
        pass

    async def terminate(self) -> None:
        """终止 Agent，【需要实现】"""
        pass

    def _build_system_prompt(self) -> str:
        """根据配置构建系统提示词，【需要实现】"""
        pass

    def _count_tokens(self, text: str) -> int:
        """估算 token 数量，【需要实现】使用 tiktoken"""
        pass

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name} id={self.agent_id[:8]} status={self.status}>"
