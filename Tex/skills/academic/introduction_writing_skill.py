# ============================================================
# skills/academic/introduction_writing_skill.py — 引言撰写技能
# ============================================================
# 遵循"倒金字塔"结构生成引言：
# 1. 宏观背景（领域重要性）
# 2. 问题陈述（现有方法的不足）
# 3. 研究动机（为何要解决该问题）
# 4. 本文贡献（Contribution 列表）
# 5. 论文结构说明（The rest of the paper is organized as...）
#
# 输入: 研究问题 + 贡献点 + 相关工作摘要
# 输出: 引言正文（LaTeX 格式）
# ============================================================

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List


@dataclass
class IntroductionOutput:
    intro_text_latex: str = ""
    contribution_list: List[str] = field(default_factory=list)
    word_count: int = 0


class IntroductionWritingSkill:
    """
    引言撰写技能。
    【需要实现】
    - execute(research_problem, contributions, related_work_summary) -> IntroductionOutput
    - _build_background(): 生成背景段
    - _state_problem(): 陈述问题
    - _list_contributions(): 格式化贡献点列表
    - _outline_paper_structure(): 生成论文结构说明
    """
    async def execute(
        self,
        research_problem: str,
        contributions: List[str],
        related_work_summary: str = "",
    ) -> IntroductionOutput:
        """生成引言，【需要实现】"""
        pass
