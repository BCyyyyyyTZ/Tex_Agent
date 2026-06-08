# simple_agent_old.py

## 模块说明

SimpleAgent：纯 LLM 节点实现（不执行工具）。
职责：接收输入消息 -> 调用 LLM -> 返回 assistant 文本结果。

## API 概览

### 类

- `SimpleAgent`：纯推理 Agent，不负责工具调用。

## 类与方法

### SimpleAgent

纯推理 Agent，不负责工具调用。

方法：

- `__init__(self, name, system_prompt=..., tools=..., model_name=..., api_key=..., base_url=..., temperature=..., max_history=...)`：初始化纯推理 Agent，并根据配置选择 Gemini/OpenAI 兼容后端。
- `_init_backend(self)`：根据模型名与可用 API Key 选择 LLM 后端并完成初始化。
- `_build_history_messages(self)`：将 self.history 序列化为“可拼接的文本对话历史”。
- `_trim_history(self)`：将历史裁剪到 max_history 上限，并尽量保持 user/assistant 的轮次边界。
- `_append_llm_trace(self, history_messages, response_text)`：将本次 LLM 输入与输出追加写入 trace 文件，便于离线排查与复现实验。
- `_normalize_attachment(self, attachment)`：规范化附件传递策略。
- `run(self, message)`：同步执行一次推理并返回 assistant 消息。
- `ainvoke(self, message)`：异步调用入口（线程池包装同步 run）。
- `reset(self)`：清空对话历史，将 Agent 恢复到初始状态。
- `get_history(self)`：返回当前对话历史的浅拷贝（避免外部直接修改内部列表）。
