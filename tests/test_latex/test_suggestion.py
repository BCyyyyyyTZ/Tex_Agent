from __future__ import annotations

import json

from latex.constants import IssueSource
from latex.models import DiagnosticIssue, Position, TextRange
from latex.constants import Severity
from latex.suggestion import (
    parse_llm_suggestion_json,
    parse_llm_suggestions_from_agent_result,
)


def test_parse_llm_suggestion_json_minimal() -> None:
    issue = DiagnosticIssue.build(
        file="chapters/a.tex",
        line=3,
        column=1,
        message="err",
        source=IssueSource.LATEXMK,
        severity=Severity.ERROR,
    )
    raw = {
        "file": "chapters/a.tex",
        "replacement": "\\begin{equation}x\\end{equation}",
        "message": "fix brace",
        "rationale_zh": "闭合环境",
        "issue_id": issue.id,
        "range": {
            "start": {"line": 2, "character": 0},
            "end": {"line": 2, "character": 10},
        },
    }
    sug = parse_llm_suggestion_json(raw, issue=issue)
    assert sug is not None
    assert sug.replacement.startswith("\\begin{equation}")
    assert sug.issue_id == issue.id
    assert sug.source == IssueSource.LLM_FIX


def test_parse_llm_suggestions_from_agent_wrapped_result() -> None:
    issue = DiagnosticIssue.build(
        file="main.tex",
        line=1,
        message="e",
        source=IssueSource.LATEXMK,
        severity=Severity.ERROR,
    )
    agent_payload = {
        "result": json.dumps(
            [
                {
                    "issue_id": issue.id,
                    "file": "main.tex",
                    "replacement": "fixed",
                    "range": {
                        "start": {"line": 0, "character": 0},
                        "end": {"line": 0, "character": 5},
                    },
                }
            ]
        ),
        "summary": "ok",
        "confidence": 0.9,
    }
    out = parse_llm_suggestions_from_agent_result(
        agent_payload,
        issues_by_id={issue.id: issue},
    )
    assert len(out) == 1
    assert out[0].replacement == "fixed"
