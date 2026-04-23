"""
AutoAgentsMASPlanner 规划器相关配置（v2）。

Breaking Change v2：
  - PLAN_OUTPUT_SCHEMA 支持并行（parallel_fork / parallel_join）和条件边
  - SUPERVISOR_OUTPUT_SCHEMA 覆盖并行 / 条件边有效性检查
  - 移除旧的"图必须是严格单链"约束（改为推荐默认值，允许并行）
  - 新增 JOIN_POLICY_VALUES / CONDITION_OP_VALUES 常量供 schema 引用
"""
import json
import re
from typing import Any, Dict, List, Optional


# ------------------------------------------------------------------
# LLM 默认参数
# ------------------------------------------------------------------

PLANNER_TEMPERATURE: float = 0.2
NODE_DEFAULT_TEMPERATURE: float = 0.7
MAX_PLAN_ROUNDS_DEFAULT: int = 6
SUPERVISOR_MIN_QUALITY_SCORE: float = 8.0


# ------------------------------------------------------------------
# 并行 / 条件边约束常量
# ------------------------------------------------------------------

JOIN_POLICY_VALUES: List[str] = ["all_success", "partial", "first_success"]
CONDITION_OP_VALUES: List[str] = [
    "eq", "ne", "gt", "gte", "lt", "lte",
    "in", "not_in", "contains", "exists", "not_exists",
]


# ------------------------------------------------------------------
# 节点强制输出格式指令
# ------------------------------------------------------------------

NODE_OUTPUT_FORMAT_INSTRUCTION: str = """
---
[强制输出格式 - 必须严格遵守]
你必须且只能输出一个合法的 JSON 对象，禁止在 JSON 之外输出任何文字（包括解释、前言、后记）。
绝对禁止输出 Markdown 代码块标记（例如 ```json 或 ```）。
输出首字符必须是 {，末字符必须是 }。

```json
{
  "result": "你的完整主要输出内容（字符串，可换行）",
  "summary": "不超过200字的核心摘要",
  "confidence": 0.00-1.00,
  "metadata": {}
}
```
---"""

SINGLE_TURN_NODE_CONTRACT: str = """
---
[单次流水线执行契约 - 必须严格遵守]
你当前处于"单次执行"的多节点流水线中，本轮不会等待用户补充信息。
1) 禁止输出等待式追问（如"请先回答我再继续"）。若信息不足，必须显式写出合理默认假设并继续完成当前节点交付。
2) 禁止把任务抛给后续节点或用户（如"下一节点会处理""请你先提供后我再做"）。
3) 输出必须可直接消费：既要让下游节点能直接使用，也要尽量为终节点形成可交付素材。
4) 如需澄清问题，请将"澄清点"转写为"假设前提 + 风险提示"，而不是向用户发问并等待。
---
"""

DEFAULT_SINGLE_TURN_CONTRACT_MODE: str = "terminal_only"

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
   - 可选 "remove"：从列表字段中删除指定条目。

3) action 为 "set"（整字段覆盖）
   - 必须提供 "fields" 对象，按字段整体写入画像。

4) action 为 "clear"（按字段恢复默认空画像）
   - 必须提供 "clear_keys" 字符串数组。
---
"""

FINAL_DELIVERY_SYSTEM_ADDON: str = """
---
[终节点交付判据 - 必须严格遵守]
你是最终交付节点，必须直接、全面回答用户的原始问题。

【强制输出要求】
1) 直接结论/答案（先给答案再补细节，不允许开篇就说"根据上游分析"）；
2) 充分利用所有上游节点的完整输出，整合成连贯的最终答案，不得遗漏重要细节；
3) 至少包含一项可执行步骤、具体示例或行动建议；
4) 结构清晰：使用标题/列表/表格等组织信息，不要写成一大段流水文字；
5) 字数要求：result 字段内容不得少于 300 字（中文），必须足够完整；
6) 若存在假设或限制，需简明说明（不能作为减少内容的借口）。

【严格禁止】
- 仅复述上游摘要或阶段性说明
- 以"该任务已完成"等敷衍语句结束
- 在答案主体之外反问用户是否需要补充
---
"""


# ------------------------------------------------------------------
# 消息 / 记忆写入策略
# ------------------------------------------------------------------

DEFAULT_HISTORY_MODE: str = "minimal"
# 上游结果传递给下游时的最大字符数（提升到 8192 以尽量保留完整上下文）
UPSTREAM_RESULT_MAX_CHARS: int = 8192
METADATA_CHAIN_RESULT_MAX_CHARS: int = 4096

FINAL_DELIVERY_GUARD_QUESTION_KEYWORDS: List[str] = [
    "请先回答", "请先告诉我", "等你回复", "等你回答", "请补充", "是否可以先",
]
FINAL_DELIVERY_GUARD_RESTATE_KEYWORDS: List[str] = [
    "上游", "节点", "阶段", "摘要", "总结", "复述",
]


# ------------------------------------------------------------------
# 复杂度 → Agent 类型映射表
# ------------------------------------------------------------------

COMPLEXITY_AGENT_MAP: Dict[str, str] = {
    "simple": "SimpleAgent",
    "medium": "ReActAgent",
    "complex": "PlanAndSolveAgent",
}
COMPLEXITY_COMPLEX_KEYWORDS: List[str] = [
    "规划", "分解", "整合", "完整", "全面", "系统性", "架构",
]
COMPLEXITY_MEDIUM_KEYWORDS: List[str] = [
    "分析", "比较", "评估", "检索", "推理", "多步", "综合", "归纳",
]
AGENT_TYPE_NAMES: List[str] = ["SimpleAgent", "SimpleAgent_new", "ReActAgent", "PlanAndSolveAgent"]


# ------------------------------------------------------------------
# PlanAgent / Supervisor LLM 输出 Schema（v2：支持并行 + 条件边）
# ------------------------------------------------------------------

PLAN_OUTPUT_SCHEMA: str = """{
  "analysis": "<对原始任务的分析>",
  "agents": [
    {
      "node_id": "<唯一蛇形命名标识，如 literature_review>",
      "node_type": "<agent | tool | user | parallel_fork | parallel_join>",
      "role": "<该节点的角色名称>",
      "expertise": "<专长简述（agent 节点）>",
      "system_prompt": "<agent/parallel_join 节点必填：完整角色 system prompt，不含输出格式约束>",
      "subtask": "<agent/parallel_join 节点必填：具体子任务描述>",
      "output_schema": {
        "result": "<主要输出内容描述>",
        "summary": "<摘要描述>"
      },
      "tool_name": "<tool 节点必填：如 arxiv_search>",
      "tool_input": "<tool 节点必填：建议使用模板 ${metadata.<node_id>.result}>",
      "prompt_template": "<user 节点必填：给用户的提问文本>",
      "input_schema": "<user 节点可选：{\"type\":\"text\"} 或 {\"type\":\"single_choice\",\"options\":[...]}>",
      "validation": "<user 节点可选：{\"required\":true}>",
      "default_value": "<user 节点可选>",
      "write_to": "<user 节点可选：metadata 写入路径>",
      "parallel_branches": ["<parallel_fork 节点必填：分支节点 node_id 列表>"],
      "source_branches": ["<parallel_join 节点必填：被汇聚的分支节点 node_id 列表>"],
      "join_policy": "<parallel_join 节点可选：all_success | partial | first_success，默认 all_success>",
      "depends_on": ["<依赖的前置节点 node_id>"]
    }
  ],
  "edges": [
    {
      "from": "<from_node_id>",
      "to": "<to_node_id>",
      "condition": null,
      "priority": 0
    },
    {
      "from": "<from_node_id_with_condition>",
      "to": "<branch_a_node_id>",
      "condition": {
        "field": "metadata.<node_id>.confidence",
        "op": "gte",
        "value": 0.7
      },
      "priority": 1
    },
    {
      "from": "<from_node_id_with_condition>",
      "to": "<fallback_node_id>",
      "condition": null,
      "priority": 0
    }
  ],
  "entry_node": "<第一个执行的节点 node_id>"
}

【并行分叉/汇聚的正确示例 - 必须完全遵照此结构】
当任务需要并行执行时（例如同时分析多个维度），使用如下完整结构：

  "agents": [
    {"node_id": "fork_node", "node_type": "parallel_fork", "role": "分叉控制", "parallel_branches": ["branch_a", "branch_b"]},
    {"node_id": "branch_a", "node_type": "agent", "system_prompt": "...", "subtask": "...", "depends_on": ["fork_node"]},
    {"node_id": "branch_b", "node_type": "agent", "system_prompt": "...", "subtask": "...", "depends_on": ["fork_node"]},
    {"node_id": "join_node", "node_type": "parallel_join", "source_branches": ["branch_a", "branch_b"], "join_policy": "all_success", "system_prompt": "...", "subtask": "整合两个分支的结果...", "depends_on": ["branch_a", "branch_b"]}
  ],
  "edges": [
    {"from": "fork_node", "to": "branch_a", "condition": null, "priority": 0},
    {"from": "fork_node", "to": "branch_b", "condition": null, "priority": 0},
    {"from": "branch_a", "to": "join_node", "condition": null, "priority": 0},
    {"from": "branch_b", "to": "join_node", "condition": null, "priority": 0}
  ]

关键规则（违反则被驳回）：
- parallel_fork 节点必须有 parallel_branches 字段（列出所有并行分支的 node_id）
- parallel_join 节点必须有 source_branches 字段（列出所有汇聚来源的 node_id）和 join_policy 字段
- 普通 agent 节点不能有多个后继（如需并行，必须用 parallel_fork）
- parallel_join 节点必须同时有 system_prompt 和 subtask（它也是执行节点）"""

SUPERVISOR_OUTPUT_SCHEMA: str = """{
  "approved": <true 或 false>,
  "quality_score": <1到10>,
  "issues": ["<问题1>", "<问题2>"],
  "suggestions": "<整体改进建议>",
  "revised_agents": [<若 approved=false，提供修订后完整 agents 列表；true 时可为空数组>],
  "revised_edges": [<若 approved=false，提供修订后完整 edges；true 时可为空数组>],
  "revised_entry_node": "<若 approved=false，提供修订后 entry_node；true 时可为空字符串>"
}"""


# ------------------------------------------------------------------
# 共享工具函数：安全解析 LLM 输出 JSON
# ------------------------------------------------------------------

def parse_llm_json(
    raw: str,
    context: str = "",
    fallback: Optional[Dict] = None,
) -> Dict:
    """
    多级容错解析 LLM 输出的 JSON 字符串。

    尝试顺序：
      1. 直接 json.loads
      2. 提取 ```json ... ``` 代码块后解析
      3. 正则抽取第一个完整 {...} 块后解析
      4. 字段级修复（保留 result / summary / confidence）
      5. 以上均失败 → 返回 fallback

    Args:
        raw:      LLM 返回的原始文本。
        context:  调用方标识（用于日志）。
        fallback: 解析失败时的默认返回值。
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

    for candidate in candidates:
        parsed = _parse_dict_or_wrapped(candidate)
        if parsed is not None:
            return parsed

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
