from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from latex.ghost_server import create_ghost_app
from latex.watch_service import WatchService

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "latex" / "multifile"


@pytest.fixture
def ghost_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
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
        watch_id="test_ghost",
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


def test_ghost_health(ghost_client: TestClient) -> None:
    r = ghost_client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["mode"] == "ghost"


def test_ghost_snapshot_and_file(ghost_client: TestClient) -> None:
    r = ghost_client.get("/api/snapshot")
    assert r.status_code == 200
    body = r.json()
    assert body["root"]
    assert body["status"] == "running"
    assert "error_signature" in body

    r2 = ghost_client.get("/api/file", params={"path": "main.tex"})
    assert r2.status_code == 200
    assert "lines" in r2.json()


def test_ghost_apply_suggestion(ghost_client: TestClient) -> None:
    import latex.ghost_server as gs

    svc = gs._service
    assert svc is not None
    target = FIXTURES / "chapters" / "intro.tex"
    original = target.read_text(encoding="utf-8")
    try:
        payload = {
            "suggestion": {
                "file": "chapters/intro.tex",
                "range": {
                    "start": {"line": 0, "character": 0},
                    "end": {"line": 0, "character": 0},
                },
                "replacement": "% ghost apply test\n",
                "rationale_zh": "测试应用",
                "message": "test",
                "source": "llm_fix",
            }
        }
        r = ghost_client.post("/api/apply", json=payload)
        assert r.status_code == 200
        assert r.json()["ok"] is True
        assert target.read_text(encoding="utf-8").startswith("% ghost apply test\n")
    finally:
        target.write_text(original, encoding="utf-8")


def test_ghost_apply_suggestion_compare_mode(ghost_client: TestClient) -> None:
    target = FIXTURES / "chapters" / "intro.tex"
    original = target.read_text(encoding="utf-8")
    try:
        payload = {
            "mode": "compare",
            "suggestion": {
                "file": "chapters/intro.tex",
                "range": {
                    "start": {"line": 0, "character": 0},
                    "end": {"line": 0, "character": 7},
                },
                "replacement": "Updated",
                "rationale_zh": "测试对比应用",
                "message": "test",
                "source": "llm_fix",
            },
        }
        r = ghost_client.post("/api/apply", json=payload)
        assert r.status_code == 200
        assert r.json()["ok"] is True
        assert r.json()["mode"] == "compare"
        updated = target.read_text(encoding="utf-8")
        assert "% [TeX_Agent][compare]" in updated
        assert "Updated" in updated
    finally:
        target.write_text(original, encoding="utf-8")


def test_ghost_missing_file(ghost_client: TestClient) -> None:
    r = ghost_client.get("/api/file", params={"path": "not_exists.tex"})
    assert r.status_code == 404


def test_ghost_apply_rejects_out_of_range(ghost_client: TestClient) -> None:
    payload = {
        "suggestion": {
            "file": "main.tex",
            "range": {
                "start": {"line": 999, "character": 0},
                "end": {"line": 999, "character": 1},
            },
            "replacement": "x",
            "rationale_zh": "测试越界",
            "message": "test",
            "source": "llm_fix",
        }
    }
    r = ghost_client.post("/api/apply", json=payload)
    assert r.status_code == 400


def test_ghost_polish_api_success(
    ghost_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    import latex.ghost_server as gs

    class _FakeAgent:
        def __init__(self, *args, **kwargs):
            pass

        def run(self, _msg):
            return SimpleNamespace(
                content=(
                    '{"file":"main.tex","original_text":"\\\\documentclass[10pt,journal,compsoc]{IEEEtran}",'
                    '"polished_text":"\\\\documentclass[10pt,journal,compsoc]{IEEEtran}",'
                    '"problem_zh":"可读性可提升","advice_zh":"保持格式，提升表达。"}'
                )
            )

    monkeypatch.setattr(gs, "SimpleAgent", _FakeAgent)
    r = ghost_client.post(
        "/api/ghost/polish",
        json={
            "query": "请更学术一点",
            "target_file": "main.tex",
            "context_file": "main.tex",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["suggestion"]["source"] == "llm_polish"
    snap = ghost_client.get("/api/snapshot").json()
    assert len(snap["polish_suggestions"]) >= 1


def test_ghost_polish_api_missing_file(ghost_client: TestClient) -> None:
    r = ghost_client.post(
        "/api/ghost/polish",
        json={
            "query": "请润色",
            "target_file": "not_exists.tex",
            "context_file": "main.tex",
        },
    )
    assert r.status_code == 404


def test_ghost_index_html(ghost_client: TestClient) -> None:
    r = ghost_client.get("/")
    assert r.status_code == 200
    assert "ghost" in r.text.lower() or "TeX" in r.text


def test_ghost_snapshot_without_service(monkeypatch: pytest.MonkeyPatch) -> None:
    import latex.ghost_server as gs

    monkeypatch.setattr(gs, "_service", None)
    client = TestClient(create_ghost_app())
    r = client.get("/api/snapshot")
    assert r.status_code == 503
