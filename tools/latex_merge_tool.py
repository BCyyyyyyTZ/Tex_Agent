"""
LatexMergeTool：合并 chktex / latexmk / parser 诊断（阶段 6）。
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from core.message import ToolResult
from latex.coerce_payload import coerce_json_payload
from latex.constants import METADATA_LATEX_DIAGNOSTICS
from latex.diagnose_io import (
    extract_root_from_payload,
    issues_from_tool_output,
    project_from_tool_output,
)
from latex.issues import merge_issues
from latex.models import DiagnosticIssue
from latex.refs_index import collect_undefined_ref_issues
from latex.serialize import to_dict
from tools.base_tool import BaseTool
from utils.logger import get_logger

logger = get_logger(__name__)


class LatexMergeTool(BaseTool):
    """
    合并上游 Tool 输出的 DiagnosticIssue 列表。

    输入 JSON（或 workflow dict 展开）：
        - user_input / root：项目根
        - chktex_output、latexmk_output：上游节点 result 文本（JSON）
        - project_output：latex_project 节点 result（可选，用于 parser 未定义 ref）
        - include_parser_refs（可选，默认 true）
    """

    def __init__(self) -> None:
        super().__init__(
            name="latex_merge",
            description=(
                "合并 ChkTeX、latexmk 与 parser 诊断为统一 issues 列表。"
                '输入：{"user_input": "{...}", "chktex_output": "...", "latexmk_output": "..."}。'
            ),
            input_schema={
                "user_input": "用户任务 JSON 或 root 路径",
                "chktex_output": "chktex 节点 result",
                "latexmk_output": "latexmk 节点 result",
                "project_output": "latex_project 节点 result",
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

            chktex_issues = issues_from_tool_output(data.get("chktex_output"))
            latexmk_issues = issues_from_tool_output(data.get("latexmk_output"))

            parser_issues: List[DiagnosticIssue] = []
            if data.get("include_parser_refs", True):
                index = project_from_tool_output(data.get("project_output"))
                if index is not None:
                    parser_issues = collect_undefined_ref_issues(index)

            merged = merge_issues(
                chktex=chktex_issues,
                latexmk=latexmk_issues,
                parser=parser_issues,
            )
            issues_dicts = [to_dict(i) for i in merged]
            body = {
                "root": root,
                "issues": issues_dicts,
                "issue_count": len(merged),
                "sources": {
                    "chktex": len(chktex_issues),
                    "latexmk": len(latexmk_issues),
                    "parser": len(parser_issues),
                },
            }
            return ToolResult(
                success=True,
                output=json.dumps(body, ensure_ascii=False, indent=2),
                metadata={
                    METADATA_LATEX_DIAGNOSTICS: issues_dicts,
                    "issue_count": len(merged),
                    "root": root,
                },
            )
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning("latex_merge: %s", e)
            return ToolResult(success=False, output="", error=str(e))
        except Exception as e:  # noqa: BLE001
            logger.exception("latex_merge 未预期错误")
            return ToolResult(success=False, output="", error=f"{type(e).__name__}: {e}")
