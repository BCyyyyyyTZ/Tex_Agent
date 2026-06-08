"""
单文件 LaTeX 解析编排（结构 + 语法 + AST）。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from latex.ast_parse import parse_to_ast
from latex.paths import resolve_tex_file
from latex.structure_extract import extract_structure
from latex.syntax_check import RawSyntaxIssue, check_syntax
from latex.tex_source import read_tex_file


def parse_tex_source(
    source: str,
    *,
    rel_path: str = "",
) -> Dict[str, Any]:
    """对已读入的源码做结构/语法/AST 分析。"""
    structure = extract_structure(source)
    raw_issues = check_syntax(source)
    ast = parse_to_ast(source)
    return {
        "rel_path": rel_path,
        "structure": structure,
        "syntax_issues": [
            {
                "line": i.line,
                "column": i.column,
                "message": i.message,
                "severity": i.severity,
            }
            for i in raw_issues
        ],
        "ast": ast,
    }


def parse_tex_file(
    *,
    path: Optional[str] = None,
    root: Optional[str] = None,
    rel_path: Optional[str] = None,
    base_dir: Optional[str | Path] = None,
) -> Dict[str, Any]:
    """
    从磁盘读取并解析单个 .tex（路径解析兼容 Windows / Linux）。
    """
    abs_path, rel = resolve_tex_file(
        path=path,
        root=root,
        rel_path=rel_path,
        base_dir=base_dir,
    )
    source = read_tex_file(abs_path)
    rel_str = rel or rel_path or normalize_display_rel(abs_path)
    out = parse_tex_source(source, rel_path=rel_str)
    out["path"] = str(abs_path)
    out["root"] = str(root) if root else None
    return out


def normalize_display_rel(abs_path: Path) -> str:
    return abs_path.name


def raw_issues_to_dicts(issues: List[RawSyntaxIssue]) -> List[Dict[str, Any]]:
    return [
        {
            "line": i.line,
            "column": i.column,
            "message": i.message,
            "severity": i.severity,
        }
        for i in issues
    ]
