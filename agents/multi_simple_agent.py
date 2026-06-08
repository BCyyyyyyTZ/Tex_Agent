from typing import Any, Dict, List, Optional, Union
import asyncio
import os
from pathlib import Path

from agents.base_agent import BaseAgent
from core.exceptions import AgentError
from core.message import MessageLike, WorkflowMessage
from tools.base_tool import BaseTool
from utils.logger import get_logger

logger = get_logger(__name__)

DEFAULT_SYSTEM_PROMPT = "你是专业的多模态论文审查助手。"
DEFAULT_TEMPERATURE = 0.1


class MultiSimpleAgent(BaseAgent):
    """
    Gemini 多模态 Agent：
    - 支持 attachment 为：
      1) 上游 gemini_upload_pdf 输出的文件引用(dict)
      2) 本地路径(相对项目根 / 绝对路径)，自动上传
      3) 混合 list
    """

    def __init__(
        self,
        name: str,
        system_prompt: Optional[str] = None,
        tools: Optional[List[BaseTool]] = None,
        model_name: Optional[str] = None,
        api_key: Optional[str] = None,
        temperature: Optional[float] = None,
        max_history: int = 50,
    ):
        super().__init__(name, system_prompt or DEFAULT_SYSTEM_PROMPT, tools or [])
        self.project_root = Path(__file__).resolve().parent.parent
        self.model_name = model_name or os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or ""
        self.temperature = float(DEFAULT_TEMPERATURE if temperature is None else temperature)
        self.max_history = max_history
        self.history: List[WorkflowMessage] = []

        if not self.api_key:
            raise AgentError(f"{self.name} 启动失败：未配置 GEMINI_API_KEY/GOOGLE_API_KEY")

        try:
            from google import genai
            from google.genai import types
            self._genai = genai
            self._types = types
            self.client = genai.Client(api_key=self.api_key)
        except Exception as e:
            raise AgentError(f"{self.name} 启动失败：无法导入 google-genai: {e}") from e

        self._path_cache: Dict[str, Any] = {}

    def _resolve_path(self, p: str) -> str:
        p = (p or "").strip().strip('"').strip("'")
        if not p:
            return ""
        path = Path(p)
        if path.is_absolute():
            return str(path.resolve())
        return str((self.project_root / path).resolve())

    def _upload_local_pdf(self, file_path: str):
        abs_path = self._resolve_path(file_path)
        if not abs_path or not os.path.isfile(abs_path):
            raise AgentError(f"{self.name} 附件文件不存在: {abs_path}")

        if abs_path in self._path_cache:
            return self._path_cache[abs_path]

        uploaded = self.client.files.upload(
            file=abs_path,
            config={"mime_type": "application/pdf", "display_name": Path(abs_path).name},
        )
        name = getattr(uploaded, "name", "")
        if not name:
            raise AgentError(f"{self.name} 上传文件失败：未返回 name")

        # wait ACTIVE
        import time
        start = time.time()
        while True:
            f = self.client.files.get(name=name)
            state = getattr(getattr(f, "state", None), "name", str(getattr(f, "state", "")))
            state = (state or "").upper()
            if state == "ACTIVE":
                self._path_cache[abs_path] = f
                return f
            if state == "FAILED":
                raise AgentError(f"{self.name} 上传文件处理失败: {name}")
            if time.time() - start > 180:
                raise AgentError(f"{self.name} 上传文件等待 ACTIVE 超时: {name}")
            time.sleep(2)

    def _file_ref_to_obj(self, ref: Dict[str, Any]):
        """
        支持 gemini_upload_pdf 输出引用：
        {"type":"gemini_file","name":"files/xxx", ...}
        """
        name = str(ref.get("name", "") or "").strip()
        if name:
            return self.client.files.get(name=name)

        # 兼容 path 字段
        p = ref.get("path") or ref.get("file_path") or ref.get("abs_path")
        if p:
            return self._upload_local_pdf(str(p))

        raise AgentError(f"{self.name} 无法识别的附件引用: {ref}")

    def _normalize_attachments(self, attachment: Any) -> List[Any]:
        if attachment is None:
            return []

        items = attachment if isinstance(attachment, list) else [attachment]
        out: List[Any] = []

        for it in items:
            if isinstance(it, dict):
                # gemini 已上传引用
                if (it.get("type") == "gemini_file") or it.get("name") or it.get("abs_path") or it.get("path"):
                    out.append(self._file_ref_to_obj(it))
                else:
                    logger.warning(f"[{self.name}] 跳过未知 dict 附件: {it}")
                continue

            if isinstance(it, str):
                s = it.strip()
                if not s:
                    continue
                # 兼容直接传 files/xxx
                if s.startswith("files/"):
                    out.append(self.client.files.get(name=s))
                    continue
                # 本地路径
                out.append(self._upload_local_pdf(s))
                continue

            logger.warning(f"[{self.name}] 跳过未知附件类型: {type(it)}")

        return out

    def _trim_history(self):
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]

    def run(self, message: MessageLike) -> WorkflowMessage:
        normalized = self._normalize_message(message)
        self.history.append(normalized)

        attachment = normalized.metadata.get("attachment")
        file_parts = self._normalize_attachments(attachment)

        # Gemini contents：文件对象 + 文本 prompt
        contents: List[Any] = []
        contents.extend(file_parts)
        contents.append(normalized.content)

        try:
            resp = self.client.models.generate_content(
                model=self.model_name,
                contents=contents,
                config=self._types.GenerateContentConfig(
                    temperature=self.temperature,
                ),
            )
            text = (getattr(resp, "text", None) or "").strip()
            if not text:
                text = str(resp)

            out = WorkflowMessage(
                role="assistant",
                source_type="agent",
                source_id=self.name,
                content=text,
            )
            self.history.append(out)
            self._trim_history()
            return out
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