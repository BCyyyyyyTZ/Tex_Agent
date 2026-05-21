"""
DiagnosticIssue 合并与去重（阶段 5）。
"""
from __future__ import annotations

from typing import Iterable, List, Sequence

from latex.constants import Severity
from latex.models import DiagnosticIssue
from latex.paths import normalize_rel_path

_SEVERITY_RANK = {
    Severity.ERROR: 3,
    Severity.WARNING: 2,
    Severity.INFO: 1,
}


def _dedup_key(issue: DiagnosticIssue) -> tuple[str, int, str]:
    """同文件、同行、同源视为重复。"""
    return (
        normalize_rel_path(issue.file),
        issue.line,
        issue.source.value if hasattr(issue.source, "value") else str(issue.source),
    )


def _severity_rank(severity: Severity) -> int:
    return _SEVERITY_RANK.get(severity, 0)


def merge_issues(
    chktex: Iterable[DiagnosticIssue] | None = None,
    latexmk: Iterable[DiagnosticIssue] | None = None,
    parser: Iterable[DiagnosticIssue] | None = None,
    *,
    extra: Iterable[DiagnosticIssue] | None = None,
) -> List[DiagnosticIssue]:
    """
    合并多来源诊断列表；同文件同行同源仅保留 severity 最高的一条。

    参数可按来源传入，也可通过 extra 追加其它列表。
    """
    buckets: dict[tuple[str, int, str], DiagnosticIssue] = {}
    order: List[tuple[str, int, str]] = []

    def _ingest(items: Iterable[DiagnosticIssue] | None) -> None:
        if not items:
            return
        for issue in items:
            key = _dedup_key(issue)
            existing = buckets.get(key)
            if existing is None:
                buckets[key] = issue
                order.append(key)
            elif _severity_rank(issue.severity) > _severity_rank(existing.severity):
                buckets[key] = issue

    _ingest(chktex)
    _ingest(latexmk)
    _ingest(parser)
    _ingest(extra)

    merged = [buckets[k] for k in order]
    merged.sort(
        key=lambda i: (
            normalize_rel_path(i.file),
            i.line,
            i.column,
            i.source.value if hasattr(i.source, "value") else str(i.source),
        )
    )
    return merged


def merge_issue_lists(lists: Sequence[Iterable[DiagnosticIssue]]) -> List[DiagnosticIssue]:
    """将多个 issue 列表顺序合并后去重（供工作流直接拼接 metadata 列表）。"""
    flat: List[DiagnosticIssue] = []
    for group in lists:
        flat.extend(group)
    if not flat:
        return []
    return merge_issues(extra=flat)
