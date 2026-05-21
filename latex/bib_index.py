"""
Bibliography（.bib）解析与 cite 对齐（阶段 2.6）。
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Iterable, List, Set

from latex.constants import IssueSource, Severity
from latex.models import BibEntry, DiagnosticIssue, ProjectIndex
from latex.paths import normalize_rel_path
from latex.conventions_index import enrich_conventions
from latex.refs_index import enrich_refs_index
from latex.tex_source import read_tex_file, strip_comments

_BIBLIOGRAPHY_RE = re.compile(
    r"\\bibliography\s*\{([^}]+)\}",
    re.IGNORECASE,
)
_ADDBIB_RE = re.compile(
    r"\\addbibresource\s*\{([^}]+)\}",
    re.IGNORECASE,
)
_ENTRY_START_RE = re.compile(r"@\w+\s*\{\s*([^,\s}]+)\s*,", re.IGNORECASE)
_FIELD_RE = re.compile(
    r"(title|author)\s*=\s*(\{[^{}]*\}|\"[^\"]*\")",
    re.IGNORECASE,
)


def parse_bibliography_declarations(source: str) -> List[str]:
    """从 tex 源码解析 \\bibliography{} / \\addbibresource{} 声明的 .bib 路径。"""
    text = strip_comments(source)
    paths: List[str] = []
    seen: Set[str] = set()
    for pattern in (_BIBLIOGRAPHY_RE, _ADDBIB_RE):
        for match in pattern.finditer(text):
            for token in match.group(1).split(","):
                raw = token.strip().strip('"').strip("'")
                if not raw:
                    continue
                if not raw.lower().endswith(".bib"):
                    raw = f"{raw}.bib"
                norm = normalize_rel_path(raw)
                if norm and norm not in seen:
                    seen.add(norm)
                    paths.append(norm)
    return paths


def _unwrap_field_value(raw: str) -> str:
    text = raw.strip()
    if text.startswith("{") and text.endswith("}"):
        return text[1:-1].strip()
    if text.startswith('"') and text.endswith('"'):
        return text[1:-1].strip()
    return text


def parse_bib_file(path: Path) -> Dict[str, BibEntry]:
    """轻量解析 .bib：提取 @type{key, ...} 的 key、title、author。"""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}

    entries: Dict[str, BibEntry] = {}
    for match in _ENTRY_START_RE.finditer(text):
        key = match.group(1).strip()
        if not key or key in entries:
            continue
        start = match.end()
        next_at = text.find("@", start)
        block = text[start:next_at] if next_at >= 0 else text[start:]
        title = ""
        author = ""
        for field in _FIELD_RE.finditer(block):
            name = field.group(1).lower()
            value = _unwrap_field_value(field.group(2))
            if name == "title":
                title = value
            elif name == "author":
                author = value
        entries[key] = BibEntry(key=key, title=title, author=author)
    return entries


def resolve_bib_paths(root: Path, declarations: Iterable[str]) -> List[str]:
    """将声明路径解析为相对 root 且存在的 .bib 文件。"""
    found: List[str] = []
    seen: Set[str] = set()
    for decl in declarations:
        norm = normalize_rel_path(decl)
        if not norm:
            continue
        candidate = root / norm
        if candidate.is_file():
            rel = candidate.relative_to(root.resolve()).as_posix()
            if rel not in seen:
                seen.add(rel)
                found.append(rel)
    return found


def build_bib_index(
    index: ProjectIndex,
    *,
    check_missing_cites: bool = True,
) -> tuple[List[str], Dict[str, BibEntry], List[DiagnosticIssue]]:
    """解析 bibliography 声明与 .bib 条目；可选检测 tex 中缺失的 cite key。"""
    root = Path(index.root).resolve()
    issues: List[DiagnosticIssue] = []

    decls: List[str] = []
    if index.main_tex:
        main_path = root / index.main_tex
        if main_path.is_file():
            try:
                decls = parse_bibliography_declarations(read_tex_file(main_path))
            except OSError:
                pass

    bib_files = resolve_bib_paths(root, decls)
    bib_entries: Dict[str, BibEntry] = {}
    for rel in bib_files:
        bib_entries.update(parse_bib_file(root / rel))

    if check_missing_cites and bib_entries:
        cite_keys = {r.key for r in index.refs if r.kind == "cite"}
        for key in sorted(cite_keys):
            if key not in bib_entries:
                for entry in index.refs:
                    if entry.kind == "cite" and entry.key == key:
                        issues.append(
                            DiagnosticIssue.build(
                                file=entry.file,
                                line=entry.line,
                                message=f"\\cite{{{key}}} 在 .bib 中无对应条目",
                                source=IssueSource.PARSER,
                                severity=Severity.WARNING,
                                code="missing_bib_entry",
                            )
                        )
                        break

    return bib_files, bib_entries, issues


def enrich_bibliography(
    index: ProjectIndex,
    *,
    check_missing_cites: bool = True,
) -> ProjectIndex:
    """填充 bibliography_files / bib_entries。"""
    bib_files, bib_entries, _ = build_bib_index(
        index,
        check_missing_cites=check_missing_cites,
    )
    return index.model_copy(
        update={
            "bibliography_files": bib_files,
            "bib_entries": bib_entries,
        }
    )


def enrich_project_index(
    index: ProjectIndex,
    *,
    enrich_refs: bool = True,
    enrich_bib: bool = True,
    enrich_conv: bool = True,
    check_undefined_refs: bool = True,
    check_missing_cites: bool = True,
) -> ProjectIndex:
    """阶段 2.5 + 2.6 + 2.7 一步填充引用、文献与写作约定。"""
    out = index
    if enrich_refs:
        out = enrich_refs_index(out, check_undefined_refs=check_undefined_refs)
    if enrich_bib:
        out = enrich_bibliography(out, check_missing_cites=check_missing_cites)
    if enrich_conv:
        out = enrich_conventions(out)
    return out
