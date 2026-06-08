import json
from pathlib import Path
import sys
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.base_tool import BaseTool
from core.message import ToolResult
from utils.logger import get_logger

logger = get_logger(__name__)


class ChartPlotTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="chart_plot",
            description="根据给定数据生成统计图表，支持柱状图(bar)、折线图(line)、饼状图(pie)，输出为图片文件路径。",
            input_schema={
                "chart_type": "图表类型：bar | line | pie",
                "data": "图表数据。bar/line 支持 {x:[], y:[]} 或 {x:[], series:[{name:'', y:[]}, ...]}；pie 支持 {labels:[], values:[]}",
                "output_path": "输出图片路径，例如 'outputs/chart.png'",
                "title": "图表标题（可选）",
                "x_label": "X轴标题（可选）",
                "y_label": "Y轴标题（可选）",
                "width": "图宽（英寸，可选，默认 8）",
                "height": "图高（英寸，可选，默认 5）",
                "dpi": "导出DPI（可选，默认 200）",
                "legend": "是否显示图例（可选，默认 true）",
            },
        )

    def _ensure_dict(self, data: Any) -> dict[str, Any]:
        if data is None:
            return {}
        if isinstance(data, dict):
            return data
        if isinstance(data, str):
            try:
                loaded = json.loads(data)
                if isinstance(loaded, dict):
                    return loaded
            except Exception:
                return {}
        return {}

    def _as_bool(self, v: Any, default: bool) -> bool:
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            s = v.strip().lower()
            if s in {"1", "true", "yes", "y", "on"}:
                return True
            if s in {"0", "false", "no", "n", "off"}:
                return False
        return default

    def _as_int(self, v: Any, default: int) -> int:
        try:
            if v is None:
                return default
            return int(v)
        except Exception:
            return default

    def _as_float(self, v: Any, default: float) -> float:
        try:
            if v is None:
                return default
            return float(v)
        except Exception:
            return default

    def run(
        self,
        chart_type: str,
        data: Any,
        output_path: str,
        title: str = "",
        x_label: str = "",
        y_label: str = "",
        width: float = 8,
        height: float = 5,
        dpi: int = 200,
        legend: bool = True,
    ) -> ToolResult:
        try:
            try:
                import matplotlib

                matplotlib.use("Agg")
                import matplotlib.pyplot as plt
            except Exception as e:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"绘图依赖未就绪：{e}. 请安装 matplotlib（例如 pip install matplotlib）",
                )

            if not chart_type:
                return ToolResult(success=False, output="", error="chart_type 不能为空")
            if not output_path:
                return ToolResult(success=False, output="", error="output_path 不能为空")

            ct = chart_type.strip().lower()
            d = self._ensure_dict(data)
            out = Path(output_path)
            out.parent.mkdir(parents=True, exist_ok=True)

            w = self._as_float(width, 8.0)
            h = self._as_float(height, 5.0)
            dpid = self._as_int(dpi, 200)
            show_legend = self._as_bool(legend, True)

            fig, ax = plt.subplots(figsize=(w, h))

            if ct in {"bar", "barh"}:
                x = d.get("x", [])
                series = d.get("series")
                if series and isinstance(series, list):
                    n = len(x)
                    m = max(1, len(series))
                    bar_w = 0.8 / m
                    base = list(range(n))
                    for i, s in enumerate(series):
                        name = (s or {}).get("name", f"series_{i+1}")
                        y = (s or {}).get("y", [])
                        xs = [b - 0.4 + bar_w * (i + 0.5) for b in base]
                        ax.bar(xs, y, width=bar_w, label=name)
                    ax.set_xticks(base)
                    ax.set_xticklabels(x)
                else:
                    y = d.get("y", [])
                    ax.bar(x, y)

            elif ct == "line":
                x = d.get("x", [])
                series = d.get("series")
                if series and isinstance(series, list):
                    for i, s in enumerate(series):
                        name = (s or {}).get("name", f"series_{i+1}")
                        y = (s or {}).get("y", [])
                        ax.plot(x, y, marker="o", label=name)
                else:
                    y = d.get("y", [])
                    ax.plot(x, y, marker="o")

            elif ct == "pie":
                labels = d.get("labels", [])
                values = d.get("values", [])
                ax.pie(values, labels=labels, autopct="%1.1f%%")
                ax.axis("equal")

            else:
                plt.close(fig)
                return ToolResult(success=False, output="", error=f"不支持的 chart_type: {chart_type!r}")

            if title:
                ax.set_title(title)
            if x_label and ct != "pie":
                ax.set_xlabel(x_label)
            if y_label and ct != "pie":
                ax.set_ylabel(y_label)
            if show_legend and ct in {"bar", "line"} and len(ax.get_legend_handles_labels()[0]) > 0:
                ax.legend()

            fig.tight_layout()
            fig.savefig(out, dpi=dpid)
            plt.close(fig)

            return ToolResult(
                success=True,
                output=str(out),
                metadata={
                    "output_path": str(out),
                    "chart_type": ct,
                    "title": title,
                },
            )
        except Exception as e:
            logger.error(f"图表生成失败: {e}")
            return ToolResult(success=False, output="", error=f"图表生成失败: {e}")


def _assert_file_ok(path: str) -> None:
    p = Path(path)
    if not p.exists():
        raise AssertionError(f"文件未生成: {p}")
    if p.stat().st_size <= 0:
        raise AssertionError(f"文件为空: {p}")


def _run_self_test(output_dir: str | None = None) -> None:
    tool = ChartPlotTool()
    base = Path(output_dir) if output_dir else (Path(__file__).resolve().parents[1] / "outputs" / "chart_plot_tool_test")
    base.mkdir(parents=True, exist_ok=True)

    for p in base.glob("*.png"):
        try:
            p.unlink()
        except Exception:
            pass

    r1 = tool.run(
        chart_type="bar",
        data={"x": ["A", "B", "C"], "y": [3, 5, 2]},
        output_path=str(base / "bar_single.png"),
        title="bar_single",
        x_label="x",
        y_label="y",
    )
    assert r1.success, r1.error
    _assert_file_ok(r1.output)

    r2 = tool.run(
        chart_type="bar",
        data=json.dumps(
            {
                "x": ["A", "B", "C"],
                "series": [
                    {"name": "S1", "y": [1, 2, 3]},
                    {"name": "S2", "y": [3, 2, 1]},
                ],
            }
        ),
        output_path=str(base / "bar_multi.png"),
        title="bar_multi",
        legend=True,
    )
    assert r2.success, r2.error
    _assert_file_ok(r2.output)

    r3 = tool.run(
        chart_type="line",
        data={"x": [1, 2, 3, 4], "y": [10, 12, 8, 15]},
        output_path=str(base / "line_single.png"),
        title="line_single",
    )
    assert r3.success, r3.error
    _assert_file_ok(r3.output)

    r4 = tool.run(
        chart_type="line",
        data={"x": [1, 2, 3], "series": [{"name": "A", "y": [1, 4, 2]}, {"name": "B", "y": [2, 1, 3]}]},
        output_path=str(base / "line_multi.png"),
        title="line_multi",
        legend="false",
    )
    assert r4.success, r4.error
    _assert_file_ok(r4.output)

    r5 = tool.run(
        chart_type="pie",
        data={"labels": ["A", "B", "C"], "values": [40, 35, 25]},
        output_path=str(base / "pie.png"),
        title="pie",
    )
    assert r5.success, r5.error
    _assert_file_ok(r5.output)

    r6 = tool.run(chart_type="unknown", data={"x": [1], "y": [1]}, output_path=str(base / "bad.png"))
    assert not r6.success

    r7 = tool.run(chart_type="bar", data={"x": [1], "y": [1]}, output_path="")
    assert not r7.success

    print(f"图表自测通过，输出目录: {base.resolve()}")


if __name__ == "__main__":
    out_dir = sys.argv[1] if len(sys.argv) > 1 else None
    _run_self_test(out_dir)