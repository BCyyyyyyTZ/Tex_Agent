# ============================================================
# skills/academic/abstract_writing_skill.py — 摘要撰写技能
# ============================================================
# 根据论文全文或关键信息，生成符合学术规范的摘要。
# 遵循 IMRaD 结构：背景/目的 → 方法 → 结果 → 结论。
# 支持多种长度（150/250/500字）和语言（中/英文）。
#
# 输入: 论文内容/大纲/关键贡献点 + 目标长度 + 语言
# 输出: 摘要正文 + 关键词列表（5-8个）
# ============================================================

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List


@dataclass
class AbstractOutput:
    abstract_text: str = ""
    keywords: List[str] = field(default_factory=list)
    word_count: int = 0
    language: str = "en"


class AbstractWritingSkill:
    """
    摘要撰写技能。
    【需要实现】
    - execute(paper_content, length, language) -> AbstractOutput
    - _extract_key_contributions(): 提取核心贡献
    - _generate_abstract(): 调用 LLM 生成摘要
    - _extract_keywords(): 提取关键词
    - _validate_structure(): 验证 IMRaD 结构完整性
    """
    async def execute(
        self,
        paper_content: str,
        target_length: int = 250,
        language: str = "en",
    ) -> AbstractOutput:
        """生成摘要，【需要实现】"""
        pass
