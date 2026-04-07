# ============================================================
# skills/technical/code_listing_skill.py — 代码展示技能
# ============================================================
# 将代码片段格式化为 LaTeX listings/minted 环境，
# 添加语法高亮、行号、代码注释、caption 等学术规范格式。
# 支持代码简化（删除非关键实现细节，突出核心逻辑）。
#
# 输入: 代码字符串 + 编程语言 + 展示风格
# 输出: LaTeX listings 代码块
# ============================================================

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


@dataclass
class CodeListingOutput:
    latex_listing: str = ""
    language_detected: str = ""
    simplified_code: str = ""     # 简化后的代码（去除非关键细节）


class CodeListingSkill:
    """
    代码展示格式化技能。
    【需要实现】
    - execute(code, language, caption, add_line_numbers, simplify) -> CodeListingOutput
    - _detect_language(): 自动检测编程语言
    - _simplify_code(): 调用 LLM 简化代码（保留核心逻辑）
    - _format_listing(): 生成 listings/minted LaTeX 代码
    """
    async def execute(
        self,
        code: str,
        language: Optional[str] = None,
        caption: str = "",
        add_line_numbers: bool = True,
        simplify: bool = False,
    ) -> CodeListingOutput:
        """格式化代码展示，【需要实现】"""
        pass
