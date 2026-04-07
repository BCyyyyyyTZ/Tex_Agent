"""
工作流边定义（可运行）。
包含基础线性边的添加逻辑，以及 [扩展] 条件边路由接口的占位定义。
"""
from typing import Callable, Dict, Optional

from langgraph.graph import StateGraph, END

from core.state import WorkflowState
from config.workflow_config import WORKFLOW_EDGES, FINISH_NODE
from utils.logger import get_logger

logger = get_logger(__name__)


def add_linear_edges(graph: StateGraph) -> None:
    """
    向图中添加线性边（Design → Think → Execute → END）。

    读取 config/workflow_config.py 中定义的 WORKFLOW_EDGES，
    依次为每对节点添加有向边，并将终止节点连接到 END。

    Args:
        graph: 已注册了所有节点的 LangGraph StateGraph 实例。
    """
    for from_node, to_node in WORKFLOW_EDGES:
        graph.add_edge(from_node, to_node)
        logger.debug(f"添加线性边: {from_node} → {to_node}")

    graph.add_edge(FINISH_NODE, END)
    logger.debug(f"添加终止边: {FINISH_NODE} → END")


# ============================================================
# [扩展] 条件边路由接口（占位）
# ============================================================

def make_conditional_router(
    conditions: Optional[Dict[str, Callable[[WorkflowState], bool]]] = None,
) -> Callable[[WorkflowState], str]:
    """
    [扩展] 创建条件路由函数，用于 graph.add_conditional_edges()。

    条件路由函数接收当前 WorkflowState，返回下一个节点的名称字符串，
    LangGraph 据此动态决定工作流走向（分支、循环、跳过等）。

    Args:
        conditions: 条件字典，键为节点名（str），
                    值为判断函数（WorkflowState -> bool）。
                    函数按字典顺序依次求值，第一个返回 True 的节点名胜出。

    Returns:
        符合 LangGraph 规范的路由函数（WorkflowState -> str）。

    Raises:
        NotImplementedError: 此函数尚未实现，仅作接口占位。

    Usage Example（实现后）：
        router = make_conditional_router({
            "design": lambda s: s.get("error") is not None,  # 出错则重新设计
            "think":  lambda s: s.get("error") is None,      # 正常则进入思考
        })
        graph.add_conditional_edges(
            "design",
            router,
            {"design": "design", "think": "think"},
        )

    TODO: 开发者 A 在此实现条件分支路由逻辑，可结合以下策略：
          1. 错误重试：执行失败时回退到上一节点
          2. 质量门控：输出质量不达标时触发 ReflectionAgent 循环
          3. 复杂度分流：根据 Router.evaluate_complexity() 选择执行路径
    """
    raise NotImplementedError(
        "make_conditional_router() 尚未实现。\n"
        "请参考函数文档实现条件分支路由逻辑，"
        "用于动态决定工作流走向（分支/循环/跳过）。"
    )
