"""
LaTeXParserTool：单文件语法检查、结构提取、AST（阶段 2）。
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

from core.message import ToolResult
from latex.constants import IssueSource, Severity
from latex.models import DiagnosticIssue
from latex.paths import resolve_tex_file
from latex.structure_extract import extract_structure
from latex.syntax_check import check_syntax
from latex.ast_parse import parse_to_ast
from latex.tex_source import read_tex_file
from tools.base_tool import BaseTool
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class LaTeXSyntaxIssue:
    """
    LaTeX 语法问题描述（工具层；可转为 DiagnosticIssue）。
    """

    line: int
    column: int
    message: str
    severity: str = "error"

    def to_diagnostic(self, *, file: str) -> DiagnosticIssue:
        sev = Severity.ERROR
        if self.severity == "warning":
            sev = Severity.WARNING
        elif self.severity == "info":
            sev = Severity.INFO
        col = self.column if self.column >= 0 else 0
        return DiagnosticIssue.build(
            file=file,
            line=self.line,
            column=col,
            message=self.message,
            source=IssueSource.PARSER,
            severity=sev,
            code="parser",
        )


def _parse_tool_input(raw: str) -> Dict[str, Any]:
    text = (raw or "").strip()
    if not text:
        raise ValueError(
            '输入为空。示例: {"root":"...","rel_path":"weijun/Intro.tex"} 或 {"path":"..."}'
        )
    if text.startswith("{"):
        data = json.loads(text)
        if not isinstance(data, dict):
            raise ValueError("JSON 根类型必须是 object")
        return data
    return {"path": text}


class LaTeXParserTool(BaseTool):
    """
    解析单个 LaTeX 源文件：章节结构、轻量语法检查、AST（pylatexenc 可选）。

    输入 JSON（三选一）：
        - path：tex 绝对路径，或相对 cwd / root 的路径（兼容 Windows / Linux）
        - root + rel_path：项目根 + 相对 tex（推荐，如 VaLoRA 的 weijun/Intro.tex）
        - latex_source：直接传入源码字符串（仅测试/无文件场景）
    可选：base_dir — 解析相对 path 时的基准目录
    """

    def __init__(self) -> None:
        super().__init__(
            name="latex_parser",
            description=(
                "解析单个 LaTeX 文件：提取 section 结构、括号/环境语法检查、AST。"
                '输入 JSON：{"root":"...","rel_path":"weijun/Intro.tex"} 或 {"path":"..."}。'
            ),
            input_schema={
                "path": "可选，tex 文件路径（绝对或相对）",
                "root": "可选，与 rel_path 合用",
                "rel_path": "可选，相对 root 的 tex 路径",
                "latex_source": "可选，直接传入 tex 源码",
            },
        )

    def check_syntax(self, latex_source: str) -> List[LaTeXSyntaxIssue]:
        return [
            LaTeXSyntaxIssue(
                line=i.line,
                column=i.column,
                message=i.message,
                severity=i.severity,
            )
            for i in check_syntax(latex_source)
        ]

    def parse_to_ast(self, latex_source: str) -> Dict[str, Any]:
        return parse_to_ast(latex_source)

    def extract_structure(self, latex_source: str) -> Dict[str, Any]:
        return extract_structure(latex_source)

    def run(self, input: str) -> ToolResult:
        try:
            payload = _parse_tool_input(input)
            rel_display = ""
            source: str
            abs_path: Optional[str] = None

            if payload.get("latex_source"):
                source = str(payload["latex_source"])
                rel_display = str(payload.get("rel_path") or "inline.tex")
            else:
                abs_p, rel = resolve_tex_file(
                    path=payload.get("path"),
                    root=payload.get("root"),
                    rel_path=payload.get("rel_path"),
                    base_dir=payload.get("base_dir"),
                )
                source = read_tex_file(abs_p)
                abs_path = str(abs_p)
                rel_display = rel or payload.get("rel_path") or abs_p.name
                if isinstance(rel_display, str):
                    rel_display = rel_display.replace("\\", "/")

            rel_file = str(rel_display).replace("\\", "/")
            structure = self.extract_structure(source)
            syntax = self.check_syntax(source)
            ast = self.parse_to_ast(source)
            diagnostics = [s.to_diagnostic(file=rel_file) for s in syntax]

            result_body = {
                "path": abs_path,
                "rel_path": rel_file,
                "structure": structure,
                "syntax_issues": [asdict(s) for s in syntax],
                "diagnostics": [d.model_dump(mode="json") for d in diagnostics],
                "ast": ast,
            }
            return ToolResult(
                success=True,
                output=json.dumps(result_body, ensure_ascii=False, indent=2),
                metadata={
                    "rel_path": rel_file,
                    "section_count": len(structure.get("sections", [])),
                    "syntax_issue_count": len(syntax),
                },
            )
        except (json.JSONDecodeError, ValueError, FileNotFoundError, NotADirectoryError, OSError) as e:
            logger.warning("latex_parser: %s", e)
            return ToolResult(success=False, output="", error=str(e))
        except Exception as e:  # noqa: BLE001
            logger.exception("latex_parser 未预期错误")
            return ToolResult(success=False, output="", error=f"{type(e).__name__}: {e}")
