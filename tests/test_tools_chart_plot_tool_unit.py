"""
tools.chart_plot_tool 的测试。

覆盖点：
1) 输入校验（chart_type/output_path）；
2) 在 matplotlib 可用时生成图片文件并校验输出非空；
3) 在 matplotlib 不可用时返回明确的依赖错误信息。
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

from tools.chart_plot_tool import ChartPlotTool


def test_chart_plot_rejects_empty_required_fields(tmp_path: Path) -> None:
    tool = ChartPlotTool()
    r1 = tool.run(chart_type="", data={"x": [1], "y": [1]}, output_path=str(tmp_path / "a.png"))
    assert r1.success is False
    assert "chart_type" in (r1.error or "")

    r2 = tool.run(chart_type="bar", data={"x": [1], "y": [1]}, output_path="")
    assert r2.success is False
    assert "output_path" in (r2.error or "")


def test_chart_plot_generates_png_or_reports_missing_dependency(tmp_path: Path) -> None:
    """
    该用例在不同环境下行为一致：
    - 若 matplotlib 可用：应生成 PNG 文件并返回 success=True；
    - 若 matplotlib 不可用：应返回 success=False 且 error 指向 matplotlib 依赖。
    """
    tool = ChartPlotTool()
    out = tmp_path / "chart.png"
    r = tool.run(chart_type="bar", data={"x": ["A", "B"], "y": [1, 2]}, output_path=str(out), title="t")

    has_matplotlib = importlib.util.find_spec("matplotlib") is not None
    if has_matplotlib:
        assert r.success is True, r.error
        assert Path(r.output).exists()
        assert Path(r.output).stat().st_size > 0
    else:
        assert r.success is False
        assert "matplotlib" in (r.error or "").lower()

