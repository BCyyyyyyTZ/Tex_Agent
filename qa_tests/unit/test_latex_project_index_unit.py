from __future__ import annotations

from pathlib import Path

import pytest

from latex.project_index import build_project_index, extract_inputs


def test_extract_inputs__finds_include_paths(tmp_path: Path) -> None:
    root = tmp_path
    main = root / "main.tex"
    chap = root / "chapters"
    chap.mkdir()
    (chap / "intro.tex").write_text("x", encoding="utf-8")
    main.write_text(r"\input{chapters/intro}", encoding="utf-8")
    out = extract_inputs(main.read_text(encoding="utf-8"), base_file=main, root=root)
    assert out == ["chapters/intro.tex"]


def test_build_project_index__multifile_fixture(repo_root: Path) -> None:
    root = repo_root / "tests" / "fixtures" / "latex" / "multifile"
    idx = build_project_index(root, enrich=False)
    assert idx.files
    assert any(p.endswith("main.tex") for p in idx.files.keys())


def test_build_project_index__explicit_main_must_exist(repo_root: Path) -> None:
    root = repo_root / "tests" / "fixtures" / "latex" / "multifile"
    with pytest.raises(FileNotFoundError):
        build_project_index(root, main_tex="missing.tex", enrich=False)

