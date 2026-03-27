# ============================================================
# skills/technical/algorithm_description_skill.py — 算法描述技能
# ============================================================
# 将算法的自然语言描述或代码转换为 algorithm2e/algorithmic 格式的
# LaTeX 伪代码，并生成配套的文字说明段落。
#
# 输入: 算法描述（自然语言或 Python 代码）+ 目标格式
# 输出: 伪代码 LaTeX 代码 + 算法说明段落
# ============================================================

from __future__ import annotations
from dataclasses import dataclass


@dataclass
class AlgorithmOutput:
    pseudocode_latex: str = ""      # algorithm2e 格式伪代码
    description_text: str = ""     # 配套的算法说明段落
    complexity_analysis: str = ""  # 时间/空间复杂度分析（可选）


class AlgorithmDescriptionSkill:
    """
    算法描述与伪代码生成技能。
    【需要实现】
    - execute(algorithm_input, format, add_complexity) -> AlgorithmOutput
    - _generate_pseudocode(): 调用 LLM 生成标准化伪代码
    - _analyze_complexity(): 分析时空复杂度
    - _write_description(): 撰写算法说明段落
    """
    async def execute(
        self,
        algorithm_input: str,
        format: str = "algorithm2e",   # algorithm2e / algorithmic
        add_complexity: bool = False,
    ) -> AlgorithmOutput:
        """生成算法伪代码，【需要实现】"""
        pass
