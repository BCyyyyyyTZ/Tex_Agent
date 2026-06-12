from __future__ import annotations

from pathlib import Path

import pytest

from latex.constants import IssueSource
from latex.models import DiagnosticIssue
from latex.slice import slice_around_issue


def test_slice_around_issue__file_text_provided__bounds_ok(tmp_path: Path) -> None:
    issue = DiagnosticIssue.build(
        file="main.tex",
        line=3,
        message="x",
        source=IssueSource.PARSER,
    )
    text = "\n".join(["l1", "l2", "l3", "l4", "l5"])
    out = slice_around_issue(issue, root=tmp_path, context_lines=1, file_text=text)
    assert out.file == "main.tex"
    assert out.start_line == 2
    assert out.end_line == 4
    assert out.snippet == "\n".join(["l2", "l3", "l4"])


def test_slice_around_issue__negative_context_rejected(tmp_path: Path) -> None:
    issue = DiagnosticIssue.build(
        file="main.tex",
        line=1,
        message="x",
        source=IssueSource.PARSER,
    )
    with pytest.raises(ValueError):
        slice_around_issue(issue, root=tmp_path, context_lines=-1, file_text="a")


def test_slice_around_issue__reads_from_disk_when_file_text_none(tmp_path: Path) -> None:
    (tmp_path / "main.tex").write_text("a\nb\nc\n", encoding="utf-8")
    issue = DiagnosticIssue.build(
        file="main.tex",
        line=2,
        message="x",
        source=IssueSource.PARSER,
    )
    out = slice_around_issue(issue, root=tmp_path, context_lines=0)
    assert out.snippet == "b"

