"""
上下文与 Prompt 配置（唯一数据源，Python 模块）。

目录
----
1. 入口路由 ROUTING          — Web mode / workflow 名 → 使用哪个 Profile
2. 全局规则 SHARED           — 意图识别、消息过滤、终节点自动切换规则
3. Plan 规则 PLANNER         — 仅 Plan 模式使用
4. 交付与格式契约 CONTRACTS  — 终节点 brief/full、JSON 输出说明（各 Profile 引用）
5. 四种 Profile 定义 PROFILES — legacy / pipeline / dialogue / auto_single 完整行为

改配置请只改本文件（除非节点 workflow JSON 里有单独 system_prompt）。

对应关系
--------
| Web/CLI 入口 | 典型 Profile   | 用途           |
|--------------|----------------|----------------|
| task 默认    | pipeline       | 通用多节点任务 |
| task checklist_* / latex_* | legacy | 旧 checklist 行为 |
| plan         | dialogue       | 动态规划图     |
| auto         | auto_single    | 单轮轻量对话   |
"""
from __future__ import annotations

import copy
import re
from typing import Any, Dict, List, Optional

# =============================================================================
# Profile 名称常量
# =============================================================================

PROFILE_LEGACY = "legacy"
PROFILE_PIPELINE = "pipeline"
PROFILE_DIALOGUE = "dialogue"
PROFILE_AUTO_SINGLE = "auto_single"

ALL_PROFILES = (
    PROFILE_LEGACY,
    PROFILE_PIPELINE,
    PROFILE_DIALOGUE,
    PROFILE_AUTO_SINGLE,
)

# =============================================================================
# §1 入口路由
# =============================================================================

ROUTING: Dict[str, Any] = {
    "mode_defaults": {
        "auto": PROFILE_AUTO_SINGLE,
        "plan": PROFILE_DIALOGUE,
        "task": PROFILE_PIPELINE,
    },
    "workflow_prefixes": {
        "checklist_": PROFILE_LEGACY,
        "latex_": PROFILE_LEGACY,
        "thesis_": PROFILE_LEGACY,
    },
    "workflow_names": {
        "plan_dynamic": PROFILE_DIALOGUE,
        "auto_single": PROFILE_AUTO_SINGLE,
        "docling_user_test": PROFILE_LEGACY,
        "file_analysis": PROFILE_LEGACY,
    },
    "default_profile": PROFILE_PIPELINE,
}

# =============================================================================
# §2 全局规则（各 Profile 共用）
# =============================================================================

INTENT_PATTERNS: Dict[str, Dict[str, List[str]]] = {
    "echo": {
        "substr": ["原封不动", "原样", "照抄", "逐字", "复述一遍", "echo", "verbatim"],
        "regex": [],
    },
    "persona_write": {
        "substr": ["记住我", "请记住", "保存我的", "更新画像", "记住我是", "个人资料"],
        "regex": [],
    },
    "persona_read": {
        "substr": [],
        "regex": [
            r"^你是谁[？?]?$",
            r"^who are you[？?]?$",
            r"^你叫什么[？?]?$",
            r"^介绍一下你自己[？?]?$",
        ],
    },
    "user_identity": {
        "substr": [],
        "regex": [r"^我是谁[？?]?$", r"^who am i[？?]?$"],
    },
    "persona_intro_merge": {
        "substr": [],
        "regex": [],
    },
    "assistant_nickname": {
        "substr": ["改名叫", "叫你", "称呼你", "你的名字是", "以后你就叫"],
        "regex": [],
    },
    "long_form_delivery": {
        "substr": ["分析", "报告", "论文", "规划", "详细", "完整", "影评", "千字", "万字"],
        "regex": [r"\d+\s*字", r"\d+\s*words?"],
    },
}

PERSONA_REPLY_SKIP: Dict[str, Any] = {
    "min_length": 20,
    "marker_substrings": ["已记录", "已写入用户画像", "用户画像", "个人档案", "已成功记录"],
    "min_marker_hits": 2,
}

MESSAGE_FILTER: Dict[str, Any] = {
    "skip_source_suffixes": ["_prompt_builder"],
    "prompt_builder_body_markers": ["[你的具体任务]", "[原始任务背景]"],
    "dialogue_source_ids": ["chat", "user", "web", "cli"],
    "max_user_line_chars": 2000,
    "max_assistant_line_chars": 2500,
}

TERMINAL_DELIVERY_AUTO: Dict[str, Any] = {
    "short_input_max_chars": 48,
    "question_chars": ["?", "？"],
    "word_count_regex": r"\d+\s*字",
}

# =============================================================================
# §3 Plan 模式专用规则
# =============================================================================

PLANNER: Dict[str, Any] = {
    "extra_principles": [
        "若用户意图匹配 echo（见 INTENT_PATTERNS.echo）：只规划 1 个 agent 终节点，subtask 仅复述用户原文。",
        "除非用户意图匹配 persona_write，否则禁止规划 user_persona_get、user_persona_merge、load_persona、store_persona 等画像工具节点。",
        "节点 subtask 必须贴合用户字面意图，不得擅自改成用户档案复述或画像确认。",
        "简单、一句可答的任务优先 1~2 个 agent 节点。",
        "arxiv_search 受官方限流约束：同一方案内最多 1 次 arxiv_search；禁止 parallel_fork 下挂多个 arxiv_search。tool_input 必须是 2~8 个英文词（如 Agentic RAG），禁止 ${metadata.xxx.summary} 或 result 全文。",
    ],
    "forbidden_persona_tool_names": [
        "user_persona_get",
        "user_persona_merge",
        "load_persona",
        "store_persona",
        "retrieve_user_persona",
    ],
    "persona_subtask_markers": ["记录用户基本信息", "写入用户画像"],
    "persona_task_markers": ["记住", "画像", "个人资料"],
}

# =============================================================================
# §4 契约文案（Profile 通过 terminal_delivery_* / json_format_instruction 引用）
# =============================================================================

JSON_FORMAT_COMPACT: str = """---
【输出格式】只输出一个 JSON 对象，首字符 { 末字符 }。禁止 Markdown 代码块。
{"result":"正文","summary":"摘要","confidence":0.0-1.0}
可选顶层键 persona_memory_update。
---"""

DELIVERY_BRIEF_DEFAULT: str = """
---
[终节点交付判据 · 简答模式]
你是最终交付节点，必须直接回答【本轮用户输入】。

【要求】
1) result 给出直接答案；
2) 充分利用上游要点；若用户明确要求字数（如「3000字」），应尽量满足，不得无故缩短；
3) 用户若要求原样复述，result 仅含用户原文。

【禁止】
- 无关的用户画像罗列（除非用户本轮明确要求）
- 以「已记录」「档案」代替实质回答
- 未看过/未验证的内容声称「已看过」；不确定时应说明
---"""

DELIVERY_FULL_DEFAULT: str = """
---
[终节点交付判据 - 必须严格遵守]
你是最终交付节点，必须直接、全面回答用户的原始问题。

【强制输出要求】
1) 直接结论/答案（先给答案再补细节，不允许开篇就说"根据上游分析"）；
2) 充分利用所有上游节点的完整输出，整合成连贯的最终答案，不得遗漏重要细节；
3) 至少包含一项可执行步骤、具体示例或行动建议；
4) 结构清晰：使用标题/列表/表格等组织信息，不要写成一大段流水文字；
5) 字数要求：result 字段内容不得少于 300 字（中文），必须足够完整；用户若要求更长（如 3000 字），以用户要求为准；
6) 若存在假设或限制，需简明说明（不能作为减少内容的借口）。
7) 段落用正常散文排版：完整段落写在同一段内，禁止「一句一行」或「一句一空行」；仅章节标题前后用空行分隔。
8) 禁止输出 cite、turn0search 等引用占位符或未渲染的检索标记。

【严格禁止】
- 仅复述上游摘要或阶段性说明
- 以"该任务已完成"等敷衍语句结束
- 在答案主体之外反问用户是否需要补充
---"""

# =============================================================================
# §5 四种 Profile（每种模式的全部开关与 Prompt 版式）
# =============================================================================

PROFILES: Dict[str, Dict[str, Any]] = {
    # -------------------------------------------------------------------------
    # legacy — checklist / latex / thesis 等旧 workflow（保持原行为）
    # -------------------------------------------------------------------------
    PROFILE_LEGACY: {
        "title": "旧版 Pipeline（checklist / latex / thesis）",
        "used_by": ["workflow 前缀 checklist_ / latex_ / thesis_"],
        "memory_search_enabled": True,
        "dialogue_max_turns": 6,
        "conv_limit": 12,
        "include_metadata_chain": True,
        "persona_file_write": "always",
        "persona_prompt_read": "always",
        "skip_persona_reply_in_dialogue": False,
        "prompt_layout": {
            "layout": "pipeline_legacy",
            "user_input_label": "[原始任务背景]",
            "task_label": "[你的具体任务]",
            "upstream_label": "[上游节点输出]",
            "history_label": "[历史上下文]",
        },
        "json_format": "full",
        "single_turn_contract": "terminal_only",
        "terminal_delivery_default": "full",
        "terminal_delivery_auto": False,
        "terminal_delivery_brief": DELIVERY_BRIEF_DEFAULT,
        "terminal_delivery_full": DELIVERY_FULL_DEFAULT,
    },
    # -------------------------------------------------------------------------
    # pipeline — 通用 Task（默认）
    # -------------------------------------------------------------------------
    PROFILE_PIPELINE: {
        "title": "通用 Task 流水线",
        "used_by": ["CLI/Web mode=task（未命中 legacy 前缀）"],
        "memory_search_enabled": True,
        "dialogue_max_turns": 3,
        "conv_limit": 12,
        "include_metadata_chain_non_terminal": True,
        "include_metadata_chain_terminal": False,
        "persona_file_write": "on_intent",
        "persona_file_write_intents": ["persona_write"],
        "persona_prompt_read": "on_intent",
        "persona_prompt_read_intents": ["persona_write"],
        "skip_persona_reply_in_dialogue": True,
        "prompt_layout": {
            "layout": "priority_input",
            "user_input_label": "【本轮用户输入 · 最高优先级】",
            "task_label": "[你的具体任务]",
            "upstream_label": "[上游节点输出]",
            "history_label": "[历史上下文]",
            "history_disclaimer": (
                "【仅供参考 · 非本轮任务】以下历史/检索片段若与【本轮用户输入】冲突，"
                "必须以【本轮用户输入】为准。\n"
            ),
        },
        "json_format": "full",
        "single_turn_contract": "terminal_only",
        "terminal_delivery_default": "full",
        "terminal_delivery_auto": True,
        "terminal_delivery_brief": DELIVERY_BRIEF_DEFAULT,
        "terminal_delivery_full": DELIVERY_FULL_DEFAULT,
    },
    # -------------------------------------------------------------------------
    # dialogue — Plan 动态图
    # -------------------------------------------------------------------------
    PROFILE_DIALOGUE: {
        "title": "Plan 对话图",
        "used_by": ["CLI/Web mode=plan", "workflow plan_dynamic"],
        "memory_search_enabled": True,
        "dialogue_max_turns": 4,
        "conv_limit": 12,
        "include_metadata_chain": False,
        "persona_file_write": "on_intent",
        "persona_file_write_intents": ["persona_write"],
        "persona_prompt_read": "on_intent",
        "persona_prompt_read_intents": ["persona_write"],
        "skip_persona_reply_in_dialogue": True,
        "prompt_layout": {
            "layout": "priority_input",
            "user_input_label": "【本轮用户输入 · 最高优先级】",
            "task_label": "[你的具体任务]",
            "upstream_label": "[上游节点输出]",
            "history_label": "[历史上下文]",
            "history_disclaimer": (
                "【仅供参考 · 非本轮任务】以下历史/检索片段若与【本轮用户输入】冲突，"
                "必须以【本轮用户输入】为准。\n"
            ),
        },
        "json_format": "full",
        "single_turn_contract": "terminal_only",
        "terminal_delivery_default": "full",
        "terminal_delivery_auto": True,
        "terminal_delivery_brief": DELIVERY_BRIEF_DEFAULT,
        "terminal_delivery_full": DELIVERY_FULL_DEFAULT,
    },
    # -------------------------------------------------------------------------
    # auto_single — Web/CLI Auto 单节点
    # -------------------------------------------------------------------------
    PROFILE_AUTO_SINGLE: {
        "title": "Auto 单轮对话",
        "used_by": ["CLI/Web mode=auto", "workflow auto_single"],
        "memory_search_enabled": False,
        "mem_limit": 0,
        "dialogue_max_turns": 3,
        "conv_limit": 6,
        "include_metadata_chain": False,
        "persona_file_write": "on_intent",
        "persona_file_write_intents": [
            "persona_write",
            "persona_intro_merge",
            "assistant_nickname",
        ],
        "persona_prompt_read": "on_intent",
        "persona_prompt_read_intents": [
            "persona_write",
            "persona_read",
            "user_identity",
            "persona_intro_merge",
        ],
        "skip_persona_reply_in_dialogue": True,
        "prompt_layout": {
            "layout": "chat_compact",
            "user_input_label": "【用户本轮消息】",
            "history_label": "【近期对话摘要 · 仅供参考】",
        },
        "json_format_instruction": JSON_FORMAT_COMPACT,
        "single_turn_contract": "never",
        "terminal_delivery_default": "brief",
        "terminal_delivery_auto": True,
        "terminal_delivery_brief": DELIVERY_BRIEF_DEFAULT,
        "terminal_delivery_full": DELIVERY_FULL_DEFAULT,
        "node_defaults": {
            "history_mode": "minimal",
            "mem_limit": 0,
            "conv_limit": 6,
            "terminal_delivery_style": "brief",
            "persona_read_in_prompt": None,
        },
        "agent": {
            "node_id": "auto_response",
            "agent_name": "SimpleAgent",
            "system_prompt": (
                "你是本系统的 Auto 对话助手。只回答用户本轮消息；"
                "不要输出与本轮无关的长篇画像说明。"
                "用户明确要求字数时，在 result 中尽量写足，不足则说明并给出可续写方案。"
            ),
            "subtask": "直接回应用户本轮消息。",
        },
    },
}


# =============================================================================
# 组装为 load_context_config() 兼容的 dict（供旧代码 / 可选 JSON 覆盖）
# =============================================================================

_CONFIG_VERSION = 1


def _profiles_for_legacy_dict() -> Dict[str, Any]:
    """导出给 context_settings：保留 prompt_template 键以兼容节点覆盖。"""
    out: Dict[str, Any] = {}
    for name, spec in PROFILES.items():
        p = copy.deepcopy(spec)
        layout = p.get("prompt_layout") or {}
        p["prompt_template"] = layout.get("layout") or "priority_input"
        out[name] = p
    return out


def build_context_config() -> Dict[str, Any]:
    return {
        "version": _CONFIG_VERSION,
        "routing": copy.deepcopy(ROUTING),
        "intent_patterns": copy.deepcopy(INTENT_PATTERNS),
        "persona_reply_skip": copy.deepcopy(PERSONA_REPLY_SKIP),
        "message_filter": copy.deepcopy(MESSAGE_FILTER),
        "terminal_delivery_auto": copy.deepcopy(TERMINAL_DELIVERY_AUTO),
        "planner": copy.deepcopy(PLANNER),
        "profiles": _profiles_for_legacy_dict(),
    }


def resolve_delivery_addon(profile: str, style: str) -> str:
    """按 Profile + brief/full 取终节点交付契约（供 planner_config / nodes 调用）。"""
    s = str(style or "full").strip().lower()
    if s == "none":
        return ""
    spec = PROFILES.get(profile) or PROFILES[PROFILE_PIPELINE]
    if s == "brief":
        return str(spec.get("terminal_delivery_brief") or DELIVERY_BRIEF_DEFAULT)
    return str(spec.get("terminal_delivery_full") or DELIVERY_FULL_DEFAULT)


def user_requests_long_form(text: str) -> bool:
    """用户输入是否应触发长篇交付（字数 / long_form 意图）。"""
    body = str(text or "")
    if not body.strip():
        return False
    wc_pat = TERMINAL_DELIVERY_AUTO.get("word_count_regex") or r"\d+\s*字"
    try:
        if re.search(str(wc_pat), body, re.IGNORECASE):
            return True
    except re.error:
        pass
    for sub in (INTENT_PATTERNS.get("long_form_delivery") or {}).get("substr") or []:
        if sub and str(sub) in body:
            return True
    for pat in (INTENT_PATTERNS.get("long_form_delivery") or {}).get("regex") or []:
        if not pat:
            continue
        try:
            if re.search(str(pat), body, re.IGNORECASE | re.DOTALL):
                return True
        except re.error:
            continue
    return False
