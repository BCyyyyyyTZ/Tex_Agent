"""
AutoAgentsMASPlanner 规划器相关配置。

将规划器的所有可调参数、Prompt 模板与共享工具函数集中于此，
修改配置无需改动 router/planner.py 或 workflow/nodes.py 等业务文件。

此文件是 router 层与 workflow 层的共享依赖，两层均可安全导入（无循环依赖）。
"""
import json
import re
from typing import Any, Dict, List, Optional


# ------------------------------------------------------------------
# LLM 默认参数
# ------------------------------------------------------------------

PLANNER_TEMPERATURE: float = 0.2        # 规划/Supervisor 任务：低随机性，保证结构稳定
# 模型名称不在此定义，统一从 config/settings.py 的 settings.llm_model 读取（对应 .env 的 LLM_MODEL）
NODE_DEFAULT_TEMPERATURE: float = 0.7   # 执行节点：适度创造性
MAX_PLAN_ROUNDS_DEFAULT: int = 6        # PlanAgent ↔ Supervisor 最大迭代轮数
# Supervisor 评分统一采用 1~10 分制；阈值 8 分表示“可通过”基准线。
SUPERVISOR_MIN_QUALITY_SCORE: float = 8.0


# ------------------------------------------------------------------
# 节点强制输出格式指令
# 由 make_agent_node() 统一追加到每个专家 Agent system_prompt 末尾，
# Agent 自身的 system_prompt 不需要（也不应该）包含此内容。
# ------------------------------------------------------------------

NODE_OUTPUT_FORMAT_INSTRUCTION: str = """
---
[强制输出格式 - 必须严格遵守]
你必须且只能输出一个 JSON 对象，禁止在 JSON 外输出任何文本。
绝对禁止输出 Markdown 代码块标记（例如 ```json 或 ```）。
输出首字符必须是 {，末字符必须是 }。

必须包含以下字段（键名不可改）：
{
  "result": "你的完整主要输出内容（字符串，可换行）",
  "summary": "不超过80字的核心摘要",
  "confidence": 0.95,
  "metadata": {}
}
---"""

# 单次流水线执行契约：适用于所有节点，约束“不可等待用户回复、必须继续交付”。
SINGLE_TURN_NODE_CONTRACT: str = """
---
[单次流水线执行契约 - 必须严格遵守]
你当前处于“单次执行”的多节点流水线中，本轮不会等待用户补充信息。
1) 禁止输出等待式追问（如“请先回答我再继续”）。若信息不足，必须显式写出合理默认假设并继续完成当前节点交付。
2) 禁止把任务抛给后续节点或用户（如“下一节点会处理”“请你先提供后我再做”）。
3) 输出必须可直接消费：既要让下游节点能直接使用，也要尽量为终节点形成可交付素材。
4) 如需澄清问题，请将“澄清点”转写为“假设前提 + 风险提示”，而不是向用户发问并等待。
---
"""

# 工作流入口节点（拓扑上的第一个节点）在输出 JSON 中必须携带的画像更新字段说明。
# 实际解析与落盘见 memory.persona_memory.UserPersonaMemory；不实现 tools / function call。
PERSONA_ENTRY_NODE_FORMAT_ADDON: str = """
---
[入口节点专用 - 顶层 JSON 额外字段 | 必须严格遵守]
你是本工作流的第一个执行节点，除 result / summary / confidence / metadata 外，必须在同一 JSON 顶层包含：

  "persona_memory_update": {
    "action": "none" | "merge" | "set" | "clear",
    "delta": { ... },
    "fields": { ... },
    "clear_keys": [ ... ],
    "remove": { ... }
  }

各 action 用法（互斥，只选一种主操作）：

1) action 为 "none"
   - 不修改用户画像文件；其它子字段可省略。

2) action 为 "merge"（追加式更新）
   - "delta"：与原先相同。列表字段为去重追加；字符串字段仅当新值非空时覆盖原值；extra 为键值合并。
   - 可选 "remove"：从列表字段中删除指定条目（字符串与画像中某项去空白后完全一致才删除），例如：
     "remove": { "preferences": ["请用中文回答"], "research_areas": ["旧领域"] }

3) action 为 "set"（整字段覆盖，用于「改偏好」如中文→英文）
   - 必须提供 "fields" 对象，按字段整体写入画像：
     - 字符串类字段（display_name / writing_preferences / latex_preferences / citation_preferences / other_notes）：
       写成空字符串 "" 表示清空该字段。
     - 列表类字段（research_areas / preferences）：整表替换为给定数组（可 [] 清空）。
     - "extra"：传入对象则整体替换 extra；传 null 则 extra 变为 {}。

4) action 为 "clear"（按字段恢复默认空画像）
   - 必须提供 "clear_keys" 字符串数组，如 ["writing_preferences", "preferences"]，
     将对应字段恢复为系统默认值（等同删除该字段上的用户内容）。

示例（用户要求改为英文回答）：
  "persona_memory_update": {
    "action": "set",
    "fields": { "writing_preferences": "请使用英文回答与写作建议。" }
  }
---
"""


# ------------------------------------------------------------------
# 动态图：消息 / 记忆写入策略
# - full：每节点将 prompt 与回复写入 state.messages，并 ctx.save
# - minimal：不在 state.messages 中累积中间轮次；上游依赖走 metadata；仅终端节点 ctx.save
# 长期用户画像由 UserPersonaMemory 单独文件维护，不由各节点写入 BranchMemory。
# 节点可在 NodeConfig.config 中设置 history_mode 覆盖构图时的 default_history_mode。
# ------------------------------------------------------------------

DEFAULT_HISTORY_MODE: str = "minimal"

# ------------------------------------------------------------------
# 运行时上下文注入策略（去重与截断）
# ------------------------------------------------------------------
# 上游节点 result 注入长度上限，避免 history 与 upstream 双通道重复灌入过长内容
UPSTREAM_RESULT_MAX_CHARS: int = 1200
# metadata_chain 中每个节点 result 的展示上限，优先保留 summary，result 仅作补充
METADATA_CHAIN_RESULT_MAX_CHARS: int = 600

# 终节点轻量交付告警：仅日志提示，不阻断执行
FINAL_DELIVERY_GUARD_QUESTION_KEYWORDS: List[str] = [
    "请先回答",
    "请先告诉我",
    "等你回复",
    "等你回答",
    "请补充",
    "是否可以先",
]
FINAL_DELIVERY_GUARD_RESTATE_KEYWORDS: List[str] = [
    "上游",
    "节点",
    "阶段",
    "摘要",
    "总结",
    "复述",
]

FINAL_DELIVERY_SYSTEM_ADDON: str = """
---
[终节点交付判据 - 必须严格遵守]
你是最终交付节点，输出必须直接回答用户原始问题。
输出至少包含：
1) 直接结论/答案（先给答案，再补解释）；
2) 可执行步骤、示例或行动建议（至少一项）；
3) 若存在假设或限制，需简明说明。
禁止仅复述上游摘要或阶段性说明。
---
"""


# ------------------------------------------------------------------
# 复杂度 → Agent 类型映射表
# [BaseRouter 预留接口] BaseRouter 实现后，此表由 router.route() 驱动而非直接查询；
# 映射关系本身可作为 route() 内部决策逻辑的参考标准。
# ------------------------------------------------------------------

COMPLEXITY_AGENT_MAP: Dict[str, str] = {
    "simple":  "SimpleAgent",         # 当前可运行
    "medium":  "ReActAgent",           # 待 ReActAgent 实现后激活
    "complex": "PlanAndSolveAgent",    # 待 PlanAndSolveAgent 实现后激活
}

# 关键词规则（router=None 时 _infer_complexity() 的兜底推断使用）
COMPLEXITY_COMPLEX_KEYWORDS: List[str] = [
    "规划", "分解", "整合", "完整", "全面", "系统性", "架构",
]
COMPLEXITY_MEDIUM_KEYWORDS: List[str] = [
    "分析", "比较", "评估", "检索", "推理", "多步", "综合", "归纳",
]


# ------------------------------------------------------------------
# 已知 Agent 类型名称列表
# [BaseRouter 预留接口] 当新 Agent 类型实现后，在此添加名称即可，
# build_dynamic_graph() 中的降级检测无需任何其他修改。
# ------------------------------------------------------------------

AGENT_TYPE_NAMES: List[str] = ["SimpleAgent", "ReActAgent", "PlanAndSolveAgent"]


# ------------------------------------------------------------------
# PlanAgent / Supervisor LLM 输出 Schema 模板（嵌入 Prompt 中作为格式示例）
# ------------------------------------------------------------------

PLAN_OUTPUT_SCHEMA: str = """{
  "analysis": "<对原始任务的分析，100字以内>",
  "agents": [
    {
      "node_id": "<唯一蛇形命名标识，如 literature_review>",
      "node_type": "<agent 或 tool 或 user>",
      "role": "<该 Agent 的角色名称>",
      "expertise": "<专长简述>",
      "system_prompt": "<agent 节点必填：该 Agent 的完整角色 system prompt，不含输出格式约束>",
      "subtask": "<agent 节点必填：该节点需要完成的具体子任务描述>",
      "output_schema": {
        "result": "<主要输出内容描述>",
        "summary": "<摘要描述>"
      },
      "tool_name": "<tool 节点必填：如 arxiv_search>",
      "tool_input": "<tool 节点必填：建议使用模板 ${metadata.<node_id>.result}>",
      "prompt_template": "<user 节点必填：给用户的提问文本，可使用模板变量>",
      "input_schema": "<user 节点可选：例如 {\"type\":\"text\"} 或 {\"type\":\"single_choice\",\"options\":[...]} >",
      "validation": "<user 节点可选：例如 {\"required\":true,\"min_length\":3}>",
      "default_value": "<user 节点可选：无有效输入时使用>",
      "write_to": "<user 节点可选：写入 metadata 的路径，如 user_feedback.confirm>",
      "depends_on": ["<依赖的前置节点 node_id，无依赖则为空数组>"]
    }
  ],
  "edges": [
    {"from": "<from_node_id>", "to": "<to_node_id>", "condition": null}
  ],
  "entry_node": "<第一个执行的节点 node_id>"
}"""

SUPERVISOR_OUTPUT_SCHEMA: str = """{
  "approved": <true 或 false>,
  "quality_score": <1到10>,
  "issues": ["<问题1>", "<问题2>"],
  "suggestions": "<整体改进建议>",
  "revised_agents": [<若 approved=false，提供修订后的完整 agents 列表，格式同上；approved=true 时可为空数组>],
  "revised_edges": [<若 approved=false，提供修订后的完整 edges；approved=true 时可为空数组>],
  "revised_entry_node": "<若 approved=false，提供修订后的 entry_node；approved=true 时可为空字符串>"
}"""


# ------------------------------------------------------------------
# 共享工具函数：安全解析 LLM 输出 JSON
# 放在此处而非 router/ 或 workflow/ 以避免跨层依赖：
# router/planner.py 和 workflow/nodes.py 均可从 config 安全导入。
# ------------------------------------------------------------------

def parse_llm_json(
    raw: str,
    context: str = "",
    fallback: Optional[Dict] = None,
) -> Dict:
    """
    多级容错解析 LLM 输出的 JSON 字符串。

    尝试顺序：
      1. 直接 json.loads（LLM 严格输出时）
      2. 提取 ```json ... ``` 代码块后解析
      3. 正则抽取第一个完整 {...} 块后解析
      4. 以上均失败 → 返回 fallback 字典并打印警告

    Args:
        raw:      LLM 返回的原始文本。
        context:  调用方标识（用于日志）。
        fallback: 解析失败时的默认返回值（None 时返回空字典）。

    Returns:
        解析成功的字典，或 fallback 字典。
    """
    from utils.logger import get_logger
    logger = get_logger(__name__)

    if fallback is None:
        fallback = {}

    text = _normalize_text(raw)
    if not text:
        logger.warning(f"[{context}] LLM 输出为空，使用兜底值。")
        return fallback

    candidates: List[str] = [text]
    candidates.extend(_extract_code_blocks(text))
    first_obj = _extract_first_balanced_object(text)
    if first_obj:
        candidates.append(first_obj)

    # 尝试 1：原文/代码块/首个对象解析
    for candidate in candidates:
        parsed = _parse_dict_or_wrapped(candidate)
        if parsed is not None:
            return parsed

    # 尝试 2：节点统一输出格式修复（尽量保住 result/summary/confidence）
    recovered = _recover_node_payload(text, fallback)
    if recovered is not None:
        logger.warning(
            f"[{context}] JSON 解析失败，但字段修复成功。"
            f"原始输出前200字：{text[:200]}"
        )
        return recovered

    logger.warning(
        f"[{context}] JSON 解析全部失败，使用兜底值。"
        f"原始输出前200字：{text[:200]}"
    )
    return fallback


def _normalize_text(raw: Any) -> str:
    if raw is None:
        return ""
    return str(raw).strip().lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")


def _parse_dict_or_wrapped(candidate: str) -> Optional[Dict[str, Any]]:
    candidate = candidate.strip()
    if not candidate:
        return None
    try:
        parsed = json.loads(candidate)
    except (json.JSONDecodeError, TypeError):
        return None
    if isinstance(parsed, dict):
        return parsed
    if isinstance(parsed, str):
        inner = _normalize_text(parsed)
        if inner.startswith("{") and inner.endswith("}"):
            try:
                inner_parsed = json.loads(inner)
                if isinstance(inner_parsed, dict):
                    return inner_parsed
            except (json.JSONDecodeError, TypeError):
                return None
    return None


def _extract_code_blocks(text: str) -> List[str]:
    blocks: List[str] = []
    for match in re.finditer(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE):
        body = match.group(1).strip()
        if body:
            blocks.append(body)
    return blocks


def _extract_first_balanced_object(text: str) -> Optional[str]:
    n = len(text)
    i = 0
    while i < n:
        if text[i] != "{":
            i += 1
            continue
        start = i
        depth = 0
        in_str = False
        escaped = False
        j = i
        while j < n:
            ch = text[j]
            if escaped:
                escaped = False
                j += 1
                continue
            if ch == "\\":
                escaped = True
                j += 1
                continue
            if ch == '"':
                in_str = not in_str
                j += 1
                continue
            if in_str:
                j += 1
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[start:j + 1]
            j += 1
        i += 1
    return None


def _recover_node_payload(raw: str, fallback: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    key_hits = sum(1 for k in ('"result"', '"summary"', '"confidence"') if k in raw)
    if key_hits == 0:
        return None

    out = dict(fallback or {})
    extracted_any = False

    result_val = _extract_string_field(raw, "result")
    if result_val is not None:
        out["result"] = result_val
        extracted_any = True

    summary_val = _extract_string_field(raw, "summary")
    if summary_val is not None:
        out["summary"] = summary_val
        extracted_any = True

    conf_val = _extract_numeric_field(raw, "confidence")
    if conf_val is not None:
        out["confidence"] = max(0.0, min(1.0, conf_val))
        extracted_any = True

    meta_val = _extract_object_field(raw, "metadata")
    if meta_val is not None:
        out["metadata"] = meta_val
        extracted_any = True

    pm_val = _extract_object_field(raw, "persona_memory_update")
    if pm_val is not None:
        out["persona_memory_update"] = pm_val
        extracted_any = True

    return out if extracted_any else None


def _extract_string_field(raw: str, field: str) -> Optional[str]:
    marker = f'"{field}"'
    idx = raw.find(marker)
    if idx < 0:
        return None
    idx = raw.find(":", idx + len(marker))
    if idx < 0:
        return None
    i = idx + 1
    while i < len(raw) and raw[i].isspace():
        i += 1
    if i >= len(raw) or raw[i] != '"':
        return None
    candidate = raw[i:]
    try:
        decoder = json.JSONDecoder()
        value, _ = decoder.raw_decode(candidate)
        if isinstance(value, str):
            return value
        return str(value)
    except (json.JSONDecodeError, TypeError):
        return None


def _extract_numeric_field(raw: str, field: str) -> Optional[float]:
    m = re.search(rf'"{re.escape(field)}"\s*:\s*([0-9]+(?:\.[0-9]+)?)', raw)
    if not m:
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None


def _extract_object_field(raw: str, field: str) -> Optional[Dict[str, Any]]:
    marker = f'"{field}"'
    idx = raw.find(marker)
    if idx < 0:
        return None
    idx = raw.find(":", idx + len(marker))
    if idx < 0:
        return None
    sub = raw[idx + 1:]
    obj = _extract_first_balanced_object(sub)
    if not obj:
        return None
    return _parse_dict_or_wrapped(obj)
