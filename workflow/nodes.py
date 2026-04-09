"""
工作流节点定义（最终生产就绪版 v2）。
核心修复：
  ✅ 强制兼容 agent.run() 返回 str/dict/AgentMessage 的所有情况
  ✅ 安全构建 state["messages"] 更新，避免 LangGraph 状态冲突或类型污染
  ✅ 统一调用 ctx.build()，自动注入 RAG/Memory/History
  ✅ 彻底移除对 .content 的直接裸露访问
"""
from typing import TYPE_CHECKING, Callable, Dict, Any, Optional, Union
from datetime import datetime
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

# ================= 📝 Design 节点（修复版） =================
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

        # 5. 保存响应到上下文
        ctx.save(resp)
        
        # 🔧 修复：保存到长期记忆
        if memory:
            try:
                memory.save(
                    key=f"design_{abs(hash(input_str)) % 10000}",
                    value={
                        "task": input_str[:100],
                        "design": resp.content,
                        "timestamp": datetime.now().isoformat()
                    },
                    metadata={"node": "design", "agent": "design"}
                )
                logger.info(f"[Design 节点] 已保存到长期记忆，当前记忆数: {memory.get_size()}")
            except Exception as e:
                logger.error(f"保存到长期记忆失败: {e}", exc_info=True)

        logger.info(f"[Design 节点] 完成，输出 {len(resp.content)} 字符")

        return {
            "messages": state["messages"] + [_safe_to_dict(user_msg), _safe_to_dict(resp)],
            "current_node": "design",
            "error": None,
        }
    return design_node


# ================= 🟩 Think 节点（修复版） =================
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
        
        # 🔧 修复：保存到长期记忆
        if memory:
            try:
                memory.save(
                    key=f"think_{abs(hash(state['input'])) % 10000}",
                    value={
                        "task": state['input'][:100],
                        "analysis": resp.content[:500],
                        "timestamp": datetime.now().isoformat()
                    },
                    metadata={"node": "think", "agent": "think"}
                )
                logger.info(f"[Think 节点] 已保存到长期记忆，当前记忆数: {memory.get_size()}")
            except Exception as e:
                logger.error(f"保存到长期记忆失败: {e}", exc_info=True)
        
        return {
            "messages": state["messages"] + [_safe_to_dict(user_msg), _safe_to_dict(resp)],
            "current_node": "think", 
            "error": None,
        }
    return think_node


# ================= 🟥 Execute 节点（保持原样，已有记忆保存） =================
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

        # 结果持久化到 Memory
        if memory:
            try:
                memory.save(
                    key=f"result_{abs(hash(state['input'])) % 10000}", 
                    value={
                        "task": state['input'], 
                        "output": resp.content,
                        "timestamp": datetime.now().isoformat()
                    }, 
                    metadata={"agent": "execute", "node": "execute"}
                )
                logger.info(f"[Execute 节点] 已保存到长期记忆，当前记忆数: {memory.get_size()}")
            except Exception as e:
                logger.error(f"保存到长期记忆失败: {e}", exc_info=True)

        return {
            "messages": state["messages"] + [_safe_to_dict(user_msg), _safe_to_dict(resp)],
            "current_node": "execute",
            "output": resp.content,
            "error": None,
        }
    return execute_node


# ================= 🔧 通用动态节点工厂（供 build_dynamic_graph 使用） =================

def make_generic_agent_node(
    agent: BaseAgent,
    ctx: BaseContext,
    node_id: str,
    node_config: dict,
    memory: Optional["BaseMemory"] = None,
) -> Callable[[WorkflowState], dict]:
    """
    通用 Agent 节点工厂，供 build_dynamic_graph() 按 NodeConfig 动态创建节点。

    与固定节点（make_design_node 等）的区别：
      - system_prompt / subtask / output_schema 均从 node_config 动态读取
      - 统一在 system_prompt 末尾注入 NODE_OUTPUT_FORMAT_INSTRUCTION，
        强制 LLM 输出结构化 JSON（result / summary / confidence / metadata）
      - 解析 JSON 输出后存入 state["metadata"][node_id]，供下游节点精确读取
      - 自动从 state["metadata"] 提取 depends_on 节点的 summary 注入上游上下文

    Args:
        agent:       已实例化的 BaseAgent（SimpleAgent / ReActAgent 等）。
        ctx:         共享 ContextManager 实例。
        node_id:     节点唯一标识（对应 NodeConfig.node_id），用于日志和 metadata 键。
        node_config: NodeConfig.config 字典，包含：
                       system_prompt : 角色系统提示（不含输出格式约束）
                       subtask       : 该节点具体子任务描述
                       output_schema : 输出字段描述（仅用于注释说明，不影响解析）
                       depends_on    : 上游节点 node_id 列表
                       temperature   : （由 build_dynamic_graph 在实例化 agent 时使用）
        memory:      长期记忆实例（可选）。

    Returns:
        符合 LangGraph 规范的节点函数 WorkflowState -> dict。
    """
    # 从 config 层导入，避免 workflow → router 的跨层依赖
    from config.planner_config import NODE_OUTPUT_FORMAT_INSTRUCTION, parse_llm_json

    system_prompt: str = node_config.get("system_prompt", f"你是 {node_id} 专家。")
    subtask: str       = node_config.get("subtask", "")
    depends_on: list   = node_config.get("depends_on", [])

    # 将输出格式约束追加到 system_prompt（框架统一注入，agent 自身 prompt 无需包含）
    full_system_prompt = system_prompt + NODE_OUTPUT_FORMAT_INSTRUCTION

    def generic_node(state: WorkflowState) -> dict:
        logger.info(f"[{node_id} 节点] 开始执行...")

        # 1. 收集上游节点 summary（从 state["metadata"] 精确读取）
        upstream_summaries: list = []
        for dep_id in depends_on:
            dep_result = state.get("metadata", {}).get(dep_id, {})
            if dep_result:
                summary = dep_result.get("summary", str(dep_result)[:200])
                upstream_summaries.append(f"[{dep_id}] {summary}")

        upstream_ctx = (
            "\n".join(upstream_summaries)
            if upstream_summaries
            else "（无上游节点输出）"
        )

        # 2. 构建 prompt（system + 上游结果 + 原始任务 + 具体子任务）
        prompt = (
            f"{full_system_prompt}\n\n"
            f"[原始任务]\n{state.get('input', '')}\n\n"
            f"[上游节点输出]\n{upstream_ctx}\n\n"
            f"[你的具体任务]\n{subtask if subtask else state.get('input', '')}"
        )

        user_msg = AgentMessage(role="user", content=prompt[:150] + "...", agent_name="system")
        ctx.save(user_msg)

        # 3. 调用 Agent
        try:
            raw_resp = agent.run(prompt)
            resp = _ensure_agent_message(raw_resp, "assistant", node_id)
        except Exception as e:
            logger.error(f"[{node_id} 节点] 执行失败: {e}")
            return {
                "messages":    state["messages"] + [_safe_to_dict(user_msg)],
                "current_node": node_id,
                "error":       str(e),
            }

        ctx.save(resp)

        # 4. 解析结构化输出（三级容错）
        structured: dict = parse_llm_json(
            resp.content,
            context=node_id,
            fallback={
                "result":     resp.content,
                "summary":    resp.content[:80],
                "confidence": 0.5,
                "metadata":   {},
            },
        )

        # 5. 写入长期记忆
        if memory:
            try:
                memory.save(
                    key=f"{node_id}_{abs(hash(state.get('input', ''))) % 10000}",
                    value={
                        "task":    state.get("input", "")[:100],
                        "result":  structured.get("result", "")[:500],
                        "summary": structured.get("summary", ""),
                    },
                    metadata={"node": node_id},
                )
            except Exception as e:
                logger.error(f"[{node_id} 节点] 保存长期记忆失败: {e}")

        # 6. 更新 state：metadata 存结构化结果供下游读取，output 跟踪最新节点产出
        current_metadata: dict = dict(state.get("metadata", {}))
        current_metadata[node_id] = structured

        logger.info(
            f"[{node_id} 节点] 完成，"
            f"confidence={structured.get('confidence', '?')}, "
            f"输出 {len(structured.get('result', ''))} 字符"
        )

        return {
            "messages":    state["messages"] + [_safe_to_dict(user_msg), _safe_to_dict(resp)],
            "current_node": node_id,
            "output":      structured.get("result", resp.content),
            "metadata":    current_metadata,
            "error":       None,
        }

    return generic_node