# nodes.py

## 模块说明

（无）

## API 概览

### 类

- `LlmClientLike`：LLM 客户端的最小能力约束。
- `BaseNode`：工作流节点抽象基类。
- `FunctionNode`：以函数形式实现节点逻辑的适配器。
- `LlmNode`：LLM 节点。
- `ToolNode`：工具调用节点。

## 类与方法

### LlmClientLike

LLM 客户端的最小能力约束。

方法：

- `response(self, prompt, *args, **kwargs)`：根据 prompt 生成模型回复文本（可选携带文件、工具参数等扩展能力）。

### BaseNode

工作流节点抽象基类。

方法：

- `__init__(self, node_id)`：Args:
- `run(self, message, context)`：执行节点逻辑。

### FunctionNode

以函数形式实现节点逻辑的适配器。

方法：

- `__init__(self, node_id, fn)`：Args:
- `run(self, message, context)`：调用封装的处理函数并返回其输出。

### LlmNode

LLM 节点。

方法：

- `__init__(self, node_id, llm_client, *, prompt=..., output_parser=...)`：Args:
- `run(self, message, context)`：调用 LLM 并将其输出转换为结构化消息。

### ToolNode

工具调用节点。

方法：

- `__init__(self, node_id, *, tool_names=...)`：Args:
- `run(self, message, context)`：执行消息中包含的工具调用，并返回聚合后的工具结果消息。
