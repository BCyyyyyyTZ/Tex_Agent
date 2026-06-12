from __future__ import annotations

from utils.web_artifact_registry import get_file_path, register_file


def test_register_and_get_file_path__round_trip() -> None:
    tok = register_file(r"C:\x\y.txt", ttl_sec=1.0)
    assert isinstance(tok, str) and len(tok) >= 8
    assert get_file_path(tok).endswith("y.txt")


def test_get_file_path__invalid_token_none() -> None:
    assert get_file_path("") is None
    assert get_file_path("short") is None

