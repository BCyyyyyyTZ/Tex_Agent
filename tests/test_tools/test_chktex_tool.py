from __future__ import annotations

import json
from pathlib import Path
import pytest

from latex.chktex_runner import ChkTeXRunResult
from latex.constants import METADATA_LATEX_DIAGNOSTICS
from latex.models import DiagnosticIssue
from latex.constants import IssueSource, Severity
from latex.tex_env import TexEnvStatus
from tools.chktex_tool import ChkTeXTool

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "latex"
BROKEN = FIXTURES / "broken_braces.tex"
MULTIFILE = FIXTURES / "multifile"


def test_chktex_tool_not_found_graceful(monkeypatch) -> None:
    monkeypatch.setattr(
        "tools.chktex_tool.run_chktex",
        lambda *a, **k: ChkTeXRunResult(warnings=["chktex_not_found"]),
    )
    tool = ChkTeXTool()
    out = tool.run(
        json.dumps({"root": str(MULTIFILE), "files": ["main.tex"]})
    )
    assert out.success is True, out.error
    body = json.loads(out.output)
    assert body["issues"] == []
    assert "chktex_not_found" in body["warnings"]


def test_chktex_tool_mock_subprocess(tmp_path: Path, monkeypatch) -> None:
    root = MULTIFILE
    issue = DiagnosticIssue.build(
        file="main.tex",
        line=2,
        column=0,
        message="Warning from mock",
        source=IssueSource.CHKTEX,
        severity=Severity.WARNING,
        code="1",
    )
    monkeypatch.setattr(
        "tools.chktex_tool.run_chktex",
        lambda *a, **k: ChkTeXRunResult(
            issues=[issue],
            env=TexEnvStatus(chktex=True, paths={"chktex": "/bin/chktex"}),
            files_checked=["main.tex"],
        ),
    )
    tool = ChkTeXTool()
    out = tool.run(json.dumps({"root": str(root), "main_tex": "main.tex"}))
    assert out.success is True, out.error
    body = json.loads(out.output)
    assert len(body["issues"]) == 1
    assert out.metadata[METADATA_LATEX_DIAGNOSTICS][0]["file"] == "main.tex"
    assert out.metadata["issue_count"] == 1


def test_chktex_tool_missing_root() -> None:
    tool = ChkTeXTool()
    out = tool.run("{}")
    assert out.success is False
    assert "root" in (out.error or "")


@pytest.mark.latex_integration
@pytest.mark.skipif(
    not __import__("shutil").which("chktex"),
    reason="chktex not installed",
)
def test_chktex_integration_broken_braces() -> None:
    tool = ChkTeXTool()
    out = tool.run(json.dumps({"root": str(FIXTURES), "files": ["broken_braces.tex"]}))
    assert out.success is True, out.error
    body = json.loads(out.output)
    if body["warnings"] == ["chktex_not_found"]:
        pytest.skip("chktex not available at runtime")
    assert len(body["issues"]) >= 1
