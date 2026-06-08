"""
全项目 label / ref / cite 索引（阶段 2.5）。
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple

from latex.constants import IssueSource, Severity
from latex.models import DiagnosticIssue, LabelDef, ProjectIndex, RefEntry
from latex.tex_source import read_tex_file, strip_inline_comment

_LABEL_RE = re.compile(r"\\label\s*\{([^}]+)\}", re.IGNORECASE)
_REF_RE = re.compile(
    r"\\(?:ref|eqref|pageref|autoref|nameref|cref|Cref)\s*\*?"
    r"(?:\[[^\]]*\])?\s*\{([^}]+)\}",
    re.IGNORECASE,
)
_CITE_RE = re.compile(r"\\cite\w*\s*\*?(?:\[[^\]]*\])?\s*\{([^}]+)\}", re.IGNORECASE)


def iter_main_closure_files(index: ProjectIndex) -> List[str]:
    """从 main_tex 沿 \\input 边 BFS；无 main 时返回全部 tex（字典序）。"""
    files = index.files
    if not files:
        return []

    if index.main_tex and index.main_tex in files:
        start = index.main_tex
    else:
        return sorted(files.keys())

    seen: Set[str] = set()
    order: List[str] = []
    queue: List[str] = [start]
    while queue:
        rel = queue.pop(0)
        if rel in seen or rel not in files:
            continue
        seen.add(rel)
        order.append(rel)
        for inp in files[rel].inputs:
            if inp not in seen:
                queue.append(inp)
    return order


def _split_keys(raw: str) -> List[str]:
    return [k.strip() for k in raw.split(",") if k.strip()]


def extract_refs_from_source(
    source: str,
    *,
    rel_path: str,
) -> Tuple[Dict[str, LabelDef], List[RefEntry]]:
    """从单文件源码提取 label 定义与 ref/cite 引用。"""
    labels: Dict[str, LabelDef] = {}
    refs: List[RefEntry] = []

    for line_no, raw_line in enumerate(source.splitlines(), start=1):
        line = strip_inline_comment(raw_line)
        if not line.strip():
            continue

        for lab in _LABEL_RE.finditer(line):
            key = lab.group(1).strip()
            if key and key not in labels:
                labels[key] = LabelDef(defined_in=rel_path, line=line_no)

        for ref in _REF_RE.finditer(line):
            for key in _split_keys(ref.group(1)):
                refs.append(
                    RefEntry(key=key, file=rel_path, line=line_no, kind="ref")
                )

        for cite in _CITE_RE.finditer(line):
            for key in _split_keys(cite.group(1)):
                refs.append(
                    RefEntry(key=key, file=rel_path, line=line_no, kind="cite")
                )

    return labels, refs


def build_refs_index(
    index: ProjectIndex,
    *,
    scope: str = "main_closure",
    check_undefined_refs: bool = True,
) -> Tuple[Dict[str, LabelDef], List[RefEntry], List[DiagnosticIssue]]:
    """
    在 ProjectIndex 上构建全局 labels / refs。

    scope:
        - main_closure: 仅 main_tex 可达闭包（推荐）
        - all: 扫描到的全部 tex
    """
    root = Path(index.root)
    if scope == "all":
        rel_files = sorted(index.files.keys())
    else:
        rel_files = iter_main_closure_files(index)

    global_labels: Dict[str, LabelDef] = {}
    global_refs: List[RefEntry] = []
    issues: List[DiagnosticIssue] = []

    for rel in rel_files:
        full = root / rel
        if not full.is_file():
            continue
        try:
            text = read_tex_file(full)
        except OSError:
            continue
        file_labels, file_refs = extract_refs_from_source(text, rel_path=rel)
        for key, defn in file_labels.items():
            if key not in global_labels:
                global_labels[key] = defn
        global_refs.extend(file_refs)

    if check_undefined_refs:
        for entry in global_refs:
            if entry.kind != "ref":
                continue
            if entry.key in global_labels:
                continue
            issues.append(
                DiagnosticIssue.build(
                    file=entry.file,
                    line=entry.line,
                    message=f"未定义的引用: \\ref{{{entry.key}}}",
                    source=IssueSource.PARSER,
                    severity=Severity.WARNING,
                    code="undefined_ref",
                )
            )

    return global_labels, global_refs, issues


def enrich_refs_index(
    index: ProjectIndex,
    *,
    scope: str = "main_closure",
    check_undefined_refs: bool = True,
) -> ProjectIndex:
    """填充 index.labels / index.refs。"""
    labels, refs, _ = build_refs_index(
        index,
        scope=scope,
        check_undefined_refs=check_undefined_refs,
    )
    return index.model_copy(update={"labels": labels, "refs": refs})


def collect_undefined_ref_issues(index: ProjectIndex) -> List[DiagnosticIssue]:
    """基于已填充的 labels/refs 生成未定义 ref 诊断。"""
    _, _, issues = build_refs_index(
        index,
        scope="main_closure",
        check_undefined_refs=True,
    )
    return issues
