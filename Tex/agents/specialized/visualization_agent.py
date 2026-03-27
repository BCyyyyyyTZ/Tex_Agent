# ============================================================
# agents/specialized/visualization_agent.py
# VisualizationAgent —— 学术数据可视化智能体
# ============================================================
# VisualizationAgent 根据数据和用户需求，自动生成符合
# IEEE/ACM 等学术规范的高质量图表，并输出 LaTeX 可嵌入的代码。
#
# 【需要实现的内容】
#
# 1. ChartConfig — 图表配置
#    字段:
#    - chart_type: str              # bar/line/scatter/heatmap/boxplot/histogram/pie
#    - title: str
#    - x_label: str
#    - y_label: str
#    - legend: bool
#    - style: str                   # "ieee" / "acm" / "nature" / "default"
#    - color_palette: str           # "colorblind_safe" / "grayscale" / "vibrant"
#    - figure_size: tuple           # (width_inches, height_inches)
#    - dpi: int                     # 输出分辨率
#    - output_format: str           # "pdf" / "png" / "svg" / "eps"
#    - font_size: int               # 基础字体大小
#    - line_width: float
#    - error_bars: bool             # 是否显示误差条
#
# 2. ChartOutput — 图表输出结果
#    字段:
#    - chart_id: str
#    - file_path: str               # 生成的图表文件路径
#    - latex_figure_code: str       # 嵌入 LaTeX 的 \begin{figure}...代码
#    - caption: str                 # 图表标题
#    - description: str             # 图表内容描述（用于 accessibility）
#    - config: ChartConfig          # 使用的配置
#
# 3. VisualizationAgent 类（继承 SimpleAgent）
#    agent_type = "visualization"
#
#    核心方法:
#
#    async create_chart(
#        data: Any,              # pandas DataFrame 或字典
#        chart_type: str,
#        config: ChartConfig = None,
#        output_dir: str = None
#    ) -> ChartOutput:
#    - 根据图表类型调用对应的绘制方法
#    - 应用学术图表样式（rcParams 设置）
#    - 保存为指定格式
#    - 生成对应的 LaTeX 嵌入代码
#
#    async auto_visualize(
#        data: Any,
#        description: str,
#        style: str = "ieee"
#    ) -> list[ChartOutput]:
#    - 根据数据特征和用户描述自动选择最合适的图表类型
#    - 调用 LLM 理解用户意图，生成 ChartConfig
#    - 可能生成多张互补的图表
#
#    async create_comparison_chart(
#        data_groups: dict,
#        metric: str,
#        chart_type: str = "bar"
#    ) -> ChartOutput:
#    - 专门用于方法对比实验结果的图表
#    - 支持误差条和显著性标注
#    - 符合论文实验结果展示规范
#
#    async create_trend_chart(
#        time_series: dict,
#        x_label: str = "Year",
#        y_label: str = "Count"
#    ) -> ChartOutput:
#    - 生成文献趋势折线图
#
#    async create_correlation_heatmap(
#        correlation_matrix: Any,
#        labels: list[str]
#    ) -> ChartOutput:
#    - 生成相关性热力图
#    - IEEE 风格，使用色盲友好配色
#
#    _apply_academic_style(style: str) -> None:
#    - 设置 matplotlib rcParams 为学术风格
#    - 包含字体（Times New Roman / Helvetica）、线宽、颜色等
#
#    _generate_latex_figure(
#        file_path: str, caption: str, label: str, width: str
#    ) -> str:
#    - 生成标准的 LaTeX figure 环境代码
#    - 支持单列/双列图（\columnwidth/\textwidth）
#
#    async _infer_chart_type(data: Any, description: str) -> str:
#    - 调用 LLM 根据数据特征和描述推荐图表类型
# ============================================================

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from agents.base.simple_agent import SimpleAgent
from core.base_agent import AgentResult, TaskContext


@dataclass
class ChartConfig:
    """图表配置，【实现字段见上方注释】"""
    chart_type: str = "bar"
    title: str = ""
    x_label: str = ""
    y_label: str = ""
    legend: bool = True
    style: str = "ieee"
    color_palette: str = "colorblind_safe"
    figure_size: Tuple[float, float] = (3.5, 2.5)
    dpi: int = 300
    output_format: str = "pdf"
    font_size: int = 9
    line_width: float = 1.0
    error_bars: bool = False


@dataclass
class ChartOutput:
    """图表输出结果，【实现字段见上方注释】"""
    chart_id: str = ""
    file_path: str = ""
    latex_figure_code: str = ""
    caption: str = ""
    description: str = ""
    config: Optional[ChartConfig] = None


class VisualizationAgent(SimpleAgent):
    """
    学术数据可视化专家 Agent。
    生成符合 IEEE/ACM 规范的高质量学术图表。
    【完整实现规范见上方注释】
    """

    agent_type: str = "visualization"
    version: str = "1.0.0"

    def __init__(
        self,
        name: str = "VisualizationAgent",
        config: Optional[Any] = None,
    ) -> None:
        super().__init__(name=name, config=config)
        self.default_style: str = "ieee"
        self.output_dpi: int = 300
        self.output_formats: List[str] = ["pdf", "png"]
        self.output_dir: str = "./data/exports/figures"

    async def create_chart(
        self,
        data: Any,
        chart_type: str,
        config: Optional[ChartConfig] = None,
        output_dir: Optional[str] = None,
    ) -> ChartOutput:
        """创建学术图表，【需要实现】"""
        pass

    async def auto_visualize(
        self,
        data: Any,
        description: str,
        style: str = "ieee",
    ) -> List[ChartOutput]:
        """自动推断并生成最合适的图表，【需要实现】"""
        pass

    async def create_comparison_chart(
        self,
        data_groups: Dict[str, Any],
        metric: str,
        chart_type: str = "bar",
    ) -> ChartOutput:
        """方法对比实验图表，【需要实现】"""
        pass

    async def create_trend_chart(
        self,
        time_series: Dict[int, float],
        x_label: str = "Year",
        y_label: str = "Count",
    ) -> ChartOutput:
        """文献趋势折线图，【需要实现】"""
        pass

    async def create_correlation_heatmap(
        self, correlation_matrix: Any, labels: List[str]
    ) -> ChartOutput:
        """相关性热力图，【需要实现】"""
        pass

    def _apply_academic_style(self, style: str) -> None:
        """设置 matplotlib 学术样式，【需要实现】"""
        pass

    def _generate_latex_figure(
        self,
        file_path: str,
        caption: str,
        label: str,
        width: str = r"\columnwidth",
    ) -> str:
        """生成 LaTeX figure 环境代码，【需要实现】"""
        pass

    async def _infer_chart_type(self, data: Any, description: str) -> str:
        """LLM 推断最优图表类型，【需要实现】"""
        pass
