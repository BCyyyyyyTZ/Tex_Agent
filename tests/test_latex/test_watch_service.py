import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from latex.watch_service import WatchService
from latex.watch_events import WatchEvent


@pytest.fixture
def mock_simple_agent():
    with patch("latex.watch_service.SimpleAgent") as mock_agent:
        instance = mock_agent.return_value
        mock_msg = MagicMock()
        mock_msg.content = '{"replacement": "fixed text", "rationale_zh": "测试修复"}'
        instance.run.return_value = mock_msg
        yield mock_agent


@pytest.fixture
def mock_run_chktex():
    with patch("latex.watch_service.run_chktex") as mock_chktex:
        mock_res = MagicMock()
        mock_res.issues = []
        mock_res.warnings = []
        mock_chktex.return_value = mock_res
        yield mock_chktex


def test_watch_service_debounce(tmp_path, mock_simple_agent, mock_run_chktex):
    root = tmp_path / "test_project"
    root.mkdir()
    tex_file = root / "main.tex"
    tex_file.write_text("Hello world", encoding="utf-8")

    events = []

    def on_event(ev: WatchEvent):
        events.append(ev)

    service = WatchService(
        watch_id="test_1",
        root=str(root),
        main_tex="main.tex",
        idle_polish_sec=0.5,
        diagnose_debounce_ms=100,
        enable_latexmk=False,
        on_event=on_event,
    )

    service.start()
    time.sleep(0.2)
    assert mock_run_chktex.called

    service.on_file_changed(tex_file)
    time.sleep(0.3)
    assert mock_run_chktex.call_count >= 2

    time.sleep(0.7)

    service.stop()

    event_types = [e.event_type for e in events]
    assert "diagnostics_updated" in event_types
    assert "polish_suggestions_updated" in event_types
