# base_agent.py

## 模块说明

BaseAgent 抽象基类。
所有 Agent 实现均继承此类，保证接口统一，支持面向接口编程与 Mock 测试。

## API 概览

### 类

- `AgentMemoryItem`：Agent 内存项，用于存储单条消息。
- `AgentMemory`：Agent 内存管理类，用于存储和检索 Agent 运行时的状态。
- `LlmClient`：（无）
- `GeminiClient`：（无）
- `QwenClient`：（无）
- `BaseAgent`：Agent 标准抽象基类。

## 类与方法

### AgentMemoryItem

Agent 内存项，用于存储单条消息。

方法：

- `__init__(self, data, data_type)`：Args:

### AgentMemory

Agent 内存管理类，用于存储和检索 Agent 运行时的状态。

方法：

- `__init__(self)`：初始化空内存容器。
- `add(self, item)`：追加一条内存记录。
- `clear(self)`：清空全部内存记录。
- `get(self, item_type)`：按类型过滤内存记录。

### LlmClient

（无）

方法：

- `__init__(self, model_name, api_key, base_url, temperature)`：OpenAI 兼容接口的 LLM 客户端封装。
- `response(self, prompt, attachments=..., file_paths=..., *, max_file_chars=...)`：生成LLM响应，支持上传附件

### GeminiClient

（无）

方法：

- `__init__(self, model_name, api_key, temperature)`：:param api_key: 你的 Google AI Studio API Key
- `_upload_files_parallel(self, file_paths, file_mime_types=...)`：内部方法：上传多个文件并确保它们都进入 ACTIVE 状态。
- `response(self, prompt, file_paths=..., file_mime_types=...)`：上传文件并根据内容进行提问。

### QwenClient

（无）

方法：

- `__init__(self, model_name, api_key, temperature, *, base_url=..., file_purpose=..., max_file_chars=..., upload_wait_seconds=...)`：DashScope OpenAI 兼容通道的 Qwen 客户端封装。
- `_upload_files(self, file_paths)`：上传文件并缓存结果。
- `_wait_files_ready(self, uploaded)`：轮询等待上传文件进入可用状态。
- `response(self, prompt, file_paths=..., **_)`：生成模型回复，并可选上传文件供模型引用。

### BaseAgent

Agent 标准抽象基类。

方法：

- `__init__(self, name, system_prompt, tools)`：初始化 Agent 基类属性。
- `set_llm(self, llm_name, model_name, api_key, base_url, temperature)`：注册一个 OpenAI 兼容通道的 LlmClient。
- `set_gemini(self, llm_name, model_name, api_key, temperature)`：注册一个 GeminiClient。
- `set_qwen(self, llm_name, model_name, api_key, temperature, base_url=...)`：注册一个 QwenClient（OpenAI compatible-mode）。
- `set_tool_args(self, args)`：设置工具默认参数（按工具名组织）。
- `call_tool(self, tool_name, tool_args)`：调用指定工具，返回工具执行结果。
- `_normalize_message(self, message)`：将各种输入格式统一转换为 AgentMessage 对象。
- `run(self, message)`：同步执行推理，接收输入消息并返回 Agent 响应。
- `ainvoke(self, message)`：异步执行推理。
- `reset(self)`：重置 Agent 内部状态（如清空对话历史、工具调用记录等）。
- `get_history(self)`：获取当前 Agent 的对话历史。
