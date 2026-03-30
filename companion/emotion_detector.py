# ============================================================
# companion/emotion_detector.py — 情绪状态检测器
# ============================================================
# 分析用户文本消息，识别其情绪状态，为 CompanionAgent 提供
# 情绪感知能力。结合规则和 LLM 分析双重策略。
#
# 核心内容:
# - EmotionState: 枚举（neutral/anxious/frustrated/tired/happy/stuck/overwhelmed）
# - EmotionSignal: 检测结果（状态/置信度/触发词/强度/建议响应类型）
# - EmotionDetector:
#   - detect(message: str) -> EmotionSignal: 检测情绪
#   - detect_from_history(messages: list) -> EmotionSignal: 从历史趋势检测
#   - _rule_detect(): 关键词快速检测（焦虑/沮丧/疲劳相关词汇）
#   - _llm_detect(): LLM 精细情绪分析（规则置信度低时触发）
# ============================================================

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class EmotionState(str, Enum):
    NEUTRAL = "neutral"
    ANXIOUS = "anxious"           # 焦虑
    FRUSTRATED = "frustrated"     # 沮丧
    TIRED = "tired"               # 疲惫
    HAPPY = "happy"               # 愉快/有成就感
    STUCK = "stuck"               # 卡住了/不知道怎么办
    OVERWHELMED = "overwhelmed"   # 不堪重负


@dataclass
class EmotionSignal:
    state: EmotionState = EmotionState.NEUTRAL
    confidence: float = 0.0
    trigger_words: List[str] = field(default_factory=list)
    intensity: float = 0.0         # 0(轻微) - 1(强烈)
    suggested_response_type: str = "neutral"  # empathetic/encouraging/celebratory/rest


class EmotionDetector:
    """
    用户情绪状态检测器。
    【需要实现】
    - detect(message) -> EmotionSignal
    - detect_from_history(messages) -> EmotionSignal
    - _rule_detect(): 关键词规则检测
    - _llm_detect(): LLM 精细分析
    """

    ANXIETY_KEYWORDS = ["焦虑", "紧张", "担心", "害怕", "不安", "压力", "stressed", "anxious"]
    FRUSTRATION_KEYWORDS = ["沮丧", "失败", "不行", "放弃", "没用", "hate", "frustrated"]
    TIRED_KEYWORDS = ["累了", "疲惫", "困", "好累", "撑不住", "tired", "exhausted"]
    HAPPY_KEYWORDS = ["成功", "搞定", "太好了", "完成", "done", "excited", "great"]

    def detect(self, message: str) -> EmotionSignal:
        """检测单条消息的情绪，【需要实现】"""
        pass

    def detect_from_history(
        self, messages: List[Dict[str, Any]]
    ) -> EmotionSignal:
        """从对话历史趋势检测情绪，【需要实现】"""
        pass

    async def _llm_detect(
        self, message: str, initial: EmotionSignal
    ) -> EmotionSignal:
        """LLM 精细情绪分析，【需要实现】"""
        pass
