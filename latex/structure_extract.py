"""
单文件结构提取：章节、label、图表环境（阶段 2 MVP，基于逐行扫描）。
"""
from __future__ import annotations

import re
from typing import Any, Dict, List

from latex.tex_source import strip_inline_comment

_SECTION_RE = re.compile(
    r"\\(chapter|section|subsection|subsubsection|paragraph|subparagraph)"
    r"\*?(?:\[[^\]]*\])?\s*\{([^}]*)\}",
    re.IGNORECASE,
)
_LABEL_RE = re.compile(r"\\label\s*\{([^}]+)\}", re.IGNORECASE)
_REF_RE = re.compile(
    r"\\(?:ref|eqref|pageref|autoref|nameref|cref|Cref)\s*\*?"
    r"(?:\[[^\]]*\])?\s*\{([^}]+)\}",
    re.IGNORECASE,
)
_BEGIN_FIG_RE = re.compile(
    r"\\begin\s*\{(figure\*?|table\*?)\}",
    re.IGNORECASE,
)
_CITE_RE = re.compile(r"\\cite\w*\s*\{([^}]+)\}", re.IGNORECASE)


_SECTION_LEVEL = {
    "chapter": 0,
    "section": 1,
    "subsection": 2,
    "subsubsection": 3,
    "paragraph": 4,
    "subparagraph": 5,
}


def extract_structure(source: str) -> Dict[str, Any]:
    sections: List[Dict[str, Any]] = []
    labels: List[Dict[str, Any]] = []
    refs: List[Dict[str, Any]] = []
    figures: List[Dict[str, Any]] = []
    citations: List[str] = []
    cite_seen: set[str] = set()
    ref_seen: set[tuple[str, int, str]] = set()

    for line_no, raw_line in enumerate(source.splitlines(), start=1):
        line = strip_inline_comment(raw_line)
        if not line.strip():
            continue

        sec = _SECTION_RE.search(line)
        if sec:
            kind = sec.group(1).lower()
            title = sec.group(2).strip()
            sections.append(
                {
                    "title": title,
                    "level": _SECTION_LEVEL.get(kind, 1),
                    "kind": kind,
                    "start_line": line_no,
                }
            )

        for lab in _LABEL_RE.finditer(line):
            labels.append({"label": lab.group(1).strip(), "line": line_no})

        for ref in _REF_RE.finditer(line):
            for key in [k.strip() for k in ref.group(1).split(",") if k.strip()]:
                sig = (key, line_no, "ref")
                if sig not in ref_seen:
                    ref_seen.add(sig)
                    refs.append({"key": key, "line": line_no, "kind": "ref"})

        fig = _BEGIN_FIG_RE.search(line)
        if fig:
            figures.append({"environment": fig.group(1).lower(), "start_line": line_no})

        for cite in _CITE_RE.finditer(line):
            keys = [k.strip() for k in cite.group(1).split(",") if k.strip()]
            for key in keys:
                if key not in cite_seen:
                    cite_seen.add(key)
                    citations.append(key)
                sig = (key, line_no, "cite")
                if sig not in ref_seen:
                    ref_seen.add(sig)
                    refs.append({"key": key, "line": line_no, "kind": "cite"})

    return {
        "sections": sections,
        "labels": labels,
        "refs": refs,
        "figures": figures,
        "citations": citations,
    }
