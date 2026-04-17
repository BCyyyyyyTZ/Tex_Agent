"""
使用 Docling 将本地文档解析为全文 Markdown + Docling JSON，并写入磁盘。

输出目录由环境变量 PARSED_DOC_DIR 或 Settings.parsed_doc_dir 决定；
每次解析在输出根下创建独立子目录，避免多次解析互相覆盖。
"""
from __future__ import annotations

import re
import time
import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Set

from config.settings import settings
from utils.logger import get_logger

logger = get_logger(__name__)

# 与当前产品需求一致的最小集合；其余 Docling 支持的格式也可尝试 convert
_DEFAULT_SUFFIXES: Set[str] = {
    ".pdf",
    ".docx",
    ".md",
    ".markdown",
    ".tex",
    ".html",
    ".htm",
    ".txt",
    ".csv",
    ".xlsx",
    ".pptx",
}


@dataclass
class DoclingParseResult:
    """单次解析结果（路径均为绝对路径）。"""

    success: bool
    source_path: str
    output_dir: str
    markdown_path: str
    json_path: str
    artifacts_dir: str
    error: Optional[str] = None
    # 观测：PDF 页数（非 PDF 或未统计则为 None）；路由标签见 _ROUTING_* 常量
    page_count: Optional[int] = None
    route: str = "default"
    bypass_stage: Optional[str] = None


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def resolve_source_path(source: str | Path) -> Path:
    """将用户给出的路径解析为绝对路径（相对路径相对于项目根）。"""
    p = Path(source)
    if not p.is_absolute():
        p = _project_root() / p
    return p.resolve()


def _sanitize_stem(stem: str) -> str:
    s = stem.strip() or "document"
    s = re.sub(r"[^\w\-]+", "_", s, flags=re.UNICODE)
    return (s[:120] if len(s) > 120 else s) or "document"


def _pick_output_dir(root: Path, stem: str) -> Path:
    """在 root 下生成不冲突的子目录：{stem}_{unix_ts}。"""
    safe = _sanitize_stem(stem)
    out = root / f"{safe}_{int(time.time())}"
    out.mkdir(parents=True, exist_ok=False)
    return out


_ROUTE_DEFAULT = "default"
_ROUTE_LARGE_2B = "large_2b"
_ROUTE_LARGE_2C = "large_2c"


def count_pdf_pages(path: Path) -> Optional[int]:
    """
    廉价预检：仅读取 PDF 总页数（不跑 Docling）。
    失败时返回 None，调用方应走默认解析路径以降低风险。
    """
    try:
        import fitz  # type: ignore[import-not-found]  # pymupdf
    except ImportError:
        logger.warning("未安装 pymupdf（import fitz），无法统计 PDF 页数，将使用默认解析路径")
        return None
    try:
        doc = fitz.open(path)
        try:
            n = doc.page_count
            return int(n)
        finally:
            doc.close()
    except Exception as e:
        logger.warning("统计 PDF 页数失败: %s，将使用默认解析路径", e)
        return None


def _torch_cuda_available() -> bool:
    try:
        import torch

        return bool(torch.cuda.is_available())
    except Exception:
        return False


def _effective_pdf_device() -> str:
    """
    归一化 PDF 设备意图：cuda | cpu。
    - auto：有 CUDA 则 cuda，否则 cpu。
    - cuda：强制尝试 CUDA，不可用时回退 cpu。
    - cpu：强制 CPU。
    """
    raw = (getattr(settings, "docling_pdf_device", "auto") or "auto").strip().lower()
    if raw not in ("auto", "cpu", "cuda"):
        raw = "auto"
    if raw == "cpu":
        return "cpu"
    if raw == "cuda":
        if not _torch_cuda_available():
            logger.warning("DOCLING_PDF_DEVICE=cuda 但 torch.cuda 不可用，使用 CPU")
            return "cpu"
        return "cuda"
    return "cuda" if _torch_cuda_available() else "cpu"


def _build_document_converter():
    """
    构建 DocumentConverter。
    - CPU：默认全功能管线（与历史行为一致）。
    - CUDA：PDF 使用 ThreadedStandardPdfPipeline + AcceleratorDevice.CUDA（非 PDF 仍走默认格式）。
    """
    from docling.document_converter import DocumentConverter

    dev = _effective_pdf_device()
    if dev == "cpu":
        logger.info("Docling：使用 CPU（默认 DocumentConverter）")
        return DocumentConverter()

    try:
        from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import ThreadedPdfPipelineOptions
        from docling.document_converter import PdfFormatOption
        from docling.pipeline.threaded_standard_pdf_pipeline import ThreadedStandardPdfPipeline

        accelerator_options = AcceleratorOptions(device=AcceleratorDevice.CUDA)
        pipeline_options = ThreadedPdfPipelineOptions(
            accelerator_options=accelerator_options,
            ocr_batch_size=4,
            layout_batch_size=16,
            table_batch_size=4,
        )
        logger.info("Docling：PDF 使用 CUDA（ThreadedStandardPdfPipeline）")
        return DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(
                    pipeline_cls=ThreadedStandardPdfPipeline,
                    pipeline_options=pipeline_options,
                )
            }
        )
    except Exception as e:
        logger.warning("Docling CUDA 管线构建失败，回退 CPU: %s", e)
        return DocumentConverter()


def _export_docling_document(
    doc,
    out_dir: Path,
    artifacts: Path,
    md_path: Path,
    json_path: Path,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    artifacts.mkdir(parents=True, exist_ok=True)
    doc.save_as_markdown(md_path, artifacts_dir=artifacts)
    doc.save_as_json(json_path, artifacts_dir=artifacts, indent=2)


def _try_large_pdf_bypass_2b(
    src: Path,
    out_dir: Path,
    artifacts: Path,
    md_path: Path,
    json_path: Path,
    page_count: int,
) -> DoclingParseResult:
    """预留：分块 PDF + 拼接 Markdown/JSON（未实现）。"""
    _ = (src, out_dir, artifacts, md_path, json_path)
    logger.info(
        "Docling 旁路 2b 未实现（CHUNK_PAGES=%s CHUNK_OVERLAP=%s）",
        settings.docling_chunk_pages,
        settings.docling_chunk_overlap,
    )
    return DoclingParseResult(
        success=False,
        source_path=str(src),
        output_dir=str(out_dir),
        markdown_path="",
        json_path="",
        artifacts_dir=str(artifacts.resolve()) if artifacts.exists() else "",
        error="旁路 2b（分块拼接）尚未实现",
        page_count=page_count,
        route=_ROUTE_LARGE_2B,
        bypass_stage="2b",
    )


def _try_large_pdf_bypass_2c(
    src: Path,
    out_dir: Path,
    artifacts: Path,
    md_path: Path,
    json_path: Path,
    page_count: int,
) -> DoclingParseResult:
    """预留：更小窗口 / 单页串行等兜底（未实现）。"""
    _ = (src, out_dir, artifacts, md_path, json_path)
    return DoclingParseResult(
        success=False,
        source_path=str(src),
        output_dir=str(out_dir),
        markdown_path="",
        json_path="",
        artifacts_dir=str(artifacts.resolve()) if artifacts.exists() else "",
        error="旁路 2c 尚未实现",
        page_count=page_count,
        route=_ROUTE_LARGE_2C,
        bypass_stage="2c",
    )


def _run_large_pdf_bypass_chain(
    src: Path,
    out_dir: Path,
    artifacts: Path,
    md_path: Path,
    json_path: Path,
    page_count: int,
) -> DoclingParseResult:
    """页数 >= 阈值：成功即停。"""
    attempts = (
        _try_large_pdf_bypass_2b,
        _try_large_pdf_bypass_2c,
    )
    last: Optional[DoclingParseResult] = None
    errors: list[str] = []
    for fn in attempts:
        last = fn(src, out_dir, artifacts, md_path, json_path, page_count)
        if last.success:
            return last
        if last.error:
            errors.append(f"{last.bypass_stage}: {last.error}")
    assert last is not None
    joined = " | ".join(errors) if errors else "unknown"
    return DoclingParseResult(
        success=False,
        source_path=str(src),
        output_dir=str(out_dir),
        markdown_path="",
        json_path="",
        artifacts_dir=str(artifacts.resolve()) if artifacts.exists() else "",
        error=f"大文档旁路均失败: {joined}",
        page_count=page_count,
        route=last.route,
        bypass_stage=last.bypass_stage,
    )


def parse_document_to_dir(
    source: str | Path,
    output_root: Optional[str | Path] = None,
    *,
    allowed_suffixes: Optional[Iterable[str]] = None,
) -> DoclingParseResult:
    """
    解析单个文件，写出 document.md、document.json，资源写入 artifacts/。

    Args:
        source: 源文件路径（绝对或相对项目根）。
        output_root: 输出根目录；默认使用 settings.parsed_doc_dir。
        allowed_suffixes: 允许的后缀集合（含点、小写），None 使用内置默认列表。

    Returns:
        DoclingParseResult；失败时 success=False，error 为说明字符串。
    """
    try:
        from docling.document_converter import DocumentConverter
    except ImportError as e:
        msg = (
            "未安装 docling。请在项目根目录执行：pip install \"docling>=2.0\""
        )
        logger.error(msg)
        sp = str(resolve_source_path(source))
        root = str(Path(output_root).resolve()) if output_root else settings.parsed_doc_dir
        return DoclingParseResult(
            success=False,
            source_path=sp,
            output_dir=root,
            markdown_path="",
            json_path="",
            artifacts_dir="",
            error=f"{msg} ({e})",
        )

    src = resolve_source_path(source)
    if not src.is_file():
        msg = f"源文件不存在或不是文件: {src}"
        logger.error(msg)
        root = str(Path(output_root).resolve()) if output_root else settings.parsed_doc_dir
        return DoclingParseResult(
            success=False,
            source_path=str(src),
            output_dir=root,
            markdown_path="",
            json_path="",
            artifacts_dir="",
            error=msg,
        )

    suffixes = {s.lower() for s in (allowed_suffixes or _DEFAULT_SUFFIXES)}
    if src.suffix.lower() not in suffixes:
        msg = f"不支持的文件扩展名: {src.suffix!r}，允许: {sorted(suffixes)}"
        logger.error(msg)
        root = str(Path(output_root).resolve()) if output_root else settings.parsed_doc_dir
        return DoclingParseResult(
            success=False,
            source_path=str(src),
            output_dir=root,
            markdown_path="",
            json_path="",
            artifacts_dir="",
            error=msg,
        )

    root = Path(output_root).resolve() if output_root else Path(settings.parsed_doc_dir)
    root.mkdir(parents=True, exist_ok=True)

    out_dir = _pick_output_dir(root, src.stem)
    artifacts = out_dir / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)

    md_path = out_dir / "document.md"
    json_path = out_dir / "document.json"

    page_count: Optional[int] = None
    use_large_pdf_bypass = False
    if src.suffix.lower() == ".pdf":
        page_count = count_pdf_pages(src)
        if page_count is None:
            use_large_pdf_bypass = False
            logger.info("PDF 页数未知，使用默认 Docling 管线")
        else:
            use_large_pdf_bypass = page_count >= settings.docling_page_threshold
            logger.info(
                "PDF 页数=%s 阈值=%s -> %s",
                page_count,
                settings.docling_page_threshold,
                "旁路" if use_large_pdf_bypass else "默认管线",
            )

    try:
        if use_large_pdf_bypass and page_count is not None:
            return _run_large_pdf_bypass_chain(
                src, out_dir, artifacts, md_path, json_path, page_count
            )

        converter = _build_document_converter()
        conv_res = converter.convert(source=str(src))
        doc = conv_res.document
        _export_docling_document(doc, out_dir, artifacts, md_path, json_path)

        logger.info(
            "Docling 解析完成: src=%s -> out_dir=%s route=%s",
            src,
            out_dir,
            _ROUTE_DEFAULT,
        )
        return DoclingParseResult(
            success=True,
            source_path=str(src),
            output_dir=str(out_dir),
            markdown_path=str(md_path.resolve()),
            json_path=str(json_path.resolve()),
            artifacts_dir=str(artifacts.resolve()),
            error=None,
            page_count=page_count,
            route=_ROUTE_DEFAULT,
            bypass_stage=None,
        )
    except Exception as e:
        msg = f"Docling 解析失败: {e}"
        logger.exception(msg)
        return DoclingParseResult(
            success=False,
            source_path=str(src),
            output_dir=str(out_dir),
            markdown_path="",
            json_path="",
            artifacts_dir=str(artifacts.resolve()) if artifacts.exists() else "",
            error=msg,
            page_count=page_count,
            route=_ROUTE_DEFAULT,
            bypass_stage=None,
        )

def _ensure_project_root_on_path() -> None:
    """支持 `python rag\\docling_parse.py` 时也能 import config / utils。"""
    root = str(Path(__file__).resolve().parent.parent)
    if root not in sys.path:
        sys.path.insert(0, root)


def main(argv: Optional[list[str]] = None) -> int:
    _ensure_project_root_on_path()

    parser = argparse.ArgumentParser(
        description="使用 Docling 将文档解析为 Markdown + JSON，并写入磁盘（默认见 settings.parsed_doc_dir / PARSED_DOC_DIR）。",
    )
    parser.add_argument(
        "source",
        help="源文件路径：绝对路径，或相对「项目根 Tex_Agent」的相对路径",
    )
    parser.add_argument(
        "-o",
        "--output-root",
        default=None,
        help="输出根目录（可选）；默认使用环境变量 PARSED_DOC_DIR / settings.parsed_doc_dir",
    )
    args = parser.parse_args(argv)

    r = parse_document_to_dir(args.source, output_root=args.output_root)
    if r.success:
        print("解析成功")
        print("路由:", r.route, "| 页数:", r.page_count, "| 旁路阶段:", r.bypass_stage)
        print("输出目录:", r.output_dir)
        print("Markdown:", r.markdown_path)
        print("JSON:", r.json_path)
        print("资源目录:", r.artifacts_dir)
        return 0

    print("解析失败:", r.error, file=sys.stderr)
    print(
        "路由:", r.route, "| 页数:", r.page_count, "| 旁路阶段:", r.bypass_stage,
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())