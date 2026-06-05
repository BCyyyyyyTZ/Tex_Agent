import base64
import json
import os
import re
import sys
import time
import uuid
import zlib
from pathlib import Path
from typing import Optional

import httpx

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents.base_agent import GeminiClient
from core.message import ToolResult
from tools.base_tool import BaseTool
from utils.logger import get_logger

logger = get_logger(__name__)


class ConceptDiagramTool(BaseTool):
    def __init__(
        self,
        *,
        model_name: str = "gemini-3.1-flash-lite",
        api_key: str = "",
        temperature: float = 0.2,
    ):
        super().__init__(
            name="concept_diagram",
            description="输入概念描述，调用 Gemini 生成 Mermaid 结构化代码并渲染为学术风格概念示意图，输出图片路径。",
            input_schema={
                "prompt": "必填，概念描述或需要图示化的内容",
                "output_path": "必填，输出图片路径，例如 'outputs/diagram.png'",
                "title": "可选，图标题",
                "mermaid_code": "可选，直接提供 Mermaid 代码（跳过 Gemini）",
            },
        )
        self.model_name = model_name
        self.api_key = api_key
        self.temperature = float(temperature)

    def _resolve_api_key(self, api_key: str) -> str:
        return (
            api_key
            or self.api_key
            or os.getenv("GEMINI_API_KEY")
            or os.getenv("GOOGLE_API_KEY")
            or ""
        )

    def _build_prompt(self, user_prompt: str, title: str) -> str:
        t = (title or "").strip()
        title_line = f"标题：{t}\n" if t else ""
        return (
            "你是一个论文写作助手，负责把概念内容转换成学术风格的概念示意图。\n"
            "输出必须是 Mermaid 代码本体，禁止输出 Markdown 代码块标记、解释文字或任何额外内容。\n"
            "要求：\n"
            "1) 仅输出一段 Mermaid 代码，以 flowchart 开头。\n"
            "2) 使用简洁节点文本，避免标点符号、引号、括号与特殊字符；尽量使用短语。\n"
            "3) 图结构清晰，层级分明，适合论文排版。\n"
            "4) 不要使用 emoji。\n"
            "5) 默认方向为 TB。\n\n"
            f"{title_line}"
            f"需要图示化的内容：\n{user_prompt}\n"
        )

    def _extract_mermaid(self, text: str) -> str:
        s = (text or "").strip()
        if not s:
            return ""
        s = re.sub(r"^```(?:mermaid)?\s*", "", s, flags=re.IGNORECASE)
        s = re.sub(r"\s*```$", "", s, flags=re.IGNORECASE)
        return s.strip()

    def _encode_mermaid_ink(self, mermaid_code: str) -> str:
        payload = json.dumps(
            {"code": mermaid_code, "mermaid": {"theme": "neutral"}},
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        compressed = zlib.compress(payload, level=9)
        encoded = base64.b64encode(compressed).decode("ascii")
        encoded = encoded.replace("+", "-").replace("/", "_")
        return f"pako:{encoded}"

    def _render_with_mermaid_ink(self, mermaid_code: str, output_path: Path) -> None:
        encoded = self._encode_mermaid_ink(mermaid_code)
        url = f"https://mermaid.ink/img/{encoded}?type=png&theme=neutral&bgColor=!white"
        timeout = httpx.Timeout(60.0, connect=10.0)
        last_err: Exception | None = None
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            for i in range(3):
                try:
                    r = client.get(url, headers={"Accept": "image/png,image/*"})
                    r.raise_for_status()
                    output_path.write_bytes(r.content)
                    return
                except Exception as e:
                    last_err = e
                    if i < 2:
                        time.sleep(1.0 * (2**i))
                        continue
                    raise last_err

    def run(
        self,
        prompt: str = "",
        output_path: str = "",
        title: str = "",
        mermaid_code: str = "",
    ) -> ToolResult:
        try:
            if not output_path:
                return ToolResult(success=False, output="", error="output_path 不能为空")

            out = Path(output_path)
            out.parent.mkdir(parents=True, exist_ok=True)

            manual = self._extract_mermaid(mermaid_code)
            if manual:
                code = manual
            else:
                if not prompt:
                    return ToolResult(success=False, output="", error="prompt 不能为空（或直接提供 mermaid_code）")

                api_key = self._resolve_api_key("")
                if not api_key:
                    return ToolResult(
                        success=False,
                        output="",
                        error="未配置 GEMINI_API_KEY 或 GOOGLE_API_KEY。调试时可直接在 mermaid_code 字段粘贴 Mermaid 代码。",
                    )

                llm = GeminiClient(model_name=self.model_name, api_key=api_key, temperature=self.temperature)
                llm_prompt = self._build_prompt(prompt, title)
                raw = llm.response(llm_prompt)
                code = self._extract_mermaid(raw)

            if not code.lower().lstrip().startswith(("flowchart", "graph")):
                return ToolResult(
                    success=False,
                    output="",
                    error="不是有效的 Mermaid flowchart 代码（需以 flowchart 或 graph 开头）",
                    metadata={"mermaid_code": code},
                )

            self._render_with_mermaid_ink(code, out)
            if not out.exists() or out.stat().st_size <= 0:
                return ToolResult(success=False, output="", error="图片生成失败：输出文件为空")

            return ToolResult(
                success=True,
                output=str(out),
                metadata={
                    "output_path": str(out),
                    "model_name": self.model_name if not manual else "",
                    "render_backend": "mermaid.ink",
                    "mermaid_code": code,
                    "title": title,
                },
            )
        except Exception as e:
            logger.error(f"ConceptDiagramTool 失败: {e}")
            return ToolResult(success=False, output="", error=f"ConceptDiagramTool 失败: {e}")


def web_tool_output_dir() -> Path:
    root = Path(__file__).resolve().parents[1]
    d = root / "outputs" / "web_tool_outputs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def unique_output_path(prefix: str, ext: str = ".png") -> Path:
    safe_ext = ext if ext.startswith(".") else f".{ext}"
    name = f"{prefix}_{uuid.uuid4().hex[:12]}{safe_ext}"
    return web_tool_output_dir() / name
