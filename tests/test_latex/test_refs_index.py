from __future__ import annotations

from pathlib import Path

import pytest

from latex.bib_index import build_bib_index
from latex.project_index import build_project_index
from latex.refs_index import build_refs_index, collect_undefined_ref_issues
from latex.structure_extract import extract_structure
from tools.latex_parser import LaTeXParserTool

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "latex"
CROSS_REF = FIXTURES / "cross_ref"
VALORA = Path(__file__).resolve().parent / "VaLoRA_TMC"


def test_cross_ref_global_labels_and_refs() -> None:
    index = build_project_index(CROSS_REF, main_tex="main.tex")
    assert "fig:mainfig" in index.labels
    assert index.labels["fig:mainfig"].defined_in == "chapters/fig.tex"

    ref_keys = {(r.key, r.file, r.kind) for r in index.refs}
    assert ("fig:mainfig", "main.tex", "ref") in ref_keys
    assert ("fig:undefined", "main.tex", "ref") in ref_keys


def test_undefined_ref_diagnostic() -> None:
    index = build_project_index(CROSS_REF, main_tex="main.tex")
    issues = collect_undefined_ref_issues(index)
    messages = [i.message for i in issues]
    assert any("fig:undefined" in m for m in messages)


def test_build_refs_index_without_enrich_flag() -> None:
    index = build_project_index(CROSS_REF, main_tex="main.tex", enrich=False)
    assert index.labels == {}
    labels, refs, issues = build_refs_index(index)
    assert "fig:mainfig" in labels
    assert any(r.key == "fig:undefined" for r in refs)
    assert any("fig:undefined" in i.message for i in issues)


def test_single_file_structure_refs() -> None:
    source = r"""
\section{A}
\label{fig:a}
See \ref{fig:a} and \eqref{fig:b}.
\cite{key1}
"""
    struct = extract_structure(source)
    assert struct["refs"]
    kinds = {r["kind"] for r in struct["refs"]}
    assert "ref" in kinds
    assert "cite" in kinds
    assert any(r["key"] == "fig:a" and r["kind"] == "ref" for r in struct["refs"])


def test_latex_parser_tool_includes_refs_in_structure() -> None:
    tool = LaTeXParserTool()
    payload = (
        '{"root": "'
        + str(CROSS_REF).replace("\\", "/")
        + '", "rel_path": "main.tex"}'
    )
    out = tool.run(payload)
    assert out.success is True, out.error
    import json

    body = json.loads(out.output)
    assert "refs" in body["structure"]


@pytest.mark.skipif(not VALORA.is_dir(), reason="VaLoRA_TMC fixture not present")
def test_valora_cross_file_label_ref() -> None:
    index = build_project_index(VALORA, main_tex="paper.tex")
    assert "fig:VaLoRA" in index.labels
    valora_refs = [r for r in index.refs if r.key == "fig:VaLoRA" and r.kind == "ref"]
    assert len(valora_refs) >= 1
    assert index.labels["fig:VaLoRA"].defined_in


@pytest.mark.skipif(not VALORA.is_dir(), reason="VaLoRA_TMC fixture not present")
def test_valora_appendix_ref_via_windows_rel() -> None:
    from latex.single_file_parser import parse_tex_file

    result = parse_tex_file(root=str(VALORA), rel_path=r"weijun\Appendix.tex")
    refs = result["structure"]["refs"]
    assert any(r["key"] == "fig:templatepdf" and r["kind"] == "ref" for r in refs)


@pytest.mark.skipif(not VALORA.is_dir(), reason="VaLoRA_TMC fixture not present")
def test_valora_templatepdf_label_resolves() -> None:
    index = build_project_index(VALORA, main_tex="paper.tex")
    assert "fig:templatepdf" in index.labels
    refs = [r for r in index.refs if r.key == "fig:templatepdf"]
    assert refs
