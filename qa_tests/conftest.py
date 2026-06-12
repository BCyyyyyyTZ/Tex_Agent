from __future__ import annotations

import os
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True, scope="session")
def _disable_auto_open_browser() -> None:
    os.environ.setdefault("TEX_AGENT_NO_OPEN_BROWSER", "1")
    os.environ.setdefault("TEX_AGENT_NO_OPEN_SIMPLE_BROWSER", "1")
    os.environ.setdefault("TEX_AGENT_NO_OPEN_IDE", "1")

