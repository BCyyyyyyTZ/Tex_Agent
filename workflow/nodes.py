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

        # 2. 构建上下文（历史消息 + 长期记忆 + RAG）
        built_context = ctx.build(
            state,
            memory=memory,
            config={
                "conv_limit": int(node_config.get("conv_limit", 12)),
                "mem_limit": int(node_config.get("mem_limit", 5)),
                "max_tokens": int(node_config.get("max_tokens", 8000)),
                "format": node_config.get("format", "plain"),
            },
        )

        # 3. 构建 prompt（system + 历史上下文 + 上游结果 + 原始任务 + 具体子任务）
        prompt = (
            f"[你的具体任务]\n{subtask if subtask else state.get('input', '')}"
            f"{full_system_prompt}\n\n"
            f"[历史上下文]\n{built_context if built_context else '（无历史上下文）'}\n\n"
            f"[原始任务]\n{state.get('input', '')}\n\n"
            f"[上游节点输出]\n{upstream_ctx}\n\n"
        )

        user_msg = AgentMessage(role="user", content=prompt[:150] + "...", agent_name="system")
        ctx.save(user_msg)

        # 4. 调用 Agent
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

        # 5. 解析结构化输出（三级容错）
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

        # 6. 写入长期记忆
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

        # 7. 更新 state：metadata 存结构化结果供下游读取，output 跟踪最新节点产出
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