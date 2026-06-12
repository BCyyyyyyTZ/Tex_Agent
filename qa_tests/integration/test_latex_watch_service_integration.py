from __future__ import annotations

import time
from pathlib import Path

import pytest

from latex.watch_service import WatchService


@pytest.mark.integration
@pytest.mark.slow
def test_watch_service__diagnostics_cycle_without_latexmk(tmp_path: Path) -> None:
    (tmp_path / "main.tex").write_text(r"\documentclass{article}\begin{document}x\end{document}", encoding="utf-8")
    svc = WatchService(
        watch_id="t1",
        root=str(tmp_path),
        main_tex=None,
        idle_polish_sec=9999.0,
        diagnose_debounce_ms=10,
        enable_latexmk=False,
    )
    svc.start()
    try:
        svc.on_file_changed(tmp_path / "main.tex")
        deadline = time.time() + 5.0
        while time.time() < deadline:
            snap = svc.get_snapshot()
            if snap.project_version > 0:
                assert snap.status == "running"
                return
            time.sleep(0.1)
        pytest.fail("watch diagnostics did not update project_version in time")
    finally:
        svc.stop()

