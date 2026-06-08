"""
[扩展] VisualizationTool 接口定义。
预留调用 Matplotlib/Seaborn 生成符合学术规范图表的工具接口。

TODO: 开发者 C 负责实现此类（第四阶段任务）
"""
from abc import abstractmethod
from typing import Dict, Any, Optional

from tools.base_tool import BaseTool
from core.message import ToolResult


class VisualizationTool(BaseTool):
    """
    [扩展] 数据可视化工具抽象基类。

    功能规划：
        1. 支持从 CSV/Excel/JSON 文件加载数据
        2. 自动生成符合 IEEE/ACM 规范的学术图表
           （折线图、柱状图、散点图、箱线图等）
        3. 支持高质量导出（PDF/PNG/EPS，300DPI+）

    TODO: 开发者 C 实现建议：
          - 使用 matplotlib + seaborn 组合
          - 图表样式可参考 SciencePlots 库（pip install SciencePlots）
          - 支持 LaTeX 公式渲染（设置 plt.rcParams["text.usetex"] = True）
    """

    @property
    def name(self) -> str:
        """返回工具唯一标识符（用于路由与注册）。"""
        return "visualization"

    @property
    def description(self) -> str:
        """返回工具用途说明（用于向模型/用户展示能力与输入输出）。"""
        return (
            "根据用户提供的数据生成学术图表（折线图、柱状图、散点图等）。"
            "图表风格符合 IEEE/ACM 学术规范，支持导出为高清 PDF/PNG 格式。"
            "输入数据文件路径和图表类型，返回生成的图表文件路径。"
        )

    @abstractmethod
    def load_data(self, file_path: str) -> Dict[str, Any]:
        """
        加载数据文件为结构化字典。

        Args:
            file_path: 数据文件路径（支持 CSV / Excel / JSON 格式）。

        Returns:
            结构化数据字典（如 {"x": [...], "y": [...], "labels": [...]}）。

        Raises:
            NotImplementedError: 子类必须实现。
        """
        raise NotImplementedError

    @abstractmethod
    def generate_chart(
        self,
        data: Dict[str, Any],
        chart_type: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        根据数据和配置生成学术图表并保存。

        Args:
            data: 由 load_data() 返回的结构化数据字典。
            chart_type: 图表类型（"line" / "bar" / "scatter" / "box" / "heatmap"）。
            config: 图表样式配置字典，建议包含：
                    {
                        "title": str,
                        "xlabel": str,
                        "ylabel": str,
                        "figsize": (float, float),
                        "dpi": int,
                        "output_path": str,
                    }

        Returns:
            生成的图表文件的绝对路径。

        Raises:
            NotImplementedError: 子类必须实现。
        """
        raise NotImplementedError

    def run(self, input: str) -> ToolResult:
        """
        执行数据可视化任务（占位实现）。

        TODO: 开发者 C 在此实现输入解析（从 input 字符串提取文件路径和图表类型）、
              调用 load_data() 和 generate_chart() 的完整逻辑。
        """
        raise NotImplementedError(
            "VisualizationTool.run() 尚未实现。"
            "请参考 load_data()/generate_chart() 接口文档进行实现。"
        )
