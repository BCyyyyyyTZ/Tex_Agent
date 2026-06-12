from __future__ import annotations

import importlib

import pytest
from fastapi.testclient import TestClient

def _create_app():
    try:
        m = importlib.import_module("ui.web.server")
    except RuntimeError as e:
        if "python-multipart" in str(e):
            pytest.skip(str(e))
        raise
    return m.create_app()


def test_web_server__health_ok() -> None:
    app = _create_app()
    with TestClient(app) as c:
        r = c.get("/api/health")
        assert r.status_code == 200
        assert r.json().get("status") == "ok"


def test_web_server__index_headers_no_cache() -> None:
    app = _create_app()
    with TestClient(app) as c:
        r = c.get("/")
        assert r.status_code == 200
        cc = r.headers.get("cache-control", "")
        assert "no-store" in cc

