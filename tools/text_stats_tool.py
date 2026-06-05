"""文本统计：字数、词数、阅读时间与写作密度分析（纯规则，不调用 LLM）。"""
from __future__ import annotations

import re
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.message import ToolResult
from tools.base_tool import BaseTool


class TextStatsTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="text_stats",
            description="统计文本字数、词数、句数、阅读时间与写作密度。",
            input_schema={"text": "待分析文本"},
        )

    def _avg_word_len_en(self, text: str, en_words: int) -> float:
        if en_words <= 0:
            return 0.0
        tokens = re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?", text)
        return sum(len(t) for t in tokens) / en_words

    def run(self, text: str = "") -> ToolResult:
        t = text or ""
        if not t.strip():
            return ToolResult(success=False, output="", error="text 不能为空")

        chars = len(t)
        chars_no_space = len(re.sub(r"\s", "", t))
        cn_chars = len(re.findall(r"[\u4e00-\u9fff]", t))
        en_words = len(re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?", t))
        digits = len(re.findall(r"\d", t))
        lines = len([ln for ln in t.splitlines() if ln.strip()])
        paragraphs = max(1, len([p for p in re.split(r"\n\s*\n", t.strip()) if p.strip()]))

        # 句数：中英文标点
        sents = re.split(r"(?<=[.!?。！？…])\s+", t.strip())
        sentences = max(1, len([s for s in sents if s.strip()]))

        # 阅读速度：中文 ~350 字/分；英文 ~220 词/分（学术略慢）
        read_min = cn_chars / 350.0 + en_words / 220.0
        read_min = max(0.1, read_min)
        avg_sent_len = (cn_chars + en_words) / sentences
        avg_word_len = self._avg_word_len_en(t, en_words)

        # 写作密度提示
        if cn_chars > en_words * 3:
            lang_hint = "以中文为主"
        elif en_words > cn_chars:
            lang_hint = "以英文为主"
        else:
            lang_hint = "中英混合"

        summary_lines = [
            "── 基础统计 ──",
            f"总字符：{chars}（不含空白 {chars_no_space}）",
            f"中文汉字：{cn_chars}",
            f"英文词数：{en_words}",
            f"数字字符：{digits}",
            f"行数：{lines} · 段落：{paragraphs}",
            "",
            "── 结构 ──",
            f"句数（约）：{sentences}",
            f"平均句长：{avg_sent_len:.1f} 字/词",
            f"英文平均词长：{avg_word_len:.1f} 字符" if en_words else "英文平均词长：—",
            "",
            "── 阅读预估 ──",
            f"语言构成：{lang_hint}",
            f"阅读时间：约 {read_min:.1f} 分钟",
        ]

        # 摘要/正文长度参考
        if cn_chars + en_words < 150:
            summary_lines.append("篇幅：短文本（如摘要草稿、段落级）")
        elif cn_chars + en_words < 800:
            summary_lines.append("篇幅：中等（如 Introduction 单节）")
        else:
            summary_lines.append("篇幅：较长（接近章节或多段正文）")

        summary = "\n".join(summary_lines)
        return ToolResult(
            success=True,
            output=summary,
            metadata={
                "chars": chars,
                "chars_no_space": chars_no_space,
                "cn_chars": cn_chars,
                "en_words": en_words,
                "digits": digits,
                "lines": lines,
                "sentences": sentences,
                "paragraphs": paragraphs,
                "reading_minutes": round(read_min, 2),
                "language_hint": lang_hint,
                "mode": "rule-based",
            },
        )
