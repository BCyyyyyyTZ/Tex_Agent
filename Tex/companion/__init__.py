# companion/__init__.py — 情感陪伴模块入口
from companion.emotion_detector import EmotionDetector, EmotionState, EmotionSignal
from companion.encouragement_generator import EncouragementGenerator, ResponseStyle, EncouragementResponse
from companion.wellbeing_tracker import WellbeingTracker, WellbeingRecord

__all__ = [
    "EmotionDetector", "EmotionState", "EmotionSignal",
    "EncouragementGenerator", "ResponseStyle", "EncouragementResponse",
    "WellbeingTracker", "WellbeingRecord",
]
