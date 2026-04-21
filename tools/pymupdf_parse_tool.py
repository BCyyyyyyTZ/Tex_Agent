"""
PyMuPDFParseTool：使用 PyMuPDF（fitz）直接提取 PDF 文本层，生成与 DoclingParseTool 兼容的
Markdown + JSON 输出，无页数限制，适合 20+ 页的学位论文。

与 DoclingParseTool 的区别：
  - 不依赖 Docling / OCR，速度极快（<1s/页）
  - 无 20+ 页解析失败的问题
  - 输出格式（output_dir / markdown_path / json_path / metadata）与 Docling 兼容
  - 能识别粗体/大字号为标题（基于字体大小启发式）
  - 不支持图表内容识别（图表以 [图/表 P{n}] 占位）

JSON 格式：
  {"texts": [{"text": "...", "label": "section_header"|"text", "prov": [{"page_no": N}]}]}
"""

import json
import re
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import fitz  # PyMuPDF

from tools.base_tool import BaseTool
from core.message import ToolResult
from config.settings import settings
from utils.logger import get_logger

logger = get_logger(__name__)

_SANITIZE_RE = re.compile(r"[^\w\-]+", flags=re.UNICODE)


def _sanitize_stem(stem: str) -> str:
    s = _SANITIZE_RE.sub("_", stem.strip()) or "document"
    return s[:120] or "document"


def _find_existing_parse(root: Path, source_stem: str) -> Optional[Path]:
    """查找已有的 pymupdf 解析缓存目录。"""
    if not root.exists():
        return None
    safe_stem = _sanitize_stem(source_stem)
    candidates = []
    for item in root.iterdir():
        if item.is_dir() and item.name.startswith(f"{safe_stem}_pymupdf_"):
            md = item / "document.md"
            js = item / "document.json"
            if md.exists() and js.exists() and md.stat().st_size > 50:
                candidates.append(item)
    if not candidates:
        return None
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0]


# ---------------------------------------------------------------------------
# 核心提取逻辑
# ---------------------------------------------------------------------------

class _PageBlock:
    """单页中的一个文本块。"""
    __slots__ = ("text", "font_size", "is_bold", "page_no", "bbox")

    def __init__(self, text: str, font_size: float, is_bold: bool, page_no: int, bbox: tuple):
        self.text = text.strip()
        self.font_size = font_size
        self.is_bold = is_bold
        self.page_no = page_no
        self.bbox = bbox


def _extract_blocks(doc: fitz.Document) -> List[_PageBlock]:
    """
    逐页提取文本块，同时获取字体大小和粗体信息。
    使用 get_text("dict") 模式获取每个 span 的样式信息。
    """
    all_blocks: List[_PageBlock] = []

    for page_no, page in enumerate(doc, start=1):
        page_dict = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)
        for block in page_dict.get("blocks", []):
            if block.get("type") != 0:  # 0 = text, 1 = image
                continue
            lines_text = []
            max_size = 0.0
            has_bold = False
            for line in block.get("lines", []):
                span_texts = []
                for span in line.get("spans", []):
                    sz = span.get("size", 10)
                    flags = span.get("flags", 0)
                    bold = bool(flags & 16)  # bit4 = bold
                    span_texts.append(span.get("text", ""))
                    if sz > max_size:
                        max_size = sz
                    if bold:
                        has_bold = True
                line_text = "".join(span_texts).strip()
                if line_text:
                    lines_text.append(line_text)

            full_text = "\n".join(lines_text).strip()
            if not full_text:
                continue

            bbox = block.get("bbox", (0, 0, 0, 0))
            all_blocks.append(_PageBlock(full_text, max_size, has_bold, page_no, bbox))

    return all_blocks


# 中文章节章级标题（"第X章" 开头或独立的特殊章节名）
_CH_CHAPTER_RE = re.compile(
    r'^(?:第\s*[一二三四五六七八九十百\d]+\s*[章节篇])',
    re.UNICODE
)
# 独立特殊章节名
_CH_SPECIAL_RE = re.compile(
    r'^(?:参考文献|致\s*谢|附\s*录[A-Z]?|摘\s*要|Abstract|目\s*录|'
    r'绪论|引言|总结|结论|结语)\s*$',
    re.UNICODE
)
# 目录行（含点线）——不应被识别为标题
_TOC_LINE_RE = re.compile(r'[\.\u00b7]{4,}|(?:\. ){3,}')


def _classify_label(block: _PageBlock, median_size: float) -> str:
    """
    启发式判断文本块类型：
      - "第X章..." 开头 且不含目录点线 → section_header（H1/H2 级）
      - 独立特殊章节名（参考文献、致谢等）→ section_header
      - 字号 >= 正文的 1.15x 且短文本 且不含目录点线 → section_header
      - 粗体且行数<=2 且不含目录点线 → section_header
      - 否则 → text
    """
    text_stripped = block.text.strip()
    lines = [l for l in text_stripped.splitlines() if l.strip()]
    line_count = len(lines)

    # 过滤目录点线行（属于目录内容，不是标题）
    if _TOC_LINE_RE.search(text_stripped):
        return "text"

    # 中文章节级标题（限制长度 <= 30 字，避免把句子开头误识别为章节号）
    if _CH_CHAPTER_RE.match(text_stripped) and len(text_stripped) <= 30:
        return "section_header"

    # 独立特殊章节名
    if _CH_SPECIAL_RE.match(text_stripped):
        return "section_header"

    # 字号阈值：1.15x（适配学位论文 14pt/12pt 比例）
    big_font = block.font_size >= median_size * 1.15
    if (big_font or block.is_bold) and line_count <= 3 and len(text_stripped) < 120:
        return "section_header"
    return "text"


def _build_markdown(blocks: List[_PageBlock], median_size: float) -> str:
    """将文本块列表转为 Markdown 字符串。"""
    lines = []
    prev_page = 0
    for b in blocks:
        if b.page_no != prev_page:
            if prev_page:
                lines.append("")
            lines.append(f"\n<!-- page {b.page_no} -->")
            prev_page = b.page_no

        label = _classify_label(b, median_size)
        if label == "section_header":
            text_s = b.text.strip()
            # 章级标题 → H1；小节编号（如 1.1） → H2；其他 → H3
            if _CH_CHAPTER_RE.match(text_s) or _CH_SPECIAL_RE.match(text_s):
                prefix = "# "
            elif re.match(r'^\d+\.\d+', text_s):
                prefix = "## "
            elif re.match(r'^\d+\.\d+\.\d+', text_s):
                prefix = "### "
            else:
                ratio = b.font_size / median_size if median_size else 1
                if ratio >= 1.8:
                    prefix = "# "
                elif ratio >= 1.4:
                    prefix = "## "
                else:
                    prefix = "### "
            lines.append(f"\n{prefix}{b.text}")
        else:
            lines.append(b.text)

    return "\n".join(lines)


def _build_json(blocks: List[_PageBlock], median_size: float, source_name: str) -> dict:
    """构建与 Docling 兼容的 JSON 结构。"""
    texts = []
    for i, b in enumerate(blocks):
        label = _classify_label(b, median_size)
        entry = {
            "self_ref": f"#/texts/{i}",
            "parent": {"$ref": "#/body"},
            "children": [],
            "content_layer": "body",
            "label": label,
            "prov": [{"page_no": b.page_no, "bbox": {
                "l": b.bbox[0], "t": b.bbox[1],
                "r": b.bbox[2], "b": b.bbox[3],
                "coord_origin": "TOPLEFT"
            }}],
            "orig": b.text,
            "text": b.text,
        }
        texts.append(entry)

    return {
        "schema_name": "DoclingDocument",
        "version": "1.0-pymupdf",
        "name": source_name,
        "origin": {"filename": source_name},
        "body": {},
        "texts": texts,
        "tables": [],
        "pictures": [],
    }


def _median_font_size(blocks: List[_PageBlock]) -> float:
    sizes = sorted(b.font_size for b in blocks if b.font_size > 6)
    if not sizes:
        return 10.0
    return sizes[len(sizes) // 2]


# ---------------------------------------------------------------------------
# Tool
# ---------------------------------------------------------------------------

class PyMuPDFParseTool(BaseTool):
    """
    PyMuPDF 快速 PDF 文本提取工具。

    适合有文字层的 PDF（非扫描件），无页数限制，速度远快于 Docling。
    输出与 DoclingParseTool 兼容：同样的 output_dir / markdown_path / json_path。
    下游可直接使用 docling_search、markdown_section 等工具。
    """

    def __init__(self):
        super().__init__(
            name="pymupdf_parse",
            description=(
                "使用 PyMuPDF 直接提取 PDF 文字层，生成 Markdown + JSON，无页数限制。"
                "适合有文字层的学位论文 PDF（非扫描件）。"
                "输出格式与 docling_parse 兼容，下游可直接接 markdown_section / docling_search。"
                "参数 redo=true 强制重新提取，否则优先复用缓存。"
            ),
            input_schema={
                "pdf_path": "必填，PDF 文件路径（绝对或相对均可）",
                "redo": "可选，是否强制重新提取（默认 false，优先复用缓存）",
                "md_preview_chars": "可选，output 中附带的 Markdown 预览字符数，默认 2000",
            }
        )

    def run(
        self,
        pdf_path: str,
        redo: bool = False,
        md_preview_chars: int = 2000,
    ) -> ToolResult:

        logger.info(f"PyMuPDFParseTool | pdf={pdf_path!r} redo={redo}")
        try:
            src = Path(pdf_path)
            if not src.exists():
                # 尝试相对路径
                src = Path(settings.workspace_dir) / pdf_path if hasattr(settings, 'workspace_dir') else src
            if not src.exists():
                return ToolResult(success=False, output="", error=f"文件不存在: {pdf_path}")

            parsed_root = Path(settings.parsed_doc_dir)
            safe_stem = _sanitize_stem(src.stem)

            # ── 缓存检查 ──────────────────────────────────────────
            if not redo:
                cached = _find_existing_parse(parsed_root, src.stem)
                if cached:
                    md_path = cached / "document.md"
                    json_path = cached / "document.json"
                    md_size = md_path.stat().st_size
                    preview = md_path.read_text("utf-8")[:md_preview_chars] if md_preview_chars else ""
                    logger.info(f"[缓存复用] {cached.name}")
                    output_text = (
                        f"[缓存复用-pymupdf] 文档: {pdf_path}\n"
                        f"输出目录: {cached}\n"
                        f"Markdown: {md_path}  ({md_size:,} 字节)\n"
                        f"JSON: {json_path}\n"
                    )
                    if preview:
                        output_text += f"\n--- Markdown 预览（前 {md_preview_chars} 字符） ---\n{preview}"
                    return ToolResult(
                        success=True, output=output_text,
                        metadata={
                            "success": True, "source_path": str(src),
                            "output_dir": str(cached),
                            "markdown_path": str(md_path),
                            "json_path": str(json_path),
                            "artifacts_dir": str(cached / "artifacts"),
                            "md_size_bytes": md_size,
                            "from_cache": True, "route": "pymupdf",
                        }
                    )

            # ── 提取 ─────────────────────────────────────────────
            t0 = time.time()
            doc = fitz.open(str(src))
            page_count = doc.page_count
            logger.info(f"开始提取，共 {page_count} 页")

            blocks = _extract_blocks(doc)
            doc.close()

            if not blocks:
                return ToolResult(success=False, output="", error="PDF 未提取到任何文本（可能是扫描件）")

            median_size = _median_font_size(blocks)
            md_text = _build_markdown(blocks, median_size)
            json_data = _build_json(blocks, median_size, src.name)

            # ── 保存 ─────────────────────────────────────────────
            ts = int(time.time())
            out_dir = parsed_root / f"{safe_stem}_pymupdf_{ts}"
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / "artifacts").mkdir(exist_ok=True)

            md_path = out_dir / "document.md"
            json_path = out_dir / "document.json"
            md_path.write_text(md_text, encoding="utf-8")
            json_path.write_text(json.dumps(json_data, ensure_ascii=False, indent=2), encoding="utf-8")

            elapsed = time.time() - t0
            md_size = md_path.stat().st_size
            preview = md_text[:md_preview_chars] if md_preview_chars else ""

            output_text = (
                f"[pymupdf 提取成功] 文档: {pdf_path}\n"
                f"页数: {page_count}  文本块: {len(blocks)}  字号中位: {median_size:.1f}pt\n"
                f"耗时: {elapsed:.1f}s\n"
                f"输出目录: {out_dir}\n"
                f"Markdown: {md_path}  ({md_size:,} 字节)\n"
                f"JSON: {json_path}\n"
            )
            if preview:
                output_text += f"\n--- Markdown 预览（前 {md_preview_chars} 字符） ---\n{preview}"

            logger.info(f"提取完成 | 页={page_count} 块={len(blocks)} 耗时={elapsed:.1f}s")
            return ToolResult(
                success=True, output=output_text,
                metadata={
                    "success": True, "source_path": str(src),
                    "output_dir": str(out_dir),
                    "markdown_path": str(md_path),
                    "json_path": str(json_path),
                    "artifacts_dir": str(out_dir / "artifacts"),
                    "md_size_bytes": md_size,
                    "page_count": page_count,
                    "block_count": len(blocks),
                    "from_cache": False, "route": "pymupdf",
                }
            )

        except Exception as e:
            logger.exception(f"PyMuPDFParseTool 异常: {e}")
            return ToolResult(success=False, output="", error=str(e),
                              metadata={"pdf_path": pdf_path})
