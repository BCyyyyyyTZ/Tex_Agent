from __future__ import annotations

import pytest

from latex import ghost_cli


def test_ghost_cli_calls_runner(monkeypatch: pytest.MonkeyPatch) -> None:
    called = {}

    def _fake_run(**kwargs):
        called.update(kwargs)

    monkeypatch.setattr("latex.ghost_cli.run_ghost_server", _fake_run)
    monkeypatch.setattr(
        "sys.argv",
        [
            "ghost_cli",
            "--root",
            "tests/fixtures/latex/multifile",
            "--main-tex",
            "main.tex",
            "--quiet-sec",
            "1.2",
            "--idle-polish-sec",
            "3",
            "--enable-auto-polish",
            "--host",
            "127.0.0.1",
            "--port",
            "8772",
            "--no-browser",
        ],
    )

    ghost_cli.main()

    assert called["root"] == "tests/fixtures/latex/multifile"
    assert called["main_tex"] == "main.tex"
    assert called["quiet_sec"] == 1.2
    assert called["idle_polish_sec"] == 3.0
    assert called["auto_polish"] is True
    assert called["port"] == 8772
    assert called["open_browser"] is False

