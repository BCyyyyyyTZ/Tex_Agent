# workflow/graph_builder.py - 修复版本

"""
LangGraph 图构建器（可运行）。
负责创建、配置并编译 TeX_Agent 的动态工作流图。
所有入口（default、自定义 workflow、plan）最终都通过配置生成 nodes/edges，
并由 build_dynamic_graph() 构建可执行图。
"""
from typing import Optional, Any, Tuple

from langgraph.graph import StateGraph, START, END

from core.state import WorkflowState
from context.context_manager import ContextManager
from utils.logger import get_logger

logger = get_logger(__name__)


def load_workflow_graph_config(workflow_name: str = "default") -> Tuple[list, list]:
    """
    从 workflow registry 加载指定工作流的节点与边配置。
    """
    from workflow.workflow_registry import WorkflowRegistry

    registry = WorkflowRegistry()
    return registry.load_graph_config(workflow_name)


def build_app_from_workflow(
    workflow_name: str = "default",
    context_manager: Optional[ContextManager] = None,
    shared_memory: Optional[Any] = None,
) -> Any:
    """
    统一的工作流构建入口：所有 workflow（默认/自定义）均走 dynamic graph。
    """
    nodes, edges = load_workflow_graph_config(workflow_name)
    return build_dynamic_graph(
        nodes=nodes,
        edges=edges,
        context_manager=context_manager,
        shared_memory=shared_memory,
        default_workflow_name=workflow_name,
    )


# ============================================================
# 动态图构建器（供 MASPlanner + WorkflowParser 使用）
# ============================================================

def _build_agent_instance(agent_type: str, node_id: str, node_config: dict):
    """
    根据 agent_type 实例化对应 Agent。

    [BaseRouter 预留接口] 当 ReActAgent / PlanAndSolveAgent 实现后，
    在 config/planner_config.py 的 AGENT_TYPE_NAMES 中添加名称，
    并在此函数中补充对应分支即可激活，无需修改其他代码。

    Args:
        agent_type:  来自 NodeConfig.agent_name 的 Agent 类型字符串。
        node_id:     节点 ID（用于 agent.name 和日志）。
        node_config: NodeConfig.config 字典（含 system_prompt / temperature）。

    Returns:
        已实例化的 BaseAgent。
    """
    from agents.simple_agent import SimpleAgent as _SimpleAgent
    from config.planner_config import AGENT_TYPE_NAMES, NODE_DEFAULT_TEMPERATURE

    system_prompt = node_config.get("system_prompt", f"你是 {node_id} 专家。")
    temperature   = float(node_config.get("temperature", NODE_DEFAULT_TEMPERATURE))

    if agent_type not in AGENT_TYPE_NAMES:
        logger.warning(f"[DynamicGraph] 未知 Agent 类型 '{agent_type}'，降级为 SimpleAgent")
    elif agent_type != "SimpleAgent":
        # 此处预留：当 ReActAgent / PlanAndSolveAgent 实现后，补充 elif 分支
        logger.warning(f"[DynamicGraph] '{agent_type}' 尚未实现，降级为 SimpleAgent")

    return _SimpleAgent(
        name=node_id,
        system_prompt=system_prompt,
        temperature=temperature,
    )


def build_dynamic_graph(
    nodes: list,
    edges: list,
    context_manager: Optional[ContextManager] = None,
    shared_memory: Optional[Any] = None,
    default_workflow_name: str = "default",
) -> Any:
    """
    根据 NodeConfig / EdgeConfig 列表动态构建并编译 LangGraph 图。

    这是 MASPlanner → WorkflowParser → 可执行 app 调用链的最终环节。
    所有 workflow（default/file/plan）最终都汇聚到本函数。

    兜底策略：
      若 nodes 为空（规划失败），回退到 default workflow 的配置图。

    Args:
        nodes:           NodeConfig 对象列表（来自 MASPlanner.to_graph_config()
                         或 YAMLWorkflowParser.parse_nodes()）。
        edges:           EdgeConfig 对象列表（同上）。
        context_manager: 共享上下文管理器，None 时自动创建。
        shared_memory:   共享长期记忆实例（可选，注入每个通用节点）。

    Returns:
        已编译的 LangGraph CompiledGraph，支持 .invoke() / .ainvoke()。
    """
    from workflow.nodes import make_generic_agent_node

    # 兜底：nodes 为空时退回 default workflow 配置图
    if not nodes:
        logger.warning("[DynamicGraph] NodeConfig 为空，回退到 default workflow 配置图")
        fallback_nodes, fallback_edges = load_workflow_graph_config(default_workflow_name)
        if not fallback_nodes:
            raise ValueError("default workflow 节点配置为空，无法构图")
        nodes = fallback_nodes
        edges = fallback_edges

    node_ids = [n.node_id for n in nodes]
    logger.info(f"[DynamicGraph] 构建动态图，节点：{node_ids}")

    ctx = context_manager if context_manager is not None else ContextManager(default_limit=20)

    graph = StateGraph(WorkflowState)

    # ---- 注册节点 ----
    for node_cfg in nodes:
        agent = _build_agent_instance(node_cfg.agent_name, node_cfg.node_id, node_cfg.config)
        node_fn = make_generic_agent_node(
            agent=agent,
            ctx=ctx,
            node_id=node_cfg.node_id,
            node_config=node_cfg.config,
            memory=shared_memory,
        )
        graph.add_node(node_cfg.node_id, node_fn)
        logger.debug(f"[DynamicGraph] 注册节点: {node_cfg.node_id} ({node_cfg.agent_name})")

    # ---- 确定入口节点 ----
    # 入口为没有任何边指向它的节点（拓扑源头），或直接取第一个节点
    target_nodes = {e.to_node for e in edges}
    entry_candidates = [n.node_id for n in nodes if n.node_id not in target_nodes]
    entry_node = entry_candidates[0] if entry_candidates else nodes[0].node_id
    graph.add_edge(START, entry_node)
    logger.debug(f"[DynamicGraph] 入口节点: {entry_node}")

    # ---- 注册边 ----
    terminal_nodes = set(node_ids)
    for edge_cfg in edges:
        if edge_cfg.condition is None:
            graph.add_edge(edge_cfg.from_node, edge_cfg.to_node)
        else:
            # 条件边：condition 字符串暂存为注释，待 make_conditional_router 实现后激活
            logger.warning(
                f"[DynamicGraph] 条件边 {edge_cfg.from_node}→{edge_cfg.to_node} "
                f"(condition='{edge_cfg.condition}') 当前降级为线性边，"
                f"待 make_conditional_router 实现后激活"
            )
            graph.add_edge(edge_cfg.from_node, edge_cfg.to_node)
        terminal_nodes.discard(edge_cfg.from_node)

    # ---- 末端节点连接 END ----
    for terminal in terminal_nodes:
        graph.add_edge(terminal, END)
        logger.debug(f"[DynamicGraph] 终止边: {terminal} → END")

    app = graph.compile()
    logger.info(f"[DynamicGraph] 动态图构建完成，共 {len(nodes)} 节点，{len(edges)} 条边")
    return app