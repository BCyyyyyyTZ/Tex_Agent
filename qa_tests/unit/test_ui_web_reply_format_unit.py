from __future__ import annotations

import importlib

import pytest


def _import_server_module():
    try:
        return importlib.import_module("ui.web.server")
    except RuntimeError as e:
        if "python-multipart" in str(e):
            pytest.skip(str(e))
        raise


def test_collect_artifact_download_links__dedupe_by_token() -> None:
    m = _import_server_module()
    meta = {
        "n1": {
            "metadata": {
                "tool_metadata": {
                    "download_token": "t1",
                    "download_filename": "a.txt",
                    "relative_url": "/api/download/artifact?token=t1",
                }
            }
        },
        "n2": {
            "metadata": {
                "tool_metadata": {
                    "download_token": "t1",
                    "download_filename": "a.txt",
                    "relative_url": "/api/download/artifact?token=t1",
                }
            }
        },
    }
    links = m._collect_artifact_download_links(meta)
    assert links == [("a.txt", "/api/download/artifact?token=t1")]


def test_format_reply_from_result__error_and_links() -> None:
    m = _import_server_module()
    result = {
        "error": "boom",
        "metadata": {
            "node_x": {
                "metadata": {
                    "tool_metadata": {
                        "download_token": "t2",
                        "download_filename": "out.pdf",
                        "relative_url": "/api/download/artifact?token=t2",
                    }
                }
            }
        },
    }
    text = m._format_reply_from_result(result)
    assert "执行出错" in text
    assert "out.pdf" in text
    assert "token=t2" in text


def test_format_reply_from_result__uses_output_when_present() -> None:
    m = _import_server_module()
    result = {"output": "hello", "metadata": {}}
    text = m._format_reply_from_result(result)
    assert "hello" in text

