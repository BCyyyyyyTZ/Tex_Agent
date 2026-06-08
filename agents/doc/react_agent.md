# react_agent.py

## 模块说明

[扩展] ReActAgent 接口定义。
实现 Reason-Act 循环推理模式：在每步先 Reason（推理）再 Act（执行工具），
循环直到满足终止条件后输出最终答案。

TODO: 开发者 B 负责实现此类（第一阶段任务）

## API 概览

### 类

- `ReActAgent`：[扩展] ReAct 模式 Agent 抽象基类。

## 类与方法

### ReActAgent

[扩展] ReAct 模式 Agent 抽象基类。

方法：

- `__init__(self, name, system_prompt, tools=...)`：初始化 ReAct Agent 的基础字段。
- `name(self)`：返回 Agent 名称（只读）。
- `reason(self, observation, history)`：推理阶段：根据观察结果和历史记录决定下一步行动。
- `act(self, thought)`：行动阶段：根据推理结果选择并准备执行工具。
- `is_done(self, thought, action)`：终止条件判断。
- `run(self, message)`：ReAct 循环主流程（占位实现）。
- `reset(self)`：重置 Agent 状态，子类需清空推理历史和工具调用记录。
