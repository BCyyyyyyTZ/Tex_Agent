# ============================================================
# companion/encouragement_generator.py — 鼓励/安慰内容生成器
# ============================================================
# 根据用户情绪状态和当前任务上下文，生成个性化的鼓励、
# 安慰或庆祝内容，避免机械化和空洞的回复。
#
# 核心内容:
# - ResponseStyle: 枚举（empathetic/encouraging/celebratory/practical/rest）
# - EncouragementResponse: 响应内容（正文/建议行动/表情符号/是否建议休息）
# - EncouragementGenerator:
#   - generate(emotion, context, style) -> EncouragementResponse
#   - celebrate_milestone(milestone_type, details) -> str: 庆祝里程碑
#   - suggest_rest(session_duration_min) -> Optional[str]: 建议休息
#   - _select_template(): 根据情绪和风格选择模板
#   - _personalize(): 根据用户档案个性化内容
# ============================================================

from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

from companion.emotion_detector import EmotionState


class ResponseStyle(str, Enum):
    EMPATHETIC = "empathetic"       # 同理心，侧重倾听和理解
    ENCOURAGING = "encouraging"     # 鼓励，侧重激励和信心
    CELEBRATORY = "celebratory"     # 庆祝成就
    PRACTICAL = "practical"         # 实际建议，解决问题导向
    REST = "rest"                   # 建议休息


@dataclass
class EncouragementResponse:
    message: str = ""
    action_suggestions: List[str] = None
    emoji: str = ""
    suggest_break: bool = False
    break_duration_minutes: int = 10
    style_used: str = ""

    def __post_init__(self):
        if self.action_suggestions is None:
            self.action_suggestions = []


class EncouragementGenerator:
    """
    情感陪伴内容生成器。
    【需要实现】
    - generate(emotion_signal, context, style) -> EncouragementResponse
    - celebrate_milestone(milestone_type, details) -> str
    - suggest_rest(session_duration_min) -> Optional[str]
    - _select_template(): 选择合适的响应模板
    - _personalize(template, user_profile): 个性化内容
    """

    async def generate(
        self,
        emotion_signal: Any,
        context: str = "",
        style: Optional[ResponseStyle] = None,
    ) -> EncouragementResponse:
        """生成鼓励/安慰内容，【需要实现】"""
        pass

    async def celebrate_milestone(
        self, milestone_type: str, details: str = ""
    ) -> str:
        """庆祝里程碑，【需要实现】"""
        pass

    def suggest_rest(
        self, session_duration_min: float
    ) -> Optional[str]:
        """根据用时建议休息，【需要实现】"""
        pass
