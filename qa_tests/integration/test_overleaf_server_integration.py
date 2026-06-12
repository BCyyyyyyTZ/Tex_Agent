from __future__ import annotations

import importlib

import pytest
from fastapi.testclient import TestClient


def _import_overleaf_server():
    try:
        return importlib.import_module("ui.overleaf.server")
    except RuntimeError as e:
        if "python-multipart" in str(e):
            pytest.skip(str(e))
        raise


@pytest.mark.integration
def test_overleaf_server__index_ok() -> None:
    m = _import_overleaf_server()
    app = m.create_app()
    with TestClient(app) as c:
        r = c.get("/")
        assert r.status_code == 200

