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