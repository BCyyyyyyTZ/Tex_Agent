"""
工作流节点工厂（v2 Breaking Change）。

Breaking Change v2：
  - _finalize_node_state 不再返回完整 messages/metadata，
    只返回【增量 delta】，由 state reducer 负责合并（operator.add / _merge_metadata）
  - 移除 _append_execution_order（由 state._merge_metadata reducer 接管）
  - 新增 make_parallel_fork_node / make_parallel_join_node 工厂
  - 三类节点（agent / tool / user）的写回协议统一，并发安全
"""
import json
import re
from typing import TYPE_CHECKING, Callable, Dict, Any, Optional, List, Literal

from core.state import WorkflowState, normalize_messages_for_state, normalize_node_output
from core.message import WorkflowMessage, NodeOutput, ensure_message
from agents.base_agent import BaseAgent
from agents.simple_agent_new import SimpleAgent_new
from context.base import BaseContext
from tools.base_tool import BaseTool
from utils.logger import get_logger
from config.planner_config import (
    DEFAULT_HISTORY_MODE,
    DEFAULT_SINGLE_TURN_CONTRACT_MODE,
    NODE_OUTPUT_FORMAT_INSTRUCTION,
    SINGLE_TURN_NODE_CONTRACT,
    UPSTREAM_RESULT_MAX_CHARS,
    FINAL_DELIVERY_GUARD_QUESTION_KEYWORDS,
    FINAL_DELIVERY_GUARD_RESTATE_KEYWORDS,
    parse_llm_json,
    resolve_final_delivery_addon,
)
from config.context_settings import (
    resolve_node_context_behavior,
    build_agent_prompt,
    make_dialogue_save_messages,
    should_save_assistant_to_dialogue_context,
)
from tools.user_persona_tools import (
    entry_node_persona_simple_agent_addon,
    entry_node_persona_system_addon,
)
from workflow.run_dump import write_node_trace

if TYPE_CHECKING:
    from memory.persona_memory import UserPersonaMemory

logger = get_logger(__name__)


# ================= 核心安全转换工具 =================

def _ensure_agent_message(
    raw_resp: Any,
    *,
    role: Literal["user", "assistant", "system", "tool"],
    source_type: Literal["agent", "tool", "user", "system"],
    source_id: str,
) -> WorkflowMessage:
    """将任意返回值收敛为统一消息协议。"""
    return ensure_message(
        raw_resp,
        default_role=role,
        default_source_type=source_type,
        default_source_id=source_id,
    )


def _finalize_node_state(
    *,
    state: WorkflowState,
    node_id: str,
    node_output: Dict[str, Any],
    output: str,
    error: Optional[str],
    new_messages: Optional[List[WorkflowMessage]] = None,
    metadata_updates: Optional[Dict[str, Any]] = None,
    is_terminal: bool = False,
) -> Dict[str, Any]:
    """
    三类节点统一写回协议（v2 Breaking Change）。

    返回增量 delta，不再返回完整 state：
      - metadata: 仅含本节点贡献（reducer 深合并）
      - messages: 仅含新增消息（reducer append）
      - current_node: 始终写（reducer last-wins）
      - output: 仅终端节点写入 state.output（避免并行中间节点互相覆盖最终输出）
        中间节点的输出已存储在 metadata[node_id].result，无需再写 state.output
      - error: 始终写（reducer first-error-wins）

    并发安全性（所有字段现均有 reducer）：
      - 并行节点各自写 metadata[node_id]，键不冲突
      - current_node: last-write-wins
      - output: last-nonempty-wins + 仅终端节点写
      - error: first-error-wins
      - messages: operator.add append
    """
    # metadata 增量：只写本节点贡献
    meta_delta: Dict[str, Any] = {
        "__execution_order__": [node_id],   # reducer 负责 append+去重
        node_id: normalize_node_output(node_output),
    }
    if metadata_updates:
        meta_delta = _deep_merge_dict(meta_delta, metadata_updates)

    out: Dict[str, Any] = {
        "current_node": node_id,
        "metadata": meta_delta,             # delta，reducer 深合并
        "error": error,
    }

    # 只有终端节点才写 state.output，避免中间并行节点互相覆盖
    if is_terminal:
        out["output"] = str(output or "")
    # 非终端节点结果已写入 metadata[node_id].result，不需要写 state.output

    if new_messages is not None:
        # 仅含新增消息，reducer 负责 append
        out["messages"] = normalize_messages_for_state(
            [m.to_dict() for m in new_messages]
        )

    return out


def _deep_merge_dict(base: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
    """深合并两个字典（updates 优先）。"""
    merged = dict(base)
    for key, value in updates.items():
        cur = merged.get(key)
        if isinstance(cur, dict) and isinstance(value, dict):
            merged[key] = _deep_merge_dict(cur, value)
        else:
            merged[key] = value
    return merged


def _truncate_text(text: str, max_chars: int) -> str:
    if max_chars <= 0:
        return ""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + f"\n...（已截断，共{len(text)}字符）"


def _detect_terminal_delivery_risks(output_text: str) -> List[str]:
    """终节点轻量交付检查（仅日志告警，不中断流程）。"""
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
    """通过点路径读取嵌套值；路径不存在时返回空字符串。"""
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
    """渲染节点配置中的 ${...} 模板字符串。"""
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
            return str(last.get("content", "")) if isinstance(last, dict) else str(last)
        if expr in ("input", "output", "current_node", "error", "retrieved_context"):
            return state.get(expr, "")
        if expr == "messages":
            return state.get("messages", []) or []
        if expr.startswith("state."):
            return _resolve_path_value(state, expr[len("state."):])
        if expr.startswith("metadata."):
            return _resolve_path_value(state.get("metadata", {}) or {}, expr[len("metadata."):])
        return _resolve_path_value(state, expr)

    if len(matches) == 1 and matches[0].span() == (0, len(template)):
        return _resolve_key(matches[0].group(1))

    result = template
    for m in matches:
        value = _resolve_key(m.group(1))
        result = result.replace(m.group(0), "" if value is None else str(value))
    return result


def _resolve_tool_payload(payload: Any, state: WorkflowState) -> Any:
    """递归解析 tool_input（支持 ${...} 模板）。"""
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
    if isinstance(payload, (list, dict)):
        return len(payload) == 0
    return False


def _normalize_arxiv_tool_payload(payload: Any) -> Any:
    """将 arxiv_search 入参规范为纯查询字符串（见 tools.arxiv_tool.prepare_arxiv_query）。"""
    from tools.arxiv_tool import prepare_arxiv_query

    if _is_blank_payload(payload):
        return payload
    return prepare_arxiv_query(payload)


def _normalize_tool_payload(tool_name: str, payload: Any) -> Any:
    if tool_name == "arxiv_search":
        return _normalize_arxiv_tool_payload(payload)
    return payload


def _parse_directions_blob(text: str) -> List[str]:
    """从上游节点 result 解析多研究方向条目（JSON 对象或编号列表）。"""
    body = (text or "").strip()
    if not body:
        return []
    try:
        data = json.loads(body)
        if isinstance(data, dict):
            inner = data.get("result")
            if isinstance(inner, str) and inner.strip().startswith("{"):
                try:
                    nested = json.loads(inner)
                    if isinstance(nested, dict):
                        data = nested
                except json.JSONDecodeError:
                    pass
            if isinstance(data, dict) and data:
                from tools.arxiv_tool import _extract_english_segment

                items: List[str] = []
                for k, v in data.items():
                    label = str(k).strip()
                    val = str(v).strip() if v else ""
                    if not label:
                        continue
                    if _extract_english_segment(label) or not re.search(
                        r"[\u4e00-\u9fff]", label
                    ):
                        items.append(label)
                    elif val:
                        items.append(val)
                    else:
                        items.append(label)
                if items:
                    return items
                return [str(v) for v in data.values() if v]
    except json.JSONDecodeError:
        pass
    parts = re.split(r"\n\s*\d+[\.\)、]\s*", body)
    return [p.strip() for p in parts if p.strip()]


def _branch_index_from_node_id(node_id: str) -> Optional[int]:
    m = re.search(r"_(\d+)$", str(node_id or ""))
    if m:
        return max(0, int(m.group(1)) - 1)
    return None


def _fallback_arxiv_query(
    state: WorkflowState, node_id: str, depends_on: List[str]
) -> str:
    """arxiv payload 为空时：从上游分析节点按并行分支序号取关键词，禁止用用户原话。"""
    from tools.arxiv_tool import prepare_arxiv_query

    meta = state.get("metadata") or {}
    branch_idx = _branch_index_from_node_id(node_id)
    dep_ids: List[str] = [str(d).strip() for d in (depends_on or []) if str(d).strip()]
    for key in meta:
        if key.startswith("__"):
            continue
        if any(tok in key for tok in ("analysis", "trend", "direction", "research", "topic")):
            if key not in dep_ids:
                dep_ids.append(key)

    for dep in dep_ids:
        nd = meta.get(dep)
        if not isinstance(nd, dict):
            continue
        res = str(nd.get("result") or nd.get("summary") or "").strip()
        if not res:
            continue
        directions = _parse_directions_blob(res)
        if directions and branch_idx is not None and branch_idx < len(directions):
            logger.warning(
                "[tool_node] arxiv_search payload 为空，已用上游 %s 第 %d 个方向",
                dep,
                branch_idx + 1,
            )
            return prepare_arxiv_query(directions[branch_idx])
        if directions:
            logger.warning(
                "[tool_node] arxiv_search payload 为空，已用上游 %s 的首个方向", dep
            )
            return prepare_arxiv_query(directions[0])
        logger.warning("[tool_node] arxiv_search payload 为空，已用上游 %s.result", dep)
        return prepare_arxiv_query(res)

    logger.warning("[tool_node] arxiv_search payload 为空，已回退默认英文检索词")
    return prepare_arxiv_query("LLM autonomous agent multi-agent systems")


def _repair_tool_payload_if_needed(
    tool_name: str,
    payload: Any,
    state: WorkflowState,
    *,
    node_id: str = "",
    depends_on: Optional[List[str]] = None,
) -> Any:
    """工具入参兜底：防止空 payload。"""
    if not _is_blank_payload(payload):
        return _normalize_tool_payload(tool_name, payload)
    if tool_name == "arxiv_search":
        return _fallback_arxiv_query(state, node_id, depends_on or [])
    fallback_query = str(state.get("input", "") or "").strip()
    return fallback_query or payload


def _set_nested_path(root: Dict[str, Any], dotted_path: str, value: Any) -> None:
    """按点路径写入字典，如 'a.b.c'。"""
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
    支持序号输入：single_choice/multi_choice 下若输入纯数字，则转换为对应选项。
    """
    schema_type = str(schema.get("type", "text")).strip().lower()
    text = (raw or "").strip()
    if schema_type == "json":
        return json.loads(text) if text else {}
    if schema_type == "single_choice":
        options = schema.get("options") or []
        # 支持序号输入（"1" → options[0]）
        if text.isdigit():
            idx = int(text) - 1
            if 0 <= idx < len(options):
                return str(options[idx])
        return text
    if schema_type == "multi_choice":
        options = schema.get("options") or []
        parts = []
        for token in text.split(","):
            token = token.strip()
            if token.isdigit():
                idx = int(token) - 1
                if 0 <= idx < len(options):
                    parts.append(str(options[idx]))
                    continue
            if token:
                parts.append(token)
        return parts
    return text


def _validate_user_input(value: Any, schema: Dict[str, Any], rules: Dict[str, Any]) -> Optional[str]:
    """返回 None 表示校验通过；否则返回错误原因。"""
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
    """将工具返回统一为与 Agent 节点兼容的结构化输出。"""
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
    summary = summary_src[:80] or f"{tool_name} 执行完成"
    status: Literal["pass", "fail"] = "pass" if success else "fail"

    return NodeOutput(
        result=output,
        summary=summary,
        confidence=1.0 if success else 0.0,
        status=status,
        metadata={
            "node_type": "tool",
            "node_id": node_id,
            "tool_name": tool_name,
            "success": success,
            "error": error,
            "tool_input": payload,
            "tool_metadata": extra_meta,
        },
    ).to_dict()


def _format_inner_meta_value(key: str, val: Any, *, max_len: int = 900) -> str:
    """
    将节点 metadata 内嵌字段压缩为可读的短串，避免 tool_input / tool_metadata
    等大对象经 repr() 整段进入上游 prompt 导致上下文爆炸。
    """
    if val is None:
        return ""
    if key == "tool_input" and isinstance(val, dict):
        parts: List[str] = []
        for k, v in val.items():
            if isinstance(v, str) and len(v) > 400:
                parts.append(f"{k}=<str {len(v)} chars>")
            elif isinstance(v, (dict, list, tuple)) and len(str(v)) > 400:
                parts.append(f"{k}=<{type(v).__name__} n={len(v)}>")
            else:
                frag = repr(v)
                if len(frag) > 360:
                    frag = frag[:360] + "...(trunc)"
                parts.append(f"{k}={frag}")
        body = ", ".join(parts[:20])
        if len(body) > max_len * 3:
            body = body[: max_len * 3] + "...(trunc)"
        return "{" + body + "}"
    if key == "tool_metadata" and isinstance(val, dict):
        rp = val.get("review_packages")
        if isinstance(rp, dict):
            lens = {str(k): len(str(v)) for k, v in rp.items()}
            return (
                "{review_packages: "
                + json.dumps({"keys": list(rp.keys()), "char_lens": lens}, ensure_ascii=False)
                + " ... 完整文本见 checklist_prepare 节点 result}"
            )
        s = repr(val)
        return s[: max_len * 2] + ("...(trunc)" if len(s) > max_len * 2 else "")
    s = repr(val)
    if len(s) > max_len:
        return s[:max_len] + f"...(trunc total_len={len(s)})"
    return s


def _upstream_blocks(
    meta: dict,
    depends_on: list,
    *,
    max_result_chars: Optional[int] = None,
) -> str:
    """
    从 metadata 提取 depends_on 节点的完整产出注入上游上下文。

    传递策略：
    - result 字段：完整保留（最多 UPSTREAM_RESULT_MAX_CHARS 字符，由配置控制）
    - summary / confidence / node_type：一并传递，帮助下游了解上游节点类型和置信度
    - 节点原始 metadata（工具特定数据）：若存在则附加关键字段
    """
    lines: list = []
    for dep_id in depends_on:
        dep_result = meta.get(dep_id)
        if not isinstance(dep_result, dict):
            continue
        summary = str(dep_result.get("summary", "")).strip()
        result = str(dep_result.get("result", "")).strip()
        node_type = str(dep_result.get("node_type", "")).strip()
        confidence = dep_result.get("confidence")
        status = dep_result.get("status", "")
        if not summary and not result:
            continue

        type_label = f"[{node_type}]" if node_type else ""
        conf_label = f" confidence={confidence:.2f}" if isinstance(confidence, (int, float)) else ""
        status_label = f" status={status}" if status else ""
        block_lines = [f"━━ 节点 [{dep_id}]{type_label}{conf_label}{status_label} ━━"]
        if summary:
            block_lines.append(f"摘要: {summary}")
        if result:
            cap = (
                max_result_chars
                if max_result_chars is not None and max_result_chars > 0
                else UPSTREAM_RESULT_MAX_CHARS
            )
            # 完整传递上游 result（默认 UPSTREAM_RESULT_MAX_CHARS；节点可覆盖以控制终节点 prompt 体积）
            compact_result = _truncate_text(result, cap)
            block_lines.append(f"完整输出:\n{compact_result}")

        # 附加工具节点的关键元数据字段（如文件路径、查询词等）
        inner_meta = dep_result.get("metadata")
        if isinstance(inner_meta, dict):
            useful_keys = [k for k in inner_meta
                           if k not in {"node_type", "node_id", "error"}
                           and inner_meta[k] is not None]
            if useful_keys:
                kv = ", ".join(
                    f"{k}={_format_inner_meta_value(k, inner_meta[k])}"
                    for k in useful_keys[:8]
                )
                block_lines.append(f"节点元数据: {{{kv}}}")

        lines.append("\n".join(block_lines))
    return "\n\n".join(lines) if lines else "（无上游节点输出）"


# ================= 动态节点工厂 =================

def make_agent_node(
    agent: BaseAgent,
    ctx: BaseContext,
    node_id: str,
    node_config: dict,
    persona_memory: Optional["UserPersonaMemory"] = None,
    runtime_memory: Optional[Any] = None,
    *,
    default_history_mode: str = DEFAULT_HISTORY_MODE,
    is_terminal: bool = False,
    is_entry_node: bool = False,
) -> Callable[[WorkflowState], dict]:
    """
    通用 Agent 节点工厂。

    写回协议（Breaking Change v2）：
      - 返回 {"messages": [new_msgs_only], "metadata": {node_id: output, ...}}
      - 不再返回完整 messages 列表或完整 metadata 字典
      - 由 state reducer 负责并发安全合并
    """
    system_prompt: str = node_config.get("system_prompt", f"你是 {node_id} 专家。")
    subtask: str = node_config.get("subtask", "")
    depends_on: list = node_config.get("depends_on", [])

    raw_mode = node_config.get("history_mode")
    if raw_mode is None or (isinstance(raw_mode, str) and not raw_mode.strip()):
        raw_mode = default_history_mode
    if not isinstance(raw_mode, str):
        raw_mode = str(default_history_mode)
    mode_norm = raw_mode.strip().lower()
    if mode_norm not in ("full", "minimal"):
        logger.warning(f"[{node_id}] 非法 history_mode={raw_mode!r}，回退为 {default_history_mode!r}")
        mode_norm = str(default_history_mode).strip().lower()
        if mode_norm not in ("full", "minimal"):
            mode_norm = "minimal"

    raw_contract_mode = node_config.get("single_turn_contract_mode", DEFAULT_SINGLE_TURN_CONTRACT_MODE)
    if isinstance(raw_contract_mode, bool):
        contract_mode = "always" if raw_contract_mode else "never"
    else:
        contract_mode = str(raw_contract_mode).strip().lower()
    if contract_mode not in ("always", "terminal_only", "never"):
        contract_mode = DEFAULT_SINGLE_TURN_CONTRACT_MODE
    enable_single_turn_contract = (
        contract_mode == "always" or (contract_mode == "terminal_only" and is_terminal)
    )

    def agent_node(state: WorkflowState) -> dict:
        logger.info(
            f"[{node_id}] 开始执行 "
            f"(history_mode={mode_norm}, terminal={is_terminal}, entry={is_entry_node})"
        )
        meta = state.get("metadata", {}) or {}
        user_input = str(state.get("input", "") or "")
        graph_profile = str(node_config.get("context_profile") or "pipeline")
        behavior = resolve_node_context_behavior(
            node_config,
            graph_profile=graph_profile,
            user_input=user_input,
            is_terminal=is_terminal,
        )
        profile = behavior.profile

        persona_head = ""
        if persona_memory and behavior.persona_prompt_read:
            persona_head = persona_memory.format_for_prompt()

        entry_addon = ""
        if is_entry_node and behavior.persona_file_write:
            if isinstance(agent, SimpleAgent_new):
                entry_addon = entry_node_persona_simple_agent_addon()
            else:
                entry_addon = entry_node_persona_system_addon()

        contract_mode_eff = behavior.single_turn_contract
        if contract_mode_eff == "always":
            enable_contracts = True
        elif contract_mode_eff == "never":
            enable_contracts = False
        else:
            enable_contracts = enable_single_turn_contract

        terminal_addon = (
            resolve_final_delivery_addon(
                behavior.terminal_delivery_style, profile=behavior.profile
            )
            if is_terminal
            else ""
        )

        inline_contracts = (
            persona_head
            + (SINGLE_TURN_NODE_CONTRACT if enable_contracts else "")
            + terminal_addon
            + behavior.json_format_instruction
            + entry_addon
        )
        built_context = ctx.build(
            state,
            memory=runtime_memory,
            config={
                "conv_limit": behavior.conv_limit,
                "mem_limit": behavior.mem_limit,
                "max_tokens": int(node_config.get("max_tokens", 8000)),
                "format": node_config.get("format", "plain"),
                "history_mode": mode_norm,
                "context_profile": profile,
                "is_terminal": is_terminal,
                "include_metadata_chain": behavior.include_metadata_chain,
            },
        )
        urc = node_config.get("upstream_result_max_chars")
        upstream_max = int(urc) if urc is not None else None
        upstream_ctx = _upstream_blocks(meta, depends_on, max_result_chars=upstream_max)

        prompt = build_agent_prompt(
            user_input=user_input,
            subtask=subtask if subtask else user_input,
            upstream_ctx=upstream_ctx,
            built_context=built_context if built_context else "（无历史上下文）",
            inline_contracts=inline_contracts,
            behavior=behavior,
        )

        user_msg = WorkflowMessage(
            role="user",
            source_type="system",
            source_id=f"{node_id}_prompt_builder",
            content=prompt,
            metadata={"node_id": node_id, "node_type": "agent"},
        )
        if mode_norm == "full":
            ctx.save(user_msg)

        run_dir = meta.get("__run_output_dir__")

        # 支持 agent 附件（如 Gemini 文件引用 / 本地路径）
        attachment_cfg = node_config.get("attachment", None)
        attachment_val = _resolve_tool_payload(attachment_cfg, state) if attachment_cfg is not None else None

        try:
            if attachment_val is not None:
                agent_input = {
                    "role": "user",
                    "source_type": "user",
                    "source_id": "workflow_agent_node",
                    "content": prompt,
                    "metadata": {"attachment": attachment_val},
                }
                raw_resp = agent.run(agent_input)
            else:
                raw_resp = agent.run(prompt)
            resp = _ensure_agent_message(
                raw_resp,
                role="assistant",
                source_type="agent",
                source_id=node_id,
            )
        except Exception as e:
            logger.error(f"[{node_id}] 执行失败: {e}")
            write_node_trace(run_dir, node_id, prompt, error=str(e))
            fail_structured = NodeOutput(
                result="",
                summary=f"{node_id} 执行失败",
                confidence=0.0,
                status="fail",
                metadata={"node_type": "agent", "node_id": node_id, "error": str(e)},
            ).to_dict()
            return _finalize_node_state(
                state=state,
                node_id=node_id,
                node_output=fail_structured,
                output="",
                error=str(e),
                new_messages=[user_msg],
                is_terminal=is_terminal,
            )

        if mode_norm == "full":
            ctx.save(resp)

        fb = {
            "result": resp.content,
            "summary": resp.content[:80],
            "confidence": 0.5,
            "metadata": {},
        }
        if is_entry_node:
            fb["persona_memory_update"] = {"action": "none", "delta": {}}
        structured_raw: dict = parse_llm_json(resp.content, context=node_id, fallback=fb)
        structured_payload = dict(structured_raw)
        pm_update = structured_payload.pop("persona_memory_update", None)
        structured = normalize_node_output(structured_payload)
        if persona_memory and is_entry_node and behavior.persona_file_write:
            persona_memory.apply_persona_memory_update(pm_update)
        elif pm_update is not None and is_entry_node:
            logger.debug(f"[{node_id}] 忽略 persona_memory_update（本轮未触发画像写回）")
        elif pm_update is not None:
            logger.debug(f"[{node_id}] 忽略非入口节点产生的 persona_memory_update")

        if mode_norm == "minimal" and is_terminal:
            if profile == "legacy":
                ctx.save(resp)
            else:
                res_txt = str(structured.get("result", "") or resp.content or "").strip()
                u_msg, a_msg = make_dialogue_save_messages(user_input, res_txt)
                ctx.save(u_msg)
                if should_save_assistant_to_dialogue_context(res_txt, behavior):
                    ctx.save(a_msg)
        elif mode_norm == "full" and profile != "legacy" and is_terminal:
            res_txt = str(structured.get("result", "") or resp.content or "").strip()
            u_msg, a_msg = make_dialogue_save_messages(user_input, res_txt)
            ctx.save(u_msg)
            if should_save_assistant_to_dialogue_context(res_txt, behavior):
                ctx.save(a_msg)

        if is_terminal:
            delivery_risks = _detect_terminal_delivery_risks(structured.get("result", ""))
            if delivery_risks:
                logger.warning(f"[{node_id}] 终节点交付告警: {'; '.join(delivery_risks)}")

        logger.info(
            f"[{node_id}] 完成，"
            f"confidence={structured.get('confidence', '?')}, "
            f"输出 {len(structured.get('result', ''))} 字符"
        )

        out = _finalize_node_state(
            state=state,
            node_id=node_id,
            node_output=structured,
            output=structured.get("result", resp.content),
            error=None,
            new_messages=[user_msg, resp],
            is_terminal=is_terminal,
        )
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
    工具节点工厂（v2 Breaking Change）。

    写回协议同 make_agent_node：只返回增量 delta。
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
    tool_trace_template = str(
        node_config.get(
            "tool_trace_template",
            "[TOOL_NODE]\ntool_name={tool_name}\npayload={payload}",
        )
    )

    if raw_tool_input is not None and not _is_blank_payload(raw_tool_input):
        default_payload = raw_tool_input
    elif depends_on:
        first_dep = str(depends_on[0]).strip()
        default_payload = f"${{metadata.{first_dep}.result}}" if first_dep else "${input}"
    else:
        default_payload = "${input}"

    emit_messages = bool(node_config.get("emit_messages", False))

    def tool_node(state: WorkflowState) -> dict:
        logger.info(
            f"[{node_id}] 开始执行工具 {tool.name} "
            f"(history_mode={mode_norm}, terminal={is_terminal})"
        )
        meta = state.get("metadata", {}) or {}
        run_dir = meta.get("__run_output_dir__")

        payload = _resolve_tool_payload(default_payload, state)
        payload = _repair_tool_payload_if_needed(
            tool.name, payload, state, node_id=node_id, depends_on=depends_on
        )

        try:
            prompt_for_trace = tool_trace_template.format(
                node_id=node_id,
                tool_name=tool.name,
                payload=payload,
            )
        except Exception:
            prompt_for_trace = f"[TOOL_NODE]\ntool_name={tool.name}\npayload={payload}"

        user_msg = WorkflowMessage(
            role="user",
            source_type="system",
            source_id=f"{node_id}_tool_request",
            content=prompt_for_trace,
            metadata={"node_type": "tool", "tool_name": tool.name},
        )
        should_emit_messages = (mode_norm == "full") or emit_messages
        if should_emit_messages:
            ctx.save(user_msg)

        try:
            if isinstance(payload, dict):
                tool_resp = tool.run(**payload)
            elif isinstance(payload, list):
                tool_resp = tool.run(payload)
            else:
                tool_resp = tool.run(payload)
        except Exception as e:
            logger.error(f"[{node_id}] 工具执行失败: {e}")
            write_node_trace(run_dir, node_id, prompt_for_trace, error=str(e))
            fail_structured = NodeOutput(
                result="",
                summary=f"{tool.name} 执行失败",
                confidence=0.0,
                status="fail",
                metadata={
                    "node_type": "tool",
                    "node_id": node_id,
                    "tool_name": tool.name,
                    "error": str(e),
                    "tool_input": payload,
                },
            ).to_dict()
            return _finalize_node_state(
                state=state,
                node_id=node_id,
                node_output=fail_structured,
                output="",
                error=str(e),
                new_messages=[user_msg],
                is_terminal=is_terminal,
            )

        structured = _build_tool_structured_output(
            tool_name=tool.name,
            node_id=node_id,
            payload=payload,
            tool_resp=tool_resp,
        )

        tool_msg = WorkflowMessage(
            role="tool",
            source_type="tool",
            source_id=tool.name,
            content=structured.get("result", ""),
            metadata=structured.get("metadata", {}),
        )
        if should_emit_messages:
            ctx.save(tool_msg)
        elif mode_norm == "minimal" and is_terminal:
            ctx.save(tool_msg)

        write_node_trace(
            run_dir,
            node_id,
            prompt_for_trace,
            raw_response=structured.get("result", ""),
            structured=structured,
        )
        latex_meta_promote: Dict[str, Any] = {}
        inner = structured.get("metadata") if isinstance(structured.get("metadata"), dict) else {}
        tool_md = inner.get("tool_metadata") if isinstance(inner.get("tool_metadata"), dict) else {}
        if tool_md:
            try:
                from latex.constants import (
                    METADATA_LATEX_DIAGNOSTICS,
                    METADATA_LATEX_DIRTY,
                    METADATA_LATEX_PROJECT,
                    METADATA_LATEX_SUGGESTIONS,
                )

                for key in (
                    METADATA_LATEX_PROJECT,
                    METADATA_LATEX_DIAGNOSTICS,
                    METADATA_LATEX_DIRTY,
                    METADATA_LATEX_SUGGESTIONS,
                ):
                    if key in tool_md:
                        latex_meta_promote[key] = tool_md[key]
            except ImportError:
                pass

        return _finalize_node_state(
            state=state,
            node_id=node_id,
            node_output=structured,
            output=structured.get("result", ""),
            error=None,
            new_messages=[user_msg, tool_msg],
            metadata_updates=latex_meta_promote or None,
            is_terminal=is_terminal,
        )

    return tool_node


def make_user_node(
    *,
    node_id: str,
    node_config: dict,
    human_input_provider: Optional[Callable[[str, Dict[str, Any], Dict[str, Any]], Any]] = None,
) -> Callable[[WorkflowState], dict]:
    """
    人机反馈节点工厂（HITL）。

    写回协议同 make_agent_node：只返回增量 delta。
    """
    prompt_template = str(node_config.get("prompt_template", "请提供反馈：")).strip()
    input_schema = node_config.get("input_schema", {"type": "text"})
    if not isinstance(input_schema, dict):
        input_schema = {"type": "text"}
    validation = node_config.get("validation", {})
    if not isinstance(validation, dict):
        validation = {}
    default_value = node_config.get("default_value", "")
    result_summary_template = str(
        node_config.get("result_summary_template", "用户输入节点 {node_id} 已完成")
    ).strip()
    write_to = str(node_config.get("write_to", f"user_feedback.{node_id}")).strip()
    max_attempts = int(node_config.get("max_attempts", 2))
    if max_attempts <= 0:
        max_attempts = 1

    def _default_provider(prompt: str, schema: Dict[str, Any], rules: Dict[str, Any]) -> Any:
        _ = rules
        input_type = schema.get("type", "text")
        options = schema.get("options")
        min_len = rules.get("min_length", 0)
        max_len = rules.get("max_length")
        required = rules.get("required", False)

        width = 70
        print(f"\n{'─' * width}")
        print(f"  [用户输入] 节点: {node_id}")
        print(f"{'─' * width}")

        # 将 prompt 按行打印，超过 width 自动折行
        for line in prompt.splitlines():
            if len(line) <= width - 2:
                print(f"  {line}")
            else:
                # 简单折行
                while line:
                    print(f"  {line[:width - 2]}")
                    line = line[width - 2:]

        if input_type in ("single_choice", "multi_choice") and isinstance(options, list) and options:
            print(f"\n  可选项：")
            for i, opt in enumerate(options, 1):
                print(f"    [{i}] {opt}")
            print(f"\n  输入说明：", end="")
            if input_type == "single_choice":
                print("请输入序号（如 1）或直接输入选项文本")
            else:
                print("多选请用逗号分隔序号（如 1,3）或直接输入选项文本")
        elif input_type == "json":
            print("\n  输入说明：请输入合法 JSON 对象")
        else:
            hints = []
            if required:
                hints.append("必填")
            if min_len:
                hints.append(f"最少 {min_len} 字符")
            if max_len:
                hints.append(f"最多 {max_len} 字符")
            if hints:
                print(f"\n  输入要求：{'，'.join(hints)}")

        print(f"{'─' * width}")

        # 对 single_choice 支持序号输入
        raw = input("  >>> ").strip()

        if input_type in ("single_choice", "multi_choice") and isinstance(options, list) and options:
            # 支持序号输入
            if input_type == "single_choice":
                if raw.isdigit():
                    idx = int(raw) - 1
                    if 0 <= idx < len(options):
                        raw = options[idx]
            else:
                parts = []
                for token in raw.split(","):
                    token = token.strip()
                    if token.isdigit():
                        idx = int(token) - 1
                        if 0 <= idx < len(options):
                            parts.append(options[idx])
                        else:
                            parts.append(token)
                    else:
                        parts.append(token)
                raw = ",".join(parts)

        print(f"  已接收: {raw!r}")
        print(f"{'─' * width}\n")
        return raw

    provider = human_input_provider or _default_provider

    def user_node(state: WorkflowState) -> dict:
        logger.info(f"[{node_id}] 等待用户反馈输入...")
        rendered_prompt = _resolve_tool_payload(prompt_template, state)
        prompt_text = str(rendered_prompt)
        prompt_msg = WorkflowMessage(
            role="system",
            source_type="system",
            source_id=f"{node_id}_prompt",
            content=prompt_text,
            metadata={"node_type": "user", "node_id": node_id},
        )

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
        try:
            result_summary = result_summary_template.format(
                node_id=node_id, status=status, value=value,
            )
        except Exception:
            result_summary = f"用户输入节点 {node_id} 已完成"

        structured = {
            "result": result_str,
            "summary": result_summary,
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
        user_msg = WorkflowMessage(
            role="user",
            source_type="user",
            source_id=node_id,
            content=result_str,
            metadata={"node_type": "user", "status": status},
            payload={"raw_value": value},
        )

        metadata_updates: Dict[str, Any] = {}
        if write_to:
            _set_nested_path(metadata_updates, write_to, value)

        return _finalize_node_state(
            state=state,
            node_id=node_id,
            node_output=structured,
            output=structured["result"],
            error=None if status == "pass" else error,
            new_messages=[prompt_msg, user_msg],
            metadata_updates=metadata_updates if metadata_updates else None,
            is_terminal=False,
        )

    return user_node


def make_parallel_fork_node(
    node_id: str,
    parallel_branches: List[str],
) -> Callable[[WorkflowState], dict]:
    """
    并行分叉节点工厂。

    该节点本身无业务逻辑，仅标记并行组的起始点，
    并将分支列表写入 metadata 供调试追踪。
    真正的分叉由 graph_builder 通过多条 add_edge 实现。
    """
    def parallel_fork_node(state: WorkflowState) -> dict:
        logger.info(f"[{node_id}] 并行分叉启动: branches={parallel_branches}")
        fork_output = NodeOutput(
            result=f"并行分叉: {parallel_branches}",
            summary=f"启动 {len(parallel_branches)} 个并行分支",
            confidence=1.0,
            status="pass",
            metadata={
                "node_type": "parallel_fork",
                "node_id": node_id,
                "branches": parallel_branches,
            },
        ).to_dict()
        return _finalize_node_state(
            state=state,
            node_id=node_id,
            node_output=fork_output,
            output=f"并行分叉: {parallel_branches}",
            error=None,
        )

    return parallel_fork_node


def make_parallel_join_node(
    agent: Optional[BaseAgent],
    ctx: BaseContext,
    node_id: str,
    node_config: dict,
    source_branches: List[str],
    join_policy_str: str = "all_success",
    persona_memory: Optional["UserPersonaMemory"] = None,
    runtime_memory: Optional[Any] = None,
    *,
    default_history_mode: str = DEFAULT_HISTORY_MODE,
    is_terminal: bool = False,
) -> Callable[[WorkflowState], dict]:
    """
    并行汇聚节点工厂。

    执行步骤：
      1. 从 state.metadata 读取所有 source_branches 的结果
      2. 按 join_policy 验证整体成功/失败
      3. 若 config.passthrough_join=true：将各分支 result 纯文本拼接写回，不调用 LLM
      4. 否则：将合并后的分支内容注入 agent context，执行 agent 整合并返回

    Args:
        source_branches:   被汇聚的分支节点 ID 列表
        join_policy_str:   汇聚策略字符串（"all_success" / "partial" / "first_success"）
    """
    from workflow.parallel_merger import JoinPolicy, merge_parallel_results

    try:
        join_policy = JoinPolicy(join_policy_str)
    except ValueError:
        logger.warning(
            f"[{node_id}] 非法 join_policy={join_policy_str!r}，回退为 all_success"
        )
        join_policy = JoinPolicy.ALL_SUCCESS

    # join 节点的 agent 配置：depends_on 设为所有源分支，使 _upstream_blocks 自动填充上下文
    join_node_config = dict(node_config)
    join_node_config.setdefault("depends_on", source_branches)
    if not join_node_config.get("system_prompt"):
        join_node_config["system_prompt"] = (
            f"你是并行结果整合专家，负责整合来自 {source_branches} 的并行分支输出，"
            f"给出综合结论。"
        )
    if not join_node_config.get("subtask"):
        join_node_config["subtask"] = (
            "整合所有并行分支的输出，给出统一的结构化结论。若某分支失败，"
            "在结论中说明影响并尽量基于成功分支给出完整答案。"
        )

    passthrough_join = bool(join_node_config.get("passthrough_join"))
    if passthrough_join:
        base_agent_node = None
    else:
        if agent is None:
            raise ValueError(
                f"[{node_id}] parallel_join 未启用 passthrough_join 时必须提供 agent 实例"
            )
        base_agent_node = make_agent_node(
            agent=agent,
            ctx=ctx,
            node_id=node_id,
            node_config=join_node_config,
            persona_memory=persona_memory,
            runtime_memory=runtime_memory,
            default_history_mode=default_history_mode,
            is_terminal=is_terminal,
            is_entry_node=False,
        )

    def parallel_join_node(state: WorkflowState) -> dict:
        logger.info(
            f"[{node_id}] 并行汇聚: sources={source_branches}, policy={join_policy.value}"
        )
        merged = merge_parallel_results(state, source_branches, join_policy)

        if not merged.success:
            error_msg = (
                f"[{node_id}] 并行汇聚失败 (policy={join_policy.value}): "
                f"{merged.failed_branch_ids} 分支失败。{merged.error_summary}"
            )
            logger.error(error_msg)
            fail_output = NodeOutput(
                result=merged.combined_result,
                summary=f"并行汇聚失败: {merged.failed_branch_ids}",
                confidence=0.0,
                status="fail",
                metadata={
                    "node_type": "parallel_join",
                    "node_id": node_id,
                    "join_policy": join_policy.value,
                    "total_branches": merged.total_branches,
                    "succeeded_branches": merged.succeeded_branches,
                    "failed_branch_ids": merged.failed_branch_ids,
                    "error": error_msg,
                    "branch_outputs": merged.branch_outputs,
                },
            ).to_dict()
            return _finalize_node_state(
                state=state,
                node_id=node_id,
                node_output=fail_output,
                output="",
                error=error_msg,
            )

        logger.info(
            f"[{node_id}] 汇聚成功: {merged.succeeded_branches}/{merged.total_branches} 分支通过"
        )
        if passthrough_join:
            join_output = NodeOutput(
                result=merged.combined_result,
                summary=(
                    f"并行汇聚：{merged.succeeded_branches}/{merged.total_branches} 分支"
                    "（纯文本拼接，无 LLM）"
                ),
                confidence=1.0,
                status="pass",
                metadata={
                    "node_type": "parallel_join",
                    "node_id": node_id,
                    "join_policy": join_policy.value,
                    "total_branches": merged.total_branches,
                    "succeeded_branches": merged.succeeded_branches,
                    "passthrough_join": True,
                    "branch_outputs": merged.branch_outputs,
                },
            ).to_dict()
            return _finalize_node_state(
                state=state,
                node_id=node_id,
                node_output=join_output,
                output=merged.combined_result,
                error=None,
                new_messages=None,
                is_terminal=is_terminal,
            )

        assert base_agent_node is not None
        result = base_agent_node(state)

        # 追加并行汇聚元信息到 metadata delta
        existing_meta = result.get("metadata", {})
        if isinstance(existing_meta, dict) and node_id in existing_meta:
            existing_meta[node_id].setdefault("metadata", {}).update({
                "node_type": "parallel_join",
                "join_policy": join_policy.value,
                "total_branches": merged.total_branches,
                "succeeded_branches": merged.succeeded_branches,
            })
        return result

    return parallel_join_node
