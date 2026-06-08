from __future__ import annotations

from pathlib import Path

import pytest

from latex.conventions_index import build_conventions, parse_preamble
from latex.project_index import build_project_index

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "latex"
VALORA = Path(__file__).resolve().parent / "VaLoRA_TMC"


def test_parse_preamble_minimal() -> None:
    src = r"""
\documentclass[10pt]{article}
\usepackage{amsmath,xcolor}
\newcommand{\name}{Foo\xspace}
\newcommand{\ie}{\emph{i.e.,}\xspace}
\renewcommand\algorithmicrequire{\textbf{Input:}}
\newtheorem{definition}{Definition}
\definecolor{mypink}{rgb}{0.1,0.2,0.3}
\begin{document}
hi
"""
    conv = parse_preamble(src, defined_in="main.tex")
    assert conv.documentclass == "article"
    assert "amsmath" in conv.packages
    assert "name" in conv.macro_defs
    assert conv.macro_defs["ie"].expands_to_hint
    assert "definition" in conv.theorem_environments
    assert "mypink" in conv.colors
    assert conv.algorithm is not None
    assert conv.algorithm.require_label == "Input:"


def test_build_project_with_conventions(tmp_path: Path) -> None:
    root = tmp_path / "p"
    root.mkdir()
    (root / "main.tex").write_text(
        r"""
\documentclass{article}
\newcommand{\foo}{bar}
\begin{document}
\foo\foo
\end{document}
""",
        encoding="utf-8",
    )
    idx = build_project_index(root, main_tex="main.tex")
    assert idx.conventions is not None
    assert "foo" in idx.conventions.macro_defs
    assert idx.conventions.macro_usage.get("foo", 0) >= 2


@pytest.mark.skipif(not VALORA.is_dir(), reason="VaLoRA_TMC fixture not present")
def test_valora_conventions() -> None:
    idx = build_project_index(VALORA, main_tex="paper.tex")
    conv = idx.conventions
    assert conv is not None
    assert conv.documentclass == "IEEEtran"
    assert "algorithm" in conv.packages
    assert "algpseudocode" in conv.packages
    assert "name" in conv.macro_defs
    assert conv.macro_usage.get("name", 0) >= 50
    assert conv.macro_usage.get("eg", 0) >= 30
    assert "definition" in conv.theorem_environments
    assert conv.algorithm is not None
    assert conv.algorithm.require_label == "Input:"
    assert conv.algorithm.ensure_label == "Output:"
    assert "mypink1" in conv.colors
    assert any(t.get("parameter") == "abovecaptionskip" for t in conv.local_typography)
