"""
AST 解析：优先 pylatexenc，不可用时返回占位结构。
"""
from __future__ import annotations

from typing import Any, Dict, List


def _simplify_node(node: Any, *, depth: int = 0, max_depth: int = 6) -> Dict[str, Any]:
    if depth > max_depth:
        return {"type": "truncated"}
    name = type(node).__name__
    out: Dict[str, Any] = {"type": name}
    if hasattr(node, "pos") and node.pos is not None:
        out["pos"] = getattr(node.pos, "pos", None)
    if hasattr(node, "len") and node.len is not None:
        out["len"] = node.len
    if hasattr(node, "macro") and node.macro:
        out["macro"] = node.macro
    if hasattr(node, "environmentname") and node.environmentname:
        out["environment"] = node.environmentname
    if hasattr(node, "nodelist") and node.nodelist:
        out["children"] = [
            _simplify_node(ch, depth=depth + 1, max_depth=max_depth)
            for ch in node.nodelist[:40]
        ]
        if len(node.nodelist) > 40:
            out["children_truncated"] = len(node.nodelist) - 40
    return out


def parse_to_ast(source: str) -> Dict[str, Any]:
    try:
        from pylatexenc.latexwalker import LatexWalker
    except ImportError:
        return {
            "status": "unavailable",
            "reason": "pylatexenc 未安装；可执行 pip install pylatexenc",
        }

    try:
        walker = LatexWalker(source)
        nodelist, pos, length = walker.get_latex_nodes()
        return {
            "status": "ok",
            "parser": "pylatexenc",
            "root_span": {"pos": pos, "length": length},
            "nodes": [_simplify_node(n) for n in (nodelist or [])[:80]],
            "node_count": len(nodelist or []),
        }
    except Exception as e:  # noqa: BLE001
        return {
            "status": "error",
            "parser": "pylatexenc",
            "reason": f"{type(e).__name__}: {e}",
        }
