"""
工作流节点定义（最终生产就绪版 v2）。
核心修复：
  ✅ 强制兼容 agent.run() 返回 str/dict/AgentMessage 的所有情况
  ✅ 安全构建 state["messages"] 更新，避免 LangGraph 状态冲突或类型污染
  ✅ 统一调用 ctx.build()，自动注入 RAG/Memory/History
  ✅ 彻底移除对 .content 的直接裸露访问
"""
import re
from typing import TYPE_CHECKING, Callable, Dict, Any, Optional, Union, List, Set
from core.state import WorkflowState
from core.message import AgentMessage
from agents.base_agent import BaseAgent
from context.base import BaseContext
from utils.logger import get_logger
from config.planner_config import (
    DEFAULT_HISTORY_MODE,
    NODE_OUTPUT_FORMAT_INSTRUCTION,
    PERSONA_ENTRY_NODE_FORMAT_ADDON,
    SINGLE_TURN_NODE_CONTRACT,
    FINAL_DELIVERY_SYSTEM_ADDON,
    UPSTREAM_RESULT_MAX_CHARS,
    FINAL_DELIVERY_GUARD_QUESTION_KEYWORDS,
    FINAL_DELIVERY_GUARD_RESTATE_KEYWORDS,
    parse_llm_json,
)
from workflow.run_dump import write_node_trace

if TYPE_CHECKING:
    from memory.persona_memory import UserPersonaMemory

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


def _truncate_text(text: str, max_chars: int) -> str:
    if max_chars <= 0:
        return ""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + f"\n...（已截断，共{len(text)}字符）"


def _extract_metadata_chain_node_ids(built_context: str) -> Set[str]:
    """
    从 ctx.build() 产物中识别 metadata_chain 已覆盖的节点，便于 upstream 去重。
    """
    if "<context type='metadata_chain'>" not in built_context:
        return set()
    return set(re.findall(r"### \[([^\]]+)\]", built_context))


def _detect_terminal_delivery_risks(output_text: str) -> List[str]:
    """
    终节点轻量交付检查：仅产生日志告警，不中断流程。
    """
    text = (output_text or "").strip()
    if not text:
        return ["终节点输出为空"]

    lower_text = text.lower()
    risks: List[str] = []
    if any(kw.lower() in lower_text for kw in FINAL_DELIVERY_GUARD_QUESTION_KEYWORDS):
        risks.append("疑似等待式反问用户")

    question_marks = text.count("?") + text.count("？")
    actionable_markers = ("步骤", "示例", "例如", "建议", "你可以", "请按", "操作")
    restate_hits = sum(1 for kw in FINAL_DELIVERY_GUARD_RESTATE_KEYWORDS if kw in text)
    has_actionable = any(marker in text for marker in actionable_markers)
    if question_marks >= 2 and not has_actionable:
        risks.append("疑似以反问为主，缺少可执行交付")
    if restate_hits >= 3 and not has_actionable:
        risks.append("疑似以上游复述为主，缺少直接答案/步骤")
    return risks


# ================= 🔧 通用动态节点工厂（供 build_dynamic_graph 使用） =================

def make_generic_agent_node(
    agent: BaseAgent,
    ctx: BaseContext,
    node_id: str,
    node_config: dict,
    persona_memory: Optional["UserPersonaMemory"] = None,
    *,
    default_history_mode: str = DEFAULT_HISTORY_MODE,
    is_terminal: bool = False,
    is_entry_node: bool = False,
) -> Callable[[WorkflowState], dict]:
    """
    通用 Agent 节点工厂，供 build_dynamic_graph() 按 NodeConfig 动态创建节点。

    与固定节点（make_design_node 等）的区别：
      - system_prompt / subtask / output_schema 均从 node_config 动态读取
      - 统一在 system_prompt 末尾注入 NODE_OUTPUT_FORMAT_INSTRUCTION，
        强制 LLM 输出结构化 JSON（result / summary / confidence / metadata）
      - 解析 JSON 输出后存入 state["metadata"][node_id]，供下游节点精确读取
      - 自动从 state["metadata"] 提取 depends_on 节点的完整产出（result + 摘要）注入上游上下文
      - history_mode：节点 config.history_mode 优先，否则使用工厂参数 default_history_mode（full / minimal）

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
                       history_mode  : 可选 "full" | "minimal"，覆盖构图时的 default_history_mode
        persona_memory: 全局用户画像（单文件）；在 system 段头部注入，仅入口节点可写回。
        default_history_mode: 当 node_config 未指定 history_mode 时使用（由 build_dynamic_graph 注入）。
        is_terminal: 是否为汇节点（无出边）；minimal 模式下仅终端节点 ctx.save。
        is_entry_node: 是否为工作流入口节点；负责在 JSON 中输出 persona_memory_update。

    Returns:
        符合 LangGraph 规范的节点函数 WorkflowState -> dict。
    """
    system_prompt: str = node_config.get("system_prompt", f"你是 {node_id} 专家。")
    subtask: str       = node_config.get("subtask", "")
    depends_on: list   = node_config.get("depends_on", [])

    raw_mode = node_config.get("history_mode")
    if raw_mode is None or (isinstance(raw_mode, str) and not raw_mode.strip()):
        raw_mode = default_history_mode
    if not isinstance(raw_mode, str):
        raw_mode = str(default_history_mode)
    mode_norm = raw_mode.strip().lower()
    if mode_norm not in ("full", "minimal"):
        logger.warning(
            f"[{node_id}] 非法 history_mode={raw_mode!r}，回退为 {default_history_mode!r}"
        )
        mode_norm = str(default_history_mode).strip().lower()
        if mode_norm not in ("full", "minimal"):
            mode_norm = "minimal"

    def _upstream_blocks(meta: dict, covered_by_history: Set[str]) -> str:
        lines: list = []
        for dep_id in depends_on:
            dep_result = meta.get(dep_id)
            if not isinstance(dep_result, dict):
                continue
            summary = str(dep_result.get("summary", "")).strip()
            result = str(dep_result.get("result", "")).strip()
            if not summary and not result:
                continue
            block_lines = [f"[{dep_id}]"]
            if summary:
                block_lines.append(f"摘要: {summary}")
            # 若 history(metadata_chain) 已覆盖该节点，则 upstream 只保留摘要，避免重复灌入
            if result and dep_id not in covered_by_history:
                compact_result = _truncate_text(result, UPSTREAM_RESULT_MAX_CHARS)
                block_lines.append(f"补充产出(截断):\n{compact_result}")
            lines.append("\n".join(block_lines))
        return "\n\n".join(lines) if lines else "（无上游节点输出）"

    def generic_node(state: WorkflowState) -> dict:
        logger.info(
            f"[{node_id} 节点] 开始执行... "
            f"(history_mode={mode_norm}, terminal={is_terminal}, entry={is_entry_node})"
        )

        meta = state.get("metadata", {}) or {}

        persona_head = persona_memory.format_for_prompt() if persona_memory else ""
        entry_addon = PERSONA_ENTRY_NODE_FORMAT_ADDON if is_entry_node else ""
        terminal_addon = FINAL_DELIVERY_SYSTEM_ADDON if is_terminal else ""
        full_system_prompt = (
            persona_head
            + system_prompt
            + SINGLE_TURN_NODE_CONTRACT
            + terminal_addon
            + NODE_OUTPUT_FORMAT_INSTRUCTION
            + entry_addon
        )

        # 1. 构建上下文（历史消息 + RAG；minimal 时用 metadata 链合成；画像不走 memory.search）
        built_context = ctx.build(
            state,
            memory=None,
            config={
                "conv_limit": int(node_config.get("conv_limit", 12)),
                "mem_limit": int(node_config.get("mem_limit", 5)),
                "max_tokens": int(node_config.get("max_tokens", 8000)),
                "format": node_config.get("format", "plain"),
                "synthetic_metadata_history": mode_norm == "minimal",
            },
        )
        # 2. 基于 history 是否已包含 metadata_chain 做 upstream 去重
        covered_node_ids = _extract_metadata_chain_node_ids(built_context)
        upstream_ctx = _upstream_blocks(meta, covered_node_ids)

        # 3. 构建 prompt（system + 历史上下文 + 上游结果 + 原始任务 + 具体子任务）
        prompt = (
            f"[你的具体任务]\n{subtask if subtask else state.get('input', '')}"
            f"{full_system_prompt}\n\n"
            f"[历史上下文]\n{built_context if built_context else '（无历史上下文）'}\n\n"
            f"[原始任务]\n{state.get('input', '')}\n\n"
            f"[上游节点输出]\n{upstream_ctx}\n\n"
        )

        user_msg = AgentMessage(role="user", content=prompt, agent_name="system")
        if mode_norm == "full":
            ctx.save(user_msg)

        run_dir = meta.get("__run_output_dir__")

        # 4. 调用 Agent
        try:
            raw_resp = agent.run(prompt)
            resp = _ensure_agent_message(raw_resp, "assistant", node_id)
        except Exception as e:
            logger.error(f"[{node_id} 节点] 执行失败: {e}")
            write_node_trace(run_dir, node_id, prompt, error=str(e))
            err: Dict[str, Any] = {
                "current_node": node_id,
                "error": str(e),
            }
            if mode_norm == "full":
                err["messages"] = state["messages"] + [_safe_to_dict(user_msg)]
            return err

        if mode_norm == "full":
            ctx.save(resp)
        elif mode_norm == "minimal" and is_terminal:
            ctx.save(resp)

        # 5. 解析结构化输出（三级容错）
        fb = {
            "result": resp.content,
            "summary": resp.content[:80],
            "confidence": 0.5,
            "metadata": {},
        }
        if is_entry_node:
            fb["persona_memory_update"] = {"action": "none", "delta": {}}
        structured: dict = parse_llm_json(resp.content, context=node_id, fallback=fb)

        structured = dict(structured)
        pm_update = structured.pop("persona_memory_update", None)
        if persona_memory:
            if is_entry_node:
                persona_memory.apply_persona_memory_update(pm_update)
            elif pm_update is not None:
                logger.debug(f"[{node_id}] 忽略非入口节点产生的 persona_memory_update")

        # 6. 更新 state：metadata + 执行顺序（供 ctx.build 合成历史）
        current_metadata: dict = dict(state.get("metadata", {}))
        exec_order = list(current_metadata.get("__execution_order__", []))
        if node_id not in exec_order:
            exec_order.append(node_id)
        current_metadata["__execution_order__"] = exec_order
        current_metadata[node_id] = structured

        if is_terminal:
            delivery_risks = _detect_terminal_delivery_risks(structured.get("result", ""))
            if delivery_risks:
                logger.warning(
                    f"[{node_id} 节点] 终节点交付告警: {'; '.join(delivery_risks)}"
                )

        logger.info(
            f"[{node_id} 节点] 完成，"
            f"confidence={structured.get('confidence', '?')}, "
            f"输出 {len(structured.get('result', ''))} 字符"
        )

        out: Dict[str, Any] = {
            "current_node": node_id,
            "output": structured.get("result", resp.content),
            "metadata": current_metadata,
            "error": None,
        }
        if mode_norm == "full":
            out["messages"] = state["messages"] + [
                _safe_to_dict(user_msg),
                _safe_to_dict(resp),
            ]
        write_node_trace(
            run_dir,
            node_id,
            prompt,
            raw_response=resp.content,
            structured=structured,
        )
        return out

    return generic_node