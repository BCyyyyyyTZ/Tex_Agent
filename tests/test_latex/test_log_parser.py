from __future__ import annotations

from pathlib import Path

from latex.constants import IssueSource
from latex.log_parser import parse_latex_log, tail_log_text

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "latex"


def test_parse_bang_and_line_number() -> None:
    text = """
(./broken_braces.tex
! Missing } inserted.
<inserted text>
l.7 \\end{document}
"""
    issues = parse_latex_log(text, root=Path("/proj"), default_file="broken_braces.tex")
    assert len(issues) >= 1
    err = issues[0]
    assert err.source == IssueSource.LATEXMK
    assert err.file == "broken_braces.tex"
    assert err.line == 7
    assert "Missing" in err.message


def test_parse_file_line_format() -> None:
    text = "broken_braces.tex:7: ==> Fatal error occurred, no output PDF file produced!"
    issues = parse_latex_log(text, root=Path("/proj"))
    assert len(issues) == 1
    assert issues[0].line == 7
    assert issues[0].severity.value == "error"


def test_parse_undefined_reference_warning() -> None:
    text = """
(./main.tex
LaTeX Warning: Reference `fig:missing' on page 2 undefined on input line 42.
"""
    issues = parse_latex_log(text, default_file="main.tex")
    warn = [i for i in issues if i.code == "undefined_reference"]
    assert len(warn) == 1
    assert "fig:missing" in warn[0].message


def test_parse_undefined_citation_warning() -> None:
    text = "LaTeX Warning: Citation `foo2020' on page 1 undefined on input line 5."
    issues = parse_latex_log(text, default_file="intro.tex")
    assert any(i.code == "undefined_citation" for i in issues)


def test_parse_sample_fixture_log() -> None:
    log = FIXTURES / "sample_compile_error.log"
    text = log.read_text(encoding="utf-8")
    issues = parse_latex_log(text, root=FIXTURES.parent, default_file="broken_braces.tex")
    assert len(issues) >= 1


def test_parse_nested_file_entry_with_prefix_chars() -> None:
    text = """
) (./weijun/Background.tex
! Undefined control sequence.
l.17 \\notcommand
"""
    issues = parse_latex_log(text, default_file="paper.tex")
    assert len(issues) >= 1
    assert issues[0].file == "weijun/Background.tex"
    assert issues[0].line == 17


def test_tail_log_text() -> None:
    text = "\n".join(f"line{i}" for i in range(100))
    tail = tail_log_text(text, max_lines=10)
    assert tail.startswith("line90")
    assert "line0" not in tail
