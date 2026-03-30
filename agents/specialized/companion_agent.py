# ============================================================
# agents/specialized/companion_agent.py
# CompanionAgent —— 情感陪伴与心理支持智能体
# ============================================================
# CompanionAgent 是 NeuroTeX 最独特的 Agent 之一。
# 它不只是一个工具，而是用户在漫长科研旅途中的智能伙伴。
# 通过感知用户情绪状态，在适当时机提供鼓励、情感支持和人文关怀，
# 让严谨的学术工具也有温度。
#
# 【核心设计理念】
# - 不替代心理咨询，而是提供陪伴式支持
# - 科研压力是真实存在的，适时的情绪认可很重要
# - 在用户连续工作过久时，主动建议休息
# - 在用户完成里程碑任务时，真诚地给予肯定
# - 风格：温暖、真诚、不浮夸、不说教
#
# 【需要实现的内容】
#
# 1. EmotionState — 枚举，用户情绪状态
#    - NEUTRAL       # 平稳
#    - FOCUSED       # 专注工作中
#    - FRUSTRATED    # 受挫/焦虑
#    - TIRED         # 疲惫
#    - EXCITED       # 兴奋/有成就感
#    - CONFUSED      # 困惑
#    - STRESSED      # 高压状态
#    - SATISFIED     # 满足/完成感
#
# 2. EmotionRecord — 情绪记录
#    字段:
#    - detected_emotion: EmotionState
#    - confidence: float         # 检测置信度（0-1）
#    - indicators: list[str]     # 检测到的情绪指标（关键词、语气等）
#    - session_duration_min: int # 本次连续工作时长（分钟）
#    - timestamp: datetime
#
# 3. CompanionResponse — 陪伴响应
#    字段:
#    - response_type: str        # "encouragement"/"rest_suggestion"/"celebration"/"empathy"
#    - message: str              # 陪伴消息文本
#    - emoji: str                # 适当的 emoji（可配置关闭）
#    - action_suggestions: list  # 可选的具体行动建议（如"喝杯水"）
#    - should_interrupt: bool    # 是否主动打断用户当前任务
#
# 4. CompanionAgent 类（继承 SimpleAgent）
#    agent_type = "companion"
#
#    额外属性:
#    - response_style: str       # "warm" / "professional" / "casual"
#    - emotion_check_interval: int  # 每 N 轮对话检测一次情绪
#    - encouragement_probability: float  # 主动鼓励的概率
#    - rest_reminder_threshold_min: int  # 连续工作 N 分钟后提醒休息
#    - _session_start_time: datetime
#    - _emotion_history: list[EmotionRecord]
#    - _milestone_counter: dict  # 记录各类里程碑完成情况
#
#    核心方法:
#
#    async detect_emotion(user_message: str, context: dict) -> EmotionRecord:
#    - 分析用户消息的情绪指标:
#      - 关键词分析（"头疼"/"终于"/"搞不定"/"耶"等）
#      - 语气分析（感叹号、省略号的情绪含义）
#      - 消息长度和频率（短促可能表示焦虑）
#      - 历史情绪趋势（连续负面状态）
#      - 工作时长（>2小时警惕疲劳）
#    - 调用 LLM 做综合判断（轻量级调用）
#    - 返回情绪记录
#
#    async generate_companion_response(
#        emotion: EmotionRecord,
#        task_context: str,
#        milestone_achieved: bool = False
#    ) -> CompanionResponse:
#    - 根据情绪状态生成适当的陪伴响应
#    - FRUSTRATED -> 共情 + 鼓励 + 可能的解决思路提示
#    - TIRED -> 关心 + 休息建议
#    - EXCITED / SATISFIED -> 真诚庆祝
#    - STRESSED -> 温和的任务分解建议
#    - 注意：不是每次都要插入陪伴消息，避免干扰工作流
#
#    async check_and_respond(
#        user_message: str,
#        conversation_context: list,
#        task_progress: dict
#    ) -> Optional[CompanionResponse]:
#    - 综合评估当前是否需要伴随响应
#    - 基于时间触发（连续工作 N 分钟）
#    - 基于情绪触发（检测到负面情绪）
#    - 基于里程碑触发（完成重要任务节点）
#    - 如不需要响应则返回 None
#
#    async celebrate_milestone(
#        milestone_type: str,
#        details: str
#    ) -> CompanionResponse:
#    - 庆祝用户完成重要节点（完成第一章/修复难题/论文提交等）
#
#    def should_suggest_rest(self) -> bool:
#    - 判断当前是否应该建议用户休息
#    - 基于连续工作时长和最近的情绪状态
#
#    async _analyze_message_tone(message: str) -> dict:
#    - 分析消息语气（轻量级分析）
#    - 不调用 LLM，使用规则 + 关键词匹配
#
#    _get_session_duration_minutes(self) -> int:
#    - 计算当前会话已持续时长
# ============================================================

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from agents.base.simple_agent import SimpleAgent
from core.base_agent import AgentResult, TaskContext


class EmotionState(str, Enum):
    """用户情绪状态枚举，【实现见上方注释】"""
    NEUTRAL = "neutral"
    FOCUSED = "focused"
    FRUSTRATED = "frustrated"
    TIRED = "tired"
    EXCITED = "excited"
    CONFUSED = "confused"
    STRESSED = "stressed"
    SATISFIED = "satisfied"


@dataclass
class EmotionRecord:
    """情绪检测记录，【实现字段见上方注释】"""
    detected_emotion: EmotionState = EmotionState.NEUTRAL
    confidence: float = 0.0
    indicators: List[str] = field(default_factory=list)
    session_duration_min: int = 0
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class CompanionResponse:
    """陪伴响应，【实现字段见上方注释】"""
    response_type: str = "encouragement"
    message: str = ""
    emoji: str = ""
    action_suggestions: List[str] = field(default_factory=list)
    should_interrupt: bool = False


class CompanionAgent(SimpleAgent):
    """
    情感陪伴与心理支持智能体。
    科研路上的温暖伙伴，而不只是工具。
    【完整实现规范见上方注释】
    """

    agent_type: str = "companion"
    version: str = "1.0.0"

    def __init__(
        self,
        name: str = "CompanionAgent",
        config: Optional[Any] = None,
    ) -> None:
        super().__init__(name=name, config=config)
        # 【需要实现】初始化额外属性
        self.response_style: str = "warm"
        self.emotion_check_interval: int = 5
        self.encouragement_probability: float = 0.3
        self.rest_reminder_threshold_min: int = 90
        self._session_start_time: datetime = datetime.now()
        self._emotion_history: List[EmotionRecord] = []
        self._milestone_counter: Dict[str, int] = {}

    async def detect_emotion(
        self, user_message: str, context: Dict[str, Any]
    ) -> EmotionRecord:
        """检测用户情绪状态，【需要实现】"""
        pass

    async def generate_companion_response(
        self,
        emotion: EmotionRecord,
        task_context: str,
        milestone_achieved: bool = False,
    ) -> CompanionResponse:
        """生成情感陪伴响应，【需要实现】"""
        pass

    async def check_and_respond(
        self,
        user_message: str,
        conversation_context: List[Any],
        task_progress: Dict[str, Any],
    ) -> Optional[CompanionResponse]:
        """综合评估是否需要陪伴响应，【需要实现】"""
        pass

    async def celebrate_milestone(
        self, milestone_type: str, details: str
    ) -> CompanionResponse:
        """庆祝里程碑完成，【需要实现】"""
        pass

    def should_suggest_rest(self) -> bool:
        """判断是否应建议休息，【需要实现】"""
        pass

    async def _analyze_message_tone(self, message: str) -> Dict[str, Any]:
        """轻量级消息语气分析，【需要实现】不调用 LLM"""
        pass

    def _get_session_duration_minutes(self) -> int:
        """计算当前会话时长，【需要实现】"""
        pass
