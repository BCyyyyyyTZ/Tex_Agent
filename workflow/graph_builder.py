"""
LangGraph 图构建器（v2 Breaking Change）。

Breaking Change v2：
  - 条件边真正使用 add_conditional_edges（废弃"降级为线性边"行为）
  - 并行分叉通过多条 add_edge 实现 fan-out（LangGraph 超步并行）
  - parallel_fork / parallel_join 节点类型正式支持
  - 边按 from_node 分组后分类处理：单边 / 条件路由 / 并行分叉
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from langgraph.graph import StateGraph, START, END

from core.state import WorkflowState
from context.context_manager import ContextManager
from config.planner_config import DEFAULT_HISTORY_MODE
from utils.logger import get_logger
from workflow.condition_evaluator import route_by_conditions
from workflow.workflow_parser import EdgeConfig, NodeConfig

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# 内部辅助
# ---------------------------------------------------------------------------

def _resolve_entry_node(node_ids: list, edges: list) -> str:
    """推断入口节点（无入边节点优先）。"""
    target_nodes = {e.to_node for e in edges}
    entry_candidates = [nid for nid in node_ids if nid not in target_nodes]
    return entry_candidates[0] if entry_candidates else node_ids[0]


def _resolve_terminal_nodes(node_ids: list, edges: list) -> set:
    """推断汇节点（无出边节点）。"""
    terminal = set(node_ids)
    for edge_cfg in edges:
        terminal.discard(edge_cfg.from_node)
    return terminal


def load_workflow_graph_config(workflow_name: str = "default") -> Tuple[list, list]:
    """从 workflow registry 加载指定工作流的节点与边配置。"""
    from workflow.workflow_registry import WorkflowRegistry
    registry = WorkflowRegistry()
    return registry.load_graph_config(workflow_name)


# ---------------------------------------------------------------------------
# Agent / Tool 实例化
# ---------------------------------------------------------------------------

def _build_agent_instance(agent_type: str, node_id: str, node_config: dict):
    """根据 agent_type 实例化对应 Agent。"""
    from agents.simple_agent import SimpleAgent as _SimpleAgent
    from config.planner_config import AGENT_TYPE_NAMES, NODE_DEFAULT_TEMPERATURE

    system_prompt = node_config.get("system_prompt", f"你是 {node_id} 专家。")
    temperature = float(node_config.get("temperature", NODE_DEFAULT_TEMPERATURE))

    alias = str(agent_type or "").strip() or "SimpleAgent"
    if alias not in AGENT_TYPE_NAMES:
        logger.warning(f"[DynamicGraph] 未知 Agent 类型 '{alias}'，降级为 SimpleAgent")
    elif alias not in ("SimpleAgent", "SimpleAgent_new"):
        logger.warning(f"[DynamicGraph] '{alias}' 尚未实现，降级为 SimpleAgent")

    return _SimpleAgent(
        name=node_id,
        system_prompt=system_prompt,
        temperature=temperature,
        tools=[],
    )


def _build_tool_instance(tool_name: str, node_id: str):
    """根据 tool_name 获取工具实例。"""
    from tools.tool_list import tool_list

    for tool in tool_list:
        if getattr(tool, "name", "") == tool_name:
            return tool

    raise ValueError(
        f"[DynamicGraph] 节点 '{node_id}' 指定的工具 '{tool_name}' 未注册，"
        "请先在 tools/tool_list.py 中添加该工具实例。"
    )


# ---------------------------------------------------------------------------
# 条件边注册
# ---------------------------------------------------------------------------

def _register_conditional_edges(
    graph: StateGraph,
    from_node: str,
    edges: List[EdgeConfig],
) -> None:
    """
    为 from_node 注册条件路由边。

    - 带 condition 的边按 priority 降序评估
    - 无 condition 的边作为 fallback
    - 若无显式 fallback，使用 END 作为默认目标

    Breaking Change v2：真正使用 add_conditional_edges，不再降级为 add_edge。
    """
    conditional = [e for e in edges if e.condition is not None]
    fallbacks = [e for e in edges if e.condition is None]

    if not conditional:
        raise ValueError(
            f"[DynamicGraph] _register_conditional_edges 调用时 "
            f"from_node={from_node!r} 没有带条件的边"
        )

    fallback_target = fallbacks[0].to_node if fallbacks else END

    # 构建路由映射：label → node_id
    # label 与 node_id 直接同名，简化配置
    routing_map: Dict[str, str] = {}
    for edge in conditional:
        routing_map[edge.to_node] = edge.to_node
    routing_map[str(fallback_target)] = str(fallback_target)

    def router_fn(state: WorkflowState) -> str:
        return route_by_conditions(state, edges, str(fallback_target))

    graph.add_conditional_edges(from_node, router_fn, routing_map)

    logger.info(
        f"[DynamicGraph] 条件边注册: {from_node} → "
        f"条件目标={[e.to_node for e in conditional]}, "
        f"fallback={fallback_target}"
    )


# ---------------------------------------------------------------------------
# 主构图函数
# ---------------------------------------------------------------------------

def build_dynamic_graph(
    nodes: List[NodeConfig],
    edges: List[EdgeConfig],
    context_manager: Optional[ContextManager] = None,
    persona_memory: Optional[Any] = None,
    runtime_memory: Optional[Any] = None,
    default_workflow_name: str = "default",
    default_history_mode: Optional[str] = None,
    human_input_provider: Optional[Any] = None,
) -> Any:
    """
    根据 NodeConfig / EdgeConfig 列表动态构建并编译 LangGraph 图。

    Edge 分类处理（Breaking Change v2）：
      - 按 from_node 分组后：
        * 只有一条且无 condition → add_edge（普通线性边）
        * 多条且全无 condition → 多次 add_edge（并行分叉 fan-out）
        * 任意一条有 condition → add_conditional_edges（真条件路由，不再降级）

    节点类型处理：
      - agent            → make_agent_node
      - tool             → make_tool_node
      - user             → make_user_node
      - parallel_fork    → make_parallel_fork_node（轻量分叉标记）
      - parallel_join    → make_parallel_join_node（汇聚 + agent 整合）

    Returns:
        已编译的 LangGraph CompiledGraph，支持 .invoke() / .ainvoke()。
    """
    from workflow.nodes import (
        make_agent_node,
        make_tool_node,
        make_user_node,
        make_parallel_fork_node,
        make_parallel_join_node,
    )

    eff_history_mode = (
        default_history_mode if default_history_mode is not None else DEFAULT_HISTORY_MODE
    )

    # 兜底：nodes 为空时退回 default workflow 配置图
    if not nodes:
        logger.warning("[DynamicGraph] NodeConfig 为空，回退到 default workflow 配置图")
        fallback_nodes, fallback_edges = load_workflow_graph_config(default_workflow_name)
        if not fallback_nodes:
            raise ValueError("default workflow 节点配置为空，无法构图")
        nodes = fallback_nodes
        edges = fallback_edges

    node_ids = [n.node_id for n in nodes]
    logger.info(f"[DynamicGraph] 构建动态图，节点: {node_ids}")

    ctx = context_manager if context_manager is not None else ContextManager(default_limit=20)
    graph = StateGraph(WorkflowState)

    terminal_nodes = _resolve_terminal_nodes(node_ids, edges)
    entry_node = _resolve_entry_node(node_ids, edges)
    logger.debug(f"[DynamicGraph] 入口节点: {entry_node}，汇节点: {terminal_nodes}")

    # ---- 注册节点 ----
    for node_cfg in nodes:
        nid = node_cfg.node_id
        node_type = (getattr(node_cfg, "node_type", "agent") or "agent").strip().lower()

        if node_type == "tool":
            if not node_cfg.tool_name:
                raise ValueError(f"[DynamicGraph] 工具节点 '{nid}' 缺少 tool_name 配置")
            tool = _build_tool_instance(node_cfg.tool_name, nid)
            node_fn = make_tool_node(
                tool=tool,
                ctx=ctx,
                node_id=nid,
                node_config=node_cfg.config,
                default_history_mode=eff_history_mode,
                is_terminal=nid in terminal_nodes,
            )
            graph.add_node(nid, node_fn)
            logger.debug(f"[DynamicGraph] 注册工具节点: {nid} ({node_cfg.tool_name})")
            continue

        if node_type == "user":
            node_fn = make_user_node(
                node_id=nid,
                node_config=node_cfg.config,
                human_input_provider=human_input_provider,
            )
            graph.add_node(nid, node_fn)
            logger.debug(f"[DynamicGraph] 注册用户节点: {nid}")
            continue

        if node_type == "parallel_fork":
            branches = node_cfg.parallel_branches
            if not branches:
                # 尝试从边推断（所有从此节点出发的目标节点）
                branches = [e.to_node for e in edges if e.from_node == nid]
                logger.warning(
                    f"[DynamicGraph] parallel_fork 节点 '{nid}' 未指定 parallel_branches，"
                    f"从边推断: {branches}"
                )
            node_fn = make_parallel_fork_node(node_id=nid, parallel_branches=branches)
            graph.add_node(nid, node_fn)
            logger.debug(f"[DynamicGraph] 注册并行分叉节点: {nid} → {branches}")
            continue

        if node_type == "parallel_join":
            src_branches = node_cfg.source_branches
            if not src_branches:
                # 尝试从边推断（所有指向此节点的源节点）
                src_branches = [e.from_node for e in edges if e.to_node == nid]
                logger.warning(
                    f"[DynamicGraph] parallel_join 节点 '{nid}' 未指定 source_branches，"
                    f"从边推断: {src_branches}"
                )
            agent = _build_agent_instance(
                node_cfg.agent_name or "SimpleAgent", nid, node_cfg.config
            )
            node_fn = make_parallel_join_node(
                agent=agent,
                ctx=ctx,
                node_id=nid,
                node_config=node_cfg.config,
                source_branches=src_branches,
                join_policy_str=node_cfg.join_policy,
                persona_memory=persona_memory,
                runtime_memory=runtime_memory,
                default_history_mode=eff_history_mode,
                is_terminal=nid in terminal_nodes,
            )
            graph.add_node(nid, node_fn)
            logger.debug(
                f"[DynamicGraph] 注册并行汇聚节点: {nid} "
                f"(sources={src_branches}, policy={node_cfg.join_policy})"
            )
            continue

        # 默认: agent（包含未知 node_type）
        if node_type not in ("agent",):
            logger.warning(
                f"[DynamicGraph] 节点 '{nid}' 的 node_type='{node_type}' 不受支持，降级为 agent"
            )
        agent = _build_agent_instance(node_cfg.agent_name, nid, node_cfg.config)
        node_fn = make_agent_node(
            agent=agent,
            ctx=ctx,
            node_id=nid,
            node_config=node_cfg.config,
            persona_memory=persona_memory,
            runtime_memory=runtime_memory,
            default_history_mode=eff_history_mode,
            is_terminal=nid in terminal_nodes,
            is_entry_node=nid == entry_node,
        )
        graph.add_node(nid, node_fn)
        logger.debug(f"[DynamicGraph] 注册 agent 节点: {nid} ({node_cfg.agent_name})")

    graph.add_edge(START, entry_node)

    # ---- 注册边（Breaking Change v2：真正分类处理） ----
    # 过滤非法边
    valid_edges: List[EdgeConfig] = []
    for edge_cfg in edges:
        if edge_cfg.from_node not in node_ids or edge_cfg.to_node not in node_ids:
            logger.warning(
                f"[DynamicGraph] 跳过非法边 {edge_cfg.from_node} → {edge_cfg.to_node}"
                f"（节点不存在）"
            )
            continue
        valid_edges.append(edge_cfg)

    # 按 from_node 分组
    edges_by_from: Dict[str, List[EdgeConfig]] = defaultdict(list)
    for edge_cfg in valid_edges:
        edges_by_from[edge_cfg.from_node].append(edge_cfg)

    for from_node, group in edges_by_from.items():
        has_conditions = any(e.condition is not None for e in group)

        if has_conditions:
            # 条件路由：add_conditional_edges（Breaking Change: 不再降级）
            _register_conditional_edges(graph, from_node, group)

        elif len(group) == 1:
            # 普通单边
            graph.add_edge(from_node, group[0].to_node)
            logger.debug(f"[DynamicGraph] 普通边: {from_node} → {group[0].to_node}")

        else:
            # 并行分叉（多条无条件边 fan-out）
            for edge_cfg in group:
                graph.add_edge(from_node, edge_cfg.to_node)
            logger.info(
                f"[DynamicGraph] 并行分叉边: {from_node} → "
                f"{[e.to_node for e in group]}（fan-out）"
            )

    # ---- 末端节点连接 END ----
    for terminal in terminal_nodes:
        graph.add_edge(terminal, END)
        logger.debug(f"[DynamicGraph] 终止边: {terminal} → END")

    app = graph.compile()
    logger.info(
        f"[DynamicGraph] 图编译完成: {len(nodes)} 节点 / {len(valid_edges)} 条边"
    )
    return app


# ---------------------------------------------------------------------------
# 对外统一入口
# ---------------------------------------------------------------------------

def build_app_from_workflow(
    workflow_name: str = "default",
    context_manager: Optional[ContextManager] = None,
    persona_memory: Optional[Any] = None,
    runtime_memory: Optional[Any] = None,
    default_history_mode: Optional[str] = None,
    human_input_provider: Optional[Any] = None,
    config_dict: Optional[Dict[str, Any]] = None,
) -> Any:
    """
    统一的工作流构建入口。

    - 若传入 ``config_dict``（含 ``nodes`` / ``edges``），从内存 JSON 解析，不再读注册表文件。
    - 否则按 ``workflow_name`` 从 ``workflow_registry.json`` 加载文件。
    """
    if config_dict is not None:
        from workflow.workflow_parser import YAMLWorkflowParser

        parser = YAMLWorkflowParser()
        nodes = parser.parse_nodes(config_dict)
        edges = parser.parse_edges(config_dict)
    else:
        nodes, edges = load_workflow_graph_config(workflow_name)
    return build_dynamic_graph(
        nodes=nodes,
        edges=edges,
        context_manager=context_manager,
        persona_memory=persona_memory,
        runtime_memory=runtime_memory,
        default_workflow_name=workflow_name,
        default_history_mode=default_history_mode,
        human_input_provider=human_input_provider,
    )
