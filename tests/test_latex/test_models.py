from __future__ import annotations

import json

import pytest

from latex.constants import IssueSource, Severity
from latex.models import DiagnosticIssue, Position, ProjectIndex, Suggestion, TextRange, make_issue_id
from latex.serialize import from_json, to_dict, to_json


def test_make_issue_id_normalizes_slashes() -> None:
    assert make_issue_id("chktex", r"chapters\a.tex", 42, 15) == "chktex:chapters/a.tex:42:15"


def test_diagnostic_issue_auto_id() -> None:
    issue = DiagnosticIssue(
        file="main.tex",
        line=3,
        column=5,
        severity=Severity.ERROR,
        source=IssueSource.CHKTEX,
        code="15",
        message="test",
    )
    assert issue.id == "chktex:main.tex:3:5"
    assert issue.end_line == 3
    assert issue.end_column == 5


def test_diagnostic_issue_build() -> None:
    issue = DiagnosticIssue.build(
        file="a.tex",
        line=1,
        column=-1,
        message="m",
        source=IssueSource.LATEXMK,
        severity=Severity.WARNING,
    )
    assert issue.id == "latexmk:a.tex:1:0"
    assert issue.column == 0


def test_suggestion_roundtrip_json() -> None:
    sug = Suggestion(
        document_version=7,
        file="x.tex",
        range=TextRange(
            start=Position(line=0, character=0),
            end=Position(line=2, character=10),
        ),
        source=IssueSource.LLM_FIX,
        message="fix",
        replacement="\\end{equation}",
        confidence=0.9,
        rationale_zh="说明",
    )
    raw = to_json(sug)
    restored = from_json(Suggestion, raw)
    assert restored.file == "x.tex"
    assert restored.range.start.line == 0
    assert restored.replacement == "\\end{equation}"


def test_project_index_roundtrip() -> None:
    idx = ProjectIndex(root="/tmp/proj", main_tex="main.tex", files={})
    data = to_dict(idx)
    assert data["root"] == "/tmp/proj"
    roundtrip = from_json(ProjectIndex, json.dumps(data))
    assert roundtrip.main_tex == "main.tex"


def test_line_must_be_at_least_one() -> None:
    issue = DiagnosticIssue(
        file="f.tex",
        line=0,
        message="m",
        source=IssueSource.PARSER,
    )
    assert issue.line == 1
