from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from latex.chktex_runner import ChkTeXRunResult
from latex.constants import METADATA_LATEX_DIAGNOSTICS, METADATA_LATEX_PROJECT, METADATA_LATEX_SUGGESTIONS
from latex.latexmk_runner import LatexmkRunResult
from latex.models import DiagnosticIssue
from latex.constants import IssueSource, Severity
from latex.tex_env import TexEnvStatus
from tools.latex_collect_suggestions_tool import LatexCollectSuggestionsTool
from tools.latex_fix_prepare_tool import LatexFixPrepareTool
from workflow.workflow_registry import WorkflowRegistry

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "latex"
MULTIFILE = FIXTURES / "multifile"
ROOT_JSON = json.dumps({"root": str(MULTIFILE), "main_tex": "main.tex"})

_MOCK_ERROR = DiagnosticIssue.build(
    file="main.tex",
    line=4,
    message="mock latexmk error",
    source=IssueSource.LATEXMK,
    severity=Severity.ERROR,
)


def test_workflow_latex_diagnose_v1_registered() -> None:
    reg = WorkflowRegistry()
    assert "latex_diagnose_v1" in reg.list_workflows()
    nodes, edges = reg.load_graph_config("latex_diagnose_v1")
    node_ids = {n.node_id for n in nodes}
    assert "latex_fix_prepare" in node_ids
    assert "fix_agent" in node_ids
    assert "latex_collect_suggestions" in node_ids
    assert len(edges) == 8


def test_latex_fix_prepare_and_collect_mock_llm() -> None:
    from tools.latex_merge_tool import LatexMergeTool
    from tools.latex_slice_tool import LatexSliceTool
    from tools.latex_project_tool import LatexProjectTool

    project_out = LatexProjectTool().run(ROOT_JSON)
    assert project_out.success

    merge_out = LatexMergeTool().run(
        user_input=ROOT_JSON,
        chktex_output=json.dumps({"issues": []}),
        latexmk_output=json.dumps(
            {"issues": [_MOCK_ERROR.model_dump(mode="json")]}
        ),
        project_output=project_out.output,
        include_parser_refs=False,
    )
    assert merge_out.success

    slice_out = LatexSliceTool().run(
        user_input=ROOT_JSON,
        merge_output=merge_out.output,
        severity="error",
    )
    assert slice_out.success

    prepare_out = LatexFixPrepareTool().run(
        user_input=ROOT_JSON,
        merge_output=merge_out.output,
        slice_output=slice_out.output,
        project_output=project_out.output,
        max_issues=5,
    )
    assert prepare_out.success, prepare_out.error
    batch = json.loads(prepare_out.output)
    assert batch["task_count"] >= 1

    issue_id = batch["tasks"][0]["issue_id"]
    mock_agent = {
        "result": json.dumps(
            [
                {
                    "issue_id": issue_id,
                    "file": "main.tex",
                    "replacement": "{\\fixed}",
                    "message": "mock fix",
                    "rationale_zh": "测试",
                    "range": {
                        "start": {"line": 3, "character": 0},
                        "end": {"line": 3, "character": 10},
                    },
                    "source": "llm_fix",
                }
            ],
            ensure_ascii=False,
        ),
        "summary": "mock",
        "confidence": 0.95,
        "metadata": {},
    }

    collect_out = LatexCollectSuggestionsTool().run(
        fix_agent_output=json.dumps(mock_agent),
        fix_prepare_output=prepare_out.output,
        merge_output=merge_out.output,
    )
    assert collect_out.success, collect_out.error
    body = json.loads(collect_out.output)
    assert body["suggestion_count"] == 1
    assert body["suggestions"][0]["replacement"]
    assert METADATA_LATEX_SUGGESTIONS in collect_out.metadata


@pytest.mark.slow
def test_latex_diagnose_v1_invoke_mocked(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("openai")
    from workflow.graph_builder import build_dynamic_graph
    from workflow.workflow_registry import WorkflowRegistry

    monkeypatch.setattr(
        "tools.chktex_tool.run_chktex",
        lambda *a, **k: ChkTeXRunResult(
            issues=[],
            env=TexEnvStatus(chktex=True),
            files_checked=["main.tex"],
        ),
    )
    monkeypatch.setattr(
        "tools.latexmk_tool.run_latexmk",
        lambda *a, **k: LatexmkRunResult(
            success=False,
            issues=[_MOCK_ERROR],
            env=TexEnvStatus(latexmk=True),
            warnings=[],
        ),
    )

    mock_suggestions = [
        {
            "issue_id": _MOCK_ERROR.id,
            "file": "main.tex",
            "replacement": "{\\fixed}",
            "message": "mock",
            "rationale_zh": "mock",
            "range": {
                "start": {"line": 3, "character": 0},
                "end": {"line": 3, "character": 5},
            },
            "source": "llm_fix",
        }
    ]
    agent_json = json.dumps(
        {
            "result": json.dumps(mock_suggestions),
            "summary": "mock fix",
            "confidence": 0.9,
            "metadata": {},
        }
    )

    mock_agent_instance = MagicMock()
    mock_agent_instance.run.return_value = agent_json

    monkeypatch.setattr(
        "workflow.graph_builder._build_agent_instance",
        lambda *a, **k: mock_agent_instance,
    )

    reg = WorkflowRegistry()
    nodes, edges = reg.load_graph_config("latex_diagnose_v1")
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
    assert METADATA_LATEX_SUGGESTIONS in meta
    report = json.loads(str(meta["latex_report"].get("result", "")))
    assert report["workflow"] == "latex_diagnose_v1"
    assert report["suggestion_count"] >= 1
