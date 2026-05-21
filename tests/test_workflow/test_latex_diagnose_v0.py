from __future__ import annotations

import json
from pathlib import Path

import pytest

from latex.chktex_runner import ChkTeXRunResult
from latex.constants import METADATA_LATEX_DIAGNOSTICS, METADATA_LATEX_PROJECT
from latex.latexmk_runner import LatexmkRunResult
from latex.models import DiagnosticIssue
from latex.constants import IssueSource, Severity
from latex.tex_env import TexEnvStatus
from tools.latex_merge_tool import LatexMergeTool
from tools.latex_report_tool import LatexReportTool
from workflow.workflow_registry import WorkflowRegistry

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "latex"
MULTIFILE = FIXTURES / "multifile"
ROOT_JSON = json.dumps({"root": str(MULTIFILE), "main_tex": "main.tex"})


def test_workflow_latex_diagnose_v0_registered() -> None:
    reg = WorkflowRegistry()
    assert "latex_diagnose_v0" in reg.list_workflows()
    nodes, edges = reg.load_graph_config("latex_diagnose_v0")
    node_ids = {n.node_id for n in nodes}
    assert node_ids == {
        "latex_project",
        "chktex",
        "latexmk",
        "latex_merge",
        "latex_slice",
        "latex_report",
    }
    assert len(edges) == 5


def test_latex_merge_tool_combines_outputs() -> None:
    chktex_issue = DiagnosticIssue.build(
        file="main.tex",
        line=2,
        message="chktex warn",
        source=IssueSource.CHKTEX,
        severity=Severity.WARNING,
    )
    mk_issue = DiagnosticIssue.build(
        file="main.tex",
        line=3,
        message="latex error",
        source=IssueSource.LATEXMK,
        severity=Severity.ERROR,
    )
    tool = LatexMergeTool()
    out = tool.run(
        user_input=ROOT_JSON,
        chktex_output=json.dumps({"issues": [chktex_issue.model_dump(mode="json")]}),
        latexmk_output=json.dumps({"issues": [mk_issue.model_dump(mode="json")]}),
        project_output="",
        include_parser_refs=False,
    )
    assert out.success is True, out.error
    body = json.loads(out.output)
    assert body["issue_count"] == 2
    assert out.metadata[METADATA_LATEX_DIAGNOSTICS]


def test_latex_report_tool_assembles_report() -> None:
    merge_body = {
        "issues": [
            DiagnosticIssue.build(
                file="main.tex",
                line=1,
                message="e",
                source=IssueSource.LATEXMK,
                severity=Severity.ERROR,
            ).model_dump(mode="json")
        ],
        "issue_count": 1,
        "sources": {"latexmk": 1},
    }
    slice_body = {
        "slices": [
            {
                "issue_id": "x",
                "file": "main.tex",
                "start_line": 1,
                "end_line": 1,
                "snippet": "line",
                "context_lines": 2,
            }
        ],
        "slice_count": 1,
    }
    project_body = json.loads(
        __import__("tools.latex_project_tool", fromlist=["LatexProjectTool"])
        .LatexProjectTool()
        .run(ROOT_JSON)
        .output
    )
    tool = LatexReportTool()
    out = tool.run(
        user_input=ROOT_JSON,
        project_output=json.dumps(project_body),
        merge_output=json.dumps(merge_body),
        slice_output=json.dumps(slice_body),
    )
    assert out.success is True, out.error
    report = json.loads(out.output)
    assert report["workflow"] == "latex_diagnose_v0"
    assert report["diagnostics"]["issue_count"] == 1
    assert report["slice_count"] == 1
    assert METADATA_LATEX_PROJECT in out.metadata


@pytest.mark.slow
def test_latex_diagnose_v0_invoke_mocked(monkeypatch: pytest.MonkeyPatch) -> None:
    """端到端构图执行；chktex/latexmk 用 mock，避免依赖本机 TeX。"""
    pytest.importorskip("openai")
    from workflow.graph_builder import build_dynamic_graph
    from workflow.workflow_registry import WorkflowRegistry

    monkeypatch.setattr(
        "tools.chktex_tool.run_chktex",
        lambda *a, **k: ChkTeXRunResult(
            issues=[
                DiagnosticIssue.build(
                    file="main.tex",
                    line=2,
                    message="mock chktex",
                    source=IssueSource.CHKTEX,
                    severity=Severity.WARNING,
                )
            ],
            env=TexEnvStatus(chktex=True),
            files_checked=["main.tex"],
        ),
    )
    monkeypatch.setattr(
        "tools.latexmk_tool.run_latexmk",
        lambda *a, **k: LatexmkRunResult(
            success=False,
            issues=[
                DiagnosticIssue.build(
                    file="main.tex",
                    line=4,
                    message="mock latexmk",
                    source=IssueSource.LATEXMK,
                    severity=Severity.ERROR,
                )
            ],
            env=TexEnvStatus(latexmk=True),
            warnings=[],
        ),
    )

    reg = WorkflowRegistry()
    nodes, edges = reg.load_graph_config("latex_diagnose_v0")
    app = build_dynamic_graph(nodes, edges, default_history_mode="minimal")

    result = app.invoke(
        {
            "input": ROOT_JSON,
            "messages": [],
            "metadata": {},
        }
    )
    assert result.get("error") in (None, "")
    meta = result.get("metadata") or {}
    assert METADATA_LATEX_PROJECT in meta
    assert METADATA_LATEX_DIAGNOSTICS in meta
    assert "latex_report" in meta
    report = json.loads(str(meta["latex_report"].get("result", "")))
    assert report["diagnostics"]["issue_count"] >= 1
