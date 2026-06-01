"""
上下文运行时：从 config.context_profiles 读取配置并合并节点覆盖。
配置正文请只编辑 context_profiles.py，不要在本文件写策略字符串。
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from config.context_profiles import (
    ALL_PROFILES,
    PROFILE_AUTO_SINGLE,
    PROFILE_DIALOGUE,
    PROFILE_LEGACY,
    PROFILE_PIPELINE,
    PROFILES,
    build_context_config,
    user_requests_long_form,
)
from config.planner_config import NODE_OUTPUT_FORMAT_INSTRUCTION

# 对外常量（与 context_profiles 一致）
__all__ = [
    "PROFILE_LEGACY",
    "PROFILE_PIPELINE",
    "PROFILE_DIALOGUE",
    "PROFILE_AUTO_SINGLE",
    "NodeContextBehavior",
    "load_context_config",
    "reload_context_config",
    "valid_profiles",
    "resolve_graph_context_profile",
    "resolve_node_context_profile",
    "match_intent",
    "match_any_intent",
    "resolve_node_context_behavior",
    "resolve_terminal_delivery_style",
    "get_json_format_instruction",
    "get_planner_extra_principles",
    "get_planner_local_config",
    "get_profile_node_defaults",
    "get_profile_agent_spec",
    "get_message_filter_config",
    "memory_search_enabled",
    "default_include_metadata_chain",
    "dialogue_max_turns",
    "build_agent_prompt",
    "filter_messages_for_memory",
    "format_dialogue_history",
    "should_save_assistant_to_dialogue_context",
    "is_persona_confirmation_reply",
    "make_dialogue_save_messages",
    "should_persona_file_write",
]


@dataclass
class NodeContextBehavior:
    """合并 profile 默认值 + 节点 config 覆盖后的运行时行为。"""

    profile: str
    memory_search_enabled: bool = True
    dialogue_max_turns: int = 4
    include_metadata_chain: bool = False
    persona_file_write: bool = False
    persona_prompt_read: bool = False
    skip_persona_reply_in_dialogue: bool = True
    prompt_template: str = "priority_input"
    json_format_instruction: str = ""
    single_turn_contract: str = "terminal_only"
    terminal_delivery_style: str = "full"
    mem_limit: int = 5
    conv_limit: int = 12


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _optional_json_override_path() -> Optional[Path]:
    raw = __import__("os").getenv("CONTEXT_CONFIG_PATH", "").strip()
    if not raw:
        return None
    p = Path(raw)
    return p if p.is_absolute() else _project_root() / p


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(base)
    for k, v in override.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


@lru_cache(maxsize=1)
def load_context_config() -> Dict[str, Any]:
    """返回完整配置 dict；默认来自 context_profiles，可选 JSON 覆盖。"""
    cfg = build_context_config()
    path = _optional_json_override_path()
    if path and path.is_file():
        with path.open("r", encoding="utf-8") as f:
            override = json.load(f)
        if isinstance(override, dict):
            cfg = _deep_merge(cfg, override)
    return cfg


def reload_context_config() -> Dict[str, Any]:
    load_context_config.cache_clear()
    return load_context_config()


def valid_profiles() -> frozenset:
    return frozenset(ALL_PROFILES)


def resolve_graph_context_profile(
    workflow_name: str,
    *,
    explicit: Optional[str] = None,
    mode: Optional[str] = None,
) -> str:
    cfg = load_context_config()
    if explicit and str(explicit).strip().lower() in valid_profiles():
        return str(explicit).strip().lower()

    routing = cfg.get("routing") or {}
    mode_l = str(mode or "").strip().lower()
    mode_defaults = routing.get("mode_defaults") or {}

    wl_lower = str(workflow_name or "").strip().lower()
    for name, prof in (routing.get("workflow_names") or {}).items():
        if wl_lower == str(name).lower():
            return str(prof)
    for prefix, prof in (routing.get("workflow_prefixes") or {}).items():
        if wl_lower.startswith(str(prefix).lower()):
            return str(prof)

    if mode_l and mode_l in mode_defaults:
        return str(mode_defaults[mode_l])
    return str(routing.get("default_profile") or PROFILE_PIPELINE)


def resolve_node_context_profile(
    node_config: Dict[str, Any],
    *,
    graph_profile: str,
) -> str:
    raw = node_config.get("context_profile")
    if raw and str(raw).strip().lower() in valid_profiles():
        return str(raw).strip().lower()
    return graph_profile


def _profile_spec(profile: str) -> Dict[str, Any]:
    cfg = load_context_config()
    spec = (cfg.get("profiles") or {}).get(profile)
    if not isinstance(spec, dict):
        spec = PROFILES.get(profile)
    if not isinstance(spec, dict):
        raise KeyError(f"未知 context profile: {profile}")
    return spec


def match_intent(intent_name: str, text: str) -> bool:
    cfg = load_context_config()
    patterns = (cfg.get("intent_patterns") or {}).get(intent_name) or {}
    if not isinstance(patterns, dict):
        return False
    body = str(text or "")
    for sub in patterns.get("substr") or []:
        if sub and str(sub) in body:
            return True
    for pat in patterns.get("regex") or []:
        if not pat:
            continue
        try:
            if re.search(str(pat), body, re.IGNORECASE | re.DOTALL):
                return True
        except re.error:
            continue
    return False


def match_any_intent(intent_names: List[str], text: str) -> bool:
    return any(match_intent(n, text) for n in intent_names)


def _resolve_bool_policy(
    policy: str,
    intent_names: List[str],
    text: str,
    *,
    node_override: Any = None,
) -> bool:
    if node_override is True:
        return True
    if node_override is False:
        return False
    p = str(policy or "never").strip().lower()
    if p == "always":
        return True
    if p == "never":
        return False
    if p == "on_intent":
        return match_any_intent(intent_names, text)
    return False


def is_persona_confirmation_reply(text: str) -> bool:
    cfg = load_context_config().get("persona_reply_skip") or {}
    t = str(text or "").strip()
    min_len = int(cfg.get("min_length", 20) or 20)
    if len(t) < min_len:
        return False
    markers = cfg.get("marker_substrings") or []
    hits = sum(1 for m in markers if m and str(m) in t)
    need = int(cfg.get("min_marker_hits", 2) or 2)
    return hits >= need


def resolve_terminal_delivery_style(
    user_input: str,
    node_config: Dict[str, Any],
    *,
    profile: str,
    is_terminal: bool,
) -> str:
    if not is_terminal:
        return "none"
    explicit = str(node_config.get("terminal_delivery_style") or "").strip().lower()
    if explicit in ("brief", "full", "none"):
        return explicit

    spec = _profile_spec(profile)
    default = str(spec.get("terminal_delivery_default") or "full").strip().lower()
    base = default if default in ("brief", "full", "none") else "full"

    if not spec.get("terminal_delivery_auto", True):
        return base

    if match_intent("echo", user_input):
        return "brief"
    if user_requests_long_form(user_input):
        return "full"

    auto_cfg = load_context_config().get("terminal_delivery_auto") or {}
    t = str(user_input or "").strip()
    max_short = int(auto_cfg.get("short_input_max_chars", 48) or 48)
    q_chars = auto_cfg.get("question_chars") or ["?", "？"]
    if len(t) <= max_short and not any(q in t for q in q_chars):
        if not match_intent("long_form_delivery", t):
            return "brief"
    return base


def get_json_format_instruction(key: str, *, profile: Optional[str] = None) -> str:
    if profile:
        spec = _profile_spec(profile)
        inline = spec.get("json_format_instruction")
        if inline is not None and str(inline).strip():
            return str(inline)
    if key == "full" or not key:
        return NODE_OUTPUT_FORMAT_INSTRUCTION
    return NODE_OUTPUT_FORMAT_INSTRUCTION


def get_planner_extra_principles() -> List[str]:
    planner = load_context_config().get("planner") or {}
    items = planner.get("extra_principles") or []
    return [str(x) for x in items if str(x).strip()]


def get_planner_local_config() -> Dict[str, Any]:
    p = load_context_config().get("planner") or {}
    return p if isinstance(p, dict) else {}


def get_profile_node_defaults(profile: str) -> Dict[str, Any]:
    spec = _profile_spec(profile)
    nd = spec.get("node_defaults")
    return dict(nd) if isinstance(nd, dict) else {}


def get_profile_agent_spec(profile: str) -> Dict[str, Any]:
    spec = _profile_spec(profile)
    agent = spec.get("agent")
    return dict(agent) if isinstance(agent, dict) else {}


def resolve_node_context_behavior(
    node_config: Dict[str, Any],
    *,
    graph_profile: str,
    user_input: str,
    is_terminal: bool,
) -> NodeContextBehavior:
    profile = resolve_node_context_profile(node_config, graph_profile=graph_profile)
    spec = _profile_spec(profile)

    write_intents = list(spec.get("persona_file_write_intents") or ["persona_write"])
    read_intents = list(spec.get("persona_prompt_read_intents") or ["persona_write"])

    persona_write = _resolve_bool_policy(
        str(spec.get("persona_file_write", "never")),
        write_intents,
        user_input,
        node_override=node_config.get("persona_writeback"),
    )
    persona_read = _resolve_bool_policy(
        str(spec.get("persona_prompt_read", "never")),
        read_intents,
        user_input,
        node_override=node_config.get("persona_read_in_prompt"),
    )

    if "include_metadata_chain" in node_config:
        incl_chain = bool(node_config.get("include_metadata_chain"))
    elif "include_metadata_chain" in spec:
        incl_chain = bool(spec.get("include_metadata_chain"))
    elif is_terminal:
        incl_chain = bool(spec.get("include_metadata_chain_terminal", False))
    else:
        incl_chain = bool(spec.get("include_metadata_chain_non_terminal", False))

    mem_enabled = spec.get("memory_search_enabled", True)
    if "memory_search_enabled" in node_config:
        mem_enabled = bool(node_config.get("memory_search_enabled"))

    mem_limit = int(node_config.get("mem_limit", spec.get("mem_limit", 5)) or 0)
    if not mem_enabled:
        mem_limit = 0

    delivery = resolve_terminal_delivery_style(
        user_input, node_config, profile=profile, is_terminal=is_terminal
    )

    layout = spec.get("prompt_layout") or {}
    prompt_template_key = str(
        node_config.get("prompt_template", layout.get("layout", "priority_input"))
    )

    json_instr = spec.get("json_format_instruction")
    if json_instr is None:
        json_instr = get_json_format_instruction(
            str(node_config.get("json_format", spec.get("json_format", "full")))
        )
    else:
        json_instr = str(json_instr)

    return NodeContextBehavior(
        profile=profile,
        memory_search_enabled=bool(mem_enabled),
        dialogue_max_turns=int(
            node_config.get("dialogue_max_turns", spec.get("dialogue_max_turns", 4)) or 4
        ),
        include_metadata_chain=incl_chain,
        persona_file_write=persona_write,
        persona_prompt_read=persona_read,
        skip_persona_reply_in_dialogue=bool(
            spec.get("skip_persona_reply_in_dialogue", True)
        ),
        prompt_template=prompt_template_key,
        json_format_instruction=json_instr,
        single_turn_contract=str(
            node_config.get(
                "single_turn_contract", spec.get("single_turn_contract", "terminal_only")
            )
        ),
        terminal_delivery_style=delivery,
        mem_limit=mem_limit,
        conv_limit=int(node_config.get("conv_limit", spec.get("conv_limit", 12)) or 12),
    )


def get_message_filter_config() -> Dict[str, Any]:
    mf = load_context_config().get("message_filter") or {}
    return mf if isinstance(mf, dict) else {}


def memory_search_enabled(node_config: Dict[str, Any], profile: str) -> bool:
    b = resolve_node_context_behavior(
        node_config, graph_profile=profile, user_input="", is_terminal=False
    )
    return b.memory_search_enabled


def default_include_metadata_chain(
    profile: str, *, is_terminal: bool, node_config: Dict[str, Any]
) -> bool:
    if "include_metadata_chain" in node_config:
        return bool(node_config.get("include_metadata_chain"))
    spec = _profile_spec(profile)
    if "include_metadata_chain" in spec:
        return bool(spec.get("include_metadata_chain"))
    if is_terminal:
        return bool(spec.get("include_metadata_chain_terminal", False))
    return bool(spec.get("include_metadata_chain_non_terminal", False))


def dialogue_max_turns(profile: str) -> int:
    return int(_profile_spec(profile).get("dialogue_max_turns", 4) or 4)


def _get_prompt_layout(profile: str, behavior: NodeContextBehavior) -> Dict[str, str]:
    spec = _profile_spec(profile)
    layout = spec.get("prompt_layout")
    if isinstance(layout, dict) and layout:
        return {str(k): str(v) for k, v in layout.items()}
    cfg = load_context_config()
    templates = cfg.get("prompt_templates") or {}
    t = templates.get(behavior.prompt_template) or templates.get("priority_input") or {}
    return t if isinstance(t, dict) else {}


def build_agent_prompt(
    *,
    user_input: str,
    subtask: str,
    upstream_ctx: str,
    built_context: str,
    inline_contracts: str,
    behavior: NodeContextBehavior,
) -> str:
    tpl = _get_prompt_layout(behavior.profile, behavior)
    layout = str(tpl.get("layout") or "priority_input")
    empty_history = "（无历史上下文）"
    history = (built_context or "").strip() or empty_history

    if layout == "pipeline_legacy":
        task_block = subtask or user_input
        return (
            f"{tpl.get('task_label', '[你的具体任务]')}\n{task_block}\n\n"
            f"{tpl.get('upstream_label', '[上游节点输出]')}\n"
            f"{upstream_ctx.strip() or '（无上游节点输出）'}\n\n"
            f"{tpl.get('user_input_label', '[原始任务背景]')}\n{user_input}\n\n"
            f"{tpl.get('history_label', '[历史上下文]')}\n{history}\n\n"
            f"{inline_contracts}\n"
        )

    if layout == "chat_compact":
        hist_block = ""
        if history != empty_history:
            hist_block = (
                f"{tpl.get('history_label', '【近期对话摘要】')}\n{history}\n\n"
            )
        return (
            f"{tpl.get('user_input_label', '【用户本轮消息】')}\n{user_input}\n\n"
            f"{hist_block}"
            f"{inline_contracts}\n"
        )

    task_block = subtask or user_input
    disclaimer = str(tpl.get("history_disclaimer") or "")
    return (
        f"{tpl.get('user_input_label', '【本轮用户输入】')}\n{user_input}\n\n"
        f"{tpl.get('task_label', '[你的具体任务]')}\n{task_block}\n\n"
        f"{tpl.get('upstream_label', '[上游节点输出]')}\n"
        f"{upstream_ctx.strip() or '（无上游节点输出）'}\n\n"
        f"{disclaimer}"
        f"{tpl.get('history_label', '[历史上下文]')}\n{history}\n\n"
        f"{inline_contracts}\n"
    )


def _is_prompt_builder_message(msg: Any, mf: Dict[str, Any]) -> bool:
    from core.message import WorkflowMessage, ensure_message

    m = msg if isinstance(msg, WorkflowMessage) else ensure_message(
        msg, default_role="assistant", default_source_type="system", default_source_id="session"
    )
    sid = str(m.source_id or "")
    for suf in mf.get("skip_source_suffixes") or []:
        if sid.endswith(str(suf)):
            return True
    body = str(m.content or "")
    markers = mf.get("prompt_builder_body_markers") or []
    if len(markers) >= 2 and markers[0] in body and markers[1] in body:
        return True
    return False


def _normalize_dialogue_source_type(
    role: str,
    source_type: Optional[str],
) -> Literal["agent", "tool", "user", "system"]:
    """对话通道标识在 source_id（如 chat）；source_type 必须是协议四值之一。"""
    st = str(source_type or "").strip().lower()
    if st == "chat":
        st = ""
    if st in ("agent", "tool", "user"):
        return st  # type: ignore[return-value]
    if st == "system":
        return "user" if role == "user" else "agent"
    return "user" if role == "user" else "agent"


def _extract_dialogue_text(msg: Any, mf: Dict[str, Any], *, profile: str) -> Optional[str]:
    from core.message import WorkflowMessage, ensure_message
    from config.planner_config import parse_llm_json

    m = msg if isinstance(msg, WorkflowMessage) else ensure_message(
        msg, default_role="assistant", default_source_type="system", default_source_id="session"
    )
    if _is_prompt_builder_message(m, mf):
        return None
    dialogue_ids = set(str(x) for x in (mf.get("dialogue_source_ids") or []))
    if m.source_type in ("system",) and m.role != "user":
        if str(m.source_id or "") not in dialogue_ids:
            return None
    body = str(m.content or "").strip()
    if not body:
        return None
    max_user = int(mf.get("max_user_line_chars", 2000) or 2000)
    max_asst = int(mf.get("max_assistant_line_chars", 2500) or 2500)
    spec = _profile_spec(profile) if profile in valid_profiles() else {}
    skip_persona = bool(spec.get("skip_persona_reply_in_dialogue", False))

    if m.role == "user":
        if len(body) <= max_user and (mf.get("prompt_builder_body_markers") or ["[你的具体任务]"])[0] not in body[:200]:
            return body
        return None
    if m.role == "assistant":
        if body.startswith("{") and "result" in body:
            try:
                parsed = parse_llm_json(body, context="dialogue_history", fallback={})
                r = str(parsed.get("result") or "").strip()
                if r and not (skip_persona and is_persona_confirmation_reply(r)):
                    return r[:max_asst]
            except Exception:  # noqa: BLE001
                pass
        if skip_persona and is_persona_confirmation_reply(body):
            return None
        if len(body) <= max_asst and "persona_memory_update" not in body[:300]:
            return body[:max_asst]
    return None


def filter_messages_for_memory(msgs_raw: List[Any], profile: str) -> List[Any]:
    from core.message import WorkflowMessage, ensure_message

    mf = get_message_filter_config()
    if profile == PROFILE_LEGACY:
        return [
            ensure_message(m, default_role="assistant", default_source_type="system", default_source_id="session")
            for m in msgs_raw
        ]
    out: List[WorkflowMessage] = []
    suffixes = tuple(str(s) for s in (mf.get("skip_source_suffixes") or []))
    for raw in msgs_raw:
        msg = ensure_message(
            raw,
            default_role="assistant",
            default_source_type="system",
            default_source_id="session",
        )
        text = _extract_dialogue_text(msg, mf, profile=profile)
        if not text:
            continue
        sid = msg.source_id if not str(msg.source_id or "").endswith(suffixes) else "chat"
        out.append(
            WorkflowMessage(
                role=msg.role,
                source_type=_normalize_dialogue_source_type(msg.role, msg.source_type),
                source_id=sid,
                content=text,
                metadata=dict(msg.metadata or {}),
            )
        )
    return out


def format_dialogue_history(messages: List[Any], max_turns: int) -> str:
    from core.message import ensure_message

    if not messages:
        return ""
    lines: List[str] = []
    window = messages[-max(1, max_turns) * 2 :]
    prev: Optional[str] = None
    for raw in window:
        msg = ensure_message(
            raw,
            default_role="assistant",
            default_source_type="agent",
            default_source_id="chat",
        )
        role = "用户" if msg.role == "user" else "助手"
        line = f"{role}: {str(msg.content or '').strip()}"
        if line == prev:
            continue
        prev = line
        lines.append(line)
    return "\n".join(lines)


def should_save_assistant_to_dialogue_context(result_text: str, behavior: NodeContextBehavior) -> bool:
    if not behavior.skip_persona_reply_in_dialogue:
        return True
    return not is_persona_confirmation_reply(result_text)


def should_persona_file_write(user_input: str, profile: str) -> bool:
    """当前 profile + 用户输入是否应写 user_persona.json。"""
    b = resolve_node_context_behavior(
        {},
        graph_profile=profile,
        user_input=user_input,
        is_terminal=False,
    )
    return b.persona_file_write


def make_dialogue_save_messages(user_input: str, result_text: str) -> tuple:
    from core.message import WorkflowMessage

    u = WorkflowMessage(
        role="user",
        source_type="user",
        source_id="chat",
        content=str(user_input or "").strip(),
        metadata={"channel": "dialogue"},
    )
    a = WorkflowMessage(
        role="assistant",
        source_type="agent",
        source_id="chat",
        content=str(result_text or "").strip()[:4000],
        metadata={"channel": "dialogue"},
    )
    return u, a
