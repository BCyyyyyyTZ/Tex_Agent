"""
工作流节点定义（最终生产就绪版 v2）。
核心修复：
  ✅ 强制兼容 agent.run() 返回 str/dict/AgentMessage 的所有情况
  ✅ 安全构建 state["messages"] 更新，避免 LangGraph 状态冲突或类型污染
  ✅ 统一调用 ctx.build()，自动注入 RAG/Memory/History
  ✅ 彻底移除对 .content 的直接裸露访问
"""
from typing import TYPE_CHECKING, Callable, Dict, Any, Optional, Union

from core.state import WorkflowState
from core.message import AgentMessage
from agents.base_agent import BaseAgent
from context.base import BaseContext
from utils.logger import get_logger

if TYPE_CHECKING:
    from rag.base_retriever import BaseRAGPipeline
    from memory.base_memory import BaseMemory

logger = get_logger(__name__)


# ================= 🔒 核心安全转换工具 =================

def _ensure_agent_message(raw_resp: Any, role: str, agent_name: str) -> AgentMessage:
    """
    绝对安全：将 Agent 返回值强制转为 AgentMessage。
    兼容 LLM SDK 返回 str、dict、None 或已包装对象。
    """
    if isinstance(raw_resp, AgentMessage):
        return raw_resp
    content = str(raw_resp) if raw_resp is not None else ""
    if isinstance(raw_resp, dict):
        return AgentMessage(
            role=raw_resp.get("role", role),
            content=str(raw_resp.get("content", content)),
            agent_name=raw_resp.get("agent_name", agent_name)
        )
    return AgentMessage(role=role, content=content, agent_name=agent_name)


def _safe_to_dict(msg: Union[AgentMessage, Dict[str, Any], str, Any]) -> Dict[str, Any]:
    """
    绝对安全：将任意消息转为标准 dict，供 LangGraph 状态合并使用。
    """
    if isinstance(msg, dict):
        return msg
    if isinstance(msg, AgentMessage):
        return msg.to_dict() if hasattr(msg, "to_dict") else {
            "role": msg.role, 
            "content": msg.content, 
            "agent_name": getattr(msg, "agent_name", "system")
        }
    # 兜底：如果是字符串或其他类型
    return {"role": "assistant", "content": str(msg), "agent_name": "unknown"}

def make_design_node(
    agent: BaseAgent,
    ctx: BaseContext,
    memory: Optional["BaseMemory"] = None,
) -> Callable[[WorkflowState], dict]:
    def design_node(state: WorkflowState) -> dict:
        logger.info("[Design 节点] 开始执行...")

        # 1. 安全获取任务输入
        raw_input = state.get('input', '')
        if hasattr(raw_input, 'content'):
            input_str = str(raw_input.content)
        elif isinstance(raw_input, str):
            input_str = raw_input
        else:
            input_str = str(raw_input)

        # 2. 构造用户消息
        user_msg = AgentMessage(
            role="user",
            content=f"请分析任务并制定设计方案：\n\n{input_str}",
            agent_name="user"
        )
        ctx.save(user_msg)

        # 3. GSSC 上下文构建
        context = ctx.build(state, memory=memory, config={
            "conv_limit": 10, "mem_limit": 3, "max_tokens": 6000, "format": "plain"
        })

        # 4. 生成 Prompt 并调用 Agent
        prompt = f"<system>你是论文架构师。请基于上下文制定结构化设计方案。</system>\n\n{context}\n\n<task>{input_str}</task>"

        try:
            raw_resp = agent.run(prompt)
            resp = _ensure_agent_message(raw_resp, "assistant", "design")
        except Exception as e:
            logger.error(f"Design 节点执行失败: {e}")
            return {
                "messages": state["messages"] + [_safe_to_dict(user_msg)],
                "current_node": "design", 
                "error": str(e)
            }

        # 5. 保存响应并返回
        ctx.save(resp)
        logger.info(f"[Design 节点] 完成，输出 {len(resp.content)} 字符")

        return {
            "messages": state["messages"] + [_safe_to_dict(user_msg), _safe_to_dict(resp)],
            "current_node": "design",
            "error": None,
        }
    return design_node


# ================= 🟨 Retrieve 节点 =================
def make_retrieve_node(
    pipeline: "BaseRAGPipeline",
    ctx: BaseContext,
) -> Callable[[WorkflowState], dict]:
    def retrieve_node(state: WorkflowState) -> dict:
        logger.info("[Retrieve 节点] 开始执行...")
        if not pipeline.is_ready():
            return {"retrieved_context": "", "current_node": "retrieve", "error": None}

        try:
            retrieved = pipeline.retrieve(query=state["input"])
            return {"retrieved_context": retrieved, "current_node": "retrieve", "error": None}
        except Exception as e:
            logger.error(f"Retrieve 节点执行失败: {e}")
            return {"retrieved_context": "", "current_node": "retrieve", "error": str(e)}
    return retrieve_node


# ================= 🟩 Think 节点 =================
def make_think_node(
    agent: BaseAgent,
    ctx: BaseContext,
    memory: Optional["BaseMemory"] = None,
) -> Callable[[WorkflowState], dict]:
    def think_node(state: WorkflowState) -> dict:
        logger.info("[Think 节点] 开始执行...")

        context = ctx.build(state, memory=memory, config={
            "conv_limit": 12, "mem_limit": 5, "max_tokens": 8000, "format": "plain"
        })

        prompt = f"<system>你是技术评审专家。请对设计方案进行批判性思考与细化。</system>\n\n{context}\n\n<task>{state['input']}\n\n请输出：\n1）关键技术细节\n2）潜在问题与风险\n3）优化建议</task>"

        user_msg = AgentMessage(role="user", content=prompt[:150]+"...", agent_name="system")
        ctx.save(user_msg)

        try:
            raw_resp = agent.run(prompt)
            resp = _ensure_agent_message(raw_resp, "assistant", "think")
        except Exception as e:
            return {"messages": state["messages"] + [_safe_to_dict(user_msg)], "current_node": "think", "error": str(e)}
            
        ctx.save(resp)
        return {
            "messages": state["messages"] + [_safe_to_dict(user_msg), _safe_to_dict(resp)],
            "current_node": "think", "error": None,
        }
    return think_node


# ================= 🟥 Execute 节点 =================
def make_execute_node(
    agent: BaseAgent,
    ctx: BaseContext,
    memory: Optional["BaseMemory"] = None,
) -> Callable[[WorkflowState], dict]:
    def execute_node(state: WorkflowState) -> dict:
        logger.info("[Execute 节点] 开始执行...")

        context = ctx.build(state, memory=memory, config={
            "conv_limit": 20, "mem_limit": 5, "max_tokens": 10000, "format": "plain"
        })

        prompt = f"<system>你是最终执行者，请直接输出可用结果。</system>\n\n{context}\n\n<task>{state['input']}</task>"
        user_msg = AgentMessage(role="user", content=prompt[:150]+"...", agent_name="system")
        ctx.save(user_msg)

        try:
            raw_resp = agent.run(prompt)
            resp = _ensure_agent_message(raw_resp, "assistant", "execute")
        except Exception as e:
            return {"messages": state["messages"] + [_safe_to_dict(user_msg)], "current_node": "execute", "output": f"失败: {e}", "error": str(e)}
            
        ctx.save(resp)

        # (可选) 结果持久化到 Memory
        if memory:
            try:
                memory.save(key=f"res_{abs(hash(state['input']))%10000}", 
                           value={"task": state["input"], "out": resp.content}, 
                           metadata={"agent":"execute"})
            except Exception as mem_e:
                logger.warning(f"Memory 保存失败: {mem_e}")

        return {
            "messages": state["messages"] + [_safe_to_dict(user_msg), _safe_to_dict(resp)],
            "current_node": "execute",
            "output": resp.content,
            "error": None,
        }
    return execute_node