# command_running_tool.py

## 模块说明

CommandRunningTool：执行指定的命令行命令并返回执行结果。

## API 概览

### 类

- `CommandRunningTool`：命令行执行工具。

## 类与方法

### CommandRunningTool

命令行执行工具。

方法：

- `__init__(self)`：初始化命令执行工具，并声明输入 schema（单条 command）。
- `_execute_command_with_auto_encoding(self, command)`：执行命令并尝试自动处理控制台输出编码（优先 gbk，失败回退 utf-8）。
- `run(self, command)`：执行命令行命令。
