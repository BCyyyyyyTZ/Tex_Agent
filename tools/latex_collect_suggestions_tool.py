"""
LatexCollectSuggestionsTool：解析 fix_agent 输出为 Suggestion 列表（阶段 7）。
"""
from __future__ import annotations

import json
from typing import Any, Dict, Optional

from core.message import ToolResult
from latex.coerce_payload import coerce_json_payload
from latex.constants import METADATA_LATEX_SUGGESTIONS
from latex.diagnose_io import issues_from_tool_output
from latex.models import DiagnosticIssue
from latex.serialize import from_dict, to_dict
from latex.suggestion import parse_llm_suggestions_from_agent_result, suggestions_to_metadata
from tools.base_tool import BaseTool
from utils.logger import get_logger

logger = get_logger(__name__)


def _loads_dict(text: Any) -> Optional[Dict[str, Any]]:
    if text is None:
        return None
    if isinstance(text, dict):
        return text
    s = str(text).strip()
    if not s:
        return None
    try:
        data = json.loads(s)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        return None


class LatexCollectSuggestionsTool(BaseTool):
    """
    将 fix_agent 的 result JSON 归一化为 Suggestion[]，写入 __latex_suggestions__。

    输入：
        - fix_agent_output：Agent 节点 result 字符串或对象
        - fix_prepare_output：latex_fix_prepare 的 fix_batch（用于 issue 对齐）
        - merge_output（可选）：补充 issue 字典
    """

    def __init__(self) -> None:
        super().__init__(
            name="latex_collect_suggestions",
            description=(
                "解析 LaTeX 修复 Agent 的 JSON 输出为 Suggestion 列表，"
                "写入 metadata __latex_suggestions__。"
            ),
            input_schema={
                "fix_agent_output": "fix_agent 节点 result",
                "fix_prepare_output": "latex_fix_prepare result",
                "merge_output": "可选，latex_merge result",
            },
        )

    def run(
        self,
        payload: Optional[str | Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> ToolResult:
        try:
            data = coerce_json_payload(payload, **kwargs)

            agent_raw = data.get("fix_agent_output") or data.get("agent_output")
            prepare = _loads_dict(data.get("fix_prepare_output"))
            issues_by_id: Dict[str, DiagnosticIssue] = {}

            for issue in issues_from_tool_output(data.get("merge_output")):
                issues_by_id[issue.id] = issue

            if prepare:
                for task in prepare.get("tasks") or []:
                    if not isinstance(task, dict):
                        continue
                    iid = str(task.get("issue_id", ""))
                    raw_issue = task.get("issue")
                    if iid and isinstance(raw_issue, dict) and iid not in issues_by_id:
                        issues_by_id[iid] = from_dict(DiagnosticIssue, raw_issue)

            suggestions = parse_llm_suggestions_from_agent_result(
                agent_raw,
                issues_by_id=issues_by_id,
            )

            body = {
                "suggestion_count": len(suggestions),
                "suggestions": suggestions_to_metadata(suggestions),
            }
            meta = {METADATA_LATEX_SUGGESTIONS: body["suggestions"]}

            return ToolResult(
                success=True,
                output=json.dumps(body, ensure_ascii=False, indent=2),
                metadata=meta,
            )
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning("latex_collect_suggestions: %s", e)
            return ToolResult(success=False, output="", error=str(e))
        except Exception as e:  # noqa: BLE001
            logger.exception("latex_collect_suggestions 未预期错误")
            return ToolResult(success=False, output="", error=f"{type(e).__name__}: {e}")
