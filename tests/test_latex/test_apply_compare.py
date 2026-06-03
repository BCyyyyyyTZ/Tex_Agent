from __future__ import annotations

from pathlib import Path

from latex.apply_compare import apply_suggestion_compare_to_file

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "latex" / "multifile"


def test_apply_compare_keeps_old_text_as_comment() -> None:
    target = FIXTURES / "chapters" / "intro.tex"
    original = target.read_text(encoding="utf-8")
    try:
        suggestion = {
            "file": "chapters/intro.tex",
            "range": {
                "start": {"line": 0, "character": 0},
                "end": {"line": 0, "character": 7},
            },
            "replacement": "Replaced intro line",
            "source": "llm_fix",
            "message": "test",
            "rationale_zh": "test",
        }
        apply_suggestion_compare_to_file(FIXTURES, suggestion)
        updated = target.read_text(encoding="utf-8")
        assert "% [TeX_Agent][compare]" in updated
        assert "Replaced intro line" in updated
    finally:
        target.write_text(original, encoding="utf-8")
