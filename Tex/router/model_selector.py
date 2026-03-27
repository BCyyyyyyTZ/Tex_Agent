# ============================================================
# router/model_selector.py
# ModelSelector —— LLM 模型智能选择器
# ============================================================
# ModelSelector 根据任务特性和系统状态，从可用模型中
# 选择最优的 LLM 模型，实现性能与成本的最优平衡。
#
# 【需要实现的内容】
#
# 1. ModelSelector 类
#
#    核心方法:
#
#    select(
#        task_category: TaskCategory,
#        complexity_score: ComplexityScore,
#        user_preference: str = "balanced",  # "quality"/"speed"/"economy"
#        required_capabilities: list = []
#    ) -> ModelConfig:
#    - 综合考虑任务类型、复杂度、用户偏好、能力要求
#    - 返回最优模型配置
#
#    select_for_role(
#        role: str   # "planner"/"executor"/"evaluator"/"router"/"companion"
#    ) -> ModelConfig:
#    - 为不同 Agent 角色选择最优模型
#    - Router: 轻量快速模型（gpt-4o-mini）
#    - Planner: 强推理模型（gpt-4o / claude）
#    - CompanionAgent: 情感温暖的模型
#
#    get_fallback(primary_model: str) -> ModelConfig:
#    - 当主模型不可用时，返回回退模型
#
#    estimate_cost(
#        model_id: str,
#        estimated_input_tokens: int,
#        estimated_output_tokens: int
#    ) -> float:
#    - 估算调用费用
#
#    check_availability(model_id: str) -> bool:
#    - 检查模型当前是否可用（API 健康状态）
# ============================================================

from __future__ import annotations

from typing import Any, Dict, List, Optional

from config.model_configs import ModelConfig


class ModelSelector:
    """
    LLM 模型智能选择器。
    根据任务需求和用户偏好优化模型选择策略。
    【完整实现规范见上方注释】
    """

    # 角色 -> 推荐模型映射
    ROLE_MODEL_MAP: Dict[str, str] = {
        "router": "gpt-4o-mini",
        "planner": "gpt-4o",
        "evaluator": "gpt-4o",
        "companion": "gpt-4o",
        "latex": "gpt-4o",
        "analysis": "gpt-4o",
        "writing": "gpt-4o",
    }

    def select(
        self,
        task_category: Any,
        complexity_score: Any,
        user_preference: str = "balanced",
        required_capabilities: Optional[List[str]] = None,
    ) -> Any:
        """智能选择最优模型，【需要实现】"""
        pass

    def select_for_role(self, role: str) -> Any:
        """按角色选择模型，【需要实现】"""
        pass

    def get_fallback(self, primary_model: str) -> Any:
        """获取回退模型，【需要实现】"""
        pass

    def estimate_cost(
        self,
        model_id: str,
        estimated_input_tokens: int,
        estimated_output_tokens: int,
    ) -> float:
        """估算调用费用，【需要实现】"""
        pass

    def check_availability(self, model_id: str) -> bool:
        """检查模型可用性，【需要实现】"""
        pass
