"""
L3 修复批次：从 issues + slices 选取待 LLM 处理的 error（阶段 7）。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from config.settings import settings
from latex.models import DiagnosticIssue, ProjectIndex
from latex.prompt_builder import build_fix_prompt, build_project_meta
from latex.serialize import to_dict
from latex.slice import IssueSlice


def select_error_issues(
    issues: List[DiagnosticIssue],
    *,
    max_count: Optional[int] = None,
    severity: str = "error",
) -> List[DiagnosticIssue]:
    """选取待修复 issue，默认仅 error，最多 max_count 条。"""
    cap = max_count if max_count is not None else settings.latex_llm_max_issues_per_run
    sev = severity.strip().lower()
    filtered = [i for i in issues if i.severity.value == sev]
    return filtered[: max(1, int(cap))]


def _slices_by_issue_id(slices: List[IssueSlice]) -> Dict[str, IssueSlice]:
    return {s.issue_id: s for s in slices if s.issue_id}


def build_fix_batch(
    issues: List[DiagnosticIssue],
    slices: List[IssueSlice],
    index: Optional[ProjectIndex] = None,
    *,
    max_issues: Optional[int] = None,
) -> Dict[str, Any]:
    """
    构建 fix_batch：每项含 issue、slice、prompt。

    无 slice 的 issue 跳过（无法提供上下文）。
    """
    selected = select_error_issues(issues, max_count=max_issues)
    by_id = _slices_by_issue_id(slices)
    project_meta = build_project_meta(index)
    tasks: List[Dict[str, Any]] = []

    for issue in selected:
        sl = by_id.get(issue.id)
        if sl is None:
            continue
        prompt = build_fix_prompt(
            issue,
            sl.snippet,
            project_meta,
            index=index,
        )
        tasks.append(
            {
                "issue_id": issue.id,
                "issue": to_dict(issue),
                "slice": to_dict(sl),
                "prompt": prompt,
            }
        )

    return {
        "task_count": len(tasks),
        "max_issues": max_issues or settings.latex_llm_max_issues_per_run,
        "project_meta": project_meta,
        "tasks": tasks,
        "prompt_bundle": _bundle_prompts(tasks),
    }


def _bundle_prompts(tasks: List[Dict[str, Any]]) -> str:
    """合并为单条 Agent 用户消息附件（多 issue 一次调用）。"""
    if not tasks:
        return "（无待修复 error 或无对应切片）"
    parts: List[str] = []
    for i, t in enumerate(tasks, start=1):
        parts.append(f"========== Issue {i}/{len(tasks)}: {t.get('issue_id', '')} ==========")
        parts.append(str(t.get("prompt", "")))
    parts.append(
        "\n【批量输出要求】\n"
        "在 JSON 的 result 字段中放入一个数组，长度与 issue 数相同，"
        "每个元素为一条 Suggestion 对象（含 issue_id、file、range、replacement、rationale_zh）。"
        "不要为同一 issue_id 输出多条建议。"
    )
    return "\n\n".join(parts)
