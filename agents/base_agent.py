"""
BaseAgent 抽象基类。
所有 Agent 实现均继承此类，保证接口统一，支持面向接口编程与 Mock 测试。
"""
from abc import ABC, abstractmethod
from typing import Any, List, Optional, Union
import asyncio
import openai

from core.message import AgentMessage, ToolResult
from tools.base_tool import BaseTool
from tools.file_loading_tool import FileLoadingTool
from utils.utils import set_nested_value

import os
import time
from google import genai
from google.genai import types

class AgentMemoryItem:
    """
    Agent 内存项，用于存储单条消息。
    """

    def __init__(self, data: any, data_type: str):
        """
        Args:
            data: 要存储的原始数据（可为消息、结构化对象或任意运行期信息）
            data_type: 数据类型标签，用于检索与分类（由调用方自定义）
        """
        self.data = data
        self.type = data_type  


class AgentMemory:
    """
    Agent 内存管理类，用于存储和检索 Agent 运行时的状态。
    """

    def __init__(self):
        """
        初始化空内存容器。

        memory 以时间顺序追加；若需要做“最近 N 条”或“按类型汇总”，可在此基础上扩展索引结构。
        """
        self.memory: List[AgentMemoryItem] = []

    def add(self, item: AgentMemoryItem):
        """
        追加一条内存记录。

        Args:
            item: AgentMemoryItem 实例
        """
        self.memory.append(item)

    def clear(self):
        """
        清空全部内存记录。
        """
        self.memory.clear()

    def get(self, item_type: str) -> List[AgentMemoryItem]:
        """
        按类型过滤内存记录。

        Args:
            item_type: 目标类型标签

        Returns:
            匹配类型的 AgentMemoryItem 列表（保持原有插入顺序）。
        """
        return [item for item in self.memory if item.type == item_type]

class LlmClient:
	def __init__(self, model_name: str, api_key: str, base_url: str, temperature: float):
		"""
		OpenAI 兼容接口的 LLM 客户端封装。

		该客户端通过 openai.OpenAI(base_url=...) 连接到兼容 OpenAI Chat Completions 的服务：
		- 可用于 Groq、DashScope compatible-mode 等
		- 支持通过 FileLoadingTool 抽取本地文件文本并注入到 prompt（用于不支持原生文件上传的 API）

		Args:
		    model_name: 模型名
		    api_key: API Key
		    base_url: OpenAI 兼容服务的 base_url
		    temperature: 采样温度
		"""
		self.model_name = model_name
		self.api_key = api_key
		self.client = openai.OpenAI(api_key=api_key, base_url=base_url)
		self.temperature = temperature
		self._file_loader = FileLoadingTool()
		
	def response(
		self,
		prompt: str,
		attachments: Optional[List[dict]] = None,
		file_paths: Union[str, List[str], None] = None,
		*,
		max_file_chars: int = 200000,
	) -> str:
		"""
		生成LLM响应，支持上传附件
		
		Args:
		    prompt: 文本提示
		    attachments: 附件列表，每个附件为包含type和相关信息的字典
		                例如: [{"type": "image_url", "image_url": {"url": "..."}}]
		                或: [{"type": "file", "file": {"file_id": "..."}}]
		    file_paths: 本地文件路径（用于不支持上传文件的 API；会抽取文本并注入 prompt）
		
		Returns:
		    LLM生成的文本响应
		"""
		if file_paths is not None:
			if isinstance(file_paths, str):
				file_paths = [file_paths]

			buf: List[str] = []
			buf.append(prompt)
			buf.append("\n\n以下为本地文件抽取的文本内容（按文件分隔）：\n")

			used = 0
			for p in file_paths:
				r = self._file_loader.run(str(p))
				if not r.success:
					continue
				text = r.output or ""
				remain = max_file_chars - used
				if remain <= 0:
					break
				if len(text) > remain:
					text = text[:remain]
				used += len(text)
				buf.append(f"\n--- FILE: {os.path.basename(str(p))} ---\n{text}\n")

			prompt = "".join(buf)

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
				model=self.model_name,
				messages=[
					{"role": "user", "content": message_content}
				],
				temperature=self.temperature,
				max_tokens=4096
			)
		return response.choices[0].message.content.strip()

class GeminiClient:
    def __init__(self, model_name: str, api_key: str, temperature: float):
        """
        :param api_key: 你的 Google AI Studio API Key
        :param model_id: 推荐使用 gemini-1.5-flash (免费额度高且支持长文本)
        """
        self.model_name = model_name
        self.api_key = api_key
        self.client = genai.Client(api_key=self.api_key)
        self.temperature = temperature
        self.files = {}
        self.files_by_id = {}
        
    def _upload_files_parallel(self, file_paths: List[str], file_mime_types: Optional[dict[str, str]] = None):
        """
        内部方法：上传多个文件并确保它们都进入 ACTIVE 状态。

        Gemini 的文件上传是异步处理的：upload 后文件可能处于 PROCESSING 状态。
        这里会轮询直到全部文件 ACTIVE 才返回，以保证后续 generate_content 可引用文件内容。

        Args:
            file_paths: 要上传的本地文件路径列表
            file_mime_types: 可选 MIME 映射（key 可为完整路径或 basename）
        """
        mime_map = dict(file_mime_types or {})
        uploaded_files = []
        for path in file_paths:
            if not os.path.exists(path):
                print(f"跳过不存在的文件: {path}")
                continue
            
            print(f"正在上传: {os.path.basename(path)}...")
            mime_type = mime_map.get(path) or mime_map.get(os.path.basename(path))
            ext = os.path.splitext(path)[1].lower()
            if not mime_type and ext == ".tex":
                mime_type = "text/plain"
            if (mime_type or "").lower() in {"application/x-tex", "text/x-tex"}:
                mime_type = "text/plain"
            try:
                if mime_type:
                    try:
                        file_obj = self.client.files.upload(file=path, mime_type=mime_type)
                    except TypeError:
                        file_obj = self.client.files.upload(file=path, mimeType=mime_type)
                else:
                    file_obj = self.client.files.upload(file=path)
            except TypeError:
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

    def response(
        self,
        prompt: str,
        file_paths: Union[str, List[str]] = None,
        file_mime_types: Union[str, List[str], dict[str, str], None] = None,
    ) -> str:
        """
        上传文件并根据内容进行提问。

        Args:
            prompt: 文本提示词
            file_paths: 可选文件路径（单个路径或列表）；传入后会先上传文件再调用模型
            file_mime_types:
                - str: 所有 file_paths 统一使用该 MIME
                - list[str]: 与 file_paths 一一对应
                - dict[str,str]: key 为 path 或 basename，value 为 MIME

        Returns:
            模型输出文本（response.text）

        说明：
        - 由于 Gemini 官方未把 .tex 列为独立大类，但它本质是文本，本实现会把 .tex 默认按 text/plain 上传，
          同时把 application/x-tex 与 text/x-tex 映射到 text/plain，以避免不被支持的 MIME 类型导致上传失败。
        """
        contents = []

        if file_paths is not None:
            if isinstance(file_paths, str):
                file_paths = [file_paths]

            mime_map: dict[str, str] = {}
            if isinstance(file_mime_types, str) and file_mime_types.strip():
                for p in file_paths:
                    mime_map[p] = file_mime_types.strip()
            elif isinstance(file_mime_types, list):
                for p, m in zip(file_paths, file_mime_types):
                    if isinstance(m, str) and m.strip():
                        mime_map[p] = m.strip()
            elif isinstance(file_mime_types, dict):
                for k, v in file_mime_types.items():
                    if isinstance(k, str) and isinstance(v, str) and v.strip():
                        mime_map[k] = v.strip()

            file_paths_to_upload = []
            
            for path in file_paths:
                if path in self.files:
                    contents.append(self.files[path])
                else:
                    file_paths_to_upload.append(path)
            
            if file_paths_to_upload:
                uploaded_files = self._upload_files_parallel(file_paths_to_upload, file_mime_types=mime_map)
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
                    #max_output_tokens=8192 # 综述任务建议调大输出上限
                )
        )

        return response.text.strip()


class QwenClient:
    def __init__(
        self,
        model_name: str,
        api_key: str,
        temperature: float,
        *,
        base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1",
        file_purpose: str = "file-extract",
        max_file_chars: int = 200000,
        upload_wait_seconds: int = 99999999,
    ):
        """
        DashScope OpenAI 兼容通道的 Qwen 客户端封装。

        特点：
        - 使用 OpenAI compatible-mode 的 files.create 上传文件
        - 通过 system message 注入 fileid://... 让模型在对话中引用文件内容

        Args:
            model_name: 模型名
            api_key: API Key
            temperature: 采样温度
            base_url: OpenAI 兼容服务地址
            file_purpose: 上传文件用途字段
            max_file_chars: 作为纯文本注入时的最大字符数（保留参数，便于扩展）
            upload_wait_seconds: 轮询等待文件可用的最大秒数（<=0 表示不等待）
        """
        self.model_name = model_name
        self.api_key = api_key
        self.base_url = base_url
        self.temperature = temperature
        self.file_purpose = file_purpose
        self.max_file_chars = int(max_file_chars or 0)
        self.upload_wait_seconds = int(upload_wait_seconds or 0)
        self.client = openai.OpenAI(api_key=api_key, base_url=base_url)
        self.files: dict[str, Any] = {}
        self._file_loader = FileLoadingTool()

    def _upload_files(self, file_paths: List[str]) -> List[Any]:
        """
        上传文件并缓存结果。

        Args:
            file_paths: 本地文件路径列表

        Returns:
            已上传的文件对象列表（与输入顺序一致；不存在的文件会被跳过）。
        """
        uploaded: List[Any] = []
        for path in file_paths:
            if not os.path.exists(path):
                continue
            if path in self.files:
                uploaded.append(self.files[path])
                continue
            with open(path, "rb") as f:
                file_obj = self.client.files.create(file=f, purpose=self.file_purpose)
            self.files[path] = file_obj
            uploaded.append(file_obj)
        print(f"QwenClient: 上传 {len(uploaded)} 个文件")
        return uploaded

    def _wait_files_ready(self, uploaded: List[Any]) -> None:
        """
        轮询等待上传文件进入可用状态。

        说明：
        - 不同平台的状态字段可能不同，因此这里做了尽量兼容的 status/state 读取。
        - 遇到 FAILED/ERROR 会停止等待并返回（调用方可选择继续或报错）。
        """
        if self.upload_wait_seconds <= 0 or not uploaded:
            return
        deadline = time.time() + self.upload_wait_seconds
        pending: list[str] = []
        for f in uploaded:
            fid = getattr(f, "id", None) or getattr(f, "file_id", None)
            if fid:
                pending.append(str(fid))
        if not pending:
            return
        remaining = set(pending)
        while remaining and time.time() < deadline:
            done: set[str] = set()
            for fid in list(remaining):
                try:
                    info = self.client.files.retrieve(fid)
                except Exception:
                    continue
                status = getattr(info, "status", None) or getattr(getattr(info, "state", None), "name", None) or getattr(info, "state", None)
                if status is None:
                    continue
                s = str(status).upper()
                if s in {"ACTIVE", "SUCCEEDED", "SUCCESS", "PROCESSED", "READY"}:
                    done.add(fid)
                if s in {"FAILED", "ERROR"}:
                    done.add(fid)
            remaining -= done
            if remaining:
                time.sleep(2)

    def response(self, prompt: str, file_paths: Union[str, List[str], None] = None, **_: Any) -> str:
        """
        生成模型回复，并可选上传文件供模型引用。

        Args:
            prompt: 用户提示词
            file_paths: 可选文件路径（单个或列表）

        Returns:
            模型输出文本。
        """
        if file_paths is not None and isinstance(file_paths, str):
            file_paths = [file_paths]

        messages: List[dict[str, Any]] = []
        if file_paths:
            uploaded = self._upload_files(file_paths)
            self._wait_files_ready(uploaded)
            for f in uploaded:
                fid = getattr(f, "id", None) or getattr(f, "file_id", None)
                if fid:
                    messages.append({"role": "system", "content": f"fileid://{fid}"})
                    print(f"QwenClient: 上传文件 {fid} 完成")
        messages.append({"role": "user", "content": prompt})
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            temperature=self.temperature,
            max_tokens=4096,
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
        """
        初始化 Agent 基类属性。

        Args:
            name: Agent 名称/标识
            system_prompt: system 级提示词
            tools: 可调用的工具实例列表
        """
        self.name = name
        self.system_prompt = system_prompt
        self.tools: List[BaseTool] = tools
        self.tool_args = {}
        self.memory = AgentMemory()
        self.llms = {}
  
    def set_llm(self, llm_name: str, model_name: str, api_key: str, base_url: str, temperature: float) -> None:
        """
        注册一个 OpenAI 兼容通道的 LlmClient。
        """
        self.llms[llm_name] = LlmClient(model_name, api_key, base_url, temperature) 

    def set_gemini(self, llm_name: str, model_name: str, api_key: str, temperature: float) -> None:
        """
        注册一个 GeminiClient。
        """
        self.llms[llm_name] = GeminiClient(model_name, api_key, temperature)    

    def set_qwen(self, llm_name: str, model_name: str, api_key: str, temperature: float, base_url: str = "") -> None:
        """
        注册一个 QwenClient（OpenAI compatible-mode）。
        """
        self.llms[llm_name] = QwenClient(
            model_name=model_name,
            api_key=api_key,
            temperature=temperature,
            base_url=base_url or "https://dashscope.aliyuncs.com/compatible-mode/v1",
        )

    def set_tool_args(self, args: dict) -> None:
        """
        设置工具默认参数（按工具名组织）。

        该默认参数会在 call_tool 时与调用方传入的参数合并，用于统一注入路径、API key 等配置。
        """
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
