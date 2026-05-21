"""
LaTeX 项目扫描：文件图、checksum、main.tex 启发式（阶段 1，P0 解析）。
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Iterable, List, Optional, Set

from latex.constants import DEFAULT_MAX_SCAN_DEPTH, IGNORED_DIR_NAMES
from latex.bib_index import enrich_project_index
from latex.models import ProjectFile, ProjectIndex
from latex.paths import normalize_rel_path

_DOCUMENTCLASS_RE = re.compile(r"\\documentclass\b", re.IGNORECASE)
_INPUT_INCLUDE_RE = re.compile(
    r"\\(?:input|InputIfFileExists|include|includeonly)\s*\*?(?:\[[^\]]*\])?\s*\{([^}]+)\}",
    re.IGNORECASE,
)


def file_checksum(text: str) -> str:
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def _should_skip_dir(name: str) -> bool:
    return name in IGNORED_DIR_NAMES or name.startswith(".")


def iter_tex_files(root: Path, *, max_depth: int = DEFAULT_MAX_SCAN_DEPTH) -> Iterable[Path]:
    """在 root 下递归列举 .tex，限制相对深度并跳过常见无关目录。"""
    root = root.resolve()
    if not root.is_dir():
        return

    def walk(current: Path, depth: int) -> Iterable[Path]:
        if depth > max_depth:
            return
        try:
            entries = sorted(current.iterdir(), key=lambda p: p.name.lower())
        except OSError:
            return
        for entry in entries:
            if entry.is_dir():
                if _should_skip_dir(entry.name):
                    continue
                yield from walk(entry, depth + 1)
            elif entry.is_file() and entry.suffix.lower() == ".tex":
                yield entry

    yield from walk(root, 0)


def _normalize_input_path(raw: str, *, base_file: Path, root: Path) -> Optional[str]:
    """
    将 \\input/\\include 参数转为相对 root 的正斜杠路径。
    支持省略 .tex、相对路径。
    """
    token = raw.strip().strip('"').strip("'")
    if not token:
        return None
    if token.startswith("#"):
        return None

    candidate = Path(token)
    if not candidate.suffix:
        candidate = candidate.with_suffix(".tex")

    if candidate.is_absolute():
        try:
            resolved = candidate.resolve().relative_to(root.resolve())
        except ValueError:
            return None
    else:
        resolved = (base_file.parent / candidate).resolve()
        try:
            resolved = resolved.relative_to(root.resolve())
        except ValueError:
            return None

    return resolved.as_posix()


def extract_inputs(tex_source: str, *, base_file: Path, root: Path) -> List[str]:
    seen: Set[str] = set()
    out: List[str] = []
    for match in _INPUT_INCLUDE_RE.finditer(tex_source):
        rel = _normalize_input_path(match.group(1), base_file=base_file, root=root)
        if rel and rel not in seen:
            seen.add(rel)
            out.append(rel)
    return out


def find_main_tex_candidates(files: dict[str, ProjectFile], root: Path) -> List[str]:
    """含 \\documentclass 的 .tex，按路径字典序。"""
    candidates: List[str] = []
    for rel_path in sorted(files.keys()):
        full = root / rel_path
        if not full.is_file():
            continue
        try:
            text = full.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if _DOCUMENTCLASS_RE.search(text):
            candidates.append(rel_path)
    return candidates


def build_project_index(
    root: str | Path,
    *,
    main_tex: Optional[str] = None,
    max_depth: int = DEFAULT_MAX_SCAN_DEPTH,
    enrich: bool = True,
) -> ProjectIndex:
    """
    扫描目录并构建 ProjectIndex。

    Args:
        root: 项目根目录。
        main_tex: 显式指定主文件（相对 root）；未指定时用启发式（唯一 documentclass）。
        max_depth: 相对 root 的最大目录深度。
        enrich: 为 True 时填充 labels/refs、bib 与 conventions（阶段 2.5–2.7）。
    """
    root_path = Path(root).expanduser().resolve()
    if not root_path.is_dir():
        raise NotADirectoryError(f"不是有效目录: {root_path}")

    files: dict[str, ProjectFile] = {}

    for abs_path in iter_tex_files(root_path, max_depth=max_depth):
        rel = abs_path.relative_to(root_path).as_posix()
        try:
            text = abs_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            files[rel] = ProjectFile(checksum="", inputs=[])
            continue
        inputs = extract_inputs(text, base_file=abs_path, root=root_path)
        files[rel] = ProjectFile(checksum=file_checksum(text), inputs=inputs)

    candidates = find_main_tex_candidates(files, root_path)
    resolved_main: Optional[str] = None

    if main_tex:
        norm = normalize_rel_path(str(main_tex))
        if norm not in files:
            raise FileNotFoundError(f"main_tex 不在扫描结果中: {norm}")
        resolved_main = norm
    elif len(candidates) == 1:
        resolved_main = candidates[0]

    index = ProjectIndex(
        root=str(root_path),
        main_tex=resolved_main,
        main_tex_candidates=candidates,
        files=files,
        labels={},
        refs=[],
        bibliography_files=[],
        bib_entries={},
    )
    if enrich:
        return enrich_project_index(index)
    return index
