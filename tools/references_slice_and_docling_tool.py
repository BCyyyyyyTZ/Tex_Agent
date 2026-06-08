"""
ReferencesSliceAndDoclingTool：
1) 基于 chapter_routing 的 references 路由信息确定原 PDF 参考文献页范围（1-based）
2) 将该范围切成子 PDF
3) 对子 PDF 执行 docling 解析
4) 从 docling 产出的 Markdown 中提取“参考文献”章节文本

注意：输出 metadata 中的页码始终是“原 PDF 页码”，供下游批注节点使用。
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import fitz

from config.settings import settings
from core.message import ToolResult
from rag.document_parse import parse_document_to_dir
from tools.base_tool import BaseTool
from utils.logger import get_logger

logger = get_logger(__name__)


def _normalize_title(text: str) -> str:
    return re.sub(r"\s+", "", str(text or "").strip().lower())


def _is_ref_title(title: str) -> bool:
    t = _normalize_title(title)
    return any(k in t for k in ("参考文献", "references", "bibliography"))


def _extract_ref_nodes(chapter_routing: Dict[str, Any]) -> List[Dict[str, Any]]:
    matched = chapter_routing.get("matched_nodes", {}) if isinstance(chapter_routing, dict) else {}
    refs = matched.get("references", []) if isinstance(matched, dict) else []
    return [x for x in refs if isinstance(x, dict)]


def _iter_all_matched_nodes(chapter_routing: Dict[str, Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    matched = chapter_routing.get("matched_nodes", {}) if isinstance(chapter_routing, dict) else {}
    if not isinstance(matched, dict):
        return out
    for val in matched.values():
        if isinstance(val, list):
            out.extend([x for x in val if isinstance(x, dict)])
    return out


def _safe_int(v: Any, default: int) -> int:
    try:
        iv = int(v)
        return iv
    except Exception:
        return default


def _compute_reference_page_range(
    chapter_routing: Dict[str, Any],
    total_pages: int,
) -> Tuple[int, int]:
    """
    返回 (start_page, end_page_exclusive)，1-based。

    规则：
    - start_page = references 节点最小 page_start
    - end_page_exclusive：
      * 若存在 references 之后的其它章节，则取最小后续章节 page_start
      * 否则取 total_pages + 1（到文档末尾）
    """
    ref_nodes = _extract_ref_nodes(chapter_routing)
    if not ref_nodes:
        raise ValueError("chapter_routing 中未找到 references 路由节点")

    starts = [_safe_int(n.get("page_start"), 1) for n in ref_nodes]
    start_page = max(1, min(starts))

    next_starts: List[int] = []
    for n in _iter_all_matched_nodes(chapter_routing):
        title = str(n.get("title", "") or "")
        if _is_ref_title(title):
            continue
        ps = _safe_int(n.get("page_start"), 0)
        if ps > start_page:
            next_starts.append(ps)

    if next_starts:
        end_page_exclusive = min(next_starts)
    else:
        end_page_exclusive = max(2, total_pages + 1)

    end_page_exclusive = min(end_page_exclusive, total_pages + 1)
    if end_page_exclusive <= start_page:
        end_page_exclusive = min(total_pages + 1, start_page + 1)
    if end_page_exclusive <= start_page:
        raise ValueError("无法计算有效的参考文献页范围")

    return start_page, end_page_exclusive


def _extract_ref_markdown_section(md_text: str) -> str:
    """
    优先提取“## 参考文献/References/Bibliography”标题下的文本。
    若未匹配到二级标题，则回退到任意层级标题匹配；仍失败则返回全文。
    """
    lines = md_text.splitlines()
    if not lines:
        return ""

    h2_re = re.compile(r"^(##)\s+(.+?)\s*$")
    h_re = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
    candidates: List[Tuple[int, int]] = []

    for idx, line in enumerate(lines):
        m = h2_re.match(line.strip())
        if not m:
            continue
        title = m.group(2)
        if _is_ref_title(title):
            candidates.append((idx, 2))

    if not candidates:
        for idx, line in enumerate(lines):
            m = h_re.match(line.strip())
            if not m:
                continue
            title = m.group(2)
            lvl = len(m.group(1))
            if _is_ref_title(title):
                candidates.append((idx, lvl))

    if not candidates:
        return md_text.strip()

    start_idx, start_lvl = candidates[0]
    end_idx = len(lines)
    for j in range(start_idx + 1, len(lines)):
        m = h_re.match(lines[j].strip())
        if not m:
            continue
        lvl = len(m.group(1))
        if lvl <= start_lvl:
            end_idx = j
            break

    section = "\n".join(lines[start_idx:end_idx]).strip()
    return section if section else md_text.strip()


class ReferencesSliceAndDoclingTool(BaseTool):
    def __init__(self) -> None:
        super().__init__(
            name="references_slice_and_docling",
            description=(
                "基于 chapter_routing 的 references 路由切出参考文献子PDF，"
                "再用 docling 解析并提取参考文献章节 Markdown。"
            ),
            input_schema={
                "pdf_path": "必填，原始 PDF 路径",
                "chapter_routing": (
                    "必填，chapter_routing 节点的 tool_metadata 对象，"
                    "至少包含 matched_nodes.references"
                ),
                "redo_docling": "可选，是否强制重新 docling 解析，默认 false",
                "docling_md_preview_chars": "可选，docling 工具预览长度，默认 12000",
            },
        )

    def run(
        self,
        pdf_path: str = "",
        chapter_routing: Optional[Dict[str, Any]] = None,
        redo_docling: bool = False,
        docling_md_preview_chars: int = 12000,
        **kwargs: Any,
    ) -> ToolResult:
        try:
            if kwargs:
                pdf_path = str(kwargs.get("pdf_path", pdf_path) or pdf_path)
                chapter_routing = kwargs.get("chapter_routing", chapter_routing)
                redo_docling = bool(kwargs.get("redo_docling", redo_docling))
                docling_md_preview_chars = _safe_int(
                    kwargs.get("docling_md_preview_chars", docling_md_preview_chars),
                    docling_md_preview_chars,
                )

            src = Path(str(pdf_path or "").strip())
            if not src.exists():
                return ToolResult(
                    success=False,
                    output="",
                    error=f"pdf_path 不存在：{pdf_path}",
                    metadata={"pdf_path": pdf_path},
                )

            if not isinstance(chapter_routing, dict):
                return ToolResult(
                    success=False,
                    output="",
                    error="chapter_routing 缺失或格式非法，期望 dict",
                    metadata={"pdf_path": str(src)},
                )

            doc = fitz.open(str(src))
            total_pages = doc.page_count
            doc.close()

            start_page, end_page_exclusive = _compute_reference_page_range(
                chapter_routing=chapter_routing,
                total_pages=total_pages,
            )

            out_root = Path(settings.parsed_doc_dir) / "references_slice"
            out_root.mkdir(parents=True, exist_ok=True)
            stem = src.stem
            base_dir = out_root / f"{stem}_references_p{start_page}_{end_page_exclusive - 1}"
            run_dir = base_dir if not redo_docling else out_root / f"{base_dir.name}_{time.strftime('%Y%m%d_%H%M%S')}"
            run_dir.mkdir(parents=True, exist_ok=True)
            sliced_pdf = run_dir / "references_slice.pdf"

            docling_dir = run_dir / "docling"
            cached_md = docling_dir / "document.md"
            cached_json = docling_dir / "document.json"
            from_cache = False
            if (not redo_docling) and sliced_pdf.exists() and cached_md.exists() and cached_json.exists():
                from_cache = True
            else:
                src_doc = fitz.open(str(src))
                out_doc = fitz.open()
                try:
                    for p0 in range(start_page - 1, end_page_exclusive - 1):
                        out_doc.insert_pdf(src_doc, from_page=p0, to_page=p0)
                    out_doc.save(str(sliced_pdf))
                finally:
                    out_doc.close()
                    src_doc.close()

            if from_cache:
                md_path = cached_md
                json_path = str(cached_json)
                docling_output_dir = str(docling_dir)
            else:
                docling_out = parse_document_to_dir(
                    source=str(sliced_pdf),
                    output_root=str(settings.parsed_doc_dir),
                    output_dir=str(docling_dir),
                )
                if not docling_out.success or not docling_out.markdown_path:
                    return ToolResult(
                        success=False,
                        output="",
                        error=docling_out.error or "docling 解析失败",
                        metadata={
                            "pdf_path": str(src),
                            "slice_pdf_path": str(sliced_pdf),
                            "original_page_start": start_page,
                            "original_page_end_exclusive": end_page_exclusive,
                        },
                    )
                md_path = Path(docling_out.markdown_path)
                json_path = str(docling_out.json_path or "")
                docling_output_dir = str(docling_out.output_dir or docling_dir)

            md_text = md_path.read_text(encoding="utf-8") if md_path.exists() else ""
            ref_text = _extract_ref_markdown_section(md_text)

            ref_md_path = run_dir / "references_only.md"
            ref_md_path.write_text(ref_text, encoding="utf-8")

            preview_chars = max(0, int(docling_md_preview_chars))
            preview = ref_text[:preview_chars] if preview_chars else ""
            if preview_chars and len(ref_text) > preview_chars:
                preview += f"\n\n...[内容已截断，完整文件见: {ref_md_path}]"

            output = (
                f"[参考文献提取成功]\n"
                f"原PDF: {src}\n"
                f"参考文献页范围(原PDF): [{start_page}, {end_page_exclusive})\n"
                f"子PDF: {sliced_pdf}\n"
                f"Docling Markdown: {md_path}\n"
                f"参考文献正文文件: {ref_md_path}\n"
            )
            if preview:
                output += f"\n--- 参考文献正文预览 ---\n{preview}"

            return ToolResult(
                success=True,
                output=output,
                metadata={
                    "pdf_path": str(src),
                    "total_pages": total_pages,
                    "slice_pdf_path": str(sliced_pdf),
                    "original_page_start": start_page,
                    "original_page_end_exclusive": end_page_exclusive,
                    "original_page_end_inclusive": end_page_exclusive - 1,
                    "page_offset": start_page - 1,
                    "docling_output_dir": docling_output_dir,
                    "docling_markdown_path": str(md_path),
                    "docling_json_path": json_path,
                    "references_markdown_path": str(ref_md_path),
                    "references_text_chars": len(ref_text),
                    "from_cache": from_cache,
                    "redo_docling": bool(redo_docling),
                },
            )
        except Exception as e:  # noqa: BLE001
            logger.exception("ReferencesSliceAndDoclingTool 执行失败")
            return ToolResult(
                success=False,
                output="",
                error=str(e),
                metadata={"pdf_path": str(pdf_path or "")},
            )
