from __future__ import annotations

from pathlib import Path

import pytest

from latex.paths import normalize_rel_path, resolve_tex_file


def test_normalize_rel_path__strips_drive_and_slashes() -> None:
    assert normalize_rel_path(r"C:\a\b\c.tex") == "a/b/c.tex"
    assert normalize_rel_path("/a/b/c.tex") == "a/b/c.tex"
    assert normalize_rel_path("./a/./b//c.tex") == "a/b/c.tex"


def test_resolve_tex_file__path_relative_to_base_dir(tmp_path: Path) -> None:
    base = tmp_path / "base"
    base.mkdir()
    (base / "main.tex").write_text("x", encoding="utf-8")
    abs_p, rel = resolve_tex_file(path="main.tex", base_dir=base)
    assert abs_p.name == "main.tex"
    assert rel is None


def test_resolve_tex_file__root_and_rel_path_appends_tex(tmp_path: Path) -> None:
    (tmp_path / "chap.tex").write_text("x", encoding="utf-8")
    abs_p, rel = resolve_tex_file(root=str(tmp_path), rel_path="chap")
    assert abs_p.name == "chap.tex"
    assert rel == "chap.tex"


def test_resolve_tex_file__requires_inputs() -> None:
    with pytest.raises(ValueError):
        resolve_tex_file()

