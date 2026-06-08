from __future__ import annotations

from latex.constants import IssueSource, Severity
from latex.issues import merge_issue_lists, merge_issues
from latex.models import DiagnosticIssue


def _issue(
    *,
    file: str,
    line: int,
    source: IssueSource,
    severity: Severity,
    message: str = "msg",
) -> DiagnosticIssue:
    return DiagnosticIssue.build(
        file=file,
        line=line,
        message=message,
        source=source,
        severity=severity,
    )


def test_merge_same_file_line_source_keeps_highest_severity() -> None:
    low = _issue(
        file="main.tex",
        line=10,
        source=IssueSource.CHKTEX,
        severity=Severity.WARNING,
        message="warn",
    )
    high = _issue(
        file="main.tex",
        line=10,
        source=IssueSource.CHKTEX,
        severity=Severity.ERROR,
        message="err",
    )
    merged = merge_issues(chktex=[low, high])
    assert len(merged) == 1
    assert merged[0].severity == Severity.ERROR
    assert merged[0].message == "err"


def test_merge_different_sources_same_line_keeps_both() -> None:
    a = _issue(
        file="main.tex",
        line=5,
        source=IssueSource.CHKTEX,
        severity=Severity.WARNING,
    )
    b = _issue(
        file="main.tex",
        line=5,
        source=IssueSource.LATEXMK,
        severity=Severity.WARNING,
    )
    merged = merge_issues(chktex=[a], latexmk=[b])
    assert len(merged) == 2
    sources = {i.source for i in merged}
    assert IssueSource.CHKTEX in sources
    assert IssueSource.LATEXMK in sources


def test_merge_normalizes_path_separators_for_dedup() -> None:
    a = _issue(
        file="chapters\\intro.tex",
        line=1,
        source=IssueSource.PARSER,
        severity=Severity.INFO,
    )
    b = _issue(
        file="chapters/intro.tex",
        line=1,
        source=IssueSource.PARSER,
        severity=Severity.ERROR,
    )
    merged = merge_issues(parser=[a, b])
    assert len(merged) == 1
    assert merged[0].severity == Severity.ERROR


def test_merge_issue_lists_stable_sort() -> None:
    issues = [
        _issue(file="b.tex", line=2, source=IssueSource.PARSER, severity=Severity.WARNING),
        _issue(file="a.tex", line=1, source=IssueSource.PARSER, severity=Severity.WARNING),
    ]
    merged = merge_issue_lists([issues])
    assert [i.file for i in merged] == ["a.tex", "b.tex"]
