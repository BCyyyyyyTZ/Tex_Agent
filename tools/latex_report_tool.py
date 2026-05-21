"""
LatexReportTool：汇总诊断工作流终态 JSON（阶段 6，无 LLM）。
"""
from __future__ import annotations

import json
from typing import Any, Dict, Optional

from core.message import ToolResult
from latex.coerce_payload import coerce_json_payload
from latex.constants import METADATA_LATEX_DIAGNOSTICS, METADATA_LATEX_PROJECT
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

            issues = issues_from_tool_output(merge_data or data.get("merge_output"))
            slices = []
            if isinstance(slice_data, dict):
                slices = slice_data.get("slices", []) or []

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
            report = {
                "workflow": "latex_diagnose_v0",
                "root": root or (index.root if index else ""),
                "project": project_summary,
                "diagnostics": {
                    "issue_count": len(issues),
                    "issues": [to_dict(i) for i in issues],
                    "sources": sources,
                },
                "slices": slices,
                "slice_count": len(slices),
            }
            issues_dicts = [to_dict(i) for i in issues]
            meta: Dict[str, Any] = {
                METADATA_LATEX_DIAGNOSTICS: issues_dicts,
                "report": report,
            }
            if index is not None:
                meta[METADATA_LATEX_PROJECT] = to_dict(index)

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
