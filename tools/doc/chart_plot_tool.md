# chart_plot_tool.py

## 模块说明

统计图表生成工具（ChartPlotTool）。

输入结构化数据，生成常见科研图表并导出为图片文件：
- bar: 柱状图
- line: 折线图
- pie: 饼图

该工具主要用于把实验结果/消融数据快速可视化，便于论文写作与报告展示。

## API 概览

### 类

- `ChartPlotTool`：以统一 schema 接收图表参数，并将图表写入 output_path。

### 函数

- `_assert_file_ok(path)`：断言指定路径文件存在且非空（用于自测验证输出）。
- `_run_self_test(output_dir=...)`：运行本工具的最小自测：生成多种图表并校验输出文件可用。

## 类与方法

### ChartPlotTool

以统一 schema 接收图表参数，并将图表写入 output_path。

方法：

- `__init__(self)`：初始化图表生成工具，并声明可用图表类型与输入参数 schema。
- `_ensure_dict(self, data)`：将输入 data 归一化为 dict。
- `_as_bool(self, v, default)`：将输入归一化为 bool（支持常见字符串形式），失败则返回 default。
- `_as_int(self, v, default)`：将输入归一化为 int，失败则返回 default。
- `_as_float(self, v, default)`：将输入转换为 float，失败则返回默认值。
- `run(self, chart_type, data, output_path, title=..., x_label=..., y_label=..., width=..., height=..., dpi=..., legend=...)`：生成并导出图表。

## 函数

### _assert_file_ok(path)

断言指定路径文件存在且非空（用于自测验证输出）。

### _run_self_test(output_dir=...)

运行本工具的最小自测：生成多种图表并校验输出文件可用。
