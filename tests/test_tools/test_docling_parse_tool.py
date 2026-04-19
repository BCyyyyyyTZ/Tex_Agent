"""
DoclingParseTool 单元 / 集成测试。

- HMVLM.pdf、Efficient Video Analytics.pdf：依赖本机已在 settings.parsed_doc_dir
  下的预解析目录（只读，不向 doc/ 写入）。
- LoRAuter.pdf：真实解析，输出目录 monkeypatch 到 tmp_path，避免污染 doc/parsed_doc。

运行示例（在内层 Tex_Agent 包根目录）：
  pytest tests/test_tools/test_docling_parse_tool.py -v
  pytest tests/test_tools/test_docling_parse_tool.py -v -m "not integration"   # 跳过慢测试
  pytest tests/test_tools/test_docling_parse_tool.py -v -m integration        # 仅慢测试
"""
from __future__ import annotations

from pathlib import Path

import pytest

from config.settings import settings
from tools.docling_tool import DoclingParseTool, _find_existing_parse


# tests/test_tools -> tests -> test_rag/test_document
FIXTURE_PDF_DIR = Path(__file__).resolve().parent.parent / "test_rag" / "test_document"

HMVLM_PDF = FIXTURE_PDF_DIR / "HMVLM.pdf"
EVA_PDF = FIXTURE_PDF_DIR / "Efficient Video Analytics.pdf"
LORAUTER_PDF = FIXTURE_PDF_DIR / "LoRAuter.pdf"


def _require_pdf(path: Path) -> None:
    if not path.is_file():
        pytest.skip(f"缺少测试用 PDF: {path}")


@pytest.fixture
def tool() -> DoclingParseTool:
    return DoclingParseTool()


# --------------------------------------------------------------------------- #
# 缓存命中（只读 doc/parsed_doc，不写）
# --------------------------------------------------------------------------- #


def test_cache_hit_hmvlm(tool: DoclingParseTool) -> None:
    _require_pdf(HMVLM_PDF)
    parsed_root = Path(settings.parsed_doc_dir)
    if _find_existing_parse(parsed_root, HMVLM_PDF.stem) is None:
        pytest.skip(f"未在 {parsed_root} 找到 HMVLM 的预解析缓存，跳过只读缓存测试")

    r = tool.run(str(HMVLM_PDF), redo=False)
    assert r.success is True
    assert r.metadata.get("from_cache") is True
    assert Path(r.metadata["markdown_path"]).is_file()
    assert Path(r.metadata["json_path"]).is_file()


def test_cache_hit_efficient_video_analytics(tool: DoclingParseTool) -> None:
    _require_pdf(EVA_PDF)
    parsed_root = Path(settings.parsed_doc_dir)
    if _find_existing_parse(parsed_root, EVA_PDF.stem) is None:
        pytest.skip(f"未在 {parsed_root} 找到该文档的预解析缓存，跳过只读缓存测试")

    r = tool.run(str(EVA_PDF), redo=False)
    assert r.success is True
    assert r.metadata.get("from_cache") is True
    assert Path(r.metadata["markdown_path"]).is_file()
    assert Path(r.metadata["json_path"]).is_file()


def test_redo_true_bypasses_cache_even_if_present(tool: DoclingParseTool, monkeypatch: pytest.MonkeyPatch) -> None:
    """有缓存时 redo=True 仍应调用解析（此处 mock，避免真跑 Docling）。"""
    _require_pdf(HMVLM_PDF)
    parsed_root = Path(settings.parsed_doc_dir)
    if _find_existing_parse(parsed_root, HMVLM_PDF.stem) is None:
        pytest.skip("无预解析缓存则无法验证 bypass")

    calls: list[tuple[str, str]] = []

    def fake_parse(source: str, output_root=None, **kwargs):  # type: ignore[no-untyped-def]
        calls.append((str(source), str(output_root) if output_root else ""))
        from rag.docling_parse import DoclingParseResult

        out_dir = Path(parsed_root) / "fake_hmvlm_9999999999"
        out_dir.mkdir(parents=True, exist_ok=True)
        md = out_dir / "document.md"
        js = out_dir / "document.json"
        md.write_text("x" * 120, encoding="utf-8")
        js.write_text('{"ok": true}', encoding="utf-8")
        return DoclingParseResult(
            success=True,
            source_path=str(HMVLM_PDF.resolve()),
            output_dir=str(out_dir),
            markdown_path=str(md.resolve()),
            json_path=str(js.resolve()),
            artifacts_dir=str((out_dir / "artifacts").resolve()),
        )

    monkeypatch.setattr("tools.docling_tool.parse_document_to_dir", fake_parse)
    r = tool.run(str(HMVLM_PDF), redo=True)
    assert r.success is True
    assert r.metadata.get("from_cache") is False
    assert len(calls) == 1
    # 清理测试写入的假目录（仍在 parsed_root 下，若你希望完全不碰 doc，可把 fake 输出也改到 tmp_path）
    fake_dir = Path(parsed_root) / "fake_hmvlm_9999999999"
    if fake_dir.exists():
        import shutil
        shutil.rmtree(fake_dir, ignore_errors=True)


# --------------------------------------------------------------------------- #
# 真实解析 LoRAuter（输出仅 tmp_path，不写 doc/parsed_doc）
# --------------------------------------------------------------------------- #


@pytest.mark.integration
def test_lorauter_parse_writes_under_tmp_only(tool: DoclingParseTool, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    pytest.importorskip("docling")
    _require_pdf(LORAUTER_PDF)

    class _FakeSettings:
        parsed_doc_dir = str(tmp_path)

    monkeypatch.setattr("tools.docling_tool.settings", _FakeSettings())

    r = tool.run(str(LORAUTER_PDF), redo=True)
    assert r.success is True, r.error
    assert r.metadata.get("from_cache") is False
    md = Path(r.metadata["markdown_path"])
    js = Path(r.metadata["json_path"])
    assert md.is_file() and js.is_file()
    assert tmp_path in md.parents or md.parent == tmp_path
    assert tmp_path in js.parents or js.parent == tmp_path