"""
SimpleAgent：最基础的可运行 Agent 实现。
接收输入消息 → 调用 LLM → 返回响应，支持工具列表注入与有界多轮对话历史维护。
"""
from typing import List, Optional, Union
import asyncio

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

from agents.base_agent import BaseAgent
from core.message import AgentMessage
from core.exceptions import AgentError
from tools.base_tool import BaseTool
from config.settings import settings
from utils.logger import get_logger

logger = get_logger(__name__)


class SimpleAgent(BaseAgent):
    """
    基础 Agent 实现，封装 LangChain ChatOpenAI 调用。

    特性：
    - 维护有界多轮对话历史，每次 run() 都将历史消息拼入 LLM 请求。
    - 支持工具列表注入（MVP 中工具结果需手动传入 prompt，后续可升级为 ToolCalling）。
    - 懒加载 LLM 实例，避免导入时因 API Key 未配置而报错。

    Args:
        name: Agent 唯一标识名（如 "DesignAgent"）。
        system_prompt: LLM 的 system 角色提示词。
        tools: 可用工具列表（BaseTool 子类实例），默认为空。
        temperature: LLM 温度，覆盖全局配置；None 则使用全局配置值。
        model: LLM 模型名，覆盖全局配置；None 则使用全局配置值。
        max_history: 对话历史最大保留条数（含用户和 AI 消息）。
                     None 表示不限制（慎用，长对话会超出 Token 限制）。
                     默认 100 条，约等于 50 轮对话。
    """

    def __init__(
        self,
        name: str,
        system_prompt: str,
        tools: Optional[List[BaseTool]] = None,
        temperature: Optional[float] = None,
        model: Optional[str] = None,
        max_history: Optional[int] = 100,
    ):
        self._name = name
        self.system_prompt = system_prompt
        self.tools: List[BaseTool] = tools or []
        self.temperature = temperature if temperature is not None else settings.llm_temperature
        self.model = model or settings.llm_model
        self.max_history = max_history
        self._llm: Optional[ChatOpenAI] = None  # 懒加载
        self._history: List[AgentMessage] = []

    @property
    def name(self) -> str:
        return self._name

    def _get_llm(self) -> ChatOpenAI:
        """懒加载并返回 LLM 实例，首次调用时初始化。"""
        if self._llm is None:
            if not settings.openai_api_key:
                logger.warning(
                    "OPENAI_API_KEY 未配置，LLM 调用将失败。请检查 .env 文件。"
                )
            self._llm = ChatOpenAI(
                model=self.model,
                temperature=self.temperature,
                openai_api_key=settings.openai_api_key or "placeholder",
                base_url=settings.openai_base_url,
                max_tokens=settings.llm_max_tokens,
                timeout=settings.llm_timeout,
                max_retries=settings.llm_max_retries,
            )
        return self._llm

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

    def _build_lc_messages(self, message: AgentMessage) -> list:
        """
        将对话历史与当前消息转换为 LangChain 消息格式列表。

        构建顺序：[SystemMessage] + [历史消息...] + [当前 HumanMessage]
        """
        lc_messages = [SystemMessage(content=self.system_prompt)]
        for hist in self._history:
            if hist.role in ("user", "human"):
                lc_messages.append(HumanMessage(content=hist.content))
            elif hist.role in ("assistant", "ai"):
                lc_messages.append(AIMessage(content=hist.content))
            # system / tool 消息暂不加入历史，避免 LLM 混淆
        lc_messages.append(HumanMessage(content=message.content))
        return lc_messages

    def _trim_history(self) -> None:
        """若历史超出 max_history 上限，丢弃最旧的消息（保持偶数对齐）。"""
        if self.max_history is None:
            return
        if len(self._history) > self.max_history:
            # 从头部裁剪，同时保持 user/assistant 消息对的完整性（步长 2）
            excess = len(self._history) - self.max_history
            # 向上取整到偶数，确保不破坏对话轮次边界
            excess = excess + (excess % 2)
            self._history = self._history[excess:]

    def run(self, message: Union[str, AgentMessage, dict]) -> AgentMessage:
        """
        同步执行推理。

        Args:
            message: 用户/上游节点发送的消息，可以是：
                    - 字符串：自动转换为 AgentMessage
                    - AgentMessage 对象：直接使用
                    - 字典：根据字段转换为 AgentMessage

        Returns:
            LLM 生成的响应 AgentMessage（role="assistant"）。

        Raises:
            AgentError: LLM 调用失败或返回异常时抛出。
        """
        # 1. 标准化输入消息
        normalized_msg = self._normalize_message(message)
        
        # 2. 日志记录（安全截取）
        content_preview = normalized_msg.content[:80] + "..." if len(normalized_msg.content) > 80 else normalized_msg.content
        logger.debug(f"[{self._name}] 接收消息: {content_preview}")
        
        try:
            # 3. 调用 LLM
            llm = self._get_llm()
            lc_messages = self._build_lc_messages(normalized_msg)
            response = llm.invoke(lc_messages)

            # 4. 构建响应消息
            result = AgentMessage(
                role="assistant",
                content=response.content,
                agent_name=self._name,
            )

            # 5. 更新对话历史（用于下一轮 run() 时构建上下文）并按上限裁剪
            self._history.append(normalized_msg)
            self._history.append(result)
            self._trim_history()

            logger.debug(f"[{self._name}] 响应生成完毕，长度: {len(result.content)} 字符")

            # TODO: 未来在此处接入 Tool Calling 逻辑（解析 LLM 的工具调用意图并执行）
            # TODO: 未来在此处接入情感分析 Hook（感知用户情绪状态）

            return result

        except AgentError:
            # 已经是业务异常，直接向上传播，避免双重包装
            raise
        except Exception as e:
            logger.error(f"[{self._name}] LLM 调用失败: {e}")
            raise AgentError(f"Agent '{self._name}' 执行失败: {e}") from e

    async def ainvoke(self, message: Union[str, AgentMessage, dict]) -> AgentMessage:
        """异步执行推理（在线程池中运行同步 LLM 调用，不阻塞事件循环）。"""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.run, message)

    def reset(self) -> None:
        """清空对话历史，重置 Agent 为初始状态。"""
        self._history.clear()
        logger.debug(f"[{self._name}] 对话历史已清空")

    def get_history(self) -> List[AgentMessage]:
        """获取完整的对话历史副本。"""
        return list(self._history)