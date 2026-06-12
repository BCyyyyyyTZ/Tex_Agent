from __future__ import annotations

from pathlib import Path

from latex.log_parser import parse_latex_log, tail_log_text


def test_tail_log_text__caps_lines() -> None:
    text = "\n".join(str(i) for i in range(100))
    out = tail_log_text(text, max_lines=5)
    assert out.splitlines() == ["95", "96", "97", "98", "99"]


def test_parse_latex_log__extracts_errors_and_warnings_from_fixture(repo_root: Path) -> None:
    p = repo_root / "tests" / "fixtures" / "latex" / "diagnose_demo" / "run_v0_result.txt"
    raw = p.read_text(encoding="utf-8", errors="replace")
    issues = parse_latex_log(raw, root=repo_root, default_file="main.tex")
    assert isinstance(issues, list)
    assert all(hasattr(i, "file") for i in issues)

