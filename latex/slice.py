"""
按 DiagnosticIssue 切片源码上下文（阶段 5）。
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Union

from pydantic import BaseModel, Field

from latex.models import DiagnosticIssue
from latex.paths import normalize_rel_path, path_from_user_string


class IssueSlice(BaseModel):
    """冻结输出形状，供 PromptBuilder / latex_slice Tool 使用。"""

    issue_id: str
    file: str
    start_line: int
    end_line: int
    snippet: str
    context_lines: int = 10


def slice_around_issue(
    issue: DiagnosticIssue,
    *,
    root: Union[str, Path],
    context_lines: int = 10,
    file_text: Optional[str] = None,
) -> IssueSlice:
    """
    读取 issue 所在文件，返回报错行 ±context_lines 的片段。

    line 为 1-based（与 DiagnosticIssue 一致）。
    """
    if context_lines < 0:
        raise ValueError("context_lines 不能为负")

    root_path = path_from_user_string(str(root)).resolve()
    rel = normalize_rel_path(issue.file)
    if not rel:
        raise ValueError("issue.file 为空")

    if file_text is None:
        tex_path = root_path / Path(rel)
        if not tex_path.is_file():
            raise FileNotFoundError(f"找不到 tex 文件: {tex_path}")
        file_text = tex_path.read_text(encoding="utf-8", errors="replace")

    lines = file_text.splitlines()
    total = len(lines)
    if total == 0:
        return IssueSlice(
            issue_id=issue.id,
            file=rel,
            start_line=1,
            end_line=1,
            snippet="",
            context_lines=context_lines,
        )

    center = max(1, min(issue.line, total))
    start = max(1, center - context_lines)
    end = min(total, center + context_lines)
    snippet = "\n".join(lines[start - 1 : end])

    return IssueSlice(
        issue_id=issue.id,
        file=rel,
        start_line=start,
        end_line=end,
        snippet=snippet,
        context_lines=context_lines,
    )


def slice_issues(
    issues: List[DiagnosticIssue],
    *,
    root: Union[str, Path],
    context_lines: int = 10,
    issue_ids: Optional[List[str]] = None,
) -> List[IssueSlice]:
    """批量切片；issue_ids 非空时仅处理匹配 id 的 issue。"""
    selected = issues
    if issue_ids:
        wanted = set(issue_ids)
        selected = [i for i in issues if i.id in wanted]
    return [
        slice_around_issue(i, root=root, context_lines=context_lines)
        for i in selected
    ]
