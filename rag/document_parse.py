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
from typing import Iterable, Optional, Set, List, Dict, Any, Tuple
from collections import Counter

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_pr = str(_PROJECT_ROOT)
if _pr not in sys.path:
    sys.path.insert(0, _pr)

from config.settings import settings
from utils.logger import get_logger

import hashlib
from typing import List, Dict, Any
import json
try:
    import fitz  # pymupdf
except ImportError:
    fitz = None

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


def _ensure_chunk_dir() -> Path:
    """确保 chunk 解析结果目录存在"""
    chunk_root = Path(getattr(settings, "chunk_parsed_doc_dir", "doc/chunk_parsed_doc"))
    chunk_root.mkdir(parents=True, exist_ok=True)
    return chunk_root

def _split_pdf_into_chunks(
    src: Path, chunk_pages: int = 25, overlap: int = 1
) -> List[Tuple[Path, int]]:
    """
    将PDF切分成多个临时小PDF，返回 [(temp_pdf_path, start_page_in_original)]。
    start_page_in_original 用于后续全局页号偏移。
    """
    if fitz is None:
        raise ImportError("大PDF旁路需要 pymupdf: pip install pymupdf")
        
    doc = fitz.open(src)
    total_pages = doc.page_count
    chunks: List[Tuple[Path, int]] = []
    step = max(1, chunk_pages - overlap)
    try:
        for start in range(0, total_pages, step):
            end = min(start + chunk_pages, total_pages)
            if end - start < 1:
                continue
            temp_pdf = src.parent / f"temp_chunk_{start+1}_{end}_{int(time.time())}.pdf"
            chunk_doc = fitz.open()
            for p in range(start, end):
                chunk_doc.insert_pdf(doc, from_page=p, to_page=p)
            chunk_doc.save(temp_pdf)
            chunk_doc.close()
            chunks.append((temp_pdf, start))  # start 是 0-based 原页索引
    finally:
        doc.close()
    return chunks

def _normalize_text_for_dedup(text: str) -> str:
    text = (text or "").strip().lower()
    # 归一化空白与常见分隔符，降低 chunk 边界重复差异
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[|·•]+", " ", text)
    return text


def _compute_element_key(elem: Dict) -> str:
    """用于去重的 key：page + label + normalized_text_hash"""
    page = int(elem.get("global_page_no", 0) or 0)
    label = str(elem.get("label", "") or "").lower()
    text = _normalize_text_for_dedup(elem.get("text", ""))
    text_hash = hashlib.md5(text.encode("utf-8")).hexdigest()[:12]
    return f"{page}_{label}_{text_hash}"


def _is_meaningful_text(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    # 纯页码、非常短噪声可按需过滤（此处保守）
    return True


def _heading_level_from_text(text: str, elem: Dict[str, Any]) -> int:
    """
    推断标题层级：
    1) 先用 Docling level
    2) 再识别“第X章”
    3) 再识别数字标题如 6.3 / 6.3.1
    """
    lvl = elem.get("level", None)
    if isinstance(lvl, int) and 1 <= lvl <= 6:
        return lvl

    t = (text or "").strip()

    # 第X章
    if re.match(r"^第[一二三四五六七八九十百零〇\d]+章\b", t):
        return 1

    # 6 / 6.3 / 6.3.1 / 6.3.1.2
    m = re.match(r"^(\d+(?:\.\d+){0,5})\b", t)
    if m:
        parts = m.group(1).split(".")
        return max(1, min(6, len(parts)))

    return 2


def _extract_elements_from_docling_json(
    json_path: Path,
    page_offset: int = 0,
    *,
    chunk_idx: int = 0,
) -> List[Dict]:
    """
    从单个 chunk 的 document.json 提取元素，保留结构顺序：
    - 先按 body.children 顺序
    - group 递归展开，保留顺序路径 _order_path
    """
    if not json_path.exists():
        return []

    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    texts = {item["self_ref"]: item for item in data.get("texts", [])}
    groups = {item["self_ref"]: item for item in data.get("groups", [])}
    pictures = {item["self_ref"]: item for item in data.get("pictures", [])}
    tables = {item["self_ref"]: item for item in data.get("tables", [])}

    def resolve_ref(ref: str) -> Optional[Dict]:
        if ref in texts:
            return texts[ref]
        if ref in groups:
            return groups[ref]
        if ref in pictures:
            return pictures[ref]
        if ref in tables:
            return tables[ref]
        return None

    elements: List[Dict] = []
    emitted_leaf_refs: set[str] = set()

    def walk_ref(
        ref: str,
        order_path: tuple[int, ...],
        parent_page_no: Optional[int] = None,
        parent_global_page: Optional[int] = None,
    ) -> None:
        elem = resolve_ref(ref)
        if not elem or not isinstance(elem, dict):
            return

        label = str(elem.get("label", "") or "")
        provs = elem.get("prov", [])
        prov = provs[0] if (isinstance(provs, list) and provs and isinstance(provs[0], dict)) else {}

        # 页号优先用自身 prov，其次继承父节点
        page_no = prov.get("page_no", parent_page_no if parent_page_no is not None else 1)
        global_page_no = int(page_no) + page_offset if page_no is not None else (
            parent_global_page if parent_global_page is not None else 1 + page_offset
        )

        # group 仅作为容器，递归展开其 children（不直接落地）
        if label == "group":
            for child_idx, child in enumerate(elem.get("children", [])):
                if isinstance(child, dict) and "$ref" in child:
                    walk_ref(
                        child["$ref"],
                        order_path + (child_idx,),
                        parent_page_no=page_no,
                        parent_global_page=global_page_no,
                    )
            return

        text = (elem.get("text", "") or "").strip()
        if not text and label not in ("picture", "table"):
            return

        # 同一 chunk 内避免同一叶子 ref 重复发射
        if ref in emitted_leaf_refs:
            return
        emitted_leaf_refs.add(ref)

        item = elem.copy()
        item["self_ref"] = ref
        item["page_no"] = page_no
        item["global_page_no"] = global_page_no
        item["_chunk_idx"] = chunk_idx
        item["_order_path"] = order_path

        if "bbox" in prov:
            item["bbox"] = prov["bbox"]

        item["text"] = text
        elements.append(item)

    for body_idx, child in enumerate(data.get("body", {}).get("children", [])):
        if not isinstance(child, dict) or "$ref" not in child:
            continue
        walk_ref(child["$ref"], (body_idx,))

    return elements


def _pick_best_chunk_for_page(page_items: Dict[int, List[Dict]]) -> int:
    """
    对同一 global_page_no 在多个 chunk 中的候选，选择一个最佳 chunk：
    - 文本有效元素更多优先
    - 标题元素更多优先
    - chunk_idx 更小优先（稳定）
    """
    best_chunk = -1
    best_score = None

    for cidx, items in page_items.items():
        text_cnt = 0
        heading_cnt = 0
        for it in items:
            text = (it.get("text", "") or "").strip()
            label = str(it.get("label", "") or "").lower()
            if _is_meaningful_text(text) or label in ("picture", "table"):
                text_cnt += 1
            if label in ("section_header", "title"):
                heading_cnt += 1
        score = (text_cnt, heading_cnt, -cidx)
        if best_score is None or score > best_score:
            best_score = score
            best_chunk = cidx

    return best_chunk


def _merge_docling_jsons(
    chunk_infos: List[Tuple[Path, int]],
    original_page_count: int
) -> tuple[str, Dict[str, Any]]:
    """
    合并多个 chunk 的 JSON。
    策略：
    1) 保留 Docling 结构顺序（order_path）；
    2) 重叠页按页选优 chunk，避免跨 chunk 互相打乱；
    3) 最后按 (global_page_no, order_path) 输出；
    """
    all_elements: List[Dict] = []

    # 先提取（保留 chunk_idx）
    for chunk_idx, (json_path, page_offset) in enumerate(chunk_infos):
        elems = _extract_elements_from_docling_json(
            json_path,
            page_offset,
            chunk_idx=chunk_idx,
        )
        all_elements.extend(elems)

    # page -> chunk -> items
    page_chunk_map: Dict[int, Dict[int, List[Dict]]] = {}
    for it in all_elements:
        page = int(it.get("global_page_no", 0) or 0)
        cidx = int(it.get("_chunk_idx", 0) or 0)
        page_chunk_map.setdefault(page, {}).setdefault(cidx, []).append(it)

    # 每页只保留一个最优 chunk，避免 overlap 页混拼
    selected: List[Dict] = []
    for page in sorted(page_chunk_map.keys()):
        chunk_items = page_chunk_map[page]
        chosen_chunk = _pick_best_chunk_for_page(chunk_items)
        selected.extend(chunk_items.get(chosen_chunk, []))

    # 按全局页 + 结构顺序排序（不再依赖 bbox.t）
    selected.sort(
        key=lambda x: (
            int(x.get("global_page_no", 0) or 0),
            tuple(x.get("_order_path", (10**9,))),
        )
    )

    # 跨页最终去重（常见于 overlap）
    seen = set()
    deduped: List[Dict] = []
    for it in selected:
        k = _compute_element_key(it)
        if k in seen:
            continue
        seen.add(k)
        deduped.append(it)

    # 输出 Markdown
    md_lines: List[str] = []
    for elem in deduped:
        label = str(elem.get("label", "") or "").lower()
        text = (elem.get("text", "") or "").strip()

        if not text and label not in ("picture", "table"):
            continue

        if label in ("section_header", "title"):
            level = _heading_level_from_text(text, elem)
            md_lines.append("#" * level + " " + text)
            md_lines.append("")
        elif label == "list_item" or "list" in label:
            md_lines.append("- " + text)
        elif label == "picture":
            md_lines.append("<!-- image -->")
            if text:
                md_lines.append(text)
            md_lines.append("")
        elif label == "table":
            md_lines.append("**[Table]**")
            if text:
                md_lines.append(text)
            md_lines.append("")
        else:
            md_lines.append(text)
            md_lines.append("")

    final_md = "\n".join(md_lines).strip()

    merged_json = {
        "schema_name": "MergedDoclingDocument",
        "version": "1.1.0",
        "name": "merged_large_pdf",
        "page_count": original_page_count,
        "markdown": final_md,
        "chunk_count": len(chunk_infos),
        "sources": [str(p) for p, _ in chunk_infos],
    }
    return final_md, merged_json

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
    """大PDF旁路2b：分块解析 + JSON结构化合并（已完善）。"""
    logger.info(
        "启动大PDF旁路2b：分块解析 + JSON拼接 (总页数=%s, chunk_size=%s, overlap=%s)",
        page_count,
        settings.docling_chunk_pages,
        settings.docling_chunk_overlap,
    )

    chunk_root = _ensure_chunk_dir()
    chunk_base_name = f"{_sanitize_stem(src.stem)}_chunks_{int(time.time())}"
    chunk_base = chunk_root / chunk_base_name
    chunk_base.mkdir(parents=True, exist_ok=True)

    chunk_infos: List[Tuple[Path, int]] = []  # (json_path, page_offset)
    temp_pdfs: List[Path] = []

    try:
        # 1. 切分PDF并记录原始页偏移
        chunks = _split_pdf_into_chunks(
            src,
            chunk_pages=settings.docling_chunk_pages,
            overlap=settings.docling_chunk_overlap,
        )

        # 2. 逐块解析（输出到 chunk_parsed_doc）
        for i, (temp_pdf, page_offset) in enumerate(chunks):
            temp_pdfs.append(temp_pdf)
            chunk_dir = chunk_base / f"chunk_{i:02d}"
            chunk_dir.mkdir(exist_ok=True)

            chunk_result = parse_document_to_dir(
                source=str(temp_pdf),
                output_root=str(chunk_dir),
            )

            if chunk_result.success and chunk_result.json_path:
                json_p = Path(chunk_result.json_path)
                chunk_infos.append((json_p, page_offset))
                logger.info("Chunk %d (原页偏移 %d) 解析成功", i, page_offset)
            else:
                logger.warning("Chunk %d 解析失败: %s", i, chunk_result.error or "unknown")

        if not chunk_infos:
            return DoclingParseResult(
                success=False,
                source_path=str(src),
                output_dir=str(out_dir),
                markdown_path="",
                json_path="",
                artifacts_dir=str(artifacts),
                error="所有分块均解析失败",
                page_count=page_count,
                route=_ROUTE_LARGE_2B,
                bypass_stage="2b",
            )

        # 3. 合并
        final_md, merged_json = _merge_docling_jsons(chunk_infos, page_count)

        # 4. 写入最终结果（保持与默认路径一致）
        out_dir.mkdir(parents=True, exist_ok=True)
        artifacts.mkdir(parents=True, exist_ok=True)
        md_path.write_text(final_md, encoding="utf-8")
        json_path.write_text(
            json.dumps(merged_json, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        logger.info(
            "大PDF旁路2b完成！总页数=%s，处理chunk=%s，最终MD长度=%s",
            page_count,
            len(chunk_infos),
            len(final_md),
        )

        return DoclingParseResult(
            success=True,
            source_path=str(src),
            output_dir=str(out_dir),
            markdown_path=str(md_path.resolve()),
            json_path=str(json_path.resolve()),
            artifacts_dir=str(artifacts.resolve()),
            page_count=page_count,
            route=_ROUTE_LARGE_2B,
            bypass_stage="2b",
        )

    except Exception as e:
        logger.exception("大PDF旁路2b执行异常")
        return DoclingParseResult(
            success=False,
            source_path=str(src),
            output_dir=str(out_dir),
            markdown_path="",
            json_path="",
            artifacts_dir=str(artifacts),
            error=f"2b旁路失败: {str(e)}",
            page_count=page_count,
            route=_ROUTE_LARGE_2B,
            bypass_stage="2b",
        )
    finally:
        # 清理临时PDF文件
        for p in temp_pdfs:
            try:
                if p.exists():
                    p.unlink()
            except Exception as e:
                logger.warning("清理临时文件 %s 失败: %s", p, e)


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
    """支持 `python rag\\document_parse.py` 时也能 import config / utils。"""
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