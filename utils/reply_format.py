"""助手回复展示前的文本整理（去引用垃圾、合并碎段落，保留 Markdown/章节结构）。"""
from __future__ import annotations

import re

# OpenAI / 部分代理返回的私有区引用标记，如 cite turn0search0
_CITATION_ARTIFACT_RE = re.compile(
    r"[\uE000-\uF8FF]*"
    r"cite"
    r"[\uE000-\uF8FF]*"
    r"(?:turn\d+search\d+[\uE000-\uF8FF]*)+",
    re.IGNORECASE,
)
_CITATION_ARTIFACT_ASCII_RE = re.compile(
    r"\s*cite\s*turn\d+search\d+(?:\s*turn\d+search\d+)*\s*",
    re.IGNORECASE,
)

# 中文章节标题行
_SECTION_HEADER_RE = re.compile(
    r"^(【|[一二三四五六七八九十百千]+[、．.]|第[一二三四五六七八九十\d]+[章节部分])"
)

# Markdown / 列表 / 引用 / 围栏
_MD_STRUCTURAL_RE = re.compile(
    r"^(?:#{1,6}\s|[-*+]\s+|\d+\.\s+|>\s?|```|~~~|\*\*[^*]+\*\*\s*$)"
)

# 在长段无换行文本中，于章节/标题前插入分段
_INSERT_BREAK_BEFORE_RE = re.compile(
    r"(?<=\S)\s+("
    r"#{1,6}\s|"
    r"[一二三四五六七八九十百千]+[、．.]|"
    r"第[一二三四五六七八九十\d]+[章节部分]"
    r")"
)


def strip_citation_artifacts(text: str) -> str:
    if not text:
        return ""
    out = _CITATION_ARTIFACT_RE.sub("", text)
    out = _CITATION_ARTIFACT_ASCII_RE.sub(" ", out)
    return re.sub(r"[ \t]{2,}", " ", out)


def _is_structural_line(line: str, *, short_para_chars: int) -> bool:
    s = line.strip()
    if not s:
        return False
    if _MD_STRUCTURAL_RE.match(s):
        return True
    if _SECTION_HEADER_RE.match(s):
        return True
    if len(s) >= short_para_chars:
        return True
    return False


def _insert_breaks_in_dense_text(text: str) -> str:
    """极少量换行时，在可见章节/Markdown 标题前补空行。"""
    if not text or text.count("\n") >= max(8, len(text) // 400):
        return text
    return _INSERT_BREAK_BEFORE_RE.sub(r"\n\n\1", text)


def _merge_block_lines(block: str, *, short_para_chars: int) -> list[str]:
    """同一段落块内：合并碎短句，保留标题/列表行独立成段。"""
    paragraphs: list[str] = []
    buf: list[str] = []

    def flush_buf() -> None:
        if buf:
            paragraphs.append(" ".join(buf))
            buf.clear()

    for line in block.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        if _is_structural_line(stripped, short_para_chars=short_para_chars):
            flush_buf()
            paragraphs.append(stripped)
        else:
            buf.append(stripped)
    flush_buf()
    return paragraphs


def normalize_reply_display(text: str, *, short_para_chars: int = 100) -> str:
    """
    合并「一句一段」的碎行，同时保留 Markdown 标题、列表与中文章节。
    空行分段；同一块内的连续短句合并为一段（不再全局把 \\n 压成空格）。
    """
    out = strip_citation_artifacts(str(text or ""))
    out = out.replace("\r\n", "\n").replace("\r", "\n")
    out = _insert_breaks_in_dense_text(out)
    out = re.sub(r"\n{3,}", "\n\n", out).strip()
    if not out:
        return ""

    raw_blocks = [b.strip() for b in re.split(r"\n\s*\n", out) if b.strip()]
    merged_blocks: list[str] = []
    short_buf: list[str] = []

    def flush_short_buf() -> None:
        if short_buf:
            merged_blocks.append("\n".join(short_buf))
            short_buf.clear()

    def block_is_mergeable(block: str) -> bool:
        lines = [ln.strip() for ln in block.split("\n") if ln.strip()]
        if not lines:
            return False
        return all(
            not _is_structural_line(ln, short_para_chars=short_para_chars)
            and len(ln) < short_para_chars
            for ln in lines
        )

    for block in raw_blocks:
        if block_is_mergeable(block):
            short_buf.append(block)
        else:
            flush_short_buf()
            merged_blocks.append(block)
    flush_short_buf()

    paragraphs: list[str] = []
    for block in merged_blocks:
        paragraphs.extend(_merge_block_lines(block, short_para_chars=short_para_chars))

    return "\n\n".join(paragraphs)


def format_reply_for_ui(text: str) -> str:
    return normalize_reply_display(text)
