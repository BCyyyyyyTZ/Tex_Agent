# base_tool.py

## 模块说明

BaseTool 标准工具抽象基类。
所有工具实现均继承此类，保证工具接口统一，支持动态注册与插拔式扩展。

## API 概览

### 类

- `BaseTool`：工具标准接口基类。

## 类与方法

### BaseTool

工具标准接口基类。

方法：

- `__init__(self, name, description, input_schema)`：初始化工具的基础元信息（名称、描述与输入参数 schema）。
- `run(self, input)`：同步执行工具。
- `arun(self, input)`：异步执行工具（默认实现：在线程池中运行同步 run，不阻塞事件循环）。
- `__repr__(self)`：返回便于调试的工具简短表示（包含类名与工具名）。
