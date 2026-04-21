"""
SimpleAgent：纯 LLM 节点实现（不执行工具）。
职责：接收输入消息 -> 调用 LLM -> 返回 assistant 文本结果。
"""
from typing import Any, List, Optional
import asyncio
import os
from datetime import datetime
from pathlib import Path

from agents.base_agent import BaseAgent
from core.message import WorkflowMessage, MessageLike
from core.exceptions import AgentError
from tools.base_tool import BaseTool
from config.settings import settings
from utils.logger import get_logger
from tools.tool_list import tool_list

logger = get_logger(__name__)
_LLM_TRACE_PATH = Path(__file__).resolve().parent.parent / "logs" / "llm_interactions_trace.txt"

DEFAULT_TEMPERATURE = 0.2
DEFAULT_SYSTEM_PROMPT = "你是一个专业、可靠、直接给出可执行结果的助手。"


class SimpleAgent(BaseAgent):
    """
    纯推理 Agent，不负责工具调用。
    注意：工具调用应由 workflow 的 tool 节点处理。
    """

    def __init__(
        self,
        name: str,
        system_prompt: Optional[str] = None,
        tools: Optional[List[BaseTool]] = None,
        model_name: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        temperature: Optional[float] = None,
        max_history: int = 100,
    ):
        if tools is None:
            tools = tool_list
        super().__init__(name, system_prompt or DEFAULT_SYSTEM_PROMPT, tools)

        self.model_name = model_name or settings.llm_model
        self.temperature = float(
            settings.llm_temperature if temperature is None else temperature
        )
        if self.temperature <= 0:
            self.temperature = DEFAULT_TEMPERATURE

        self.openai_api_key = api_key or settings.openai_api_key
        self.openai_base_url = base_url or settings.openai_base_url
        self.gemini_api_key = (
            os.getenv("GEMINI_API_KEY")
            or os.getenv("GOOGLE_API_KEY")
            or ""
        )

        self.backend = self._init_backend()
        self.history: List[WorkflowMessage] = []
        self.max_history = max_history

    def _init_backend(self) -> str:
        model_lower = (self.model_name or "").lower()
        wants_gemini = "gemini" in model_lower

        if wants_gemini and self.gemini_api_key:
            self.set_gemini("llm", self.model_name, self.gemini_api_key, self.temperature)
            return "gemini"

        if self.openai_api_key:
            self.set_llm(
                "llm",
                self.model_name,
                self.openai_api_key,
                self.openai_base_url,
                self.temperature,
            )
            if wants_gemini:
                logger.warning(
                    f"[{self.name}] 检测到 Gemini 模型名但未配置 GEMINI_API_KEY，已回退 OpenAI 兼容通道"
                )
            return "openai"

        if wants_gemini:
            raise AgentError(
                f"{self.name} 启动失败：模型 {self.model_name} 需要 GEMINI_API_KEY 或 GOOGLE_API_KEY"
            )
        raise AgentError(
            f"{self.name} 启动失败：未配置可用 API Key（OPENAI_API_KEY / GEMINI_API_KEY）"
        )

    def _build_history_messages(self) -> List[str]:
        messages = [f"SYSTEM\n{self.system_prompt}"]
        for hist in self.history:
            if hist.role == "user":
                messages.append(f"USER\n{hist.content}")
            elif hist.role == "assistant":
                messages.append(f"ASSISTANT\n{hist.content}")
            elif hist.role == "tool":
                messages.append(f"TOOL:{hist.tool_name}\n{hist.content}")
        return messages

    def _trim_history(self) -> None:
        if self.max_history is None:
            return
        if len(self.history) > self.max_history:
            excess = len(self.history) - self.max_history
            excess = excess + (excess % 2)
            self.history = self.history[excess:]

    def _append_llm_trace(self, history_messages: List[str], response_text: str) -> None:
        try:
            _LLM_TRACE_PATH.parent.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().isoformat(timespec="seconds")
            serialized = [f"[{i}] {m}" for i, m in enumerate(history_messages, start=1)]
            block = (
                "\n" + "=" * 88 + "\n"
                f"[{ts}] agent={self.name} backend={self.backend} model={self.model_name}\n"
                "\n[llm_messages]\n"
                + "\n\n".join(serialized)
                + "\n[llm_response]\n"
                + str(response_text)
                + "\n"
                + "=" * 88 + "\n"
            )
            with _LLM_TRACE_PATH.open("a", encoding="utf-8") as f:
                f.write(block)
        except Exception as e:
            logger.error(f"[{self.name}] 写入 LLM 交互日志失败: {e}")

    def _normalize_attachment(self, attachment: Any) -> Any:
        # Gemini 通道支持文件路径；OpenAI 兼容通道忽略本地附件
        if self.backend == "gemini":
            return attachment
        if attachment:
            logger.warning(f"[{self.name}] OpenAI 兼容通道暂不支持本地附件，已忽略 attachment")
        return None

    def run(self, message: MessageLike) -> WorkflowMessage:
        self.reset()
        normalized_msg = self._normalize_message(message)
        self.history.append(normalized_msg)

        # 保留 set_tool_args 兼容能力，但 SimpleAgent 本身不执行工具
        tool_args = normalized_msg.metadata.get("tool_args")
        if tool_args is not None:
            self.set_tool_args(tool_args)
        attachment = self._normalize_attachment(normalized_msg.metadata.get("attachment"))

        try:
            history_messages = self._build_history_messages()
            prompt = "\n\n".join(history_messages)
            llm_content = self.llms["llm"].response(prompt, attachment).strip()
            self._append_llm_trace(history_messages, llm_content)

            result = WorkflowMessage(
                role="assistant",
                source_type="agent",
                source_id=self.name,
                content=llm_content,
            )
            self.history.append(result)
            self._trim_history()
            return result
        except AgentError:
            raise
        except Exception as e:
            logger.error(f"[{self.name}] 执行失败: {e}")
            raise AgentError(f"{self.name} 执行失败: {e}") from e

    async def ainvoke(self, message: MessageLike) -> WorkflowMessage:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.run, message)

    def reset(self) -> None:
        self.history.clear()

    def get_history(self) -> List[WorkflowMessage]:
        return list(self.history)