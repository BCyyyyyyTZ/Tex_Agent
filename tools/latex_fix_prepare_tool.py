"""
LatexFixPrepareTool：为 L3 修复 Agent 组装 prompt 批次（阶段 7，无 LLM）。
"""
from __future__ import annotations

import json
from typing import Any, Dict, Optional

from config.settings import settings
from core.message import ToolResult
from latex.coerce_payload import coerce_json_payload
from latex.diagnose_io import extract_root_from_payload, issues_from_tool_output, project_from_tool_output
from latex.fix_batch import build_fix_batch
from latex.models import DiagnosticIssue
from latex.serialize import from_dict
from latex.slice import IssueSlice
from tools.base_tool import BaseTool
from utils.logger import get_logger

logger = get_logger(__name__)


def _slices_from_payload(data: Dict[str, Any]) -> list[IssueSlice]:
    raw = data.get("slices")
    if raw is None and data.get("slice_output"):
        loaded = json.loads(data["slice_output"]) if isinstance(data["slice_output"], str) else data["slice_output"]
        if isinstance(loaded, dict):
            raw = loaded.get("slices", [])
    if not isinstance(raw, list):
        return []
    out: list[IssueSlice] = []
    for item in raw:
        if isinstance(item, IssueSlice):
            out.append(item)
        elif isinstance(item, dict):
            out.append(from_dict(IssueSlice, item))
    return out


class LatexFixPrepareTool(BaseTool):
    """
    从 merge + slice + project 产出 fix_batch（最多 N 条 error）。

    输入：
        - user_input / root
        - merge_output、slice_output、project_output（工作流上游 result）
        - max_issues（可选，默认 settings.latex_llm_max_issues_per_run）
    """

    def __init__(self) -> None:
        super().__init__(
            name="latex_fix_prepare",
            description=(
                "为 LaTeX L3 修复准备 prompt 批次（error issues + 切片 + 引用上下文）。"
                "不调用 LLM。"
            ),
            input_schema={
                "user_input": "用户任务 JSON",
                "merge_output": "latex_merge result",
                "slice_output": "latex_slice result",
                "project_output": "latex_project result",
                "max_issues": "可选，默认 LATEX_LLM_MAX_ISSUES_PER_RUN",
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

            issues = issues_from_tool_output(data.get("merge_output"))
            if not issues and data.get("issues"):
                raw_issues = data.get("issues")
                if isinstance(raw_issues, list):
                    issues = [
                        from_dict(DiagnosticIssue, x) if isinstance(x, dict) else x
                        for x in raw_issues
                    ]

            slices = _slices_from_payload(data)
            index = project_from_tool_output(data.get("project_output"))

            max_issues = data.get("max_issues", settings.latex_llm_max_issues_per_run)
            try:
                max_issues = int(max_issues)
            except (TypeError, ValueError):
                max_issues = settings.latex_llm_max_issues_per_run

            batch = build_fix_batch(
                issues,
                slices,
                index,
                max_issues=max_issues,
            )
            batch["root"] = root or (index.root if index else "")

            return ToolResult(
                success=True,
                output=json.dumps(batch, ensure_ascii=False, indent=2),
                metadata={"fix_batch": batch, "task_count": batch.get("task_count", 0)},
            )
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning("latex_fix_prepare: %s", e)
            return ToolResult(success=False, output="", error=str(e))
        except Exception as e:  # noqa: BLE001
            logger.exception("latex_fix_prepare 未预期错误")
            return ToolResult(success=False, output="", error=f"{type(e).__name__}: {e}")
