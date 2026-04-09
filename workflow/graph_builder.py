# workflow/graph_builder.py - 修复版本

"""
LangGraph 图构建器（可运行）。
负责创建、配置并编译 TeX_Agent 的工作流图。
这是整个系统的"装配车间"：将 Agent、Context、RAG 管道、节点和边组装成可执行的工作流。

工作流拓扑：
  不启用 RAG：START → Design → Think → Execute → END
  启用 RAG：   START → Design → Retrieve → Think → Execute → END
"""
from typing import TYPE_CHECKING, Optional, Any, Dict

from langgraph.graph import StateGraph, START, END

from core.state import WorkflowState
from agents.simple_agent import SimpleAgent
from context.context_manager import ContextManager
from workflow.nodes import make_design_node, make_think_node, make_execute_node, make_retrieve_node
from workflow.edges import add_linear_edges
from config.agent_config import DESIGN_AGENT_CONFIG, THINK_AGENT_CONFIG, EXECUTE_AGENT_CONFIG
from config.workflow_config import ENTRY_NODE
from utils.logger import get_logger

if TYPE_CHECKING:
    from rag.base_retriever import BaseRAGPipeline
    from memory.base_memory import BaseMemory

logger = get_logger(__name__)


def build_graph(
    context_manager: Optional[ContextManager] = None,
    rag_pipeline: Optional["BaseRAGPipeline"] = None,
    design_memory: Optional["BaseMemory"] = None,
    think_memory: Optional["BaseMemory"] = None,
    execute_memory: Optional["BaseMemory"] = None,
    shared_memory: Optional["BaseMemory"] = None,
) -> Any:
    """
    构建并编译 TeX_Agent LangGraph 工作流图。

    不启用 RAG（默认）：
        START → Design → Think → Execute → END

    启用 RAG（传入 rag_pipeline 参数）：
        START → Design → Retrieve → Think → Execute → END
        Retrieve 节点将检索结果写入 state["retrieved_context"]，
        Think 和 Execute 节点会自动将其注入 Prompt。

    Args:
        context_manager: 共享上下文管理器实例（BaseContext 接口）。
                         None 时自动创建新实例（max_messages=200）。
        rag_pipeline:    RAG 检索管道实例（BaseRAGPipeline 接口）。
                         None 表示不启用 RAG，工作流保持原有的三节点结构。
                         传入后在 Design 与 Think 节点之间插入 Retrieve 节点。
        design_memory:   Design 节点的长期记忆实例。
        think_memory:    Think 节点的长期记忆实例。
        execute_memory:  Execute 节点的长期记忆实例。
        shared_memory:   共享长期记忆实例（所有节点都可访问，优先级低于专属记忆）。

    Returns:
        已编译的 LangGraph CompiledGraph，支持：
        - app.invoke(initial_state)       - 同步执行
        - await app.ainvoke(initial_state) - 异步执行

    Example:
        # 不启用 RAG（原始工作流）
        app = build_graph()

        # 启用 RAG
        from rag.rag_pipeline import RAGPipeline
        pipeline = RAGPipeline()
        pipeline.index_file("papers/survey.md")
        app = build_graph(rag_pipeline=pipeline)

        # 使用记忆
        from memory.factory import MemoryFactory
        shared_mem = MemoryFactory.create_shared_memory()
        app = build_graph(shared_memory=shared_mem)

        result = app.invoke({
            "messages": [],
            "current_node": "",
            "input": "帮我检索 transformer 相关论文",
            "output": "",
            "error": None,
            "metadata": {},
            "retrieved_context": "",
        })
        print(result["output"])
    """
    rag_enabled = rag_pipeline is not None
    topology = "Design → Retrieve → Think → Execute" if rag_enabled else "Design → Think → Execute"
    logger.info(f"正在构建 TeX_Agent 工作流图... [拓扑: {topology}]")

    # ---- 创建共享上下文管理器 ----
    # 注意：必须用 `is not None` 而非 `or`，因为空的 ContextManager 的 len()==0
    # 会被 Python 视为 falsy，导致 `or` 错误地忽略调用者传入的实例。
    ctx = context_manager if context_manager is not None else ContextManager(default_limit=20)

    # ---- 创建各节点的 Agent 实例 ----
    design_agent = SimpleAgent(
        name=DESIGN_AGENT_CONFIG["name"],
        system_prompt=DESIGN_AGENT_CONFIG["system_prompt"],
        temperature=DESIGN_AGENT_CONFIG.get("temperature"),
    )
    think_agent = SimpleAgent(
        name=THINK_AGENT_CONFIG["name"],
        system_prompt=THINK_AGENT_CONFIG["system_prompt"],
        temperature=THINK_AGENT_CONFIG.get("temperature"),
    )
    execute_agent = SimpleAgent(
        name=EXECUTE_AGENT_CONFIG["name"],
        system_prompt=EXECUTE_AGENT_CONFIG["system_prompt"],
        temperature=EXECUTE_AGENT_CONFIG.get("temperature"),
    )

    # TODO: 未来在此处接入 BaseRouter，根据任务类型动态选择 Agent 架构
    # TODO: 未来在此处支持从 workflow_config.py 读取自定义节点配置

    # ---- 创建节点函数（通过工厂函数注入 Agent、ContextManager 和 Memory）----
    # 优先级：专属记忆 > 共享记忆 > None
    design_fn = make_design_node(
        design_agent, 
        ctx, 
        memory=design_memory or shared_memory  # 优先用专属记忆，否则用共享记忆
    )
    think_fn = make_think_node(
        think_agent, 
        ctx, 
        memory=think_memory or shared_memory
    )
    execute_fn = make_execute_node(
        execute_agent, 
        ctx, 
        memory=execute_memory or shared_memory
    )

    # ---- 构建 LangGraph StateGraph ----
    graph = StateGraph(WorkflowState)

    # 注册核心节点
    graph.add_node("design", design_fn)
    graph.add_node("think", think_fn)
    graph.add_node("execute", execute_fn)

    if rag_enabled:
        # ---- RAG 模式：Design → Retrieve → Think → Execute ----
        # make_retrieve_node 本身不引入 chromadb 依赖（使用 TYPE_CHECKING 注解）；
        # chromadb 的实际加载发生在 RAGPipeline.__init__ 内的延迟导入，
        # 由调用方（main.py 或用户代码）在实例化 RAGPipeline 时触发。
        retrieve_fn = make_retrieve_node(rag_pipeline, ctx)
        graph.add_node("retrieve", retrieve_fn)

        graph.add_edge(START, "design")
        graph.add_edge("design", "retrieve")
        graph.add_edge("retrieve", "think")
        graph.add_edge("think", "execute")
        graph.add_edge("execute", END)

        # TODO: 未来在此处为 retrieve 节点添加条件边：
        #       若检索结果为空，可直接跳转到 think，跳过 retrieve 日志
    else:
        # ---- 标准模式：Design → Think → Execute ----
        graph.add_edge(START, ENTRY_NODE)
        add_linear_edges(graph)

    # ---- 编译图 ----
    app = graph.compile()

    logger.info(f"TeX_Agent 工作流图构建完成 [{topology}]")
    
    # 记录记忆配置
    if design_memory or think_memory or execute_memory or shared_memory:
        logger.info(f"记忆系统已集成: design={design_memory is not None}, "
                   f"think={think_memory is not None}, "
                   f"execute={execute_memory is not None}, "
                   f"shared={shared_memory is not None}")

    # TODO: 未来在此处支持添加 checkpointer（如 MemorySaver / SqliteSaver）
    #       实现工作流状态的持久化，支持断点续跑

    return app


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
) -> Any:
    """
    根据 NodeConfig / EdgeConfig 列表动态构建并编译 LangGraph 图。

    这是 MASPlanner → WorkflowParser → 可执行 app 调用链的最终环节。
    与硬编码的 build_graph() 并存，两者互不影响：
      - build_dynamic_graph()：动态拓扑，由 AutoAgentsMASPlanner 驱动
      - build_graph()：固定三节点，始终作为兜底

    兜底策略：
      若 nodes 为空（规划失败），直接调用 build_graph() 返回硬编码图。

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

    # 兜底：nodes 为空时退回硬编码图
    if not nodes:
        logger.warning("[DynamicGraph] NodeConfig 列表为空，回退到硬编码 build_graph()")
        return build_graph(context_manager=context_manager, shared_memory=shared_memory)

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