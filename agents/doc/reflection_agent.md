# reflection_agent.py

## 模块说明

[扩展] ReflectionAgent 接口定义。
实现自我反思迭代模式：生成初始答案后，通过批判性反思机制识别不足并迭代改进。

TODO: 开发者 B 负责实现此类（第一阶段任务）

## API 概览

### 类

- `ReflectionAgent`：[扩展] 自我反思 Agent 抽象基类。

## 类与方法

### ReflectionAgent

[扩展] 自我反思 Agent 抽象基类。

方法：

- `__init__(self, name, system_prompt=..., tools=..., model_name=..., api_key=..., base_url=..., temperature=..., max_history=...)`：初始化 ReflectionAgent。
- `_build_history_messages(self, history)`：构建对话历史消息列表
- `_build_executor_prompt(self)`：构建“修改者/执行器”侧的输入 prompt。
- `run(self, message)`：执行“生成-反思-改写”的迭代流程。
- `reset(self)`：清空对话历史，重置 Agent 为初始状态。
