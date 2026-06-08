from __future__ import annotations

import json
from pathlib import Path

import pytest

from latex.constants import IssueSource, Severity
from latex.models import DiagnosticIssue
from latex.slice import slice_around_issue, slice_issues

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "latex"
MULTIFILE = FIXTURES / "multifile"


def test_slice_around_issue_context_lines() -> None:
    issue = DiagnosticIssue.build(
        file="chapters/intro.tex",
        line=1,
        message="test",
        source=IssueSource.PARSER,
        severity=Severity.INFO,
    )
    sl = slice_around_issue(issue, root=MULTIFILE, context_lines=0)
    assert sl.issue_id == issue.id
    assert sl.file == "chapters/intro.tex"
    assert sl.start_line == 1
    assert sl.end_line == 1
    assert "Introduction" in sl.snippet
    assert sl.context_lines == 0


def test_slice_includes_surrounding_lines() -> None:
    text = "\n".join(f"line{i}" for i in range(1, 21))
    issue = DiagnosticIssue.build(
        file="dummy.tex",
        line=10,
        message="center",
        source=IssueSource.PARSER,
        severity=Severity.ERROR,
    )
    sl = slice_around_issue(
        issue,
        root=MULTIFILE,
        context_lines=2,
        file_text=text,
    )
    assert sl.start_line == 8
    assert sl.end_line == 12
    assert "line10" in sl.snippet
    assert "line8" in sl.snippet
    assert "line7" not in sl.snippet
    assert "line13" not in sl.snippet


def test_slice_issues_filter_by_id() -> None:
    i1 = DiagnosticIssue.build(
        file="chapters/intro.tex",
        line=1,
        message="a",
        source=IssueSource.PARSER,
        severity=Severity.INFO,
    )
    i2 = DiagnosticIssue.build(
        file="main.tex",
        line=2,
        message="b",
        source=IssueSource.PARSER,
        severity=Severity.INFO,
    )
    slices = slice_issues([i1, i2], root=MULTIFILE, context_lines=1, issue_ids=[i1.id])
    assert len(slices) == 1
    assert slices[0].issue_id == i1.id


def test_slice_missing_file_raises() -> None:
    issue = DiagnosticIssue.build(
        file="no/such.tex",
        line=1,
        message="x",
        source=IssueSource.PARSER,
        severity=Severity.ERROR,
    )
    with pytest.raises(FileNotFoundError):
        slice_around_issue(issue, root=MULTIFILE, context_lines=1)


def test_slice_tool_multifile(tmp_path: Path) -> None:
    from tools.latex_slice_tool import LatexSliceTool

    issue = DiagnosticIssue.build(
        file="chapters/intro.tex",
        line=1,
        message="slice me",
        source=IssueSource.PARSER,
        severity=Severity.WARNING,
    )
    tool = LatexSliceTool()
    out = tool.run(
        json.dumps(
            {
                "root": str(MULTIFILE),
                "issues": [issue.model_dump(mode="json")],
                "context_lines": 2,
            }
        )
    )
    assert out.success is True, out.error
    body = json.loads(out.output)
    assert body["slice_count"] == 1
    assert body["slices"][0]["issue_id"] == issue.id
    assert "Introduction" in body["slices"][0]["snippet"]
