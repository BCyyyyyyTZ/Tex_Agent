# ============================================================
# skills/academic/conclusion_skill.py — 结论章节撰写技能
# ============================================================
# 生成论文结论章节，包含：
# - 研究工作总结（回顾核心贡献）
# - 研究局限性诚实陈述
# - 未来研究方向展望
# - 可选的 broader impact 声明
#
# 输入: 贡献列表 + 实验结果摘要 + 局限性说明
# 输出: 结论正文（LaTeX 格式）
# ============================================================

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List


@dataclass
class ConclusionOutput:
    conclusion_text_latex: str = ""
    limitations: List[str] = field(default_factory=list)
    future_works: List[str] = field(default_factory=list)
    word_count: int = 0


class ConclusionSkill:
    """
    结论撰写技能。
    【需要实现】
    - execute(contributions, results_summary, limitations, future_directions) -> ConclusionOutput
    - _summarize_contributions(): 总结贡献
    - _state_limitations(): 陈述局限性
    - _suggest_future_works(): 展望未来工作
    """
    async def execute(
        self,
        contributions: List[str],
        results_summary: str,
        limitations: List[str] = [],
        future_directions: List[str] = [],
    ) -> ConclusionOutput:
        """生成结论章节，【需要实现】"""
        pass
