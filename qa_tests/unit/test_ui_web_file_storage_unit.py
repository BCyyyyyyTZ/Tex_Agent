from __future__ import annotations

from pathlib import Path

import pytest

from ui.web import file_storage


def test_sanitize_filename__removes_path_and_bad_chars() -> None:
    s = file_storage.sanitize_filename(r"..\..\evil?.pdf")
    assert s.endswith(".pdf")
    assert ".." not in s
    assert "?" not in s


def test_unique_stored_path__enforces_extension_allowlist(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(file_storage, "STORAGE_ROOT", tmp_path)
    with pytest.raises(ValueError):
        file_storage.unique_stored_path(file_storage.CATEGORY_PDFS, "a.exe")


def test_unique_stored_path__collision_adds_suffix(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(file_storage, "STORAGE_ROOT", tmp_path)
    p1 = file_storage.unique_stored_path(file_storage.CATEGORY_PDFS, "a.pdf")
    p1.parent.mkdir(parents=True, exist_ok=True)
    p1.write_bytes(b"x")
    p2 = file_storage.unique_stored_path(file_storage.CATEGORY_PDFS, "a.pdf")
    assert p2.name.startswith("a_")
    assert p2.name.endswith(".pdf")
    assert p2 != p1


def test_resolve_safe_path__prevents_traversal_and_requires_existing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(file_storage, "STORAGE_ROOT", tmp_path)
    d = file_storage.ensure_category_dir(file_storage.CATEGORY_PDFS)
    (d / "ok.pdf").write_bytes(b"x")

    assert file_storage.resolve_safe_path(file_storage.CATEGORY_PDFS, "ok.pdf") is not None
    p = file_storage.resolve_safe_path(file_storage.CATEGORY_PDFS, "../ok.pdf")
    assert p is not None
    assert p.resolve().parent == d.resolve()
    assert file_storage.resolve_safe_path(file_storage.CATEGORY_PDFS, "missing.pdf") is None
    assert file_storage.resolve_safe_path(file_storage.CATEGORY_PDFS, "..") is None
    assert file_storage.resolve_safe_path(file_storage.CATEGORY_PDFS, "../evil.exe") is None

