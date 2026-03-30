# ============================================================
# skills/analytical/result_interpretation_skill.py — 结果解释技能
# ============================================================
# 将统计数字/实验结果转换为学术写作中规范的文字解释，
# 包括：统计意义说明、与基线对比分析、消融实验解读。
# 避免常见错误（如混淆统计显著性与实际意义）。
#
# 输入: 统计检验结果对象 / 实验指标数据
# 输出: 学术规范的结果解读段落 + 潜在问题警告
# ============================================================

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class InterpretationOutput:
    interpretation_text: str = ""     # 结果解读文字
    warnings: List[str] = field(default_factory=list)  # 潜在问题警告
    apa_formatted_results: str = ""   # APA 格式统计结果


class ResultInterpretationSkill:
    """
    实验结果解释技能。
    【需要实现】
    - execute(results, context) -> InterpretationOutput
    - _interpret_statistics(): 解释统计检验结果
    - _compare_baselines(): 与基线方法对比分析
    - _analyze_ablation(): 消融实验分析
    - _check_common_mistakes(): 检查常见统计错误
    """
    async def execute(
        self, results: Any, context: str = ""
    ) -> InterpretationOutput:
        """解释实验结果，【需要实现】"""
        pass
