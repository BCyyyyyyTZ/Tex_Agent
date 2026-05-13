"""
ThesisOutlineExtractTool：按 PDF 目录树提取指定章节。

能力：
1) mode=outline：仅提取目录树和页码区间，不抽正文；
2) mode=extract：按用户给定 chapters 选择器抽取指定章节正文（pdfplumber 按页），输出 Markdown + docling 兼容 JSON。
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from config.settings import settings
from core.message import ToolResult
from tools.base_tool import BaseTool
from utils.logger import get_logger
from utils.thesis_pdf_extract import (
    ChapterNode,
    build_docling_compatible_json,
    build_outline_tree,
    build_outline_tree_from_toc,
    compute_end_pages,
    flatten_nodes,
    process_chapter,
    select_nodes_by_chapters,
    write_markdown,
)

logger = get_logger(__name__)
_CACHE_VERSION = "v3"


def _sanitize_stem(stem: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in ("_", "-") else "_" for ch in (stem or "document"))
    safe = safe.strip("_")[:120]
    return safe or "document"


def _selection_key(mode: str, chapters: str) -> str:
    payload = f"{_CACHE_VERSION}|{mode}|{str(chapters or '').strip()}".encode("utf-8")
    return hashlib.sha1(payload).hexdigest()[:8]


def _iter_subtree(root: ChapterNode) -> List[ChapterNode]:
    out: List[ChapterNode] = []
    flatten_nodes([root], out)
    return out


def _dump_outline_tree(nodes: List[ChapterNode]) -> List[Dict[str, Any]]:
    def _one(node: ChapterNode) -> Dict[str, Any]:
        return {
            "title": node.title,
            "number": node.number,
            "depth": node.depth,
            "page_start": int(node.page) + 1,
            "page_end_exclusive": int(node.end_page or node.page) + 1,
            "children": [_one(c) for c in node.children],
        }

    return [_one(n) for n in nodes]


def _outline_text(nodes: List[ChapterNode]) -> str:
    lines: List[str] = []
    for node in nodes:
        indent = "  " * max(0, node.depth)
        number = f"{node.number} " if node.number else ""
        end_page = (node.end_page or node.page) + 1
        lines.append(f"{indent}- {number}{node.title}  (p{node.page + 1}-p{end_page - 1})")
    return "\n".join(lines)


def _resolve_pdf_path(pdf_path: str) -> Path:
    src = Path(pdf_path)
    if src.exists():
        return src.resolve()
    workspace_dir = getattr(settings, "workspace_dir", "")
    if workspace_dir:
        candidate = Path(workspace_dir) / pdf_path
        if candidate.exists():
            return candidate.resolve()
    return src


def _load_outline(pdf_path: Path, outline_source: str) -> Tuple[List[ChapterNode], int, str]:
    source = (outline_source or "auto").strip().lower()
    errors: List[str] = []

    if source in {"auto", "pypdf"}:
        try:
            import pypdf

            reader = pypdf.PdfReader(str(pdf_path))
            outlines = reader.outline
            total_pages = len(reader.pages)
            if outlines:
                tree = build_outline_tree(reader, outlines)
                if tree:
                    return tree, total_pages, "pypdf"
            errors.append("pypdf 未读取到目录")
        except Exception as e:  # noqa: BLE001
            errors.append(f"pypdf 读取失败: {e}")
            if source == "pypdf":
                raise ValueError("; ".join(errors)) from e

    if source in {"auto", "pymupdf"}:
        try:
            import fitz

            doc = fitz.open(str(pdf_path))
            total_pages = int(doc.page_count)
            toc = doc.get_toc()
            doc.close()
            tree = build_outline_tree_from_toc(toc)
            if tree:
                return tree, total_pages, "pymupdf"
            errors.append("pymupdf 未读取到目录")
        except Exception as e:  # noqa: BLE001
            errors.append(f"pymupdf 读取失败: {e}")
            if source == "pymupdf":
                raise ValueError("; ".join(errors)) from e

    raise ValueError("; ".join(errors) if errors else "该 PDF 没有可用目录树")


def _find_existing_output(root: Path, stem: str, key: str, mode: str) -> Optional[Path]:
    if not root.exists():
        return None
    prefix = f"{_sanitize_stem(stem)}_thesis_outline_{key}_"
    candidates: List[Path] = []
    for item in root.iterdir():
        if not item.is_dir() or not item.name.startswith(prefix):
            continue
        outline = item / "outline.json"
        if not outline.exists():
            continue
        if mode == "outline":
            candidates.append(item)
            continue
        md = item / "document.md"
        js = item / "document.json"
        sel = item / "selection.json"
        if md.exists() and js.exists() and sel.exists() and md.stat().st_size > 0:
            candidates.append(item)
    if not candidates:
        return None
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0]


class ThesisOutlineExtractTool(BaseTool):
    def __init__(self) -> None:
        super().__init__(
            name="thesis_outline_extract",
            description=(
                "按 PDF 目录树提取章节。mode=outline 只输出目录与页码，"
                "mode=extract 需要 chapters 并输出章节 Markdown + docling 兼容 JSON。"
            ),
            input_schema={
                "pdf_path": "必填，论文 PDF 路径",
                "mode": "可选：outline/extract（默认 extract）",
                "chapters": "extract 模式必填，章节选择器（例：3.1;3.2-3.4;第4章）",
                "outline_source": "可选：auto/pypdf/pymupdf（默认 auto）",
                "redo": "可选，true 强制重跑，默认 false",
                "strict_chapters": "可选，true 表示章节未匹配时直接失败，默认 true",
                "md_preview_chars": "可选，output 内 Markdown 预览长度，默认 2000",
            },
        )

    def run(
        self,
        pdf_path: str,
        mode: str = "extract",
        chapters: str = "",
        outline_source: str = "auto",
        redo: bool = False,
        strict_chapters: bool = True,
        md_preview_chars: int = 2000,
    ) -> ToolResult:
        try:
            src = _resolve_pdf_path(pdf_path)
            if not src.exists():
                return ToolResult(success=False, output="", error=f"文件不存在: {pdf_path}")

            run_mode = str(mode or "extract").strip().lower()
            if run_mode not in {"outline", "extract"}:
                return ToolResult(success=False, output="", error=f"不支持的 mode: {mode}")
            if run_mode == "extract" and not str(chapters or "").strip():
                return ToolResult(success=False, output="", error="extract 模式必须提供 chapters，且不支持默认全文提取。")

            parsed_root = Path(settings.parsed_doc_dir)
            key = _selection_key(run_mode, chapters)
            if not redo:
                cached = _find_existing_output(parsed_root, src.stem, key, run_mode)
                if cached:
                    return self._load_cached_result(cached, run_mode, md_preview_chars)

            tree, total_pages, used_source = _load_outline(src, outline_source)
            flat: List[ChapterNode] = []
            flatten_nodes(tree, flat)
            compute_end_pages(flat, total_pages)

            ts = int(time.time())
            out_dir = parsed_root / f"{_sanitize_stem(src.stem)}_thesis_outline_{key}_{ts}"
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / "artifacts").mkdir(exist_ok=True)

            outline_json = {
                "source_pdf": src.name,
                "total_pages": total_pages,
                "outline_source": used_source,
                "tree": _dump_outline_tree(tree),
            }
            outline_path = out_dir / "outline.json"
            outline_path.write_text(json.dumps(outline_json, ensure_ascii=False, indent=2), encoding="utf-8")

            if run_mode == "outline":
                output = (
                    f"[outline 提取成功] 文档: {src}\n"
                    f"总页数: {total_pages}  目录源: {used_source}\n"
                    f"输出目录: {out_dir}\n"
                    f"outline.json: {outline_path}\n\n"
                    f"--- 目录树预览 ---\n{_outline_text(flat[:200])}"
                )
                metadata = {
                    "success": True,
                    "mode": "outline",
                    "source_path": str(src),
                    "output_dir": str(out_dir),
                    "outline_path": str(outline_path),
                    "total_pages": total_pages,
                    "outline_source": used_source,
                    "route": "thesis_outline",
                    "from_cache": False,
                }
                return ToolResult(success=True, output=output, metadata=metadata)

            selected_roots, unresolved = select_nodes_by_chapters(tree, chapters)
            if not selected_roots:
                msg = f"未匹配到任何章节：{chapters}"
                if strict_chapters:
                    return ToolResult(success=False, output="", error=msg)
                logger.warning(msg)

            # 先处理整棵目录树，再输出选中章节，避免“同页相邻小节”出现空正文
            for root in tree:
                process_chapter(root, pdf_path=str(src))

            import io

            buf = io.StringIO()
            for root in selected_roots:
                write_markdown(root, buf)
            md = buf.getvalue()

            selected_flat: List[ChapterNode] = []
            for root in selected_roots:
                selected_flat.extend(_iter_subtree(root))
            json_data = build_docling_compatible_json(selected_flat, src.name)

            md_path = out_dir / "document.md"
            json_path = out_dir / "document.json"
            sel_path = out_dir / "selection.json"
            md_path.write_text(md, encoding="utf-8")
            json_path.write_text(json.dumps(json_data, ensure_ascii=False, indent=2), encoding="utf-8")
            sel_obj = {
                "chapters_input": chapters,
                "strict_chapters": bool(strict_chapters),
                "unresolved_tokens": unresolved,
                "selected_chapters": [
                    {
                        "number": n.number,
                        "title": n.title,
                        "depth": n.depth,
                        "page_start": n.page + 1,
                        "page_end_exclusive": (n.end_page or n.page) + 1,
                        "match_reason": n.match_reason or "",
                        "match_input": n.match_input or "",
                        "ordinal_path": list(n.ordinal_path) if n.ordinal_path else [],
                    }
                    for n in selected_roots
                ],
            }
            sel_path.write_text(json.dumps(sel_obj, ensure_ascii=False, indent=2), encoding="utf-8")
            full_text_mode = any(n.match_reason == "all" for n in selected_roots)
            ordinal_only = bool(selected_roots) and all(
                n.match_reason == "ordinal" for n in selected_roots
            )

            preview = md[: max(0, int(md_preview_chars or 0))]
            metadata = {
                "success": True,
                "mode": "extract",
                "source_path": str(src),
                "output_dir": str(out_dir),
                "outline_path": str(outline_path),
                "markdown_path": str(md_path),
                "json_path": str(json_path),
                "selection_path": str(sel_path),
                "total_pages": total_pages,
                "outline_source": used_source,
                "selected_chapters": sel_obj["selected_chapters"],
                "unresolved_chapter_tokens": unresolved,
                "full_text_mode": full_text_mode,
                "ordinal_only": ordinal_only,
                "route": "thesis_outline",
                "from_cache": False,
            }
            out = (
                f"[章节提取成功] 文档: {src}\n"
                f"目录源: {used_source}\n"
                f"选择器: {chapters}\n"
                f"命中章节: {len(selected_roots)}\n"
                f"输出目录: {out_dir}\n"
                f"Markdown: {md_path}\n"
                f"JSON: {json_path}\n"
                f"Selection: {sel_path}\n"
            )
            if full_text_mode:
                out += "模式: 全文（已选中所有根章节）\n"
            elif ordinal_only:
                out += "提示: 当前 PDF 目录可能缺少明确编号，已按目录顺序数到对应章节。\n"
            if unresolved:
                out += f"未匹配章节: {unresolved}\n"
            if preview:
                out += f"\n--- Markdown 预览（前 {md_preview_chars} 字符） ---\n{preview}"
            return ToolResult(success=True, output=out, metadata=metadata)
        except Exception as e:  # noqa: BLE001
            logger.exception("ThesisOutlineExtractTool 执行失败")
            return ToolResult(success=False, output="", error=str(e), metadata={"pdf_path": pdf_path, "mode": mode})

    def _load_cached_result(self, out_dir: Path, mode: str, md_preview_chars: int) -> ToolResult:
        outline_path = out_dir / "outline.json"
        outline_obj = {}
        try:
            outline_obj = json.loads(outline_path.read_text(encoding="utf-8"))
        except Exception:
            outline_obj = {}

        metadata = {
            "success": True,
            "mode": mode,
            "output_dir": str(out_dir),
            "outline_path": str(outline_path),
            "total_pages": int(outline_obj.get("total_pages", 0) or 0),
            "outline_source": str(outline_obj.get("outline_source", "") or ""),
            "route": "thesis_outline",
            "from_cache": True,
        }
        if mode == "outline":
            tree_preview = ""
            tree = outline_obj.get("tree", [])
            if isinstance(tree, list):
                lines: List[str] = []
                for item in tree[:50]:
                    if not isinstance(item, dict):
                        continue
                    lines.append(f"- {item.get('title', '')}")
                tree_preview = "\n".join(lines)
            output = (
                f"[缓存复用-outline] 输出目录: {out_dir}\n"
                f"outline.json: {outline_path}\n"
            )
            if tree_preview:
                output += f"\n--- 目录树预览 ---\n{tree_preview}"
            return ToolResult(success=True, output=output, metadata=metadata)

        md_path = out_dir / "document.md"
        json_path = out_dir / "document.json"
        sel_path = out_dir / "selection.json"
        preview = ""
        if md_path.exists() and md_preview_chars:
            preview = md_path.read_text(encoding="utf-8")[:md_preview_chars]
        sel_obj: Dict[str, Any] = {}
        if sel_path.exists():
            try:
                sel_obj = json.loads(sel_path.read_text(encoding="utf-8"))
            except Exception:
                sel_obj = {}
        metadata.update(
            {
                "markdown_path": str(md_path),
                "json_path": str(json_path),
                "selection_path": str(sel_path),
                "selected_chapters": sel_obj.get("selected_chapters", []),
                "unresolved_chapter_tokens": sel_obj.get("unresolved_tokens", []),
            }
        )
        output = (
            f"[缓存复用-章节提取] 输出目录: {out_dir}\n"
            f"Markdown: {md_path}\n"
            f"JSON: {json_path}\n"
            f"Selection: {sel_path}\n"
        )
        if preview:
            output += f"\n--- Markdown 预览（前 {md_preview_chars} 字符） ---\n{preview}"
        return ToolResult(success=True, output=output, metadata=metadata)

