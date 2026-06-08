from __future__ import annotations

from pathlib import Path

import pytest

from latex.bib_index import build_bib_index, parse_bib_file, parse_bibliography_declarations
from latex.project_index import build_project_index

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "latex"
WITH_BIB = FIXTURES / "with_bib"
VALORA = Path(__file__).resolve().parent / "VaLoRA_TMC"


def test_parse_bibliography_declarations() -> None:
    src = r"\bibliography{reference,other}"
    paths = parse_bibliography_declarations(src)
    assert paths == ["reference.bib", "other.bib"]


def test_parse_bib_file() -> None:
    entries = parse_bib_file(WITH_BIB / "refs.bib")
    assert "knownKey" in entries
    assert entries["knownKey"].title == "A Known Paper"
    assert "Alice" in entries["knownKey"].author


def test_with_bib_project_index() -> None:
    index = build_project_index(WITH_BIB, main_tex="main.tex")
    assert "refs.bib" in index.bibliography_files
    assert "knownKey" in index.bib_entries
    assert index.bib_entries["knownKey"].title == "A Known Paper"


def test_missing_cite_key_warning() -> None:
    index = build_project_index(WITH_BIB, main_tex="main.tex")
    _, _, issues = build_bib_index(index, check_missing_cites=True)
    assert any("missingKey" in i.message for i in issues)


@pytest.mark.skipif(not VALORA.is_dir(), reason="VaLoRA_TMC fixture not present")
def test_valora_cite_keys_in_reference_bib() -> None:
    index = build_project_index(VALORA, main_tex="paper.tex")
    assert any(f.endswith("reference.bib") for f in index.bibliography_files)
    assert len(index.bib_entries) > 100

    cite_keys = {r.key for r in index.refs if r.kind == "cite"}
    sample = list(cite_keys)[:8]
    found = sum(1 for k in sample if k in index.bib_entries)
    assert found >= 5, f"expected >=5 of {sample} in bib, got {found}"


@pytest.mark.skipif(not VALORA.is_dir(), reason="VaLoRA_TMC fixture not present")
def test_valora_intro_cite_sample() -> None:
    index = build_project_index(VALORA, main_tex="paper.tex")
    intro_cites = {r.key for r in index.refs if r.file == "weijun/Intro.tex" and r.kind == "cite"}
    assert intro_cites
    matched = [k for k in list(intro_cites)[:10] if k in index.bib_entries]
    assert len(matched) >= 3
