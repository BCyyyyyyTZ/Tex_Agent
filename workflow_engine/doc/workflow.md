# workflow.py

## 模块说明

（无）

## API 概览

### 类

- `WorkflowContext`：工作流运行时上下文。
- `Edge`：工作流有向边。
- `Workflow`：DAG 工作流。

### 函数

- `_merge_message(messages)`：将同一节点的多路输入消息合并为一个 MergedMessage。

## 类与方法

### WorkflowContext

工作流运行时上下文。

方法：无

### Edge

工作流有向边。

方法：无

### Workflow

DAG 工作流。

方法：

- `__init__(self)`：初始化空工作流。
- `add_node(self, node)`：注册节点。
- `add_edge(self, from_node, to_node, *, condition=...)`：注册边（依赖/路由关系）。
- `_topological_order(self)`：计算节点拓扑序。
- `_infer_start_nodes(self)`：推断工作流起始节点：所有入度为 0 的节点。
- `run(self, initial_message=..., *, start_nodes=..., context=..., return_context=...)`：执行工作流。

## 函数

### _merge_message(messages)

将同一节点的多路输入消息合并为一个 MergedMessage。
