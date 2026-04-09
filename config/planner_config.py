"""
AutoAgentsMASPlanner 规划器相关配置。

将规划器的所有可调参数、Prompt 模板与共享工具函数集中于此，
修改配置无需改动 router/planner.py 或 workflow/nodes.py 等业务文件。

此文件是 router 层与 workflow 层的共享依赖，两层均可安全导入（无循环依赖）。
"""
import json
import re
from typing import Dict, List, Optional


# ------------------------------------------------------------------
# LLM 默认参数
# ------------------------------------------------------------------

PLANNER_TEMPERATURE: float = 0.2        # 规划/Supervisor 任务：低随机性，保证结构稳定
# 模型名称不在此定义，统一从 config/settings.py 的 settings.llm_model 读取（对应 .env 的 LLM_MODEL）
NODE_DEFAULT_TEMPERATURE: float = 0.7   # 执行节点：适度创造性
MAX_PLAN_ROUNDS_DEFAULT: int = 3        # PlanAgent ↔ Supervisor 最大迭代轮数


# ------------------------------------------------------------------
# 节点强制输出格式指令
# 由 make_generic_agent_node() 统一追加到每个专家 Agent system_prompt 末尾，
# Agent 自身的 system_prompt 不需要（也不应该）包含此内容。
# ------------------------------------------------------------------

NODE_OUTPUT_FORMAT_INSTRUCTION: str = """
---
[强制输出格式 - 必须严格遵守]
你必须且只能输出如下 JSON，禁止在 JSON 之外输出任何内容（包括解释、前言或 Markdown 标题）：

```json
{
  "result": "<你的完整主要输出内容，支持换行>",
  "summary": "<不超过80字的核心摘要，后续节点将直接读取此字段>",
  "confidence": <0.0到1.0之间的浮点数，表示输出质量置信度>,
  "metadata": {}
}
```
---"""


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
      "role": "<该 Agent 的角色名称>",
      "expertise": "<专长简述>",
      "system_prompt": "<该 Agent 的完整角色 system prompt，不含输出格式约束>",
      "subtask": "<该节点需要完成的具体子任务描述>",
      "output_schema": {
        "result": "<主要输出内容描述>",
        "summary": "<摘要描述>"
      },
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
  "quality_score": <0.0到1.0>,
  "issues": ["<问题1>", "<问题2>"],
  "suggestions": "<整体改进建议>",
  "revised_agents": [<若 approved=false，提供修订后的完整 agents 列表，格式同上；approved=true 时为空数组>]
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
    三级容错解析 LLM 输出的 JSON 字符串。

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

    # 尝试 1：直接解析
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        pass

    # 尝试 2：提取 ```json ... ``` 代码块
    match = re.search(r'```(?:json)?\s*(.*?)\s*```', raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except (json.JSONDecodeError, TypeError):
            pass

    # 尝试 3：正则抽取第一个完整 {...} 块
    match = re.search(r'\{.*\}', raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except (json.JSONDecodeError, TypeError):
            pass

    logger.warning(
        f"[{context}] JSON 解析全部失败，使用兜底值。"
        f"原始输出前200字：{raw[:200]}"
    )
    return fallback
