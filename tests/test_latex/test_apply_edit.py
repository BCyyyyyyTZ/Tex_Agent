from __future__ import annotations

from pathlib import Path

import pytest

from latex.apply_edit import apply_suggestion_to_file, offset_from_position

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "latex" / "multifile"


def test_offset_from_position() -> None:
    text = "ab\ncd\n"
    assert offset_from_position(text, 0, 0) == 0
    assert offset_from_position(text, 1, 0) == 3
    assert offset_from_position(text, 1, 1) == 4


def test_apply_suggestion_replaces_range() -> None:
    target = FIXTURES / "chapters" / "intro.tex"
    original = target.read_text(encoding="utf-8")
    try:
        suggestion = {
            "file": "chapters/intro.tex",
            "range": {
                "start": {"line": 0, "character": 0},
                "end": {"line": 0, "character": 0},
            },
            "replacement": "% test ghost apply\n",
            "rationale_zh": "test",
            "message": "test",
            "source": "llm_fix",
        }
        apply_suggestion_to_file(FIXTURES, suggestion)
        updated = target.read_text(encoding="utf-8")
        assert updated.startswith("% test ghost apply\n")
    finally:
        target.write_text(original, encoding="utf-8")


def test_apply_suggestion_missing_file() -> None:
    suggestion = {
        "file": "not_exists.tex",
        "range": {"start": {"line": 0, "character": 0}, "end": {"line": 0, "character": 0}},
        "replacement": "x",
        "source": "llm_fix",
    }
    with pytest.raises(FileNotFoundError):
        apply_suggestion_to_file(FIXTURES, suggestion)
