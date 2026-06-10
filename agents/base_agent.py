"""
BaseAgent 抽象基类。
所有 Agent 实现均继承此类，保证接口统一，支持面向接口编程与 Mock 测试。
"""
from abc import ABC, abstractmethod
import json
import logging
from typing import Any, List, Optional, Union

from config.settings import settings
import asyncio
import openai

from core.message import WorkflowMessage, MessageLike, ToolResult, ensure_message
from tools.base_tool import BaseTool
from utils.utils import set_nested_value

import os
import time

from google import genai
from google.genai import types

_logger = logging.getLogger(__name__)


class AgentMemoryItem:
    """
    Agent 内存项，用于存储单条工作流消息。
    """

    def __init__(self, data: any, data_type: str):
        self.data = data
        self.type = data_type  


class AgentMemory:
    """
    Agent 内存管理类，用于存储和检索 Agent 运行时的状态。
    """

    def __init__(self):
        self.memory: List[AgentMemoryItem] = []

    def add(self, item: AgentMemoryItem):
        self.memory.append(item)

    def clear(self):
        self.memory.clear()

    def get(self, item_type: str) -> List[AgentMemoryItem]:
        return [item for item in self.memory if item.type == item_type]

class LlmClient:
	def __init__(
		self,
		model_name: str,
		api_key: str,
		base_url: str,
		temperature: float,
		max_tokens: Optional[int] = None,
	):
		self.model_name = model_name
		self.api_key = api_key
		self.client = openai.OpenAI(api_key=api_key, base_url=base_url)
		self.temperature = temperature
		mt = int(max_tokens) if max_tokens is not None else int(settings.llm_max_tokens)
		# 合并超长 checklist 标注列表等场景需要足够 completion 预算
		self.max_tokens = max(512, min(mt, 128000))

	@staticmethod
	def _parse_chat_completion_response(response: Any) -> str:
		"""
		从 OpenAI Chat Completions 响应中提取文本。
		兼容部分代理在异常/限流时直接返回 str 或非标准 dict 的情况。
		"""
		if response is None:
			raise ValueError("LLM 返回为空")

		if isinstance(response, str):
			text = response.strip()
			if text.startswith("{") and text.endswith("}"):
				try:
					parsed = json.loads(text)
					if isinstance(parsed, dict):
						return LlmClient._parse_chat_completion_response(parsed)
				except json.JSONDecodeError:
					pass
			return text

		if isinstance(response, dict):
			choices = response.get("choices") or []
			if choices:
				first = choices[0] if isinstance(choices[0], dict) else {}
				msg = first.get("message") if isinstance(first, dict) else {}
				if isinstance(msg, dict):
					content = msg.get("content")
					if content is not None:
						return str(content).strip()
			for key in ("output_text", "text", "content", "result"):
				val = response.get(key)
				if isinstance(val, str) and val.strip():
					return val.strip()
			raise ValueError(f"dict 响应缺少 choices/message: keys={list(response.keys())[:12]}")

		choices = getattr(response, "choices", None)
		if choices:
			first = choices[0]
			message = getattr(first, "message", None)
			content = getattr(message, "content", None) if message is not None else None
			if content is not None:
				if isinstance(content, str):
					return content.strip()
				if isinstance(content, list):
					parts: List[str] = []
					for part in content:
						if isinstance(part, dict) and part.get("type") == "text":
							parts.append(str(part.get("text", "")))
						elif isinstance(part, str):
							parts.append(part)
					return "\n".join(p for p in parts if p).strip()
			return ""

		raise ValueError(f"无法解析 LLM 响应类型: {type(response).__name__}")

	def response(self, prompt: str, attachments: Optional[List[dict]] = None, **kwargs) -> str:
		"""
		生成LLM响应，支持上传附件
		
		Args:
		    prompt: 文本提示
		    attachments: 附件列表，每个附件为包含type和相关信息的字典
		                例如: [{"type": "image_url", "image_url": {"url": "..."}}]
		                或: [{"type": "file", "file": {"file_id": "..."}}]
		
		Returns:
		    LLM生成的文本响应
		"""
		# 构建消息内容
		message_content = []
		
		# 添加文本内容
		message_content.append({"type": "text", "text": prompt})
		
		# 添加附件
		if attachments:
			message_content.extend(attachments)
		
		# 如果只有文本，直接使用字符串格式
		if len(message_content) == 1 and message_content[0].get("type") == "text":
			message_content = message_content[0]["text"]
		
		raw = self.client.chat.completions.create(
			model=self.model_name,
			messages=[{"role": "user", "content": message_content}],
			temperature=self.temperature,
			max_tokens=self.max_tokens,
		)
		try:
			return self._parse_chat_completion_response(raw)
		except (AttributeError, IndexError, TypeError, ValueError) as e:
			_logger.warning(
				"LlmClient 响应解析失败 (%s)，类型=%s，将重试一次",
				e,
				type(raw).__name__,
			)
			raw_retry = self.client.chat.completions.create(
				model=self.model_name,
				messages=[{"role": "user", "content": message_content}],
				temperature=self.temperature,
				max_tokens=self.max_tokens,
			)
			return self._parse_chat_completion_response(raw_retry)

class GeminiClient:
    def __init__(
        self,
        model_name: str,
        api_key: str,
        temperature: float,
        max_output_tokens: Optional[int] = None,
    ):
        """
        :param api_key: 你的 Google AI Studio API Key
        :param model_id: 推荐使用 gemini-1.5-flash (免费额度高且支持长文本)
        """
        self.model_name = model_name
        self.api_key = api_key
        self.client = genai.Client(api_key=self.api_key)
        self.temperature = temperature
        mt = int(max_output_tokens) if max_output_tokens is not None else int(settings.llm_max_tokens)
        self.max_output_tokens = max(512, min(mt, 65536))
        self.files = {}
        self.files_by_id = {}
        
    def _upload_files_parallel(self, file_paths: List[str]):
        """
        内部方法：上传多个文件并确保它们都进入 ACTIVE 状态
        """
        uploaded_files = []
        for path in file_paths:
            if not os.path.exists(path):
                print(f"跳过不存在的文件: {path}")
                continue
            
            print(f"正在上传: {os.path.basename(path)}...")
            file_obj = self.client.files.upload(file=path)
            uploaded_files.append(file_obj)
            self.files[path] = file_obj
            self.files_by_id[getattr(file_obj, "name", str(file_obj))] = file_obj

        # 轮询检查所有文件的状态
        print("等待所有文件处理完成...")
        while True:
            # 检查是否还有文件在 PROCESSING 状态
            states = [self.client.files.get(name=f.name).state.name for f in uploaded_files]
            if all(state == "ACTIVE" for state in states):
                break
            if "FAILED" in states:
                raise RuntimeError("部分文件处理失败。")
            time.sleep(2)
        
        print("\n所有文件处理完成")

        return uploaded_files

    def response(self, prompt: str, file_paths: Union[str, List[str]] = None) -> str:
        """
        上传文件并根据内容进行提问
        """
        contents = []

        if file_paths is not None:
            if isinstance(file_paths, str):
                file_paths = [file_paths]

            file_paths_to_upload = []
            
            for path in file_paths:
                if path in self.files:
                    contents.append(self.files[path])
                else:
                    file_paths_to_upload.append(path)
            
            if file_paths_to_upload:
                uploaded_files = self._upload_files_parallel(file_paths_to_upload)
                contents.extend(uploaded_files)

        contents.append(prompt)

        # 3. 发起对话
        # 传入的 contents 可以是一个列表，包含文件对象和文本 Prompt
        #print("===模型列表===")
        #for model in self.client.models.list():
            #print(f"{model.name:<40}")
        print(f"===调用模型{self.model_name}===")
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=contents,
            config=types.GenerateContentConfig(
                temperature=self.temperature,
                max_output_tokens=self.max_output_tokens,
            ),
        )

        return response.text.strip()


class BaseAgent(ABC):
    """
    Agent 标准抽象基类。

    所有 Agent（SimpleAgent、ReActAgent 等）必须继承此类并实现以下接口：
    - name: Agent 唯一标识名（property）
    - run: 同步推理执行
    - reset: 重置 Agent 内部状态

    ainvoke 提供默认的异步实现（线程池包装 run），子类可按需重写以实现真正的异步推理。

    设计原则：
        工作流节点（workflow/nodes.py）仅依赖 BaseAgent 接口，不依赖具体实现。
        开发者可通过 Mock BaseAgent 独立测试工作流，无需真实 LLM 调用。

    TODO: 未来在此处增加 emotion_hook(message: WorkflowMessage) 情感分析钩子接口
    TODO: 未来在此处增加 before_run / after_run 生命周期钩子，用于中间件拦截
    """
    def __init__(
        self, 
        name: str, 
        system_prompt: str, 
        tools: Optional[List[BaseTool]]
    ):
        self.name = name
        self.system_prompt = system_prompt
        self.tools: List[BaseTool] = tools
        self.tool_args = {}
        self.memory = AgentMemory()
        self.llms = {}
  
    def set_llm(
        self,
        llm_name: str,
        model_name: str,
        api_key: str,
        base_url: str,
        temperature: float,
        max_tokens: Optional[int] = None,
    ) -> None:
        self.llms[llm_name] = LlmClient(
            model_name, api_key, base_url, temperature, max_tokens=max_tokens
        )

    def set_gemini(
        self,
        llm_name: str,
        model_name: str,
        api_key: str,
        temperature: float,
        max_tokens: Optional[int] = None,
    ) -> None:
        self.llms[llm_name] = GeminiClient(
            model_name, api_key, temperature, max_output_tokens=max_tokens
        )    

    def set_tool_args(self, args: dict) -> None:
        for tool_name, tool_args in args.items():
            for arg_name, arg_value in tool_args.items():
                set_nested_value(self.tool_args, [tool_name, arg_name], arg_value)

    def call_tool(self, tool_name: str, tool_args: dict) -> ToolResult:
        """
        调用指定工具，返回工具执行结果。
        """
        target_tool = None
        for tool in self.tools:
            if tool.name == tool_name:
                target_tool = tool
                break
        if target_tool is None:
            raise ValueError(f"工具 {tool_name} 未注册")
        
        tool_args.update(self.tool_args.get(tool_name, {}))

        tool_result = target_tool.run(**tool_args)
        return tool_result

    def _normalize_message(self, message: MessageLike) -> WorkflowMessage:
        """
        将各种输入格式统一转换为 WorkflowMessage 对象。
        
        Args:
            message: 可以是字符串、WorkflowMessage 对象或字典。
            
        Returns:
            标准化的 WorkflowMessage 对象。
        """
        return ensure_message(
            message,
            default_role="user",
            default_source_type="user",
            default_source_id="agent_input",
        )

    @abstractmethod
    def run(self, message: MessageLike) -> WorkflowMessage:
        """
        同步执行推理，接收输入消息并返回 Agent 响应。

        Args:
            message: 输入消息（统一消息对象/字典/字符串）。

        Returns:
            Agent 生成的响应 WorkflowMessage（role="assistant"，source_id=self.name）。

        Raises:
            AgentError: 推理执行失败时抛出。
        """
        pass

    async def ainvoke(self, message: MessageLike) -> WorkflowMessage:
        """
        异步执行推理。

        默认实现将同步 run() 包装在线程池中执行，避免阻塞事件循环。
        子类可重写此方法以实现真正的原生异步推理（如使用 httpx 的异步 LLM 调用）。

        Args:
            message: 输入的 WorkflowMessage 对象。

        Returns:
            Agent 生成的响应 WorkflowMessage。
        """
        pass

    @abstractmethod
    def reset(self) -> None:
        """
        重置 Agent 内部状态（如清空对话历史、工具调用记录等）。
        在开始处理新任务前调用，防止历史上下文污染新任务。
        """
        self.memory.clear()

    def get_history(self) -> List[WorkflowMessage]:
        """
        获取当前 Agent 的对话历史。

        BaseAgent 默认返回空列表，维护历史的子类应重写此方法。

        Returns:
            WorkflowMessage 历史列表（按时间正序）。
        """
        return []
