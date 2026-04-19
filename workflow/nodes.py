"""
工作流节点定义（最终生产就绪版 v2）。
核心修复：
  ✅ 强制兼容 agent.run() 返回 str/dict/AgentMessage 的所有情况
  ✅ 安全构建 state["messages"] 更新，避免 LangGraph 状态冲突或类型污染
  ✅ 统一调用 ctx.build()，自动注入 RAG/Memory/History
  ✅ 彻底移除对 .content 的直接裸露访问
"""
import json
import re
from typing import TYPE_CHECKING, Callable, Dict, Any, Optional, Union, List, Set
from core.state import WorkflowState
from core.message import AgentMessage
from agents.base_agent import BaseAgent
from context.base import BaseContext
from tools.base_tool import BaseTool
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


def _is_tool_node_output(blob: Any) -> bool:
    """
    判断结构化节点产出是否来自 tool 节点。
    """
    if not isinstance(blob, dict):
        return False
    meta = blob.get("metadata", {})
    return isinstance(meta, dict) and meta.get("node_type") == "tool"


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


def _resolve_path_value(root: Any, path: str) -> Any:
    """
    通过点路径读取嵌套值；路径不存在时返回空字符串。
    例：
      path = "metadata.design.result"
    """
    cur = root
    for part in [p for p in path.split(".") if p]:
        if isinstance(cur, dict):
            cur = cur.get(part, "")
        elif isinstance(cur, list):
            try:
                cur = cur[int(part)]
            except (ValueError, IndexError):
                return ""
        else:
            return ""
    return cur


def _render_template_string(template: str, state: WorkflowState) -> Any:
    """
    渲染节点配置中的模板字符串：
      - ${input} / ${output} / ${current_node}
      - ${metadata.xxx.yyy}
    当模板串整体就是单个占位符时，返回原始类型值（dict/list/number 也可透传）。
    """
    pattern = re.compile(r"\$\{([^}]+)\}")
    matches = list(pattern.finditer(template))
    if not matches:
        return template

    def _resolve_key(expr: str) -> Any:
        expr = expr.strip()
        if expr == "last_message":
            msgs = state.get("messages", []) or []
            return msgs[-1] if msgs else {}
        if expr == "last_message_content":
            msgs = state.get("messages", []) or []
            if not msgs:
                return ""
            last = msgs[-1]
            if isinstance(last, dict):
                return str(last.get("content", ""))
            if isinstance(last, AgentMessage):
                return str(last.content)
            return str(last)
        if expr in ("input", "output", "current_node", "error", "retrieved_context"):
            return state.get(expr, "")
        if expr == "messages":
            return state.get("messages", []) or []
        if expr.startswith("state."):
            return _resolve_path_value(state, expr[len("state."):])
        if expr.startswith("metadata."):
            return _resolve_path_value(state.get("metadata", {}) or {}, expr[len("metadata."):])
        # 回退：默认按 state 根路径读取，便于 `${messages.0.content}` 这类表达式
        return _resolve_path_value(state, expr)

    # 整串占位符：返回真实类型，不强转字符串
    if len(matches) == 1 and matches[0].span() == (0, len(template)):
        return _resolve_key(matches[0].group(1))

    # 混合字符串：一律转字符串拼接
    result = template
    for m in matches:
        value = _resolve_key(m.group(1))
        result = result.replace(m.group(0), "" if value is None else str(value))
    return result


def _resolve_tool_payload(payload: Any, state: WorkflowState) -> Any:
    """
    递归解析 tool_input：
      - str 中可用 ${...} 模板
      - dict/list 递归解析
      - 其他类型原样返回
    """
    if isinstance(payload, str):
        return _render_template_string(payload, state)
    if isinstance(payload, list):
        return [_resolve_tool_payload(v, state) for v in payload]
    if isinstance(payload, dict):
        return {k: _resolve_tool_payload(v, state) for k, v in payload.items()}
    return payload


def _is_blank_payload(payload: Any) -> bool:
    if payload is None:
        return True
    if isinstance(payload, str):
        return not payload.strip()
    if isinstance(payload, list):
        return len(payload) == 0
    if isinstance(payload, dict):
        return len(payload) == 0
    return False


def _repair_tool_payload_if_needed(tool_name: str, payload: Any, state: WorkflowState) -> Any:
    """
    工具入参兜底：
      - 防止出现空 payload 导致工具 400（尤其是 arxiv_search）
    """
    if not _is_blank_payload(payload):
        return payload

    fallback_query = str(state.get("input", "") or "").strip()
    if tool_name == "arxiv_search":
        if fallback_query:
            logger.warning("[tool_node] arxiv_search payload 为空，已回退为 state.input")
            return fallback_query
        return "machine learning"
    return payload


def _set_nested_path(root: Dict[str, Any], dotted_path: str, value: Any) -> None:
    """
    按点路径写入字典，如 "a.b.c"。
    """
    parts = [p for p in str(dotted_path).split(".") if p]
    if not parts:
        return
    cur = root
    for part in parts[:-1]:
        nxt = cur.get(part)
        if not isinstance(nxt, dict):
            nxt = {}
            cur[part] = nxt
        cur = nxt
    cur[parts[-1]] = value


def _coerce_user_input(raw: str, schema: Dict[str, Any]) -> Any:
    """
    按 input_schema 将用户输入转为结构化值。
    """
    schema_type = str(schema.get("type", "text")).strip().lower()
    text = (raw or "").strip()
    if schema_type == "json":
        return json.loads(text) if text else {}
    if schema_type == "multi_choice":
        return [x.strip() for x in text.split(",") if x.strip()]
    return text


def _validate_user_input(value: Any, schema: Dict[str, Any], rules: Dict[str, Any]) -> Optional[str]:
    """
    返回 None 表示校验通过；否则返回错误原因。
    """
    required = bool(rules.get("required", False))
    if required:
        if value is None:
            return "输入不能为空"
        if isinstance(value, str) and not value.strip():
            return "输入不能为空"
        if isinstance(value, list) and not value:
            return "至少选择一项"

    schema_type = str(schema.get("type", "text")).strip().lower()
    if schema_type in ("single_choice", "multi_choice"):
        options = schema.get("options", []) or []
        if isinstance(options, list) and options:
            allowed = {str(x) for x in options}
            if schema_type == "single_choice":
                if value and str(value) not in allowed:
                    return f"输入不在可选项中: {value}"
            else:
                values = value if isinstance(value, list) else []
                for item in values:
                    if str(item) not in allowed:
                        return f"输入不在可选项中: {item}"

    if isinstance(value, str):
        min_len = rules.get("min_length")
        max_len = rules.get("max_length")
        if isinstance(min_len, int) and len(value) < min_len:
            return f"输入长度不能小于 {min_len}"
        if isinstance(max_len, int) and len(value) > max_len:
            return f"输入长度不能大于 {max_len}"
    return None


def _build_tool_structured_output(
    *,
    tool_name: str,
    node_id: str,
    payload: Any,
    tool_resp: Any,
) -> Dict[str, Any]:
    """
    将工具返回统一为与 Agent 节点兼容的结构化输出。
    保证下游 metadata_chain / depends_on 可以直接复用。
    """
    success = True
    output = ""
    error = None
    extra_meta: Dict[str, Any] = {}

    if hasattr(tool_resp, "success") and hasattr(tool_resp, "output"):
        success = bool(getattr(tool_resp, "success", True))
        output = str(getattr(tool_resp, "output", "") or "")
        err_val = getattr(tool_resp, "error", None)
        error = str(err_val) if err_val else None
        raw_meta = getattr(tool_resp, "metadata", {}) or {}
        if isinstance(raw_meta, dict):
            extra_meta = dict(raw_meta)
    elif isinstance(tool_resp, dict):
        success = bool(tool_resp.get("success", True))
        output = str(tool_resp.get("output", tool_resp))
        err_val = tool_resp.get("error")
        error = str(err_val) if err_val else None
        md = tool_resp.get("metadata", {})
        if isinstance(md, dict):
            extra_meta = dict(md)
    else:
        output = "" if tool_resp is None else str(tool_resp)

    summary_src = output.strip() if output else (error or "")
    summary = summary_src[:80]
    if not summary:
        summary = f"{tool_name} 执行完成"

    status = "pass" if success else "fail"
    confidence = 1.0 if success else 0.0

    return {
        "result": output,
        "summary": summary,
        "confidence": confidence,
        "status": status,
        "metadata": {
            "node_type": "tool",
            "node_id": node_id,
            "tool_name": tool_name,
            "success": success,
            "error": error,
            "tool_input": payload,
            "tool_metadata": extra_meta,
        },
    }


# ================= 🔧 动态节点工厂（供 build_dynamic_graph 使用） =================

def make_agent_node(
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
                if _is_tool_node_output(dep_result):
                    # 工具节点结果保留全量，避免检索结果被截断
                    block_lines.append(f"补充产出(完整):\n{result}")
                else:
                    compact_result = _truncate_text(result, UPSTREAM_RESULT_MAX_CHARS)
                    block_lines.append(f"补充产出(截断):\n{compact_result}")
            lines.append("\n".join(block_lines))
        return "\n\n".join(lines) if lines else "（无上游节点输出）"

    def agent_node(state: WorkflowState) -> dict:
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

    return agent_node


def make_tool_node(
    tool: BaseTool,
    ctx: BaseContext,
    node_id: str,
    node_config: dict,
    *,
    default_history_mode: str = DEFAULT_HISTORY_MODE,
    is_terminal: bool = False,
) -> Callable[[WorkflowState], dict]:
    """
    工具节点工厂：
      - 解析 tool_input 模板（支持 ${input} / ${metadata.xxx}）
      - 执行 tool.run(...)
      - 输出统一结构化 metadata（result/summary/confidence/...）
    """
    raw_mode = node_config.get("history_mode")
    if raw_mode is None or (isinstance(raw_mode, str) and not raw_mode.strip()):
        raw_mode = default_history_mode
    if not isinstance(raw_mode, str):
        raw_mode = str(default_history_mode)
    mode_norm = raw_mode.strip().lower()
    if mode_norm not in ("full", "minimal"):
        mode_norm = str(default_history_mode).strip().lower()
        if mode_norm not in ("full", "minimal"):
            mode_norm = "minimal"

    depends_on = node_config.get("depends_on", []) or []
    if not isinstance(depends_on, list):
        depends_on = []

    raw_tool_input = node_config.get("tool_input")

    # 工具节点默认入参策略（可扩展）：
    # 1) 显式配置 tool_input：使用用户配置
    # 2) 未配置且存在 depends_on：自动读取第一个上游节点 result
    # 3) 仍无上游：回退为原始用户输入
    if raw_tool_input is not None:
        default_payload = raw_tool_input
    elif depends_on:
        first_dep = str(depends_on[0]).strip()
        default_payload = f"${{metadata.{first_dep}.result}}" if first_dep else "${input}"
    else:
        default_payload = "${input}"
    emit_messages = bool(node_config.get("emit_messages", False))

    def tool_node(state: WorkflowState) -> dict:
        logger.info(
            f"[{node_id} 节点] 开始执行工具 {tool.name} "
            f"(history_mode={mode_norm}, terminal={is_terminal})"
        )
        meta = state.get("metadata", {}) or {}
        run_dir = meta.get("__run_output_dir__")

        payload = _resolve_tool_payload(default_payload, state)
        payload = _repair_tool_payload_if_needed(tool.name, payload, state)
        prompt_for_trace = (
            f"[TOOL_NODE]\n"
            f"tool_name={tool.name}\n"
            f"payload={payload}"
        )

        user_msg = AgentMessage(
            role="user",
            content=prompt_for_trace,
            agent_name="system",
            metadata={"node_type": "tool", "tool_name": tool.name},
        )
        should_emit_messages = (mode_norm == "full") or emit_messages
        if should_emit_messages:
            ctx.save(user_msg)

        try:
            if isinstance(payload, dict):
                tool_resp = tool.run(**payload)
            elif isinstance(payload, list):
                # 约定：列表参数默认作为单个 input 传入
                tool_resp = tool.run(payload)
            else:
                tool_resp = tool.run(payload)
        except Exception as e:
            logger.error(f"[{node_id} 节点] 工具执行失败: {e}")
            write_node_trace(run_dir, node_id, prompt_for_trace, error=str(e))
            err_out: Dict[str, Any] = {
                "current_node": node_id,
                "error": str(e),
            }
            if should_emit_messages:
                err_out["messages"] = state["messages"] + [_safe_to_dict(user_msg)]
            return err_out

        structured = _build_tool_structured_output(
            tool_name=tool.name,
            node_id=node_id,
            payload=payload,
            tool_resp=tool_resp,
        )

        tool_msg = AgentMessage(
            role="tool",
            content=structured.get("result", ""),
            agent_name=node_id,
            tool_name=tool.name,
            metadata=structured.get("metadata", {}),
        )
        if should_emit_messages:
            ctx.save(tool_msg)
        elif mode_norm == "minimal" and is_terminal:
            ctx.save(tool_msg)

        current_metadata: dict = dict(meta)
        exec_order = list(current_metadata.get("__execution_order__", []))
        if node_id not in exec_order:
            exec_order.append(node_id)
        current_metadata["__execution_order__"] = exec_order
        current_metadata[node_id] = structured

        write_node_trace(
            run_dir,
            node_id,
            prompt_for_trace,
            raw_response=structured.get("result", ""),
            structured=structured,
        )

        out: Dict[str, Any] = {
            "current_node": node_id,
            "output": structured.get("result", ""),
            "metadata": current_metadata,
            "error": None,
        }
        if should_emit_messages:
            out["messages"] = state["messages"] + [
                _safe_to_dict(user_msg),
                _safe_to_dict(tool_msg),
            ]
        return out

    return tool_node


def make_user_node(
    *,
    node_id: str,
    node_config: dict,
    human_input_provider: Optional[Callable[[str, Dict[str, Any], Dict[str, Any]], Any]] = None,
) -> Callable[[WorkflowState], dict]:
    """
    人机反馈节点工厂（HITL）：
      - 渲染 prompt_template
      - 读取用户输入（通过可注入 provider）
      - 做 schema 与 validation 校验
      - 统一写回 metadata（可配置 write_to）
    """
    prompt_template = str(node_config.get("prompt_template", "请提供反馈：")).strip()
    input_schema = node_config.get("input_schema", {"type": "text"})
    if not isinstance(input_schema, dict):
        input_schema = {"type": "text"}
    validation = node_config.get("validation", {})
    if not isinstance(validation, dict):
        validation = {}
    default_value = node_config.get("default_value", "")
    write_to = str(node_config.get("write_to", f"user_feedback.{node_id}")).strip()
    max_attempts = int(node_config.get("max_attempts", 2))
    if max_attempts <= 0:
        max_attempts = 1

    def _default_provider(prompt: str, schema: Dict[str, Any], rules: Dict[str, Any]) -> Any:
        _ = rules
        print(f"\n[USER_NODE:{node_id}] {prompt}")
        options = schema.get("options")
        if isinstance(options, list) and options:
            print(f"[可选项] {options}")
        return input("请输入反馈> ")

    provider = human_input_provider or _default_provider

    def user_node(state: WorkflowState) -> dict:
        logger.info(f"[{node_id} 节点] 等待用户反馈输入...")
        meta = state.get("metadata", {}) or {}
        rendered_prompt = _resolve_tool_payload(prompt_template, state)
        prompt_text = str(rendered_prompt)

        value: Any = None
        status = "needs_user"
        error = None
        for _ in range(max_attempts):
            try:
                raw = provider(prompt_text, input_schema, validation)
                if isinstance(raw, str):
                    value = _coerce_user_input(raw, input_schema)
                else:
                    value = raw
            except Exception as e:
                error = f"用户输入节点读取失败: {e}"
                value = None
                continue

            reason = _validate_user_input(value, input_schema, validation)
            if reason is None:
                status = "pass"
                error = None
                break
            error = reason
            status = "invalid"

        if status != "pass":
            value = default_value
            if status != "invalid":
                status = "needs_user"

        result_str = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
        structured = {
            "result": result_str,
            "summary": f"用户输入节点 {node_id} 已完成",
            "confidence": 1.0 if status == "pass" else 0.5,
            "status": status,
            "metadata": {
                "node_type": "user",
                "node_id": node_id,
                "input_schema": input_schema,
                "validation": validation,
                "write_to": write_to,
                "error": error,
                "raw_value": value,
            },
        }

        current_metadata: dict = dict(meta)
        exec_order = list(current_metadata.get("__execution_order__", []))
        if node_id not in exec_order:
            exec_order.append(node_id)
        current_metadata["__execution_order__"] = exec_order
        current_metadata[node_id] = structured
        if write_to:
            _set_nested_path(current_metadata, write_to, value)

        return {
            "current_node": node_id,
            "output": structured["result"],
            "metadata": current_metadata,
            "error": None if status == "pass" else error,
        }

    return user_node