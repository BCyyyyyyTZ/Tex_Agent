import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from latex.watch_service import WatchService
from latex.watch_events import WatchEvent
from latex.constants import IssueSource, Severity
from latex.models import DiagnosticIssue


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


def test_watch_service_resolve_chktex_files_includes_main_closure(tmp_path):
    root = tmp_path / "proj"
    chapters = root / "chapters"
    chapters.mkdir(parents=True)
    (root / "main.tex").write_text(
        "\\documentclass{article}\n\\begin{document}\n\\input{chapters/intro}\n\\end{document}\n",
        encoding="utf-8",
    )
    (chapters / "intro.tex").write_text("\\section{Intro}\n", encoding="utf-8")

    service = WatchService(
        watch_id="test_closure",
        root=str(root),
        main_tex="main.tex",
        enable_latexmk=False,
    )
    rel_files = service._resolve_chktex_files()
    assert "main.tex" in rel_files
    assert "chapters/intro.tex" in rel_files


def test_confirm_issue_positions_aligns_nearby_command_line(tmp_path):
    root = tmp_path / "proj"
    root.mkdir()
    tex = root / "main.tex"
    tex.write_text("line1\nline2\n\\notcommand\n", encoding="utf-8")
    service = WatchService(
        watch_id="test_align",
        root=str(root),
        main_tex="main.tex",
        enable_latexmk=False,
    )
    issue = DiagnosticIssue.build(
        file="main.tex",
        line=2,
        message="Undefined control sequence. (\\notcommand)",
        source=IssueSource.LATEXMK,
        severity=Severity.ERROR,
    )
    out = service._confirm_issue_positions([issue])
    assert out[0].line == 3


def test_confirm_issue_positions_aligns_within_plus_minus_five(tmp_path):
    root = tmp_path / "proj"
    root.mkdir()
    tex = root / "main.tex"
    tex.write_text(
        "a\nb\nc\nd\ne\nf\ng\n\\notcommand\n",
        encoding="utf-8",
    )
    service = WatchService(
        watch_id="test_align_5",
        root=str(root),
        main_tex="main.tex",
        enable_latexmk=False,
    )
    issue = DiagnosticIssue.build(
        file="main.tex",
        line=3,
        message="Undefined control sequence. (\\notcommand)",
        source=IssueSource.LATEXMK,
        severity=Severity.ERROR,
    )
    out = service._confirm_issue_positions([issue])
    assert out[0].line == 8
