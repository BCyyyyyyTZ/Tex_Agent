"""
LaTeX .log 解析为 DiagnosticIssue（阶段 4）。
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional

from latex.constants import IssueSource, Severity
from latex.models import DiagnosticIssue
from latex.paths import normalize_rel_path

_FILE_ENTER_RE = re.compile(r"^\(([^\(\)\s]+\.(?:tex|sty|cls|bbl|aux))")
_LINE_RE = re.compile(r"^l\.(\d+)\s*(.*)$")
_BANG_RE = re.compile(r"^!\s*(.+)$")
_FILE_LINE_RE = re.compile(
    r"^(?P<file>[^\s:]+\.(?:tex|sty|cls)):(?P<line>\d+):(?P<message>.+)$"
)
_LATEX_WARN_RE = re.compile(r"^LaTeX Warning:\s*(.+)$", re.IGNORECASE)
_UNDEF_REF_RE = re.compile(
    r"Reference\s+[`']([^`']+)[`'].*undefined|"
    r"undefined references|"
    r"Rerun to get cross-references right",
    re.IGNORECASE,
)
_UNDEF_CITE_RE = re.compile(
    r"Citation\s+[`']([^`']+)[`'].*undefined|"
    r"undefined citations|"
    r"There were undefined citations",
    re.IGNORECASE,
)
_REF_KEY_RE = re.compile(r"Reference\s+[`']([^`']+)[`']", re.IGNORECASE)
_CITE_KEY_RE = re.compile(r"Citation\s+[`']([^`']+)[`']", re.IGNORECASE)


def _normalize_log_file(raw: str, root: Optional[Path]) -> str:
    text = (raw or "").strip()
    if not text:
        return "unknown"
    # ./foo.tex or .\foo.tex
    if text.startswith("./"):
        text = text[2:]
    if text.startswith(".\\"):
        text = text[2:]
    p = Path(text.replace("\\", "/"))
    if root is not None:
        try:
            if p.is_absolute():
                return p.resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            pass
    norm = normalize_rel_path(text)
    return norm or text.replace("\\", "/")


def _append_issue(
    issues: List[DiagnosticIssue],
    seen: set[tuple[str, int, str, str]],
    *,
    file: str,
    line: int,
    message: str,
    severity: Severity,
    code: str = "",
    column: int = 0,
) -> None:
    key = (file, line, message[:80], severity.value)
    if key in seen:
        return
    seen.add(key)
    issues.append(
        DiagnosticIssue.build(
            file=file,
            line=max(1, line),
            column=column,
            message=message,
            source=IssueSource.LATEXMK,
            severity=severity,
            code=code or "latexmk",
        )
    )


def parse_latex_log(
    text: str,
    *,
    root: Optional[Path] = None,
    default_file: str = "",
) -> List[DiagnosticIssue]:
    """
    从 latexmk / pdflatex 生成的 .log 提取错误与常见引用/文献警告。
    """
    issues: List[DiagnosticIssue] = []
    seen: set[tuple[str, int, str, str]] = set()
    current_file = default_file
    pending_error: Optional[str] = None

    lines = text.splitlines()
    i = 0
    while i < len(lines):
        raw = lines[i]
        line = raw.rstrip()
        i += 1

        m_file_line = _FILE_LINE_RE.match(line)
        if m_file_line:
            rel = _normalize_log_file(m_file_line.group("file"), root)
            _append_issue(
                issues,
                seen,
                file=rel,
                line=int(m_file_line.group("line")),
                message=m_file_line.group("message").strip(),
                severity=Severity.ERROR,
                code="file_line",
            )
            pending_error = None
            continue

        m_enter = _FILE_ENTER_RE.match(line)
        if m_enter:
            current_file = _normalize_log_file(m_enter.group(1), root) or current_file
            continue

        m_bang = _BANG_RE.match(line)
        if m_bang:
            pending_error = m_bang.group(1).strip()
            # 向后查找 l.N
            for j in range(i, min(i + 8, len(lines))):
                m_line = _LINE_RE.match(lines[j].rstrip())
                if m_line:
                    rel = current_file or default_file or "unknown"
                    msg = pending_error
                    extra = m_line.group(2).strip()
                    if extra:
                        msg = f"{msg} ({extra})"
                    _append_issue(
                        issues,
                        seen,
                        file=rel,
                        line=int(m_line.group(1)),
                        message=msg,
                        severity=Severity.ERROR,
                        code="bang",
                    )
                    pending_error = None
                    break
            if pending_error:
                _append_issue(
                    issues,
                    seen,
                    file=current_file or default_file or "unknown",
                    line=1,
                    message=pending_error,
                    severity=Severity.ERROR,
                    code="bang",
                )
                pending_error = None
            continue

        m_line_only = _LINE_RE.match(line)
        if m_line_only and pending_error:
            rel = current_file or default_file or "unknown"
            _append_issue(
                issues,
                seen,
                file=rel,
                line=int(m_line_only.group(1)),
                message=pending_error,
                severity=Severity.ERROR,
                code="bang",
            )
            pending_error = None
            continue

        m_warn = _LATEX_WARN_RE.match(line)
        if m_warn:
            msg = m_warn.group(1).strip()
            rel = current_file or default_file or "unknown"
            if _UNDEF_REF_RE.search(msg):
                key_m = _REF_KEY_RE.search(msg)
                code = "undefined_reference"
                if key_m:
                    msg = f"未定义引用: \\ref{{{key_m.group(1)}}} ({msg})"
                _append_issue(
                    issues,
                    seen,
                    file=rel,
                    line=1,
                    message=msg,
                    severity=Severity.WARNING,
                    code=code,
                )
            elif _UNDEF_CITE_RE.search(msg):
                key_m = _CITE_KEY_RE.search(msg)
                code = "undefined_citation"
                if key_m:
                    msg = f"未定义文献: \\cite{{{key_m.group(1)}}} ({msg})"
                _append_issue(
                    issues,
                    seen,
                    file=rel,
                    line=1,
                    message=msg,
                    severity=Severity.WARNING,
                    code=code,
                )
            continue

        if "undefined references" in line.lower():
            _append_issue(
                issues,
                seen,
                file=current_file or default_file or "unknown",
                line=1,
                message=line.strip(),
                severity=Severity.WARNING,
                code="undefined_references",
            )
        if "undefined citations" in line.lower() or "there were undefined citations" in line.lower():
            _append_issue(
                issues,
                seen,
                file=current_file or default_file or "unknown",
                line=1,
                message=line.strip(),
                severity=Severity.WARNING,
                code="undefined_citations",
            )

    return issues


def tail_log_text(text: str, *, max_lines: int = 50) -> str:
    """返回 log 末尾若干行，供 Tool 输出 log_tail。"""
    lines = text.splitlines()
    if len(lines) <= max_lines:
        return text
    return "\n".join(lines[-max_lines:])
