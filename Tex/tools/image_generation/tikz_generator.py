# ============================================================
# tools/image_generation/tikz_generator.py
# TikZGenerator —— LaTeX TikZ 矢量图代码生成器
# ============================================================
# TikZGenerator 通过 LLM 生成精确的 TikZ/PGFPlots 代码，
# 用于创建可直接嵌入 LaTeX 文档的矢量图形。
# TikZ 图的优势：可缩放、字体一致、风格与文章完全统一。
#
# 【支持的图表类型】
# - flowchart: 流程图（\tikz + \node + \draw）
# - block_diagram: 系统框图（模块 + 箭头）
# - neural_network: 神经网络结构图
# - timeline: 时间线图
# - tree: 树形结构图
# - bar_chart: 使用 pgfplots 的柱状图
# - line_plot: 使用 pgfplots 的折线图
#
# 【需要实现的内容】
#
# 1. TikZCode — TikZ 代码结果
#    字段:
#    - code: str                 # 完整的 TikZ 代码（含 \begin{tikzpicture}）
#    - standalone_code: str      # 可独立编译的完整 LaTeX 文档
#    - required_packages: list   # 需要的 LaTeX 包列表
#    - figure_latex: str         # 带 caption/label 的 figure 环境代码
#
# 2. TikZGenerator 类
#
#    核心方法:
#
#    async generate(
#        diagram_type: str,
#        description: str,
#        style: str = "simple",  # simple/detailed/colorful
#        custom_requirements: str = ""
#    ) -> TikZCode:
#    - 调用 LLM 生成 TikZ 代码
#    - 使用精心设计的系统提示词
#    - 验证生成代码的基本语法正确性
#
#    async generate_flowchart(
#        steps: list[dict],  # [{"id": "1", "text": "...", "next": ["2", "3"]}]
#        title: str = ""
#    ) -> TikZCode:
#    - 根据步骤列表自动生成流程图代码
#
#    async generate_neural_network(
#        layers: list[dict],  # [{"name": "input", "size": 4}, ...]
#        title: str = ""
#    ) -> TikZCode:
#    - 根据层结构生成神经网络图
#
#    validate_tikz(code: str) -> bool:
#    - 基本验证 TikZ 代码语法（括号配对、关键命令存在）
# ============================================================

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class TikZCode:
    """TikZ 代码结果，【实现字段见上方注释】"""
    code: str = ""
    standalone_code: str = ""
    required_packages: List[str] = field(default_factory=list)
    figure_latex: str = ""


class TikZGenerator:
    """
    LaTeX TikZ 矢量图代码生成器。
    通过 LLM 生成可直接嵌入论文的专业矢量图形。
    【完整实现规范见上方注释】
    """

    SYSTEM_PROMPT_TEMPLATE = """
    You are an expert at writing TikZ/PGFPlots code for academic papers.
    Generate clean, compilable TikZ code that:
    1. Uses proper tikzlibrary packages (arrows.meta, shapes, positioning)
    2. Follows consistent styling with academic papers
    3. Is well-commented for maintainability
    Only output the TikZ code block, no explanations.
    """

    async def generate(
        self,
        diagram_type: str,
        description: str,
        style: str = "simple",
        custom_requirements: str = "",
    ) -> TikZCode:
        """LLM 生成 TikZ 代码，【需要实现】"""
        pass

    async def generate_flowchart(
        self, steps: List[Dict[str, Any]], title: str = ""
    ) -> TikZCode:
        """生成流程图，【需要实现】"""
        pass

    async def generate_neural_network(
        self, layers: List[Dict[str, Any]], title: str = ""
    ) -> TikZCode:
        """生成神经网络图，【需要实现】"""
        pass

    def validate_tikz(self, code: str) -> bool:
        """验证 TikZ 代码语法，【需要实现】"""
        pass
