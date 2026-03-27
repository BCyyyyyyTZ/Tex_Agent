# ============================================================
# companion/wellbeing_tracker.py — 用户健康状态追踪器
# ============================================================
# 持续追踪用户在科研写作过程中的心理健康状态，
# 检测长期负面情绪趋势，及时给出健康提醒。
#
# 核心内容:
# - WellbeingRecord: 每次对话的健康状态记录
# - WellbeingTracker:
#   - record(session_id, emotion_signal) -> None: 记录情绪状态
#   - get_trend(user_id, days=7) -> dict: 分析近期情绪趋势
#   - check_burnout_risk(user_id) -> float: 评估倦怠风险（0-1）
#   - should_intervene(user_id) -> bool: 判断是否需要主动干预
#   - get_health_report(user_id) -> str: 生成健康状态报告
# ============================================================

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class WellbeingRecord:
    session_id: str = ""
    user_id: str = ""
    emotion_state: str = "neutral"
    intensity: float = 0.0
    session_duration_min: float = 0.0
    recorded_at: datetime = field(default_factory=datetime.now)


class WellbeingTracker:
    """
    用户心理健康状态追踪器。
    【需要实现】
    - record(session_id, user_id, emotion_signal, duration): 记录状态
    - get_trend(user_id, days): 分析情绪趋势
    - check_burnout_risk(user_id): 倦怠风险评估（基于近期负面情绪频率和强度）
    - should_intervene(user_id): 判断是否需要主动发起关怀对话
    - get_health_report(user_id): 生成周期性健康报告
    """

    def record(
        self,
        session_id: str,
        user_id: str,
        emotion_signal: Any,
        duration_min: float = 0.0,
    ) -> None:
        """记录健康状态，【需要实现】"""
        pass

    def get_trend(
        self, user_id: str, days: int = 7
    ) -> Dict[str, Any]:
        """分析近期情绪趋势，【需要实现】"""
        pass

    def check_burnout_risk(self, user_id: str) -> float:
        """评估倦怠风险，【需要实现】"""
        pass

    def should_intervene(self, user_id: str) -> bool:
        """判断是否需要主动干预，【需要实现】"""
        pass

    async def get_health_report(self, user_id: str) -> str:
        """生成健康状态报告，【需要实现】"""
        pass
