from __future__ import annotations

from latex.fix_batch import build_fix_batch, select_error_issues
from latex.models import DiagnosticIssue
from latex.constants import IssueSource, Severity
from latex.slice import IssueSlice


def test_select_error_issues_caps() -> None:
    issues = [
        DiagnosticIssue.build(
            file="a.tex",
            line=i,
            message="e",
            source=IssueSource.LATEXMK,
            severity=Severity.ERROR,
        )
        for i in range(1, 10)
    ]
    picked = select_error_issues(issues, max_count=3)
    assert len(picked) == 3


def test_build_fix_batch_skips_without_slice() -> None:
    issue = DiagnosticIssue.build(
        file="main.tex",
        line=2,
        message="err",
        source=IssueSource.LATEXMK,
        severity=Severity.ERROR,
    )
    sl = IssueSlice(
        issue_id=issue.id,
        file="main.tex",
        start_line=1,
        end_line=3,
        snippet="x",
        context_lines=2,
    )
    batch = build_fix_batch([issue], [sl], None, max_issues=5)
    assert batch["task_count"] == 1
    assert batch["tasks"][0]["prompt"]
