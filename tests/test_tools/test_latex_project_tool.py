from __future__ import annotations

import json
from pathlib import Path

from latex.serialize import from_json
from latex.models import ProjectIndex
from tools.latex_project_tool import LatexProjectTool


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "latex" / "multifile"


def test_latex_project_tool_json_input() -> None:
    tool = LatexProjectTool()
    payload = json.dumps({"root": str(FIXTURES)})
    result = tool.run(payload)
    assert result.success is True, result.error
    index = from_json(ProjectIndex, result.output)
    assert index.main_tex == "main.tex"
    assert "chapters/intro.tex" in index.files
    assert result.metadata is not None
    assert result.metadata.get("main_tex") == "main.tex"


def test_latex_project_tool_plain_path() -> None:
    tool = LatexProjectTool()
    result = tool.run(str(FIXTURES))
    assert result.success is True, result.error


def test_latex_project_tool_missing_root() -> None:
    tool = LatexProjectTool()
    result = tool.run("{}")
    assert result.success is False
    assert result.error
