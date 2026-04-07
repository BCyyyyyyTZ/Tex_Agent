# ============================================================
# agents/meta/router_agent.py
# RouterAgent —— 智能任务路由决策元智能体
# ============================================================
# RouterAgent 是一个特殊的元级 Agent，它的职责是"决定由谁来做"，
# 而不是自己直接完成任务。它分析任务的类型、复杂度和上下文，
# 选择最合适的 Agent 模型和配置来执行。
#
# 与 router/ 目录下的路由模块区别：
# - router/ 模块：纯算法路由（规则/ML/自适应），无 LLM 推理
# - RouterAgent: 具有 LLM 推理能力的智能路由，处理复杂/模糊情况
#
# 【需要实现的内容】
#
# 1. RouteDecision — 路由决策结果
#    字段:
#    - target_agent_type: str         # 目标 Agent 类型
#    - target_model: str              # 建议使用的 LLM 模型
#    - confidence: float              # 路由决策置信度
#    - reasoning: str                 # 路由理由说明
#    - fallback_agent_type: str       # 备选 Agent 类型
#    - estimated_difficulty: str      # 任务难度估计（easy/medium/hard）
#    - requires_tools: list[str]      # 需要的工具列表
#    - requires_rag: bool             # 是否需要 RAG 检索
#    - requires_memory: bool          # 是否需要长期记忆
#    - estimated_tokens: int          # 预估 token 消耗
#
# 2. RouterAgent 类（继承 SimpleAgent）
#    agent_type = "router"
#
#    核心方法:
#
#    async route(
#        task_description: str,
#        user_context: dict,
#        available_agents: list[str]
#    ) -> RouteDecision:
#    - 综合分析任务，给出路由决策
#    - 调用 LLM（使用轻量级快速模型）输出 JSON 格式决策
#    - 结合规则路由作为底线保障
#    - 记录路由历史（用于自适应学习）
#
#    async route_with_intent(
#        user_message: str,
#        history: list,
#        system_context: dict
#    ) -> RouteDecision:
#    - 更完整的路由，考虑对话历史和系统当前状态
#    - 识别用户的实际意图（不一定是字面意思）
#    - 例如："帮我看看这篇文章" -> 根据文件类型路由到 LaTeXAgent 或其他
#
#    async should_use_planner(task_description: str) -> bool:
#    - 判断任务是否复杂到需要 Planner 分解
#    - 简单任务直接路由，复杂任务走 Planner
#    - 阈值：通常 2 个以上不同领域的 Agent 才走 Planner
#
#    async estimate_task_difficulty(task_description: str) -> dict:
#    - 估算任务的各维度难度
#    - 返回：{"overall": "medium", "reasoning_complexity": 0.7, ...}
#
#    _build_routing_prompt(task, agents, context) -> str:
#    - 构建路由决策专用提示词
#    - 列出所有可用 Agent 的能力描述
#    - 要求 LLM 输出结构化的路由决策 JSON
#
#    _validate_route_decision(decision: RouteDecision) -> bool:
#    - 验证路由决策的合法性
#    - 检查目标 Agent 是否存在且可用
#    - 检查必要工具是否都已注册
# ============================================================

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from agents.base.simple_agent import SimpleAgent
from core.base_agent import AgentResult, TaskContext


@dataclass
class RouteDecision:
    """路由决策结果，【实现字段见上方注释】"""
    target_agent_type: str = ""
    target_model: str = ""
    confidence: float = 0.0
    reasoning: str = ""
    fallback_agent_type: str = "simple"
    estimated_difficulty: str = "medium"
    requires_tools: List[str] = field(default_factory=list)
    requires_rag: bool = False
    requires_memory: bool = False
    estimated_tokens: int = 1000


class RouterAgent(SimpleAgent):
    """
    智能任务路由决策元 Agent。
    基底节（路由与分发）的 AI 实现。
    【完整实现规范见上方注释】
    """

    agent_type: str = "router"
    version: str = "1.0.0"

    def __init__(
        self,
        name: str = "RouterAgent",
        config: Optional[Any] = None,
    ) -> None:
        super().__init__(name=name, config=config)
        self._routing_history: List[Dict[str, Any]] = []
        self.fast_model: str = ""  # 路由决策使用轻量模型，减少延迟

    async def route(
        self,
        task_description: str,
        user_context: Dict[str, Any],
        available_agents: List[str],
    ) -> RouteDecision:
        """分析任务并给出路由决策，【需要实现】"""
        pass

    async def route_with_intent(
        self,
        user_message: str,
        history: List[Any],
        system_context: Dict[str, Any],
    ) -> RouteDecision:
        """基于意图识别的完整路由，【需要实现】"""
        pass

    async def should_use_planner(self, task_description: str) -> bool:
        """判断是否需要 Planner 分解，【需要实现】"""
        pass

    async def estimate_task_difficulty(
        self, task_description: str
    ) -> Dict[str, Any]:
        """估算任务难度，【需要实现】"""
        pass

    def _build_routing_prompt(
        self,
        task: str,
        agents: List[str],
        context: Dict[str, Any],
    ) -> str:
        """构建路由决策提示词，【需要实现】"""
        pass

    def _validate_route_decision(self, decision: RouteDecision) -> bool:
        """验证路由决策合法性，【需要实现】"""
        pass
