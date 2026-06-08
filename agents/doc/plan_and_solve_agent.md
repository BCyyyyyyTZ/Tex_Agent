# plan_and_solve_agent.py

## 模块说明

[扩展] PlanAndSolveAgent 接口定义。
实现先规划后执行的两阶段推理：先将复杂任务分解为子任务列表，再逐一执行解决。

TODO: 开发者 B 负责实现此类（第一阶段任务）

## API 概览

### 类

- `SubTask`：子任务数据结构。
- `PlanAndSolveAgent`：[扩展] 计划与执行 Agent 抽象基类。

## 类与方法

### SubTask

子任务数据结构。

方法：无

### PlanAndSolveAgent

[扩展] 计划与执行 Agent 抽象基类。

方法：

- `__init__(self, name, system_prompt)`：初始化计划-执行 Agent 的基础字段。
- `name(self)`：返回 Agent 名称（只读）。
- `plan(self, message)`：规划阶段：将输入任务分解为有序的子任务列表。
- `solve(self, subtask, context)`：执行阶段：解决单个子任务。
- `aggregate(self, subtasks)`：整合阶段：将所有子任务结果汇总为最终答案。
- `run(self, message)`：Plan-and-Solve 主流程（占位实现）。
- `reset(self)`：重置 Agent 内部状态（占位，子类实现）。
