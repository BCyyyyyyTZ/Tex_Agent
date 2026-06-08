"""
LaTeX 子系统数据契约（Pydantic v2）。字段名与 §6 设计文档对齐，后续阶段勿破坏性重命名。
"""
from __future__ import annotations

import uuid
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from latex.constants import IssueSource, Severity


class Position(BaseModel):
    """VS Code 兼容：0-based line / character。"""

    line: int = 0
    character: int = 0


class TextRange(BaseModel):
    start: Position
    end: Position


class DiagnosticIssue(BaseModel):
    """
    L1/L2 统一诊断条目。
    id 规则：{source}:{file}:{line}:{column}（column 未知时用 0）。
    """

    id: str = ""
    file: str
    line: int = 1
    column: int = 0
    end_line: Optional[int] = None
    end_column: Optional[int] = None
    severity: Severity = Severity.WARNING
    source: IssueSource = IssueSource.PARSER
    code: str = ""
    message: str = ""

    @field_validator("line", mode="before")
    @classmethod
    def _line_at_least_one(cls, v: object) -> int:
        n = int(v) if v is not None else 1
        return max(1, n)

    @field_validator("column", mode="before")
    @classmethod
    def _column_non_negative(cls, v: object) -> int:
        if v is None or (isinstance(v, int) and v < 0):
            return 0
        return int(v)

    @model_validator(mode="after")
    def _fill_defaults(self) -> "DiagnosticIssue":
        if not self.id:
            col = self.column if self.column >= 0 else 0
            object.__setattr__(
                self,
                "id",
                make_issue_id(self.source.value, self.file, self.line, col),
            )
        if self.end_line is None:
            object.__setattr__(self, "end_line", self.line)
        if self.end_column is None:
            object.__setattr__(self, "end_column", self.column)
        return self

    @classmethod
    def build(
        cls,
        *,
        file: str,
        line: int,
        message: str,
        source: IssueSource,
        severity: Severity = Severity.WARNING,
        column: int = 0,
        code: str = "",
        end_line: Optional[int] = None,
        end_column: Optional[int] = None,
    ) -> "DiagnosticIssue":
        col = column if column >= 0 else 0
        return cls(
            id=make_issue_id(source.value, file, line, col),
            file=file,
            line=line,
            column=column,
            end_line=end_line,
            end_column=end_column,
            severity=severity,
            source=source,
            code=code,
            message=message,
        )


def make_issue_id(source: str, rel_path: str, line: int, column: int) -> str:
    """冻结规则：{source}:{rel_path}:{line}:{column}，路径统一为正斜杠。"""
    path = rel_path.replace("\\", "/")
    return f"{source}:{path}:{line}:{column}"


class Suggestion(BaseModel):
    """L3 / 润色建议；range 为 0-based。"""

    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    document_version: int = 0
    file: str
    range: TextRange
    severity: Severity = Severity.INFO
    source: IssueSource = IssueSource.LLM_FIX
    message: str = ""
    replacement: str = ""
    confidence: Optional[float] = None
    rationale_zh: str = ""
    cause_zh: str = ""
    advice_zh: str = ""
    issue_id: Optional[str] = None


class ProjectFile(BaseModel):
    """项目内单个 .tex 文件元数据。"""

    checksum: str = ""
    inputs: List[str] = Field(default_factory=list)


class LabelDef(BaseModel):
    """\\label 定义位置（阶段 2.5 填充）。"""

    defined_in: str
    line: int = 1


class RefEntry(BaseModel):
    """\\ref / \\cite 引用位置（阶段 2.5 填充）。"""

    key: str
    file: str
    line: int = 1
    kind: str = "ref"  # ref | cite


class BibEntry(BaseModel):
    """.bib 条目轻量元数据（阶段 2.6）。"""

    key: str
    title: str = ""
    author: str = ""


class MacroDef(BaseModel):
    """导言区 \\newcommand / \\renewcommand / \\newtheorem 等定义（阶段 2.7）。"""

    name: str
    kind: str = "newcommand"  # newcommand | renewcommand | newtheorem
    arity: int = 0
    definition: str = ""
    expands_to_hint: str = ""
    defined_in: str = ""
    line: int = 1


class AlgorithmConvention(BaseModel):
    """算法块写作约定（如 Input/Output 标签）。"""

    require_label: str = "Input:"
    ensure_label: str = "Output:"
    packages: List[str] = Field(default_factory=list)


class ProjectConventions(BaseModel):
    """项目级 LaTeX 方言：宏、包、版式（阶段 2.7）。"""

    documentclass: str = ""
    documentclass_options: List[str] = Field(default_factory=list)
    packages: List[str] = Field(default_factory=list)
    macro_defs: Dict[str, MacroDef] = Field(default_factory=dict)
    colors: Dict[str, str] = Field(default_factory=dict)
    theorem_environments: List[str] = Field(default_factory=list)
    caption_setups: List[str] = Field(default_factory=list)
    algorithm: Optional[AlgorithmConvention] = None
    macro_usage: Dict[str, int] = Field(default_factory=dict)
    local_typography: List[Dict[str, object]] = Field(default_factory=list)


class ProjectIndex(BaseModel):
    """
    LaTeX 项目图（阶段 1：文件 DAG + checksum；label/ref 预留空结构）。
    """

    root: str
    main_tex: Optional[str] = None
    main_tex_candidates: List[str] = Field(default_factory=list)
    files: Dict[str, ProjectFile] = Field(default_factory=dict)
    labels: Dict[str, LabelDef] = Field(default_factory=dict)
    refs: List[RefEntry] = Field(default_factory=list)
    bibliography_files: List[str] = Field(default_factory=list)
    bib_entries: Dict[str, BibEntry] = Field(default_factory=dict)
    conventions: Optional[ProjectConventions] = None
