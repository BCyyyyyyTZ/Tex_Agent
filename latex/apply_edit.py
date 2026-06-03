"""
将 Suggestion 应用到磁盘上的 .tex 文件（幽灵窗口 / 扩展共用）。
"""
from __future__ import annotations

from pathlib import Path
from typing import Union

from latex.models import Suggestion
from latex.paths import normalize_rel_path
from latex.serialize import from_dict


class SuggestionRangeError(ValueError):
    """Suggestion 的 range 越界或非法。"""


def _split_lines_keepends(text: str) -> list[str]:
    if text == "":
        return []
    lines = text.splitlines(keepends=True)
    return lines if lines else [text]


def _line_visible_len(line_text: str) -> int:
    return len(line_text.rstrip("\r\n"))


def offset_from_position(text: str, line: int, character: int) -> int:
    """0-based line/character → 文本偏移。"""
    if line < 0 or character < 0:
        raise SuggestionRangeError("range 含负数位置")
    lines = _split_lines_keepends(text)
    if not lines:
        if line == 0 and character == 0:
            return 0
        raise SuggestionRangeError(f"空文件不支持位置 line={line}, char={character}")
    if line >= len(lines):
        raise SuggestionRangeError(
            f"range 行号越界: line={line}, 最大可用={len(lines) - 1}"
        )

    line_start = sum(len(lines[i]) for i in range(line))
    visible_len = _line_visible_len(lines[line])
    char = min(character, visible_len)
    return min(line_start + char, len(text))


def sanitize_replacement_text(text: str) -> str:
    """
    清理常见控制字符，避免应用后出现 BOM/乱码前缀。
    """
    return (text or "").replace("\ufeff", "").replace("\x00", "")


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
    start_off = offset_from_position(text, sug.range.start.line, sug.range.start.character)
    end_off = offset_from_position(text, sug.range.end.line, sug.range.end.character)
    if end_off < start_off:
        start_off, end_off = end_off, start_off

    replacement = sanitize_replacement_text(sug.replacement)
    new_text = text[:start_off] + replacement + text[end_off:]
    target.write_text(new_text, encoding=encoding)
    return target
