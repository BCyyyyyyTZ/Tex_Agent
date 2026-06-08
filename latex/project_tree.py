"""
Ghost UI 项目树构建（PR-10e）。
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Set

from latex.bib_index import parse_bibliography_declarations
from latex.models import ProjectFile
from latex.paths import normalize_rel_path
from latex.project_index import build_project_index


def _resolve_bib_candidates(root_path: Path, tex_rel: str, decl: str) -> List[str]:
    raw = normalize_rel_path(decl)
    if not raw:
        return []

    candidate = Path(raw)
    if not candidate.suffix:
        candidate = candidate.with_suffix(".bib")

    out: List[str] = []
    seen: Set[str] = set()

    # 1) 以声明文件所在目录解析
    local_resolved = (Path(tex_rel).parent / candidate).as_posix()
    # 2) 以 root 直接解析（兼容已有文档中的相对写法）
    root_resolved = candidate.as_posix()
    for rel in (local_resolved, root_resolved):
        norm = normalize_rel_path(rel)
        if not norm or norm in seen:
            continue
        if (root_path / norm).is_file():
            seen.add(norm)
            out.append(norm)
    return out


def _collect_bib_edges(root_path: Path, tex_files: List[str]) -> Dict[str, List[str]]:
    edges: Dict[str, List[str]] = {}
    for rel in tex_files:
        full = root_path / rel
        if not full.is_file():
            continue
        text = full.read_text(encoding="utf-8", errors="replace")
        decls = parse_bibliography_declarations(text)
        bibs: List[str] = []
        seen: Set[str] = set()
        for decl in decls:
            for bib_rel in _resolve_bib_candidates(root_path, rel, decl):
                if bib_rel in seen:
                    continue
                seen.add(bib_rel)
                bibs.append(bib_rel)
        if bibs:
            edges[rel] = sorted(bibs)
    return edges


def _iter_all_bib_files(root_path: Path) -> List[str]:
    out: List[str] = []
    for path in root_path.rglob("*.bib"):
        if path.is_file():
            out.append(path.relative_to(root_path).as_posix())
    return sorted(out)


def _build_tex_node(
    rel: str,
    files: Dict[str, ProjectFile],
    bib_edges: Dict[str, List[str]],
    attached_tex: Set[str],
    attached_bib: Set[str],
    stack: Set[str],
) -> Dict[str, object]:
    attached_tex.add(rel)
    if rel in stack:
        return {"path": rel, "kind": "tex", "children": []}

    node: Dict[str, object] = {"path": rel, "kind": "tex", "children": []}
    next_stack = set(stack)
    next_stack.add(rel)
    children: List[Dict[str, object]] = []

    for child_rel in sorted(files.get(rel, ProjectFile()).inputs):
        if child_rel in files:
            children.append(
                _build_tex_node(
                    child_rel,
                    files,
                    bib_edges,
                    attached_tex,
                    attached_bib,
                    next_stack,
                )
            )

    for bib_rel in sorted(bib_edges.get(rel, [])):
        attached_bib.add(bib_rel)
        children.append({"path": bib_rel, "kind": "bib", "children": []})

    node["children"] = children
    return node


def build_project_tree(*, root: str, main_tex: str | None = None) -> Dict[str, object]:
    root_path = Path(root).expanduser().resolve()
    index = build_project_index(root_path, main_tex=main_tex, enrich=False)

    tex_files = sorted(index.files.keys())
    bib_edges = _collect_bib_edges(root_path, tex_files)
    all_bibs = _iter_all_bib_files(root_path)

    nodes: List[Dict[str, object]] = []
    attached_tex: Set[str] = set()
    attached_bib: Set[str] = set()

    if index.main_tex and index.main_tex in index.files:
        nodes.append(
            _build_tex_node(
                index.main_tex,
                index.files,
                bib_edges,
                attached_tex,
                attached_bib,
                set(),
            )
        )

    for rel in tex_files:
        if rel in attached_tex:
            continue
        nodes.append(
            _build_tex_node(
                rel,
                index.files,
                bib_edges,
                attached_tex,
                attached_bib,
                set(),
            )
        )

    for bib_rel in all_bibs:
        if bib_rel in attached_bib:
            continue
        nodes.append({"path": bib_rel, "kind": "bib", "children": []})

    return {"main_tex": index.main_tex, "nodes": nodes}
