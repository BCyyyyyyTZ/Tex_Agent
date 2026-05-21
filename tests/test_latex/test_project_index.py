from __future__ import annotations

from pathlib import Path

import pytest

from latex.project_index import build_project_index, extract_inputs, file_checksum
from latex.serialize import from_json


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "latex"
MULTIFILE = FIXTURES / "multifile"


def test_file_checksum_changes_with_content() -> None:
    a = file_checksum("hello")
    b = file_checksum("hello!")
    assert a.startswith("sha256:")
    assert a != b


def test_build_multifile_project() -> None:
    index = build_project_index(MULTIFILE)
    assert index.root == str(MULTIFILE.resolve())
    assert set(index.files.keys()) == {"main.tex", "chapters/intro.tex"}
    assert index.main_tex == "main.tex"
    assert index.main_tex_candidates == ["main.tex"]

    main = index.files["main.tex"]
    assert main.inputs == ["chapters/intro.tex"]
    assert main.checksum.startswith("sha256:")

    intro = index.files["chapters/intro.tex"]
    assert intro.inputs == []


def test_build_without_enrich_skips_refs() -> None:
    index = build_project_index(MULTIFILE, enrich=False)
    assert index.labels == {}
    assert index.refs == []
    assert index.bib_entries == {}


def test_explicit_main_tex() -> None:
    index = build_project_index(MULTIFILE, main_tex="main.tex")
    assert index.main_tex == "main.tex"


def test_unknown_main_tex_raises() -> None:
    with pytest.raises(FileNotFoundError):
        build_project_index(MULTIFILE, main_tex="missing.tex")


def test_extract_inputs_resolves_relative_path(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    sub = root / "chapters"
    sub.mkdir(parents=True)
    main = root / "main.tex"
    child = sub / "part.tex"
    main.write_text(r"\input{chapters/part}", encoding="utf-8")
    child.write_text("x", encoding="utf-8")

    text = main.read_text(encoding="utf-8")
    inputs = extract_inputs(text, base_file=main, root=root)
    assert inputs == ["chapters/part.tex"]


def test_checksum_changes_when_file_mutated(tmp_path: Path) -> None:
    root = tmp_path / "p"
    root.mkdir()
    tex = root / "only.tex"
    tex.write_text("\\documentclass{article}", encoding="utf-8")
    first = build_project_index(root)
    c1 = first.files["only.tex"].checksum

    tex.write_text("\\documentclass{article}\n% edit", encoding="utf-8")
    second = build_project_index(root)
    c2 = second.files["only.tex"].checksum
    assert c1 != c2


def test_multiple_documentclass_candidates(tmp_path: Path) -> None:
    root = tmp_path / "multi"
    root.mkdir()
    (root / "a.tex").write_text("\\documentclass{article}", encoding="utf-8")
    (root / "b.tex").write_text("\\documentclass{report}", encoding="utf-8")

    index = build_project_index(root)
    assert index.main_tex is None
    assert index.main_tex_candidates == ["a.tex", "b.tex"]


def test_not_a_directory_raises(tmp_path: Path) -> None:
    f = tmp_path / "file.txt"
    f.write_text("x", encoding="utf-8")
    with pytest.raises(NotADirectoryError):
        build_project_index(f)
