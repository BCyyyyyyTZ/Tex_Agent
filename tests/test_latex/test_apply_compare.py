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


def test_apply_compare_empty_range_does_not_emit_empty_comment(tmp_path) -> None:
    target = tmp_path / "a.tex"
    target.write_text("hello\n", encoding="utf-8")
    suggestion = {
        "file": "a.tex",
        "range": {
            "start": {"line": 0, "character": 0},
            "end": {"line": 0, "character": 0},
        },
        "replacement": "HELLO",
        "source": "llm_fix",
        "message": "test",
        "rationale_zh": "test",
    }
    apply_suggestion_compare_to_file(tmp_path, suggestion)
    updated = target.read_text(encoding="utf-8")
    assert "(empty)" not in updated
    assert "% [TeX_Agent][compare]" not in updated
    assert updated.startswith("HELLO")


def test_apply_compare_empty_range_is_idempotent(tmp_path) -> None:
    target = tmp_path / "a.tex"
    target.write_text("hello\n", encoding="utf-8")
    suggestion = {
        "file": "a.tex",
        "range": {
            "start": {"line": 0, "character": 0},
            "end": {"line": 0, "character": 0},
        },
        "replacement": "HELLO",
        "source": "llm_fix",
        "message": "test",
        "rationale_zh": "test",
    }
    apply_suggestion_compare_to_file(tmp_path, suggestion)
    once = target.read_text(encoding="utf-8")
    apply_suggestion_compare_to_file(tmp_path, suggestion)
    twice = target.read_text(encoding="utf-8")
    assert twice == once
