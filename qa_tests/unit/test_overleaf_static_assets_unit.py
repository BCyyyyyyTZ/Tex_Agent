from __future__ import annotations

from pathlib import Path


def test_overleaf_static_assets__index_exists(repo_root: Path) -> None:
    p = repo_root / "ui" / "overleaf" / "static" / "index.html"
    assert p.is_file()

