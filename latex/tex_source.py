"""
读取 .tex 与注释处理（供语法检查 / 结构提取）。
"""
from __future__ import annotations

from pathlib import Path


def strip_inline_comment(line: str) -> str:
    """去掉行内未转义的 % 注释，保留换行前的有效内容。"""
    i = 0
    while i < len(line):
        ch = line[i]
        if ch == "%":
            backslashes = 0
            j = i - 1
            while j >= 0 and line[j] == "\\":
                backslashes += 1
                j -= 1
            if backslashes % 2 == 0:
                return line[:i].rstrip()
        i += 1
    return line.rstrip()


def strip_comments(source: str) -> str:
    """按行去掉 % 注释，保留换行结构。"""
    return "\n".join(strip_inline_comment(ln) for ln in source.splitlines()) + (
        "\n" if source.endswith("\n") else ""
    )


def read_tex_file(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")
