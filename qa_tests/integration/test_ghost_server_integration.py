from __future__ import annotations

import importlib

import pytest
from fastapi.testclient import TestClient


@pytest.mark.integration
def test_ghost_server__health_ok() -> None:
    try:
        m = importlib.import_module("latex.ghost_server")
    except Exception as e:  # noqa: BLE001
        pytest.skip(str(e))
    app = m.create_ghost_app()
    with TestClient(app) as c:
        r = c.get("/api/health")
        assert r.status_code == 200
        body = r.json()
        assert body.get("status") == "ok"
        assert body.get("mode") == "ghost"

