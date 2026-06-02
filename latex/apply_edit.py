"""
将 Suggestion 应用到磁盘上的 .tex 文件（幽灵窗口 / 扩展共用）。
"""
from __future__ import annotations

from pathlib import Path
from typing import Union

from latex.models import Suggestion
from latex.paths import normalize_rel_path
from latex.serialize import from_dict


def offset_from_position(text: str, line: int, character: int) -> int:
    """0-based line/character → 字节偏移（UTF-8 按 str 索引）。"""
    lines = text.splitlines(keepends=True)
    if not lines:
        return 0
    line = max(0, min(line, len(lines) - 1))
    line_start = sum(len(lines[i]) for i in range(line))
    line_len = len(lines[line])
    char = max(0, min(character, line_len))
    return min(line_start + char, len(text))


def apply_suggestion_to_file(
    root: Union[str, Path],
    suggestion: Union[Suggestion, dict],
    *,
    encoding: str = "utf-8",
) -> Path:
    """
    用 replacement 替换 suggestion.range 所指区域并写回文件。

    返回写入的绝对路径。
    """
    if isinstance(suggestion, dict):
        sug = from_dict(Suggestion, suggestion)
    else:
        sug = suggestion

    root_path = Path(root).expanduser().resolve()
    rel = normalize_rel_path(sug.file)
    target = root_path / rel
    if not target.is_file():
        raise FileNotFoundError(f"目标文件不存在: {rel}")

    text = target.read_text(encoding=encoding, errors="replace")
    start_off = offset_from_position(
        text, sug.range.start.line, sug.range.start.character
    )
    end_off = offset_from_position(
        text, sug.range.end.line, sug.range.end.character
    )
    if end_off < start_off:
        start_off, end_off = end_off, start_off

    new_text = text[:start_off] + sug.replacement + text[end_off:]
    target.write_text(new_text, encoding=encoding)
    return target
