# ============================================================
# agents/__init__.py
# 智能体模块统一入口
# ============================================================
# 导出所有 Agent 类，便于外部模块直接 import
# ============================================================

from agents.base.simple_agent import SimpleAgent
from agents.base.react_agent import ReActAgent
from agents.base.reflection_agent import ReflectionAgent
from agents.base.plan_and_solve_agent import PlanAndSolveAgent

from agents.specialized.literature_agent import LiteratureAgent
from agents.specialized.analysis_agent import AnalysisAgent
from agents.specialized.latex_agent import LaTeXAgent
from agents.specialized.visualization_agent import VisualizationAgent
from agents.specialized.writing_agent import WritingAgent
from agents.specialized.image_gen_agent import ImageGenAgent
from agents.specialized.companion_agent import CompanionAgent

from agents.orchestrator.planner_agent import PlannerAgent
from agents.orchestrator.executor_coordinator import ExecutorCoordinator
from agents.orchestrator.result_aggregator import ResultAggregator

from agents.meta.router_agent import RouterAgent
from agents.meta.evaluator_agent import EvaluatorAgent
from agents.meta.monitor_agent import MonitorAgent

__all__ = [
    "SimpleAgent", "ReActAgent", "ReflectionAgent", "PlanAndSolveAgent",
    "LiteratureAgent", "AnalysisAgent", "LaTeXAgent", "VisualizationAgent",
    "WritingAgent", "ImageGenAgent", "CompanionAgent",
    "PlannerAgent", "ExecutorCoordinator", "ResultAggregator",
    "RouterAgent", "EvaluatorAgent", "MonitorAgent",
]
