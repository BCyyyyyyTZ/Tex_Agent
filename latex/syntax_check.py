"""
轻量级 LaTeX 语法检查：括号配对、\\begin/\\end 环境配对（阶段 2 MVP）。
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List

from latex.tex_source import strip_comments

_ENV_BEGIN_RE = re.compile(r"\\begin\s*\{([^}]+)\}", re.IGNORECASE)
_ENV_END_RE = re.compile(r"\\end\s*\{([^}]+)\}", re.IGNORECASE)


@dataclass
class RawSyntaxIssue:
    line: int
    column: int
    message: str
    severity: str = "error"


def check_brace_balance(source: str) -> List[RawSyntaxIssue]:
    """检查 { } 是否配对（忽略注释与简单转义）。"""
    active = strip_comments(source)
    issues: List[RawSyntaxIssue] = []
    stack: List[tuple[int, int]] = []
    line = 1
    col = 0
    i = 0
    escaped = False
    while i < len(active):
        ch = active[i]
        if ch == "\n":
            line += 1
            col = 0
            escaped = False
            i += 1
            continue
        col += 1
        if escaped:
            escaped = False
            i += 1
            continue
        if ch == "\\":
            escaped = True
            i += 1
            continue
        if ch == "{":
            stack.append((line, col))
        elif ch == "}":
            if not stack:
                issues.append(
                    RawSyntaxIssue(
                        line=line,
                        column=col,
                        message="多余的右花括号 '}'",
                        severity="error",
                    )
                )
            else:
                stack.pop()
        i += 1
    for ln, cl in stack:
        issues.append(
            RawSyntaxIssue(
                line=ln,
                column=cl,
                message="未闭合的左花括号 '{'",
                severity="error",
            )
        )
    return issues


def _match_line_col(active: str, pos: int) -> tuple[int, int]:
    line = active[:pos].count("\n") + 1
    last_nl = active.rfind("\n", 0, pos)
    col = pos - last_nl if last_nl >= 0 else pos + 1
    return line, col


def check_environment_balance(source: str) -> List[RawSyntaxIssue]:
    """按文档顺序检查 \\begin{env} / \\end{env} 是否匹配。"""
    active = strip_comments(source)
    issues: List[RawSyntaxIssue] = []
    stack: List[tuple[str, int, int]] = []

    events: list[tuple[int, str, str, re.Match[str]]] = []
    for match in _ENV_BEGIN_RE.finditer(active):
        events.append((match.start(), "begin", match.group(1).strip(), match))
    for match in _ENV_END_RE.finditer(active):
        events.append((match.start(), "end", match.group(1).strip(), match))
    events.sort(key=lambda x: x[0])

    for _pos, kind, env, match in events:
        line, col = _match_line_col(active, match.start())
        if kind == "begin":
            stack.append((env, line, col))
        elif not stack:
            issues.append(
                RawSyntaxIssue(
                    line=line,
                    column=col,
                    message=f"\\end{{{env}}} 没有对应的 \\begin",
                    severity="error",
                )
            )
        else:
            top, bl, bc = stack.pop()
            if top != env:
                issues.append(
                    RawSyntaxIssue(
                        line=line,
                        column=col,
                        message=(
                            f"环境不匹配：\\end{{{env}}} 与 "
                            f"\\begin{{{top}}}（约 {bl}:{bc}）不对应"
                        ),
                        severity="error",
                    )
                )
    for env, ln, cl in reversed(stack):
        issues.append(
            RawSyntaxIssue(
                line=ln,
                column=cl,
                message=f"未闭合的环境 \\begin{{{env}}}",
                severity="error",
            )
        )
    return issues


def check_syntax(source: str) -> List[RawSyntaxIssue]:
    issues = check_brace_balance(source)
    issues.extend(check_environment_balance(source))
    return issues
