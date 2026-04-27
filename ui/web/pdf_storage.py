"""
Web 上传的 PDF 存放于仓库根下 ``storage/pdfs/``（见 ``ensure_pdf_dir``）。
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

# ui/web/pdf_storage.py -> …/Tex_Agent
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PDF_SUBDIR = Path("storage") / "pdfs"
MAX_PDF_BYTES = 50 * 1024 * 1024


def pdf_dir() -> Path:
    return REPO_ROOT / PDF_SUBDIR


def ensure_pdf_dir() -> Path:
    d = pdf_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d


def sanitize_pdf_filename(name: str) -> str:
    """仅保留安全文件名，保证以 .pdf 结尾。"""
    raw = Path(name or "document").name
    if not raw.lower().endswith(".pdf"):
        raw = (Path(raw).stem or "document") + ".pdf"
    stem = Path(raw).stem
    stem = re.sub(r"[^\w\u4e00-\u9fff\-.]+", "_", stem).strip("._") or "document"
    return stem[:180] + ".pdf"


def unique_pdf_path(original_name: str) -> Path:
    """在 ``storage/pdfs`` 下生成不冲突路径。"""
    name = sanitize_pdf_filename(original_name)
    d = ensure_pdf_dir()
    p = d / name
    if not p.exists():
        return p
    stem = Path(name).stem
    return d / f"{stem}_{uuid.uuid4().hex[:8]}.pdf"


def list_pdf_files() -> List[Dict[str, Any]]:
    """按修改时间倒序列出 PDF 元数据。"""
    d = ensure_pdf_dir()
    out: List[Dict[str, Any]] = []
    try:
        files = list(d.glob("*.pdf"))
    except OSError:
        return out
    files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    for f in files:
        try:
            st = f.stat()
            out.append(
                {
                    "name": f.name,
                    "size": int(st.st_size),
                    "modified": datetime.fromtimestamp(st.st_mtime).isoformat(
                        timespec="seconds"
                    ),
                }
            )
        except OSError:
            continue
    return out


def resolve_safe_pdf_path(filename: str) -> Path | None:
    """仅允许 ``storage/pdfs`` 下的 .pdf 文件。"""
    base = Path(filename).name
    if not base or not base.lower().endswith(".pdf"):
        return None
    d = ensure_pdf_dir().resolve()
    p = (d / base).resolve()
    try:
        p.relative_to(d)
    except ValueError:
        return None
    if not p.is_file():
        return None
    return p
