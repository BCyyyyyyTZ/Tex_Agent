from __future__ import annotations

from pathlib import Path

from latex.chktex_parser import parse_chktex_output


def test_parse_v0_format() -> None:
    text = "main.tex:42:5:3: You should enclose the previous parenthesis with `{}'."
    issues = parse_chktex_output(text, root=Path("/proj"), default_file="main.tex")
    assert len(issues) == 1
    assert issues[0].file == "main.tex"
    assert issues[0].line == 42
    assert issues[0].column == 5
    assert issues[0].code == "3"
    assert issues[0].source.value == "chktex"


def test_parse_v1_format() -> None:
    text = "Warning 8 in chapters/intro.tex line 10: Wrong length of dash."
    root = Path("/proj")
    issues = parse_chktex_output(text, root=root)
    assert len(issues) == 1
    assert issues[0].file == "chapters/intro.tex"
    assert issues[0].line == 10
    assert issues[0].code == "8"


def test_parse_lacheck_v3_format() -> None:
    text = '"weijun/Intro.tex", line 3: Warning 12: Interword spacing'
    issues = parse_chktex_output(text)
    assert issues[0].file == "weijun/Intro.tex"
    assert issues[0].line == 3


def test_parse_chktex_prefix_line() -> None:
    text = (
        "chktex: WARNING -- main.tex:7:1:1: Warning 15: "
        "No match found for `document'."
    )
    issues = parse_chktex_output(text, default_file="main.tex")
    assert len(issues) == 1
    assert issues[0].line == 7
    assert issues[0].severity.value == "error"


def test_structural_brace_mismatch_is_error() -> None:
    text = 'paper.tex:155:1:17: No match found for `{`.'
    issues = parse_chktex_output(text, default_file="paper.tex")
    assert len(issues) == 1
    assert issues[0].severity.value == "error"
    assert issues[0].line == 155


def test_deduplicate_same_issue() -> None:
    line = "main.tex:1:0:1: Duplicate."
    issues = parse_chktex_output(line + "\n" + line, default_file="main.tex")
    assert len(issues) == 1


def test_windows_path_normalized() -> None:
    text = r"chapters\part.tex:2:0:4: Message here."
    root = Path("F:/proj")
    issues = parse_chktex_output(text, root=root)
    assert issues[0].file == "chapters/part.tex"
