"""
Web 上传文件按类型落在仓库 ``storage/<类型>/`` 下。

- pdfs: PDF
- skills: 供 Agent 引用的 skill 文本/配置
- checklists: checklist 文本
- documents: 其余常见办公/论文/图片等（非上述专类时）
"""
from __future__ import annotations

import mimetypes
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, FrozenSet, List, Optional

# ui/web/file_storage.py -> …/Tex_Agent
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
STORAGE_ROOT = REPO_ROOT / "storage"

# 与 URL / 目录名一致
CATEGORY_PDFS = "pdfs"
CATEGORY_SKILLS = "skills"
CATEGORY_CHECKLISTS = "checklists"
CATEGORY_DOCUMENTS = "documents"

ALL_CATEGORIES = (
    CATEGORY_PDFS,
    CATEGORY_SKILLS,
    CATEGORY_CHECKLISTS,
    CATEGORY_DOCUMENTS,
)

_EXT: Dict[str, FrozenSet[str]] = {
    CATEGORY_PDFS: frozenset({".pdf"}),
    CATEGORY_SKILLS: frozenset(
        {".md", ".txt", ".yaml", ".yml", ".json", ".mdc"}
    ),
    CATEGORY_CHECKLISTS: frozenset({".md", ".txt", ".yaml", ".yml", ".json"}),
    CATEGORY_DOCUMENTS: frozenset(
        {
            ".doc",
            ".docx",
            ".odt",
            ".rtf",
            ".tex",
            ".txt",
            ".md",
            ".xlsx",
            ".xls",
            ".csv",
            ".png",
            ".jpg",
            ".jpeg",
            ".gif",
            ".webp",
            ".svg",
            ".zip",
            ".epub",
            ".bib",
            ".sty",
            ".cls",
            ".bst",
        }
    ),
}

MAX_UPLOAD_BYTES = 50 * 1024 * 1024


def category_dir(category: str) -> Path:
    if category not in ALL_CATEGORIES:
        raise ValueError(f"未知存储类别: {category!r}")
    return STORAGE_ROOT / category


def ensure_category_dir(category: str) -> Path:
    d = category_dir(category)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _ext_of(name: str) -> str:
    p = Path(name or "")
    return p.suffix.lower() or ""


def extension_allowed(category: str, filename: str) -> bool:
    ext = _ext_of(filename)
    return ext in _EXT.get(category, frozenset())


def sanitize_filename(name: str, *, default_stem: str = "file") -> str:
    raw = Path(name or default_stem).name
    stem = Path(raw).stem
    ext = Path(raw).suffix.lower()
    stem = re.sub(r"[^\w\u4e00-\u9fff\-.]+", "_", stem).strip("._") or default_stem
    stem = stem[:180]
    return stem + ext if ext else stem


def unique_stored_path(category: str, original_name: str) -> Path:
    name = sanitize_filename(original_name)
    if not extension_allowed(category, name):
        raise ValueError(f"此类别不允许扩展名: {name!r}")
    d = ensure_category_dir(category)
    p = d / name
    if not p.exists():
        return p
    stem = Path(name).stem
    ext = Path(name).suffix
    return d / f"{stem}_{uuid.uuid4().hex[:8]}{ext}"


def list_files(category: str) -> List[Dict[str, Any]]:
    d = ensure_category_dir(category)
    out: List[Dict[str, Any]] = []
    try:
        files = [f for f in d.iterdir() if f.is_file()]
    except OSError:
        return out
    # 占位用 .gitkeep 不应出现在用户文件列表
    files = [f for f in files if f.name.lower() != ".gitkeep"]
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


def resolve_safe_path(category: str, filename: str) -> Optional[Path]:
    """防目录穿越；仅允许该类别目录内真实文件。"""
    if category not in ALL_CATEGORIES:
        return None
    base = Path(filename).name
    if not base or base in (".", ".."):
        return None
    if not extension_allowed(category, base):
        return None
    d = category_dir(category).resolve()
    p = (d / base).resolve()
    try:
        p.relative_to(d)
    except ValueError:
        return None
    if not p.is_file():
        return None
    return p


def abs_path_for_injection(category: str, filename: str) -> Optional[str]:
    p = resolve_safe_path(category, filename)
    if p is None:
        return None
    return str(p.resolve())


def media_type_for_path(path: Path) -> str:
    mt, _ = mimetypes.guess_type(str(path))
    if mt:
        return mt
    return "application/octet-stream"


def allowed_extensions_hint(category: str) -> str:
    ex = sorted(_EXT.get(category, frozenset()))
    return ", ".join(ex) if ex else ""
