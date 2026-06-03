"""
将 Suggestion 以“对比模式”应用到 .tex 文件：
- 原文范围转为注释保留
- 新建议文本紧随其后写入正文
"""
from __future__ import annotations

from pathlib import Path
from typing import Union

from latex.apply_edit import (
    SuggestionRangeError,
    offset_from_position,
    sanitize_replacement_text,
)
from latex.models import Suggestion
from latex.paths import normalize_rel_path
from latex.serialize import from_dict


def _to_latex_comment_block(text: str) -> str:
    if text == "":
        return "% [TeX_Agent][compare] (empty)\n"
    lines = text.splitlines()
    if not lines:
        lines = [text]
    commented = ["% [TeX_Agent][compare] " + line for line in lines]
    # 保证注释块后换行，再接 replacement 正文
    return "\n".join(commented) + "\n"


def apply_suggestion_compare_to_file(
    root: Union[str, Path],
    suggestion: Union[Suggestion, dict],
    *,
    encoding: str = "utf-8",
) -> Path:
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
    if start_off > len(text) or end_off > len(text):
        raise SuggestionRangeError("range 偏移越界")

    original = text[start_off:end_off]
    replacement = sanitize_replacement_text(sug.replacement)
    comment_block = _to_latex_comment_block(original)
    inserted = comment_block + replacement
    if replacement and not replacement.endswith("\n"):
        inserted += "\n"

    new_text = text[:start_off] + inserted + text[end_off:]
    target.write_text(new_text, encoding=encoding)
    return target
