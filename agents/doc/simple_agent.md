# simple_agent.py

## 模块说明

SimpleAgent：最基础的可运行 Agent 实现。
接收输入消息 → 调用 LLM → 返回响应，支持工具列表注入与有界多轮对话历史维护。

## API 概览

### 类

- `SimpleAgent`：基础 Agent 实现，封装 LangChain ChatOpenAI 调用。

## 类与方法

### SimpleAgent

基础 Agent 实现，封装 LangChain ChatOpenAI 调用。

方法：

- `__init__(self, name, system_prompt=..., tools=..., model_name=..., api_key=..., base_url=..., temperature=..., max_history=...)`：初始化基础对话 Agent，并完成默认系统提示词与 LLM 后端的配置。
- `_build_history_messages(self)`：构建对话历史消息列表
- `_trim_history(self)`：若历史超出 max_history 上限，丢弃最旧的消息（保持偶数对齐）。
- `_append_llm_trace(self, lc_messages, response_text)`：统一记录所有模式下的 LLM 交互（默认/自定义/plan）。
- `run(self, message)`：同步执行推理。
- `ainvoke(self, message)`：异步执行推理（在线程池中运行同步 LLM 调用，不阻塞事件循环）。
- `reset(self)`：清空对话历史，重置 Agent 为初始状态。
- `get_history(self)`：获取完整的对话历史副本。
