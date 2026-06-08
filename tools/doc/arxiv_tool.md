# arxiv_tool.py

## 模块说明

ArxivSearchTool：调用 arXiv API 进行学术文献检索（可运行）。
这是框架中第一个完整实现的工具，验证 BaseTool 接口的正确性与可用性。

## API 概览

### 类

- `ArxivSearchTool`：arXiv 学术文献检索工具。

## 类与方法

### ArxivSearchTool

arXiv 学术文献检索工具。

方法：

- `__init__(self, max_results=...)`：初始化 arXiv 检索工具，并配置最大返回条数与 SDK Client。
- `_format_results(self, results)`：将 arXiv 检索结果格式化为可读的文本字符串。
- `run(self, query)`：执行 arXiv 文献检索。
