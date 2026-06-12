from __future__ import annotations

from pathlib import Path

import pytest

from latex.apply_edit import SuggestionRangeError, apply_suggestion_to_file
from latex.constants import IssueSource, Severity
from latex.models import Position, Suggestion, TextRange


def test_apply_suggestion_to_file__replaces_range(tmp_path: Path) -> None:
    p = tmp_path / "main.tex"
    p.write_text("abc\ndef\n", encoding="utf-8")
    sug = Suggestion(
        file="main.tex",
        range=TextRange(start=Position(line=0, character=1), end=Position(line=0, character=3)),
        severity=Severity.INFO,
        source=IssueSource.LLM_FIX,
        replacement="XX",
    )
    out = apply_suggestion_to_file(tmp_path, sug)
    assert out == p.resolve()
    assert p.read_text(encoding="utf-8") == "aXX\ndef\n"


def test_apply_suggestion_to_file__invalid_position_raises(tmp_path: Path) -> None:
    p = tmp_path / "main.tex"
    p.write_text("", encoding="utf-8")
    sug = Suggestion(
        file="main.tex",
        range=TextRange(start=Position(line=1, character=0), end=Position(line=1, character=0)),
        severity=Severity.INFO,
        source=IssueSource.LLM_FIX,
        replacement="x",
    )
    with pytest.raises(SuggestionRangeError):
        apply_suggestion_to_file(tmp_path, sug)

