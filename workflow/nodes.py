"""
工作流节点定义（可运行）。
包含 design_node、think_node、execute_node 三个核心节点的工厂函数，
以及 RAG 集成后新增的 retrieve_node 工厂函数。

每个工厂函数接收依赖项（BaseAgent、BaseMemory、BaseRAGPipeline），
返回 LangGraph 兼容的节点函数（符合"闭包注入依赖"的设计模式）。

面向接口编程：
  - Agent 依赖 BaseAgent（而非 SimpleAgent）
  - Memory 依赖 BaseMemory（而非 ContextManager）
  - RAG 管道依赖 BaseRAGPipeline（而非 RAGPipeline）
"""
from typing import TYPE_CHECKING, Callable

from core.state import WorkflowState
from core.message import AgentMessage
from agents.base_agent import BaseAgent
from memory.base_memory import BaseMemory
from utils.logger import get_logger

if TYPE_CHECKING:
    # 仅用于类型提示，运行时不导入，避免 chromadb 未安装时崩溃
    from rag.base_retriever import BaseRAGPipeline

logger = get_logger(__name__)


def make_design_node(
    agent: BaseAgent,
    ctx: BaseMemory,
) -> Callable[[WorkflowState], dict]:
    """
    创建 Design（设计）节点函数。

    职责：分析用户原始输入，制定整体解决方案的结构设计。

    Args:
        agent: 执行此节点的 BaseAgent 实例（依赖接口，不依赖具体实现）。
        ctx: 共享记忆实例（BaseMemory 接口），用于跨节点保存消息历史。

    Returns:
        符合 LangGraph 规范的节点函数（接收 WorkflowState，返回部分状态更新字典）。
    """

    def design_node(state: WorkflowState) -> dict:
        logger.info("[Design 节点] 开始执行...")

        user_msg = AgentMessage(
            role="user",
            content=(
                f"请分析以下论文写作任务，制定详细的整体解决方案设计：\n\n"
                f"【任务描述】\n{state['input']}\n\n"
                f"请输出：\n"
                f"1）任务分析：理解需求的核心要点\n"
                f"2）解决思路：整体解决方向\n"
                f"3）预计执行步骤：后续具体操作步骤"
            ),
            agent_name="user",
        )

        # 先保存用户消息，确保即使 agent.run() 异常也能记录问题现场
        ctx.save(user_msg)

        try:
            response = agent.run(user_msg)
        except Exception as e:
            logger.error(f"Design 节点执行失败: {e}")
            return {
                "messages": [user_msg.to_dict()],
                "current_node": "design",
                "error": str(e),
            }

        ctx.save(response)
        logger.info(f"[Design 节点] 完成，输出 {len(response.content)} 字符")

        # TODO: 未来在此处接入动态路由策略，根据 Design 结果决定下一个节点
        # TODO: 未来在此处调用 is_satisfactory() 判断是否需要重新设计

        return {
            "messages": [user_msg.to_dict(), response.to_dict()],
            "current_node": "design",
            "error": None,
        }

    return design_node


def make_retrieve_node(
    pipeline: "BaseRAGPipeline",
    ctx: BaseMemory,
) -> Callable[[WorkflowState], dict]:
    """
    创建 Retrieve（知识库检索）节点函数。

    职责：根据用户输入，从本地向量知识库中检索相关文档片段，
    将结果写入 WorkflowState.retrieved_context 供后续节点使用。

    节点特性：
      - 不调用 LLM，纯本地向量搜索，开销极低
      - 知识库为空时自动跳过，不影响工作流正常运行
      - 检索失败时写入空字符串并记录 error，不中断流程

    Args:
        pipeline: RAG 管道实例（BaseRAGPipeline 接口）。
        ctx:      共享记忆实例（此节点不产生 AgentMessage，ctx 参数预留给未来审计日志）。

    Returns:
        符合 LangGraph 规范的节点函数。

    TODO: 未来在此处增加查询改写（Query Rewriting）逻辑，提升检索召回率
    TODO: 未来在此处支持混合检索（向量 + BM25 关键词），提升精准度
    TODO: 未来在此处增加检索结果重排序（Reranker），进一步提升相关性
    """

    def retrieve_node(state: WorkflowState) -> dict:
        logger.info("[Retrieve 节点] 开始执行...")

        if not pipeline.is_ready():
            logger.info("[Retrieve 节点] 知识库为空，跳过检索（不影响后续节点）")
            return {
                "retrieved_context": "",
                "current_node": "retrieve",
                "error": None,
            }

        try:
            retrieved = pipeline.retrieve(state["input"])
            doc_count = pipeline.document_count() if hasattr(pipeline, "document_count") else "?"
            logger.info(
                f"[Retrieve 节点] 检索完成 | 知识库片段数: {doc_count} "
                f"| 检索结果: {len(retrieved)} 字符"
            )
            return {
                "retrieved_context": retrieved,
                "current_node": "retrieve",
                "error": None,
            }
        except Exception as e:
            logger.error(f"Retrieve 节点执行失败: {e}")
            return {
                "retrieved_context": "",
                "current_node": "retrieve",
                "error": str(e),
            }

    return retrieve_node


def make_think_node(
    agent: BaseAgent,
    ctx: BaseMemory,
) -> Callable[[WorkflowState], dict]:
    """
    创建 Think（深度思考）节点函数。

    职责：在 Design 阶段成果基础上，深入分析技术细节、潜在问题和优化方向。
    当 RAG 启用时，自动将检索到的参考资料注入 Prompt。

    Args:
        agent: 执行此节点的 BaseAgent 实例。
        ctx: 共享记忆实例（BaseMemory 接口）。

    Returns:
        符合 LangGraph 规范的节点函数。
    """

    def think_node(state: WorkflowState) -> dict:
        logger.info("[Think 节点] 开始执行...")

        # 从状态中提取 Design 节点的 assistant 输出作为上下文
        # state["messages"] 是 WorkflowState 中的必填字段，直接访问而非 .get()
        all_messages = state["messages"]
        design_output = ""
        for msg in all_messages:
            if msg.get("role") == "assistant":
                design_output = msg.get("content", "")
                break  # 取第一条 assistant 消息（来自 Design 节点）

        # RAG 检索结果注入：当知识库有内容时，为 Think 节点提供参考资料
        retrieved = state["retrieved_context"]
        retrieved_section = (
            f"【知识库参考资料】\n{retrieved}\n\n"
            if retrieved
            else ""
        )

        user_msg = AgentMessage(
            role="user",
            content=(
                f"基于以下设计方案，请进行深入的批判性思考和细化分析：\n\n"
                f"【设计方案】\n{design_output}\n\n"
                f"{retrieved_section}"
                f"【原始任务】\n{state['input']}\n\n"
                f"请输出：\n"
                f"1）关键技术细节：需要重点关注的实现要点\n"
                f"2）潜在问题与风险：可能遇到的挑战\n"
                f"3）优化建议：具体的改进方向"
            ),
            agent_name="user",
        )

        ctx.save(user_msg)

        try:
            response = agent.run(user_msg)
        except Exception as e:
            logger.error(f"Think 节点执行失败: {e}")
            return {
                "messages": [user_msg.to_dict()],
                "current_node": "think",
                "error": str(e),
            }

        ctx.save(response)
        logger.info(f"[Think 节点] 完成，输出 {len(response.content)} 字符")

        # TODO: 未来在此处接入 ReflectionAgent，对思考结果进行自我批评与改进
        # TODO: 未来在此处调用 ArxivSearchTool，基于思考结果自动检索相关文献

        return {
            "messages": [user_msg.to_dict(), response.to_dict()],
            "current_node": "think",
            "error": None,
        }

    return think_node


def make_execute_node(
    agent: BaseAgent,
    ctx: BaseMemory,
) -> Callable[[WorkflowState], dict]:
    """
    创建 Execute（执行）节点函数。

    职责：整合 Design + Think 阶段的全部成果以及 RAG 检索结果，
    执行任务并生成最终可用输出。

    当 RAG 启用时，检索结果会被优先注入 Prompt 顶部，
    使 LLM 能够基于知识库内容给出更准确的回答。

    Args:
        agent: 执行此节点的 BaseAgent 实例。
        ctx: 共享记忆实例（BaseMemory 接口）。

    Returns:
        符合 LangGraph 规范的节点函数。
    """

    def execute_node(state: WorkflowState) -> dict:
        logger.info("[Execute 节点] 开始执行...")

        # 整合前序节点的所有 assistant 消息作为完整上下文
        all_messages = state["messages"]
        context_parts = []
        for msg in all_messages:
            if msg.get("role") == "assistant":
                agent_name = msg.get("agent_name", "Agent")
                context_parts.append(f"[{agent_name} 的分析]\n{msg.get('content', '')}")

        full_context = "\n\n---\n\n".join(context_parts) if context_parts else "（无前序分析）"

        # RAG 检索结果注入：放在 Prompt 最前，让 LLM 基于知识库内容作答
        retrieved = state["retrieved_context"]
        retrieved_section = (
            f"【知识库检索结果（优先参考）】\n{retrieved}\n\n"
            if retrieved
            else ""
        )

        user_msg = AgentMessage(
            role="user",
            content=(
                f"请根据以下完整的设计与思考分析，执行任务并输出最终结果：\n\n"
                f"{retrieved_section}"
                f"【前序分析汇总】\n{full_context}\n\n"
                f"【原始任务】\n{state['input']}\n\n"
                f"请给出完整、详细、可直接使用的最终答案。"
            ),
            agent_name="user",
        )

        ctx.save(user_msg)

        try:
            response = agent.run(user_msg)
        except Exception as e:
            logger.error(f"Execute 节点执行失败: {e}")
            return {
                "messages": [user_msg.to_dict()],
                "current_node": "execute",
                "output": f"执行失败: {e}",
                "error": str(e),
            }

        ctx.save(response)
        logger.info(f"[Execute 节点] 完成，最终输出 {len(response.content)} 字符")

        # TODO: 未来在此处接入工具调用（如 ArxivSearchTool、LaTeXParserTool）
        # TODO: 未来在此处接入结果验证（MASPlanner.validate()）
        # TODO: 未来在此处将结果持久化到 RAG 知识库（pipeline.index_text(response.content)）

        return {
            "messages": [user_msg.to_dict(), response.to_dict()],
            "current_node": "execute",
            "output": response.content,
            "error": None,
        }

    return execute_node
