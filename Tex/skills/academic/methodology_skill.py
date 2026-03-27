# ============================================================
# skills/academic/methodology_skill.py — 方法论章节撰写技能
# ============================================================
# 生成论文方法论/模型章节，包含：
# - 问题形式化定义（数学符号/公式）
# - 模型架构描述（可触发 TikZGenerator 生成框图）
# - 算法伪代码（algorithm2e 格式）
# - 实现细节说明
#
# 输入: 方法描述（自然语言）+ 是否生成图表
# 输出: 方法论正文（LaTeX）+ 可选的 TikZ 图/算法代码
# ============================================================

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class MethodologyOutput:
    methodology_text_latex: str = ""
    equations: List[str] = field(default_factory=list)        # LaTeX 公式列表
    algorithm_code: str = ""                                   # algorithm2e 伪代码
    tikz_diagram: Optional[str] = None                        # 可选架构图 TikZ 代码
    figure_latex: str = ""


class MethodologySkill:
    """
    方法论章节撰写技能。
    【需要实现】
    - execute(method_description, generate_diagram, add_algorithm) -> MethodologyOutput
    - _formalize_problem(): 生成数学形式化定义
    - _describe_architecture(): 撰写模型架构说明
    - _generate_pseudocode(): 生成算法伪代码（algorithm2e）
    - _generate_diagram(): 调用 TikZGenerator 生成框图
    """
    async def execute(
        self,
        method_description: str,
        generate_diagram: bool = False,
        add_algorithm: bool = False,
    ) -> MethodologyOutput:
        """生成方法论章节，【需要实现】"""
        pass
