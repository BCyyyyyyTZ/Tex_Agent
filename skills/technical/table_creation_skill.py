# ============================================================
# skills/technical/table_creation_skill.py — 学术表格创建技能
# ============================================================
# 将结构化数据（CSV/JSON/dict）转换为符合学术规范的 LaTeX 表格：
# - 支持 booktabs 风格（\toprule/\midrule/\bottomrule）
# - 支持多列合并（\multicolumn）、粗体最优值
# - 自动添加 caption 和 label
# - 支持跨页长表格（longtable 环境）
# - 可选：生成配套的表格分析文字说明
#
# 输入: 数据（dict/CSV字符串）+ 列名 + 样式配置
# 输出: LaTeX 表格代码 + 可选的分析文字
# ============================================================

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class TableOutput:
    latex_table: str = ""
    caption: str = ""
    label: str = ""
    analysis_text: str = ""       # 对表格数据的文字分析（可选）
    is_long_table: bool = False


class TableCreationSkill:
    """
    学术表格创建技能。
    【需要实现】
    - execute(data, columns, caption, highlight_best, long_table) -> TableOutput
    - _format_booktabs(): 生成 booktabs 风格表格
    - _highlight_best_values(): 自动加粗最优指标值
    - _generate_analysis(): 调用 LLM 生成表格文字说明
    """
    async def execute(
        self,
        data: List[Dict[str, Any]],
        columns: List[str],
        caption: str = "",
        label: str = "",
        highlight_best: bool = True,
        generate_analysis: bool = False,
    ) -> TableOutput:
        """创建学术表格，【需要实现】"""
        pass
