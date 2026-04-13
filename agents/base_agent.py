"""
BaseAgent 抽象基类。
所有 Agent 实现均继承此类，保证接口统一，支持面向接口编程与 Mock 测试。
"""
from abc import ABC, abstractmethod
from typing import List, Optional, Union
import asyncio
import openai

from core.message import AgentMessage
from tools.base_tool import BaseTool

class AgentMemoryItem:
    """
    Agent 内存项，用于存储单条消息。
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
	def __init__(self, model: str, api_key: str, base_url: str = "https://api.groq.com/openai/v1", temperature: float = 0.2):
		self.model = model
		self.api_key = api_key
		self.client = openai.OpenAI(api_key=api_key, base_url=base_url)
		self.temperature = temperature
		
	def response(self, prompt: str, attachments: Optional[List[dict]] = None) -> str:
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
		
		response = self.client.chat.completions.create(
				model=self.model,
				messages=[
					{"role": "user", "content": message_content}
				],
				temperature=self.temperature,
				max_tokens=4096
			)
		return response.choices[0].message.content.strip()


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

    TODO: 未来在此处增加 emotion_hook(message: AgentMessage) 情感分析钩子接口
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
        self.memory = AgentMemory()
        self.llms = {}
  
    def set_llm(self, llm_name: str, model_name: str, api_key: str, base_url: str, temperature: float) -> None:
        self.llms[llm_name] = LlmClient(model_name, api_key, base_url, temperature) 

    def _normalize_message(self, message: Union[str, AgentMessage, dict]) -> AgentMessage:
        """
        将各种输入格式统一转换为 AgentMessage 对象。
        
        Args:
            message: 可以是字符串、AgentMessage 对象或字典。
            
        Returns:
            标准化的 AgentMessage 对象。
        """
        if isinstance(message, AgentMessage):
            return message
        elif isinstance(message, str):
            return AgentMessage(
                role="user",
                content=message,
                agent_name="user"
            )
        elif isinstance(message, dict):
            return AgentMessage(
                role=message.get("role", "user"),
                content=message.get("content", str(message)),
                agent_name=message.get("agent_name", "unknown")
            )
        else:
            # 兜底处理
            return AgentMessage(
                role="user",
                content=str(message),
                agent_name="unknown"
            )

    @abstractmethod
    def run(self, message: AgentMessage) -> AgentMessage:
        """
        同步执行推理，接收输入消息并返回 Agent 响应。

        Args:
            message: 输入的 AgentMessage 对象（role 通常为 "user"）。

        Returns:
            Agent 生成的响应 AgentMessage（role="assistant"，agent_name=self.name）。

        Raises:
            AgentError: 推理执行失败时抛出。
        """
        pass

    async def ainvoke(self, message: AgentMessage) -> AgentMessage:
        """
        异步执行推理。

        默认实现将同步 run() 包装在线程池中执行，避免阻塞事件循环。
        子类可重写此方法以实现真正的原生异步推理（如使用 httpx 的异步 LLM 调用）。

        Args:
            message: 输入的 AgentMessage 对象。

        Returns:
            Agent 生成的响应 AgentMessage。
        """
        pass

    @abstractmethod
    def reset(self) -> None:
        """
        重置 Agent 内部状态（如清空对话历史、工具调用记录等）。
        在开始处理新任务前调用，防止历史上下文污染新任务。
        """
        self.memory.clear()

    def get_history(self) -> List[AgentMessage]:
        """
        获取当前 Agent 的对话历史。

        BaseAgent 默认返回空列表，维护历史的子类应重写此方法。

        Returns:
            AgentMessage 历史列表（按时间正序）。
        """
        return []
