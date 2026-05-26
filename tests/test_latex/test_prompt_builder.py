from __future__ import annotations

from pathlib import Path

from latex.models import DiagnosticIssue, LabelDef, ProjectIndex, RefEntry
from latex.constants import IssueSource, Severity
from latex.prompt_builder import (
    build_fix_prompt,
    build_project_meta,
    collect_ref_context_snippets,
)
from latex.project_index import build_project_index

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "latex"
CROSS_REF = FIXTURES / "cross_ref"


def test_build_project_meta_from_index() -> None:
    index = build_project_index(CROSS_REF, main_tex="main.tex", enrich=True)
    meta = build_project_meta(index)
    assert meta["main_tex"] == "main.tex"
    assert meta["file_count"] >= 2


def test_build_fix_prompt_includes_issue_and_snippet() -> None:
    issue = DiagnosticIssue.build(
        file="main.tex",
        line=5,
        message="undefined",
        source=IssueSource.LATEXMK,
        severity=Severity.ERROR,
    )
    prompt = build_fix_prompt(issue, "line5 context", {"root": "/tmp", "main_tex": "main.tex"})
    assert issue.id in prompt
    assert "line5 context" in prompt
    assert "replacement" in prompt


def test_collect_ref_context_cross_file() -> None:
    index = ProjectIndex(
        root=str(CROSS_REF),
        main_tex="main.tex",
        files={},
        labels={"fig:mainfig": LabelDef(defined_in="chapters/fig.tex", line=3)},
        refs=[RefEntry(key="fig:mainfig", file="main.tex", line=4, kind="ref")],
    )
    issue = DiagnosticIssue.build(
        file="main.tex",
        line=4,
        message="ref",
        source=IssueSource.PARSER,
        severity=Severity.ERROR,
    )
    ctx = collect_ref_context_snippets(issue, index, root=CROSS_REF)
    assert len(ctx) == 1
    assert ctx[0]["ref_key"] == "fig:mainfig"
    assert "chapters/fig.tex" in ctx[0]["defined_in"]
