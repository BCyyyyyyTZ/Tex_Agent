from __future__ import annotations

import json
from pathlib import Path

import pytest

from latex.constants import METADATA_LATEX_DIAGNOSTICS
from latex.latexmk_runner import LatexmkRunResult
from latex.models import DiagnosticIssue
from latex.constants import IssueSource, Severity
from latex.tex_env import TexEnvStatus
from tools.latexmk_tool import LatexmkTool

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "latex"
BROKEN = FIXTURES / "broken_braces.tex"
MULTIFILE = FIXTURES / "multifile"


def test_latexmk_tool_not_found_graceful(monkeypatch) -> None:
    monkeypatch.setattr(
        "tools.latexmk_tool.run_latexmk",
        lambda *a, **k: LatexmkRunResult(
            success=True,
            warnings=["latexmk_not_found"],
        ),
    )
    tool = LatexmkTool()
    out = tool.run(
        json.dumps({"root": str(MULTIFILE), "main_tex": "main.tex"})
    )
    assert out.success is True, out.error
    body = json.loads(out.output)
    assert body["issues"] == []
    assert "latexmk_not_found" in body["warnings"]


def test_latexmk_tool_mock_compile(monkeypatch) -> None:
    issue = DiagnosticIssue.build(
        file="main.tex",
        line=5,
        column=0,
        message="Fatal error",
        source=IssueSource.LATEXMK,
        severity=Severity.ERROR,
        code="bang",
    )
    monkeypatch.setattr(
        "tools.latexmk_tool.run_latexmk",
        lambda *a, **k: LatexmkRunResult(
            issues=[issue],
            success=False,
            env=TexEnvStatus(latexmk=True, paths={"latexmk": "/bin/latexmk"}),
            log_path="main.log",
            log_tail="l.5 error",
        ),
    )
    tool = LatexmkTool()
    out = tool.run(
        json.dumps({"root": str(MULTIFILE), "main_tex": "main.tex", "mode": "fast"})
    )
    assert out.success is True, out.error
    body = json.loads(out.output)
    assert body["success"] is False
    assert len(body["issues"]) == 1
    assert out.metadata["compile_success"] is False
    assert out.metadata[METADATA_LATEX_DIAGNOSTICS][0]["file"] == "main.tex"


def test_latexmk_tool_missing_root() -> None:
    tool = LatexmkTool()
    out = tool.run("{}")
    assert out.success is False


def test_build_latexmk_argv_fast() -> None:
    from latex.latexmk_runner import build_latexmk_argv

    argv = build_latexmk_argv("main.tex", latexmk_path="/bin/latexmk", mode="fast")
    assert argv[0] == "/bin/latexmk"
    assert "-draftmode" in argv
    assert "-halt-on-error" in argv
    assert argv[-1] == "main.tex"


def test_build_latexmk_argv_full() -> None:
    from latex.latexmk_runner import build_latexmk_argv

    argv = build_latexmk_argv("paper.tex", latexmk_path="latexmk", mode="full")
    assert "-draftmode" not in argv


@pytest.mark.latex_integration
@pytest.mark.skipif(
    not __import__("shutil").which("latexmk"),
    reason="latexmk not installed",
)
def test_latexmk_integration_broken_braces() -> None:
    tool = LatexmkTool()
    out = tool.run(
        json.dumps(
            {
                "root": str(FIXTURES),
                "main_tex": "broken_braces.tex",
                "mode": "fast",
            }
        )
    )
    assert out.success is True, out.error
    body = json.loads(out.output)
    if "latexmk_not_found" in body.get("warnings", []):
        pytest.skip("latexmk not available")
    assert body["success"] is False
    assert len(body["issues"]) >= 1
