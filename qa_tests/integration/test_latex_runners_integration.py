from __future__ import annotations

from pathlib import Path

import pytest

from latex.chktex_runner import resolve_target_files, run_chktex
from latex.latexmk_runner import run_latexmk


@pytest.mark.latex_integration
def test_latexmk_runner__graceful_when_missing_tool(repo_root: Path) -> None:
    root = repo_root / "tests" / "fixtures" / "latex" / "multifile"
    r = run_latexmk(root, "main.tex", mode="fast", timeout_sec=30)
    assert r is not None
    if not r.env.paths.get("latexmk"):
        assert "latexmk_not_found" in r.warnings


@pytest.mark.latex_integration
def test_chktex_runner__graceful_when_missing_tool(repo_root: Path) -> None:
    root = repo_root / "tests" / "fixtures" / "latex" / "broken_braces.tex"
    rel_files = resolve_target_files(repo_root / "tests" / "fixtures" / "latex", files=["broken_braces.tex"])
    r = run_chktex(repo_root / "tests" / "fixtures" / "latex", rel_files)
    assert r is not None
    if not r.env.paths.get("chktex"):
        assert "chktex_not_found" in r.warnings

