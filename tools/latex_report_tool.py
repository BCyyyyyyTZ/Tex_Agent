"""
LatexReportTool：汇总诊断工作流终态 JSON（阶段 6，无 LLM）。
"""
from __future__ import annotations

import json
from typing import Any, Dict, Optional

from core.message import ToolResult
from latex.coerce_payload import coerce_json_payload
from latex.constants import (
    METADATA_LATEX_DIAGNOSTICS,
    METADATA_LATEX_PROJECT,
    METADATA_LATEX_SUGGESTIONS,
)
from latex.diagnose_io import (
    extract_root_from_payload,
    issues_from_tool_output,
    project_from_tool_output,
)
from latex.serialize import to_dict
from tools.base_tool import BaseTool
from utils.logger import get_logger

logger = get_logger(__name__)


class LatexReportTool(BaseTool):
    """
    汇总 project / merge / slice 产出为可交付 report JSON。

    输入：
        - user_input / root
        - project_output、merge_output、slice_output（上游 result 字符串）
        - suggestions_output（可选，latex_collect_suggestions result）
        - workflow（可选，默认 latex_diagnose_v0）
    """

    def __init__(self) -> None:
        super().__init__(
            name="latex_report",
            description=(
                "汇总 LaTeX 诊断工作流结果为 report JSON（issues、slices、project 摘要）。"
                "无 LLM，仅拼接上游 Tool 真实输出。"
            ),
            input_schema={
                "user_input": "用户任务 JSON",
                "project_output": "latex_project result",
                "merge_output": "latex_merge result",
                "slice_output": "latex_slice result",
                "suggestions_output": "可选，latex_collect_suggestions result",
                "workflow": "可选，报告 workflow 名称",
            },
        )

    def run(
        self,
        payload: Optional[str | Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> ToolResult:
        try:
            data = coerce_json_payload(payload, **kwargs)
            root = extract_root_from_payload(data)

            index = project_from_tool_output(data.get("project_output"))
            merge_data = _loads_dict(data.get("merge_output"))
            slice_data = _loads_dict(data.get("slice_output"))
            suggestions_data = _loads_dict(data.get("suggestions_output"))

            issues = issues_from_tool_output(merge_data or data.get("merge_output"))
            slices = []
            if isinstance(slice_data, dict):
                slices = slice_data.get("slices", []) or []

            suggestions: list = []
            if isinstance(suggestions_data, dict):
                suggestions = suggestions_data.get("suggestions", []) or []

            workflow_name = str(data.get("workflow") or "latex_diagnose_v0").strip()

            project_summary: Dict[str, Any] = {}
            if index is not None:
                project_summary = {
                    "root": index.root,
                    "main_tex": index.main_tex,
                    "file_count": len(index.files),
                    "label_count": len(index.labels),
                    "ref_count": len(index.refs),
                }

            sources = merge_data.get("sources", {}) if isinstance(merge_data, dict) else {}
            
            # 阶段 9：人读层扩展
            error_count = sum(1 for i in issues if i.severity.value == "error")
            warning_count = sum(1 for i in issues if i.severity.value == "warning")
            by_source = {}
            for i in issues:
                src = i.source.value if hasattr(i.source, "value") else str(i.source)
                by_source[src] = by_source.get(src, 0) + 1
            
            summary = {
                "error": error_count,
                "warning": warning_count,
                "by_source": by_source
            }
            
            issues_dicts = [to_dict(i) for i in issues]
            # Top-K: 所有的 error，加上部分 warning (最多 20 条)
            errors = [i for i in issues_dicts if i.get("severity") == "error"]
            warnings = [i for i in issues_dicts if i.get("severity") == "warning"]
            issues_top_k = errors + warnings[:20]

            report = {
                "workflow": workflow_name,
                "root": root or (index.root if index else ""),
                "project": project_summary,
                "summary": summary,
                "diagnostics": {
                    "issue_count": len(issues),
                    "issues": issues_dicts,
                    "issues_top_k": issues_top_k,
                    "sources": sources,
                },
                "slices": slices,
                "slice_count": len(slices),
                "suggestions": suggestions,
                "suggestion_count": len(suggestions),
            }
            meta: Dict[str, Any] = {
                METADATA_LATEX_DIAGNOSTICS: issues_dicts,
                "report": report,
            }
            if index is not None:
                meta[METADATA_LATEX_PROJECT] = to_dict(index)
            if suggestions:
                meta[METADATA_LATEX_SUGGESTIONS] = suggestions

            return ToolResult(
                success=True,
                output=json.dumps(report, ensure_ascii=False, indent=2),
                metadata=meta,
            )
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning("latex_report: %s", e)
            return ToolResult(success=False, output="", error=str(e))
        except Exception as e:  # noqa: BLE001
            logger.exception("latex_report 未预期错误")
            return ToolResult(success=False, output="", error=f"{type(e).__name__}: {e}")


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
