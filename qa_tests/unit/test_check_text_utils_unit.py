from __future__ import annotations

from pathlib import Path

import pytest

from check_text import (
    allocate_output_pdf,
    collect_pdf_paths,
    is_connection_failure_text,
    resolve_path,
)


def test_is_connection_failure_text__known_substrings__true() -> None:
    assert is_connection_failure_text("Connection refused by host") is True
    assert is_connection_failure_text("api connection error") is True
    assert is_connection_failure_text("SSL handshake failed") is True


def test_is_connection_failure_text__empty__false() -> None:
    assert is_connection_failure_text("") is False
    assert is_connection_failure_text("  ") is False


def test_resolve_path__absolute_passthrough(tmp_path: Path) -> None:
    p = tmp_path / "a.txt"
    p.write_text("x", encoding="utf-8")
    assert resolve_path(str(p), base_dir=tmp_path) == p.resolve()


def test_resolve_path__relative_under_base(tmp_path: Path) -> None:
    base = tmp_path / "base"
    base.mkdir()
    assert resolve_path("x/y.txt", base_dir=base) == (base / "x" / "y.txt").resolve()


def test_collect_pdf_paths__dedupe_and_order() -> None:
    data = {
        "pdf_paths": ["a.pdf", "b.pdf", "a.pdf"],
        "pdfs": ["b.pdf", "c.pdf"],
        "pdf_path": "d.pdf",
    }
    assert collect_pdf_paths(data) == ["a.pdf", "b.pdf", "c.pdf", "d.pdf"]


def test_allocate_output_pdf__first_and_collision(tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    p1 = allocate_output_pdf(out_dir, "paper1.pdf")
    assert p1.name == "paper1-checked.pdf"
    p1.write_text("dummy", encoding="utf-8")
    p2 = allocate_output_pdf(out_dir, "paper1.pdf")
    assert p2.name == "paper1-checked_1.pdf"

