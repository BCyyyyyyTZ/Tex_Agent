import json
import os
import time
from pathlib import Path
from typing import Dict

from core.message import ToolResult
from tools.base_tool import BaseTool


class GeminiUploadPdfTool(BaseTool):
    """
    上传 PDF 到 Gemini Files API，并等待 ACTIVE。
    输出 metadata.gemini_file 可直接给 MultiSimpleAgent 的 attachment 使用。
    """

    def __init__(self):
        super().__init__(
            name="gemini_upload_pdf",
            description="上传本地 PDF 到 Gemini Files API 并返回文件引用信息。",
            input_schema={"pdf_path": "PDF 的绝对路径或相对项目根路径"},
        )
        self.project_root = Path(__file__).resolve().parent.parent
        self._cache: Dict[str, Dict[str, str]] = {}
        self._client = None

    def _get_client(self):
        if self._client is not None:
            return self._client
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or ""
        if not api_key:
            raise RuntimeError("未配置 GEMINI_API_KEY/GOOGLE_API_KEY")
        from google import genai  # 延迟导入，避免未安装时影响其他功能
        self._client = genai.Client(api_key=api_key)
        return self._client

    def _abs(self, p: str) -> str:
        p = (p or "").strip().strip('"').strip("'")
        if not p:
            return ""
        path = Path(p)
        if path.is_absolute():
            return str(path.resolve())
        return str((self.project_root / path).resolve())

    def _wait_active(self, name: str, timeout_sec: int = 180, interval_sec: float = 2.0):
        client = self._get_client()
        start = time.time()
        while True:
            f = client.files.get(name=name)
            state = getattr(getattr(f, "state", None), "name", str(getattr(f, "state", "")))
            state = (state or "").upper()
            if state == "ACTIVE":
                return f
            if state == "FAILED":
                raise RuntimeError(f"Gemini 文件处理失败: {name}")
            if time.time() - start > timeout_sec:
                raise TimeoutError(f"等待 Gemini 文件 ACTIVE 超时: {name}")
            time.sleep(interval_sec)

    def run(self, pdf_path: str) -> ToolResult:
        try:
            abs_path = self._abs(pdf_path)
            if not abs_path or not os.path.isfile(abs_path):
                return ToolResult(success=False, output="", error=f"PDF 不存在: {abs_path}")

            # 先用缓存
            if abs_path in self._cache:
                ref = self._cache[abs_path]
                return ToolResult(
                    success=True,
                    output=json.dumps(ref, ensure_ascii=False),
                    metadata={"gemini_file": ref, "pdf_abs_path": abs_path},
                )

            client = self._get_client()
            uploaded = client.files.upload(
                file=abs_path,
                config={"mime_type": "application/pdf", "display_name": Path(abs_path).name},
            )
            name = getattr(uploaded, "name", "")
            if not name:
                raise RuntimeError("Gemini 上传成功但未返回文件 name")

            active_file = self._wait_active(name=name)
            ref = {
                "type": "gemini_file",
                "name": getattr(active_file, "name", name),
                "uri": getattr(active_file, "uri", ""),
                "mime_type": getattr(active_file, "mime_type", "application/pdf"),
                "display_name": Path(abs_path).name,
                "abs_path": abs_path,
            }
            self._cache[abs_path] = ref

            return ToolResult(
                success=True,
                output=json.dumps(ref, ensure_ascii=False),
                metadata={"gemini_file": ref, "pdf_abs_path": abs_path},
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))