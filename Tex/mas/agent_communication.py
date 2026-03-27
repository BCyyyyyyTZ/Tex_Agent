# ============================================================
# mas/agent_communication.py
# AgentCommunicationProtocol —— Agent 间标准化通信协议
# ============================================================
# 定义 NeuroTeX MAS 中 Agent 间通信的标准协议格式、
# 握手机制和错误处理规范。
#
# 【需要实现的内容】
#
# 1. CommunicationPattern — 通信模式枚举
#    - REQUEST_RESPONSE   # 请求-响应（最常见）
#    - FIRE_AND_FORGET    # 发送后不等待响应
#    - STREAM             # 流式响应（大量数据）
#    - NEGOTIATION        # 协商模式（如 ReflectionAgent 与外部 Critic）
#    - BROADCAST          # 广播（状态通知）
#
# 2. ProtocolMessage — 标准化协议消息（扩展 AgentMessage）
#    新增字段:
#    - protocol_version: str     # 协议版本（向后兼容）
#    - communication_pattern: CommunicationPattern
#    - expects_response: bool    # 是否期待响应
#    - response_schema: dict     # 期望的响应格式（用于验证）
#    - sequence_number: int      # 消息序列号（流式消息排序）
#    - is_final: bool            # 是否是流的最后一条消息
#
# 3. AgentCommunicationProtocol 类
#
#    核心方法:
#
#    async request(
#        sender_id: str,
#        receiver_id: str,
#        request_data: Any,
#        timeout: float = 30.0
#    ) -> Any:
#    - 标准的请求-响应通信
#    - 发送请求消息后等待响应
#    - 超时处理
#
#    async fire_and_forget(
#        sender_id: str, receiver_id: str, data: Any
#    ) -> None:
#    - 单向消息发送，不等待响应
#
#    async stream_request(
#        sender_id: str, receiver_id: str, data: Any
#    ) -> AsyncGenerator[Any, None]:
#    - 流式请求，逐步接收响应片段
#
#    async negotiate(
#        agent1_id: str, agent2_id: str,
#        proposal: Any, max_rounds: int = 3
#    ) -> Any:
#    - 两个 Agent 之间的协商通信
#    - 适用于 ReflectionAgent 与 EvaluatorAgent 的评审协作
#    - 支持多轮来回协商直到达成共识
#
#    _validate_message(message: ProtocolMessage) -> bool:
#    - 验证消息格式符合协议规范
#
#    _create_response_message(
#        original: ProtocolMessage, response_data: Any
#    ) -> ProtocolMessage:
#    - 根据请求消息创建响应消息（保持 correlation_id 一致）
# ============================================================

from __future__ import annotations

import asyncio
from enum import Enum
from typing import Any, AsyncGenerator, Optional

from core.base_agent import AgentMessage


class CommunicationPattern(str, Enum):
    """通信模式枚举，【实现见上方注释】"""
    REQUEST_RESPONSE = "request_response"
    FIRE_AND_FORGET = "fire_and_forget"
    STREAM = "stream"
    NEGOTIATION = "negotiation"
    BROADCAST = "broadcast"


class AgentCommunicationProtocol:
    """
    Agent 间标准化通信协议。
    统一管理各种通信模式，提供高层次的通信 API。
    【完整实现规范见上方注释】
    """

    def __init__(self) -> None:
        # 【需要实现】初始化消息总线引用、待响应请求字典等
        self._pending_responses: dict = {}

    async def request(
        self,
        sender_id: str,
        receiver_id: str,
        request_data: Any,
        timeout: float = 30.0,
    ) -> Any:
        """请求-响应通信，【需要实现】"""
        pass

    async def fire_and_forget(
        self, sender_id: str, receiver_id: str, data: Any
    ) -> None:
        """单向消息发送，【需要实现】"""
        pass

    async def stream_request(
        self,
        sender_id: str,
        receiver_id: str,
        data: Any,
    ) -> AsyncGenerator[Any, None]:
        """流式请求，【需要实现】"""
        pass
        return

    async def negotiate(
        self,
        agent1_id: str,
        agent2_id: str,
        proposal: Any,
        max_rounds: int = 3,
    ) -> Any:
        """两 Agent 协商通信，【需要实现】"""
        pass

    def _validate_message(self, message: AgentMessage) -> bool:
        """验证消息格式，【需要实现】"""
        pass
