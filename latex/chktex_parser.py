"""
ChkTeX stdout 解析为 DiagnosticIssue（阶段 3）。
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional

from latex.constants import IssueSource, Severity
from latex.models import DiagnosticIssue
from latex.paths import normalize_rel_path

# -v0: File:Line:Column:Warning number:Warning message
_V0_RE = re.compile(
    r"^(?P<file>[^:]+):(?P<line>\d+):(?P<col>\d+):(?P<code>\d+):\s*(?P<message>.+)$"
)
# Warning 3 in paper.tex line 42: message
_V1_RE = re.compile(
    r"^Warning\s+(?P<code>\d+)\s+in\s+(?P<file>.+?)\s+line\s+(?P<line>\d+):\s*(?P<message>.+)$",
    re.IGNORECASE,
)
# "paper.tex", line 42: Warning 3: message  (lacheck / -v3)
_V3_RE = re.compile(
    r'^"(?P<file>[^"]+)"\s*,\s*line\s+(?P<line>\d+):\s*(?:Warning\s+(?P<code>\d+):\s*)?(?P<message>.+)$',
    re.IGNORECASE,
)
# chktex: WARNING -- path:line:col:col: Warning N: message
_PREFIX_RE = re.compile(
    r"chktex:\s*WARNING\s*--\s*"
    r"(?P<file>[^:]+):(?P<line>\d+):(?P<col>\d+):\d+:\s*"
    r"(?:Warning\s+(?P<code>\d+):\s*)?(?P<message>.+)$",
    re.IGNORECASE,
)
# Error N in file line L: message
_ERROR_RE = re.compile(
    r"^Error\s+(?P<code>\d+)\s+in\s+(?P<file>.+?)\s+line\s+(?P<line>\d+):\s*(?P<message>.+)$",
    re.IGNORECASE,
)


def _map_severity(message: str, code: str) -> Severity:
    lower = message.lower()
    if "error" in lower or code.startswith("e"):
        return Severity.ERROR
    if "info" in lower:
        return Severity.INFO
    return Severity.WARNING


def _normalize_file_path(raw: str, root: Optional[Path]) -> str:
    text = (raw or "").strip().strip('"')
    if not text:
        return "unknown"
    p = Path(text)
    if root is not None:
        try:
            if p.is_absolute():
                return p.resolve().relative_to(root.resolve()).as_posix()
            return normalize_rel_path(text)
        except ValueError:
            pass
    return normalize_rel_path(text.replace("\\", "/")) or text.replace("\\", "/")


def parse_chktex_output(
    text: str,
    *,
    root: Optional[Path] = None,
    default_file: str = "",
) -> List[DiagnosticIssue]:
    """将 chktex 合并后的 stdout+stderr 解析为 DiagnosticIssue 列表。"""
    issues: List[DiagnosticIssue] = []
    seen: set[tuple[str, int, int, str]] = set()

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("ChkTeX") and "Copyright" in line:
            continue

        parsed = _parse_line(line)
        if not parsed:
            continue

        file_raw, line_no, col, code, message = parsed
        rel_file = _normalize_file_path(file_raw, root) if file_raw else default_file
        if not rel_file:
            rel_file = default_file or "unknown"

        key = (rel_file, line_no, col, code)
        if key in seen:
            continue
        seen.add(key)

        issues.append(
            DiagnosticIssue.build(
                file=rel_file,
                line=line_no,
                column=col,
                message=message,
                source=IssueSource.CHKTEX,
                severity=_map_severity(message, code),
                code=code or "chktex",
            )
        )

    return issues


def _parse_line(line: str) -> Optional[tuple[str, int, int, str, str]]:
    for pattern, use_col in (
        (_V0_RE, True),
        (_PREFIX_RE, True),
        (_V1_RE, False),
        (_V3_RE, False),
        (_ERROR_RE, False),
    ):
        m = pattern.match(line)
        if not m:
            continue
        gd = m.groupdict()
        file_raw = gd.get("file", "") or ""
        line_no = int(gd.get("line") or 1)
        col = int(gd.get("col") or 0) if use_col and gd.get("col") else 0
        code = str(gd.get("code") or "").strip()
        message = (gd.get("message") or "").strip()
        return file_raw, line_no, col, code, message
    return None
