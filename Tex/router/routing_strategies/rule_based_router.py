# ============================================================
# router/routing_strategies/rule_based_router.py
# RuleBasedRouter —— 基于规则的确定性路由策略
# ============================================================
# RuleBasedRouter 使用预定义的规则进行快速确定性路由，
# 作为系统的保底路由策略（总是有结果，不依赖 LLM）。
# 规则优先级高于 ML 路由，确保系统的可预期性。
#
# 【需要实现的内容】
#
# 1. RoutingRule — 路由规则
#    字段:
#    - rule_id: str
#    - name: str
#    - condition: Callable[[str, dict], bool]   # 条件判断函数
#    - target_agent_type: str
#    - target_model: str
#    - priority: int                             # 规则优先级（越小越高）
#    - description: str
#
# 2. RuleBasedRouter 类
#
#    内置路由规则（按优先级排序）:
#    P1: 包含 LaTeX 内容 + 有编译错误 -> LaTeXAgent + fast_model
#    P2: 包含 "检索"/"文献"/"arXiv" -> LiteratureAgent + standard_model
#    P3: 包含 ".csv"/"数据集"/"统计分析" -> AnalysisAgent + standard_model
#    P4: 包含 "图表"/"可视化" -> VisualizationAgent + fast_model
#    P5: 包含 "生成图"/"DALL-E" -> ImageGenAgent + standard_model
#    P6: 包含 "难受"/"焦虑"/"压力" -> CompanionAgent + warm_model
#    P7: 复杂度 > 0.8 -> PlannerAgent + premium_model
#    P8: 默认 -> SimpleAgent + fast_model
#
#    核心方法:
#
#    route(task: str, context: dict) -> RouteDecision:
#    - 按优先级顺序匹配规则
#    - 返回第一个匹配规则的路由决策
#    - 如所有规则都不匹配，返回默认路由（P8）
#
#    add_rule(rule: RoutingRule) -> None:
#    - 动态添加路由规则
#    - 按优先级插入到正确位置
#
#    remove_rule(rule_id: str) -> bool:
#    - 移除路由规则
#
#    list_rules() -> list[RoutingRule]:
#    - 返回所有规则（按优先级排序）
# ============================================================

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from agents.meta.router_agent import RouteDecision


@dataclass
class RoutingRule:
    """路由规则，【实现字段见上方注释】"""
    rule_id: str = ""
    name: str = ""
    condition: Optional[Callable] = None
    target_agent_type: str = "simple"
    target_model: str = ""
    priority: int = 99
    description: str = ""


class RuleBasedRouter:
    """
    基于规则的确定性路由策略。
    快速可靠，作为系统保底路由。
    【完整实现规范见上方注释】
    """

    def __init__(self) -> None:
        self._rules: List[RoutingRule] = []
        self._load_builtin_rules()

    def _load_builtin_rules(self) -> None:
        """加载内置路由规则，【需要实现】"""
        pass

    def route(
        self, task: str, context: Optional[Dict[str, Any]] = None
    ) -> RouteDecision:
        """按规则路由，【需要实现】"""
        pass

    def add_rule(self, rule: RoutingRule) -> None:
        """动态添加规则，【需要实现】"""
        pass

    def remove_rule(self, rule_id: str) -> bool:
        """移除规则，【需要实现】"""
        pass

    def list_rules(self) -> List[RoutingRule]:
        """列出所有规则，【需要实现】"""
        return sorted(self._rules, key=lambda r: r.priority)
