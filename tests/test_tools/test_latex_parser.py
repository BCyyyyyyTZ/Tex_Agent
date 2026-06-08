from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from latex.paths import resolve_tex_file
from latex.single_file_parser import parse_tex_file
from tools.latex_parser import LaTeXParserTool

VALORA = Path(__file__).resolve().parents[1] / "test_latex" / "VaLoRA_TMC"
INTRO_REL = "weijun/Intro.tex"


@pytest.mark.skipif(not VALORA.is_dir(), reason="VaLoRA_TMC fixture not present")
def test_parse_valora_intro_structure() -> None:
    result = parse_tex_file(root=str(VALORA), rel_path=INTRO_REL)
    sections = result["structure"]["sections"]
    assert len(sections) >= 1
    assert sections[0]["title"] == "Introduction"
    assert sections[0]["kind"] == "section"
    assert sections[0]["start_line"] >= 1
    assert result["rel_path"] == INTRO_REL
    assert "path" in result
    assert Path(result["path"]).is_file()


@pytest.mark.skipif(not VALORA.is_dir(), reason="VaLoRA_TMC fixture not present")
def test_parse_valora_intro_via_windows_path_strings() -> None:
    root_str = str(VALORA)
    rel_win = r"weijun\Intro.tex"
    result = parse_tex_file(root=root_str, rel_path=rel_win)
    assert result["structure"]["sections"][0]["title"] == "Introduction"


@pytest.mark.skipif(not VALORA.is_dir(), reason="VaLoRA_TMC fixture not present")
def test_latex_parser_tool_json_root_rel() -> None:
    tool = LaTeXParserTool()
    payload = json.dumps({"root": str(VALORA), "rel_path": INTRO_REL})
    out = tool.run(payload)
    assert out.success is True, out.error
    body = json.loads(out.output)
    assert body["rel_path"] == INTRO_REL
    assert len(body["structure"]["sections"]) >= 1
    assert out.metadata["section_count"] >= 1


@pytest.mark.skipif(not VALORA.is_dir(), reason="VaLoRA_TMC fixture not present")
def test_latex_parser_tool_absolute_path() -> None:
    intro = (VALORA / "weijun" / "Intro.tex").resolve()
    tool = LaTeXParserTool()
    out = tool.run(json.dumps({"path": str(intro), "root": str(VALORA)}))
    assert out.success is True, out.error
    body = json.loads(out.output)
    assert body["structure"]["sections"][0]["title"] == "Introduction"
    assert len(body["diagnostics"]) == 0


def test_broken_braces_syntax_issues() -> None:
    broken = Path(__file__).resolve().parents[1] / "fixtures" / "latex" / "broken_braces.tex"
    result = parse_tex_file(path=str(broken))
    issues = result["syntax_issues"]
    assert len(issues) >= 1
    messages = " ".join(i["message"] for i in issues)
    assert "{" in messages or "环境" in messages or "end" in messages.lower()


def test_check_syntax_methods() -> None:
    tool = LaTeXParserTool()
    issues = tool.check_syntax("{ unmatched")
    assert len(issues) >= 1
    struct = tool.extract_structure("\\section{A}\n\\label{fig:1}\n\\ref{fig:1}")
    assert struct["sections"][0]["title"] == "A"
    assert struct["labels"][0]["label"] == "fig:1"
    assert any(r["key"] == "fig:1" and r["kind"] == "ref" for r in struct.get("refs", []))


def test_resolve_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        resolve_tex_file(root=str(tmp_path), rel_path="no/such.tex")
