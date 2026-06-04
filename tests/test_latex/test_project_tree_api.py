from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from latex.ghost_server import create_ghost_app
from latex.constants import IssueSource
from latex.models import Position, Suggestion, TextRange
from latex.watch_service import WatchService

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "latex" / "multifile"


@pytest.fixture
def tree_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    import latex.ghost_server as gs
    import latex.watch_service as ws

    monkeypatch.setattr(
        ws,
        "resolve_target_files",
        lambda root, main_tex=None: ["main.tex"],
    )
    monkeypatch.setattr(
        ws,
        "run_chktex",
        lambda root, rel_files: SimpleNamespace(issues=[], warnings=[]),
    )

    svc = WatchService(
        watch_id="test_project_tree",
        root=str(FIXTURES),
        main_tex="main.tex",
        enable_latexmk=False,
    )
    svc.start()
    monkeypatch.setattr(gs, "_service", svc)
    client = TestClient(create_ghost_app())
    try:
        yield client
    finally:
        svc.stop()


def test_project_tree_api_contains_input_hierarchy(tree_client: TestClient) -> None:
    resp = tree_client.get("/api/project-tree")
    assert resp.status_code == 200
    body = resp.json()
    assert body["main_tex"] == "main.tex"
    nodes = body["nodes"]
    assert nodes
    assert nodes[0]["path"] == "main.tex"
    child_paths = [child["path"] for child in nodes[0]["children"]]
    assert "chapters/intro.tex" in child_paths


def test_snapshot_contains_file_status_indexes(tree_client: TestClient) -> None:
    import latex.ghost_server as gs

    svc = gs._service
    assert svc is not None
    with svc._lock:  # noqa: SLF001 - 测试内直接构造状态
        svc.suggestions = [
            Suggestion(
                file="main.tex",
                range=TextRange(
                    start=Position(line=0, character=0),
                    end=Position(line=0, character=1),
                ),
                replacement="x",
                source=IssueSource.LLM_FIX,
            )
        ]
        svc.polish_suggestions = [
            Suggestion(
                file="chapters/intro.tex",
                range=TextRange(
                    start=Position(line=0, character=0),
                    end=Position(line=0, character=1),
                ),
                replacement="y",
                source=IssueSource.LLM_POLISH,
            )
        ]
    snap = tree_client.get("/api/snapshot")
    assert snap.status_code == 200
    body = snap.json()
    assert body["errors_by_file"]["main.tex"] == 1
    assert body["polish_by_file"]["chapters/intro.tex"] == 1
